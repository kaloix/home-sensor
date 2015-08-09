#!/usr/bin/env python3

import locale
import time
import string
import markdown
import datetime
import logging
import collections
import random
import matplotlib.pyplot

class RichComparisonMixin:
	def __le__(self, other):
		return self.__lt__(other) or self.__eq__(other)
	def __ne__(self, other):
		return not self.__eq__(other)
	def __gt__(self, other):
		return not self.__lt__(other) and not self.__eq__(other)
	def __ge__(self, other):
		return not self.__lt__(other)
class Measurement(RichComparisonMixin):
	def __init__(self, value):
		self.value = value
		self.time = datetime.datetime.now()
	def __str__(self):
		return '{:.1f} °C / {:%X}'.format(self.value, self.time)
	def __lt__(self, other):
		return self.value < other.value
	def __eq__(self, other):
		return self.value == other.value
class Sensor:
	def __init__(self, name, file):
		self.name = name
		self.file = file
		self.history = collections.deque()
	def update(self):
		# TODO parse self.file
		value = random.randrange(100, 400) / 10
		self.history.append(Measurement(value))
		lower_bound = self.history[-1].time - datetime.timedelta(days=1)
		while self.history[0].time < lower_bound:
			self.history.popleft()
		logging.debug('first: {}, last: {}'.format(
			self.history[0].time,
			self.history[-1].time))

locale.setlocale(locale.LC_ALL, 'de_DE.UTF-8')
logging.basicConfig(
	format = '[%(asctime)s:%(levelname)s:%(module)s:%(threadName)s] %(message)s',
	datefmt = '%y-%m-%d-%H-%M-%S',
	level = logging.DEBUG)
with open('template.md') as markdown_file:
	markdown_template = markdown_file.read()
with open('template.html') as html_file:
	html_template = html_file.read()
markdown_to_html = markdown.Markdown(
	extensions = ['markdown.extensions.tables'],
	output_format = 'html5')
sensor = [
	Sensor('Wohnzimmer', None),
	Sensor('Klimaanlage', None)]

while True:
	start = time.perf_counter()
	logging.info('collect data')
	data = list()
	for s in sensor:
		s.update()
		data.append('{} | {} | {} | {}'.format(
			s.name,
			s.history[-1],
			min(s.history),
			max(s.history)))
	data = '\n'.join(data)

	logging.info('write html')
	markdown_filled = string.Template(markdown_template).substitute(
		datum_aktualisierung = time.strftime('%c'),
		data = data)
	html_body = markdown_to_html.convert(markdown_filled)
	html_filled = string.Template(html_template).substitute(
		body = html_body)
	with open('index.html', mode='w') as html_file:
		html_file.write(html_filled)

	logging.info('generate plot')
	a = sensor[0].history
	for b in a:
		print(b)
	x, y = zip(a)
	print(x)
	print(y)
	#matplotlib.pyplot.plot(*zip(sensor[0].history))
	#matplotlib.pyplot.savefig('plot.png')
	
	# TODO scp to uberspace

	pause = start + 5 - time.perf_counter()
	if pause > 0:
		logging.info('sleep for {:.0f}s'.format(pause))
		try:
			time.sleep(pause)
		except KeyboardInterrupt:
			logging.info('exiting')
			break
