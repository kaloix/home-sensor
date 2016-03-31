#!/usr/bin/env python3

import datetime
import json
import logging
import socket
import subprocess
import time

import numpy
import scipy.misc

import api
import utility


CONFIG = 'sensor.json'
INTERVAL = 10


def main():
	utility.logging_config()
	hostname = socket.gethostname()
	with open(CONFIG) as json_file:
		sensor_json = json_file.read()
	sensors = list()
	for sensor in json.loads(sensor_json):
		if sensor['input']['hostname'] != hostname:
			continue
		if sensor['input']['type'] == 'thermosolar':
			sensors.append(Thermosolar(
				sensor['input']['file'],
				[sensor['output']['temperature']['group'],
					sensor['output']['switch']['group']],
				[sensor['output']['temperature']['name'],
					sensor['output']['switch']['name']],
		       sensor['input']['interval']))
		elif sensor['input']['type'] == 'ds18b20':
			sensors.append(DS18B20(
				sensor['input']['file'],
				[sensor['output']['temperature']['group']],
				[sensor['output']['temperature']['name']],
		       sensor['input']['interval']))
		elif sensor['input']['type'] == 'mdeg_celsius':
			sensors.append(MdegCelsius(
				sensor['input']['file'],
				[sensor['output']['temperature']['group']],
				[sensor['output']['temperature']['name']],
				sensor['input']['interval']))
	with api.ApiClient() as connection:
		while True:
			for sensor in sensors:
				now = datetime.datetime.now(tz=datetime.timezone.utc)
				now = now.replace(microsecond=0)
				start = time.perf_counter()
				try:
					result = list(sensor.values())
				except utility.CallDenied:
					continue
				except SensorError as err:
					logging.error('failure {}: {}'.format(sensor, err))
					continue
				logging.info('{} updated in {:.3f}s'.format(
					sensor, time.perf_counter()-start))
				for group, name, value in result:
					logging.info('{}/{}: {} / {}'.format(group, name,
					                                     now, value))
					connection.send(group=group, name=name, value=value,
					                timestamp=int(now.timestamp()))
			time.sleep(INTERVAL)


class Sensor(object):

	def __init__(self, file, groups, names, interval):
		self.file = file
		self.groups = groups
		self.names = names
		self.values = utility.allow_every_x_seconds(interval)(self.values)

	def __repr__(self):
		return '/'.join(self.names)

	def values(self):
		for index, value in enumerate(self.read()):
			yield self.groups[index], self.names[index], value


class Thermosolar(Sensor):

	def read(self):
		result = self.thermosolar_once()
		time.sleep(0.5)
		if self.thermosolar_once() != result:
			raise SensorError('ocr results differ')
		return result

	def thermosolar_once(self):
		# capture image
		if subprocess.call(['fswebcam',
			                '--device', self.file,
			                '--quiet',
			                '--title', 'Thermosolar',
			                'thermosolar.jpg']):
			raise SensorError('camera failure')
		image = scipy.misc.imread('thermosolar.jpg')
		# crop seven segment
		left, top, right, bottom = 46, 53, 160, 118
		seven_segment = image[top:bottom, left:right]
		image = self.make_box(image, left, top, right, bottom)
		# crop pump light
		left, top, right, bottom = 106, 157, 116, 166
		pump_light = image[top:bottom, left:right]
		image = self.make_box(image, left, top, right, bottom)
		# export boxes
		scipy.misc.imsave('thermosolar.jpg', image) # FIXME
		return self.parse_segment(seven_segment), self.parse_light(pump_light)

	def parse_segment(self, image):
		scipy.misc.imsave('seven_segment.png', image)
		try:
			ssocr_output = subprocess.check_output(['./ssocr',
				                                    '--number-digits=-1',
				                                    '--number-pixels=3',
				                                    '--one-ratio=2.3',
				                                    '--threshold=98',
				                                    'invert',
				                                    'seven_segment.png'])
		except subprocess.CalledProcessError as err:
			raise SensorError('ssocr exit code {}'.format(err.returncode)) \
				from err
		try:
			return int(ssocr_output)
		except ValueError as err:
			raise SensorError('invalid ssocr output') from err

	def parse_light(self, image):
		hist, bin_edges = numpy.histogram(
			image, bins=4, range=(0,255), density=True)
		decider = round(hist[3], ndigits=5) # FIXME
		threshold = 0.006
		return bool(decider > threshold)

	def make_box(self, image, left, top, right, bottom):
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


class DS18B20(Sensor):

	def read(self):
		try:
			with open(self.file) as w1_file:
				if not w1_file.readline().strip().endswith('YES'):
					raise SensorError('w1 sensor says no')
				t_value = w1_file.readline().split('t=')[-1].strip()
		except OSError as err:
			raise SensorError('invalid w1 file') from err
		try:
			return int(t_value) / 1e3,
		except ValueError as err:
			raise SensorError('invalid t value in w1 file') from err


class MdegCelsius(Sensor):

	def read(self):
		try:
			with open(self.file) as mdc_file:
				return int(mdc_file.read()) / 1e3,
		except (OSError, ValueError) as err:
			raise SensorError('invalid millidegrees-celsius file') from err


class SensorError(Exception):
	pass


if __name__ == "__main__":
	main()
