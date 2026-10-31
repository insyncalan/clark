# Design note: #33 Local server skeleton and its security (guarded)

Written by a teammate, 28-10-2026. Required before the build (`Team/01`). The source is creaite release tag **v2.6.9 (`db5adb2`)** only, read from a copy of the tag; nothing in creaite is edited. Review: **Full, two independent reviewers** (one reads the code, one tests from outside, `Team/07`), never the builder. The owner approves the exact copy.

## What creaite has (v2.6.9, `system/scripts/live_server.py`, 9,443 lines)
- **Binding:** `LocalServer(ThreadingHTTPServer)` binds to `("127.0.0.1", port)` and skips the reverse DNS lookup that stalls on some Macs.
- **Token:** `TOKEN = secrets.token_urlsafe(24)`, new at every start, put into the page's data only. `authorised()` needs the right Host and `X-Creaite-Token == TOKEN`, and a stale token gets a "reload" message.
- **Host check:** `host_ok()` allows only `127.0.0.1`, `localhost` or `::1`, on every GET and POST, including `/health`.
- **No cross-origin calls:** `do_OPTIONS` refuses every preflight.
- **Security headers on every response, through `end_headers`:** `frame-ancestors 'none'`, `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy: no-referrer`, and `Cache-Control: no-store` on `send`.
- **Script policy:** a hash-based CSP (`csp_hashes` / `csp_policy`), built from the exact page being sent. It is **report-only** in creaite, with `/csp-report` rate-limited.
- **Body limit:** `body()` refuses a larger Content-Length (`BODY_LIMIT`, per-route `ROUTE_BODY_LIMITS`) with a 400.
- **`/health`** returns only `{"ok": true}`.

## What is copied
`LocalServer` (the bind with no DNS lookup), `host_name`, `host_ok`, `authorised`, `do_OPTIONS`, `SECURITY_HEADERS` with `end_headers`, `send`, `body` with its limit, `csp_sha` / `csp_hashes` / `csp_policy`, `/health`, and the start-up port handling (a clear message when the port is taken). From the routes, only `GET /`, `GET /api/data` and `/csp-report` for now. Later items add theirs: `/api/change`, `/api/undo`, `/api/import`, `/api/publish`.

## What is cut
Everything else: ask creaite's runs, the sweep, the VIP check, calendars, transcripts, intake, updates, permissions, the service worker and installable app, the change stream, search, the vault, and all the `paths` and settings coupling.

## Changed from creaite (outline)
| creaite | clark | Why |
|---|---|---|
| `!= TOKEN` | `hmac.compare_digest(sent, TOKEN)` | compares in constant time; costs nothing |
| header `X-Creaite-Token` | `X-Clark-Token` | the name |
| CSP **report-only** | **enforced** from day one, with the same hash method, plus report-only reporting as a second header for diagnosis | clark starts clean, with no legacy inline code to clear. If the build ever needs an inline exception, it is a reviewed change |
| `BODY_LIMIT` 40 MB | 2 MB by default; imports raise it per route (`ROUTE_BODY_LIMITS`) | clark has no 25 MB attachment uploads |
| port from creaite's settings | port from clark's settings, default 8766 | so clark and creaite can run side by side |
| page served by `build_dashboard.render` | page served from the bundled page plus `/api/data` | clark's page is built by #35 |

A POST must also send `Content-Type: application/json`; anything else gets a 415. With the token header and no preflight allowed, that leaves no way for a simple cross-site form post to reach the API.

## Tests that pin it
1. **Binding:** the listening socket's address is 127.0.0.1. A connection to the machine's LAN address is refused.
2. **Host:** `Host: evil.example`, `Host: 127.0.0.1.evil.example` and a missing Host each get 403 on `/`, `/health` and `/api/data`. `localhost`, `127.0.0.1` and `[::1]` with a port all pass.
3. **Token:** no token, a wrong token, and the token from an earlier start each get 403 on every `/api/` route. The right token passes. A test checks the comparison is `compare_digest`.
4. **Preflight:** any OPTIONS gets 403.
5. **Headers:** every response, including errors and 404s, carries the four security headers and `no-store`. HTML replies carry an enforced CSP whose script hashes match the page's inline blocks.
6. **CSP in a real browser:** a headless browser loads `/`, and an injected inline script without its hash is blocked and reported.
7. **Body limit and type:** a body over the limit gets 400, and a POST with `text/plain` gets 415.
8. **`/health`** returns exactly `{"ok": true}`, with no path, version or port.
9. **The copy is recorded:** the reuse record lists `live_server.py` at v2.6.9 `db5adb2` with the functions copied. A test checks that the row exists.

These are re-made from creaite's own tests at the same tag (`dev/tests/test_live_server.py`, `test_live_server_bind.py`), with clark's names.

## Review focus
Every route goes through `authorised()`, including any added later. A test lists the routes and fails on one that doesn't. Also review the Host parsing edge cases, the CSP hash of the exact bytes sent, and that the server never binds to `0.0.0.0` whatever the setting says.
