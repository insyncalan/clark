"""Run the prototype's click-through test (selftest.js) in headless Chrome and print the result.

Usage: python3 run_selftest.py [--all]   (--all prints the passing checks too)
The phone-width checks ask this runner for a 390 px window (Emulation.setDeviceMetricsOverride); run another way, they are skipped.
The same goes for the other widths (title SELFTEST-W:1100) and for the reduced-motion setting (title SELFTEST-REDUCE), added with the UX sweep fixes.
Needs Google Chrome and an internet connection (fonts and the Excel tools load from the web). It writes one temporary page
beside index.html while it runs and removes it after; the browser profile is a fresh temporary folder each time.
The test runs in real time, driven over Chrome's DevTools pipe (standard library only). Virtual time was faster but raced the
browser database, which opens in real time, so about one run in four started before the demo data had loaded.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import build_css

HERE = Path(__file__).resolve().parent
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
TIMEOUT = 300
ERRORS = ('<script>window.__e=[];addEventListener("error",e=>__e.push((e.message||"")+" @"+(e.filename||"").split("/").pop()+":"+e.lineno));'
          'addEventListener("unhandledrejection",e=>__e.push("rejected: "+(e.reason&&e.reason.message||e.reason)));</script>')


class Pipe:
    """Chrome's --remote-debugging-pipe: JSON messages ended by a NUL byte, Chrome reads fd 3 and writes fd 4."""
    def __init__(self, w, r):
        self.w, self.r, self.n, self.buf = w, r, 0, b""

    def call(self, method, params=None, session=None):
        self.n += 1
        msg = {"id": self.n, "method": method, "params": params or {}}
        if session:
            msg["sessionId"] = session
        os.write(self.w, json.dumps(msg).encode() + b"\0")
        while True:
            while b"\0" not in self.buf:
                chunk = os.read(self.r, 1 << 16)
                if not chunk:
                    raise RuntimeError("Chrome closed the pipe")
                self.buf += chunk
            raw, self.buf = self.buf.split(b"\0", 1)
            m = json.loads(raw)
            if m.get("id") == self.n:
                if "error" in m:
                    raise RuntimeError(m["error"])
                return m["result"]

    def js(self, expr, session):
        return self.call("Runtime.evaluate", {"expression": expr, "returnByValue": True}, session)["result"].get("value")


def main():
    build_css.main()
    page = (HERE / "index.html").read_text(encoding="utf-8").replace("<head>", "<head>" + ERRORS, 1)
    test = (HERE / "selftest.js").read_text(encoding="utf-8")
    i = page.rindex("</body>")
    tmp = HERE / "selftest-run.html"
    tmp.write_text(page[:i] + "<script>" + test + "</script>" + page[i:], encoding="utf-8")
    to_r, to_w = os.pipe()
    from_r, from_w = os.pipe()

    def child_fds():   # move both ends clear of 3 and 4 first: os.pipe() may have used them, and dup2 onto itself keeps close-on-exec
        a, b = os.dup2(to_r, 100), os.dup2(from_w, 101)
        os.dup2(a, 3)
        os.dup2(b, 4)

    try:
        with tempfile.TemporaryDirectory() as prof:
            proc = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", "--allow-file-access-from-files", f"--user-data-dir={prof}",
                                     "--use-mock-keychain", "--password-store=basic",   # no macOS Keychain prompt ("Keychain Not Found")
                                     "--window-size=1440,1000", "--remote-debugging-pipe", "about:blank"],
                                    preexec_fn=child_fds, close_fds=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:   # from here on, whatever happens (an error, the timeout, Ctrl-C) Chrome is killed and waited for
                os.close(to_r)
                os.close(from_w)
                cdp = Pipe(to_w, from_r)
                tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
                sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
                cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, sid)
                cdp.call("Browser.setDownloadBehavior", {"behavior": "deny"})   # the publish and export tests would otherwise save a copy into ~/Downloads on every run
                cdp.call("Page.navigate", {"url": tmp.as_uri()}, sid)
                t0, text = time.time(), None
                while time.time() - t0 < TIMEOUT and not text:
                    time.sleep(0.5)
                    text = cdp.js("document.title==='SELFTEST-DONE'?document.getElementById('selftest').textContent:null", sid)
                    title = text or cdp.js("document.title", sid)
                    # the phone checks ask for a 390 px window (the page cannot resize itself), and give it back when done
                    if title == "SELFTEST-PHONE":
                        cdp.call("Emulation.setDeviceMetricsOverride", {"width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": False}, sid)
                        cdp.js("window.__phone=true;document.title='SELFTEST-PHONE-ON'", sid)
                    elif title == "SELFTEST-PHONE-END":
                        cdp.call("Emulation.clearDeviceMetricsOverride", {}, sid)
                        cdp.js("window.__phone=false;document.title='SELFTEST-PHONE-OFF'", sid)
                    # any other width, for the checks that depend on a media query (title "SELFTEST-W:1100"), and the reduced-motion setting the same way
                    elif title.startswith("SELFTEST-W:"):
                        cdp.call("Emulation.setDeviceMetricsOverride", {"width": int(title.split(":")[1]), "height": 844, "deviceScaleFactor": 1, "mobile": False}, sid)
                        cdp.js("window.__w=" + title.split(":")[1] + ";document.title='SELFTEST-W-ON'", sid)
                    elif title == "SELFTEST-W-END":
                        cdp.call("Emulation.clearDeviceMetricsOverride", {}, sid)
                        cdp.js("window.__w=0;document.title='SELFTEST-W-OFF'", sid)
                    elif title == "SELFTEST-REDUCE":
                        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]}, sid)
                        cdp.js("window.__reduce=true;document.title='SELFTEST-REDUCE-ON'", sid)
                    elif title == "SELFTEST-REDUCE-END":
                        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "no-preference"}]}, sid)
                        cdp.js("window.__reduce=false;document.title='SELFTEST-REDUCE-OFF'", sid)
                if not text:
                    live = cdp.js("(e=>e?(e.dataset.step||'')+'\\n'+e.textContent:'')(document.getElementById('selftest-live'))", sid) or "\n"
                    step, _, last = live.partition("\n")
                    print(f"NO RESULT: the test did not finish in {TIMEOUT} s, in the step '{step}'; the last checks were:\n{last or '(none)'}")
                    return 1
            finally:
                proc.kill()
                proc.wait()
    finally:
        tmp.unlink(missing_ok=True)
    lines = text.splitlines()
    print("\n".join(l for l in lines if "--all" in sys.argv or not l.startswith("PASS")))
    return 0 if re.match(r"RESULT \d+ passed, 0 failed", lines[0]) and lines[-1] == "ERRORS []" else 1


if __name__ == "__main__":
    sys.exit(main())
