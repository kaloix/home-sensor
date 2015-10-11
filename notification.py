import datetime
import email.mime.text
import logging
import smtplib


WARNING_PAUSE = datetime.timedelta(days=1)
ADMIN_ADDRESS = 'stefan@kaloix.de'
USER_ADDRESS = 'stefan@kaloix.de'
ENABLE_EMAIL = True


def send_email(subject, message, address):
	if not ENABLE_EMAIL:
		logging.info('email disabled')
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


def crash_report(message):
	logging.error(message)
	send_email('Programmabsturz', message, ADMIN_ADDRESS)


class NotificationCenter:
	def __init__(self):
		self.pause = dict()

	def _sending_guard(self, key, pause):
		now = datetime.datetime.now()
		if key in self.pause and self.pause[key] > now:
			logging.debug('suppress email')
			return False
		self.pause[key] = now + pause
		return True
	
	def user_warning(self, message):
		logging.warning(message)
		if self._sending_guard(hash(message), WARNING_PAUSE):
			send_email('Warnung', message, USER_ADDRESS)
