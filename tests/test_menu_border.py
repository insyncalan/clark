"""#955: the border every menu shares reaches 3:1 against the page ground and against a card surface, in light and in dark.

Run: python3 dev/run_tests.py test_menu_border
The real page and a real server over the fictional demo data, at 1400 and 900 px, light and dark. Opened and measured: the drop-down menu (the
profile menu, .ddmenu), a cell picker (the Work items Status picker, .cpop) and the filter line's suggestion list (.flist). The computed border colour
of each is compared with the body's ground and with the menu's own surface (the colour of a card): at least 3:1 on both. The menu border is one rule and
one token (--menu-border), so the published page's menus (the same shell stylesheet) have it too. Chrome is required.
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
  return JSON.stringify({border: cs.borderTopColor, style: cs.borderTopStyle, width: cs.borderTopWidth, surface: cs.backgroundColor, ground: getComputedStyle(document.body).backgroundColor}); }"""


def tearDownModule():
    shutil.rmtree(EMPTY_BRANDING, ignore_errors=True)


def rgb(text):
    """rgb(1, 2, 3), rgba(...) or color(srgb 0.1 0.2 0.3) (what color-mix computes to) as three 0-255 numbers."""
    nums = [float(x) for x in re.findall(r"-?[\d.]+(?:e-?\d+)?", text)[:3]]
    return [n * 255 for n in nums] if text.startswith("color(") else nums


def lum(c):
    out = []
    for v in c:
        v /= 255
        out.append(v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4)
    return 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]


def ratio(a, b):
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


class MenuBorder(unittest.TestCase):
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

    def read(self, code):
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

    def check(self, where, got):
        self.assertEqual((got["style"], got["width"]), ("solid", "1px"), where)
        border = rgb(got["border"])
        for what in ("ground", "surface"):
            r = ratio(border, rgb(got[what]))
            self.assertGreaterEqual(r, 3.0, f"{where}: border {got['border']} on the {what} {got[what]} is {r:.2f}:1")

    def test_every_menu_border_is_3_to_1_on_the_page_and_on_a_card_at_both_widths_in_both_looks(self):
        with chrome() as cdp:
            for width in (1400, 900):
                for theme in ("light", "dark"):
                    sid = page_target(cdp)
                    cdp.call("Page.enable", {}, sid)
                    cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
                    cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.s.port}/#work&p=TUL&f=mode:all"}, sid)
                    self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.ready", sid) == "1"), "the bundle ran")
                    cdp.js(f"document.documentElement.dataset.theme = {json.dumps(theme)}", sid)
                    cdp.js("document.querySelector('[data-mode=edit]').click()", sid)
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('table.items .cell-pick[data-cell$=\":status\"]')", sid)), "Edit drew")
                    where = f"{width} px, {theme}"
                    # the drop-down menu
                    cdp.js("document.querySelector('#profile-btn').click()", sid)
                    self.check(where + ": drop-down menu", self.look(cdp, sid, ".ddmenu"))
                    cdp.js("document.querySelector('#profile-btn').click()", sid)
                    self.assertTrue(wait(lambda: not cdp.js("document.querySelector('.ddmenu')", sid)), "the menu closed")
                    # a cell picker
                    cdp.js("document.querySelector('table.items .cell-pick[data-cell$=\":status\"]').click()", sid)
                    self.check(where + ": cell picker", self.look(cdp, sid, ".cpop"))
                    cdp.js("document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))", sid)
                    cdp.js("document.activeElement && document.activeElement.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))", sid)
                    self.assertTrue(wait(lambda: not cdp.js("document.querySelector('.cpop')", sid)), "the picker closed")
                    # the filter line's suggestion list
                    set_line(cdp, sid, "owner:")
                    arm(cdp, sid)                                       # row 931: the list follows Space
                    self.check(where + ": suggestion list", self.look(cdp, sid, ".flist"))


if __name__ == "__main__":
    unittest.main()
