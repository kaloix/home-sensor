import datetime
import email.mime.text
import logging
import smtplib
import traceback


WARNING_PAUSE = datetime.timedelta(days=1)
ADMIN_ADDRESS = 'stefan@kaloix.de' # TODO move to private file
USER_ADDRESS = 'stefan@kaloix.de'
ENABLE_EMAIL = True


def send_email(subject, message, address):
	if not ENABLE_EMAIL:
		logging.info('no email: {}'.format(subject))
		return
	logging.info('email: {}'.format(subject))
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
	send_email('Programmabsturz', message, ADMIN_ADDRESS)


class NotificationCenter:
	def __init__(self):
		self.pause = dict()

	def __enter__(self):
		return self

	def __exit__(self, exc_type, exc_value, traceback_):
		if exc_type is not None and exc_type is not KeyboardInterrupt:
			tb_lines = traceback.format_tb(traceback_)
			crash_report('{}: {}\n{}'.format(
				exc_type, exc_value, ''.join(tb_lines)))

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
