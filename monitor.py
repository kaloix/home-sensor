import http.client
import http.server
import json
import logging
import ssl
import threading
import time

import utility


CERT = 'server.crt'
CONTENT_TYPE = 'application/json'
HEADERS = {'Content-type': 'application/json', 'Accept': 'text/plain'}
HOST = 'kaloix.de'
KEY = 'server.key'
PORT = 64918
TOKEN_FILE = 'api_token'
INTERVAL = 60


class MonitorClient:

	def __init__(self):
		# client authentication
		with open(TOKEN_FILE) as token_file:
			self.token = token_file.readline().strip()
		# connection encryption
		self.context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
		self.context.verify_mode = ssl.CERT_REQUIRED
		self.context.load_verify_locations(CERT)
		# data buffer
		self.buffer = list()
		self.buffer_send = threading.Event()
		self.buffer_mutex = threading.Lock()
		self.buffer_block = time.perf_counter()
		# sender thread
		self.shutdown = False
		self.sender = threading.Thread(target=self._sender)
		self.sender.start()

	def _send(self, **kwargs):
		logging.debug('send {}'.format(kwargs))
		kwargs['_token'] = self.token
		try:
			body = json.dumps(kwargs)
		except TypeError as err:
			raise MonitorError(str(err)) from None
		try:
			conn = http.client.HTTPSConnection(HOST, PORT,
			                                   context=self.context)
			conn.request('POST', '', body, HEADERS)
			resp = conn.getresponse()
			conn.close()
		except OSError as err:
			logging.warning(str(err))
			return False
		if resp.status == 201:
			return True
		else:
			raise MonitorError('{} {}'.format(resp.status, resp.reason))

	def _send_buffer(self):
		repeat = list()
		for item in self.buffer:
			try:
				success = self._send(*item)
			except MonitorError as err:
				logging.error('unable to send: {}'.format(err))
			else:
				if not success:
					repeat.append(item)
		self.buffer = repeat
		if not self.buffer:
			self.buffer_send.clear()

	def _sender(self):
		while not self.shutdown:
			# wait for data
			self.buffer_send.wait()
			# wait for interval
			now = time.perf_counter()
			delay = now - self.buffer_block
			if delay > 0:
				time.sleep(delay)
			# send buffer
			with self.buffer_mutex:
				try:
					self._send_buffer()
				except MonitorError as err:
					logging.warning('send fail: {}'.format(err))
			# reset interval
			self.buffer_block = now + INTERVAL

	def send(self, data):
		with self.buffer_mutex:
			self.buffer.append(data)
			self.buffer_send.set()

	def close(self):
		self.shutdown = True
		self.sender.join()


class MonitorServer:

	def __init__(self, handle_function):
		self.httpd = http.server.HTTPServer(('', PORT), HTTPRequestHandler)
		self.httpd.socket = ssl.wrap_socket(self.httpd.socket,
		                                    keyfile=KEY, certfile=CERT,
		                                    server_side=True)
		self.httpd.handle = handle_function
		with open(TOKEN_FILE) as token_file:
			self.httpd.token = [t.strip() for t in token_file]
		self.httpd.serve_forever() # FIXME make concurrent


class HTTPRequestHandler(http.server.BaseHTTPRequestHandler):

	def do_POST(self):
		if self.headers['content-type'] != CONTENT_TYPE:
			self.send_error(400, 'bad content type')
			self.end_headers()
			return
		try:
			content_length = int(self.headers['content-length'])
			content = self.rfile.read(content_length).decode()
			data = json.loads(content)
		except ValueError as err:
			self.send_error(400, 'bad json', str(err))
			self.end_headers()
			return
		if type(data) is not list or not data:
			self.send_error(401, 'missing api token')
			self.end_headers()
			return
		if data[0] not in self.server.token:
			self.send_error(401, 'invalid api token')
			self.end_headers()
			return
		try:
			self.server.handle(data[1:])
		except MonitorError as err:
			self.send_error(400, 'bad parameters', str(err))
			self.end_headers()
			return
		self.send_response(201, 'value received')
		self.end_headers()


class MonitorError(Exception):
	pass
