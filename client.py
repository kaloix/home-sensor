#!/usr/bin/env python3

import argparse
import collections
import json
import logging
import os
import time
import util
import config
import datetime

class Sensor:
	def __init__(self, name, file):
		self.history = util.History(name)
		self.file = file
	def update(self):
		now = datetime.datetime.now()
		value = util.parse_w1_temp(self.file)
		if value is not None:
			self.history.append(now, value)
		self.history.clear(now)
		self.history.write(config.data_dir)

parser = argparse.ArgumentParser()
parser.add_argument('station', type=int)
args = parser.parse_args()
util.init_logging()
with open('sensor.json') as json_file:
	json_config = json_file.read()
sensor_json = json.loads(json_config)
sensor = list()
for name, attr in sensor_json.items():
	if attr['station'] != args.station:
		continue
	sensor.append(Sensor(name, attr['file']))

while True:
	start = time.time()
	logging.info('collect data')
	for s in sensor:
		s.update()
	logging.info('copy to webserver')
	if os.system('scp {0}* {1}{0}'.format(config.data_dir, config.client_server)):
		logging.error('scp failed')
	util.memory_check()
	logging.info('sleep, duration was {}s'.format(
		round(time.time() - start)))
	time.sleep(config.update_interval.total_seconds())
