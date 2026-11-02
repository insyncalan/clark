"""#322: publish a real file for a test, and open it from file:// in headless Chrome, without borrowing another test's class.

Mix PublishedFile into a test class that has `self.store` (a real store holding project ABC, as test_glance_page.Setup
plants it): `self.publish()` writes the finished file into a temporary folder that is removed afterwards and returns its
path; `self.draw(cdp, path)` opens it at a width, light or dark, and returns the page under test once the file has drawn.
Every row is fictional, and the brand folder is empty so a brand on this laptop never changes a test.
"""
import shutil
import tempfile
from pathlib import Path

from _demo import USER
from test_report_editor import EMPTY_BRANDING, Pg

from clark import publish as publish_module


class PublishedFile:
    def publish(self):
        self.out = tempfile.mkdtemp(prefix="clark-45-")
        self.addCleanup(shutil.rmtree, self.out, ignore_errors=True)
        done = publish_module.publish(self.store, "ABC", self.out, by_user=USER, now="2026-10-28", branding=EMPTY_BRANDING)
        return Path(done["path"])

    def draw(self, cdp, path, width=1400, dark=False):
        tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Page.navigate", {"url": path.as_uri()}, sid)
        p = Pg(self, cdp, sid)
        p.until("document.documentElement.dataset.ready === '1' && !!document.querySelector('h1')", "the file drew")
        if dark:
            p.js("document.documentElement.dataset.theme = 'dark'")
        return p
