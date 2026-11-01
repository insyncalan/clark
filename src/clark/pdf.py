"""PDF export: a published page file turned into a PDF by Chrome's DevTools print (Page.printToPDF).

No library is added: headless Chrome prints the finished, self-contained page (nothing is fetched; any address is refused).
Pure parts: print_css(), stack_script(), print_params() and chrome_args(). The one part that runs a program: make_pdf(), which
starts one Chrome child, always stops it, and removes its throwaway profile folder (retrying, as Chrome can still be writing
into it as it exits). On Mac and Linux Chrome is driven over a pipe (--remote-debugging-pipe: two inherited file descriptors,
no network port at all); where pipes cannot be passed (Windows) it is driven over a port on 127.0.0.1 for the seconds a print takes.
The page file has three tabs and shows one at a time, so the print stacks them first (stack_script): each tab is opened in
turn through the page's own navigation and its content is copied under a heading, with the live page hidden by print_css.
The Publish dialog, the checks of the PDF's text and the name-clash questions are in publish_pdf.py; this module gives them the PDF.
Standard library only, Python 3.9.
"""
import base64
import hashlib
import json
import os
import re
import select
import shutil
import socket
import struct
import tempfile
import time
from html import escape as html_escape
from pathlib import Path

from clark import platform

WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
TIMEOUT = 60                       # seconds Chrome is given for one page
KEYCHAIN_FLAGS = ("--use-mock-keychain", "--password-store=basic")
MAC_CHROME_PATHS = ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge")
NO_CHROME = "A PDF needs Google Chrome, and clark could not find it on this computer. Install Chrome, or leave the PDF box unticked."
FAILED = "Chrome could not make the PDF. Try again; if it keeps happening, leave the PDF box unticked."
TOO_SLOW = "Chrome took too long to make the PDF. Try again; if it keeps happening, leave the PDF box unticked."
ORIENTATIONS = ("portrait", "landscape")


def stop_child(proc):
    """Make sure `proc` (a platform.Child) and anything it started in its process group are gone."""
    group = getattr(os, "killpg", None)
    if proc.poll() is None:
        try:
            group(proc.pid, 15)
        except (OSError, TypeError):
            proc.terminate()
        try:
            proc.wait(5)
        except Exception:  # noqa: BLE001  (did not stop when asked)
            try:
                group(proc.pid, 9)
            except (OSError, TypeError):
                proc.kill()
    try:
        proc.wait(5)
    except Exception:  # noqa: BLE001
        pass
    try:
        group(proc.pid, 9)             # any helper process the program left in the group
    except (OSError, TypeError):
        pass


class PdfError(Exception):
    """A failure with a message that is already in plain words for the person."""


def find_chrome(environ=None, which=shutil.which, exists=os.path.exists):
    """The Chrome program for printing, or None: CLARK_CHROME, then google-chrome / chromium / chromium-browser on the PATH,
    then the Chrome (or Edge) app on a Mac."""
    environ = os.environ if environ is None else environ
    named = environ.get("CLARK_CHROME")
    if named and exists(named):
        return named
    for name in ("google-chrome", "chromium", "chromium-browser"):
        found = which(name)
        if found:
            return found
    return next((p for p in MAC_CHROME_PATHS if exists(p)), None)


