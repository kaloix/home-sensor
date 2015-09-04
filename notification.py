import datetime
import email.mime.text
import logging
import smtplib
import config

class NotificationCenter:
	def __init__(self):
		self.warning_pause = dict()
		self.admin_error('test mail')

	def send_email(self, message, address):
		logging.info('send email')
		msg = email.mime.text.MIMEText(str(message))
		msg['Subject'] = 'Automatische Nachricht vom Sensor-Server'
		msg['From'] = 'sensor@kaloix.de'
		msg['To'] = address
		try:
			s = smtplib.SMTP(host='adhara.uberspace.de', port=587)
			s.starttls()
			s.ehlo()
			s.send_message(msg)
			s.quit()
		except OSError as err:
			logging.error('send email failed: {}'.format(err))
	
	def admin_error(self, message):
		logging.error(message)
		text = 'Administrator-Meldung:\n{}'.format(message)
		self.send_email(text, config.admin_address)
	
	def user_warning(self, message, id):
		logging.warning(message)
		now = datetime.datetime.now()
		if id in self.warning_pause and self.warning_pause[id] > now:
			logging.info('suppress email')
			return
		self.send_email(message, config.user_address)
		self.warning_pause[id] = now + config.warning_pause

	def sensor_warning(self, id, name):
		text = 'Messpunkt "{}" liefert keine Daten.'.format(name)
		self.user_warning(text, 's'+id)

	def low_warning(self, id, name, measurement):
		text = 'Messpunkt "{}" unterhalb des zulässigen Bereichs:\n{}'.format(name, measurement)
		self.user_warning(text, 'l'+id)

	def high_warning(self, id, name, measurement):
		text = 'Messpunkt "{}" überhalb des zulässigen Bereichs:\n{}'.format(name, measurement)
		self.user_warning(text, 'h'+id)
