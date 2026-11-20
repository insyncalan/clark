"""Theme Cards item 8 (optional per the ticket): the Add button is dashed, 28 px high, with the plain surface ground at rest (no brand fill; opaque so the text stays 4.5 to 1 over a brand picture), and fills on hover and keyboard focus.

Run: python3 dev/run_tests.py test_add_look_28_item8
The real page over the fictional demo data in Edit at 1400 and 900 px. The first .newb on the Work items page is measured: computed height 28 px, border
style dashed 1px, the surface ground at rest; on hover it takes the filled brand colour. Chrome is required.
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
LOOK = r"""(sel) => { const e = document.querySelector(sel); if (!e) return null; const cs = getComputedStyle(e); const r = e.getBoundingClientRect(); const i = e.querySelector('.i');
  return JSON.stringify({h: r.height, style: cs.borderTopStyle, bw: cs.borderTopWidth, bg: cs.backgroundColor, icon: i ? i.getBoundingClientRect().width : null, ioff: i ? i.getBoundingClientRect().left - r.left : null, bc: cs.borderTopColor, w: r.width}); }"""


def tearDownModule():
    shutil.rmtree(EMPTY_BRANDING, ignore_errors=True)


class Add28(unittest.TestCase):
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

    def test_add_button_is_dashed_28_and_fills_on_hover_at_both_widths(self):
        with chrome() as cdp:
            for width in (1400, 900):
                sid = self.open_edit(cdp, width)
                cdp.js("document.querySelector('[data-mode=edit]').click()", sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.newb')", sid)), "an Add button drew")
                rest = self.look(cdp, sid, ".newb")
                self.assertEqual(rest["h"], 28, f"{width}: height")
                self.assertEqual((rest["style"], rest["bw"]), ("dashed", "1px"), f"{width}: border")
                ground = cdp.js("(() => { const p = document.createElement('i'); p.style.background = 'var(--surface)'; document.body.append(p); const c = getComputedStyle(p).backgroundColor; p.remove(); return c; })()", sid)
                self.assertEqual(rest["bg"], ground, f"{width}: at rest the button has the page's surface ground, not a brand fill, so its blue stays readable over a brand picture (test_brand_backdrop)")
                self.assertGreaterEqual(rest["w"], rest["icon"], f"{width}: icon not clipped")
                self.assertEqual(rest["w"], 28, f"{width}: drawn width at rest is the 28 px minimum")
                self.assertEqual(rest["ioff"], 5, f"{width}: icon sits 1 px border + 4 px padding from the left edge")
                cdp.js("document.querySelector('.newb').focus()", sid)
                cdp.js("document.querySelector('.newb').dispatchEvent(new MouseEvent('mouseover', {bubbles: true}))", sid)
                cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": 0, "y": 0}, sid)
                box = json.loads(cdp.js("(() => { const r = document.querySelector('.newb').getBoundingClientRect(); return JSON.stringify([r.x + r.width / 2, r.y + r.height / 2]); })()", sid))
                cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": box[0], "y": box[1]}, sid)
                self.assertTrue(wait(lambda: cdp.js("document.getAnimations().length === 0", sid)), "motion finished")
                hov = json.loads(cdp.js(f"({LOOK})('.newb')", sid))
                self.assertNotIn(hov["bg"], ("rgba(0, 0, 0, 0)", "transparent"), f"{width}: filled on hover")
                self.assertEqual(hov["bc"], hov["bg"], f"{width}: border takes the fill colour on hover")
                self.assertNotEqual(hov["bc"], rest["bc"], f"{width}: border colour changed from rest")


if __name__ == "__main__":
    unittest.main()
