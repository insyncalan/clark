"""#71: the page's side of clark as a Chrome app (src/clark/page/src/app.js), in headless Chrome against the real server.

Run: python3 dev/run_tests.py test_app_page
The live page adds the manifest link and the theme colour, registers the worker and says "still here" to /api/here; the published
page (page-view.html) does none of it. The strict script policy stays on (the server's own, with worker-src 'self').
"""
import logging
import tempfile
import time
import unittest
from unittest import mock

from _paths import SRC, ROOT  # noqa: F401

from clark import appfiles, idle, page, server as sv  # noqa: E402
from test_page import DATA, navigate  # noqa: E402
from test_server import Running, chrome, wait  # noqa: E402


class Source(unittest.TestCase):
    def test_the_heartbeat_keeps_step_with_the_servers_limit(self):
        js = (ROOT / "src" / "clark" / "page" / "src" / "app.js").read_text(encoding="utf-8")
        self.assertIn(f"const HEARTBEAT_MS = {idle.HEARTBEAT * 1000};", js)
        self.assertLess(idle.HEARTBEAT * 3, idle.STOP_AFTER, "a few missed beats must not stop clark")

    def test_the_published_page_has_none_of_it_and_the_live_page_writes_no_link(self):
        folder = ROOT / "src" / "clark" / "page"
        view, live = (folder / "page-view.html").read_text(encoding="utf-8"), (folder / "page.html").read_text(encoding="utf-8")
        for word in ("api/here", "serviceWorker", "webmanifest", "theme-color"):
            self.assertNotIn(word, view, word)
        self.assertNotIn("<link rel=\"manifest\"", live, "the link is added by script: the publish scan rejects any <link but the icons")
        self.assertIn("/sw.js", live)


class Live(unittest.TestCase):
    def setUp(self):
        self.s = Running(data_for=DATA.get, page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(self.s.close)
        for patch in (mock.patch.dict(sv.OPEN_GET_ROUTES, appfiles.open_files()), mock.patch.object(sv, "IDLE", idle.Idle(stop_after=60))):
            patch.start()
            self.addCleanup(patch.stop)
        self.blocked = []
        handler = logging.Handler()
        handler.emit = lambda record: self.blocked.append(record.getMessage()) if "blocked" in record.getMessage() else None
        sv.LOG.addHandler(handler)
        sv.LOG.setLevel("INFO")
        self.addCleanup(sv.LOG.removeHandler, handler)

    def test_manifest_theme_colour_worker_and_still_here(self):
        beats = []
        real = sv.here_route
        with mock.patch.object(sv, "here_route", lambda h, req: (beats.append(1), real(h, req))[1]), chrome() as cdp:
            sid = navigate(cdp, self.s.port, "#dashboard&p=ABC")
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('link[rel=manifest]')", sid)), "no manifest link")
            self.assertEqual(cdp.js("document.querySelector('link[rel=manifest]').getAttribute('href')", sid), "/manifest.webmanifest")
            for width in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
                for scheme, theme, navy, rgb in (("light", "", "#062F3A", "rgb(6, 47, 58)"), ("dark", "dark", "#04202A", "rgb(4, 32, 42)")):
                    cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
                    cdp.js(f"document.documentElement.dataset.theme = '{theme}'", sid)
                    self.assertTrue(wait(lambda: cdp.js("document.querySelector('meta[name=theme-color]').content", sid) == navy),
                                    f"the theme colour is the top bar's navy in {scheme} at {width}")
                    self.assertEqual(cdp.js("getComputedStyle(document.querySelector('.top')).backgroundColor", sid), rgb,
                                     "and the top bar is that colour")
            cdp.js("window.ready = 0; navigator.serviceWorker.ready.then(() => { window.ready = 1; })", sid)
            self.assertTrue(wait(lambda: cdp.js("window.ready", sid) == 1), "the worker registered and activated under the policy")
            self.assertTrue(wait(lambda: len(beats) >= 1), "the page said it is here")
            before = len(beats)
            cdp.js("document.dispatchEvent(new Event('visibilitychange'))", sid)
            self.assertTrue(wait(lambda: len(beats) > before), "and says so again when it becomes visible")
            time.sleep(0.3)
        self.assertEqual(self.blocked, [], "the policy blocked nothing")


if __name__ == "__main__":
    unittest.main()
