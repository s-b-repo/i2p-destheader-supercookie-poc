#!/usr/bin/env bash
# End-to-end driver for the X-I2P-DestB32 supercookie PoC.
# Two independent eepsites (A, B), each = a backend app + an I2PTunnelHTTPServer
# shim. Two visitors (Alice, Bob) with fixed I2P destinations. Shows that the
# destination header links Alice across both sites and across a cookie clear,
# while Bob stays distinct. Python 3 stdlib only.
set -euo pipefail
cd "$(dirname "$0")"

JAR_DIR="$(mktemp -d)"
rm -f logs/siteA.jsonl logs/siteB.jsonl
mkdir -p logs

pids=()
cleanup() { for p in "${pids[@]:-}"; do kill "$p" 2>/dev/null || true; done; rm -rf "$JAR_DIR"; }
trap cleanup EXIT

wait_port() {
  python3 - "$1" <<'PY'
import socket, sys, time
port = int(sys.argv[1])
for _ in range(100):
    s = socket.socket(); s.settimeout(0.2)
    if s.connect_ex(("127.0.0.1", port)) == 0:
        s.close(); sys.exit(0)
    s.close(); time.sleep(0.05)
sys.exit(1)
PY
}

echo ">> starting eepsite A (backend :9001, tunnel shim :9101)"
python3 eepsite_backend.py --site A --port 9001 --log logs/siteA.jsonl & pids+=($!)
python3 server_tunnel_shim.py --port 9101 --backend 127.0.0.1:9001 & pids+=($!)

echo ">> starting eepsite B (backend :9002, tunnel shim :9102)  [different operator]"
python3 eepsite_backend.py --site B --port 9002 --log logs/siteB.jsonl & pids+=($!)
python3 server_tunnel_shim.py --port 9102 --backend 127.0.0.1:9002 & pids+=($!)

for p in 9001 9002 9101 9102; do wait_port "$p" || { echo "port $p failed"; exit 1; }; done

ALICE="DEST-ALICE-aaaaaaaaaaaaaaaaaaaaaaaaaaaa"
BOB="DEST-BOB-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"

echo ">> Alice visits site A (fresh cookie issued)"
python3 visitor.py --via http://127.0.0.1:9101 --dest "$ALICE" --path /home  --jar "$JAR_DIR/alice.jar" --label Alice

echo ">> Alice CLEARS COOKIES, visits site A again (new cookie)"
python3 visitor.py --via http://127.0.0.1:9101 --dest "$ALICE" --path /again --jar "$JAR_DIR/alice.jar" --clear-cookies --label Alice

echo ">> Alice visits site B (different operator)"
python3 visitor.py --via http://127.0.0.1:9102 --dest "$ALICE" --path /read  --jar "$JAR_DIR/alice.jar" --label Alice

echo ">> Bob (different user) visits site A"
python3 visitor.py --via http://127.0.0.1:9101 --dest "$BOB"   --path /home  --jar "$JAR_DIR/bob.jar"   --label Bob

echo
python3 correlate.py --logs logs/siteA.jsonl logs/siteB.jsonl
