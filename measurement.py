import scipy.misc
import subprocess
import numpy

def w1_temp(file):
	with open(file) as w1_file:
		if w1_file.readline().strip().endswith('YES'):
			return int(w1_file.readline().split('t=')[-1].strip()) / 1e3
		else:
			raise Exception('sensor says no')

def _parse_segment(image):
	scipy.misc.imsave('seven_segment.png', image)
	command = ['ssocr/ssocr', '--number-digits=2', '--background=black', 'seven_segment.png']
	try:
		return int(subprocess.check_output(command))
	except (subprocess.CalledProcessError, ValueError) as err:
		logging.error(err)
		return None

def _parse_light(image):
	hist, bin_edges = numpy.histogram(image, bins=4, range=(0,255), density=True)
	return hist[3] > 0.006

def thermosolar_ocr(file):
	if subprocess.call(['fswebcam', '--device', file, 'thermosolar.jpg']):
		raise Exception('camera failure')
	image = scipy.misc.imread('thermosolar.jpg')
	top, left, height, width = 11, 76, 76, 123
	seven_segment = image[top:top+height, left:left+width]
	top, left, length = 146, 128, 15
	pump_light = image[top:top+length, left:left+length]
	return parse_segment(seven_segment), parse_light(pump_light)
