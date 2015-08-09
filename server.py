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
import os

class Sensor:
	def __init__(self, name, file):
		self.name = name
		self.file = file
		self.history = collections.deque()
	def update(self):
		# TODO parse self.file
		value = random.randrange(100, 400) / 10
		self.history.append((value, datetime.datetime.now()))
		lower = self.history[-1][1] - datetime.timedelta(days=1)
		while self.history[0][1] < lower:
			self.history.popleft()
		logging.debug('first: {}, last: {}'.format(
			self.history[0][1],
			self.history[-1][1]))
def format_measurement(m):
	return '{:.1f} °C / {:%X}'.format(*m)

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
			format_measurement(s.history[-1]),
			format_measurement(min(s.history)),
			format_measurement(max(s.history))))
	data = '\n'.join(data)

	logging.info('write html')
	markdown_filled = string.Template(markdown_template).substitute(
		datum_aktualisierung = time.strftime('%c'),
		data = data)
	html_body = markdown_to_html.convert(markdown_filled)
	html_filled = string.Template(html_template).substitute(body=html_body)
	with open('index.html', mode='w') as html_file:
		html_file.write(html_filled)

	logging.info('generate plot')
	matplotlib.pyplot.figure(figsize=(12, 4))
	for s in sensor:
		times, values = map(list, zip(*s.history))
		matplotlib.pyplot.plot(values, times, label=s.name)
	matplotlib.pyplot.xlabel('Uhrzeit')
	matplotlib.pyplot.ylabel('Temperatur °C')
	now = datetime.datetime.now()
	matplotlib.pyplot.xlim(now-datetime.timedelta(days=1), now)
	matplotlib.pyplot.ylim(-20, 40)
	matplotlib.pyplot.legend(loc=2)
	matplotlib.pyplot.savefig(filename='plot.png', bbox_inches='tight')
	matplotlib.pyplot.clf()

	logging.info('copy to webserver')
	files = ['index.html', 'plot.png', 'style.css']
	target = 'kaloix@adhara.uberspace.de:html/sensor'
	if os.system('scp {} {}'.format(' '.join(files), target)):
		logging.error('scp failed')

	pause = start + 3 - time.perf_counter()
	if pause > 0:
		logging.info('sleep for {:.0f}s'.format(pause))
		try:
			time.sleep(pause)
		except KeyboardInterrupt:
			logging.info('exiting')
			break
