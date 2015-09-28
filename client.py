#!/usr/bin/env python3

import argparse
import csv
import datetime
import json
import logging
import subprocess
import time

import numpy
import scipy.misc

import utility


CLIENT_SERVER = 'kaloix@adhara.uberspace.de:home-sensor/'
DATA_DIR = 'data/'
SAMPLING_INTERVAL = datetime.timedelta(minutes=1)


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('station', type=int)
	args = parser.parse_args()
	utility.init()
	with open('sensor.json') as json_file:
		sensor_json = json_file.read()
	sensors = list()
	for device in json.loads(sensor_json):
		if device['input']['station'] != args.station:
			continue
		if device['input']['type'] == 'ds18b20':
			sensors.append(DS18B20(
				device['output']['temperature']['name'],
				device['input']['file']))
		elif device['input']['type'] == 'thermosolar':
			sensors.append(Thermosolar(
				device['output']['temperature']['name'],
				device['output']['switch']['name'],
				device['input']['file']))
	transmit = utility.Timer(utility.TRANSMIT_INTERVAL)
	while True:
		start = time.time()
		for sensor in sensors:
			sensor.update()
		if transmit.check():
			logging.info('copy to webserver')
			if subprocess.call(['rsync',
			                    '--recursive',
			                    '--rsh=ssh',
			                    DATA_DIR,
			                    '{}{}'.format(CLIENT_SERVER, DATA_DIR)]):
				logging.error('scp failed')
		logging.info('sleep, duration was {}s'.format(
			round(time.time() - start)))
		time.sleep(SAMPLING_INTERVAL.total_seconds())


def w1_temp(file):
	try:
		with open(file) as w1_file:
			if w1_file.readline().strip().endswith('YES'):
				return int(w1_file.readline().split('t=')[-1].strip()) / 1e3
			else:
				raise SensorError('w1 sensor says no')
	except (OSError, ValueError) as err:
		raise SensorError('invalid w1 file') from err


def _make_box(image, left, top, right, bottom):
	left -= 1
	top -= 1
	right += 1
	bottom += 1
	width = 3
	color = (204, 41, 38)
	image[top-width:bottom+width,left-width:left       ] = color
	image[top-width:bottom+width,right     :right+width] = color
	image[top-width:top         ,left-width:right+width] = color
	image[bottom   :bottom+width,left-width:right+width] = color
	return image


def _parse_segment(image):
	scipy.misc.imsave('seven_segment.png', image)
	try:
		ssocr_output = subprocess.check_output(['./ssocr',
		                                        '--number-digits=2',
		                                        '--number-pixels=3',
		                                        '--one-ratio=2.3',
		                                        '--threshold=98',
		                                        'invert',
		                                        'seven_segment.png'])
	except subprocess.CalledProcessError as err:
		raise SensorError('ssocr failure') from err
	logging.debug('parse_segment: ssocr_output={}'.format(ssocr_output))
	try:
		return int(ssocr_output)
	except ValueError as err:
		raise SensorError('invalid ssocr output') from err


def _parse_light(image):
	hist, bin_edges = numpy.histogram(
		image, bins=4, range=(0,255), density=True)
	decider = round(hist[3], ndigits=5)
	threshold = 0.006
	result = decider > threshold
	logging.debug('parse_light: {} with decider={} threshold={}'.format(
		'ON' if result else 'OFF', decider, threshold))
	return result


def _thermosolar_ocr_single(file):
	# capture image
	if subprocess.call(['fswebcam',
	                    '--device', file,
	                    '--quiet',
	                    '--title', 'Thermosolar',
	                    'thermosolar.jpg']):
		raise SensorError('camera failure')
	image = scipy.misc.imread('thermosolar.jpg')
	# crop seven segment
	left, top, right, bottom = 67, 53, 160, 118
	seven_segment = image[top:bottom, left:right]
	image = _make_box(image, left, top, right, bottom)
	# crop pump light
	left, top, right, bottom = 106, 157, 116, 166
	pump_light = image[top:bottom, left:right]
	image = _make_box(image, left, top, right, bottom)
	# export boxes
	scipy.misc.imsave(DATA_DIR+'thermosolar.jpg', image) # FIXME
	return _parse_segment(seven_segment), _parse_light(pump_light)


def thermosolar_ocr(file):
	result = _thermosolar_ocr_single(file)
	time.sleep(0.5)
	if _thermosolar_ocr_single(file) != result:
		raise SensorError('ocr results differ')
	return result


class SensorError(Exception):
	pass


class Series(object):

	def __init__(self, name):
		self.name = name

	def write(self, value):
		now = datetime.datetime.now()
		filename = '{}/{}_{}.csv'.format(DATA_DIR, self.name, now.year)
		with open(filename, mode='a', newline='') as csv_file:
			self.writer = csv.writer(csv_file)
			self.writer.writerow((int(now.timestamp()), value))


class DS18B20(object):

	def __init__(self, name, file):
		self.history = Series(name)
		self.file = file
		self.name = name

	def update(self):
		logging.info('update DS18B20 {}'.format(self.name))
		try:
			temperature = w1_temp(self.file)
		except SensorError as err:
			logging.error('DS18B20 failure: {}'.format(err))
		else:
			self.history.write(temperature)


class Thermosolar(object):

	def __init__(self, temperature_name, pump_name, file):
		self.temp_hist = Series(temperature_name)
		self.pump_hist = Series(pump_name)
		self.file = file
		self.name = '{}-{}'.format(temperature_name, pump_name)

	def update(self):
		logging.info('update Thermosolar {}'.format(self.name))
		try:
			temp, pump = thermosolar_ocr(self.file)
		except SensorError as err:
			logging.error('Thermosolar failure: {}'.format(err))
		else:
			self.temp_hist.write(temp)
			self.pump_hist.write(pump)


if __name__ == "__main__":
	main()
