"""clark's local server: the page and its data, for this machine only (#33; guarded; BRD NFR-2).

Copied from creaite v2.6.9 (db5adb2) system/scripts/live_server.py, only what clark needs today, with the changes
function. Later items add their routes to GET_ROUTES and POST_ROUTES, where the one dispatcher checks the token first.

Routes:
- GET  /health           {"ok": true, "version": "x.y.z"} only (and "this_data", with "folder" (row 975), when asked with X-Clark-Data, #71); the Host is checked as everywhere
- GET  /                 the page, with this run's token in a JSON data block (id="clark-boot"), never run as a script
- GET  /api/projects     the projects the page can ask for: [{"code", "name", "open"?}], from the store (`projects`, #31); `open` is the count of open work items (#439)
- GET  /api/data         ?project=<CODE>: one project's data, from the store (`data_for`, #31)
- GET  /api/movement     ?project=<CODE>: Milestones Movement (#136), owner only, never published: the view of the store's `milestone_moves` read (movement_read.py); without the seam, not found
- GET  /api/activity     ?project=<CODE>&item=<ID>: one item's changes for the peek's Activity tab (#42), owner only, never published (activity_read.py); without the seam, not found
- GET  /api/milestones   ?project=<CODE>: that project's milestones for the Calendar and its list (#146), read only: the `milestones` seam (milestone_feed.py); without the seam, not found
- POST /api/section-body  a section's content (#273): a change of /api/change, report_sections update of `body` only, the logic is `section_body(req)`, from clark.changes (which refuses any other request); its own body limit
- POST /api/change       one change to a project's report sections (#65); the logic is `change(req)`, from clark.changes
- POST /api/undo         reverse one earlier step of the report's (#65); the logic is `undo(req)`
- POST /api/section-image  one picture into a section template's slot, or out of it (#96 R1): one step, one Undo; the logic is
                         `section_image(req)`, from clark.changes (the picture's checks are there); its own body limit
- POST /api/sneak/read  words about one work item as from → to changes (#42); read only, plain code (clark.sneak)
- POST /api/here         "still here" from an open page (#71); stops a launcher-started server when no page is left
- POST /api/quit         Quit (item 836): answers, then stops this server (the Settings card "Quit clark"); nothing is read from the body
- POST /api/publish      Publish (#43): Local, and the client folder only when the body says `to_client: true`; publish_flow.py
- POST /api/client-folder  choose or clear the project's client folder (#43); never writes into it
- GET  /api/publication  ?project=<CODE>: when the project was last published and whether to the client (#43)
- POST /api/preview      Preview (#147): builds the page as publish would, in memory; answers a one-visit address (publish_flow.py)
- GET  /preview          ?id=<from /api/preview>: that page, once, local only (a new tab cannot send the token header)
- GET  /api/export       ?project=<CODE>: the project's workbook as a download named <CODE>-<date>.xlsx (publish_flow.py);
                         ?template=1: the empty import template, "clark import template.xlsx" (#454)
- GET  /api/publications ?project=<CODE>[&archived=1]: the newest 10 publications with number, time, where and who (#443; past_reports.py); no path, no hash; archived=1 (#345) lists the archived ones too, marked
- POST /api/publications/archive  {project, number}: hide one publication from that list, never delete it (#345; changes.make_publication_mark); /api/publications/restore puts it back. No Undo
- GET  /api/past-report  ?project=<CODE>&number=<N>: checks that publication's kept copy and answers a one-visit address (#443)
- GET  /past             ?id=<from /api/past-report>: that kept page as it was published, with the read-only banner added (#343), once, local only (#443)
- GET  /api/as-at        ?project=<CODE>&date=<YYYY-MM-DD>: the project's data as at the end of that day, rebuilt from the change
                         history in a copy, read only, never published (#349; as_at.py); without the seam, not found
- GET  /api/backups      the backups newest first, a status line, the daily-copy warning (#111; safety.py)
- POST /api/backups/preview  {name}: counts in a backup and now, from a temporary copy
- POST /api/backups/restore  {name, last_step}: put a backup back (one writer at a time, never waiting)
- POST /api/backups/copy-folder  {folder}: choose the optional folder each backup is also copied into, OneDrive allowed, or "" for none (#622; safety.py)
- GET  /api/providers    Settings › AI (#54): whether Claude is connected, the model and the models offered (ai_connect.py)
- POST /api/providers/connect {provider}: clark may use it; POST /api/providers/disconnect {provider}: clark stops using it, and the sign-in stays
- POST /api/providers/model {model, accept?}: the model asking uses, from a fixed list
- POST /api/page-error   the page reports a fault: one short line in the log at most, rate-limited (#110; log_routes.py)
- GET  /api/diagnostics  the logging level, the last 7 days' errors and the Copy diagnostics text (#110)
- POST /api/logging      set Normal or Debug (#110); POST /api/logging/open-folder shows the log folder
- POST /api/draft-email  Draft email (#50): the ticks and the email text from the builder; read only, never sends (draft_email_feed.make)
- POST /api/draft-email/sent  "I sent it" (#50): records the ids, the mode and the day, and one History sentence (the recipient's name and the subject, composed here; never the address or the body) (draft_email_feed.make_sent)
- POST /api/ask/change/dry    {project, reply}: the dry run of the changes an answer suggested, held on the server (#47e; ask_service.py)
- POST /api/ask/open-source   {project, file, page|null}: open a saved folder's PDF at a page in the system's viewer (#943; ask_service.py, platform.py)
- POST /api/ask/change/apply  {project, offer, confirm?}: one offer saved as one undoable step (#47e; ask_apply.py, changes.make_ask_change)
- GET  /assets/<name>    the brand's picture (#98): only cover.png, cover.jpg, cover.jpeg and cover.webp, from the local brand folder; no
                         token (an <img> can't send one), but the Host, Origin and Sec-Fetch-Site are checked; 404 when there is none
- GET  /api/profile      the name, email and Alias typed in Settings › Personal (#180, #613), from the data folder's settings.json; without the seam, not found
- POST /api/profile      save them: {name, email, alias}, all text, alias optional (left out, the saved one is kept); a refusal is in plain words and writes nothing (profile_settings.py)
- GET  /api/people       the people list, archived too (#115; changes.make_people_list); without the seam, not found
- POST /api/people       one person writer: {op: add | edit | rename | merge | archive | restore | paste, ...}, one undoable step (#115; changes.make_people)
- POST /api/people/undo  {apply_id}: reverse one people step (#115; changes.make_people_undo)
- POST /api/excel-import a workbook to read back in, and the choice of what to take from it (#444; excel_route.py)
- GET  /api/demo        whether the made-up demo projects are on show: {ok, demo} (#731)
- POST /api/demo/clear removes the untouched demo projects, after a safety copy (#731; demo_seed.py)
- POST /api/project     a new project, or a project's name, client and added workstreams (#444; project_route.py)
- POST /api/word-import  a Word file to read into new items, and the choice to add them (#48); the logic is `word_import(req)`
- POST /api/word-export  the report as a Word file, saved in the report folder, and in the client folder with To client (#48)
- GET  /api/update       Settings › Version and updates: what is installed, an update in Downloads, the last update (updater.py)
- POST /api/update/review     {from, reinstall}: check the newest file in Downloads, or one chosen in the system's dialog, and review it
- POST /api/update/install    {review_id}: install the reviewed update; the server stops after the answer so the helper can swap
- POST /api/update/arm-undo   {}: arm Undo update for a few seconds; says whether only the app and settings can be put back
- POST /api/update/undo       {arm_id, app_only}: the armed undo; the server stops after the answer, as for an install
- POST /api/section-file  {project, section}: the Open dialog, then the file copied into the client folder's "Report files" folder and
                         added to the section in one step (#96; publish_flow.py and section_files.py). The request never names a file
- POST /csp-report       the browser's reports of what the script policy blocked: local only, rate-limited, small

Run: python3 -m clark.server   (CLARK_PORT sets the port; the default is 8766, beside creaite's 8765)
Standard library only, Python 3.9.
"""
import base64
import errno
import hashlib
import hmac
import importlib
import inspect
import json
import logging
import os
import re
import secrets
import socketserver
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlsplit

LOG = logging.getLogger("clark.server")
HOST = "127.0.0.1"                    # the address clark listens on, whatever any setting says (in the container: CONTAINER_BIND, below)
DEFAULT_PORT = 8766
CONTAINER_BIND = "0.0.0.0"            # item 427: only inside the shipped container (see container_mode); the Mac publishes the port to 127.0.0.1 only


def container_mode():
    """item 427: True only when CLARK_CONTAINER=1 is set (by docker/compose.yaml, which runs a stock Python image) AND this really is a
    container (Docker makes /.dockerenv in every container, Podman /run/.containerenv). Never by the setting alone; never on a Mac."""
    return os.environ.get("CLARK_CONTAINER") == "1" and (os.path.exists("/.dockerenv") or os.path.exists("/run/.containerenv"))


def container_gateway():
    """item 427: the container's default gateway address, the one peer a published port arrives from; None when it can't be read.
    Why this address and no other: a published port is forwarded by Docker's proxy (docker-proxy on Linux; Docker Desktop's
    forwarder in its VM on Mac and Windows), which opens a new connection to the container from the host side of the
    container's network. That side's address is the network's gateway (172.17.0.1 on the default bridge, the compose network's
    own, such as 172.18.0.1, here), and it is the gateway of the container's default route, read from the kernel's table rather
    than assumed. Other containers on that network have other addresses in the subnet and are refused, and the LAN cannot
    reach the port at all (compose publishes it on 127.0.0.1 only). Only a true default route counts: destination and mask
    both 0.0.0.0, with the gateway flag. The table prints each address as a number in this machine's byte order."""
    try:
        with open("/proc/net/route", encoding="utf-8") as table:
            for line in table.read().splitlines()[1:]:
                f = line.split()
                if f[1] == "00000000" and f[7] == "00000000" and int(f[3], 16) & 2:
                    return ".".join(str(b) for b in int(f[2], 16).to_bytes(4, sys.byteorder))
    except (OSError, ValueError, IndexError):
        pass
    return None


def local_peer(address):
    """Whether a request's peer address is this machine, or, in a container only, the container's gateway (item 427)."""
    if address in ("127.0.0.1", "::1", "::ffff:127.0.0.1"):
        return True
    gateway = container_mode() and container_gateway()
    return bool(gateway) and address == gateway


