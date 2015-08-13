#!/usr/bin/env python3

import collections
import random
import json
import argparse
import time
import os
import util
import logging

class Sensor:
	def __init__(self, id, file, parser):
		self.file = file
		self.parser = parser
		self.history = collections.deque()
		self.csv = 'csv/{}.csv'.format(id)
		try:
			data = util.read_csv(self.csv)
		except FileNotFoundError as err:
			logging.warning('backup not found: {}'.format(err))
		else:
			for d in data:
				self.history.append(tuple(map(float, d)))
			logging.info('backup restored for {}'.format(id))

	def update(self):
		now = time.time()
		value = self.parser(self.file)
		self.history.append((now, value))
		history_seconds = config['history_hours'] * 60 * 60
		while self.history[0][0] < now - history_seconds:
			self.history.popleft()

def parse_temp(file):
	# TODO parse self.file
	return random.randrange(180, 500) / 10

parser = argparse.ArgumentParser()
parser.add_argument('station', type=int)
args = parser.parse_args()
util.init_logging()
with open('config.json') as json_file:
	json_config = json_file.read()
config = json.loads(json_config)
sensor = list()
for id, attr in config['sensor'].items():
	if attr['station'] != args.station:
		continue
	if attr['type'] == 'temperature':
		sensor.append(Sensor(id, attr['file'], parse_temp))

def loop():
	logging.info('collect data')
	files = list()
	for s in sensor:
		try:
			s.update()
		except Exception as err:
			logging.error(err)
		else:
			util.write_csv(s.csv, s.history)
			files.append(s.csv)

	logging.info('copy to webserver')
	if files:
		if os.system('scp {} {}'.format(' '.join(files), config['server'])):
			logging.error('scp failed')

while True:
	loop()
	logging.info('sleep')
	time.sleep(config['update_minutes']*60)
