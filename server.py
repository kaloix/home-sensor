#!/usr/bin/env python3

import locale
import time
import string
import markdown
import datetime
import logging
import matplotlib.pyplot
import os
import csv
import traceback
import config
import notification
import sensor

def loop():
	logging.info('collect data')
	now = time.time()
	data = list()
	for sensor in sensor_list:
		sensor.update(now)
		if sensor.problem:
			notify.measurement_warning(sensor.problem, sensor.name)
		data.append(str(sensor))
	data = '\n'.join(data)

	logging.info('write html and csv')
	markdown_filled = string.Template(markdown_template).substitute(
		datum_aktualisierung = time.strftime('%c', time.localtime(now)),
		data = data)
	html_body = markdown_to_html.convert(markdown_filled)
	html_filled = string.Template(html_template).substitute(body=html_body)
	with open('index.html', mode='w') as html_file:
		html_file.write(html_filled)
	for sensor in sensor_list:
		filename = 'backup/{}.csv'.format(sensor.name)
		with open(filename, mode='w', newline='') as csv_file:
			writer = csv.writer(csv_file)
			writer.writerows(sensor.history)

	logging.info('generate plot')
	matplotlib.pyplot.figure(figsize=(12, 4))
	for sensor in sensor_list:
		values, times = map(list, zip(*sensor.history))
		times = list(map(datetime.datetime.fromtimestamp, times))
		matplotlib.pyplot.plot(times, values, label=sensor.name)
	matplotlib.pyplot.xlabel('Uhrzeit')
	matplotlib.pyplot.ylabel('Temperatur °C')
	matplotlib.pyplot.xlim(
		datetime.datetime.fromtimestamp(now - config.history_seconds),
		datetime.datetime.fromtimestamp(now))
	matplotlib.pyplot.legend(loc='best')
	matplotlib.pyplot.grid(True)
	matplotlib.pyplot.gca().yaxis.tick_right()
	matplotlib.pyplot.gca().yaxis.set_label_position('right')
	matplotlib.pyplot.savefig(filename='plot.png', bbox_inches='tight')
	matplotlib.pyplot.clf()

	logging.info('copy to webserver')
	files = ['index.html', 'plot.png']
	target = 'kaloix@adhara.uberspace.de:html/sensor'
	if os.system('scp {} {}'.format(' '.join(files), target)):
		notify.admin_error('scp to uberspace failed')

locale.setlocale(locale.LC_ALL, 'de_DE.UTF-8')
logging.basicConfig(
	format = '[%(asctime)s:%(levelname)s:%(module)s:%(threadName)s] '
		'%(message)s',
	datefmt = '%y-%m-%d-%H-%M-%S',
	level = logging.INFO)
with open('template.md') as markdown_file:
	markdown_template = markdown_file.read()
with open('template.html') as html_file:
	html_template = html_file.read()
markdown_to_html = markdown.Markdown(
	extensions = ['markdown.extensions.tables'],
	output_format = 'html5')
sensor_list = [
	sensor.Sensor('Wohnzimmer', None, 15, 30),
	sensor.Sensor('Klimaanlage', None, 10, 30)]
for sensor in sensor_list:
	filename = 'backup/{}.csv'.format(sensor.name)
	backup = list()
	try:
		with open(filename, newline='') as csv_file:
			reader = csv.reader(csv_file)
			for row in reader:
				backup.append(tuple(map(float, row)))
	except FileNotFoundError:
		logging.warning('no backup for {}'.format(sensor.name))
	else:
		sensor.history.extend(backup)
		logging.info('backup restored for {}'.format(sensor.name))
notify = notification.NotificationCenter()

while True:
	start = time.perf_counter()
	try:
		loop()
	except Exception as err:
		tb_lines = traceback.format_tb(err.__traceback__)
		notify.admin_error(
			'{}: {}\n{}'.format(type(err).__name__, err, ''.join(tb_lines)))
		break
	pause = start + config.update_seconds - time.perf_counter()
	logging.info('sleep for {:.0f} minutes'.format(pause/60))
	try:
		time.sleep(pause)
	except KeyboardInterrupt:
		logging.info('exiting')
		break
