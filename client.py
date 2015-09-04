#!/usr/bin/env python3

import argparse
import collections
import json
import logging
import os
import random
import time
import util
import config

class Sensor(util.History):
	def __init__(self, id, file):
		super().__init__()
		self.csv = 'csv/{}.csv'.format(id)
		self.file = file
	def read_value(self):
		now = time.time()
		value = random.randrange(180, 500) / 10
		self.append(now, value)
		self.clear(now)
	def export_csv(self):
		util.write_csv(self.csv, list(self.history))

parser = argparse.ArgumentParser()
parser.add_argument('station', type=int)
args = parser.parse_args()
util.init_logging()
with open('sensor.json') as json_file:
	json_config = json_file.read()
sensor_json = json.loads(json_config)
sensor = list()
for id, attr in sensor_json.items():
	if attr['station'] != args.station:
		continue
	sensor.append(Sensor(id, attr['file']))

while True:
	start = time.perf_counter()
	logging.info('collect data')
	files = list()
	for s in sensor:
		s.read_value()
		s.export_csv()
		files.append(s.csv)
	logging.info('copy to webserver')
	if files:
		if os.system('scp {} {}'.format(' '.join(files), config.client_server)):
			logging.error('scp failed')
	util.memory_check()
	logging.info('sleep, duration was {}s'.format(
		round(time.perf_counter() - start)))
	time.sleep(config.interval_seconds)
