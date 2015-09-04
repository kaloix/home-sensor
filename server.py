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

class Sensor(DetailHistory):
	def __init__(self, floor, ceiling, id, name):
		super().__init__(floor, ceiling)
		self.id = id
		self.name = name
	def import_csv(self, now):
		self.reset()
		for data in util.read_csv(self.csv):
			self.append(map(float, data))
		self.clear(now)
		if self.history:
			self.process(now)
	def markdown(self):
		delimiter = ' | '
		string = [
			self.name,
			delimiter]
		if not self.history:
			string.extend([
				'Keine Daten',
				delimiter, delimiter, delimiter])
		else:
			string.extend([
				str(self.current, short=True) if self.current else 'Fehler',
				delimiter,
				'⚠ ' if self.warn_low else '',
				str(self.minimum),
				delimiter,
				'⚠ ' if self.warn_high else '',
				str(self.maximum),
				delimiter,
				str(self.floor, short=True),
				' bis ',
				str(self.ceiling, short=True)])
		return ''.join(string)

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
with open('sensor.json') as json_file:
	json_config = json_file.read()
sensor_json = json.loads(json_config)
sensor = list()
for id, attr in sensor_json.items():
	if attr['type'] == 'temperature':
		sensor_list.append(Sensor(
			id,
			attr['name'],
			attr['floor'],
			attr['ceiling']))

def loop():
	logging.info('read csv')
	now = time.time()
	markdown_string = list()
	for s in sensor:
		s.import_csv(now)
		markdown_string.append(s.markdown())
		if not sensor.history:
			notify.sensor_warning(sensor.id, sensor.name)
		if sensor.warn_low:
			notify.low_warning(sensor.id, sensor.name, sensor.minimum)
		if sensor.warn_high:
			notify.high_warning(sensor.id, sensor.name, sensor.maximum)
	markdown_data = '\n'.join(markdown_string)

	logging.info('write html')
	markdown_filled = string.Template(markdown_template).substitute(
		data = markdown_data,
		update_time = '{:%A %d. %B %Y %X}'.format(now),
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
	matplotlib.pyplot.close()
	os.system('cp index.html plot.png {}'.format(config['webserver']))

while True:
	start = time.perf_counter()
	try:
		loop()
		#gc.collect()
		util.memory_check()
	except Exception as err:
		tb_lines = traceback.format_tb(err.__traceback__)
		notify.admin_error(
			'{}: {}\n{}'.format(type(err).__name__, err, ''.join(tb_lines)))
		break
	logging.info('sleep, duration was {}s'.format(
		round(time.perf_counter() - start)))
	time.sleep(60)
