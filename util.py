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
	def __init__(self, id):
		self.csv = '{}.csv'.format(id)
		self.data = collections.deque()
	def append(self, timestamp, value):
		if not self.data or timestamp > self.data[-1].timestamp:
			measurement = Measurement(timestamp, value)
			self.data.append(measurement)
	def clear(self, now):
		while self.data[0].timestamp < now - config.history_range:
			self.data.popleft()
	def read(self, file):
		with open(dir+self.csv, newline='') as csv_file:
			for row in csv.reader(csv_file):
				self.append(
					datetime.datetime.fromtimestamp(float(row[0])),
					float(row[1]))
	def write(self, dir):
		rows = [(d.timestamp.timestamp(), d.value.value) for d in self.data]
		with open(dir+self.csv, mode='w', newline='') as csv_file:
			writer = csv.writer(csv_file)
			writer.writerows(rows)

class DetailHistory(History):
	def __init__(self, id, floor, ceiling):
		super().__init__(id)
		self.floor = Value(floor)
		self.ceiling = Value(ceiling)
	def process(self, now):
		if not self.data:
			raise Exception('cant process empty data')
		if self.data[-1].timestamp < now - config.history_range:
			self.current = None
		else:
			self.current = self.data[-1]
		self.minimum = min(self.data)
		self.maximum = max(self.data)
		self.warn_low = self.minimum.value < self.floor
		self.warn_high = self.maximum.value > self.ceiling
