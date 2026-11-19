#!/usr/bin/env python3
"""Faithful shim for I2PTunnelHTTPServer's destination-header injection.

This models exactly what apps/i2ptunnel/.../I2PTunnelHTTPServer.java does on
the eepsite side, lines 529-531 (pre-patch):

    addEntry(headers, HASH_HEADER,   peerHash.toBase64());   // X-I2P-DestHash
    addEntry(headers, DEST32_HEADER, peerB32);               // X-I2P-DestB32
    addEntry(headers, DEST64_HEADER, ...toBase64());         // X-I2P-DestB64

Key fidelity points this shim reproduces:
  * It STRIPS any client-supplied X-I2P-Dest* headers first (CLIENT_SKIPHEADERS
    in the real code), so the value the backend sees is not attacker-controlled.
  * It then INJECTS the visitor's destination, taken from the I2P transport
    layer -- NOT from anything the browser sent. The browser cannot remove it
    or forge it.

Because there is no real I2P transport here, the transport-layer peer
destination is supplied to the shim in the request as `X-PoC-Peer-Dest`
(set by visitor.py). That header stands in for `socket.getPeerDestination()`
in the real server; it is stripped before forwarding and never reaches the
backend. In a real deployment the browser has no way to set it.

Run:  python3 server_tunnel_shim.py --port 9101 --backend 127.0.0.1:9001
"""
import argparse
import hashlib
import sys
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BACKEND = None
PEER_DEST_HEADER = "X-PoC-Peer-Dest"          # stand-in for the I2P transport identity
SKIP_FROM_CLIENT = {"x-i2p-desthash", "x-i2p-destb32", "x-i2p-destb64",
                    PEER_DEST_HEADER.lower(), "proxy-connection", "host"}


def derive_dest_ids(peer_dest):
    """Mirror peerHash/peerB32/B64 from one opaque destination string.
    The exact encoding doesn't matter for the PoC; what matters is that it is
    deterministic and unique per visitor, exactly like the real b32."""
    h = hashlib.sha256(peer_dest.encode()).digest()
    b32 = hashlib.sha256(peer_dest.encode()).hexdigest()[:52] + ".b32.i2p"
    return (h.hex(), b32, "B64:" + peer_dest)


class Shim(BaseHTTPRequestHandler):
    server_version = "i2ptunnel-httpserver-shim/1.0"

    def do_GET(self):
        peer_dest = self.headers.get(PEER_DEST_HEADER)
        # forward headers, minus the ones the real server strips from the client
        fwd = {}
        for k in self.headers.keys():
            if k.lower() in SKIP_FROM_CLIENT:
                continue
            fwd[k] = self.headers.get(k)

        # INJECT the visitor's destination from the transport layer (unavoidable)
        if peer_dest:
            dhash, b32, b64 = derive_dest_ids(peer_dest)
            fwd["X-I2P-DestHash"] = dhash
            fwd["X-I2P-DestB32"] = b32
            fwd["X-I2P-DestB64"] = b64

        url = "http://%s%s" % (BACKEND, self.path)
        req = urllib.request.Request(url, headers=fwd, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                body = r.read()
                status = r.status
                resp_headers = r.getheaders()
        except Exception as e:  # noqa
            self.send_response(502)
            self.end_headers()
            self.wfile.write(("backend error: %s" % e).encode())
            return

        self.send_response(status)
        for k, v in resp_headers:
            if k.lower() in ("transfer-encoding", "connection", "content-length"):
                continue
            self.send_header(k, v)   # relay Set-Cookie etc. back to the visitor
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def main():
    global BACKEND
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--backend", required=True, help="host:port of the eepsite app")
    args = ap.parse_args()
    BACKEND = args.backend
    httpd = ThreadingHTTPServer(("127.0.0.1", args.port), Shim)
    sys.stderr.write("[shim] :%d  ->  %s  (injects X-I2P-Dest*)\n"
                     % (args.port, BACKEND))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
