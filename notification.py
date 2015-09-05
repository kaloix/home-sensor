import datetime
import email.mime.text
import logging
import smtplib
import config

class NotificationCenter:
	def __init__(self):
		self.warning_pause = dict()
		self.warn_admin('test mail')

	def _send_email(self, message, address):
		return
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
	
	def warn_admin(self, message):
		logging.error(message)
		text = 'Administrator-Meldung:\n{}'.format(message)
		self._send_email(text, config.admin_address)
	
	def warn_user(self, message, key):
		logging.warning(message)
		now = datetime.datetime.now()
		if key in self.warning_pause and self.warning_pause[key] > now:
			logging.info('suppress email')
			return
		self._send_email(message, config.user_address)
		self.warning_pause[key] = now + config.warning_pause
