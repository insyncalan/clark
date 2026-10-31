"""#71: clark as a Chrome app, in headless Chrome: the service worker registers under the strict policy, the manifest makes the page
installable, and the offline page shows when clark is stopped. Required: it fails, never skips, without Chrome.

Run: python3 dev/run_tests.py test_app_browser
It runs the real server (the real Host check, headers, open routes and policy, `worker-src 'self'` included) with the table of
open files that __main__ gives it. The page is the test's own, with the link and the registering script the page shell will carry.
"""
import json
import logging
import socket
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401

from clark import appfiles, server as sv
from test_server import CHROME, chrome, wait

FILES = appfiles.open_files()
PAGE = """<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><title>clark</title>
<link rel="manifest" href="/manifest.webmanifest"></head><body><p id="s">the page</p><script>
window.result = "pending";
navigator.serviceWorker.register("/sw.js").then(() => { window.result = "registered"; }).catch(e => { window.result = "error: " + e.message; });
</script></body></html>"""


class Collect(logging.Handler):
    def __init__(self, into):
        super().__init__()
        self.into = into

    def emit(self, record):
        if "blocked" in record.getMessage():
            self.into.append(record.getMessage())


class Stoppable(sv.LocalServer):
    """The server, which when stopped also drops the connections it has accepted. Chrome opens spare connections ahead of need;
    a stopped program would take them with it, but a thread would go on answering on one."""

    def __init__(self, *a, **kw):
        self.accepted = []
        super().__init__(*a, **kw)

    def process_request(self, request, client_address):
        self.accepted.append(request)
        super().process_request(request, client_address)

    def handle_error(self, request, client_address):
        pass                                        # a client that hangs up (the browser stops) is not a failure


def start(port=0):
    httpd = Stoppable((sv.HOST, port), page_html=lambda: PAGE)
    threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
    return httpd


def stop(httpd):
    httpd.shutdown()
    httpd.server_close()
    for conn in httpd.accepted:
        try:
            conn.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass


