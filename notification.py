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
		self.pause = dict()

	def _send_email(self, subject, message, address):
		if not ENABLE_EMAIL:
			logging.info('send email disabled')
			return
		logging.info('send email')
		msg = email.mime.text.MIMEText(str(message))
		msg['Subject'] = '[Sensor] {}'.format(subject)
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
	
	def crash_report(self, message):
		logging.error(message)
		self._send_email('Programmabsturz', message, ADMIN_ADDRESS)
	
	def value_warning(self, message):
		now = datetime.datetime.now()
		logging.warning(message)
		if hash(message) in self.pause and self.pause[hash(message)] > now:
			logging.debug('suppress email')
			return
		self._send_email('Messwerte außerhalb des zulässigen Bereichs',
		                 message, USER_ADDRESS)
		self.pause[hash(message)] = now + WARNING_PAUSE
