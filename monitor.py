import http.client
import http.server
import json
import logging
import ssl


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

	def send(self, **kwargs):
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
			response = conn.getresponse()
			conn.close()
		except OSError as err:
			raise MonitorError(str(err)) from None # FIXME buffer instead
		if response.status != 201:
			raise MonitorError('{} {}'.format(response.status,
			                                  response.reason))


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
		if type(data) is not dict or '_token' not in data:
			self.send_error(401, 'missing api token')
			self.end_headers()
			return
		if data.pop('_token') not in self.server.token:
			self.send_error(401, 'invalid api token')
			self.end_headers()
			return
		try:
			self.server.handle(data)
		except MonitorError as err:
			self.send_error(400, 'bad parameters', str(err))
			self.end_headers()
			return
		self.send_response(201, 'value received')
		self.end_headers()


class MonitorError(Exception):
	pass
