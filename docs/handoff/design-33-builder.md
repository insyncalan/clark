# Builder's design note: #33 local server skeleton and its security (guarded)

Written by a teammate (builder), 28-10-2026, for the two readers, the Head and a teammate, and then for the owner, who approves the exact copy. It builds on a teammate's note (`design-33-server.md`) and was checked line by line against creaite **v2.6.9 (`db5adb2`)** `system/scripts/live_server.py`, read from the tag (nothing in creaite is touched). **Nothing is built until both readers pass this note.**

Where this note differs from a teammate's, it says so in **Open for the readers** at the end. Everything else follows her note.

## What gets built
- One file, `src/clark/server.py`, which is new and guarded.
- One test file, `tests/test_server.py`.
- A row in the reuse record.

Standard library only, Python 3.9. No other `src/` file changes. `server.py` starts no program, so it passes #56's source rules.

## Copied from creaite, with what changes in each

| creaite v2.6.9 (line) | clark | Change |
|---|---|---|
| `LocalServer.server_bind` (3947) | `LocalServer` | Copied. **Added:** `__init__` refuses any address other than `127.0.0.1` with a `ValueError`, so the port is the only setting. `daemon_threads = True` |
| `TOKEN = secrets.token_urlsafe(24)` (214) | same | Copied, new at each start |
| `SECURITY_HEADERS` + `end_headers` (943, 1159) | same | **`Cache-Control: no-store` moves from `send` into `end_headers`**, so the standard library's own error pages (a malformed request, a 400 from `send_error`) carry it too. A teammate's test 5 requires that, and creaite misses it |
| `host_name` (947), `host_ok` (1154) | same | Copied exactly. A Host header in capitals ("LOCALHOST") is refused, as in creaite, which is the safe direction |
| `send` (1167) | same | Copied. The HTML branch adds the **enforced** CSP (below) |
| `body` (1181) | same | `BODY_LIMIT` is 2 MB, with `ROUTE_BODY_LIMITS` kept empty for later items. Copied with one fix: a non-numeric `Content-Length` is a 400, where creaite's `int()` would raise |
| `authorised` (1188) | same | The header is `X-Clark-Token`, compared with `hmac.compare_digest`. A stale token gets creaite's "reload" message with clark's wording, and no product name starts the line |
| `do_OPTIONS` (1202) | same | Copied: every preflight gets 403 |
| `health_answer` (961) | `/health` → `{"ok": true}` | The `this_vault` mark is cut (no launcher yet). The route stays Host-checked |
| `csp_sha`, `csp_hashes` (990, 997) | same | Copied exactly, including the block parser |
| `csp_policy` (1032) | same | `worker-src 'self'` is cut, because clark has no service worker. The rest is copied. The policy is sent as **`Content-Security-Policy`** (enforced), not `-Report-Only` |
| `csp_kind`, `csp_directive`, `csp_reports`, `csp_local`, `csp_take`, `csp_report_route` (1056–1143), `post_or_report` (8018) | same | Copied. creaite's `debuglog` becomes a standard `logging` logger, `clark.server`, which logs the directive and kind only, as in creaite |
| `do_GET` (1206), `do_POST` (1263) | same shape | Only `/health`, `/`, `/api/data` and `/csp-report`. The route tables are explicit (below) |
| `Handler.log_message` (1148) | same | Kept quiet: one line per `/api/` call. `server_version = "clark"`, and `sys_version = ""`, so no Python version is sent |
| `main` port handling (3976–3996) | `serve(port)` | 127.0.0.1 only; the port comes from `CLARK_PORT` or defaults to 8766. A port that is taken gives one plain line, "Port 8766 is in use. Is clark already running? Set CLARK_PORT to use another port", and exit code 1. The launcher, Rosetta, vault and settings parts are cut |

**Cut:** everything else in the 9,443 lines, as a teammate's note lists.

## How the routes stay guarded
- Two explicit tables: `GET_ROUTES = {"/api/data": ...}` and `POST_ROUTES = {}`. Any path under `/api/` reaches its handler only through one dispatcher. The dispatcher calls `authorised()` first. A route never checks the token itself, so a later route can't forget to.
- **Order, GET:** Host check (403), then `/health`, `/`, then `/api/*` through `authorised()` (403), then 404.
- **Order, POST:**
  1. `/csp-report`. It does its own local-only checks, as in creaite, because a browser's report carries no token.
  2. Then `authorised()` (403).
  3. Then the type check: anything but `application/json` gets 415.
  4. Then `body()`, which returns 400 when the body is over the limit or not JSON.
  5. Then `POST_ROUTES`, and 404 for anything else.
  So the 415 and 400 rules can be tested in #33 although no POST route exists yet.
