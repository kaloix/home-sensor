import csv
import logging
import resource
import collections
import config
import functools

def read_csv(file):
	data = list()
	with open(file, newline='') as csv_file:
		reader = csv.reader(csv_file)
		for row in reader:
			data.append(row)
	return data
	# return list(reader)?

def write_csv(file, data):
	with open(file, mode='w', newline='') as csv_file:
		writer = csv.writer(csv_file)
		writer.writerows(data)

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
class Measurement:
	def __init__(self, timestamp, value):
		self.timestamp = timestamp
		self.value = value
	def __str__(self, short=False):
		if short:
			return '{:.1f} °C'.format(self.value)
		else:
			return '{:.1f} °C um {:%H:%M} Uhr'.format(self.value, self.timestamp)
	def __lt__(self, other):
		return self.timestamp < other.timestamp
	def __eq__(self, other):
		return self.timestamp == other.timestamp
	def __len__(self):
		return 2
	def __getitem__(self, key):
		return [self.timestamp, self.value][key]
class History:
	def __init__(self):
		self.history = collections.deque()
	def append(self, timestamp, value):
		if self.history and timestamp <= self.history[-1].timestamp:
			raise Exception('timestamp not ascending')
		measurement = Measurement(timestamp, value)
		self.history.append(measurement)
	def clear(self, now):
		while self.history[0].timestamp < now - config.history_seconds:
			self.history.popleft()
class DetailHistory(History):
	def __init__(self, floor, ceiling):
		super().__init__()
		self.floor = Measurement(None, floor)
		self.ceiling = Measurement(None, ceiling)
	def reset(self):
		self.history = collections.deque()
	def process(self, now):
		if not self.history:
			raise Exception('cant process empty data')
		if self.history[-1].timestamp >= now - config.history_seconds:
			self.current = self.history[-1]
		else:
			self.current = None
		self.minimum = min(self.history)
		self.maximum = max(self.history)
		self.warn_low = self.minimum.value < self.floor.value
		self.warn_high = self.maximum.value > self.ceiling.value
