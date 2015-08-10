import logging
import datetime
import collections
import random
import time
import config

class Sensor:
	def __init__(self, name, file, floor, ceiling):
		self.name = name
		self.file = file
		self.floor = floor
		self.ceiling = ceiling
		self.history = collections.deque()
		self.minimum = None
		self.maximum = None
		self.problem = None

	def __str__(self):
		return ' | '.join([
			self.name,
			format_measurement(self.history[-1]),
			format_measurement(self.minimum),
			format_measurement(self.maximum),
			'{:.1f} °C – {:.1f} °C'.format(self.floor, self.ceiling),
			'Warnung' if self.problem else 'Ok'])

	def update(self):
		# TODO parse self.file
		value = random.randrange(200, 400) / 10
		self.history.append((value, time.time()))
		while self.history[0][1] < self.history[-1][1] - config.history_seconds:
			self.history.popleft()
			logging.debug('dropping measurement')
		logging.debug('first: {:%c}, last: {:%c}'.format(
			datetime.datetime.fromtimestamp(self.history[0][1]),
			datetime.datetime.fromtimestamp(self.history[-1][1])))
		self.minimum = min(self.history)
		self.maximum = max(self.history)
		if self.minimum[0] < self.floor:
			self.problem = self.minimum
		elif self.maximum[0] > self.ceiling:
			self.problem = self.maximum
		else:
			self.problem = None

def format_measurement(m):
	return '{:.1f} °C / {:%X}'.format(
		m[0],
		datetime.datetime.fromtimestamp(m[1]))

