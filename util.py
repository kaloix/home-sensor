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
	memory = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1000000
	logging.debug('using {:.3f} megabytes of memory'.format(memory))
	if memory > 100:
		raise Exception('memory leak')

def parse_w1_temp(file):
	try:
		with open(file) as w1_file:
			if file.readline().endswith('YES'):
				return int(file.readline().split('t=')[-1]) / 1000
	except Exception as err:
		logging.error('sensor failure: {}'.format(err))

def timestamp(date_time):
	return (date_time - datetime.datetime(1970, 1, 1)).total_seconds()

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
		return self.timestamp < other.timestamp
	def __eq__(self, other):
		return self.timestamp == other.timestamp

class History:
	def __init__(self, name):
		self.csv = '{}.csv'.format(name)
		self.data = collections.deque()
	def append(self, timestamp, value):
		if not self.data or timestamp > self.data[-1].timestamp:
			measurement = Measurement(timestamp, value)
			self.data.append(measurement)
	def clear(self, now):
		while self.data and self.data[0].timestamp < now - config.history_range:
			self.data.popleft()
	def read(self, directory):
		try:
			with open(directory+self.csv, newline='') as csv_file:
				for r in csv.reader(csv_file):
					self.append(datetime.datetime.fromtimestamp(float(r[0])), float(r[1]))
		except FileNotFoundError:
			pass
	def write(self, directory):
		rows = [(timestamp(d.timestamp), d.value.value) for d in self.data]
		with open(directory+self.csv, mode='w', newline='') as csv_file:
			writer = csv.writer(csv_file)
			writer.writerows(rows)

class DetailHistory(History):
	def __init__(self, name, floor, ceiling):
		super().__init__(name)
		self.floor = Value(floor)
		self.ceiling = Value(ceiling)
	def process(self, now):
		if self.data and self.data[-1].timestamp >= now - config.history_range:
			self.current = self.data[-1]
		else:
			self.current = None
		self.minimum = min(self.data) if self.data else None
		self.maximum = max(self.data) if self.data else None
		self.warn_low = self.minimum.value < self.floor if self.data else None
		self.warn_high = self.maximum.value > self.ceiling if self.data else None
	def melt(self):
		timestamp = list()
		value = list()
		for d in self.data:
			timestamp.append(d.timestamp)
			value.append(d.value.value)
		return timestamp, value
