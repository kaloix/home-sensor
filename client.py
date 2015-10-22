#!/usr/bin/env python3

import argparse
import contextlib
import datetime
import functools
import json
import logging
import subprocess
import time

import numpy
import scipy.misc

import monitor
import utility


CLIENT_INTERVAL = datetime.timedelta(seconds=10)
CLIENT_SERVER = 'kaloix@adhara.uberspace.de:home-sensor/'
DATA_DIR = 'data/'
TRANSMIT_INTERVAL = datetime.timedelta(minutes=10)


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('station', type=int)
	args = parser.parse_args()
	utility.init()
	with open('sensor.json') as json_file:
		sensor_json = json_file.read()
	sensors = list()
	for sensor in json.loads(sensor_json):
		if sensor['input']['station'] != args.station:
			continue
		if sensor['input']['type'] == 'mdeg_celsius':
			sensors.append(Sensor(
				[sensor['output']['temperature']['name']],
				functools.partial(mdeg_celsius, sensor['input']['file']),
				sensor['input']['interval']))
		if sensor['input']['type'] == 'ds18b20':
			sensors.append(Sensor(
				[sensor['output']['temperature']['name']],
				functools.partial(ds18b20, sensor['input']['file']),
				sensor['input']['interval']))
		elif sensor['input']['type'] == 'thermosolar':
			sensors.append(Sensor(
				[sensor['output']['temperature']['name'],
					sensor['output']['switch']['name']],
				functools.partial(thermosolar, sensor['input']['file']),
				sensor['input']['interval']))
	with monitor.MonitorClient as connection:
		while True:
			start = datetime.datetime.now()
			for sensor in sensors:
				with contextlib.suppress(utility.CallDenied):
					sensor.update(connection)
			duration = (datetime.datetime.now() - start).total_seconds()
			#logging.debug('sleep, duration was {:.1f}s'.format(duration))
			time.sleep(CLIENT_INTERVAL.total_seconds())


def mdeg_celsius(file):
	try:
		with open(file) as mdc_file:
			return (int(mdc_file.read()) / 1e3,) # FIXME
	except (OSError, ValueError) as err:
		raise SensorError('invalid millidegrees-celsius file') from err


def ds18b20(file):
	try:
		with open(file) as w1_file:
			if not w1_file.readline().strip().endswith('YES'):
				raise SensorError('w1 sensor says no')
			t_value = w1_file.readline().split('t=')[-1].strip()
	except OSError as err:
		raise SensorError('invalid w1 file') from err
	try:
		return (int(t_value) / 1e3,) # FIXME
	except ValueError as err:
		raise SensorError('invalid t value in w1 file') from err


def thermosolar(file):
	result = _thermosolar_once(file)
	time.sleep(0.5)
	if _thermosolar_once(file) != result:
		raise SensorError('ocr results differ')
	return result


def _thermosolar_once(file):
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
		raise SensorError('ssocr exit code {}'.format(err.returncode)) from err
	try:
		return int(ssocr_output)
	except ValueError as err:
		raise SensorError('invalid ssocr output') from err


def _parse_light(image):
	hist, bin_edges = numpy.histogram(
		image, bins=4, range=(0,255), density=True)
	decider = round(hist[3], ndigits=5) # FIXME
	threshold = 0.006
	return bool(decider > threshold)


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


class Sensor(object):

	def __init__(self, names, reader_function, interval):
		self.names = names
		self.reader = reader_function
		self.update = utility.allow_every_x_seconds(interval)(self.update)

	def __repr__(self):
		return '{} {}'.format(self.__class__.__name__, '/'.join(self.names))

	def update(self, connection):
		logging.info('update {}'.format(self))
		now = datetime.datetime.now()
		try:
			values = self.reader()
		except SensorError as err:
			logging.error('{} failure: {}'.format(self, err))
			return
		for index, name in enumerate(self.names):
			logging.info('{}: {} / {}'.format(name, now, values[index]))
			connection.send(name=name, value=values[index],
			                timestamp=int(now.timestamp()))


class SensorError(Exception):
	pass


if __name__ == "__main__":
	try:
		main()
	except KeyboardInterrupt:
		connection.close()
	except Exception as err:
		logging.error('{}: {}'.format(type(err).__name__, err))
		connection.close()
		raise
	logging.debug('end')
