import logging
import resource
import collections
import config
import functools
import datetime
import csv
import pytz
import pysolar
import scipy.misc
import subprocess
import numpy

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

def nighttime(count, date_time):
	# make aware
	date_time = pytz.timezone('Europe/Berlin').localize(date_time)
	# calculate nights
	date_time -= datetime.timedelta(days=count)
	sun_change = list()
	for c in range(0, count+1):
		date_time += datetime.timedelta(days=1)
		sun_change.extend(pysolar.util.get_sunrise_sunset(49.2, 11.08, date_time))
	sun_change = sun_change[1:-1]
	night = list()
	for r in range(0, count):
		night.append((sun_change[2*r], sun_change[2*r+1]))
	# make naive
	for sunset, sunrise in night:
		yield sunset.replace(tzinfo=None), sunrise.replace(tzinfo=None)

class Measurement(collections.namedtuple('Measurement', 'value timestamp')):
	__slots__ = ()
	def __str__(self):
		return '{:.1f} °C um {:%H:%M} Uhr'.format(self.value, self.timestamp)

class Record:
	def __init__(self, name, period):
		self.csv = '{}.csv'.format(name)
		self.period = period
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
					self.append(float(r[0]), datetime.datetime.fromtimestamp(float(r[1])))
		except (IOError, OSError):
			pass

class History:
	def __init__(self, name, floor, ceiling):
		self.floor = floor
		self.ceiling = ceiling
		self.detail = Record(name, config.detail_range)
		self.summary_min = Record(name+'-min', config.summary_range)
		self.summary_avg = Record(name+'-avg', config.summary_range)
		self.summary_max = Record(name+'-max', config.summary_range)
	def _clear(self, now):
		self.detail.clear(now)
		self.summary_min.clear(now)
		self.summary_avg.clear(now)
		self.summary_max.clear(now)
	def _process(self, now):
		if self.detail and self.detail[-1].timestamp >= now - 2*config.client_interval:
			self.current = self.detail[-1]
		else:
			self.current = None
		self.minimum = min(reversed(self.detail)) if self.detail else None
		self.maximum = max(reversed(self.detail)) if self.detail else None
		self.warn_low = self.minimum.value < self.floor if self.minimum else None
		self.warn_high = self.maximum.value > self.ceiling if self.maximum else None
		self.mean = sum(self.detail.value) / len(self.detail) if self.detail else None
	def _summarize(self, now):
		if self.detail:
			date = self.detail[-1].timestamp.date()
			if  now.date() > date:
				noon = datetime.datetime.combine(date, datetime.time(12))
				self.summary_min.append(self.minimum.value, noon)
				self.summary_avg.append(self.mean, noon)
				self.summary_max.append(self.maximum.value, noon)
				assert len(self.summary_min) == len(self.summary_avg) == len(self.summary_max)
	def store(self, value):
		now = datetime.datetime.now()
		self._summarize(now)
		self.detail.append(value, now)
		self._clear(now)
		self._process(now)
	def backup(self, directory):
		self.detail.write(directory)
		self.summary_min.write(directory)
		self.summary_avg.write(directory)
		self.summary_max.write(directory)
	def restore(self, directory):
		now = datetime.datetime.now()
		self.detail.read(directory)
		self.summary_min.read(directory)
		self.summary_avg.read(directory)
		self.summary_max.read(directory)
		assert len(self.summary_min) == len(self.summary_avg) == len(self.summary_max)
		self._clear(now)
		self._process(now)

class ThermosolarOCR:
	def _parse_segment(self, image):
		scipy.misc.imsave('seven_segment.png', image)
		command = ['ssocr/ssocr', '--number-digits=2', '--background=black', 'seven_segment.png']
		try:
			return int(subprocess.check_output(command))
		except (subprocess.CalledProcessError, ValueError) as err:
			logging.error(err)
	def _parse_light(self, image):
		hist, bin_edges = numpy.histogram(image, bins=4, range=(0,255), density=True)
		return hist[3] > 0.006
	def load_image(self, file):
		image = scipy.misc.imread(file)
		top = 11
		left = 76
		height = 76
		width = 123
		self.seven_segment = image[top:top+height, left:left+width]
		top = 146
		left = 128
		length = 15
		self.pump_light = image[top:top+length, left:left+length]
		top = 147
		left = 98
		self.sensor_light = image[top:top+length, left:left+length]
	def temperature(self):
		return self._parse_segment(self.seven_segment)
	def pump_active(self):
		return self._parse_light(self.pump_light)
	def sensor_failure(self):
		return self._parse_light(self.sensor_light)
