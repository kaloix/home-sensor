class Measurement:
	value = None
	time = None
	
	def __str__(self):
		return '{:.1f} °C / {:%X}'.format(self.value, self.time)
