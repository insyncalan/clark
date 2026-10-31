"""#204: the published file's Work items tab draws no Add item button (a published file is read only); the editor keeps it.

Run: python3 dev/run_tests.py test_published_work_no_add
Headless Chrome (required: fails, never skips, without it). The published file is opened from disk; the editor from a real server.
Desktop only: 1400 and 900 px, light and dark.
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


class PublishedWork(unittest.TestCase):
    def setUp(self):
        need_chrome()

    def test_the_published_work_items_tab_has_no_add_item_button(self):
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
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#work h1')", sid)), "the Work items tab drew")
                self.assertEqual(cdp.js(f"{ADD}.length", sid), 0, "no Add control in a published file")
                self.assertEqual(cdp.js("document.querySelectorAll('#work .head button').length", sid), 0, "no button in the Work items heading")

    def test_the_editor_keeps_its_add_button(self):
        demo = DemoStore()
        self.addCleanup(demo.close)
        s = Running(data_for=demo.store.data_for, page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(s.close)
        for width, scheme in VARIANTS:
            with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                sid = open_page(cdp, f"http://127.0.0.1:{s.port}/#work&p=ABC", width, scheme)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#work h1')", sid)), "the Work items page drew")
                self.assertEqual(cdp.js("document.querySelectorAll('#newBtn').length", sid), 1)


if __name__ == "__main__":
    unittest.main()
