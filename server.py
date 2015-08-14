#!/usr/bin/env python3

import datetime
import json
import locale
import logging
import markdown
import matplotlib.pyplot
import notification
import os
import string
import time
import traceback
import util

class Sensor:
	def __init__(self, id, name, floor, ceiling):
		self.id = id
		self.name = name
		self.floor = floor
		self.ceiling = ceiling
		self.csv = 'csv/{}.csv'.format(id)

	def __str__(self):
		return ' | '.join([
			self.name,
			'Fehler' if self.error else '{:.1f} °C'.format(self.current[0]),
			'{}{:.1f} °C um {:%H:%M} Uhr'.format(
				'⚠ ' if self.low else '',
				*self.minimum),
			'{}{:.1f} °C um {:%H:%M} Uhr'.format(
				'⚠ ' if self.high else '',
				*self.maximum),
			'{:.0f} °C bis {:.0f} °C'.format(self.floor, self.ceiling)])

	def update(self, data):
		self.history = list()
		for d in data:
			self.history.append((
				float(d[1]),
				datetime.datetime.fromtimestamp(float(d[0]))))
		self.current = self.history[-1]
		self.minimum = min(self.history)
		self.maximum = max(self.history)
		if self.minimum[0] < self.floor:
			self.low = self.minimum
		else:
			self.low = None
		if self.maximum[0] > self.ceiling:
			self.high = self.maximum
		else:
			self.high = None

locale.setlocale(locale.LC_ALL, 'de_DE.UTF-8')
util.init_logging()
with open('template.md') as markdown_file:
	markdown_template = markdown_file.read()
with open('template.html') as html_file:
	html_template = html_file.read()
markdown_to_html = markdown.Markdown(
	extensions = ['markdown.extensions.tables'],
	output_format = 'html5')
notify = notification.NotificationCenter()
with open('config.json') as json_file:
	json_config = json_file.read()
config = json.loads(json_config)
sensor_list = list()
for id, attr in config['sensor'].items():
	if attr['type'] == 'temperature':
		sensor_list.append(Sensor(
			id,
			attr['name'],
			attr['floor'],
			attr['ceiling']))

def loop():
	logging.info('read csv')
	now = datetime.datetime.now()
	min_age = now - datetime.timedelta(minutes=config['update_minutes'])
	markdown_data = list()
	for sensor in sensor_list:
		sensor.error = False
		try:
			sensor.update(util.read_csv(sensor.csv))
		except FileNotFoundError:
			sensor.error = True
		if sensor.current[1] < min_age:
			sensor.error = True
		if sensor.error:
			notify.sensor_warning(sensor.id, sensor.name)
		if sensor.low:
			notify.low_warning(sensor.id, sensor.name, sensor.low)
		if sensor.high:
			notify.high_warning(sensor.id, sensor.name, sensor.high)
		markdown_data.append(str(sensor))
	markdown_data = '\n'.join(markdown_data)

	logging.info('write html')
	markdown_filled = string.Template(markdown_template).substitute(
		data = markdown_data,
		date = '{:%A %d. %B %Y}'.format(now),
		time = '{:%X %Z}'.format(now),
		year = '{:%Y}'.format(now))
	html_body = markdown_to_html.convert(markdown_filled)
	html_filled = string.Template(html_template).substitute(body=html_body)
	with open('index.html', mode='w') as html_file:
		html_file.write(html_filled)

	logging.info('generate plot')
	frame_start = now - datetime.timedelta(hours=config['history_hours'])
	matplotlib.pyplot.figure(figsize=(12, 4))
	for sensor in sensor_list:
		values, times = map(list, zip(*sensor.history))
		matplotlib.pyplot.plot(times, values, label=sensor.name)
	matplotlib.pyplot.xlim(frame_start, now)
	matplotlib.pyplot.xlabel('Uhrzeit')
	matplotlib.pyplot.ylabel('Temperatur °C')
	matplotlib.pyplot.grid(True)
	matplotlib.pyplot.gca().yaxis.tick_right()
	matplotlib.pyplot.gca().yaxis.set_label_position('right')
	matplotlib.pyplot.legend(loc='best')
	matplotlib.pyplot.savefig(filename='plot.png', bbox_inches='tight')
	matplotlib.pyplot.clf()
	os.system('cp index.html plot.png {}'.format(config['webserver']))

while True:
	start = time.perf_counter()
	try:
		loop()
		util.memory_check()
	except Exception as err:
		tb_lines = traceback.format_tb(err.__traceback__)
		notify.admin_error(
			'{}: {}\n{}'.format(type(err).__name__, err, ''.join(tb_lines)))
		break
	logging.info('sleep, duration was {}s'.format(
		round(time.perf_counter() - start)))
	time.sleep(60)
