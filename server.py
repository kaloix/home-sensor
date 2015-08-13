#!/usr/bin/env python3

import locale
import time
import string
import markdown
import datetime
import matplotlib.pyplot
import os
import traceback
import notification
import util
import json

class Sensor:
	def __init__(self, id, name, floor, ceiling):
		self.name = name
		self.floor = floor
		self.ceiling = ceiling
		self.csv = 'csv/{}.csv'.format(id)

	def __str__(self):
		return ' | '.join([
			self.name,
			'Fehler' if self.error else '{:.1f} °C'.format(self.current[0]),
			'{:.1f} °C um {:%H:%M} Uhr'.format(*self.minimum),
			'{:.1f} °C um {:%H:%M} Uhr'.format(*self.maximum),
			'{:.0f} °C bis {:.0f} °C'.format(self.floor, self.ceiling),
			'Warnung' if self.problem else 'Ok'])

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
			self.problem = self.minimum
		elif self.maximum[0] > self.ceiling:
			self.problem = self.maximum
		else:
			self.problem = None

locale.setlocale(locale.LC_ALL, 'de_DE.UTF-8')
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
	print('read csv')
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
			notify.admin_error('no data from sensor {}'.format(sensor.name))
		if sensor.problem:
			notify.measurement_warning(sensor.name, sensor.problem)
		markdown_data.append(str(sensor))
	markdown_data = '\n'.join(markdown_data)

	print('write html')
	markdown_filled = string.Template(markdown_template).substitute(
		datum_aktualisierung = '{:%c}'.format(now),
		data = markdown_data)
	html_body = markdown_to_html.convert(markdown_filled)
	html_filled = string.Template(html_template).substitute(body=html_body)
	with open('index.html', mode='w') as html_file:
		html_file.write(html_filled)

	print('generate plot')
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
	matplotlib.pyplot.savefig(filename='plot.png', bbox_inches='tight')
	matplotlib.pyplot.clf()
	os.system('cp index.html plot.png {}'.format(config['webserver']))

while True:
	try:
		loop()
	except Exception as err:
		tb_lines = traceback.format_tb(err.__traceback__)
		notify.admin_error(
			'{}: {}\n{}'.format(type(err).__name__, err, ''.join(tb_lines)))
		break
	print('sleep')
	time.sleep(60)
