import logging
import resource
import collections
import config
import datetime
import csv
import locale

def init():
	locale.setlocale(locale.LC_ALL, 'de_DE.UTF-8')
	logging.basicConfig(
		format = '[%(asctime)s:%(levelname)s:%(module)s] %(message)s',
		datefmt = '%y-%m-%d-%H-%M-%S',
		level = logging.DEBUG)

def memory_check():
	memory = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e3
	logging.debug('using {:.0f} megabytes of memory'.format(memory))
	if memory > 100:
		raise Exception('memory leak')

def timestamp(date_time):
	return float('{:%s}'.format(date_time)) + date_time.microsecond / 1e6

def bool_string(boolean):
	if boolean is None:
		return 'Fehler'
	return 'Ein' if boolean else 'Aus'

class Measurement(collections.namedtuple('Measurement', 'value timestamp')):
	__slots__ = ()
	def __str__(self):
		return '{:.1f} °C um {:%H:%M} Uhr'.format(self.value, self.timestamp)

class Record:
	def __init__(self, name, period, parser):
		self.csv = '{}.csv'.format(name)
		self.period = period
		self.parser = parser
		self.value = collections.deque()
		self.timestamp = collections.deque()
	def __len__(self):
		return len(self.value)
	def __getitem__(self, key):
		return Measurement(self.value[key], self.timestamp[key])
	def __nonzero__(self):
		return bool(self.value)
	def append(self, value, timestamp):
		if not self.value or timestamp > self.timestamp[-1]:
			self.value.append(value)
			self.timestamp.append(timestamp)
			assert len(self.value) == len(self.timestamp)
	def clear(self, now):
		while self.value and self.timestamp[0] < now - self.period:
			self.timestamp.popleft()
			self.value.popleft()
			assert len(self.value) == len(self.timestamp)
	def write(self, directory):
		rows = [(data.value, timestamp(data.timestamp)) for data in self]
		with open(directory+self.csv, mode='w', newline='') as csv_file:
			writer = csv.writer(csv_file)
			writer.writerows(rows)
	def read(self, directory):
		try:
			with open(directory+self.csv, newline='') as csv_file:
				for r in csv.reader(csv_file):
					self.append(self.parser(r[0]), datetime.datetime.fromtimestamp(float(r[1])))
		except (IOError, OSError):
			pass

class FloatHistory:
	def __init__(self, name, floor, ceiling):
		self.name = name
		self.floor = floor
		self.ceiling = ceiling
		self.float = Record(name, config.detail_range, float)
		self.summary_min = Record(name+'-min', config.summary_range, float)
		self.summary_avg = Record(name+'-avg', config.summary_range, float)
		self.summary_max = Record(name+'-max', config.summary_range, float)
	def __str__(self):
		now = datetime.datetime.now()
		if self.float and self.float[-1].timestamp >= now - 2*config.client_interval:
			current = self.float[-1]
		else:
			current = None
		minimum = min(reversed(self.float)) if self.float else None
		maximum = max(reversed(self.float)) if self.float else None
		warn_low = minimum.value < self.floor if minimum else None
		warn_high = maximum.value > self.ceiling if maximum else None
		return ' | '.join([
			self.name,
			'{:.1f} °C'.format(current.value) if current else 'Fehler',
			('⚠ ' if warn_low else '') + str(minimum) if minimum else '—',
			('⚠ ' if warn_high else '') + str(maximum) if maximum else '—',
			'{:.0f} °C  bis {:.0f} °C'.format(self.floor, self.ceiling)])
	def _process(self, now):
		self.float.clear(now)
		self.summary_min.clear(now)
		self.summary_avg.clear(now)
		self.summary_max.clear(now)
#	def _summarize(self, now):
#		if self.float:
#			date = self.float[-1].timestamp.date()
#			if  now.date() > date:
#				noon = datetime.datetime.combine(date, datetime.time(12))
#				# FIXME: filter for exact date, improves accuracy after downtime, enables variable detail_range
#				self.summary_min.append(self.minimum.value, noon)
#				self.summary_avg.append(self.mean, noon)
#				self.summary_max.append(self.maximum.value, noon)
#				assert len(self.summary_min) == len(self.summary_avg) == len(self.summary_max)
	def store(self, value):
		now = datetime.datetime.now()
#		self._summarize(now)
		self.float.append(value, now)
		self._process(now)
	def backup(self, directory):
		self.float.write(directory)
		self.summary_min.write(directory)
		self.summary_avg.write(directory)
		self.summary_max.write(directory)
	def restore(self, directory):
		now = datetime.datetime.now()
		self.float.read(directory)
		self.summary_min.read(directory)
		self.summary_avg.read(directory)
		self.summary_max.read(directory)
		assert len(self.summary_min) == len(self.summary_avg) == len(self.summary_max)
		self._process(now)

class BoolHistory:
	def __init__(self, name, valid):
		self.name = name
		self.valid = valid
		self.boolean = Record(name, config.detail_range, lambda bool_str: bool_str=='True')
	def __str__(self):
		now = datetime.datetime.now()
		if self.boolean and self.boolean[-1].timestamp >= now - 2*config.client_interval:
			current = self.boolean[-1]
		else:
			current = None
		warn_low = '⚠ ' if False not in self.valid else ''
		warn_high = '⚠ ' if True not in self.valid else ''
		return ' | '.join([
			self.name,
			bool_string(current),
			warn_low + bool_string(False) if False in self.boolean else '—',
			warn_high + bool_string(True) if True in self.boolean else '—',
			', '.join([bool_string(v) for v in self.valid])])
	def store(self, value):
		if not self.boolean or value != self.boolean[-1]:
			now = datetime.datetime.now()
			self.boolean.append(value, now)
			self.boolean.clear(now)
	def backup(self, directory):
		self.boolean.write(directory)
	def restore(self, directory):
		now = datetime.datetime.now()
		self.boolean.read(directory)
		self.boolean.clear(now)
