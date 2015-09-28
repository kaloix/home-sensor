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
		ret.append(str(hours))
		ret.append('Stunde' if hours==1 else 'Stunden')
	minutes = (td.seconds//60) % 60
	ret.append(str(minutes))
	ret.append('Minute' if minutes==1 else 'Minuten')
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

	def _clear(self, now):
		while self.data and self.data[0].timestamp < now-self.period:
			self.data.popleft()

	@property
	def current(self):
		now = datetime.datetime.now()
		if self.data and self.data[-1].timestamp >= now-ALLOWED_DOWNTIME:
			return self.data[-1].value
		else:
			return None

	def store(self, value):
		now = datetime.datetime.now()
		self.data.append(Measurement(value, now))
		# delete center of three equal values while keeping some
		if len(self.data) >= 3 and self.data[-3].value == self.data[-2].value \
				== self.data[-1].value and self.data[-2].timestamp- \
				self.data[-3].timestamp < TRANSMIT_INTERVAL:
			del self.data[-2]
		self._clear(now)

	def write(self, directory):
		rows = [(d.value, int(d.timestamp.timestamp())) for d in self.data]
		with open(directory+self.csv, mode='w', newline='') as csv_file:
			writer = csv.writer(csv_file)
			writer.writerows(rows)

	def read(self, directory):
		now = datetime.datetime.now()
		try:
			with open(directory+self.csv, newline='') as csv_file:
				for row in csv.reader(csv_file):
					value = self.parser(row[0])
					timestamp = datetime.datetime.fromtimestamp(float(row[1]))
					if not self.data or timestamp > self.data[-1].timestamp:
						self.data.append(Measurement(value, timestamp))
		except OSError:
			pass
		self._clear(now)


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

	def store(self, value):
		self.float.store(value)

	def backup(self, directory):
		self.float.write(directory)

	def restore(self, directory):
		self.float.read(directory)


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
		self.boolean.store(value)

	def backup(self, directory):
		self.boolean.write(directory)

	def restore(self, directory):
		self.boolean.read(directory)


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
