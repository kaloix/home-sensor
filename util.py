import logging
import resource
import collections
import config
import functools
import datetime
import csv

def init_logging():
	logging.basicConfig(
		format = '[%(asctime)s:%(levelname)s:%(module)s] %(message)s',
		datefmt = '%y-%m-%d-%H-%M-%S',
		level = logging.DEBUG)

def memory_check():
	memory = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e3
	logging.debug('using {:.0f} megabytes of memory'.format(memory))
	if memory > 100:
		raise Exception('memory leak')

def parse_w1_temp(file):
	with open(file) as w1_file:
		if w1_file.readline().strip().endswith('YES'):
			return int(w1_file.readline().split('t=')[-1].strip()) / 1e3
		else:
			raise Exception('sensor says no')

def timestamp(date_time):
	return float('{:%s}'.format(date_time)) + date_time.microsecond / 1e6

@functools.total_ordering
class Value:
	def __init__(self, value):
		self.value = value
	def __str__(self):
		return '{:.1f} °C'.format(self.value)
	def __lt__(self, other):
		return self.value < other.value
	def __eq__(self, other):
		return self.value == other.value

@functools.total_ordering
class Measurement:
	def __init__(self, timestamp, value):
		self.timestamp = timestamp
		self.value = Value(value)
	def __str__(self):
		return '{} um {:%H:%M} Uhr'.format(self.value, self.timestamp)
	def __lt__(self, other):
		return self.value < other.value
	def __eq__(self, other):
		return self.value == other.value

Summary = collections.namedtuple('Summary', 'timestamp minimum mean maximum')

class Record:
	def __init__(self, period):
		self.period = period
		self.data = collections.deque()
#	def __iter__(self):
#		return self.data.__iter__()
	def __len__(self):
		return len(self.data)
	def __getitem__(self, key):
		return self.data[key]
	def append(self, item):
		if not self.data or item.timestamp > self.data[-1].timestamp:
			self.data.append(item)
	def clear(self, now):
		while self.data and self.data[0].timestamp < now - self.period:
			self.data.popleft()

class History:
	def __init__(self, name, floor, ceiling):
		self.name = name
		self.floor = Value(floor)
		self.ceiling = Value(ceiling)
		self.detail = Record(config.detail_range)
		print(bool(self.detail))
		self.summary = Record(config.summary_range)
	def store(self, value):
		# detail record
		now = datetime.datetime.now()
		item = Measurement(now, value)
		self.detail.append(item)
		# summary record
		if now.date() > self.summary[-1].timestamp:
			item = Summary(timestamp.date(), self.minimum, self.mean, self.maximum)
			self.summary.append(item)
	def process(self, now):
		self.detail.clear(now)
		self.summary.clear(now)
		if self.detail and self.detail[-1].timestamp >= now - 2*config.client_interval:
			self.current = self.detail[-1]
		else:
			self.current = None
		self.minimum = min(reversed(self.detail)) if self.detail else None
		self.maximum = max(reversed(self.detail)) if self.detail else None
		self.warn_low = self.minimum.value < self.floor if self.minimum else None
		self.warn_high = self.maximum.value > self.ceiling if self.maximum else None
		self.mean = sum(self.detail) / len(self.detail) if self.detail else None
	def write(self, directory):
		# detail record
		rows = [(timestamp(d.timestamp), d.value.value) for d in self.detail]
		file = '{}{}-detail.csv'.format(directory, self.name)
		with open(file, mode='w', newline='') as csv_file:
			writer = csv.writer(csv_file)
			writer.writerows(rows)
		# summary record
		file = '{}{}-summary.csv'.format(directory, self.name)
		with open(file, mode='w', newline='') as csv_file:
			writer = csv.writer(csv_file)
			writer.writerows(self.summary)
	def read(self, directory):
		# detail record
		file = '{}{}-detail.csv'.format(directory, self.name)
		try:
			with open(file, newline='') as csv_file:
				for r in csv.reader(csv_file):
					item = Measurement(
						datetime.datetime.fromtimestamp(float(r[0])),
						float(r[1]))
					self.detail.append(item)
		except FileNotFoundError:
			pass
		# summary record
		file = '{}{}-summary.csv'.format(directory, self.name)
		try:
			with open(file, newline='') as csv_file:
				for r in csv.reader(csv_file):
					item = Summary(
						datetime.datetime.fromtimestamp(float(r[0])),
						float(r[1]),
						float(r[2]),
						float(r[3]))
					self.summary.append(item)
		except FileNotFoundError:
			pass
	def melt(self):
		timestamp = list()
		value = list()
		for d in self.detail:
			timestamp.append(d.timestamp)
			value.append(d.value.value)
		return timestamp, value
