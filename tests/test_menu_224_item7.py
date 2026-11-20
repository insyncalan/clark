"""Theme Cards item 7 (optional per the ticket): the drop-down menu is 224 px wide at least and its items are 15 px text.

Run: python3 dev/run_tests.py test_menu_224_item7
The real page over the fictional demo data at 1400 and 900 px. The profile menu (.ddmenu) is opened; its computed min-width is 224 px and the computed
font size of each menu item is 15 px. Chrome is required.
"""
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401  (puts src/ on the path)

from clark import page, server as sv  # noqa: E402
from clark.store import open_store  # noqa: E402
from test_server import CHROME, Running, chrome, wait  # noqa: E402
from test_work_filters import arm, set_line  # noqa: E402
from test_work_items import FIXED_DATE, load_demo, page_target  # noqa: E402

EMPTY_BRANDING = tempfile.mkdtemp(prefix="clark-no-brand-")
LOOK = r"""(sel) => { const e = document.querySelector(sel); if (!e) return null; const cs = getComputedStyle(e);
  const items = [...e.querySelectorAll('[role=menuitem],[role=menuitemradio]')];
  return JSON.stringify({min: cs.minWidth, width: e.getBoundingClientRect().width, sizes: items.map(i => getComputedStyle(i).fontSize), n: items.length, wraps: items.filter(i => i.getBoundingClientRect().height > 2 * (parseFloat(getComputedStyle(i).lineHeight) || 1.4 * parseFloat(getComputedStyle(i).fontSize))).length, hs: items.map(i => i.getBoundingClientRect().height + ":" + i.textContent.trim())}); }"""


def tearDownModule():
    shutil.rmtree(EMPTY_BRANDING, ignore_errors=True)


class Menu224(unittest.TestCase):
    def setUp(self):
        assert Path(CHROME).is_file(), f"Google Chrome is needed for the required browser tests ({CHROME}); set CLARK_CHROME"
        self.store, self.folder, _ = load_demo()
        self.addCleanup(shutil.rmtree, str(self.folder), True)
        self.addCleanup(self.store.close)
        self.path = self.folder / "clark.db"
        self.s = Running(data_for=self.read, projects=lambda archived=False: [{"code": "TUL", "name": "Tulip"}], page_html=lambda: page.page_html(EMPTY_BRANDING))
        self.addCleanup(self.s.close)
        quiet = mock.patch.object(sv.LOG, "disabled", True)
        quiet.start()
        self.addCleanup(quiet.stop)

    def read(self, code, archived=None):
        st = open_store(self.path, onedrive_roots=[])
        try:
            return st.data_for(code)
        finally:
            st.close()

    def look(self, cdp, sid, selector):
        got = None

        def seen():
            nonlocal got
            got = cdp.js(f"({LOOK})({json.dumps(selector)})", sid)
            return got is not None
        self.assertTrue(wait(seen), f"{selector} is on the page")
        self.assertTrue(wait(lambda: cdp.js("document.getAnimations().length === 0", sid)), "the page's motion has finished before anything is measured")
        return json.loads(cdp.js(f"({LOOK})({json.dumps(selector)})", sid))


    def open_edit(self, cdp, width):
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.s.port}/#work&p=TUL&f=mode:all"}, sid)
        self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.ready", sid) == "1"), "the bundle ran")
        return sid

    def test_profile_menu_is_224_wide_with_15px_items_at_both_widths(self):
        with chrome() as cdp:
            for width in (1400, 900):
                sid = self.open_edit(cdp, width)
                cdp.js("document.querySelector('[data-mode=edit]').click()", sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('table.items .cell-pick[data-cell$=\":status\"]')", sid)), "Edit drew")
                cdp.js("document.querySelector('#profile-btn').click()", sid)
                got = self.look(cdp, sid, ".ddmenu")
                self.assertGreater(got["n"], 0, f"{width}: the menu has items")
                self.assertEqual(got["min"], "224px", f"{width}: min-width")
                self.assertGreaterEqual(got["width"], 224, f"{width}: drawn width")
                self.assertEqual(set(got["sizes"]), {"15px"}, f"{width}: item font sizes")


if __name__ == "__main__":
    unittest.main()
