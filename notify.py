import email.mime.text
import logging
import smtplib
import time
import traceback


class MailSender(object):
	def __init__(self, source, admin, user, enable):
		self.source = source
		self.admin = admin
		self.user = user
		self.enable = enable
		self.pause = dict()
		self.outbox = list()

	def __enter__(self):
		return self

	def __exit__(self, exc_type, exc_value, traceback_):
		if exc_type is not None and exc_type is not KeyboardInterrupt:
			tb_lines = traceback.format_tb(traceback_)
			msg = '{}: {}\n{}'.format(exc_type, exc_value, ''.join(tb_lines))
			self._send_email('Programmabsturz', msg, self.admin)

	def _send_email(self, subject, message, address):
		if not self.enable:
			logging.info('email disabled: {}'.format(subject))
			return
		msg = email.mime.text.MIMEText(str(message))
		msg['Subject'] = '[Sensor] {}'.format(subject)
		msg['From'] = self.source
		msg['To'] = address
		try:
			s = smtplib.SMTP(host='adhara.uberspace.de', port=587)
			s.starttls()
			s.ehlo()
			s.send_message(msg)
			s.quit()
		except OSError as err:
			logging.error('send email failed: {}'.format(err))

	def queue(self, message, pause):
		now = time.perf_counter()
		key = hash(message)
		if key in self.pause and self.pause[key] > now:
			return
		self.pause[key] = now + pause
		logging.warning(message)
		self.outbox.append(message)

	def send_all(self):
		if self.outbox:
			self._send_email('Warnung', '\n'.join(self.outbox), self.user)
			self.outbox = list()
