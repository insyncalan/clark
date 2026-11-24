"""Row 1294: the Defaults page's ask clark row in the Classic Theme, as mock-up A8 draws it: the name, the help line, and "Open All projects" as a text
link (a muted dashed underline, no button box), in the row. Real Settings page, demo database, fictional data. Cards is pinned by
test_settings_essentials_1115 (words and the jump to the All projects tab).

Run: python3 dev/run_tests.py test_ask_link_classic_1294"""
import shutil
import tempfile
import time
import unittest
from pathlib import Path

import _paths  # noqa: F401
from _editor_checks import for_url

from clark import page
from test_server import Running, chrome, wait
from test_work_items import FIXED_DATE, load_demo, page_target

NAME = "prototype-2.0"
PROBE = """(() => { const b = document.querySelector('[data-ess-ask-open]'); if (!b) return null; const s = getComputedStyle(b), r = b.getBoundingClientRect(), row = b.closest('.set-row').getBoundingClientRect();
  return {text: b.textContent, border: s.borderBottomStyle, top: s.borderTopWidth, bg: s.backgroundColor, inside: r.width > 0 && r.right <= row.right + 1 && r.left >= row.left - 1, wide: document.documentElement.scrollWidth > document.documentElement.clientWidth,
          name: b.closest('.set-row').querySelector('label').textContent}; })()"""


class Link(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store, cls.folder, cls.ids = load_demo()
        cls.names = {p["code"]: p["name"] for p in cls.store.read("projects")}
        cls.data = {c: cls.store.data_for(c) for c in cls.names}

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        shutil.rmtree(str(cls.folder), ignore_errors=True)

    def look(self, width, theme):
        s = Running(data_for=lambda code, **kw: self.data.get(code), projects=lambda archived=False: [{"code": c, "name": n} for c, n in sorted(self.names.items())],
                    page_html=lambda: page.page_html(tempfile.mkdtemp(), theme=theme))
        self.addCleanup(s.close)
        with chrome() as cdp:
            sid = page_target(cdp)
            cdp.call("Page.enable", {}, sid)
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
            cdp.call("Page.navigate", {"url": "about:blank"}, sid)
            cdp.call("Page.navigate", {"url": for_url(f"http://127.0.0.1:{s.port}/#settings&p=TUL&s=profile")}, sid)
            self.assertTrue(wait(lambda: bool(cdp.js("!!document.querySelector('[data-ess-ask-open]')", sid)), 30), "timed out waiting for the Essentials row")
            time.sleep(0.3)
            got = cdp.js(PROBE, sid)
            cdp.js("document.querySelector('[data-ess-ask-open]').click()", sid)
            opened = wait(lambda: bool(cdp.js("!!document.querySelector('[data-ask-tab=all][aria-current=true]') && !!document.querySelector('#ai-settings')", sid)), 20)
            return got, opened

    def test_classic_draws_a_dashed_text_link_in_the_row_at_1400_and_900(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                got, opened = self.look(width, NAME)
                self.assertEqual((got["name"], got["text"]), ("ask clark", "Open All projects"))
                self.assertEqual((got["border"], got["top"], got["bg"]), ("dashed", "0px", "rgba(0, 0, 0, 0)"), "a text link with a dashed underline, no button box")
                self.assertTrue(got["inside"], "the link is inside its row")
                self.assertFalse(got["wide"], "no sideways scroll")
                self.assertTrue(opened, "the link opens the All projects tab")

    def test_cards_keeps_its_own_look(self):
        got, _ = self.look(1400, None)
        self.assertNotEqual(got["border"], "dashed", "the Classic rule does not reach Cards")


if __name__ == "__main__":
    unittest.main()
