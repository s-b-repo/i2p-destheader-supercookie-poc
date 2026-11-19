#!/usr/bin/env python3
"""An eepsite's backend web application (what the operator runs behind the
I2P HTTP server tunnel). It does NOTHING unusual -- it just reads the headers
the tunnel gives it. The point of the PoC is that one of those headers,
X-I2P-DestB32, is a stable per-visitor identifier the operator never had to
ask for and the visitor cannot suppress.

For contrast it also sets an ordinary cookie. The cookie is the identifier a
visitor CAN clear; the destination header is the one they cannot.

Logs one JSON line per request to the shared log file.
Run:  python3 eepsite_backend.py --site A --port 9001 --log logs/siteA.jsonl
"""
import argparse
import json
import os
import sys
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie

LOGFILE = None
SITE = None


class Backend(BaseHTTPRequestHandler):
    server_version = "eepsite-app/1.0"

    def do_GET(self):
        dest = self.headers.get("X-I2P-DestB32")       # injected by the tunnel
        cookie_hdr = self.headers.get("Cookie")
        cookie_id = None
        if cookie_hdr:
            c = SimpleCookie(cookie_hdr)
            if "visitor" in c:
                cookie_id = c["visitor"].value

        set_cookie = None
        if not cookie_id:
            cookie_id = "ck-" + uuid.uuid4().hex[:12]
            set_cookie = "visitor=%s; Path=/" % cookie_id

        rec = {
            "site": SITE,
            "ts": round(time.time(), 3),
            "path": self.path,
            "dest_b32": dest,          # <-- stable, operator didn't ask for it
            "cookie": cookie_id,       # <-- clearable by the visitor
        }
        with open(LOGFILE, "a") as fh:
            fh.write(json.dumps(rec) + "\n")
        sys.stderr.write("[site %s] path=%s dest=%s cookie=%s\n"
                         % (SITE, self.path, dest, cookie_id))

        body = ("<!doctype html><title>eepsite %s</title>"
                "<h1>eepsite %s</h1><p>dest seen by app: %s</p>"
                % (SITE, SITE, dest)).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        if set_cookie:
            self.send_header("Set-Cookie", set_cookie)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def main():
    global LOGFILE, SITE
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", required=True)
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--log", required=True)
    args = ap.parse_args()
    LOGFILE = args.log
    SITE = args.site
    os.makedirs(os.path.dirname(LOGFILE) or ".", exist_ok=True)
    httpd = ThreadingHTTPServer(("127.0.0.1", args.port), Backend)
    sys.stderr.write("[site %s] backend on :%d  ->  %s\n"
                     % (SITE, args.port, LOGFILE))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
