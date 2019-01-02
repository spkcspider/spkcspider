#! /usr/bin/python3

from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
import hashlib
from urllib.parse import parse_qs, urlsplit


class ReferrerServer(HTTPServer):
    tokens = None
    runthread = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tokens = []
        self.runthread = threading.Thread(target=self.serve_forever)
        self.runthread.daemon = True
        self.runthread.run()


class ReferrerHandler(BaseHTTPRequestHandler):
    secret = None
    query = None

    def do_POST(self):
        length = self.headers.get('content-length')
        if not length:
            self.send_error(400)
            return
        self.secret = self.rfile.read(int(length))

    def do_GET(self):
        sp = urlsplit(self.address_string())
        self.query = parse_qs(sp.query)
        # check secret
        if not self.secret:
            hdigest = "None"
        else:
            h = hashlib.new(self.query.get("algorithm", "sha512"))
            h.update(self.secret)
            hdigest = h.hexdigest()

        if "hash" not in self.query:
            answer = "Hash: {}\nnothing, unrelated query".format(hdigest)
            answer = answer.encode("utf8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", "{}".format(len(answer)))
            self.end_headers()
            self.wfile.write(answer)
        elif hdigest == self.query["hash"]:
            self.server.tokens.append(self.secret)
            answer = "Hash: {}\nsuccess".format(hdigest)
            answer = answer.encode("utf8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", "{}".format(len(answer)))
            self.end_headers()
            self.wfile.write(answer)
        else:
            self.send_error(400, explain="Hash Mismatch")


def create_referrer_server(addrtup):
    server = ReferrerServer(addrtup, ReferrerHandler)
    return server


if __name__ == "__main__":
    s = create_referrer_server(("127.0.0.1", 8001))
    s.runthread.join()
