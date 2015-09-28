import collections
import csv
import datetime
import locale
import logging
import resource
import time


DETAIL_RANGE = datetime.timedelta(days=1)
TRANSMIT_INTERVAL = datetime.timedelta(minutes=10)
ALLOWED_DOWNTIME = 2 * TRANSMIT_INTERVAL

Measurement = collections.namedtuple('Measurement', 'value timestamp')


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


def format_timedelta(td):
	ret = list()
	hours = td.days*24 + td.seconds//3600
	if hours:
		ret.append('{} Stunden'.format(hours))
	ret.append('{} Minuten'.format((td.seconds//60) % 60))
	return ' '.join(ret)


class Record(object):

	def __init__(self, name, period, parser):
		self.csv = '{}.csv'.format(name)
		self.period = period
		self.parser = parser
		self.data = collections.deque()

	def __len__(self):
		return len(self.data)

	def __getitem__(self, key):
		return self.data[key]

	@property
	def current(self):
		now = datetime.datetime.now()
		if self.data and self.data[-1].timestamp >= now - ALLOWED_DOWNTIME:
			return self.data[-1].value
		else:
			return None

	def append(self, value, timestamp):
		# only accept newer values
		if self.data and timestamp <= self.data[-1].timestamp:
			return
		self.data.append(Measurement(value, timestamp.replace(microsecond=0)))
		# delete center of three equal values
		if len(self.data) >= 3 and self.data[-3].value == self.data[-2].value \
				== self.data[-1].value:
			# keep some values
			if self.data[-2].timestamp - self.data[-3].timestamp \
					< TRANSMIT_INTERVAL:
				del self.data[-2]

	def clear(self, now):
		while self.data and self.data[0].timestamp < now - self.period:
			self.data.popleft()

	def write(self, directory):
		rows = [(d.value, int(d.timestamp.timestamp())) for d in self.data]
		with open(directory+self.csv, mode='w', newline='') as csv_file:
			writer = csv.writer(csv_file)
			writer.writerows(rows)

	def read(self, directory):
		try:
			with open(directory+self.csv, newline='') as csv_file:
				for r in csv.reader(csv_file):
					self.append(self.parser(r[0]),
					            datetime.datetime.fromtimestamp(float(r[1])))
		except OSError:
			pass


class FloatHistory(object):

	def __init__(self, name, usual, warn):
		self.name = name
		self.usual = usual
		self.warn = warn
		self.float = Record(name, DETAIL_RANGE, float)

	def __str__(self):
		current = self.float.current
		minimum = min(reversed(self.float)) if self.float else None
		maximum = max(reversed(self.float)) if self.float else None
		ret = list()
		ret.append('<b>{}:</b> '.format(self.name))
		if current is None:
			ret.append('Fehler')
		else:
			ret.append('{:.1f} °C'.format(current))
			if current < self.warn[0] or current > self.warn[1]:
				ret.append(' ⚠')
		ret.append('<ul>\n')
		if minimum:
			ret.append(
				'<li>Minimum bei {:.1f} °C am {:%A um %H:%M} Uhr.'.format(
					*minimum))
			if minimum.value < self.warn[0]:
				ret.append(' ⚠')
			ret.append('</li>\n')
		if maximum:
			ret.append(
				'<li>Maximum bei {:.1f} °C am {:%A um %H:%M} Uhr.'.format(
					*maximum))
			if maximum.value > self.warn[1]:
				ret.append(' ⚠')
			ret.append('</li>\n')
		ret.append(
			'<li>Warnbereich unter {:.0f} °C und über {:.0f} °C.</li>\n'
				.format(*self.warn))
		ret.append('</ul>')
		return ''.join(ret)

	def _process(self, now):
		self.float.clear(now)

	def store(self, value):
		now = datetime.datetime.now()
		self.float.append(value, now)
		self._process(now)

	def backup(self, directory):
		self.float.write(directory)

	def restore(self, directory):
		now = datetime.datetime.now()
		self.float.read(directory)
		self._process(now)


class BoolHistory(object):

	def __init__(self, name):
		self.name = name
		self.boolean = Record(
			name, DETAIL_RANGE, lambda bool_str: bool_str=='True')

	def __str__(self):
		current = self.boolean.current
		last_false = last_true = None
		for measurement in self.boolean:
			if measurement.value:
				last_true = measurement.timestamp
			else:
				last_false = measurement.timestamp
		ret = list()
		ret.append('<b>{}:</b> '.format(self.name))
		if current is None:
			ret.append('Fehler')
		elif current:
			ret.append('Ein')
		else:
			ret.append('Aus')
		ret.append('<ul>\n')
		if last_true and (current is None or not current):
			ret.append(
				'<li>Zuletzt Ein am {:%A um %H:%M} Uhr.</li>\n'.format(
					last_true))
		if last_false and (current is None or current):
			ret.append(
				'<li>Zuletzt Aus am {:%A um %H:%M} Uhr.</li>\n'.format(
					last_false))
		if self.boolean:
			ret.append(
				'<li>Insgesamt {} Einschaltdauer.</li>\n'.format(
					format_timedelta(self.uptime)))
		ret.append('</ul>')
		return ''.join(ret)

	@property
	def segments(self):
		expect = True
		for value, timestamp in self.boolean:
			if value != expect:
				continue
			if expect:
				start = timestamp
				expect = False
			else:
				yield start, timestamp
				expect = True
		if not expect:
			now = datetime.datetime.now()
			yield start, min(timestamp+ALLOWED_DOWNTIME, now)

	@property
	def uptime(self):
		total = datetime.timedelta()
		for start, stop in self.segments:
			total += stop - start
		return total

	def store(self, value):
		now = datetime.datetime.now()
		self.boolean.append(value, now)
		self.boolean.clear(now)

	def backup(self, directory):
		self.boolean.write(directory)

	def restore(self, directory):
		now = datetime.datetime.now()
		self.boolean.read(directory)
		self.boolean.clear(now)


class Timer(object):

	def __init__(self, interval):
		self.interval = interval.total_seconds()
		self.next_ = int()

	def check(self):
		now = time.perf_counter()
		if now < self.next_:
			return False
		else:
			self.next_ = now + self.interval
			return True