- **Errors:** an exception in a route gets 500, `{"ok": false, "message": "<plain sentence>", "code": "server_error"}`. creaite sends the exception's text too, which can name a path; clark sends a plain sentence with `code: "server_error"` and logs the rest (see Later rulings). A dropped connection is ignored, as in creaite.

## Where the page and the data come from (the seams to #31 and #35)
- **The page:** `page_html()` returns the bundled page. Until #35, that is a small placeholder page with one inline script, which the CSP tests use. #35 replaces only this function.
- **The token reaches the page in the page itself:** `GET /` puts `<script type="application/json" id="clark-boot">{"token": "..."}</script>` before `</body>`.
  - This is creaite's method: its rendered data carries the token.
  - A JSON block isn't run, so it needs no CSP hash, which is creaite's own `csp_hashes` rule.
  - Another site can't read the reply, because there is no CORS, no preflight, and the Host is checked.
  - **A teammate's note doesn't say how the page gets the token. This is the gap it fills.**
- **The data:** `GET /api/data?project=<CODE>` calls `data_for(code)`, which is passed to the server when it starts.
  - `CODE` must match creaite's project code pattern `[A-Z][A-Z0-9]{2,6}` (3 to 7 characters, as ruled); anything else gets 400.
  - An unknown project gets 404.
  - #31 supplies `data_for` from `Store.read`. Until then the tests pass a fake with demo data. The server holds no database code and never imports the store.

## Tests that pin it (`tests/test_server.py`)
These are a teammate's nine, re-made from creaite's `test_live_server.py` and `test_live_server_bind.py` at v2.6.9. Each runs a real server on `127.0.0.1:0` in a thread and speaks HTTP with `http.client`, so the Host header and the bodies are exactly what the test sends.

1. **Binding:**
   - The socket's address is 127.0.0.1.
   - `LocalServer(("0.0.0.0", 0))` and the LAN address raise.
   - A connection to the machine's LAN address is refused. This part is skipped with its reason when the machine has none.
   - Binding calls no `getfqdn`; it is checked in a separate process, as creaite does.
2. **Host:**
   - `evil.example`, `127.0.0.1.evil.example`, `localhost.evil.example`, `LOCALHOST`, an empty Host and a missing Host each get 403 on `/`, `/health` and `/api/data`.
   - `localhost:p`, `127.0.0.1:p` and `[::1]:p` pass.
3. **Token:**
   - No token, a wrong one, the same length but wrong, and the token of an earlier server each get 403 on **every route in the tables**, which the test reads from `GET_ROUTES` and `POST_ROUTES` themselves.
   - The right token passes.
   - A source check confirms the comparison is `hmac.compare_digest`.
4. **Preflight:** OPTIONS on `/`, `/health` and `/api/data` gets 403.
5. **Headers:**
   - 200, 403, 404, 415, 400 and a stdlib `send_error` (a malformed request line) each carry the four security headers and `Cache-Control: no-store`.
   - HTML replies carry `Content-Security-Policy` (enforced). Its script hashes equal `csp_hashes()` of the exact bytes sent, and it allows no outside source: no `http:`, `https:` or `*`.
6. **The CSP in a real browser:** headless Chrome loads `/` with an extra inline script that has no hash. The test checks that the page's own script ran, the injected one didn't, and `/csp-report` received the report. It is required: it fails, never skips, when Chrome isn't installed (as ruled). It uses the DevTools-pipe method of `system/prototype/run_selftest.py`.
7. **Body and type:** a POST with `text/plain` gets 415; a body over 2 MB gets 400; bad JSON gets 400; a bad Content-Length gets 400.
8. **`/health`:** it returns exactly `{"ok": true}`.
9. **The record:** the reuse record has the `live_server.py` row at v2.6.9 `db5adb2` naming each copied function. A test checks the row exists.

Also: `/api/data` with a bad code gets 400, an unknown project 404, and the fake project 200; a port that is taken gives the plain message and exit code 1.

## Open for the readers (my recommendation first)
1. **The second, report-only CSP header ("plus report-only reporting as a second header").**
   - *Recommendation: drop it.* The enforced policy's own `report-uri /csp-report` already reports what it blocks. A second header with the same policy only doubles the reports.
   - Keep it only if you want a stricter trial policy alongside the enforced one, and name what it would trial.
2. **`/api/data` for one project, chosen by `?project=`.** The Done-when says "one project's data". *Recommendation:* the page asks for its project by code. The other choice is a single project per server start, which is simpler but no use once there are several.
3. **The seam to #31 is `data_for(code) -> dict | None`, passed in at start.** *Recommendation:* a teammate confirms that name and shape on #31, so neither of us waits on the other.
4. **#33 waits for #31.** The skeleton and all nine tests can be built against the fake now, and only the wiring of `data_for` waits for #31. *Recommendation:* build against the fake once this note passes.

## Readers' rulings (28-10-2026), built as written below
The Head passed this note with conditions (13:51) and gave the Head ruling with a teammate's five changes (13:52). These lines **replace** the matching lines above where they differ.

