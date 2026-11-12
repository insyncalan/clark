"""Row 1104: a column's width changes by dragging the right edge of its heading, in the Use cases list and the Work items table.

Run: python3 dev/run_tests.py test_col_widths
Drag the edge (wider), press Right and Left on it, double-click to reset, keep it after a reload, never below the minimum; the handle is 24 px
tall and has plain words; the default widths stay when nothing was changed. At 1400 and 900 px, light and dark. A real page and server.
"""
import json
import shutil
import unittest
from pathlib import Path
from unittest import mock

from _real_server import real_server
from clark import __main__ as launcher, page, server as sv, use_cases_read
from clark.store import open_store
from test_inline_edits import EMPTY_BRANDING, key, need_chrome, tearDownModule  # noqa: F401
from test_server import chrome, wait
from test_work_items import FIXED_DATE, load_demo, page_target

PAGES = [("usecases", "#usecases&p=TUL", "#usecases .ucl-hd", "ref", "[data-uc]"), ("work", "#work&p=TUL&f=mode:all", "#work table.items", "owner", "#work tbody tr[data-id]")]


class Widths(unittest.TestCase):
    def setUp(self):
        need_chrome()
        self.store, self.folder, _ = load_demo()
        self.addCleanup(shutil.rmtree, str(self.folder), True)
        self.addCleanup(self.store.close)
        self.path = self.folder / "clark.db"
        self.s = real_server(self.path, self.read, projects=lambda archived=False: [{"code": "TUL", "name": "Tulip"}], page_html=lambda: page.page_html(EMPTY_BRANDING))
        self.s.httpd.use_cases = use_cases_read.make_read(self.read, lambda code: set(), launcher.use_case_history(mock.Mock(path=self.path)))
        self.addCleanup(self.s.close)
        quiet = mock.patch.object(sv.LOG, "disabled", True)
        quiet.start()
        self.addCleanup(quiet.stop)

    def read(self, code, archived="hide"):
        st = open_store(self.path, onedrive_roots=[])
        try:
            return st.data_for(code, archived=archived)
        finally:
            st.close()

    def open(self, cdp, width, scheme, name):
        sid = page_target(cdp)
        for m, p in (("Page.enable", {}), ("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}),
                     ("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}), ("Emulation.setFocusEmulationEnabled", {"enabled": True})):
            cdp.call(m, p, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.s.port}/{name}"}, sid)
        return sid

    def drag(self, cdp, sid, sel, dx):
        x, y = cdp.js(f"(() => {{ const b = document.querySelector({json.dumps(sel)}).getBoundingClientRect(); return [b.x + b.width / 2, b.y + b.height / 2]; }})()", sid)
        for t, px, extra in (("mouseMoved", x, {}), ("mousePressed", x, {"button": "left", "buttons": 1, "clickCount": 1}), ("mouseMoved", x + dx / 2, {"buttons": 1}),
                             ("mouseMoved", x + dx, {"buttons": 1}), ("mouseReleased", x + dx, {"button": "left", "buttons": 0, "clickCount": 1})):
            cdp.call("Input.dispatchMouseEvent", {"type": t, "x": px, "y": y, **extra}, sid)

    def test_a_heading_edge_changes_the_width_and_it_is_kept(self):
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                for name, url, head, col, ready in PAGES:
                    with self.subTest(width=width, scheme=scheme, table=name), chrome() as cdp:
                        self.check(cdp, width, scheme, name, url, head, col, ready)

    def check(self, cdp, width, scheme, name, url, head, col, ready):
        sid = self.open(cdp, width, scheme, url)
        js = lambda e: cdp.js(e, sid)  # noqa: E731
        until = lambda e, what: self.assertTrue(wait(lambda: js(e), 20), what)  # noqa: E731
        until(f"document.querySelectorAll({json.dumps(ready)}).length > 0 && !!document.querySelector('{head} [data-cgrip=\"{col}\"]')", "the heading has its handle")
        grip = f"{head} [data-cgrip=\"{col}\"]"
        cell = f"document.querySelector({json.dumps(grip)}).parentElement.getBoundingClientRect().width"
        box = js(f"(() => {{ const b = document.querySelector({json.dumps(grip)}).getBoundingClientRect(); return [b.width, b.height]; }})()")
        self.assertGreaterEqual(box[1], 24, "the hit area is 24 px tall")
        self.assertIn("Width of the", js(f"document.querySelector({json.dumps(grip)}).getAttribute('aria-label')"))
        first = js(cell)
        self.assertIsNone(js(f"localStorage.getItem('clark.cols.{name}')"), "nothing is stored until a width is changed")
        self.drag(cdp, sid, grip, 40)
        until(f"{cell} > {first} + 20", "dragging the edge to the right widens the column")
        wider = js(cell)
        self.assertIn(col, js(f"localStorage.getItem('clark.cols.{name}')"), "the width is kept on this computer")
        js(f"document.querySelector({json.dumps(grip)}).focus()")
        key(cdp, sid, "ArrowRight")
        until(f"{cell} > {wider} + 4", "Right widens it")
        key(cdp, sid, "ArrowLeft")
        key(cdp, sid, "ArrowLeft")
        until(f"{cell} < {wider}", "Left narrows it")
        for _ in range(40):
            key(cdp, sid, "ArrowLeft")
        until(f"{cell} >= 47 && {cell} <= 60", "a column stops at its minimum and does not vanish")
        self.assertEqual(js("document.documentElement.scrollWidth <= innerWidth + 1"), True) if name == "usecases" else None
        cdp.call("Page.reload", {}, sid)
        until(f"!!document.querySelector({json.dumps(grip)}) && {cell} < 61", "the width is still there after a reload")
        js(f"document.querySelector({json.dumps(grip)}).dispatchEvent(new MouseEvent('dblclick', {{bubbles: true}}))")
        until(f"Math.abs({cell} - {first}) < 2", "a double-click on the edge puts the column back")
        self.assertNotIn(col, js(f"localStorage.getItem('clark.cols.{name}')"))


    def test_the_published_page_has_no_handles(self):
        view = (Path(page.__file__).parent / "page-view.html").read_text(encoding="utf-8")
        self.assertNotIn("cgrip", view)
        self.assertNotIn("Width of the", view)


if __name__ == "__main__":
    unittest.main()
