#!/usr/bin/env python3

import datetime
import gc # FIXME
import json
import logging
import os
import string
import time
import traceback

import config
import notification
import presentation
import utility


def main():
	util.init()
	with open('template.html') as html_file:
		html_template = html_file.read()
	with open('sensor.json') as json_file:
		sensor_json = json.loads(json_file.read())
	sensor = dict()
	for group, sensor_list in sensor_json.items():
		temp = list()
		switch = list()
		for s in sensor_list:
			for kind, attr in s['output'].items():
				if kind == 'temperature':
					temp.append(Temperature(
						attr['name'],
						attr['floor'],
						attr['ceiling']))
				elif kind == 'switch':
					switch.append(Switch(
						attr['name']))
		sensor[group] = temp + switch
	notify = notification.NotificationCenter()

	while True:
		start = time.time()
		try:
			for group, sensor_list in sensor.items():
				loop(group, sensor_list)
			gc.collect() # FIXME
			util.memory_check()
		except Exception as err:
			tb_lines = traceback.format_tb(err.__traceback__)
			notify.warn_admin(
				'{}: {}\n{}'.format(type(err).__name__, err, ''.join(tb_lines)))
			break
		logging.info('sleep, duration was {}s'.format(
			round(time.time() - start)))
		time.sleep(config.server_interval.total_seconds())


def loop(group, sensor_list):
	logging.info('read csv')
	now = datetime.datetime.now()
	for s in sensor_list:
		s.update()
		s.check()
	if os.system('cp {}{} {}'.format(config.data_dir, 'thermosolar.jpg', config.web_dir)):
		logging.error('cp thermosolar.jpg failed')

	logging.info('write html')
	html_filled = string.Template(html_template).substitute(
		refresh_seconds = int(config.transmit_interval.total_seconds()),
		group = group,
		values = presentation.detail_html([s.history for s in sensor_list]),
		update_time = '{:%A %d. %B %Y %X}'.format(now),
		year = '{:%Y}'.format(now))
	with open(config.web_dir+group+'.html', mode='w') as html_file:
		html_file.write(html_filled)

	logging.info('generate plot')
	presentation.plot_history([s.history for s in sensor_list], config.web_dir+group+'.png', now)


class Temperature:

	def __init__(self, name, floor, ceiling):
		self.history = util.FloatHistory(name, floor, ceiling)
		self.history.restore(config.backup_dir)
		self.name = name

	def update(self):
		self.history.restore(config.data_dir)
		self.history.backup(config.backup_dir)

	def check(self):
		pass # TODO
#		if not self.history.current:
#			text = 'Messpunkt "{}" liefert keine Daten.'.format(self.name)
#			notify.warn_user(text, self.name+'s')
#		if self.history.warn_low:
#			text = 'Messpunkt "{}" unterhalb des zulässigen Bereichs:\n{}'.format(self.name, self.history.minimum)
#			notify.warn_user(text, self.name+'l')
#		if self.history.warn_high:
#			text = 'Messpunkt "{}" überhalb des zulässigen Bereichs:\n{}'.format(self.name, self.history.maximum)
#			notify.warn_user(text, self.name+'h')


if __name__ == "__main__":
	main()
