class Measurement:
	value = None
	time = None
	
	def __str__(self):
		return '{} °C / {}'.format(self.value, self.time.strftime('%X'))