# item 427 (a reader's finding): a peer refused in container mode is told why in a plain page, and the container's log names it, so
# a second run in Docker shows which address Docker Desktop really connects from. Addresses only: never a token or a header.
CONTAINER_REFUSED = "This connection was refused. clark is running in Docker and only answers this computer."
CONTAINER_REFUSED_PAGE = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>clark</title></head><body><p>{CONTAINER_REFUSED}</p></body></html>
"""
_REFUSED_PEERS = set()          # each refused address is logged once; at most REFUSED_PEERS_KEPT of them, then no more lines
REFUSED_PEERS_KEPT = 256
_REFUSED_LOCK = threading.Lock()


def note_refused_peer(address):
    """item 427: one line to the container's log (stderr) the first time `address` is refused, naming it and the gateway that is
    accepted. Never more than once for an address, and never more than REFUSED_PEERS_KEPT lines in all, so no peer can fill the log."""
    with _REFUSED_LOCK:
        if address in _REFUSED_PEERS or len(_REFUSED_PEERS) >= REFUSED_PEERS_KEPT:
            return
        _REFUSED_PEERS.add(address)
    gateway = container_gateway()
    print(f"Refused a connection from {address}: in Docker only 127.0.0.1 and the container's gateway "
          f"({gateway or 'not found'}) are accepted.", file=sys.stderr, flush=True)
TOKEN = secrets.token_urlsafe(24)     # new at every start; the page gets it in GET /
TOKEN_HEADER = "X-Clark-Token"
STALE_PAGE = "This page is out of date because clark was restarted. Reload the page and try again."
# What a person reads in an error reply (`message`), by the stable `code` the page and the tests use. A person never sees
# the code. A fault's class and text go to the log only, never into a reply.
RELOAD = "Reload the page and try again."
MESSAGES = {
    "not_allowed": f"That was not accepted. {RELOAD}",
    "stale": STALE_PAGE,
    "bad_request": f"That could not be read. {RELOAD}",
    "send_json": f"That could not be read. {RELOAD}",
    "length_required": f"That could not be read. {RELOAD}",
    "too_large": "That is too big for clark to take. Try again with less in it.",
    "change_too_large": "That is too big to save. Make the text shorter, or take some of the list out, then try again.",
    "unsupported_type": f"That could not be read. {RELOAD}",
    "not_found": f"That could not be found. {RELOAD}",
    "not_supported": "That is not something clark can do. Go back to the page you were on.",
    "picture_not_found": "Your brand's picture could not be found. Put it in the assets folder next to your brand's tokens.css, "
                         "named cover.jpg, cover.png or cover.webp, then reload the page.",
    "bad_project_code": "Use a project code of 3 to 7 capital letters or digits.",
    "project_not_found": "There is no project with that code. Check the code in the address, or choose a project from the list.",     # = changes.NO_PROJECT (a test keeps the two equal)
    "bad_archived": "That way of showing archived records isn't available. Reload the page and try again.",
    "server_error": "Something went wrong, and nothing was changed. Try again, or restart clark.",
    "no_backups": "Backups can't be shown right now. Restart clark the usual way and try again.",
    "saving_off": "Saving is switched off, so that change was not kept. Restart clark the usual way to turn it on.",
    "updating": "An update is being installed, so nothing was changed. Wait a minute, then reload the page.",
    "no_updates": "Updates can't be shown right now. Restart clark the usual way and try again.",
    "no_brands": "Brands can't be shown right now. Restart clark the usual way and try again.",
    "item_not_found": f"That item could not be found. {RELOAD}",
    "reading_off": "Changing items with words is not available right now, and nothing was changed. Restart clark the usual way to turn it on.",
}
# The standard library's error status → the code of the plain reply (Handler.send_error). Any other 400 to 499 is
# bad_request and any 500 or more server_error.
ERROR_PAGES = {501: "not_supported", 505: "bad_request", 414: "too_large", 431: "too_large"}
BODY_LIMIT = 2 * 1024 * 1024          # any request; a route that needs more (an import) adds itself below
EXCEL_FILE_MB = 25                     # the largest workbook clark reads (excel.MAX_FILE_BYTES); sent as text, a third bigger, plus the words around it (#444)
WORD_FILE_MB = 25                      # the largest Word file clark reads (docx_read.MAX_FILE_BYTES); sent as text, a third bigger, plus the words around it
# #247: no tracker-only limit is needed. Every change, tracker or not, is read up to this one limit, which is above the widest
# tracker the checker accepts (95 KB in the worst letters), so the checker's own words are what a person sees; a request over it
# gets the general words. No request kind is given a larger door. tests/test_tracker_route.py pins this over the real route.
SECTION_BODY_MAX = 256 * 1024          # #405: the largest section content the change route carries: the stored limit of "Needs from you" and the tracker (a template's body is 64 KB at most); a test keeps it equal to the checker's largest
ESCAPE_FACTOR = 2                      # the body is a string inside the request, so each quote and backslash is escaped once more: at worst twice the bytes. A client that writes non-ASCII as \\u escapes can take three times a plain letter's bytes; the page sends plain UTF-8, and "Needs from you" and the tracker are measured over the route in tests
REQUEST_ENVELOPE = 4 * 1024            # the request around the body: its kind, op, id and the rest of its changes


def change_body_limit(body_max=SECTION_BODY_MAX):
    return ESCAPE_FACTOR * body_max + REQUEST_ENVELOPE


SECTION_BODY_LIMIT = change_body_limit()   # #96, #378, #405, #273: 516 KB today; /api/section-body, the one route that carries a section's content; moves with the three above, never with a bare number
CHANGE_BODY_LIMIT = 16 * 1024          # #273: every other change (a section's content has its own route)
# #454: the People card's paste, worked out the way the change limit is, never a bare number. This server imports nothing from clark, so the
# four caps are copied here and tests/test_server.py keeps them equal to people.py (ROW_LIMIT, NAME_MAX, EMAIL_MAX, CELL_MAX). The bound is
# the worst the page can send: every character of every cell a six-byte JSON escape (\u00XX, which JSON.stringify gives a control character;
# a lone surrogate half is the same six bytes, and the page counts a letter outside the basic plane as two halves, so six bytes a counted
# character holds for it too). Plain text is one to three bytes a character, so nothing a person types comes near it.
PEOPLE_ROW_MAX = 500                   # people.ROW_LIMIT: rows in one paste
PEOPLE_NAME_MAX, PEOPLE_EMAIL_MAX = 120, 254
PEOPLE_CELL_MAX = 100                  # people.CELL_MAX: organisation, and role
JSON_ESCAPE_BYTES = 6                  # the most one character takes in a JSON string
PEOPLE_ROW_ENVELOPE = 64               # a row's braces, four keys, quotes, colons and comma: 51 bytes compact, 59 when spaced
PEOPLE_ROW_BYTES = (PEOPLE_NAME_MAX + PEOPLE_EMAIL_MAX + 2 * PEOPLE_CELL_MAX) * JSON_ESCAPE_BYTES + PEOPLE_ROW_ENVELOPE      # 574 * 6 + 64 = 3508
PEOPLE_BODY_LIMIT = PEOPLE_ROW_MAX * PEOPLE_ROW_BYTES + REQUEST_ENVELOPE      # 500 * 3508 + 4096 = 1,758,096 bytes (1.68 MiB), under BODY_LIMIT; an add or an edit is a few hundred bytes
ROUTE_BODY_LIMITS = {"/api/change": CHANGE_BODY_LIMIT, "/api/section-body": SECTION_BODY_LIMIT, "/api/undo": 8 * 1024, "/api/sneak/read": 4 * 1024, "/api/backups/preview": 1024, "/api/backups/restore": 1024, "/api/backups/copy-folder": 4096,
                     "/api/section-image": 1536 * 1024,     # #96 R1: one picture, shrunk by the page, in base64 (the route checks it)
                     "/api/ask-folders": 4096, "/api/ask-enabled": 1024, "/api/providers/connect": 1024, "/api/providers/disconnect": 1024, "/api/providers/model": 1024, "/api/ask": 128 * 1024, "/api/ask/stop": 1024,
                     "/api/ask/change/dry": 1024, "/api/ask/change/apply": 1024, "/api/ask/open-source": 1024, "/api/ai/suggest": 80 * 1024, "/api/ai/stop": 1024,
                     "/api/publications/archive": 1024, "/api/publications/restore": 1024,     # #345: a project code and a number
                     "/api/people": PEOPLE_BODY_LIMIT, "/api/people/undo": 1024,     # #115: a person's few short fields; #454: or one paste of up to 500 rows; a step number
                     "/api/profile": 2 * 1024,     # #65: a change or an undo is small; over is the 400 "too big"
                     "/api/page-error": 4 * 1024, "/api/logging": 1024, "/api/logging/open-folder": 1024,     # #110
                     "/api/draft-email": 16 * 1024,                    # #50: the ticked ids and a few short words
                     "/api/draft-email/sent": 4 * 1024,                # #50: the ids, the mode and the day: never the email's words
                     "/api/word-import": (WORD_FILE_MB * 4 // 3 + 1) * 1024 * 1024, "/api/word-export": 1024,      # #48
                     "/api/update/review": 1024, "/api/update/install": 1024, "/api/update/arm-undo": 1024, "/api/update/undo": 1024,
                     "/api/brands/review": 1024, "/api/brands/install": 1024, "/api/brands/remove": 1024, "/api/brands/undo": 1024,      # #944: a source word, a review id or a brand id; never a path
                     "/api/excel-import": (EXCEL_FILE_MB * 4 // 3 + 1) * 1024 * 1024,      # #444: a workbook as text, like the Word one
                     "/api/project": 4 * 1024,      # #444: a name, a code, a client and a few workstreams
                     "/api/demo/clear": 1024,      # #731: no words, only the token
                     "/api/section-file": 1024}     # #96: names a project and a section only; the file never comes in the request
PROJECT_CODE = re.compile(r"[A-Z][A-Z0-9]{2,6}")      # creaite's projects.code CHECK: 3 to 7 characters
CLIENT_LEFT = (BrokenPipeError, ConnectionResetError)  # the page went mid-reply: not a 500

# creaite SECURITY_HEADERS (BL-212). clark: Cache-Control is sent from end_headers too, so every reply carries it once.
SECURITY_HEADERS = (("Content-Security-Policy", "frame-ancestors 'none'"), ("X-Frame-Options", "DENY"),
                    ("X-Content-Type-Options", "nosniff"), ("Referrer-Policy", "no-referrer"))
NO_STORE = ("Cache-Control", "no-store")


class Busy(Exception):
    """A read the store refused in plain words that must reach the page as they are (a restore is under way): 503."""


class LengthRequired(ValueError):
    """A body sent without a Content-Length (chunked): refused with 411."""


class TooLarge(ValueError):
    """A body over the limit (or a negative length): refused with 400, code too_large."""


def error_body(code, **extra):
    """The JSON of an error reply: `message` in plain words for people, `code` stable for the page and the tests."""
    return {"ok": False, "message": MESSAGES[code], "code": code, **extra}


def host_name(host):
    """The host part of a Host header: `127.0.0.1:8766` → 127.0.0.1, `[::1]:8766` → ::1. (creaite host_name)"""
    host = (host or "").strip()
    if host.startswith("["):
        return host[1:host.find("]")] if "]" in host else ""
    return host.split(":")[0]


HOST_HEADER = re.compile(r"(127\.0\.0\.1|localhost|clark\.localhost|\[::1\])(?::([0-9]{1,5}))?")


def host_allowed(host):
    """Whether a Host header (or an Origin's host) is exactly this machine: 127.0.0.1, localhost, clark.localhost (row
    1076: the address the launcher opens; Chrome resolves *.localhost to this computer) or [::1], with an optional port
    of 1 to 65535 and nothing else. (clark: stricter than creaite's host_name check)"""
    m = HOST_HEADER.fullmatch(host or "")
    return bool(m) and (m.group(2) is None or 1 <= int(m.group(2)) <= 65535)


def token_ok(sent):
    """Whether `sent` is this run's token, compared in constant time as bytes (a non-ASCII token is simply wrong)."""
    return hmac.compare_digest((sent or "").encode("utf-8", "surrogatepass"), TOKEN.encode("ascii"))


# #71: /health says only {"ok": true}, unless the launcher asks with its mark of the data folder in X-Clark-Data: then it also says
# whether this server's data folder is that one ("this_data"). A web page can't send that header without a preflight, which is
# always refused. __main__ gives the server its mark (clark.appfiles.data_mark); with none set, "this_data" is false.
MARK_HEADER = "X-Clark-Data"
DATA_MARK = None
VERSION = None            # issue 745: the running clark's version, given by __main__ (this server imports nothing from clark); /health says it


CODE_MARK = None          # row 975: a mark of the folder this server's program files are in; /health tells it to the launcher (with the mark asked)


def set_code_mark(mark):
    """Give the server the mark of the folder its program files are in."""
    global CODE_MARK
    CODE_MARK = mark


def set_version(version):
    """Give the server the version it is running."""
    global VERSION
    VERSION = version


def set_data_mark(mark):
    """Give the server the mark of its data folder."""
    global DATA_MARK
    DATA_MARK = mark


def health_answer(asked):
    """What /health says: {"ok": true}, plus "this_data" only when `asked` (the X-Clark-Data header) is not empty."""
    out = {"ok": True}
    if VERSION is not None:
        out["version"] = VERSION
    if asked:
        out["this_data"] = DATA_MARK is not None and asked == DATA_MARK
        if CODE_MARK is not None:
            out["folder"] = CODE_MARK
    return out


# ===== The script policy (creaite BL-255, copied from report-only and sent enforced; #71 adds worker-src 'self') =====
# Every HTML reply carries Content-Security-Policy with the SHA-256 of each inline <script> the browser runs and each
# inline <style>, taken from the exact bytes sent. clark's page is one HTML file with inline scripts, so script-src lists
# hashes only (no 'self'); Tiptap keeps injectCSS: false (#35, #41). What the policy blocks is reported to /csp-report.
CSP_REPORT_ROUTE = "/csp-report"
CSP_REPORT_LIMIT, CSP_REPORT_WINDOW, CSP_REPORT_BYTES = 60, 60.0, 16 * 1024   # reports a minute; the largest body read
CSP_REPORTS = {"since": 0.0, "n": 0, "dropped": 0}
CSP_LOCK = threading.Lock()
CSP_BLOCK = re.compile(r"<!--|<(script|style)\b([^>]*)>", re.I)
CSP_END = {"script": re.compile(r"</script[\s/>]", re.I), "style": re.compile(r"</style[\s/>]", re.I)}
CSP_TYPE = re.compile(r"""\btype\s*=\s*["']?([^"'\s>]*)""", re.I)
CSP_JS_TYPES = ("", "module", "text/javascript", "application/javascript", "application/ecmascript", "text/ecmascript")
CSP_KINDS = ("inline", "eval", "wasm-eval", "trusted-types-policy", "trusted-types-sink")
CSP_LOOPBACK = ("127.0.0.1", "localhost", "clark.localhost", "::1")


def csp_sha(text):
    """The CSP source for one block's text: 'sha256-<base64>' of its UTF-8 bytes, line ends as the HTML parser reads them."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return "'sha256-" + base64.b64encode(hashlib.sha256(text.encode("utf-8")).digest()).decode() + "'"


def csp_hashes(html):
    """{"script": [...], "style": [...]}: the hashes of the inline blocks a browser would run or apply, in page order. A
    block ends at its first close tag, as the parser ends it; script text (a "<style>" in a string) is never read as markup;
    a script with src= or a data type (the JSON data block) is not run, so it needs no hash."""
    out, at = {"script": [], "style": []}, 0
    while True:
        m = CSP_BLOCK.search(html, at)
        if not m:
            return out
        if m.group(0) == "<!--":
            end = html.find("-->", m.end())
            at = len(html) if end < 0 else end + 3
            continue
        tag, attrs = m.group(1).lower(), m.group(2)
        end = CSP_END[tag].search(html, m.end())
        stop = end.start() if end else len(html)
        kind = (CSP_TYPE.search(attrs) or [None, ""])[1].lower()
        if tag == "style" or (kind in CSP_JS_TYPES and not re.search(r"\bsrc\s*=", attrs, re.I)):
            sha = csp_sha(html[m.end():stop])
            if sha not in out[tag]:
                out[tag].append(sha)
        at = stop


def csp_policy(html, host=None):
    """The enforced policy for one page: this page's script and style hashes, nothing from outside this machine.
    style="" attributes stay allowed (style-src-attr 'unsafe-inline'), which Preact and Tiptap need. Images come from data:,
    blob: and, under the Host the page was asked for (host_allowed, so nothing else is let in), the brand's /assets/ route and the app's own
    icons under /app/ (the manifest's, which the browser fetches as images) only."""
    h = csp_hashes(html if isinstance(html, str) else html.decode("utf-8", "surrogateescape"))
    scripts = " ".join(h["script"]) or "'none'"
    images = ["data:", "blob:"] + ([f"http://{host}{BRAND_PREFIX}", f"http://{host}{APP_ICON_PREFIX}"] if host_allowed(host) else [])
    return "; ".join([
        "default-src 'self'", f"script-src {scripts}", "worker-src 'self'",
        "style-src 'self' 'unsafe-inline'", " ".join(["style-src-elem 'self'"] + h["style"]), "style-src-attr 'unsafe-inline'",
        " ".join(["img-src"] + images), "font-src 'self' data:", "connect-src 'self'", "object-src 'none'",
        "base-uri 'none'", "form-action 'self'", "frame-ancestors 'none'", f"report-uri {CSP_REPORT_ROUTE}"])


def csp_kind(blocked):
    """What kind of source a report names, never the source itself: inline, eval, data, blob, self, external or other."""
    b = str(blocked or "").strip().lower()
    if b in CSP_KINDS:
        return b
    for scheme in ("data", "blob", "about", "filesystem"):
        if b.startswith(scheme + ":") or b == scheme:
            return scheme
    if b.startswith(("http://", "https://", "ws://", "wss://")):
        return "self" if host_name(b.split("://", 1)[1].split("/", 1)[0]) in CSP_LOOPBACK else "external"
    return "other"


def csp_directive(name):
    """A report's directive as a short plain name (script-src-elem…), or "unknown"."""
    d = (str(name or "").strip().lower().split() or [""])[0]
    return d if re.fullmatch(r"[a-z][a-z-]{0,39}", d) else "unknown"


def csp_reports(raw, ctype):
    """[(directive, kind)] from a report body: the classic application/csp-report form or the Reporting API's list."""
    data = json.loads(raw or b"{}")
    if ctype == "application/csp-report" or (isinstance(data, dict) and "csp-report" in data):
        r = data.get("csp-report") if isinstance(data, dict) else None
        r = r if isinstance(r, dict) else {}
        return [(csp_directive(r.get("effective-directive") or r.get("violated-directive")), csp_kind(r.get("blocked-uri")))]
    out = []
    for r in data if isinstance(data, list) else []:
        b = r.get("body") if isinstance(r, dict) and r.get("type") == "csp-violation" else None
        if isinstance(b, dict):
            out.append((csp_directive(b.get("effectiveDirective")), csp_kind(b.get("blockedURL"))))
    return out


def csp_local(handler):
    """Whether a request comes from this machine's own page: a local address and Host, and no other site's Origin. Every
    Origin and Sec-Fetch-Site header counts, not only the first, and an Origin must be this very Host and port (#65: the page
    is served from that one address; a page on another local port is another site). No Origin at all (a plain client) is fine."""
    if not handler.host_ok() or not local_peer(handler.client_address[0]):
        if container_mode() and not local_peer(handler.client_address[0]):
            note_refused_peer(handler.client_address[0])                 # item 427: the container's log names a refused peer, once
        return False
    get_all = getattr(handler.headers, "get_all", None)                  # a request with no version has no parsed headers (a dict)
    every = (lambda name: get_all(name) or []) if get_all else (lambda name: [v for v in [handler.headers.get(name)] if v])
    if any(p.strip().lower() == "cross-site" for v in every("Sec-Fetch-Site") for p in v.split(",")):      # one line may hold several values
        return False
    host = (handler.headers.get("Host") or "").lower()
    return all(o.lower() == "http://" + host for o in every("Origin"))


def csp_take(n):
    """Of `n` new reports, how many fit this minute's allowance; the rest are counted as dropped and said once a minute."""
    with CSP_LOCK:
        now = time.time()
        if now - CSP_REPORTS["since"] >= CSP_REPORT_WINDOW:
            if CSP_REPORTS["dropped"]:
                LOG.warning("%d more script-policy reports in the last minute were not logged", CSP_REPORTS["dropped"])
            CSP_REPORTS.update(since=now, n=0, dropped=0)
        room = max(0, min(n, CSP_REPORT_LIMIT - CSP_REPORTS["n"]))
        CSP_REPORTS["n"] += room
        CSP_REPORTS["dropped"] += n - room
        return room


TIMER_SKIPPED = "The timer for the turned-away count could not start. The count is written by the next request, or when clark stops."


class Refused:
    """Requests turned away before authorised() let them in (#234): counted, never a line of their own, so a page on another
    site looping requests at this port cannot fill the day's log. A burst in one window of `interval` seconds writes exactly
    one line, when the window ends: how many were turned away and how long the window was. A timer writes it, so a lone
    refusal or a last burst before quiet is still written; a later request writes it too if the timer has not yet. Nothing is
    written when the first request arrives. Only two whole numbers are written: nothing of any request (no path, query, header
    or Origin). A timer that cannot start is skipped, and one line says so the first time it happens (#553). `clock` is monotonic, so a clock stepping back never holds the line back; tests pass their own clock and
    `timer=None`."""

    def __init__(self, interval=CSP_REPORT_WINDOW, clock=time.monotonic, timer=threading.Timer):
        self.interval, self.clock, self.timer, self.lock = interval, clock, timer, threading.Lock()
        self.since, self.n, self.gen = None, 0, 0
        self.timer_noted = False                         # #553: the "no timer" line is written once

    def _close(self):
        """End the window (the lock is held): the count of the requests in it, or 0."""
        n, self.since, self.n = self.n, None, 0
        return n

    def flush(self, gen=None):
        """Write what the window counted and end it (the timer calls this, for the window it was started for)."""
        with self.lock:
            if gen is not None and gen != self.gen:
                return                                   # that window already ended; a newer one has its own timer
            n = self._close()
        self._say(n)

    def _say(self, n):
        """The one line for a window that has ended: fixed words (one message for 1, one for more), with only whole numbers
        (how many, and how many seconds the window was) as values."""
        secs = int(round(self.interval))
        if n == 1:
            LOG.warning("1 request was turned away in the last %d seconds.", secs)
        elif n:
            LOG.warning("%d requests were turned away in the last %d seconds.", n, secs)

    def count(self):
        done = 0
        with self.lock:
            now = self.clock()
            if self.since is not None and now - self.since >= self.interval:
                done = self._close()                     # the window ended before the timer wrote it
            if self.since is None:
                self.since, self.gen = now, self.gen + 1
                if self.timer:
                    try:
                        t = self.timer(self.interval, self.flush, (self.gen,))
                        t.daemon = True
                        t.start()
                    except (RuntimeError, OSError):      # no thread could be started: the next request or the stop writes the window
                        noted, self.timer_noted = self.timer_noted, True
                        if not noted:
                            LOG.warning("The timer for the turned-away count could not start. The count is written by the next request, or when clark stops.")   # #553: fixed words (the same as TIMER_SKIPPED, which the test pins), once; nothing of the error
            self.n += 1
        self._say(done)


REFUSED = Refused()


def refused_count():
    """One more request turned away (see Refused)."""
    REFUSED.count()


def csp_report_route(handler):
    """POST /csp-report: what the policy blocked. Local only, rate-limited, a small body; each report is one log line naming
    the directive and the kind of source, never a URL, a sample or page text. Writes nothing else."""
    if not csp_local(handler):
        return handler.send(403, error_body("not_allowed"))
    if handler.chunked():
        return handler.send(411, error_body("length_required"))
    try:
        n = int(handler.headers.get("Content-Length") or 0)
    except ValueError:
        n = -1
    if n < 0 or n > CSP_REPORT_BYTES:
        return handler.send(413, error_body("too_large"))
    ctype = (handler.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    if ctype not in ("application/csp-report", "application/reports+json", "application/json"):
        return handler.send(415, error_body("unsupported_type"))
    try:
        found = csp_reports(handler.rfile.read(n) if n else b"", ctype)
    except (ValueError, AttributeError, RecursionError):   # not JSON, not a browser's shape, or nested too deep
        return handler.send(400, error_body("bad_request"))
    for directive, kind in found[:csp_take(len(found))]:
        LOG.info("script policy blocked: %s %s", directive, kind)
    handler.send_response(204)
    handler.send_header("Content-Length", "0")
    handler.end_headers()
    return None
# ===== end of the script policy =====


# ===== The brand's pictures (#98) =====
BRAND_PREFIX = "/assets/"
APP_ICON_PREFIX = "/app/"                 # the app icons (appfiles.ICONS): an image source too, or the browser cannot show the manifest's icons
BRAND_ID = re.compile(r"[a-z0-9-]{1,40}")       # #944: a brand's id in /assets/<id>/<name>; only looked up by the seam, never joined onto a path
BRAND_PICTURES = ("logo.png", "cover.png", "cover.jpg", "cover.jpeg", "cover.webp")     # the fixed allow-list; = page.PICTURES (a test keeps the two equal)


def brand_picture_route(handler, name, brand_id=None):
    """GET /assets/<name> or (#944) /assets/<id>/<name>, for a name in BRAND_PICTURES only (the dispatcher checks, and checks the id's shape): the brand's picture. No token, since an
    <img> or a CSS url() can't send one, so the same local checks as /csp-report (csp_local: Host, a local address, no other
    site's Origin or Sec-Fetch-Site). The file comes from the `brand_picture` seam (page.brand_picture, given by the launcher), which never builds a path from a request."""
    if not csp_local(handler):
        return handler.send(403, error_body("not_allowed"))
    if handler.requestline.split()[1:2] != [handler.path]:      # newer Pythons fold "//assets/x" into "/assets/x": not this route
        return handler.send(404, error_body("not_found"))
    got = handler.server.brand_picture(name) if brand_id is None else handler.server.brand_picture(name, brand_id)
    if got is None:
        return handler.send(404, error_body("picture_not_found"))
    data, ctype = got
    handler.send_response(200)
    handler.send_header("Content-Type", ctype)
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)
    return None
# ===== end of the brand's pictures =====


# ===== The page and the data (the seams to #35 and #31) =====
# #960: the base text size (brand/tokens.css --size-body); this server imports nothing from clark, so a test keeps the two equal.
BODY_SIZE = "15px"
PLACEHOLDER = """<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8"><title>clark</title>
<style>body{font:@SIZE_BODY@ system-ui,sans-serif;margin:3rem}</style></head>
<body><p id="state">clark is starting.</p>
<script>document.getElementById("state").dataset.ready = "1";</script>
</body></html>
"""
PLACEHOLDER = PLACEHOLDER.replace("@SIZE_BODY@", BODY_SIZE)


def placeholder_html():
    """The page until #35 bundles the real one: one inline style and one inline script."""
    return PLACEHOLDER


def with_boot(html):
    """`html` with this run's token in a JSON data block before </body>. A data block is never run, so it needs no hash,
    and "<" is escaped so the block can't be closed early."""
    boot = json.dumps({"token": TOKEN}).replace("<", "\\u003c")
    block = f'<script type="application/json" id="clark-boot">{boot}</script>'
    i = html.rfind("</body>")
    html = html[:i] + block + html[i:] if i >= 0 else html + block
    return dev_marked(html) if os.environ.get("CLARK_DEV") == "1" else html


DEV_RIBBON = ('<div id="clark-dev-ribbon" style="position:fixed;top:0;left:50%;transform:translateX(-50%);z-index:2147483647;'
              'background:#d9480f;color:#fff;font:700 12px/1 system-ui,sans-serif;letter-spacing:.08em;padding:4px 14px;'
              'border-radius:0 0 8px 8px;pointer-events:none;box-shadow:0 1px 4px rgba(0,0,0,.3)">DEV COPY</div>')


def dev_marked(html):
    """The dev instance (CLARK_DEV=1, set by dev-clark.command) shows an orange DEV COPY tab at the top and "DEV" in the browser tab,
    so it is never taken for production. A style attribute only: the policy allows those, so no new hash is needed."""
    html = html.replace("<title>clark", "<title>DEV clark", 1)
    i = html.find("<body")
    j = html.find(">", i) + 1 if i >= 0 else -1
    return html[:j] + DEV_RIBBON + html[j:] if j > 0 else html


def data_route(handler):
    """GET /api/data?project=<CODE>[&archived=hide|show|only]: one project's data. 400 for a malformed code or an archived value
    that isn't in the list, 404 for a project that isn't there."""
    query = parse_qs(urlsplit(handler.path).query)
    code = (query.get("project") or [""])[0]
    if not PROJECT_CODE.fullmatch(code):
        return handler.send(400, error_body("bad_project_code"))
    given = parse_qs(urlsplit(handler.path).query, keep_blank_values=True).get("archived") or [None]
    shown = given[0]                                    # #126: hide (the default), show or only; checked against a fixed list, and given once
    if len(given) > 1 or shown is not None and shown not in ARCHIVED_VIEWS:
        return handler.send(400, error_body("bad_archived"))
    data = handler.server.data_for(code) if shown is None else handler.server.data_for(code, archived=shown)
    if data is None:
        return handler.send(404, error_body("project_not_found"))
    return handler.send(200, {"ok": True, "project": code, "data": data})


def movement_route(handler):
    """GET /api/movement?project=<CODE> (#136): what the Movement page draws, for the owner only. The read is a seam (`movement`,
    movement_read.make_read: the store's milestone_moves cut down by movement_view); this server imports nothing from clark. It is not
    in ask clark's reach and no published file is made from it. No body is accepted (400), a malformed code or another parameter is
    400, a missing project 404, and without the seam the route is not there (404). The reply is whatever movement_view lets
    through: no raw event, no internal note."""
    read = getattr(handler.server, "movement", None)
    if read is None:
        return handler.send(404, error_body("not_found"))
    if handler.headers.get("Content-Length") not in (None, "0") or handler.headers.get("Transfer-Encoding"):
        return handler.send(400, error_body("bad_request"))
    query = parse_qs(urlsplit(handler.path).query, keep_blank_values=True)
    given = query.get("project") or [""]
    code = given[0]
    if len(given) > 1 or set(query) - {"project"} or not PROJECT_CODE.fullmatch(code):
        return handler.send(400, error_body("bad_project_code"))
    view = read(code)
    if view is None:
        return handler.send(404, error_body("project_not_found"))
    return handler.send(200, {"ok": True, "project": code, "movement": view})


ITEM_ID = re.compile(r"[A-Z][A-Z0-9]{2,6}-(?:[A-Z]-)?\d{3,6}")      # #42: a work item's or milestone's ID, at most 16 characters


def activity_route(handler):
    """GET /api/activity?project=<CODE>&item=<ID> (#42): one item's changes, newest first, for the peek's Activity tab (Edit only).
    The read is a seam (`activity`, activity_read.make_read): it checks the item is the project's, reads history on a read-only
    connection and keeps only who, how, when and what changed. No body is accepted (400); each parameter once, nothing else, a
    code and an ID of the stored shape with the ID inside the project (400); a missing project or item 404; without the seam
    the route is not there (404)."""
    read = getattr(handler.server, "activity", None)
    if read is None:
        return handler.send(404, error_body("not_found"))
    if handler.headers.get("Content-Length") not in (None, "0") or handler.headers.get("Transfer-Encoding"):
        return handler.send(400, error_body("bad_request"))
    query = parse_qs(urlsplit(handler.path).query, keep_blank_values=True)
    codes, items = query.get("project") or [""], query.get("item") or [""]
    code, item = codes[0], items[0]
    if (set(query) != {"project", "item"} or len(codes) != 1 or len(items) != 1 or not PROJECT_CODE.fullmatch(code)
            or not ITEM_ID.fullmatch(item) or not item.startswith(code + "-")):
        return handler.send(400, error_body("bad_request"))
    view = read(code, item)
    if view is None:
        return handler.send(404, error_body("item_not_found"))
    return handler.send(200, {"ok": True, "project": code, "item": item, "activity": view})


def milestones_route(handler):
    """GET /api/milestones?project=<CODE> (#146): the milestones the Calendar and its list draw, read only. The read is a seam
    (`milestones`, milestone_feed.make_feed over the store's data_for); this server imports nothing from clark. Only the fields the
    page needs leave (no internal note, reason or description). No body is accepted (400), a malformed code or another parameter
    is 400, a missing project 404, and without the seam the route is not there (404). Nothing from the request is used as a path.
    The published file never calls it: its rows come from its own data block."""
    read = getattr(handler.server, "milestones", None)
    if read is None:
        return handler.send(404, error_body("not_found"))
    if handler.headers.get("Content-Length") not in (None, "0") or handler.headers.get("Transfer-Encoding"):
        return handler.send(400, error_body("bad_request"))
    query = parse_qs(urlsplit(handler.path).query, keep_blank_values=True)
    given = query.get("project") or [""]
    code = given[0]
    if len(given) > 1 or set(query) - {"project"} or not PROJECT_CODE.fullmatch(code):
        return handler.send(400, error_body("bad_project_code"))
    body = read(code)
    if body is None:
        return handler.send(404, error_body("project_not_found"))
    return handler.send(200, {"ok": True, "project": code, **body})


PAST_ROUTE = "/past"
PAST_SANDBOX = "sandbox allow-scripts"          # a kept page may run its own script, but as a null origin: never as clark (no allow-same-origin)
PUBLICATION_NUMBER = re.compile(r"[1-9][0-9]{0,5}")           # a whole number from 1 to 999999, as the kept copies' names allow


def past_route(method):
    """GET /api/publications?project=<CODE> and GET /api/past-report?project=<CODE>&number=<N> (#443): the Published reports list and
    Open. The server's `past` (past_reports.PastReports) answers (status, body); without one the routes are not there (404). The token,
    the Host and the Origin are checked before this runs, as for every GET under /api/. No body is accepted (400); each parameter
    once and nothing else, a code of the stored shape and a plain whole number (400). Nothing from the request is used as a path:
    the seam makes a kept copy's name from the code and the number, and reads nothing else. No path and no hash is in a reply."""
    def route(handler):
        seam = getattr(handler.server, "past", None)
        if seam is None:
            return handler.send(404, error_body("not_found"))
        if handler.headers.get("Content-Length") not in (None, "0") or handler.headers.get("Transfer-Encoding"):
            return handler.send(400, error_body("bad_request"))
        query = parse_qs(urlsplit(handler.path).query, keep_blank_values=True)
        want = {"project"} if method == "listing" else {"project", "number"}
        shown_archived = method == "listing" and query.get("archived") == ["1"]      # #345: Show archived; any other value is a 400
        if set(query) - ({"archived"} if shown_archived else set()) != want or any(len(v) != 1 for v in query.values()):
            return handler.send(400, error_body("bad_request"))
        code = query["project"][0]
        if not PROJECT_CODE.fullmatch(code):
            return handler.send(400, error_body("bad_project_code"))
        if method == "listing":
            status, body = seam.listing(code, archived=shown_archived)
        else:
            number = query["number"][0]
            if not PUBLICATION_NUMBER.fullmatch(number):
                return handler.send(400, error_body("bad_request"))
            status, body = seam.visit(code, int(number))
        return handler.send(status, body)
    return route


def publication_mark_route(action):
    """POST /api/publications/archive and /api/publications/restore (#345): {project, number} and nothing else. The server's
    `publication_mark` (changes.make_publication_mark) archives or restores that one publication and answers (status, body); it writes
    the archive mark and one history line, and offers no Undo. Checked like change_route before this runs (token, Host, Origin, JSON
    only, the route's own small limit). A body that is not exactly a code of the stored shape and a whole number from 1 to 999999 is
    the 400 bad_request; a refusal in the store's plain words is 400, and a publication already in the state asked for is 409. Without
    the seam, saving is switched off (503). Nothing from the request is used as a path: the seam makes the mark's name from the two."""
    def route(handler, req):
        seam = getattr(handler.server, "publication_mark", None)
        if seam is None:
            return handler.send(503, error_body("saving_off"))
        code = req.get("project") if isinstance(req, dict) else None
        number = req.get("number") if isinstance(req, dict) else None
        if (not isinstance(req, dict) or set(req) != {"project", "number"} or not isinstance(code, str) or not PROJECT_CODE.fullmatch(code)
                or type(number) is not int or not 1 <= number <= 999999):
            return handler.send(400, error_body("bad_request"))
        status, body = seam(action, req)
        return handler.send(status, body)
    return route


def as_at_route(handler):
    """GET /api/as-at?project=<CODE>&date=<YYYY-MM-DD> (#349): the project's data as at the end of that day, rebuilt from the change
    history. The server's `as_at` (as_at.AsAt) answers (status, body); it reads clark.db on a read-only connection and rebuilds in a
    copy of its own, so it never writes. Without the seam the route is not there (404). No body is accepted (400); each parameter
    once and nothing else (400); the seam checks the code and the day."""
    seam = getattr(handler.server, "as_at", None)
    if seam is None:
        return handler.send(404, error_body("not_found"))
    if handler.headers.get("Content-Length") not in (None, "0") or handler.headers.get("Transfer-Encoding"):
        return handler.send(400, error_body("bad_request"))
    query = parse_qs(urlsplit(handler.path).query, keep_blank_values=True)
    if set(query) != {"project", "date"} or any(len(v) != 1 for v in query.values()):
        return handler.send(400, error_body("bad_request"))
    if not PROJECT_CODE.fullmatch(query["project"][0]):
        return handler.send(400, error_body("bad_project_code"))
    status, body = seam.read(query["project"][0], query["date"][0])
    return handler.send(status, body)


def past_page_route(handler):
    """GET /past?id=: a kept page, once (#443). A new tab can't send the token, so the address itself is the one-visit secret (made by
    GET /api/past-report); the Host and Origin checks are as everywhere, the id is the one parameter, and what is sent is the kept
    file's own bytes, checked against its SHA-256 when the address was made. Nothing is written and no path is read from the request."""
    seam = getattr(handler.server, "past", None)
    if seam is None or not csp_local(handler):
        return handler.send(404 if seam is None else 403, error_body("not_found" if seam is None else "not_allowed"))
    query = parse_qs(urlsplit(handler.path).query, keep_blank_values=True)
    given = query.get("id") or [""]
    if set(query) != {"id"} or len(given) != 1:
        return handler.send(404, error_body("not_found"))
    body = seam.take(given[0])
    if body is None:
        return handler.send(404, error_body("not_found"))
    # The kept page runs in a sandbox with scripts but WITHOUT allow-same-origin: its origin is null, so it cannot read clark's page or
    # token (the cross-origin fetch of "/" is refused), and its /api calls arrive with Origin: null, which csp_local turns away.
    # The usual hash-only policy stays, so the sandbox only adds to it. (no-store and nosniff come from end_headers.)
    policy = csp_policy(body, handler.headers.get("Host")) + "; " + PAST_SANDBOX
    return handler.send(200, body, "text/html", extra={"Content-Security-Policy": policy})


ARCHIVED_VIEWS = ("hide", "show", "only")          # what ?archived= may be on /api/data (#126); never passed on unchecked
PROJECT_LIST_LIMIT = 500
PROJECT_NAME_LIMIT = 200


def projects_route(handler):
    """GET /api/projects[?archived=1]: the code and name of each project (and, when the list gives one, how many work items are open), nothing else, so the page can choose which one to ask for.
    Only a code of the shape the store accepts is listed (3 to 7 capital letters or digits), a row that isn't a dict is
    skipped, a name that is not text falls back to the code, a name is cut at PROJECT_NAME_LIMIT characters, and the list stops at
    PROJECT_LIST_LIMIT."""
    given = parse_qs(urlsplit(handler.path).query, keep_blank_values=True).get("archived") or [None]
    shown = given[0]                                    # #126: 1 lists the archived ones; given once
    if len(given) > 1 or shown not in (None, "1"):
        return handler.send(400, error_body("bad_archived"))
    out = []
    try:
        listed = handler.server.projects() if shown is None else handler.server.projects(archived=True)
    except Busy as e:
        return handler.send(503, {"ok": False, "message": str(e), "code": "restore_busy"})
    for row in listed:
        if len(out) >= PROJECT_LIST_LIMIT:
            break
        try:
            code = str(row["code"])
        except (KeyError, TypeError, IndexError):
            continue
        if not PROJECT_CODE.fullmatch(code):
            continue
        try:
            name = row["name"]
        except (KeyError, TypeError, IndexError):
            name = None
        if not isinstance(name, str) or not name.strip():           # only text is a name; anything else falls back to the code
            name = code
        one = {"code": code, "name": name[:PROJECT_NAME_LIMIT]}
        try:
            count = row["open"]
        except (KeyError, TypeError, IndexError):
            count = None
        if type(count) is int and count >= 0:                       # #439: the open work items, for the switcher; left out when not a plain count
            one["open"] = count
        out.append(one)
    return handler.send(200, {"ok": True, "projects": out})


def use_cases_route(handler):
    """GET /api/use-cases?project=<CODE>: the project's use cases for the Use Cases page (#163), read only. The one parameter is
    checked like data_route's; any other is refused. Without a reader (the server was given none) the route does not exist: 404
    not_found, whatever the request. 404 for a project that isn't there. The reader does all the work and writes nothing."""
    if handler.server.use_cases is None:
        return handler.send(404, error_body("not_found"))
    query = parse_qs(urlsplit(handler.path).query, keep_blank_values=True)
    given = query.get("project") or [""]
    if set(query) != {"project"} or len(given) != 1 or not PROJECT_CODE.fullmatch(given[0]):
        return handler.send(400, error_body("bad_project_code"))
    found = handler.server.use_cases(given[0])
    if found is None:
        return handler.send(404, error_body("project_not_found"))
    return handler.send(200, {"ok": True, "project": given[0], "use_cases": found})


def seam_route(handler, seam, req):
    """Pass a request to a seam (`change` or `undo`, given to the server) and send its answer, (status, body). The server
    imports no store: the seam does all the work, in plain words. With no seam, 503 saving_off (saving is switched off)
    A fault inside the seam is the one 500 of run_route, with no class and no text."""
    if seam is None:
        return handler.send(503, error_body("saving_off"))
    status, body = seam(req)
    return handler.send(status, body)


def change_route(handler, req):
    """POST /api/change (#65). The token, the Host, JSON only, the length and the body are checked before this runs."""
    return seam_route(handler, handler.server.change, req)


def section_body_route(handler, req):
    """POST /api/section-body (#273): the change of /api/change for a section's content, and only that. The seam (`section_body`, from
    clark.changes) refuses any other request and does the rest as `change` does, so every check, the step, the Undo and the history
    are the same. Checked like change_route before this runs, with its own body limit."""
    return seam_route(handler, handler.server.section_body, req)


def undo_route(handler, req):
    """POST /api/undo (#65). Checked like change_route before this runs."""
    return seam_route(handler, handler.server.undo, req)


def people_route(seam_name):
    """GET and POST /api/people and POST /api/people/undo (#115): hand the request to the server's seam of that name (`people`,
    `people_undo`, `people_list`), which answers (status, body). With no seam: saving is switched off for a write, not found for the
    read. Checked like change_route before this runs (token, Host, Origin, JSON only, the route's own limit)."""
    def route(handler, *req):
        seam = getattr(handler.server, seam_name)
        if seam is None:
            return handler.send(404 if seam_name == "people_list" else 503, error_body("not_found" if seam_name == "people_list" else "saving_off"))
        status, body = seam(*req)
        return handler.send(status, body)
    return route


def section_image_route(handler, req):
    """POST /api/section-image (#96 R1). Checked like change_route before this runs, with its own body limit."""
    return seam_route(handler, handler.server.section_image, req)


def sneak_route(handler, req):
    """POST /api/sneak/read (#42): typed words about one work item as from → to changes. Read only: the seam (clark.sneak) reads
    the project's data and the words with plain code and writes nothing. A refusal of the words is 200 with ok false and plain
    words; no seam is the 503 of the other routes."""
    ok = isinstance(req, dict) and set(req) <= {"project", "id", "text"}
    code, item, text = (req.get(k) for k in ("project", "id", "text")) if ok else (None, None, None)
    if not (isinstance(code, str) and PROJECT_CODE.fullmatch(code) and isinstance(item, str) and isinstance(text, str)):
        return handler.send(400, error_body("bad_request"))
    if handler.server.sneak is None:
        return handler.send(503, error_body("reading_off"))                 # a read, so not "saving is switched off"
    return seam_route(handler, handler.server.sneak, req)


# #71: the six files a browser fetches with no token (it sends no custom header for a manifest, a worker script or an icon).
# Their own table, GET only, matched by exact path (the query is dropped), fixed bytes read once, no data and no token in them.
# {route: (bytes, content type, extra headers)}. The server imports no other clark module (a guard test), so __main__ gives it
# the table from clark.appfiles.open_files() with set_open_files(); until then the table is empty and nothing is open.
OPEN_GET_ROUTES = {}


def set_open_files(files):
    """Give the server its open files, replacing any earlier set. (Module setting, so serve()'s signature stays as it is.)"""
    OPEN_GET_ROUTES.clear()
    OPEN_GET_ROUTES.update(files)


def open_route(handler, route):
    """Send one of the six open files: fixed bytes, its own type and its extra headers (the worker's own policy)."""
    data, ctype, extra = OPEN_GET_ROUTES[route]
    return handler.send(200, data, ctype, extra)


# #71: "still here". An open clark page posts to /api/here every few seconds (with the token), and opening the page counts too.
# Only a server the launcher started has an Idle (clark.idle, given by __main__ with set_idle); it stops that server when no
# window has said so for two minutes and no job is running. A server started by hand has none and never stops by itself.
HERE_ROUTE = "/api/here"
IDLE = None
BUSY = {"n": 0}
BUSY_KINDS = {"save": 0, "publish": 0}   # the running POST routes by kind: a Publish is "publish"; a POST that writes data or a file is "save"; any other is not a kind
PUBLISH_PATHS = ("/api/publish",)
SAVE_PATHS = ("/api/change", "/api/section-body", "/api/undo", "/api/section-image", "/api/section-file", "/api/client-folder",
              "/api/backups/restore", "/api/backups/copy-folder", "/api/ask/change/apply", "/api/ask-folders", "/api/ask-enabled",
              "/api/profile", "/api/people", "/api/people/undo", "/api/project", "/api/publications/archive", "/api/publications/restore",
              "/api/draft-email/sent", "/api/word-import", "/api/word-export", "/api/excel-import", "/api/demo/clear",
              "/api/brands/install", "/api/brands/remove", "/api/brands/undo")     # the POST routes that write project data or a file; the rest (ask, suggest, preview, reads) count as busy only
BUSY_LOCK = threading.Lock()
JOB_WAIT_LIMIT = 60.0                  # seconds the server waits for a running job once it has been told to stop


def set_idle(idle):
    """Give the server the idle watch of a launcher-started run (None: it never stops by itself)."""
    global IDLE
    IDLE = idle


def mark_here():
    """A window said it is open."""
    if IDLE is not None:
        IDLE.here()


def busy():
    """Whether a POST route is running now (a later Publish or Import is covered by run_route, with no list to keep)."""
    with BUSY_LOCK:
        return BUSY["n"] > 0


def running_kind():
    """What the running job is, for the Quit card: "publish" while a Publish runs, else "save" while any other data job runs, else None."""
    with BUSY_LOCK:
        if BUSY_KINDS["publish"] > 0:
            return "publish"
        return "save" if BUSY_KINDS["save"] > 0 else None


def others_busy():
    """Whether a POST route other than the one asking is running: an update's install or undo (itself a POST) waits for these
    to finish before it backs up the data."""
    with BUSY_LOCK:
        return BUSY["n"] > 1


def page_load_is_ours(headers, port):
    """Whether a load of the page counts as "a window is open": the browser says it came from the address bar or this site
    (`Sec-Fetch-Site` absent, none or same-origin) and no foreign Origin is sent. Anything else still gets the page
    (it cannot read it) but cannot keep a launcher-started server alive."""
    site = headers.get("Sec-Fetch-Site")
    if site is not None and site.strip().lower() not in ("none", "same-origin"):      # an empty value is not a browser's
        return False
    origin = headers.get("Origin")
    return origin is None or origin in (f"http://127.0.0.1:{port}", f"http://localhost:{port}", f"http://clark.localhost:{port}")


def here_route(handler, req):
    """POST /api/here: the token, the Host, JSON only, the length and the body are checked before this runs."""
    mark_here()
    return handler.send(200, {"ok": True})


def publisher_route(method):
    """A route that hands its request to the server's publisher (publish_flow.Publisher, #43), which answers (status, body).
    Without a publisher there is nothing to ask: not found. The decisions, the checks and the only write into a client folder
    are in publish_flow.py and to_client.py, not here."""
    def route(handler, *req):
        publisher = getattr(handler.server, "publisher", None)
        if publisher is None:
            return handler.send(404, error_body("not_found"))
        if not req:                          # a GET: the project comes from the address
            req = ((parse_qs(urlsplit(handler.path).query).get("project") or [""])[0],)
        status, body = getattr(publisher, method)(*req)
        return handler.send(status, body)
    return route


PREVIEW_ROUTE = "/preview"
DOWNLOAD_CHUNK = 64 * 1024
XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


# What the address of a preview shows once it has been opened, or when it ran out of time or was never made: a plain page in the
# browser tab, in plain words, not a bare line (the prototype's Preview is a page in a tab). It names nothing internal.
PREVIEW_GONE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Preview not available</title>
<style>
:root { color-scheme: light dark; }
body { margin: 0; min-height: 100vh; display: grid; place-items: center; font: @SIZE_BODY@/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; background: #f4f6f9; color: #1d2733; }
main { box-sizing: border-box; max-width: 34rem; margin: 24px; padding: 28px 32px; background: #fff; border: 1px solid #d9dee5; border-radius: 12px; }
h1 { margin: 0 0 8px; font-size: 1.4rem; font-weight: 500; }
p { margin: 0 0 8px; color: #55606e; }
@media (prefers-color-scheme: dark) { body { background: #12171d; color: #e8ecf1; } main { background: #1b222b; border-color: #2e3844; } p { color: #a9b4c1; } }
</style></head><body><main>
<h1>This preview is no longer available</h1>
<p>A preview opens once, and only for a couple of minutes after you ask for it.</p>
<p>Go back to clark, open your menu (the circle at the top right) and choose Preview the page in a new tab for a new one.</p>
</main></body></html>
"""
PREVIEW_GONE = PREVIEW_GONE.replace("@SIZE_BODY@", BODY_SIZE)


def page_for(page_html, code):
    """The page for a well-formed project code, or the page with no argument (no code, or a seam that takes none: tests pass one)."""
    if code is not None:
        try:
            inspect.signature(page_html).bind(code)
        except TypeError:
            return page_html()
        return page_html(code)
    return page_html()


def page_route(handler):
    """GET /: the page, with this run's token. Run through run_route like every other route, so a page that cannot be made (a
    copy of clark without its page files that cannot build them) is answered with a 500 in plain words.
    Before, the error left the handler and the standard library closed the connection with no answer at all."""
    if page_load_is_ours(handler.headers, handler.server.server_port):
        mark_here()
    given = parse_qs(urlsplit(handler.path).query).get("project") or [None]      # #944: GET /?project=<code> is the page in that project's brand
    code = given[0] if len(given) == 1 and given[0] and PROJECT_CODE.fullmatch(given[0]) else None
    return handler.send(200, with_boot(page_for(handler.server.page_html, code)), "text/html")


def preview_page_route(handler):
    """GET /preview?id=: the page a preview made, once. A new tab can't send the token, so the address itself is the one-visit
    secret (made by POST /api/preview); the Host and Origin checks are as everywhere. Nothing is written."""
    publisher = getattr(handler.server, "publisher", None)
    if publisher is None or not csp_local(handler):
        return handler.send(404 if publisher is None else 403, error_body("not_found" if publisher is None else "not_allowed"))
    body = publisher.take_preview((parse_qs(urlsplit(handler.path).query).get("id") or [""])[0])
    if body is None:
        return handler.send(404, PREVIEW_GONE, "text/html")      # a second visit, a late one or a guess: a plain page, still a 404
    return handler.send(200, body, "text/html")


def content_disposition(name):
    """Row 1143: an attachment header for `name`. A name of plain ASCII is `filename="..."` as before; any other gets an ASCII
    fallback there and the whole name in `filename*` (RFC 6266), since a header holds no more than latin-1 and the browser
    reads `filename*` first."""
    if name.isascii():
        return f'attachment; filename="{name}"'
    plain = re.sub(r'[^\x20-\x7e]', "_", name)
    return f"attachment; filename=\"{plain}\"; filename*=UTF-8''{quote(name, safe='')}"


def export_route(handler):
    """GET /api/export?project=<CODE>: the workbook as a download, or the publisher's plain refusal as JSON. GET /api/export?template=1
    (#454): the import template instead, an export's workbook with no rows, which names no project and reads nothing from the store;
    no other value of `template` and nothing else in the query is read for it, and a request value never reaches a path."""
    publisher = getattr(handler.server, "publisher", None)
    if publisher is None:
        return handler.send(404, error_body("not_found"))
    query = parse_qs(urlsplit(handler.path).query)
    if query.get("template") == ["1"]:
        status, body = publisher.template()
    else:
        status, body = publisher.export((query.get("project") or [""])[0])
    if status != 200:
        return handler.send(status, body)
    data = body["data"]
    handler.send_response(200)
    handler.send_header("Content-Type", XLSX_TYPE)
    handler.send_header("Content-Length", str(len(data)))
    handler.send_header("Content-Disposition", content_disposition(body["name"]))
    if body.get("warnings"):
        handler.send_header("X-Export-Warning", quote(" ".join(body["warnings"]), safe=" "))        # plain words, any logo warning
    handler.end_headers()
    for i in range(0, len(data), DOWNLOAD_CHUNK):
        handler.wfile.write(data[i:i + DOWNLOAD_CHUNK])
    return None


def safety_route(method):
    """A route that hands its request to the server's `safety` (safety.Safety, #111), which answers (status, body): the backup list,
    Preview and Restore. Without one: 503, in plain words. The checks and the swap are in safety.py and backup.py, not here."""
    def route(handler, *req):
        safety = handler.server.safety
        if safety is None:
            return handler.send(503, error_body("no_backups"))
        status, body = getattr(safety, method)(*req)
        return handler.send(status, body)
    return route


def draft_email_route(seam_name):
    """POST /api/draft-email and /api/draft-email/sent (#50): hand the request to the server's seam of that name, which answers
    (status, body). The first writes nothing and sends nothing; the second records one "I sent it" (ids, mode, day, and the one History sentence the server composes; never the address or the body of
    the email). With no seam there is nothing to ask: not found. Checked like change_route before this runs (token, Host, Origin,
    JSON only, a Content-Length, the route's own limit)."""
    def route(handler, req):
        seam = getattr(handler.server, seam_name)
        if seam is None:
            return handler.send(404, error_body("not_found"))
        status, body = seam(req)
        return handler.send(status, body)
    return route


def ask_folders_route(method):
    """GET and POST /api/ask-folders (#47): the folders asking may read. The server's `ask_folders` (ask_folders.AskFolders)
    answers (status, body); without one there is nothing to ask: not found. The token, the Host, the Origin, JSON only and the
    length are checked before this runs; the checks of the folder and the only write are in ask_folders.py and the store."""
    def route(handler, *req):
        service = getattr(handler.server, "ask_folders", None)
        if service is None:
            return handler.send(404, error_body("not_found"))
        if not req:                          # a GET: the project comes from the address
            req = ((parse_qs(urlsplit(handler.path).query).get("project") or [""])[0],)
        status, body = getattr(service, method)(*req)
        return handler.send(status, body)
    return route


def ai_connect_route(method):
    """GET /api/providers and POST /api/providers/connect, /disconnect and /model (#54): hand the request to the server's `ai_connect`
    (ai_connect.AiConnect), which answers (status, body). Without one: not found."""
    def route(handler, *req):
        service = getattr(handler.server, "ai_connect", None)
        if service is None:
            return handler.send(404, error_body("not_found"))
        status, body = getattr(service, method)(*req)
        return handler.send(status, body)
    return route


def app_settings_route(method):
    """GET and POST /api/ask-enabled (#47): asking's on/off switch for this computer. The server's `app_settings`
    (app_settings.AppSettings) answers (status, body); without one there is nothing to ask: not found. The token, the Host, the
    Origin, JSON only and the length are checked before this runs; the value checks and the only write are in app_settings.py and
    the store."""
    def route(handler, *req):
        service = getattr(handler.server, "app_settings", None)
        if service is None:
            return handler.send(404, error_body("not_found"))
        status, body = getattr(service, method)(*req)
        return handler.send(status, body)
    return route


def ask_route(method, attr="ask"):
    """POST /api/ask, GET /api/ask/status and POST /api/ask/stop (#47): a question about the open project, whether asking can
    answer, and Stop. The server's `ask` (ask_service.AskService) answers (status, body): it reads the switch from the store before
    anything is sent, so nothing leaves while asking is off; without one there is nothing to ask: not found. The token, the Host,
    the Origin, JSON only and the length are checked before this runs; no model code is in this module. #47e: POST
    /api/ask/change/dry and /apply hand the dry run and Apply of a suggested change to the same service, which never asks a model.
    #72: the AI routes (/api/ai/suggest, /status, /stop) go the same way to the server's `ai` (ai_service.AiService)."""
    def route(handler, *req):
        service = getattr(handler.server, attr, None)
        if service is None:
            return handler.send(404, error_body("not_found"))
        status, body = getattr(service, method)(*req)
        if method == "ask" and isinstance(body, dict) and "held" in body:
            if body["held"] is True:
                LOG.warning("question answer dropped, it held the private marker")     # #277: a fixed line; no reply, no marker
            body = {k: v for k, v in body.items() if k != "held"}                 # #300: the log needs the flag; the page does not
        return handler.send(status, body)
    return route


def logs_route(method):
    """A route that hands its request to the server's logs seam (log_routes.Logs, #110), which answers (status, body). Without
    one there is nothing to ask: not found. What may be logged and what a report holds are decided in log.py, not here."""
    def route(handler, *req):
        logs = getattr(handler.server, "logs", None)
        if logs is None:
            return handler.send(404, error_body("not_found"))
        status, body = getattr(logs, method)(*req)
        return handler.send(status, body)
    return route


def word_import_route(handler, req):
    """POST /api/word-import (#48). Checked like change_route before this runs: the token, the Host, no other site's Origin, JSON
    only, a Content-Length and the route's own size limit."""
    return seam_route(handler, handler.server.word_import, req)


def word_export_route(handler, req):
    """POST /api/word-export (#48). Checked like change_route before this runs."""
    return seam_route(handler, handler.server.word_export, req)


def excel_import_route(handler, req):
    """POST /api/excel-import (#444). Checked like change_route before this runs: the token, the Host, no other site's Origin, JSON
    only, a Content-Length and the route's own size limit."""
    return seam_route(handler, handler.server.excel_import, req)


def project_save_route(handler, req):
    """POST /api/project (#444): a new project, or a project's name, client and added workstreams. Checked like change_route before this runs."""
    return seam_route(handler, handler.server.project_save, req)


def profile_route(method):
    """GET and POST /api/profile (#180): hand the request to the server's `profile` (profile_settings.Profile), which answers (status,
    body). Without one: not found. Checked like change_route before this runs (token, Host, Origin, JSON only, the 2 KiB limit)."""
    def route(handler, *req):
        seam = handler.server.profile
        if seam is None:
            return handler.send(404, error_body("not_found"))
        status, body = getattr(seam, method)(*req)
        return handler.send(status, body)
    return route


def demo_route(method):
    """GET /api/demo (is demo data on show) and POST /api/demo/clear (#731): hand the request to the server's `demo` (demo_seed.Demo),
    which answers (status, body). Without one: not on show, and nothing to remove. Checked like change_route before this runs."""
    def route(handler, *req):
        if handler.server.demo is None:
            return handler.send(200, {"ok": True, "demo": False}) if method == "status" else handler.send(503, error_body("saving_off"))
        status, body = getattr(handler.server.demo, method)(*req)
        return handler.send(status, body)
    return route


def update_route(method):
    """A route that hands its request to the server's `updater` (updater.Updater), which answers (status, body). Without one: 503.
    An answer that says "restart" (an install or an undo was handed to the update helper) stops this server once it is sent, so
    the helper can replace the files; the helper starts the new version."""
    def route(handler, *req):
        updater = handler.server.updater
        if updater is None:
            return handler.send(503, error_body("no_updates"))
        status, body = getattr(updater, method)(*req)
        handler.send(status, body)
        if status == 200 and body.get("restart") is True:
            threading.Thread(target=handler.server.shutdown, daemon=True).start()
        return None
    return route


def quit_route(handler, req):
    """POST /api/quit (#836): answer, then stop this server the way an update's restart does (serve() waits for a running job, closes
    the socket and ends; __main__ then lets go of the data folder). The token, the Host, the Origin, JSON only and the length are
    checked before this runs. Nothing is read from the body."""
    handler.send(200, {"ok": True, "quit": True, "finishing": running_kind()})   # "save", "publish" or None: the card says which job is finished first
    threading.Thread(target=handler.server.shutdown, daemon=True).start()


UPDATE_ROUTES = ("/api/update", "/api/update/review", "/api/update/install", "/api/update/arm-undo", "/api/update/undo")


def updating(handler, route):
    """While an update is being installed every route but the update's own answers 503 in plain words (sent here)."""
    updater = getattr(handler.server, "updater", None)
    if updater is None or route in UPDATE_ROUTES or route == HERE_ROUTE or not updater.installing():
        return False
    handler.send(503, error_body("updating"))
    return True


# ===== The brands (#944 T2) =====
BRAND_BODY_KEYS = {"review": {"from"}, "install": {"review_id"}, "remove": {"id"}, "undo": set()}


def brand_route(method):
    """GET /api/brands and POST /api/brands/review, /install, /remove, /undo: hand the request to the server's `brands` seam (listing(),
    review(body), install(body), remove(body), undo(body); each answers (status, body)). Without one: 503. A body that is not an object is
    a plain 400; a "path" is dropped before the seam hears (the page never sends one: the file is chosen in the system dialog or is the
    newest in Downloads). Checked like change_route before this runs (token, Host, Origin, JSON only, the route's own 1 KiB limit)."""
    def route(handler, *req):
        seam = handler.server.brands
        if seam is None:
            return handler.send(503, error_body("no_brands"))
        if method != "listing":
            if not isinstance(req[0], dict):
                return handler.send(400, error_body("bad_request"))
            req = ({k: v for k, v in req[0].items() if k != "path"},)
        status, body = getattr(seam, method)(*req)
        return handler.send(status, body)
    return route


BRAND_PATHS = {"root": None, "data": None}


def set_brand_paths(root, data):
    """Give the server the clark folder (holding branding/) and the data folder, so serve() can make the brand seam."""
    BRAND_PATHS["root"], BRAND_PATHS["data"] = root, data


class BrandLibrary:
    """The `brands` seam over clark.brands (found by name when asked, so this module imports no other clark module). It chooses the
    file (the newest zip in Downloads, or the system's Open dialog) and turns the library's refusals into (status, body); the checks
    are all in the library. `choose` and `downloads` are seams for tests."""

    def __init__(self, root, data, choose=None, downloads=None):
        self.root, self.data, self.choose, self.downloads = root, data, choose, downloads

    @staticmethod
    def library():
        return importlib.import_module("clark.brands")

    def _run(self, call):
        lib = self.library()
        try:
            return 200, dict(call(lib), ok=True)
        except lib.BrandError as e:
            return (409 if e.key in ("expired", "busy") else 400), {"ok": False, "code": e.key or "refused", "message": e.message}
        except OSError:             # the Downloads folder or the Open dialog failing: the same plain refusal as the library's own
            return 400, {"ok": False, "code": "failed", "message": lib.MESSAGES["failed"]}
        except Exception as e:      # item 1100: in Docker, the needs-the-Mac sentence, not a fault; found by the class name, so no top-level import of clark is needed
            if type(e).__name__ != "NotBuiltYet":
                raise
            plat = importlib.import_module("clark.platform")
            return 409, {"ok": False, "code": "needs_mac", "message": plat.refusal_words(e, plat.not_built_words())}

    def listing(self):
        return self._run(lambda lib: {"brands": lib.installed(self.root), "undo": lib.can_undo(self.root, self.data),
                                      "review_ready": self._review_ready(lib)})

    def _review_ready(self, lib):
        plat = importlib.import_module("clark.platform")
        try:
            return lib.newest_brand_zip(self._downloads(plat)) is not None
        except plat.NotBuiltYet:    # no Downloads folder to read here (Docker, Windows, Linux): an empty review, the rest of the listing stands
            return False

    def _file(self, source):
        plat = importlib.import_module("clark.platform")
        if source == "file":
            return (self.choose or plat.choose_zip_file)("Choose a brand file", start=self._downloads(plat))
        return self.library().newest_brand_zip(self._downloads(plat))

    def _downloads(self, plat):
        return self.downloads if self.downloads is not None else plat.downloads_dir()

    def review(self, body):
        if set(body) - BRAND_BODY_KEYS["review"] or body.get("from") not in ("downloads", "file"):
            return 400, error_body("bad_request")
        def look(lib):
            path = self._file(body["from"])
            return {"review": None if path is None else lib.review(path, self.root)}
        return self._run(look)

    def install(self, body):
        if set(body) - BRAND_BODY_KEYS["install"] or not isinstance(body.get("review_id"), str):
            return 400, error_body("bad_request")
        return self._run(lambda lib: (lib.install(body["review_id"], self.root, self.data), {})[1])

    def remove(self, body):
        if set(body) - BRAND_BODY_KEYS["remove"] or not isinstance(body.get("id"), str):
            return 400, error_body("bad_request")
        return self._run(lambda lib: (lib.remove(body["id"], self.root, self.data), {})[1])

    def undo(self, body):
        if body:
            return 400, error_body("bad_request")
        return self._run(lambda lib: (lib.undo(self.root, self.data), {})[1])


GET_ROUTES = {"/api/projects": projects_route, "/api/data": data_route, "/api/publication": publisher_route("latest"),
              "/api/export": export_route, "/api/use-cases": use_cases_route, "/api/backups": safety_route("listing"),
              "/api/movement": movement_route, "/api/activity": activity_route, "/api/milestones": milestones_route, "/api/ask-folders": ask_folders_route("read"),
              "/api/ask-enabled": app_settings_route("read_ask"), "/api/providers": ai_connect_route("get"), "/api/ask/status": ask_route("status"), "/api/ai/status": ask_route("status", "ai"),
              "/api/profile": profile_route("get"), "/api/people": people_route("people_list"), "/api/update": update_route("status"), "/api/diagnostics": logs_route("diagnostics"),
              "/api/publications": past_route("listing"), "/api/past-report": past_route("open"), "/api/as-at": as_at_route, "/api/demo": demo_route("status"),
              "/api/brands": brand_route("listing")}
POST_ROUTES = {"/api/change": change_route, "/api/section-body": section_body_route, "/api/undo": undo_route, "/api/section-image": section_image_route, "/api/sneak/read": sneak_route, "/api/publish": publisher_route("publish"),
               "/api/quit": quit_route, "/api/client-folder": publisher_route("client_folder"), "/api/preview": publisher_route("preview"),
               "/api/backups/preview": safety_route("preview"), "/api/backups/restore": safety_route("restore"), "/api/backups/copy-folder": safety_route("copy_folder"),
                "/api/ask-folders": ask_folders_route("change"), "/api/ask-enabled": app_settings_route("change_ask"), "/api/providers/connect": ai_connect_route("connect"),
                "/api/providers/disconnect": ai_connect_route("disconnect"), "/api/providers/model": ai_connect_route("choose"),
                "/api/ask": ask_route("ask"), "/api/ask/stop": ask_route("stop"),
                "/api/ai/suggest": ask_route("suggest", "ai"), "/api/ai/stop": ask_route("stop", "ai"),
                "/api/ask/change/dry": ask_route("change_dry"), "/api/ask/change/apply": ask_route("change_apply"),
                "/api/ask/open-source": ask_route("open_source"),     # #943
                "/api/profile": profile_route("save"), "/api/people": people_route("people"), "/api/people/undo": people_route("people_undo"), "/api/page-error": logs_route("page_error"),
                "/api/logging": logs_route("set_level"), "/api/logging/open-folder": logs_route("open_folder"),     # #110
                "/api/update/review": update_route("review"),
                "/api/update/install": update_route("install"), "/api/update/arm-undo": update_route("arm_undo"),
                "/api/update/undo": update_route("undo"),
                "/api/publications/archive": publication_mark_route("archive"), "/api/publications/restore": publication_mark_route("restore"),     # #345
                "/api/draft-email": draft_email_route("draft_email"),
                "/api/draft-email/sent": draft_email_route("draft_email_sent"),
                "/api/word-import": word_import_route, "/api/word-export": word_export_route,
                "/api/excel-import": excel_import_route, "/api/project": project_save_route,     # #444
               "/api/demo/clear": demo_route("remove"),     # #731
               "/api/brands/review": brand_route("review"), "/api/brands/install": brand_route("install"),     # #944
               "/api/brands/remove": brand_route("remove"), "/api/brands/undo": brand_route("undo"),
                "/api/section-file": publisher_route("section_file")}     # later items: /api/import
# ===== end of the page and the data =====


class Handler(BaseHTTPRequestHandler):
    """The requests. Every reply carries the security headers; every /api/ route goes through authorised() first."""
    server_version = "clark"
    sys_version = ""                                   # clark: the Python version isn't sent
    default_request_version = "HTTP/1.0"               # clark: a request line that doesn't parse still gets headers
    timeout = 30                                       # clark: an idle or half-sent request never holds a thread

    def parse_request(self):
        self.let_in = False                            # set by authorised(); fresh for each request (#234)
        return super().parse_request()

    def log_request(self, code="-", size="-"):
        """A reply to a request authorised() did not let in (any /api/ call before its token passed, and any refusal: a 403,
        a doubled header, an unknown method, an oversized header) is counted, not a line of its own (#234)."""
        if not getattr(self, "let_in", False) and ((getattr(self, "path", "") or "").startswith("/api/")
                                                   or (isinstance(code, int) and code >= 400)):
            return refused_count()
        return super().log_request(code, size)

    def log_message(self, fmt, *args):
        """Quiet: one log line per API call; safe when the request line didn't parse. (creaite log_message)"""
        path = getattr(self, "path", "") or ""
        if path.startswith("/api/") and path.split("?")[0] not in (HERE_ROUTE, "/api/page-error"):   # the heartbeat is not logged; a page error's own capped line is its record
            LOG.info("%s %s", ascii(getattr(self, "command", "") or "")[1:-1], ascii(path.split("?")[0])[1:-1])   # escaped: no raw bytes

    def send_error(self, code, message=None, explain=None):
        """The standard library's own error pages (a method clark has no handler for, a request line or headers it cannot
        read) as the server's plain JSON error, never Python's HTML. `message` and `explain` carry the method or the
        request's bytes and are ignored, so nothing of the request is echoed. A HEAD reply has the headers and no body."""
        key = ERROR_PAGES.get(code) or ("server_error" if code >= 500 else "bad_request")
        data = json.dumps(error_body(key)).encode()
        self.send_response(code)           # the standard reason for the code, not the request's text
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Connection", "close")
        self.end_headers()
        if getattr(self, "command", None) != "HEAD":
            self.wfile.write(data)

    def host_ok(self):
        """Whether the Host header is exactly this machine. (creaite host_ok, BL-212; clark: strict, see host_allowed)"""
        return host_allowed(self.headers.get("Host"))

    def follow_zone(self):
        """#631: in the container only, the page's time zone (X-Clark-Tz) is applied before the request is routed; anything that is not
        an IANA name is ignored. Found by name when asked, so this module imports no other clark module."""
        if container_mode():
            importlib.import_module("clark.zone").follow_header(self.headers.get("X-Clark-Tz"), True)

    def headers_ok(self):
        """No second Host or Content-Length (which one counts would depend on who reads it); sends the 400 when not."""
        get_all = getattr(self.headers, "get_all", None)       # a request with no version has no parsed headers (a dict)
        if get_all and any(len(get_all(h) or []) > 1 for h in ("Host", "Content-Length")):
            self.send(400, error_body("bad_request"))
            return False
        return True

    def end_headers(self):
        """Every response, `send` and the standard library's own errors alike, carries the security headers and no-store,
        once each. (creaite end_headers, BL-212; clark: no-store here, not in send)"""
        for k, v in SECURITY_HEADERS + (NO_STORE,):
            self.send_header(k, v)
        super().end_headers()

    def send(self, code, body, ctype="application/json", extra=None):
        """Send one reply: JSON for a dict, else text or bytes as `ctype`; an HTML reply carries its enforced script
        policy, built from its own bytes. (creaite send)"""
        data = body if isinstance(body, bytes) else (json.dumps(body) if ctype == "application/json" else body).encode()
        self.send_response(code)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        if ctype == "text/html":
            extra = {"Content-Security-Policy": csp_policy(data, self.headers.get("Host")), **(extra or {})}
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def chunked(self):
        """Whether the body is sent chunked (no Content-Length)."""
        return "chunked" in (self.headers.get("Transfer-Encoding") or "").lower()

    def body(self):
        """The request's JSON body ({} when empty). LengthRequired when it has no Content-Length; ValueError when the length
        is malformed or over the limit, or the body isn't JSON. (creaite body; clark: 411 and a malformed length)"""
        if self.chunked() or self.headers.get("Content-Length") is None:
            raise LengthRequired("no Content-Length")
        n = int(self.headers["Content-Length"])          # ValueError when it isn't a number
        if n < 0 or n > ROUTE_BODY_LIMITS.get(self.path.split("?")[0], BODY_LIMIT):
            raise TooLarge("request too large")
        try:
            return json.loads(self.rfile.read(n) or b"{}") if n else {}
        except RecursionError:                          # nested too deep to read: a bad request, not a fault
            raise ValueError("nested too deep") from None

    def authorised(self):
        """Whether an API call may go ahead: the right Host, no other site's Origin (csp_local's test, #65: a page on another
        site can't make the browser change anything), and this run's token. Sends the 403 itself when not; a page opened
        before a restart is told to reload. (creaite authorised; clark: compared in constant time)"""
        if not csp_local(self):
            self.send(403, error_body("not_allowed"))
            return False
        sent = self.headers.get(TOKEN_HEADER)
        if not sent:
            self.send(403, error_body("not_allowed"))
            return False
        if not token_ok(sent):
            self.send(403, error_body("stale", stale=True))
            return False
        self.let_in = True
        return True

    def run_route(self, route, *args):
        """Run a route; a fault is a 500 in plain words (code server_error). The class, the text and the stack go to the log
        only: the text could name a path, and a person gets no technical word."""
        counted = self.command == "POST" and route is not here_route       # a POST mid-run keeps the idle stop waiting
        kind = None
        if counted and route is not quit_route:
            where = self.path.split("?")[0]
            kind = "publish" if where in PUBLISH_PATHS else "save" if where in SAVE_PATHS else None
        if counted:
            with BUSY_LOCK:
                BUSY["n"] += 1
                if kind:
                    BUSY_KINDS[kind] += 1
        try:
            if counted and updating(self, self.path.split("?")[0]):   # the update's flag went up while this request was read
                return None
            return route(self, *args)
        except CLIENT_LEFT:
            return None
        except Exception as e:  # noqa: BLE001  the server answers whatever a route does
            if type(e).__name__ == "NotBuiltYet":    # item 1100: a Mac-only step no route caught: the same words, never a fault (found by the class name, so no top-level import of clark is needed)
                LOG.warning("%s %s needs the Mac", self.command, self.path.split("?")[0])
                plat = importlib.import_module("clark.platform")
                return self.send(409, {"ok": False, "code": "needs_mac", "message": plat.refusal_words(e, plat.not_built_words())})
            LOG.exception("%s %s failed", self.command, self.path.split("?")[0])
            return self.send(500, error_body("server_error"))
        finally:
            if counted:
                with BUSY_LOCK:
                    BUSY["n"] -= 1
                    if kind:
                        BUSY_KINDS[kind] -= 1

    def do_OPTIONS(self):
        """Refuse every preflight: no cross-origin call is allowed. (creaite do_OPTIONS, BL-212)"""
        if self.headers_ok():
            self.send(403, error_body("not_allowed"))

    def do_GET(self):
        """GET /health, the page, the brand's pictures, and the API's GET routes (token first, also before a 404 under /api/)."""
        if not self.headers_ok():
            return None
        if not self.host_ok():
            return self.send(403, error_body("not_allowed"))
        if container_mode() and not local_peer(self.client_address[0]):      # item 427: with the container's 0.0.0.0 bind, the page and /health are for this machine only too
            note_refused_peer(self.client_address[0])
            return self.send(403, CONTAINER_REFUSED_PAGE, "text/html")
        self.follow_zone()
        route = self.path.split("?")[0]
        if route == "/health":
            return self.send(200, health_answer(self.headers.get(MARK_HEADER)))
        if route == "/":
            return self.run_route(page_route)
        if route in OPEN_GET_ROUTES:
            return self.run_route(open_route, route)
        if route == PREVIEW_ROUTE:
            return self.run_route(preview_page_route)
        if route == PAST_ROUTE:
            return self.run_route(past_page_route)
        if route.startswith(BRAND_PREFIX):
            parts = route[len(BRAND_PREFIX):].split("/")
            if len(parts) == 1 and parts[0] in BRAND_PICTURES:
                return self.run_route(brand_picture_route, parts[0])
            if len(parts) == 2 and BRAND_ID.fullmatch(parts[0]) and parts[1] in BRAND_PICTURES:        # #944: exactly two parts
                return self.run_route(brand_picture_route, parts[1], parts[0])
        api = GET_ROUTES.get(route)
        if api or route.startswith("/api/"):
            if not self.authorised() or updating(self, route):
                return None
            if api:
                return self.run_route(api)
        return self.send(404, error_body("not_found"))

    def post_route(self, route):
        """The function for a POST route, or None. /api/here has its own statement, outside POST_ROUTES. SetupHandler overrides this."""
        return here_route if route == HERE_ROUTE else POST_ROUTES.get(route)

    def do_POST(self):
        """POST /csp-report (its own local checks: a browser's report carries no token), then every other POST: the token,
        JSON only (415), a Content-Length (411), the body (400), then the route (404 if none)."""
        if not self.headers_ok():
            return None
        route = self.path.split("?")[0]
        if route == CSP_REPORT_ROUTE:
            return csp_report_route(self)
        if not self.authorised() or updating(self, route):
            return None
        self.follow_zone()
        if (self.headers.get("Content-Type") or "").split(";")[0].strip().lower() != "application/json":
            return self.send(415, error_body("send_json"))
        try:
            req = self.body()
        except LengthRequired:
            return self.send(411, error_body("length_required"))
        except TooLarge:
            sent = error_body("too_large")
            if self.path.split("?")[0] in ("/api/change", "/api/section-body"):
                sent["message"] = MESSAGES["change_too_large"]      # a section's content is the one thing that grows: say what to do (the code stays too_large)
            return self.send(400, sent)
        except ValueError:
            return self.send(400, error_body("bad_request"))
        api = self.post_route(route)
        if not api:
            return self.send(404, error_body("not_found"))
        return self.run_route(api, req)


# ===== Setup mode (item 836 step 4b): a second, very small server the launcher starts instead of the normal one when a check fails =====
# It has no database and none of clark's data routes: only the routes below, a stand-in page, /health and the heartbeat. All the logic is
# in `server.setup` (setup_mode.Setup); this server imports nothing from clark. design-836-setup-mode.md sections 1 to 4.
def setup_route(method, needs_empty_body=True):
    """A setup route: hands the request to the server's `setup` object, which answers (status, body), or None when that part is not
    wired (404). Nothing is trusted from the request: a POST body must be exactly {} (so a route cannot be given a path, a command or
    a setting). An answer that says "restart" stops this server once it is sent (as update_route does), and the launcher's ordinary
    start takes over."""
    def route(handler, *req):
        if needs_empty_body and req != ({},):
            return handler.send(400, error_body("bad_request"))
        setup = getattr(handler.server, "setup", None)
        answer = getattr(setup, method)() if setup is not None else None
        if answer is None:
            return handler.send(404, error_body("not_found"))
        status, body = answer
        try:
            handler.send(status, body)
        finally:           # setup's done is already true: the server stops even when the reply was dropped (else no window on the next start)
            if status == 200 and body.get("restart") is True:
                threading.Thread(target=handler.server.shutdown, daemon=True).start()
        return None
    return route


SETUP_GET_ROUTES = {"/api/setup/checks": setup_route("api_checks", needs_empty_body=False)}
SETUP_POST_ROUTES = {"/api/setup/folder": setup_route("api_folder"), "/api/setup/finish": setup_route("api_finish"),
                     "/api/setup/done": setup_route("api_done")}
SETUP_PAGES = ("/", "/setup")


def setup_page_route(handler):
    """GET / and GET /setup: the setup page with this run's token. It is the service's own (`setup.page_html()`); a service without one
    gets the stand-in (the normal server's own, one inline style and script)."""
    if page_load_is_ours(handler.headers, handler.server.server_port):
        mark_here()
    page = getattr(handler.server.setup, "page_html", None)
    return handler.send(200, with_boot(page() if page else placeholder_html()), "text/html")


class SetupHandler(Handler):
    """Setup mode's requests: the same gates as Handler (Host, Origin, token, JSON, length, body), but its own two route tables.
    It reads none of GET_ROUTES, POST_ROUTES, the page, preview, past, brand, open-file or report routes."""

    def do_GET(self):
        if not self.headers_ok():
            return None
        if not self.host_ok():
            return self.send(403, error_body("not_allowed"))
        if container_mode() and not local_peer(self.client_address[0]):
            note_refused_peer(self.client_address[0])
            return self.send(403, CONTAINER_REFUSED_PAGE, "text/html")
        self.follow_zone()
        route = self.path.split("?")[0]
        if route == "/health":
            return self.send(200, health_answer(self.headers.get(MARK_HEADER)))
        if route in SETUP_PAGES:
            return self.run_route(setup_page_route)
        if route.startswith("/api/"):
            if not self.authorised():
                return None
            api = SETUP_GET_ROUTES.get(route)
            if api:
                if self.headers.get("Content-Length") not in (None, "0") or self.headers.get("Transfer-Encoding"):
                    return self.send(400, error_body("bad_request"))
                return self.run_route(api)
        return self.send(404, error_body("not_found"))

    def do_POST(self):
        if not self.headers_ok():                  # sends the one 400; Handler.do_POST checks again, which sends nothing when they are fine
            return None
        if self.path.split("?")[0] == CSP_REPORT_ROUTE:          # no report endpoint: no log is set up before a data folder
            return self.send(404, error_body("not_found"))
        return super().do_POST()

    def post_route(self, route):
        return here_route if route == HERE_ROUTE else SETUP_POST_ROUTES.get(route)


class LocalServer(ThreadingHTTPServer):
    """The server, on 127.0.0.1 (in the container, on its own addresses, peers checked), without the reverse DNS lookup at bind. (creaite LocalServer, #83: http.server's
    server_bind calls socket.getfqdn(host), which can stall for 30 s on some Macs.) `data_for(code)` is the store's read
    of one project (None when there is none); `projects()` lists them as rows with a code and a name; `page_html()` gives
    the page's HTML (#35 supplies the bundle); `change(req)` and `undo(req)` (#65) answer POST /api/change and /api/undo
    with (status, body), each on a store of its own (None: those routes answer 503); `section_image(req)` (#96 R1) answers POST /api/section-image the same way; `sneak(req)` (#42) answers POST /api/sneak/read the same way, reading only; `publisher` answers the publish routes (#43); `use_cases(code)` reads one project's use cases (#163); `word_import(req)` and `word_export(req)` (#48) answer POST /api/word-import and /api/word-export the same way as `change` and `undo`; `activity(code, item)` reads one item's changes (#42)."""
    daemon_threads = True

    def __init__(self, server_address, handler=Handler, data_for=None, page_html=None, projects=None, change=None, undo=None,
                 publisher=None, movement=None, use_cases=None, safety=None, brand_picture=None, profile=None, logs=None, sneak=None, activity=None, word_import=None, word_export=None, excel_import=None, project_save=None,
                 draft_email=None, draft_email_sent=None, milestones=None, ask_folders=None, app_settings=None, ask=None, ai=None, ai_connect=None, updater=None,
                 people=None, people_undo=None, people_list=None, section_image=None, section_body=None, past=None, as_at=None, publication_mark=None, demo=None, brands=None, setup=None):
        if server_address[0] != HOST and not (container_mode() and server_address[0] == CONTAINER_BIND):
            raise ValueError(f"The server listens on {HOST} only, not {server_address[0]}")
        self.data_for = data_for or (lambda code: None)
        self.projects = projects or (lambda: [])
        self.change, self.undo, self.sneak = change, undo, sneak
        self.section_image = section_image    # changes.make_section_image (#96 R1); None: that route answers 503 saving_off
        self.section_body = section_body      # changes.make_section_body (#273); None: that route answers 503 saving_off
        self.word_import, self.word_export = word_import, word_export
        self.demo = demo                      # demo_seed.Demo (#731); None: no demo data on show
        self.excel_import, self.project_save = excel_import, project_save      # #444: the workbook import, a project's new and edit; None: those routes answer 503
        self.page_html = page_html or placeholder_html
        self.logs = logs                      # log_routes.Logs (#110); None: those routes answer not found
        self.publisher = publisher            # publish_flow.Publisher (#43); None until the launcher gives one
        self.movement = movement              # store.milestone_moves (#136): the owner-only Movement read; None: no such route
        self.activity = activity              # activity(code, item) -> the peek's Activity rows, or None (#42); None: no such route
        self.milestones = milestones          # milestone_feed.make_feed (#146): the Calendar's rows; None: no such route
        self.use_cases = use_cases            # use_cases(code) -> the project's use cases, or None (#163); None: no such route
        self.brand_picture = brand_picture or (lambda name, brand_id=None: None)     # (bytes, type) of a brand picture by name, or None (#98; page.brand_picture); None: 404
        self.profile = profile                # profile_settings.Profile (#180): the name and email in Settings; None: those routes answer not found
        self.draft_email = draft_email        # #50: builds a Draft email for a request, read only; None until the launcher gives one
        self.draft_email_sent = draft_email_sent      # #50: records "I sent it" (ids, mode, day; no text); None until the launcher gives one
        self.safety = safety                  # safety.Safety (#111): the backup list, Preview and Restore; None: those routes answer 503
        self.ask_folders = ask_folders        # ask_folders.AskFolders (#47); None: the folder routes answer 404
        self.ai_connect = ai_connect          # ai_connect.AiConnect (#54): Settings › AI; None: its routes answer 404
        self.app_settings = app_settings      # app_settings.AppSettings (#47): the ask switch; None: its route answers 404
        self.people, self.people_undo, self.people_list = people, people_undo, people_list      # #115: the person writers, their Undo and the list; None: saving off (503) or not found (404)
        self.ask = ask                        # ask_service.AskService (#47): questions; None: the ask routes answer 404
        self.updater = updater                # updater.Updater: Settings › Version and updates; None: those routes answer 503
        self.ai = ai                          # ai_service.AiService (#72): AI suggestions, on the ask service's provider; None: 404
        self.past = past                      # past_reports.PastReports (#443): the Published reports list and Open; None: those routes answer 404
        self.publication_mark = publication_mark   # changes.make_publication_mark (#345): archive or restore one publication; None: saving off (503)
        self.setup = setup                    # setup_mode.Setup (item 836): given only to a SetupHandler server; None: the normal server
        self.brands = brands                  # BrandLibrary (#944), or any object with listing/review/install/remove/undo; None: those routes answer 503
        self.as_at = as_at                    # as_at.AsAt (#349): the dashboard as at a day, rebuilt from the history, read only; None: 404
        super().__init__(server_address, handler)

    def server_bind(self):
        """Bind as TCPServer does, then name the server after its own address instead of looking the name up."""
        socketserver.TCPServer.server_bind(self)
        host, port = self.server_address[:2]
        self.server_name = host
        self.server_port = port


# What a person reads when the address is taken: the cause, and the one thing to do. The launcher (__main__.py prints this line;
# launch.py says the same cause in Terminal words) and START-HERE agree with it. No port number and no other command here: closing the
# other window or program is the next step.
PORT_TAKEN = ("Nothing was started: clark is already open in another window, or another program is using the connection it needs. "
              "Close the other window or program, then start clark again.")


def port_setting():
    """The port: CLARK_PORT, or 8766."""
    return int(os.environ.get("CLARK_PORT") or DEFAULT_PORT)


def wait_for_jobs(limit=JOB_WAIT_LIMIT, sleep=time.sleep):
    """After the loop has stopped, wait (at most `limit` seconds) until no POST route is running."""
    waited = 0.0
    while busy() and waited < limit:
        sleep(0.05)
        waited += 0.05


def serve(port=None, data_for=None, page_html=None, projects=None, out=None, err=None, change=None, undo=None,
          publisher=None, movement=None, use_cases=None, safety=None, brand_picture=None, profile=None, logs=None, sneak=None, activity=None, word_import=None, word_export=None, excel_import=None, project_save=None,
          draft_email=None, draft_email_sent=None, milestones=None, ask_folders=None, app_settings=None, ask=None, ai=None, ai_connect=None, updater=None,
          people=None, people_undo=None, people_list=None, section_image=None, section_body=None, past=None, as_at=None, publication_mark=None, demo=None, brands=None, setup=None):
    """Start the server on 127.0.0.1 (in the container, on its own addresses: see container_mode) and serve until stopped. A port in use is one plain line and exit code 1."""
    out, err = out or sys.stdout, err or sys.stderr
    if brands is None and BRAND_PATHS["root"] is not None:
        brands = BrandLibrary(BRAND_PATHS["root"], BRAND_PATHS["data"])      # #944: the real library, once the launcher has said where
    port = port_setting() if port is None else port
    try:
        httpd = LocalServer((CONTAINER_BIND if container_mode() else HOST, port), SetupHandler if setup is not None else Handler, data_for=data_for, page_html=page_html, projects=projects, change=change, undo=undo,
                            publisher=publisher, movement=movement, use_cases=use_cases, safety=safety, brand_picture=brand_picture, profile=profile, logs=logs, sneak=sneak, activity=activity,
                            word_import=word_import, word_export=word_export, excel_import=excel_import, project_save=project_save, draft_email=draft_email, draft_email_sent=draft_email_sent,
                            milestones=milestones, ask_folders=ask_folders, app_settings=app_settings, ask=ask, ai=ai, ai_connect=ai_connect, updater=updater,
                            people=people, people_undo=people_undo, people_list=people_list, section_image=section_image, section_body=section_body, past=past, as_at=as_at, publication_mark=publication_mark, demo=demo, brands=brands, setup=setup)
    except OSError as e:
        if e.errno == errno.EADDRINUSE:
            print(PORT_TAKEN, file=err)
            return 1
        raise
    print(f"Open http://{HOST}:{httpd.server_port}/ to use clark. Leave this window open; press Ctrl+C to stop.",
          file=out, flush=True)
    if IDLE is not None:                  # a launcher-started run: stop when no window is left (never while a job runs)
        threading.Thread(target=IDLE.watch, args=(httpd.shutdown, busy, lambda text: print(text, file=out, flush=True)),
                         daemon=True).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        wait_for_jobs()                   # a POST that began just before the stop finishes first (its write is not cut off)
        httpd.server_close()
        REFUSED.flush()                   # the refused-request window still open is written now (#260): a last burst before exit is not lost
    return 0


if __name__ == "__main__":
    sys.exit(serve())
