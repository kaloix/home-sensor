import logging
import subprocess
import scipy.misc
import numpy

def w1_temp(file):
	with open(file) as w1_file:
		if w1_file.readline().strip().endswith('YES'):
			return int(w1_file.readline().split('t=')[-1].strip()) / 1e3
		else:
			raise Exception('sensor says no')

def _parse_segment(image):
	scipy.misc.imsave('seven_segment.png', image)
	try:
		ssocr_output = subprocess.check_output([
			'./ssocr',
			'--number-digits=2',
			'--threshold=98',
			'invert',
			'seven_segment.png'])
	except subprocess.CalledProcessError as err:
		logging.error(err)
		return None
	try:
		return int(ssocr_output)
	except ValueError as err:
		logging.error(err)
		return None

def _parse_light(image):
	hist, bin_edges = numpy.histogram(
		image, bins=4, range=(0,255), density=True)
	return hist[3] > 0.006

def thermosolar_ocr(file):
	if subprocess.call([
			'fswebcam',
			'--device', file,
			'--quiet',
			'thermosolar.jpg']):
		raise Exception('camera failure')
	image = scipy.misc.imread('thermosolar.jpg')
	left, top, right, bottom = 67, 53, 160, 118
	seven_segment = image[top:bottom, left:right]
	left, top, right, bottom = 106, 157, 116, 166
	pump_light = image[top:bottom, left:right]
	return _parse_segment(seven_segment), _parse_light(pump_light)
