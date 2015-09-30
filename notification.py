import datetime
import email.mime.text
import logging
import smtplib


WARNING_PAUSE = datetime.timedelta(days=1)
ADMIN_ADDRESS = 'stefan@kaloix.de'
USER_ADDRESS = 'stefan@kaloix.de'


def send_email(subject, message, address):
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


class NotificationCenter:
	def __init__(self):
		self.pause = dict()

	def _sending_guard(self, key, pause):
		if key in self.pause and self.pause[key] > now:
			logging.debug('suppress email')
			return False
		self.pause[key] = datetime.datetime.now() + pause
		return True
	
	def crash_report(self, message):
		logging.error(message)
		send_email('Programmabsturz', message, ADMIN_ADDRESS)
	
	def user_warning(self, message):
		logging.warning(message)
		if self._sending_guard(hash(message), WARNING_PAUSE):
			send_email('Warnung', message, USER_ADDRESS)
