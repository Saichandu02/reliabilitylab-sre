#!/usr/bin/env python3
"""Tiny local Alertmanager webhook sink for demos.

Prints every alert payload it receives as JSON lines. This is the local
notification receiver referenced by alertmanager/config.yml — alerts go
nowhere external unless you configure a real destination yourself.
"""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        payload = self.rfile.read(length).decode()
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            pass
        print(json.dumps({"received_alerts": payload}), flush=True)
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", 5001), Handler).serve_forever()
