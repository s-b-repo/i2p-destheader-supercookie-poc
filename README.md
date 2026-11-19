# PoC: `X-I2P-DestB32` is a visitor supercookie (i2p.i2p HTTP server tunnel)

A minimal, dependency-free demonstration that every I2P eepsite is handed a
**stable, uncloaked, per-visitor identifier** it never asked for and that the
visitor cannot remove — enabling persistent tracking and cross-eepsite
collusion. Python 3 standard library only.

```
bash run_poc.sh
```

## The bug

`apps/i2ptunnel/.../I2PTunnelHTTPServer.java` adds, **unconditionally**, to
every request it forwards to the local eepsite application:

```java
addEntry(headers, HASH_HEADER,   peerHash.toBase64());   // X-I2P-DestHash
addEntry(headers, DEST32_HEADER, peerB32);               // X-I2P-DestB32
addEntry(headers, DEST64_HEADER, ...toBase64());         // X-I2P-DestB64
```

- The value is the **visitor's own destination**, taken from the I2P transport
  layer. The browser cannot forge it (the server strips client-supplied copies,
  `CLIENT_SKIPHEADERS`) and cannot remove it.
- The default HTTP proxy client uses `sharedClient=true`, so the **same**
  destination is presented to **every** eepsite.
- Unlike the IRC server tunnel — which **cloaks** the destination hash by
  default with a per-tunnel random key, explicitly to stop cross-server
  tracking — the HTTP server offers no cloaking and no opt-out.

So `X-I2P-DestB32` behaves as a supercookie: stable across sessions, identical
across unrelated eepsites, and unaffected by clearing cookies, cache, or using
private-browsing.

## What the run shows

Two independent eepsites (A, B — different operators), two visitors (Alice,
Bob). Alice visits A, **clears her cookies**, visits A again, then visits B.
Bob visits A.

```
WHAT THE COOKIE SEES (visitor CAN clear it)
  every cookie is single-site and resets on clear: weak, siloed.

WHAT X-I2P-DestB32 SEES (visitor CANNOT clear it)
  dest cac8...b32.i2p
     3 requests across sites: A,B
     spanning 3 distinct cookie values
     >> CROSS-SITE LINK: A & B are different operators, same destination
     >> SURVIVED COOKIE CLEAR: new cookie each time, dest unchanged
  dest 0ddc...b32.i2p   (Bob) — distinct, never collides with Alice
```

- **Survives cookie clearing:** Alice gets a new cookie on every request, yet
  the destination is constant → tracking is unaffected by the one control a
  user actually has.
- **Cross-site collusion:** A and B, run by different operators, both log the
  identical destination for Alice → joining their logs confirms the same person
  visited both.
- **Precise, not coarse:** Bob's distinct destination never collides with
  Alice's → it is a per-user identifier, not a broad bucket.

Escalation to de-anonymization (not staged here): if that destination is ever
seen next to a real-world identity — the user also *hosts* a service on the
same shared destination, pastes their b32, logs in somewhere that knows it —
all of the linked browsing attaches to that identity.

## Components (each maps to the real system)

| File | Models |
|---|---|
| `server_tunnel_shim.py` | `I2PTunnelHTTPServer`: strips client `X-I2P-Dest*`, injects the real ones from the transport identity |
| `eepsite_backend.py` | the eepsite's web app; just reads the headers the tunnel gives it, and sets an ordinary cookie for contrast |
| `visitor.py` | a browser behind the HTTP proxy with one fixed shared-client destination, plus a cookie jar |
| `correlate.py` | the adversary joining two eepsites' logs |

### Fidelity note

There is no real I2P router here, so the transport-layer peer destination is
supplied to the shim via an `X-PoC-Peer-Dest` request header (set by
`visitor.py`) standing in for `socket.getPeerDestination()`. In a real
deployment the browser has no way to set `X-PoC-Peer-Dest` or the
`X-I2P-Dest*` headers — the server derives and injects them from the tunnel.
The shim strips `X-PoC-Peer-Dest` before forwarding, so the backend only ever
sees the injected `X-I2P-Dest*`, exactly as in production.

## Mitigation

- **Server-side (shipped PR):** `I2PTunnelHTTPServer` option `sendDestHeaders=false`
  omits all three headers for operators who don't need them (data minimization).
  See i2p.i2p PR for `cybersec/httpserver-dest-headers-optout`.
- **Client-side (follow-up):** per-eepsite destination isolation on the HTTP
  proxy client so each eepsite sees a *different* destination — this is what
  protects a visitor even against a hostile operator who leaves the headers on.

## Limitations

- Localhost HTTP, no live I2P transport; the destination injection and header
  stripping are reproduced faithfully from the server code, which is where the
  behavior lives. A real router changes only how the destination is derived, not
  that it is injected.
- This is linkability / pseudonymous tracking caused by the server, in the same
  class as PR #314; it is not by itself a full IP de-anonymization.
