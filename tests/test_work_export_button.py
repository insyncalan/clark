"""No Export icon on Work items, in the editor or in the published file (row 1142 took it off the pages; Export is in the profile menu and Settings).
Also holds open_page, which other page checks use.

Run: python3 dev/run_tests.py test_work_export_button
Headless Chrome (required: fails, never skips, without it). Desktop only: 1400 and 900 px, light and dark.
"""

import shutil
import tempfile
import unittest
from pathlib import Path

from _demo import USER, DemoStore
from clark import page, publish
from test_server import Running, chrome, wait
from test_work_filters import need_chrome
from test_work_items import page_target

TODAY = "2026-10-28"
EMPTY_BRANDING = tempfile.mkdtemp(prefix="clark-no-brand-")
ADD = "[...document.querySelectorAll('button, [role=button], a')].filter(e => /^Add\\b/.test((e.getAttribute('aria-label') || e.title || e.textContent || '').trim()) || e.id === 'newBtn' || e.classList.contains('newb'))"
VARIANTS = [(w, s) for w in (1400, 900) for s in ("light", "dark")]


def open_page(cdp, url, width, scheme):
    sid = page_target(cdp)
    cdp.call("Page.enable", {}, sid)
    cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
    cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
    cdp.call("Page.navigate", {"url": url}, sid)
    return sid


class ExportButton(unittest.TestCase):
    def setUp(self):
        need_chrome()

    def test_the_published_file_has_no_export_icon(self):
        demo = DemoStore()
        folder = tempfile.mkdtemp(prefix="clark-pub-")
        self.addCleanup(demo.close)
        self.addCleanup(shutil.rmtree, folder, True)
        path = Path(publish.publish(demo.store, "ABC", folder, by_user=USER, now=TODAY, branding=EMPTY_BRANDING)["path"])
        for width, scheme in VARIANTS:
            with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                sid = open_page(cdp, path.as_uri(), width, scheme)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.tab')", sid)))
                cdp.js("[...document.querySelectorAll('.tab')].find(t => /Work items/.test(t.textContent)).click()", sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#work h1')", sid)))
                self.assertEqual(cdp.js("document.querySelectorAll('#expBtn').length", sid), 0)

    def test_the_editor_has_no_export_or_import_icon(self):
        demo = DemoStore()
        self.addCleanup(demo.close)
        s = Running(data_for=demo.store.data_for, page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(s.close)
        for width, scheme in VARIANTS:
            with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                sid = open_page(cdp, f"http://127.0.0.1:{s.port}/#work&p=ABC", width, scheme)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#work h1')", sid)))
                self.assertEqual(cdp.js("document.querySelectorAll('#newBtn').length", sid), 1, "Add is still there")
                self.assertEqual(cdp.js("document.querySelectorAll('#expBtn, #impBtn').length", sid), 0, "row 1142: no Export or Import icon")


if __name__ == "__main__":
    unittest.main()
