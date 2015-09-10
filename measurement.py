import scipy.misc
import subprocess
import numpy

def parse_w1_temp(file):
	with open(file) as w1_file:
		if w1_file.readline().strip().endswith('YES'):
			return int(w1_file.readline().split('t=')[-1].strip()) / 1e3
		else:
			raise Exception('sensor says no')

class ThermosolarOCR:
	def _parse_segment(self, image):
		scipy.misc.imsave('seven_segment.png', image)
		command = ['ssocr/ssocr', '--number-digits=2', '--background=black', 'seven_segment.png']
		try:
			return int(subprocess.check_output(command))
		except (subprocess.CalledProcessError, ValueError) as err:
			logging.error(err)
	def _parse_light(self, image):
		hist, bin_edges = numpy.histogram(image, bins=4, range=(0,255), density=True)
		return hist[3] > 0.006
	def load_image(self, file):
		image = scipy.misc.imread(file)
		top = 11
		left = 76
		height = 76
		width = 123
		self.seven_segment = image[top:top+height, left:left+width]
		top = 146
		left = 128
		length = 15
		self.pump_light = image[top:top+length, left:left+length]
		top = 147
		left = 98
		self.sensor_light = image[top:top+length, left:left+length]
	def temperature(self):
		return self._parse_segment(self.seven_segment)
	def pump_active(self):
		return self._parse_light(self.pump_light)
	def sensor_failure(self):
		return self._parse_light(self.sensor_light)
