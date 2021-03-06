import http.client
import http.server
import json
import logging
import pickle
import socketserver
import ssl
import threading
import time

CONTENT_TYPE = 'application/json'
HOST = 'kaloix.de'
INTERVAL = 10
PORT = 64918
TIMEOUT = 60
SERVER_KEY = 'server.key'
SERVER_CERT = 'server.crt'
CLIENT_KEY = 'client.key'
CLIENT_CERT = 'client.crt'
CLIENT_CERTS = 'clients.crt'


class ApiClient(object):
    def __init__(self):
        context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
        context.verify_mode = ssl.CERT_REQUIRED
        context.load_verify_locations(SERVER_CERT)
        context.load_cert_chain(CLIENT_CERT, keyfile=CLIENT_KEY)
        self.conn = http.client.HTTPSConnection(HOST, PORT, timeout=TIMEOUT,
                                                context=context)
        try:
            with open('buffer.pickle', 'rb') as file:
                self.buffer = pickle.load(file)
        except FileNotFoundError:
            self.buffer = list()
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

    def _sender(self):
        self.buffer_send.wait()
        while not self.shutdown or self.buffer:
            time.sleep(INTERVAL)
            with self.buffer_mutex:
                self._send_buffer()
                self._backup_buffer()
            if not self.shutdown:
                self.buffer_send.wait()

    def _send_buffer(self):
        start = time.perf_counter()
        count = int()
        try:
            self.conn.connect()
            for item in self.buffer:
                try:
                    self._send(**item)
                except ApiError as err:
                    logging.error('unable to send {}: {}'.format(item, err))
                count += 1
        except (http.client.HTTPException, OSError) as err:
            logging.warning('postpone send: {}'.format(type(err).__name__))
        self.buffer = self.buffer[count:]
        if not self.buffer:
            self.buffer_send.clear()
        self.conn.close()
        if count:
            logging.info('sent {} item{} in {:.1f}s'.format(
                count, '' if count == 1 else 's', time.perf_counter() - start))

    def _send(self, **kwargs):
        try:
            body = json.dumps(kwargs)
        except TypeError as err:
            raise ApiError(str(err))
        headers = {'Content-type': CONTENT_TYPE, 'Accept': 'text/plain'}
        self.conn.request('POST', '', body, headers)
        resp = self.conn.getresponse()
        resp.read()
        if resp.status != 201:
            raise ApiError('{} {}'.format(resp.status, resp.reason))

    def _backup_buffer(self):
        with open('buffer.pickle', 'wb') as file:
            pickle.dump(self.buffer, file)

    def send(self, **kwargs):
        with self.buffer_mutex:
            self.buffer.append(kwargs)
            self.buffer_send.set()


class ApiServer(object):
    def __init__(self, handle_function):
        # FIXME removing ThreadingMixIn may resolve problems
        self.httpd = ThreadedHTTPServer(('', PORT), HTTPRequestHandler)
        # TODO do_handshake_on_connect required?
        self.httpd.socket = ssl.wrap_socket(
            self.httpd.socket, keyfile=SERVER_KEY, certfile=SERVER_CERT, server_side=True,
            cert_reqs=ssl.CERT_REQUIRED, ca_certs=CLIENT_CERTS,
            do_handshake_on_connect=False)
        self.httpd.handle = handle_function

    def __enter__(self):
        self.server = threading.Thread(target=self.httpd.serve_forever)
        self.server.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        logging.info('shutdown api server')
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
        if type(data) is not dict:
            self.send_error(401, 'invalid data')
            self.end_headers()
            return
        try:
            self.server.handle(**data)
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


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    pass


class ApiError(Exception):
    pass