class Browser(unittest.TestCase):
    def setUp(self):
        self.assertTrue(Path(CHROME).is_file(), f"Chrome is needed for this required browser test: set CLARK_CHROME ({CHROME!r})")
        patch = mock.patch.dict(sv.OPEN_GET_ROUTES, FILES)       # what __main__ gives the real server
        patch.start()
        self.addCleanup(patch.stop)
        self.blocked = []
        handler = Collect(self.blocked)
        sv.LOG.addHandler(handler)
        sv.LOG.setLevel("INFO")
        self.addCleanup(sv.LOG.removeHandler, handler)
        self.httpd = start()
        self.port = self.httpd.server_port
        self.addCleanup(lambda: stop(self.httpd) if self.httpd else None)

    def page(self, cdp):
        tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cdp.call("Page.enable", {}, sid)
        return sid

    def open_clark(self, cdp, sid):
        """Load clark, wait for the worker to register and take over the page; the page is then controlled by it."""
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.port}/"}, sid)
        self.assertTrue(wait(lambda: cdp.js("window.result && window.result !== 'pending'", sid)), "the page did not run its script")
        self.assertEqual(cdp.js("window.result", sid), "registered")
        cdp.js("navigator.serviceWorker.ready.then(() => { window.ready = 1; })", sid)
        self.assertTrue(wait(lambda: cdp.js("window.ready", sid) == 1), "the worker did not activate")
        cdp.js("window.firstLoad = 1", sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.port}/"}, sid)         # a new page load is controlled by it
        self.assertTrue(wait(lambda: cdp.js("window.firstLoad === undefined && document.readyState === 'complete' "
                                            "&& navigator.serviceWorker.controller !== null", sid)), "the worker does not control the page")

    def await_js(self, cdp, sid, promise, name):
        """The result of a promise, kept on the page as window[name] (the pipe's evaluate does not await)."""
        cdp.js(f"{promise}.then(v => {{ window.{name} = JSON.stringify(v); }})", sid)
        self.assertTrue(wait(lambda: cdp.js(f"window.{name} !== undefined", sid)))
        return json.loads(cdp.js(f"window.{name}", sid))

    def test_the_worker_registers_under_the_policy_caches_only_the_offline_page_and_clark_is_installable(self):
        with mock.patch.dict(sv.CSP_REPORTS, since=time.time(), n=0, dropped=0):
            with chrome() as cdp:
                sid = self.page(cdp)
                self.open_clark(cdp, sid)
                self.assertEqual(self.await_js(cdp, sid, "caches.keys()", "keys"), ["clark-offline-v1"])
                self.assertEqual(self.await_js(cdp, sid, "caches.open('clark-offline-v1').then(c => c.keys()).then(r => r.map(x => new URL(x.url).pathname))",
                                               "cached"), ["/offline"], "only the offline page is cached: never / (its boot block holds the token) or /api/")
                manifest = cdp.call("Page.getAppManifest", {}, sid)
                self.assertEqual(manifest["errors"], [])
                m = manifest["manifest"]
                self.assertEqual((m["name"], m["display"], m["themeColor"]), ("clark", "kStandalone", "rgba(6,47,58,1)"))
                self.assertEqual(cdp.call("Page.getInstallabilityErrors", {}, sid)["installabilityErrors"], [], "Chrome would offer Install")
                time.sleep(0.5)
        self.assertEqual(self.blocked, [], "the policy blocked nothing: /csp-report heard nothing")

    def test_no_route_but_the_worker_script_can_be_started_as_a_worker(self):
        """worker-src 'self' lets a page ask for a worker from this address; a worker must be JavaScript and nothing else clark
        sends is (JSON, HTML, an image, the manifest), so every other path is refused."""
        with chrome() as cdp:
            sid = self.page(cdp)
            self.open_clark(cdp, sid)
            for path in ("/api/projects", "/health", "/offline", "/manifest.webmanifest"):
                got = self.await_js(cdp, sid, f"navigator.serviceWorker.register('{path}', {{scope: '/x/'}}).then(() => 'registered', e => 'refused')", "w")
                self.assertEqual(got, "refused", path)
                cdp.js("delete window.w", sid)

    def test_the_offline_page_shows_when_clark_is_stopped_and_check_again_brings_clark_back(self):
        with chrome() as cdp:
            sid = self.page(cdp)
            self.open_clark(cdp, sid)
            stop(self.httpd)
            self.httpd = None
            for width, height, scheme, colour in ((1400, 900, "light", "rgb(243, 246, 252)"), (900, 800, "light", "rgb(243, 246, 252)"),
                                                  (1400, 900, "dark", "rgb(8, 35, 45)"), (900, 800, "dark", "rgb(8, 35, 45)")):
                with self.subTest(width=width, scheme=scheme):
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": False}, sid)
                    cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
                    cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.port}/"}, sid)
                    self.assertTrue(wait(lambda: cdp.js("document.title", sid) == "Not running", 10), "the offline page did not show")
                    text = cdp.js("document.body.innerText", sid)
                    for words in ("Start clark to use this window", "Double-click clark.command in your clark folder", "./clark.command", "Check again"):
                        self.assertIn(words, text)
                    self.assertEqual(cdp.js("getComputedStyle(document.body).backgroundColor", sid), colour)
                    self.assertTrue(cdp.js("document.documentElement.scrollWidth <= window.innerWidth", sid), "scrolls sideways")
                    self.assertTrue(cdp.js("(r => r.left >= 0 && r.right <= window.innerWidth && r.bottom <= window.innerHeight)"
                                           "(document.getElementById('again').getBoundingClientRect())", sid), "the button is not in view")
            cdp.js("document.getElementById('again').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("document.getElementById('msg').textContent", sid) == "Still not running. Double-click clark.command, then check again."), "no answer while stopped")
            self.httpd = start(self.port)                    # clark is back on the same port
            cdp.js("document.getElementById('again').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("document.title", sid) == "clark", 10), "Check again did not bring clark back")
        self.assertEqual(self.blocked, [])


if __name__ == "__main__":
    unittest.main()
