import http.client
import http.server
import json
import logging
import ssl

import utility


CERT = 'server.crt'
CONTENT_TYPE = 'application/json'
HEADERS = {'Content-type': 'application/json', 'Accept': 'text/plain'}
HOST = 'kaloix.de'
KEY = 'server.key'
PORT = 64918
TOKEN_FILE = 'api_token'


class MonitorClient:

	def __init__(self):
		with open(TOKEN_FILE) as token_file:
			self.token = token_file.readline().strip()
		self.context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
		self.context.verify_mode = ssl.CERT_REQUIRED
		self.context.load_verify_locations(CERT)
		self.buffer = list()

	@utility.allow_every_x_seconds(60)
	def _send_buffer(self):
		logging.debug('send {}'.format(self.buffer))
		try:
			body = json.dumps([self.token] + self.buffer)
		except TypeError as err:
			raise MonitorError(str(err)) from None
		try:
			conn = http.client.HTTPSConnection(HOST, PORT,
			                                   context=self.context)
			conn.request('POST', '', body, HEADERS)
			response = conn.getresponse()
			conn.close()
		except OSError as err:
			raise MonitorError(str(err)) from None
		if response.status != 201:
			raise MonitorError('{} {}'.format(response.status,
			                                  response.reason))

	def send(self, data):
		self.buffer.append(data)
		try:
			self._send_buffer() # FIXME connection with data suboptimal
		except MonitorError as err:
			logging.warning('send fail: {}'.format(err))
		except utility.CallDenied:
			logging.debug('send postpone')
		else:
			self.buffer = list()


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