PRINT_RULES = (
    # light only: the page is drawn with its light colours whatever the computer prefers
    ":root{color-scheme:light}"
    "html,body{-webkit-print-color-adjust:exact;print-color-adjust:exact;background:#fff}"
    # no controls: the live page (top bar, tabs, buttons, the contents lines) is not printed; the stacked copy is
    "body.print-stacked #app{display:none!important}"
    ".top,.tabs,.toc,.pubbar,nav,dialog,input,select,textarea,.filters,.sec-tools,.add,.wbar,.fbar,.factive,.newb{display:none!important}"
    "button,[role=button]{border:0!important;background:none!important;box-shadow:none!important;padding:0!important;"
    "min-height:0!important;cursor:default!important;color:inherit!important;font:inherit!important}"
    # the tabs stacked: each starts on a new page, under its own heading
    "#print-stack{display:block}"
    ".print-tab+.print-tab{break-before:page}"
    ".print-tab-title{margin:0 0 8px;font-size:15px;font-weight:400;color:#555;border-bottom:1px solid #ccc;padding-bottom:4px}"
    "main{max-width:none!important;padding:0!important}"
    ".frame{box-shadow:none!important;border:0!important;padding:0!important;background:#fff!important}"
    # sections kept whole: nothing is cut across two pages if it fits on one; a long table repeats its heading
    ".sec,article,.tile,.fig,.frame>section,figure,blockquote,tr,li,h1,h2,h3{break-inside:avoid}"
    "h1,h2,h3{break-after:avoid}"
    "thead{display:table-header-group}"
    "a{color:inherit;text-decoration:none}"
)


def print_css(orientation="portrait"):
    """The print rules added to the page before it is printed: A4, the chosen orientation, backgrounds kept, the tabs stacked,
    no controls, sections kept whole, light colours only."""
    if orientation not in ORIENTATIONS:
        raise ValueError("orientation must be 'portrait' or 'landscape'")
    return "@page{size:A4 %s;margin:12mm 12mm 16mm}@media print{%s}" % (orientation, PRINT_RULES)


def with_print_css(html, orientation="portrait"):
    """`html` (text) with the print rules in a style tag at the end of its head (or at the start if it has none), and its
    <html> tag set to the light theme."""
    tag = "<style>%s</style>" % print_css(orientation)
    html = re.sub(r"(<html\b[^>]*?)\s+data-theme\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", r"\1", html, count=1, flags=re.I)
    html = re.sub(r"<html\b", '<html data-theme="light"', html, count=1, flags=re.I)
    at = html.lower().rfind("</head>")
    return tag + html if at < 0 else html[:at] + tag + html[at:]


def stack_script():
    """The script that stacks the page's tabs for printing, run in the page once it has loaded. It opens each tab in turn with
    its own tab button, copies what the tab draws into a section under the tab's name, then marks the page printed-stacked
    (print_css hides the live page). It returns the number of tabs stacked (0 when the page has no tabs: then it is printed as it is)."""
    return """(async function(){
  var wait=function(ms){return new Promise(function(r){setTimeout(r,ms)})};
  var frame=function(){return new Promise(function(r){requestAnimationFrame(function(){requestAnimationFrame(r)})})};
  var tabs=[].map.call(document.querySelectorAll('.tabs .tab[data-view]'),function(b){return [b.getAttribute('data-view'),b.textContent.trim()]});
  var go=function(v){var b=document.querySelector('.tabs .tab[data-view="'+v+'"]'); if(b) b.click();};
  var main=document.getElementById('main');
  if(!tabs.length||!main) return 0;
  var was=document.querySelector('.tab[aria-selected=true]'); was=was&&was.getAttribute('data-view');
  var box=document.createElement('div'); box.id='print-stack';
  for(var i=0;i<tabs.length;i++){
    go(tabs[i][0]); await frame(); await wait(120);
    var sec=document.createElement('section'); sec.className='print-tab';
    var h=document.createElement('h2'); h.className='print-tab-title'; h.textContent=tabs[i][1];
    var body=document.createElement('div'); body.innerHTML=main.innerHTML;
    sec.appendChild(h); sec.appendChild(body); box.appendChild(sec);
  }
  if(was) go(was);
  document.body.appendChild(box); document.body.classList.add('print-stacked');
  return tabs.length;
})()"""


def chrome_args(chrome, profile, page, out):
    """The command line that prints `page` (a file) to `out`: headless, both keychain flags, A4 and backgrounds from the
    print rules, no header or footer from Chrome, no network (every host name is refused), a profile folder of its own."""
    return [str(chrome), "--headless=new", "--disable-gpu", "--no-first-run",
            "--no-default-browser-check", f"--user-data-dir={profile}", *KEYCHAIN_FLAGS,
            "--host-resolver-rules=MAP * ~NOTFOUND", "--disable-extensions", "--no-pdf-header-footer",
            "--run-all-compositor-stages-before-draw", "--virtual-time-budget=5000",
            f"--print-to-pdf={out}", Path(page).resolve().as_uri()]


