import datetime
import email.mime.text
import logging
import smtplib


WARNING_PAUSE = datetime.timedelta(days=1)
ADMIN_ADDRESS = 'stefan@kaloix.de'
USER_ADDRESS = 'stefan@kaloix.de'
ENABLE_EMAIL = True


class NotificationCenter:
	def __init__(self):
		self.warning_pause = dict()

	def _send_email(self, message, address):
		if not ENABLE_EMAIL:
			logging.info('send email disabled')
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
		self._send_email(text, ADMIN_ADDRESS)
	
	def warn_user(self, message, key):
		logging.warning(message)
		logging.debug(key)
		now = datetime.datetime.now()
		if key in self.warning_pause and self.warning_pause[key] > now:
			logging.info('suppress email')
			return
		self._send_email(message, USER_ADDRESS)
		self.warning_pause[key] = now + WARNING_PAUSE
