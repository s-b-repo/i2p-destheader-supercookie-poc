#!/usr/bin/env python3
"""A visitor's browser behind the I2P HTTP proxy.

Each visitor has one fixed I2P destination (the shared-client destination the
HTTP proxy reuses for every eepsite, sharedClient=true by default). We pass it
to the shim as X-PoC-Peer-Dest to stand in for the transport-layer identity the
real I2PTunnelHTTPServer reads from the socket -- see server_tunnel_shim.py.

Supports a cookie jar so we can demonstrate that clearing cookies does NOT
break tracking, because the destination header is unaffected.

Run:  python3 visitor.py --via http://127.0.0.1:9101 --dest DEST-ALICE \
                         --path /home --jar /tmp/alice.jar
"""
import argparse
import json
import os
import sys
import urllib.request


def load_jar(path):
    if path and os.path.exists(path):
        try:
            with open(path) as fh:
                return json.load(fh)
        except Exception:
            return {}
    return {}


def save_jar(path, jar):
    if path:
        with open(path, "w") as fh:
            json.dump(jar, fh)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--via", required=True, help="shim base URL")
    ap.add_argument("--dest", required=True, help="this visitor's fixed I2P destination")
    ap.add_argument("--path", default="/")
    ap.add_argument("--jar", help="cookie jar file")
    ap.add_argument("--clear-cookies", action="store_true",
                    help="wipe the cookie jar before the request (user clears cookies)")
    ap.add_argument("--label", default="")
    args = ap.parse_args()

    if args.clear_cookies and args.jar and os.path.exists(args.jar):
        os.remove(args.jar)
        sys.stderr.write("[visitor %s] cleared cookies\n" % args.label)

    jar = load_jar(args.jar)
    host = args.via.split("//", 1)[-1]
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
        "X-PoC-Peer-Dest": args.dest,     # stands in for the I2P transport identity
    }
    if host in jar:
        headers["Cookie"] = "visitor=" + jar[host]

    req = urllib.request.Request(args.via.rstrip("/") + args.path,
                                 headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=10) as r:
        r.read()
        sc = r.headers.get("Set-Cookie")
        if sc and sc.startswith("visitor="):
            jar[host] = sc.split("=", 1)[1].split(";", 1)[0]
    save_jar(args.jar, jar)
    sys.stderr.write("[visitor %s] GET %s%s cookie=%s\n"
                     % (args.label, args.via, args.path, jar.get(host)))


if __name__ == "__main__":
    main()
