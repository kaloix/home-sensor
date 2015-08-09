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
import csv
import config
import traceback
import smtplib
import email.mime.text

class Sensor:
	def __init__(self, file):
		self.file = file
		self.history = collections.deque()
	def update(self):
		# TODO parse self.file
		value = random.randrange(-222, 444) / 10
		if value < config.min_air_temp or value > config.max_air_temp:
			logging.warning('temperature out of range')
		self.history.append((value, time.time()))
		while self.history[0][1] < self.history[-1][1] - config.history_seconds:
			self.history.popleft()
		logging.debug('first: {}, last: {}'.format(
			self.history[0][1],
			self.history[-1][1]))

def format_measurement(m):
	return '{:.1f} °C / {:%X}'.format(
		m[0],
		datetime.datetime.fromtimestamp(m[1]))

def loop():
	logging.info('collect data')
	data = list()
	for name, sensor in sensor_dict.items():
		sensor.update()
		data.append('{} | {} | {} | {}'.format(
			name,
			format_measurement(sensor.history[-1]),
			format_measurement(min(sensor.history)),
			format_measurement(max(sensor.history))))
	data = '\n'.join(data)

	logging.info('write html and csv')
	markdown_filled = string.Template(markdown_template).substitute(
		datum_aktualisierung = time.strftime('%c'),
		data = data)
	html_body = markdown_to_html.convert(markdown_filled)
	html_filled = string.Template(html_template).substitute(body=html_body)
	with open('index.html', mode='w') as html_file:
		html_file.write(html_filled)
	for name, sensor in sensor_dict.items():
		filename = 'backup/{}.csv'.format(name)
		with open(filename, mode='w', newline='') as csv_file:
			writer = csv.writer(csv_file)
			writer.writerows(sensor.history)

	logging.info('generate plot')
	matplotlib.pyplot.figure(figsize=(12, 4))
	for name, sensor in sensor_dict.items():
		values, times = map(list, zip(*sensor.history))
		times = list(map(datetime.datetime.fromtimestamp, times))
		matplotlib.pyplot.plot(times, values, label=name)
	matplotlib.pyplot.xlabel('Uhrzeit')
	matplotlib.pyplot.ylabel('Temperatur °C')
	now = datetime.datetime.now()
	matplotlib.pyplot.xlim(
		now - datetime.timedelta(seconds=config.history_seconds),
		now)
	matplotlib.pyplot.ylim(config.min_air_temp, config.max_air_temp)
	matplotlib.pyplot.legend(loc=2)
	matplotlib.pyplot.savefig(filename='plot.png', bbox_inches='tight')
	matplotlib.pyplot.clf()

	logging.info('copy to webserver')
	files = ['index.html', 'plot.png', 'style.css']
	target = 'kaloix@adhara.uberspace.de:html/sensor'
	if os.system('scp {} {}'.format(' '.join(files), target)):
		logging.error('scp failed')

def _email_(address, content):
#	with open('smtpauth.txt') as smtpauth_file:
#		user = smtpauth_file.readline().rstrip('\n')
#		password = smtpauth_file.readline().rstrip('\n')
	msg = email.mime.text.MIMEText(content)
	msg['Subject'] = 'Automatische Nachricht vom Sensor-Server'
	msg['From'] = 'sensor@kaloix.de'
	msg['To'] = address
	s = smtplib.SMTP(host='adhara.uberspace.de', port=587)
	s.starttls()
	s.ehlo()
#	s.login(user, password)
	s.send_message(msg)
	s.quit()

locale.setlocale(locale.LC_ALL, 'de_DE.UTF-8')
logging.basicConfig(
	format = '[%(asctime)s:%(levelname)s:%(module)s:%(threadName)s] '
		'%(message)s',
	datefmt = '%y-%m-%d-%H-%M-%S',
	level = logging.DEBUG)
with open('template.md') as markdown_file:
	markdown_template = markdown_file.read()
with open('template.html') as html_file:
	html_template = html_file.read()
markdown_to_html = markdown.Markdown(
	extensions = ['markdown.extensions.tables'],
	output_format = 'html5')
sensor_dict = {
	'Wohnzimmer': Sensor(None),
	'Klimaanlage': Sensor(None)}
for name, sensor in sensor_dict.items():
	filename = 'backup/{}.csv'.format(name)
	try:
		backup = list()
		with open(filename, newline='') as csv_file:
			reader = csv.reader(csv_file)
			for row in reader:
				backup.append(tuple(map(float, row)))
	except FileNotFoundError:
		logging.warning('no backup for {}'.format(name))
		continue
	sensor.history.extend(backup)
	logging.info('backup restored for {}'.format(name))

while True:
	start = time.perf_counter()
	try:
		loop()
	except Exception as err:
		tb_lines = traceback.format_tb(err.__traceback__)
		error = '{}: {}\n{}'.format(type(err).__name__, err, ''.join(tb_lines))
		logging.critical(error)
		_email_('stefan@kaloix.de', error)
		break
	pause = start + config.update_seconds - time.perf_counter()
	if pause > 0:
		logging.info('sleep for {:.0f}s'.format(pause))
		try:
			time.sleep(pause)
		except KeyboardInterrupt:
			logging.info('exiting')
			break
	else:
		logging.warning('overload')
