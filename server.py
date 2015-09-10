#!/usr/bin/env python3

import datetime
import json
import logging
import notification
import os
import string
import time
import traceback
import util
import config
import presentation

class Sensor:
	def __init__(self, name, floor, ceiling):
		self.history = util.History(name, floor, ceiling)
		self.name = name
		self.history.restore(config.backup_dir)
	def update(self):
		self.history.restore(config.data_dir)
		self.history.backup(config.backup_dir)

util.init()
with open('template.html') as html_file:
	html_template = html_file.read()
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
	group = 'Lufttemperatur'

	logging.info('read csv')
	now = datetime.datetime.now()
	for s in sensor:
		s.update()
		if not s.history.current:
			text = 'Messpunkt "{}" liefert keine Daten.'.format(s.name)
			notify.warn_user(text, s.name+'s')
		if s.history.warn_low:
			text = 'Messpunkt "{}" unterhalb des zulässigen Bereichs:\n{}'.format(s.name, s.history.minimum)
			notify.warn_user(text, s.name+'l')
		if s.history.warn_high:
			text = 'Messpunkt "{}" überhalb des zulässigen Bereichs:\n{}'.format(s.name, s.history.maximum)
			notify.warn_user(text, s.name+'h')

	logging.info('write html')
	html_filled = string.Template(html_template).substitute(
		refresh_seconds = int(config.client_interval.total_seconds()),
		group = group,
		values = presentation.detail_table([s.history for s in sensor]),
		update_time = '{:%A %d. %B %Y %X}'.format(now),
		year = '{:%Y}'.format(now))
	with open(config.web_dir+group+'.html', mode='w') as html_file:
		html_file.write(html_filled)

	logging.info('generate plot')
	presentation.plot_history([s.history for s in sensor], config.web_dir+group+'.png', now)

while True:
	start = time.time()
	try:
		loop()
		util.memory_check()
	except Exception as err:
		tb_lines = traceback.format_tb(err.__traceback__)
		notify.warn_admin(
			'{}: {}\n{}'.format(type(err).__name__, err, ''.join(tb_lines)))
		break
	logging.info('sleep, duration was {}s'.format(
		round(time.time() - start)))
	time.sleep(config.server_interval.total_seconds())
