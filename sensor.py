#!/usr/bin/env python3

import collections
import random
import json
import argparse
import time
import os
import util

class Sensor:
	def __init__(self, id, file, parser):
		self.file = file
		self.parser = parser
		self.history = collections.deque()
		self.csv = 'csv/{}.csv'.format(id)
		try:
			data = util.read_csv(self.csv)
		except FileNotFoundError as err:
			print('backup not found: {}'.format(err))
		else:
			for d in data:
				self.history.append(tuple(map(float, d)))
			print('backup restored for {}'.format(id))

	def update(self):
		now = time.time()
		value = self.parser(self.file)
		self.history.append((now, value))
		history_seconds = config['history_hours'] * 60 * 60
		while self.history[0][0] < now - history_seconds:
			self.history.popleft()

def parse_temp(file):
	# TODO parse self.file
	return random.randrange(180, 260) / 10

parser = argparse.ArgumentParser()
parser.add_argument('station', type=int)
args = parser.parse_args()
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
	print('collect data')
	files = list()
	for s in sensor:
		try:
			s.update()
		except Exception as err:
			print('sensor failure: {}'.format(err))
		else:
			util.write_csv(s.csv, s.history)
			files.append(s.csv)

	print('copy to webserver')
	if files:
		os.system('scp {} {}'.format(' '.join(files), config['server_address']))

while True:
	loop()
	print('sleep')
	time.sleep(config['update_minutes']*60)
