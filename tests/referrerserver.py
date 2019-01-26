#! /usr/bin/python3

from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
import hashlib
from urllib.parse import parse_qs, urlsplit


class ReferrerServer(HTTPServer):
    tokens = None
    unverified = None
    runthread = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tokens = {}
        self.unverified = {}
        self.runthread = threading.Thread(target=self.serve_forever)
        self.runthread.daemon = True


class ReferrerHandler(BaseHTTPRequestHandler):
    query = None

    def do_POST(self):
        length = self.headers.get('content-length')
        if not length:
            self.send_error(400)
            return

        self.query = parse_qs(self.rfile.read(int(length)))
        self.log_message("query: %s", str(self.query))

        algo = self.query.get(
            b"hash_algorithm", [b"sha512"]
        )[0].decode("ascii")
        h = hashlib.new(algo)
        h.update(self.query[b"token"][0])
        hdigest = h.hexdigest()

        self.server.unverified[hdigest] = {
            "token": self.query[b"token"][0].decode("ascii"),
            "referrer": self.headers.get("Referer", "None"),
            "digest": hdigest
        }
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        sp = urlsplit(self.path)
        self.query = parse_qs(sp.query)
        # check secret

        if "token" in self.query and "hash" not in self.query:
            answer = (
                "Token: {}\nserverless success"
            ).format(
                self.query["token"][0]
            )
            answer = answer.encode("utf8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", "{}".format(len(answer)))
            self.end_headers()
            self.wfile.write(answer)
        elif "hash" not in self.query:
            answer = "Hash: None\nnothing, unrelated query"
            answer = answer.encode("utf8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", "{}".format(len(answer)))
            self.end_headers()
            self.wfile.write(answer)
        elif self.query["hash"][0] in self.server.unverified:
            self.server.tokens[self.query["hash"][0]] = \
                self.server.unverified.pop(self.query["hash"][0])
            answer = "Token: {}\nHash: {}\nReferrer: {}\nsuccess".format(
                self.server.tokens[self.query["hash"][0]]["token"],
                self.query["hash"][0],
                self.server.tokens[self.query["hash"][0]]["referrer"]
            )
            answer = answer.encode("utf8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", "{}".format(len(answer)))
            self.end_headers()
            self.wfile.write(answer)
        elif self.query["hash"][0] in self.server.tokens:
            answer = "Token: {}\nHash: {}\nReferrer: {}\nalready verified".\
                format(
                    self.server.tokens[self.query["hash"][0]]["token"],
                    self.query["hash"][0],
                    self.server.tokens[self.query["hash"][0]]["referrer"]
                )
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
    s.runthread.start()
    s.runthread.join()
