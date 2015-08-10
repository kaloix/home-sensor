import smtplib
import email.mime.text
import logging
import config
import time
import datetime

class NotificationCenter:
	warning_pause = dict()

	def send_email(self, message, address):
		logging.info('send email')
		#with open('smtpauth.txt') as smtpauth_file:
		#	user = smtpauth_file.readline().rstrip('\n')
		#	password = smtpauth_file.readline().rstrip('\n')
		msg = email.mime.text.MIMEText(str(message))
		msg['Subject'] = 'Automatische Nachricht vom Sensor-Server'
		msg['From'] = 'sensor@kaloix.de'
		msg['To'] = address
		try:
			s = smtplib.SMTP(host='adhara.uberspace.de', port=587)
			s.starttls()
			s.ehlo()
			#s.login(user, password)
			s.send_message(msg)
			s.quit()
		except OSError as err:
			logging.error('send email failed: {}'.format(err))
	
	def admin_error(self, message):
		logging.error(message)
		self.send_email(message, config.admin_address)
	
	def user_warning(self, message, id):
		logging.warning(message)
		if id in self.warning_pause and self.warning_pause[id] > time.time():
			logging.info('suppress email')
			return
		self.send_email(message, config.user_address)
		self.warning_pause[id] = time.time() + config.warning_pause_seconds

	def measurement_warning(self, measurement, name):
		text = 'Messpunkt "{}" außerhalb des zulässigen Bereichs:\n{:.1f} °C / {:%c}'.format(
			name,
			measurement[0],
			datetime.datetime.fromtimestamp(measurement[1]))
		self.user_warning(text, name)