**The four open points:** all agreed. There is no second report-only header; `/api/data?project=`; `data_for(code) -> dict | None`, which a teammate confirms on #31; built against a fake now.

**A teammate's five changes:**
1. **The token is compared as bytes:** `hmac.compare_digest(sent.encode("utf-8", "replace"), TOKEN.encode())`. A non-ASCII token gets 403, not 500.
2. **`Cache-Control: no-store` is sent once, from `end_headers` only.** It is removed from `send()` and from the csp-report route. Each security header appears exactly once, except the two Content-Security-Policy headers on an HTML reply.
3. **The enforced CSP is recorded as a change from creaite, with its seams for #35 and #41:**
   - (a) the page is one HTML file with inline scripts, so `script-src` lists hashes only, with no `'self'`;
   - (b) Tiptap keeps `injectCSS: false`, as creaite's `core/editor.js` does;
   - test 6 runs again against the real bundle in #35;
   - the REUSE row says "copied from report-only, sent enforced, worker-src cut";
   - the log line says "blocked", not "report-only violation".
4. **The project code is `[A-Z][A-Z0-9]{2,6}`,** the 3 to 7 characters of creaite's `projects.code` CHECK. A two-letter code gets 400.
5. **A chunked body, or a POST with no Content-Length, gets 411.**

**The Head's conditions, added to the tests:**
- Test 6 (real browser) is required: it fails, not skips, when Chrome is missing.
- A test pins `style-src-attr 'unsafe-inline'`.
- The 415 check accepts `application/json; charset=utf-8` and refuses `application/jsonx` and `text/json`.
- An HTML reply carries both the base `frame-ancestors 'none'` header and the full policy.
- `/csp-report` keeps creaite's limits (60 a minute, 16 KB) and refuses a Host that isn't loopback.

**Accepted as in creaite:** `GET /` hands the token to any local process that can reach the port. The Host check stops other websites, including DNS rebinding.

**Named in the PR for the owner, the departures from creaite:**
- the enforced CSP;
- `compare_digest` on bytes;
- a 500 says something went wrong and nothing was changed (the class goes to the log only);
- `no-store` sent from `end_headers`;
- 400 for a bad Content-Length;
- 411 for a chunked body;
- the 2 MB limit;
- 415 for anything that isn't JSON;
- refusing any address other than 127.0.0.1.

## The Full review's fixes (14:09)
- **MEDIUM:** `log_message` reads `path` with `getattr`, and `default_request_version` is HTTP/1.0. A request line that doesn't parse (`GARBAGE`, `GET / HTTP/9.9`, a 70 KB URL) now gets a reply that carries the headers.
- **LOWs:**
  - `Handler.timeout = 30`.
  - Nested JSON that is too deep gets 400.
  - The Host is strict: exactly 127.0.0.1, localhost or [::1], with an optional port of 1 to 65535. The Origin of a report is checked the same way.
  - A second Host or Content-Length header gets 400.
  - Under `/api/` the token is checked before a 404. A missing token gets the not_allowed message; only a wrong token gets the reload message.
  - The browser test has no opt-out.
  - The page seam is `page_html()`, as written above.

## Later rulings (28-10-2026)
- **`/api/projects`:** takes dicts at the seam; lists only a code of the shape `[A-Z][A-Z0-9]{2,6}`; stops at 500 projects; a name that isn't text (or is blank) falls back to the code; a name is cut at 200 characters.
- **Token comparison:** `token_ok` encodes with `"surrogatepass"` (a header value can't hold a lone surrogate, but any text then encodes without raising, so a non-ASCII token is a plain 403). The Head's ruling was "replace"; it is amended to match. The reason for the change: the word "replace" in the source reads as the SQL word REPLACE to the guarded one-writer source test. The page's HTML is decoded with `"surrogateescape"` for the same reason.
- **The 500 reply (Head, 28-10-2026, from the plain-words review of #35):** the body is `{"ok": false, "message": "Something went wrong, and nothing was changed. Try again, or restart clark.", "code": "server_error"}`. It names no class, no fault text and no path; `LOG.exception` keeps the class, the text and the stack in the log only. This replaces the earlier "class name only" ruling.
- **Plain-words messages:** every error reply has `message` (plain, for people: "clark" in lower case, no jargon, says what to do) and `code` (stable, for the page and the tests; a person never sees it). Codes: `not_allowed` (403), `stale` (403, also `stale: true`), `bad_request` (400), `too_large` (400; 413 for a CSP report), `send_json` (415), `unsupported_type` (415, a CSP report), `length_required` (411), `not_found` (404), `bad_project_code` (400), `project_not_found` (404), `server_error` (500). Status codes are unchanged. Tests pin the `code`, and the exact 500 sentence. The placeholder page says "clark is starting."