def remove_folder(folder, tries=10, pause=0.2):
    """Remove `folder`, trying again when Chrome is still writing into it ("Directory not empty"). Never raises."""
    for i in range(tries):
        try:
            shutil.rmtree(folder)
            return True
        except FileNotFoundError:
            return True
        except OSError:
            time.sleep(pause)
    shutil.rmtree(folder, ignore_errors=True)
    return not os.path.exists(folder)


class _CdpUnavailable(Exception):
    """The DevTools route could not start (the caller then falls back to the plain print flag)."""


class _Socket:
    """A minimal client-side WebSocket (RFC 6455) for talking JSON to Chrome's DevTools on 127.0.0.1."""

    def __init__(self, port, path, deadline):
        self.deadline = deadline
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=5)
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall(("GET %s HTTP/1.1\r\nHost: 127.0.0.1:%d\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                           "Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n" % (path, port, key)).encode())
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise _CdpUnavailable("closed during handshake")
            head += chunk
            if len(head) > 65536:
                raise _CdpUnavailable("odd handshake")
        head, self.buffer = head.split(b"\r\n\r\n", 1)
        want = base64.b64encode(hashlib.sha1((key + WS_GUID).encode()).digest())
        if b" 101 " not in head.split(b"\r\n")[0] + b" " or want not in head:
            raise _CdpUnavailable("handshake refused")

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass

    def _take(self, n):
        while len(self.buffer) < n:
            left = self.deadline - time.monotonic()
            if left <= 0:
                raise socket.timeout()
            self.sock.settimeout(left)
            chunk = self.sock.recv(1 << 16)
            if not chunk:
                raise ConnectionError("closed")
            self.buffer += chunk
        got, self.buffer = self.buffer[:n], self.buffer[n:]
        return got

    def _send(self, opcode, payload):
        head = bytes([0x80 | opcode])
        n = len(payload)
        if n < 126:
            head += bytes([0x80 | n])
        elif n < 65536:
            head += bytes([0x80 | 126]) + struct.pack(">H", n)
        else:
            head += bytes([0x80 | 127]) + struct.pack(">Q", n)
        mask = os.urandom(4)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload)) if n < 4096 else _xor(payload, mask)
        self.sock.settimeout(max(self.deadline - time.monotonic(), 0.1))
        self.sock.sendall(head + mask + masked)

    def send_json(self, obj):
        self._send(1, json.dumps(obj).encode())

    def recv_json(self):
        message, kind = b"", None
        while True:
            b0, b1 = self._take(2)
            n = b1 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._take(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._take(8))[0]
            data = self._take(n)           # servers do not mask
            op = b0 & 0x0F
            if op == 9:
                self._send(10, data)
            elif op == 8:
                raise ConnectionError("closed")
            elif op in (1, 2, 0):
                if op:
                    kind = op
                message += data
                if b0 & 0x80 and kind:
                    return json.loads(message.decode())


