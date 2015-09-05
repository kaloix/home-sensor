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
import config

class Sensor:
	def __init__(self, name, floor, ceiling):
		self.history = util.DetailHistory(name, floor, ceiling)
		self.name = name
		self.history.read(config.backup_dir)
	def update(self):
		self.history.read(config.data_dir)
		now = datetime.datetime.now()
		self.history.clear(now)
		self.history.process(now)
		self.history.write(config.backup_dir)
	def markdown(self):
		delimiter = ' | '
		return ''.join([
			self.name,
			delimiter,
			str(self.history.current.value) if self.history.current else 'Fehler',
			delimiter,
			'⚠ ' if self.history.warn_low else '',
			str(self.history.minimum),
			delimiter,
			'⚠ ' if self.history.warn_high else '',
			str(self.history.maximum),
			delimiter,
			str(self.history.floor),
			' bis ',
			str(self.history.ceiling)])

locale.setlocale(locale.LC_ALL, 'de_DE.UTF-8')
util.init_logging()
with open('template.md') as markdown_file:
	markdown_template = markdown_file.read()
with open('template.html') as html_file:
	html_template = html_file.read()
markdown_to_html = markdown.Markdown(
	extensions = ['markdown.extensions.tables'],
	output_format = 'html5')
with open('sensor.json') as json_file:
	json_config = json_file.read()
sensor_json = json.loads(json_config)
sensor = list()
for name, attr in sensor_json.items():
	sensor.append(Sensor(
		name,
		attr['floor'],
		attr['ceiling']))
notify = notification.NotificationCenter()

def loop():
	logging.info('read csv')
	now = datetime.datetime.now()
	markdown_string = list()
	for s in sensor:
		s.update()
		markdown_string.append(s.markdown())
		if not s.history.current:
			text = 'Messpunkt "{}" liefert keine Daten.'.format(s.name)
			notify.warn_user(text, s.name+'s')
		if s.history.warn_low:
			text = 'Messpunkt "{}" unterhalb des zulässigen Bereichs:\n{}'.format(s.name, s.history.minimum)
			notify.warn_user(text, s.name+'l')
		if s.history.warn_high:
			text = 'Messpunkt "{}" überhalb des zulässigen Bereichs:\n{}'.format(s.name, s.history.maximum)
			notify.warn_user(text, s.name+'h')
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
	frame_start = now - config.history_range
	matplotlib.pyplot.figure(figsize=(12, 4))
	for s in sensor:
		matplotlib.pyplot.plot(*s.history.melt(), label=s.name)
	matplotlib.pyplot.xlim(frame_start, now)
	matplotlib.pyplot.xlabel('Uhrzeit')
	matplotlib.pyplot.ylabel('Temperatur °C')
	matplotlib.pyplot.grid(True)
	matplotlib.pyplot.gca().yaxis.tick_right()
	matplotlib.pyplot.gca().yaxis.set_label_position('right')
	matplotlib.pyplot.legend(loc='best')
	matplotlib.pyplot.savefig(filename='plot.png', bbox_inches='tight')
	matplotlib.pyplot.close()
	os.system('cp index.html plot.png {}'.format(config.web_dir))

while True:
	start = time.perf_counter()
	try:
		loop()
		util.memory_check()
	except Exception as err:
		tb_lines = traceback.format_tb(err.__traceback__)
		notify.warn_admin(
			'{}: {}\n{}'.format(type(err).__name__, err, ''.join(tb_lines)))
		break
	logging.info('sleep, duration was {}s'.format(
		round(time.perf_counter() - start)))
	time.sleep(60)
