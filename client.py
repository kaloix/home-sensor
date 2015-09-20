#!/usr/bin/env python3

import argparse
import json
import logging
import os
import time

import config
import measurement
import util


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('station', type=int)
	args = parser.parse_args()
	util.init()
	with open('sensor.json') as json_file:
		sensor_json = json.loads(json_file.read())
	sensor = list()
	for group, sensor_list in sensor_json.items():
		for s in sensor_list:
			if s['input']['station'] != args.station:
				continue
			if s['input']['type'] == 'ds18b20':
				sensor.append(DS18B20(
					s['input']['file'],
					s['output']['temperature']['name']))
			elif s['input']['type'] == 'thermosolar':
				sensor.append(Thermosolar(
					s['input']['file'],
					s['output']['temperature']['name'],
					s['output']['switch']['name']))
	while True:
		start = time.time()
		logging.info('collect data')
		for s in sensor:
			s.update()
		logging.info('copy to webserver')
		if os.system('scp {0}* {1}{0}'.format(
				config.data_dir, config.client_server)):
			logging.error('scp failed')
		util.memory_check()
		logging.info('sleep, duration was {}s'.format(
			round(time.time() - start)))
		time.sleep(config.transmit_interval.total_seconds())


class DS18B20:

	def __init__(self, file, name):
		self.history = util.FloatHistory(name, None, None)
		self.history.restore(config.data_dir)
		self.file = file

	def update(self):
		try:
			temperature = measurement.w1_temp(self.file)
		except Exception as err:
			logging.error('DS18B20 failure: {}'.format(err))
		else:
			self.history.store(temperature)
			self.history.backup(config.data_dir)


class Thermosolar:

	def __init__(self, file, temperature_name, pump_name):
		self.temp_hist = util.FloatHistory(temperature_name, None, None)
		self.temp_hist.restore(config.data_dir)
		self.pump_hist = util.BoolHistory(pump_name, None)
		self.pump_hist.restore(config.data_dir)
		self.file = file

	def update(self):
		try:
			temp, pump = measurement.thermosolar_ocr(self.file)
		except Exception as err:
			logging.error('Thermosolar failure: {}'.format(err))
			return
		if temp is not None:
			self.temp_hist.store(temp)
			self.temp_hist.backup(config.data_dir)
		if pump is not None:
			self.pump_hist.store(pump)
			self.pump_hist.backup(config.data_dir)


if __name__ == "__main__":
	main()