def _xor(payload, mask):
    pad = (mask * (len(payload) // 4 + 1))[:len(payload)]
    return (int.from_bytes(payload, "big") ^ int.from_bytes(pad, "big")).to_bytes(len(payload), "big")


class _Session:
    """DevTools calls over one WebSocket: send a command, read until its answer (events are kept as they pass)."""

    def __init__(self, ws):
        self.ws, self.next_id, self.events = ws, 0, []

    def call(self, method, params=None, session=None):
        self.next_id += 1
        msg = {"id": self.next_id, "method": method, "params": params or {}}
        if session:
            msg["sessionId"] = session
        self.ws.send_json(msg)
        while True:
            got = self.ws.recv_json()
            if got.get("id") == self.next_id:
                if "error" in got:
                    raise PdfError(FAILED)
                return got.get("result", {})
            self.events.append(got)

    def wait_event(self, name, session):
        while True:
            for i, e in enumerate(self.events):
                if e.get("method") == name and e.get("sessionId") == session:
                    del self.events[i]
                    return
            self.events.append(self.ws.recv_json())


def footer_template(footer_left=""):
    """The footer Chrome prints on every page: `footer_left` (plain text, HTML-escaped here) on the left, and
    "Page X of Y" on the right, in small Arial."""
    left = html_escape(str(footer_left or ""), quote=True)
    return ('<div style="box-sizing:border-box;width:100%%;padding:0 12mm;font:8px Arial,Helvetica,sans-serif;color:#444;'
            'display:flex;justify-content:space-between">'
            '<span>%s</span><span>Page <span class="pageNumber"></span> of <span class="totalPages"></span></span></div>' % left)


def print_params(orientation="portrait", footer_left=""):
    """The Page.printToPDF options: A4 (8.27 x 11.69 in), the chosen orientation, backgrounds on, the footer above."""
    if orientation not in ORIENTATIONS:
        raise ValueError("orientation must be 'portrait' or 'landscape'")
    return {"landscape": orientation == "landscape", "paperWidth": 8.27, "paperHeight": 11.69, "printBackground": True,
            "displayHeaderFooter": True, "headerTemplate": "<span></span>", "footerTemplate": footer_template(footer_left),
            "preferCSSPageSize": False, "marginTop": 0.47, "marginLeft": 0.47, "marginRight": 0.47, "marginBottom": 0.63}


def _wait_for_port(profile, proc, deadline):
    """(port, path) from the DevToolsActivePort file Chrome writes in its profile. TOO_SLOW at the deadline; _CdpUnavailable
    if Chrome has already gone."""
    marker = Path(profile) / "DevToolsActivePort"
    while True:
        try:
            lines = marker.read_text(encoding="utf-8").split("\n")
            if len(lines) >= 2 and lines[0].strip().isdigit() and lines[1].strip():
                return int(lines[0]), lines[1].strip()
        except (OSError, ValueError):
            pass
        if proc.poll() is not None:
            raise _CdpUnavailable("Chrome exited")
        if time.monotonic() > deadline:
            raise PdfError(TOO_SLOW)
        time.sleep(0.05)


class _Pipe:
    """Chrome's --remote-debugging-pipe: JSON messages, each ended by a NUL byte, written to one file descriptor and read from
    another. No port is opened. Same two calls as _Socket (send_json, recv_json) so one session class serves both."""

    def __init__(self, to_chrome, from_chrome, deadline):
        self.out, self.inp, self.deadline, self.buffer = to_chrome, from_chrome, deadline, b""

    def close(self):
        for fd in (self.out, self.inp):
            try:
                os.close(fd)
            except OSError:
                pass

    def send_json(self, obj):
        data = json.dumps(obj).encode() + b"\0"
        while data:
            left = self.deadline - time.monotonic()
            if left <= 0 or not select.select([], [self.out], [], left)[1]:
                raise socket.timeout()
            try:
                n = os.write(self.out, data)
            except BrokenPipeError as e:
                raise ConnectionError("closed") from e
            data = data[n:]

    def recv_json(self):
        while b"\0" not in self.buffer:
            left = self.deadline - time.monotonic()
            if left <= 0 or not select.select([self.inp], [], [], left)[0]:
                raise socket.timeout()
            chunk = os.read(self.inp, 1 << 16)
            if not chunk:
                raise ConnectionError("closed")
            self.buffer += chunk
        one, self.buffer = self.buffer.split(b"\0", 1)
        return json.loads(one.decode())


def _print_over(ws, url, params, deadline, stack=True):
    """Open `url` in a new tab, wait for it to load, stack its tabs (if `stack`), and return the PDF bytes from Page.printToPDF."""
    try:
        s = _Session(ws)
        target = s.call("Target.createTarget", {"url": "about:blank"})["targetId"]
        session = s.call("Target.attachToTarget", {"targetId": target, "flatten": True})["sessionId"]
        s.call("Page.enable", session=session)
        s.call("Page.setBypassCSP", {"enabled": True}, session=session)      # the page's policy would refuse the print rules and script (a copy nobody else sees)
        s.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": "light"}]}, session=session)
        s.call("Page.navigate", {"url": url}, session=session)
        s.wait_event("Page.loadEventFired", session)
        s.call("Runtime.evaluate", {"expression": "document.fonts ? document.fonts.ready.then(() => 1) : 1",
                                    "awaitPromise": True}, session=session)
        if stack:
            s.call("Runtime.evaluate", {"expression": stack_script(), "awaitPromise": True}, session=session)
        data = s.call("Page.printToPDF", params, session=session).get("data")
        if not data:
            raise PdfError(FAILED)
        return base64.b64decode(data)
    except socket.timeout as e:
        raise PdfError(TOO_SLOW) from e
    except ConnectionError as e:
        raise _CdpUnavailable(str(e)) from e
    except (OSError, ValueError, KeyError) as e:
        raise PdfError(FAILED) from e
    finally:
        ws.close()


def _print_over_port(port, path, url, params, deadline, stack=True):
    try:
        ws = _Socket(port, path, deadline)
    except (OSError, _CdpUnavailable) as e:
        if isinstance(e, socket.timeout):
            raise PdfError(TOO_SLOW) from e
        raise _CdpUnavailable(str(e)) from e
    return _print_over(ws, url, params, deadline, stack)


def _devtools_args(chrome, profile, pipe=True):
    """Headless Chrome for DevTools: over a pipe (no port), or, where that cannot be, a port of its own choosing (written to the
    profile's DevToolsActivePort file)."""
    return [str(chrome), "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
            f"--user-data-dir={profile}", *KEYCHAIN_FLAGS, "--host-resolver-rules=MAP * ~NOTFOUND",
            "--disable-extensions", "--remote-debugging-pipe" if pipe else "--remote-debugging-port=0", "about:blank"]


def _start(args, popen, **more):
    """Start Chrome (platform.start_child, or the `popen` a test gives instead); NO_CHROME if it cannot be started."""
    try:
        return (popen or platform.start_child)(args, **more)
    except OSError as e:
        raise PdfError(NO_CHROME) from e


def _high(fd):
    """A copy of `fd` numbered 10 or more, so that placing a pipe on 3 and 4 in the child can never land on top of another."""
    import fcntl
    new = fcntl.fcntl(fd, fcntl.F_DUPFD_CLOEXEC, 10)
    os.close(fd)
    return new


def _start_piped(chrome, profile, popen):
    """Start Chrome with its DevTools pipe: Chrome reads commands on file descriptor 3 and writes answers on 4. Returns
    (process, (to_chrome, from_chrome)). The start is platform.start_child, which places the two ends on 3 and 4 for the child
    (os.posix_spawn: no preexec_fn). A test's stand-in `popen` is given the child's two ends as `pipe`."""
    cmd_r, cmd_w = os.pipe()
    ans_r, ans_w = os.pipe()
    cmd_r, ans_w, cmd_w, ans_r = _high(cmd_r), _high(ans_w), _high(cmd_w), _high(ans_r)
    args = _devtools_args(chrome, profile, True)
    try:
        proc = _start(args, popen, pipe=(cmd_r, ans_w))
    except BaseException:
        for fd in (cmd_w, ans_r):
            os.close(fd)
        raise
    finally:
        for fd in (cmd_r, ans_w):                      # the child has its ends; the parent keeps the other two
            os.close(fd)
    return proc, (cmd_w, ans_r)


CLEAN_NAME = "clark"            # the only Creator and Producer a PDF made here carries
CLEAN_TITLE = "Report"          # the Title when the page has none
CANNOT_CLEAN = "The PDF could not be made safe to share, so it was not made. Leave the PDF box unticked and publish again."


def title_of(html_text):
    """The page's <title> as plain text (tags dropped, entities read), or CLEAN_TITLE."""
    import html as _html
    m = re.search(r"<title[^>]*>(.*?)</title>", html_text, re.S | re.I)
    text = " ".join(_html.unescape(re.sub(r"<[^>]*>", "", m.group(1))).split()) if m else ""
    return text[:200] or CLEAN_TITLE


def _pdf_string(text):
    """`text` as a PDF string: plain ASCII in brackets, anything else as UTF-16 in hex."""
    if all(32 <= ord(c) < 127 for c in text):
        return "(" + text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") + ")"
    return "<FEFF" + text.encode("utf-16-be").hex().upper() + ">"


def scrub(data, title=CLEAN_TITLE):
    """`data` (a PDF as Chrome writes it: one classic cross-reference table) with its details made neutral: the Info
    dictionary is replaced by a new one that holds only Title, Creator and Producer ("clark"), the trailer keeps only Size, Root
    and Info (no ID), and any XMP metadata stream is emptied and no longer pointed at. Every object is copied byte for byte
    otherwise, and the cross-reference table is written again. Raises PdfError if the file is not of that shape."""
    try:
        start = int(re.findall(rb"startxref\s+(\d+)", data)[-1])
        head = re.compile(rb"xref\r?\n0 (\d+)\r?\n").match(data, start)
        count = int(head.group(1))
        rows = [data[head.end() + 20 * i: head.end() + 20 * (i + 1)] for i in range(count)]
        trailer = data[head.end() + 20 * count:]
        size = int(re.search(rb"/Size\s+(\d+)", trailer).group(1))
        root = int(re.search(rb"/Root\s+(\d+)\s+0\s+R", trailer).group(1))
        info = re.search(rb"/Info\s+(\d+)\s+0\s+R", trailer)
        if re.search(rb"/(?:Encrypt|Prev|XRefStm)\b", trailer):          # encrypted or updated files cannot be rewritten whole
            raise ValueError("a trailer this cannot rewrite")
        if size != count or any(len(r) != 20 or not re.fullmatch(rb"\d{10} \d{5} [nf][ \r\n]{2}", r) for r in rows):
            raise ValueError("an unusual cross-reference table")
        offsets = {i: int(r[:10]) for i, r in enumerate(rows) if r[17:18] == b"n" and i}
        order = sorted(offsets.items(), key=lambda kv: kv[1])
        first = order[0][1]
        ends = [o for _, o in order[1:]] + [start]
        body = {}
        for (num, off), end in zip(order, ends):
            chunk = data[off:end]
            if not chunk.startswith(b"%d 0 obj" % num) or not chunk.rstrip().endswith(b"endobj"):
                raise ValueError("an object out of place")
            body[num] = chunk
        gone = set()
        for num, chunk in body.items():
            dictionary = chunk.split(b"stream", 1)[0]
            if re.search(rb"/Type\s*/Metadata\b|/Subtype\s*/XML\b", dictionary):
                gone.add(num)
        for num in gone:
            body[num] = b"%d 0 obj\nnull\nendobj\n" % num
        for num, chunk in list(body.items()):
            dictionary, mark, rest = chunk.partition(b"stream")
            cleaned = re.sub(rb"/Metadata\s+\d+\s+0\s+R", b"", dictionary)
            if cleaned != dictionary:
                body[num] = cleaned + mark + rest
        info_num = int(info.group(1)) if info else size
        body[info_num] = ("%d 0 obj\n<</Title %s/Creator (%s)/Producer (%s)>>\nendobj\n" % (
            info_num, _pdf_string(title), CLEAN_NAME, CLEAN_NAME)).encode("ascii")
        total = max(size, info_num + 1)
        out, at = [data[:first]], len(data[:first])
        table = [b"0000000000 65535 f \n"] + [b"0000000000 00000 f \n"] * (total - 1)
        for num in sorted(body):
            table[num] = b"%010d 00000 n \n" % at
            out.append(body[num])
            at += len(body[num])
        out.append(b"xref\n0 %d\n" % total + b"".join(table))
        out.append(b"trailer\n<</Size %d\n/Root %d 0 R\n/Info %d 0 R>>\nstartxref\n%d\n%%%%EOF\n" % (total, root, info_num, at))
        return b"".join(out)
    except (AttributeError, IndexError, ValueError, KeyError, UnicodeError, MemoryError, RecursionError) as e:
        raise PdfError(CANNOT_CLEAN) from e


def make_pdf(page, out, orientation="portrait", chrome=None, timeout=TIMEOUT, popen=None, footer_left="", stack=True):
    """Print the page file `page` to the PDF file `out` (A4, backgrounds on, a footer with `footer_left` on the left, which
    is optional, and "Page X of Y" on the right). Returns `out`. Raises PdfError in plain words if Chrome is missing, runs
    too long, or leaves no PDF. The page file itself is not changed (a copy with the print rules is printed). Chrome is
    driven over DevTools (Page.printToPDF), by a pipe where the system can pass one and by a port on 127.0.0.1 elsewhere;
    only if that route cannot start is the plain print flag used (no footer, no stacking).
    One Chrome child at a time, always stopped; its profile folder is always removed. `stack` stacks the page's tabs."""
    chrome = chrome or find_chrome()
    if not chrome:
        raise PdfError(NO_CHROME)
    params = print_params(orientation, footer_left)
    out = Path(out)
    work = tempfile.mkdtemp(prefix="clark-pdf-")
    try:
        copy = Path(work) / "page.html"
        copy.write_text(with_print_css(Path(page).read_text(encoding="utf-8"), orientation), encoding="utf-8")
        deadline = time.monotonic() + timeout
        profile = Path(work) / "profile"
        proc, ends = None, None
        try:
            if os.name == "posix":
                proc, ends = _start_piped(chrome, profile, popen)
                data = _print_over(_Pipe(ends[0], ends[1], deadline), copy.resolve().as_uri(), params, deadline, stack)
            else:
                proc = _start(_devtools_args(chrome, profile, False), popen)
                port, path = _wait_for_port(profile, proc, deadline)
                data = _print_over_port(port, path, copy.resolve().as_uri(), params, deadline, stack)
        except _CdpUnavailable:
            data = None
        finally:
            if proc is not None:
                stop_child(proc)
        if data is None:
            data = _print_with_flag(chrome, work, copy, popen, max(deadline - time.monotonic(), 1), footer_left)
        if not data.startswith(b"%PDF"):
            raise PdfError(FAILED)
        data = scrub(data, title_of(Path(page).read_text(encoding="utf-8")))          # nothing about this computer or its browser
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        return out
    finally:
        remove_folder(work)


def footer_html(footer_left=""):
    """The fallback's footer: a line fixed to the foot of every printed page, with `footer_left` (HTML-escaped here). The flag
    cannot take a footer of its own, so it is part of the page that is printed."""
    return ('<div style="position:fixed;left:0;bottom:0;font:8px Arial,Helvetica,sans-serif;color:#444">%s</div>'
            % html_escape(str(footer_left or ""), quote=True))


def _print_with_flag(chrome, work, copy, popen, timeout, footer_left=""):
    """The fallback: Chrome's own --print-to-pdf flag. It has no footer of its own, so `footer_left` ("Publication N · date")
    is added to a copy of the page, on every printed page; there is no page count. Returns the PDF bytes."""
    made = Path(work) / "page.pdf"
    if footer_left:
        text = copy.read_text(encoding="utf-8")
        at = text.lower().rfind("</body>")
        tag = footer_html(footer_left)
        copy = Path(work) / "page-flag.html"
        copy.write_text(tag + text if at < 0 else text[:at] + tag + text[at:], encoding="utf-8")
    proc = _start(chrome_args(chrome, Path(work) / "profile2", copy, made), popen)
    try:
        proc.wait(timeout)
    except TimeoutError as e:
        raise PdfError(TOO_SLOW) from e
    finally:
        stop_child(proc)
    if proc.returncode != 0 or not made.is_file():
        raise PdfError(FAILED)
    return made.read_bytes()
