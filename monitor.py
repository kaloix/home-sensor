import contextlib
import http.client
import http.server
import json
import logging
import queue
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
		with open(TOKEN_FILE) as token_file:
			self.token = token_file.readline().strip()
		self.context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
		self.context.verify_mode = ssl.CERT_REQUIRED
		self.context.load_verify_locations(CERT)
		self.buffer = queue.Queue()
		self.buffer_send = threading.Event()
		self.buffer_mutex = threading.Lock()

	def __enter__(self):
		self.shutdown = False
		self.sender = threading.Thread(target=self._sender)
		self.sender.start()
		return self

	def __exit__(self, exc_type, exc_value, traceback):
		logging.info('wait for empty buffer')
		self.shutdown = True
		self.buffer_send.set()
		self.sender.join()

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
		before = self.buffer.qsize()
		start = time.perf_counter()
		conn = http.client.HTTPSConnection(HOST, PORT, context=self.context)
		with contextlib.closing(conn) as self.conn:
			while True:
				item = self.buffer.get(block=False)
				try:
					succes = self._send(**item)
				except MonitorError as err:
					logging.error('unable to send {}: {}'.format(item, err))
				except (http.client.HTTPException, OSError) as err:
					logging.warning('postpone send: {}'.format(
						type(err).__name__))
					self.buffer.put(item)
					break
		number = before - self.buffer.qsize()
		if number:
			logging.info('sent {} item{} in {:.1f}s'.format(
				number, '' if number==1 else 's', time.perf_counter()-start))

	def _sender(self):
		while True:
			if not self.shutdown:
				self.buffer_send.wait()
			time.sleep(INTERVAL)
			with self.buffer_mutex:
				try:
					self._send_buffer()
				except queue.Empty:
					self.buffer_send.clear()
					if self.shutdown:
						break

	def send(self, **kwargs):
		with self.buffer_mutex:
			self.buffer.put(kwargs)
			self.buffer_send.set()


class MonitorServer:

	def __init__(self, verify_function):
		self.httpd = http.server.HTTPServer(('', PORT), HTTPRequestHandler)
		self.httpd.socket = ssl.wrap_socket(self.httpd.socket,
		                                    keyfile=KEY, certfile=CERT,
		                                    server_side=True)
		self.httpd.verify = verify_function
		self.httpd.inbox = queue.Queue()
		with open(TOKEN_FILE) as token_file:
			self.httpd.token = [t.strip() for t in token_file]

	def __enter__(self):
		self.server = threading.Thread(target=self.httpd.serve_forever)
		self.server.start()
		return self

	def __exit__(self, exc_type, exc_value, traceback):
		logging.info('shutdown monitor server')
		self.httpd.shutdown()
		self.server.join()

	def fetch(self):
		with contextlib.suppress(queue.Empty):
			while True:
				yield self.httpd.inbox.get(block=False)


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
			self.server.inbox.put(self.server.verify(**data))
		except Exception as err:
			logging.error('{}: {}'.format(type(err).__name__, err))
			self.send_error(400, 'bad parameters')
		else:
			self.send_response(201, 'value received')
		self.end_headers()

	def log_error(self, format_, *args):
		logging.warning('ip {}, {}'.format(self.address_string(),
		                                   format_ % args))

	def log_message(self, format_, *args):
		pass


class MonitorError(Exception):
	pass
