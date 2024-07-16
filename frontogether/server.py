import http.server
import socketserver
import logging


class Server:
    def __init__(self):
        self._port = 8000
        self._running = True

    def stop(self):
        self._running = False

    def run(self):
        logging.info("running server at port %d", self._port)
        self._running = True
        Handler = http.server.SimpleHTTPRequestHandler

        with socketserver.TCPServer(("", self._port), Handler) as httpd:
            httpd.timeout = 0.5
            while self._running:
                httpd.handle_request()

