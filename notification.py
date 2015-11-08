import email.mime.text
import logging
import smtplib
import time
import traceback


ADMIN_ADDRESS = 'stefan@kaloix.de' # TODO move to private file
USER_ADDRESS = 'stefan@kaloix.de'
ENABLE_EMAIL = True


def send_email(subject, message, address):
	if not ENABLE_EMAIL:
		logging.info('email disabled')
		return
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


class NotificationCenter(object):
	def __init__(self):
		self.pause = dict()
		self.outbox = list()

	def __enter__(self):
		return self

	def __exit__(self, exc_type, exc_value, traceback_):
		if exc_type is not None and exc_type is not KeyboardInterrupt:
			tb_lines = traceback.format_tb(traceback_)
			crash_report('{}: {}\n{}'.format(
				exc_type, exc_value, ''.join(tb_lines)))

	def queue(self, message, pause):
		if message is None:
			return
		now = time.perf_counter()
		key = hash(message)
		if key in self.pause and self.pause[key] > now:
			return
		self.pause[key] = now + pause
		logging.warning(message)
		self.outbox.append(message)

	def send_all(self):
		if self.outbox:
			send_email('Warnung', '\n'.join(self.outbox), USER_ADDRESS)
			self.outbox = list()
