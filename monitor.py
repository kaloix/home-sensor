import http.client
import http.server
import json
import logging
import ssl
import threading
import time


CERT = 'server.crt'
CONTENT_TYPE = 'application/json'
HOST = 'kaloix.de'
KEY = 'server.key'
PORT = 64918
TOKEN_FILE = 'api_token'
INTERVAL = 10


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
		kwargs['_token'] = self.token
		try:
			body = json.dumps(kwargs)
		except TypeError as err:
			raise MonitorError(str(err))
		headers = {'Content-type': CONTENT_TYPE, 'Accept': 'text/plain'}
		self.conn.request('POST', '', body, headers)
		resp = self.conn.getresponse()
		if resp.status != 201:
			raise MonitorError('{} {}'.format(resp.status, resp.reason))

	def _send_buffer(self):
		for index, item in enumerate(self.buffer):
			try:
				self.conn = http.client.HTTPSConnection(HOST, PORT,
				                                        context=self.context)
				success = self._send(**item)
				self.conn.close()
			except MonitorError as err:
				logging.error('unable to send {}: {}'.format(item, err))
			except (http.client.HTTPException, OSError) as err:
				logging.warning(
					'postpone send: {} {}'.format(type(err).__name__, err))
				self.buffer = self.buffer[index:]
				break
		else:
			self.buffer = list()
			self.buffer_send.clear()

	def _sender(self):
		while not self.shutdown or self.buffer:
			self.buffer_send.wait()
			delay = self.buffer_block - time.perf_counter()
			if delay > 0:
				time.sleep(delay)
			with self.buffer_mutex:
				self._send_buffer()
			self.buffer_block = time.perf_counter() + INTERVAL

	def send(self, **kwargs):
		with self.buffer_mutex:
			self.buffer.append(kwargs)
			self.buffer_send.set()

	def close(self):
		logging.info('shutdown registered')
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

	def __enter__(self):
		self.server = threading.Thread(target=self.httpd.serve_forever)
		self.server.start()

	def __exit__(self, exc_type, exc_value, traceback):
		logging.info('shutdown registered')
		self.httpd.shutdown()
		self.server.join()


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
		if type(data) is not dict or '_token' not in data:
			self.send_error(401, 'missing api token')
			self.end_headers()
			return
		if data.pop('_token') not in self.server.token:
			self.send_error(401, 'invalid api token')
			self.end_headers()
			return
		try:
			self.server.handle(**data)
		except MonitorError as err:
			logging.warning(str(err))
			self.send_error(400, 'bad parameters')
		except Exception as err:
			logging.error('{}: {}'.format(type(err).__name__, err))
			self.send_error(400, 'invalid parameters')
		else:
			self.send_response(201, 'value received')
		self.end_headers()

	def log_error(self, format_, *args):
		logging.warning('ip {}, {}'.format(self.address_string(),
		                                   format_ % args))

	def log_message(self, *args):
		pass


class MonitorError(Exception):
	pass
