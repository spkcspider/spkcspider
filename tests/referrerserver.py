from http.server import BaseHTTPRequestHandler, HttpServer
import threading
import copy

PORT = 8000


class ReferrerServer(HttpServer):
    tokens = None
    runthread = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tokens = []
        self.runthread = threading.Thread(target=self.server_forever)
        self.runthread.daemon = True
        self.runthread.run()


class ReferrerHandler(BaseHTTPRequestHandler):
    secret = None

    def do_POST(self):
        length = self.headers.get('content-length')
        if not length:
            self.send_error(400)
            return
        self.secret = self.rfile.read(int(length))

    def do_GET(self):
        if True:
            self.server.tokens.append(self.secret)
        # check secret



def create_referrer_server(addrtup):
    server = HttpServer(addrtup, ReferrerHandler)
    print("serving at port", addrtup)
    return server

with HttpServer(("", PORT), Handler) as httpd:
    print("serving at port", PORT)
    httpd.serve_forever()
