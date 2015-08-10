import logging
import datetime
import collections
import random
import time
import config

class Sensor:
	def __init__(self, name, file, minimum, maximum):
		self.name = name
		self.file = file
		self.history = collections.deque()
		self.minimum = minimum
		self.maximum = maximum
		self.problem = None

	def __str__(self):
		if self.problem:
			warning = '{:.1f} °C / {:%c}'.format(
				self.problem[0],
				datetime.datetime.fromtimestamp(self.problem[1]))
		else:
			warning = '—'
		return ' | '.join([
			self.name,
			format_measurement(self.history[-1]),
			format_measurement(min(self.history)),
			format_measurement(max(self.history)),
			'{:.1f} °C – {:.1f} °C'.format(self.minimum, self.maximum),
			warning])

	def update(self):
		# TODO parse self.file
		value = random.randrange(50, 350) / 10
		self.history.append((value, time.time()))
		while self.history[0][1] < self.history[-1][1] - config.history_seconds:
			self.history.popleft()
		logging.debug('first: {:%c}, last: {:%c}'.format(
			datetime.datetime.fromtimestamp(self.history[0][1]),
			datetime.datetime.fromtimestamp(self.history[-1][1])))
		if self.history[-1][0] < self.minimum or self.history[-1][0] > self.maximum:
			self.problem = self.history[-1]

def format_measurement(m):
	return '{:.1f} °C / {:%X}'.format(
		m[0],
		datetime.datetime.fromtimestamp(m[1]))

