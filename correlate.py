#!/usr/bin/env python3
"""Join the two eepsites' access logs and show what the destination header
reveals that cookies do not."""
import argparse
import json
from collections import defaultdict


def load(path):
    out = []
    try:
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
    except FileNotFoundError:
        pass
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--logs", nargs="+", required=True)
    args = ap.parse_args()

    recs = []
    for p in args.logs:
        recs.extend(load(p))
    recs.sort(key=lambda r: r["ts"])

    bar = "=" * 76
    print(bar)
    print("X-I2P-DestB32 SUPERCOOKIE PoC  --  i2p.i2p HTTP server tunnel")
    print(bar)
    print("\nRaw access records (as each eepsite app logged them):\n")
    print("  %-6s %-10s %-14s %-24s" % ("site", "path", "cookie", "dest_b32"))
    for r in recs:
        print("  %-6s %-10s %-14s %-24s"
              % (r["site"], r["path"], r["cookie"], (r["dest_b32"] or "-")[:24]))

    by_dest = defaultdict(list)
    by_cookie = defaultdict(list)
    for r in recs:
        by_dest[r["dest_b32"]].append(r)
        by_cookie[r["cookie"]].append(r)

    print("\n" + bar)
    print("WHAT THE COOKIE SEES (the identifier the visitor CAN clear)")
    print(bar)
    for ck, rs in by_cookie.items():
        sites = sorted(set(r["site"] for r in rs))
        print("  cookie %-14s -> %d request(s), site(s): %s"
              % (ck, len(rs), ",".join(sites)))
    print("  => every cookie is single-site and resets on clear: weak, siloed.")

    print("\n" + bar)
    print("WHAT X-I2P-DestB32 SEES (the identifier the visitor CANNOT clear)")
    print(bar)
    for dest, rs in by_dest.items():
        sites = sorted(set(r["site"] for r in rs))
        cookies = sorted(set(r["cookie"] for r in rs))
        print("  dest %s" % (dest or "-"))
        print("     %d request(s) across site(s): %s" % (len(rs), ",".join(sites)))
        print("     spanning %d distinct cookie value(s): %s"
              % (len(cookies), ",".join(cookies)))
        if len(sites) > 1:
            print("     >> CROSS-SITE LINK: sites %s are run by different operators,"
                  % " & ".join(sites))
            print("        yet both identify this visitor as the same destination.")
        if len(cookies) > 1:
            print("     >> SURVIVED COOKIE CLEAR: the visitor cleared cookies between")
            print("        visits (new cookie each time) but the dest stayed constant.")

    print("\n" + bar)
    print("RESULT")
    print(bar)
    print("  - Cookies: siloed per site, reset on clear -> not a tracking primitive.")
    print("  - X-I2P-DestB32: stable per visitor, identical across unrelated eepsites,")
    print("    survives cookie/cache clearing and private browsing. The eepsite app")
    print("    received it for free, and the visitor has no way to remove it.")
    print("  - Two colluding eepsites join their logs on this value to confirm the")
    print("    same person visited both. If the value is ever tied to a real identity")
    print("    (the user also hosts a service on the same shared dest, posts their")
    print("    b32, etc.), all of that browsing links to the identity.")
    print("  - Different visitors (distinct destinations) never collide: it is a")
    print("    precise per-user ID, not a coarse bucket.")
    print("\n  Mitigation (this PR set): I2PTunnelHTTPServer 'sendDestHeaders=false'")
    print("  omits the headers; complementary client-side per-eepsite destination")
    print("  isolation stops a hostile operator who leaves them on.")
    print(bar)


if __name__ == "__main__":
    main()
