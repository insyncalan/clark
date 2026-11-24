"""Row 1104: a column's width changes by dragging the right edge of its heading, in the Use cases list and the Work items table.

Run: python3 dev/run_tests.py test_col_widths
Drag the edge (wider), press Alt+Right and Alt+Left on the heading cell or on a row (the handle is not a tab stop), double-click to reset, keep it after a reload, never below the minimum; the handle is 24 px
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
from _new_page import reload_to_new_page_cdp
from test_inline_edits import EMPTY_BRANDING, key, need_chrome, tearDownModule  # noqa: F401
from test_server import chrome, wait
from test_work_items import FIXED_DATE, load_demo, page_target

PAGES = [("usecases", "#usecases&p=TUL", "#usecases .ucl-hd", "ref", "[data-uc]"), ("work", "#work&p=TUL&f=mode:all", "#work table.items", "owner", "#work tbody tr[data-id]"),
         ("milestones", "#milestones&p=TUL", "#milestones .msl-hd", "state", "#milestones li.msl-row")]      # row 1104: the Milestones list has a heading row too


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

    def visit(self, cdp, width, scheme, name):
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
        sid = self.visit(cdp, width, scheme, url)
        js = lambda e: cdp.js(e, sid)  # noqa: E731
        until = lambda e, what: self.assertTrue(wait(lambda: js(e), 20), what)  # noqa: E731
        until(f"document.querySelectorAll({json.dumps(ready)}).length > 0 && !!document.querySelector('{head} [data-cgrip=\"{col}\"]')", "the heading has its handle")
        grip = f"{head} [data-cgrip=\"{col}\"]"
        cell = f"document.querySelector({json.dumps(grip)}).parentElement.getBoundingClientRect().width"
        box = js(f"(() => {{ const b = document.querySelector({json.dumps(grip)}).getBoundingClientRect(); return [b.width, b.height]; }})()")
        self.assertGreaterEqual(box[1], 24, "the hit area is 24 px tall")
        hidden = name != "work"      # the Use cases and Milestones heading rows is hidden from a screen reader: no focus and no words on it
        if not hidden:
            self.assertIn("Width of the", js(f"document.querySelector({json.dumps(grip)}).parentElement.getAttribute('aria-description')"))
        first = js(cell)
        self.assertIsNone(js(f"localStorage.getItem('clark.cols.{name}')"), "nothing is stored until a width is changed")
        self.drag(cdp, sid, grip, 40)
        until(f"{cell} > {first} + 20", "dragging the edge to the right widens the column")
        wider = js(cell)
        self.assertIn(col, js(f"localStorage.getItem('clark.cols.{name}')"), "the width is kept on this computer")
        self.assertEqual(js(f"document.querySelector({json.dumps(grip)}).tabIndex"), -1, "the handle is not a tab stop")
        if not hidden:
            self.assertEqual(js(f"document.querySelector({json.dumps(grip)}).parentElement.tabIndex"), -1, "the heading cell holds the focus but is not a tab stop")
            self.assertIn("Alt", js(f"document.querySelector({json.dumps(grip)}).parentElement.getAttribute('aria-description')"))
        stops = f"[...document.querySelectorAll({json.dumps(head.split(' ')[0])} [tabindex], {json.dumps(head.split(' ')[0])} button, {json.dumps(head.split(' ')[0])} a, {json.dumps(head.split(' ')[0])} input)].filter(e => e.tabIndex >= 0 && e.closest('{head.split(' ')[0]}') && e.offsetWidth).length"
        before = js(stops)
        if not hidden:
            js(f"document.querySelector({json.dumps(grip)}).parentElement.focus()")
            key(cdp, sid, "ArrowRight", alt=True)
            until(f"{cell} > {wider} + 4", "Alt+Right on the heading cell widens it")
            key(cdp, sid, "ArrowLeft", alt=True)
            key(cdp, sid, "ArrowLeft", alt=True)
            until(f"{cell} < {wider}", "Alt+Left narrows it")
            key(cdp, sid, "ArrowRight", alt=True)
        js(f"""(() => {{ const h = document.querySelector({json.dumps(grip)}).parentElement.getBoundingClientRect(), r = document.querySelector({json.dumps(ready)}).getBoundingClientRect();
            let e = document.elementFromPoint(h.left + 6, r.top + r.height / 2); e.tabIndex = -1; e.focus(); }})()""")
        now = js(cell)
        key(cdp, sid, "ArrowRight", alt=True)
        until(f"{cell} > {now} + 4", "Alt+Right with the focus on a row widens that heading's column")
        self.assertEqual(js(stops), before, "changing a width adds no tab stop")
        for _ in range(40):
            key(cdp, sid, "ArrowLeft", alt=True)
        until(f"{cell} >= 47 && {cell} <= 60", "a column stops at its minimum and does not vanish")
        self.assertEqual(js("document.documentElement.scrollWidth <= innerWidth + 1"), True) if name != "work" else None
        reload_to_new_page_cdp(cdp, sid, f"!!document.querySelector({json.dumps(grip)}) && {cell} < 61", "the width is still there after a reload")
        js(f"document.querySelector({json.dumps(grip)}).dispatchEvent(new MouseEvent('dblclick', {{bubbles: true}}))")
        until(f"Math.abs({cell} - {first}) < 2", "a double-click on the edge puts the column back")
        self.assertNotIn(col, js(f"localStorage.getItem('clark.cols.{name}')"))


    def test_saved_widths_from_a_wide_window_do_not_crush_the_item_column_at_900(self):
        for scheme in ("light", "dark"):
            with self.subTest(scheme=scheme), chrome() as cdp:
                sid = self.visit(cdp, 900, scheme, "#work&p=TUL&f=mode:all")
                js = lambda e: cdp.js(e, sid)  # noqa: E731
                self.assertTrue(wait(lambda: js("document.querySelectorAll('#work tbody tr[data-id]').length > 0"), 20))
                saved = '{"owner":400,"due":300}'
                js(f"localStorage.setItem('clark.cols.work', {json.dumps(saved)})")
                reload_to_new_page_cdp(cdp, sid, "document.querySelectorAll('#work tbody tr[data-id]').length > 0", "the table is back")
                got = js("""(() => { const t = document.querySelector('#work table.items'), c = t.parentElement, i = document.querySelector('#work table.items th.c-item, #work table.items thead th');
                    return {scroll: document.documentElement.scrollWidth, inner: innerWidth, table: t.getBoundingClientRect().width, card: c.clientWidth, item: i.getBoundingClientRect().width,
                            stored: localStorage.getItem('clark.cols.work')}; })()""")
                self.assertLessEqual(got["scroll"], got["inner"] + 1, "the page does not scroll sideways")
                self.assertLessEqual(got["table"], got["card"] + 1, "the table fits its card")
                self.assertGreaterEqual(got["item"], 150, "the Item column keeps room")
                self.assertEqual(got["stored"], saved, "the saved widths are left as they were")

    def test_saved_widths_that_fit_are_drawn_as_saved_at_1400_and_shrunk_together_at_900(self):
        saved = '{"owner":400,"due":300}'
        drawn = {}
        for width in (1400, 900):
            with chrome() as cdp:
                sid = self.visit(cdp, width, "light", "#work&p=TUL&f=mode:all")
                js = lambda e: cdp.js(e, sid)  # noqa: E731
                self.assertTrue(wait(lambda: js("document.querySelectorAll('#work tbody tr[data-id]').length > 0"), 20))
                js(f"localStorage.setItem('clark.cols.work', {json.dumps(saved)})")
                reload_to_new_page_cdp(cdp, sid, "document.querySelectorAll('#work tbody tr[data-id]').length > 0", "the table is back")
                drawn[width] = js("""(() => { const w = (c) => document.querySelector('#work table.items col.c-' + c).getBoundingClientRect().width;
                    return {owner: w('owner'), due: w('due'), item: w('item')}; })()""")
        self.assertAlmostEqual(drawn[1400]["owner"], 400, delta=1, msg="room enough: the saved owner width is drawn as saved")
        self.assertAlmostEqual(drawn[1400]["due"], 300, delta=1, msg="room enough: the saved due width is drawn as saved")
        self.assertLess(drawn[900]["owner"], 400 - 20, "no room: the saved owner width shrinks")
        self.assertLess(drawn[900]["due"], 300 - 20, "no room: the saved due width shrinks")
        self.assertGreaterEqual(drawn[900]["item"], 150, "the Item column keeps its room")
        self.assertAlmostEqual(drawn[900]["owner"] / drawn[900]["due"], 400 / 300, delta=0.1, msg="and they shrink together, in proportion")

    def test_a_drag_writes_the_store_once_when_it_ends_and_starts_from_the_latest_width(self):
        src = (Path(page.__file__).parent / "src" / "edit" / "colWidths.jsx").read_text(encoding="utf-8")
        self.assertIn("now.current", src, "put reads the latest widths, not the render a drag began in")
        with chrome() as cdp:
            sid = self.visit(cdp, 1400, "light", "#usecases&p=TUL")
            js = lambda e: cdp.js(e, sid)  # noqa: E731
            grip = "#usecases .ucl-hd [data-cgrip=\"ref\"]"
            self.assertTrue(wait(lambda: js(f"!!document.querySelector('{grip}')"), 20))
            x, y = js(f"(() => {{ const b = document.querySelector('{grip}').getBoundingClientRect(); return [b.x + b.width / 2, b.y + b.height / 2]; }})()")
            for t, px, extra in (("mouseMoved", x, {}), ("mousePressed", x, {"button": "left", "buttons": 1, "clickCount": 1}), ("mouseMoved", x + 20, {"buttons": 1}), ("mouseMoved", x + 40, {"buttons": 1})):
                cdp.call("Input.dispatchMouseEvent", {"type": t, "x": px, "y": y, **extra}, sid)
            self.assertIsNone(js("localStorage.getItem('clark.cols.usecases')"), "nothing is written while the drag goes on")
            cdp.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x + 40, "y": y, "button": "left", "buttons": 0, "clickCount": 1}, sid)
            self.assertIn("ref", js("localStorage.getItem('clark.cols.usecases')") or "", "the width is written when the drag ends")

    def test_the_milestones_heading_lines_up_with_the_rows(self):
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                    sid = self.visit(cdp, width, scheme, "#milestones&p=TUL")
                    js = lambda e: cdp.js(e, sid)  # noqa: E731
                    self.assertTrue(wait(lambda: js("!!document.querySelector('#milestones .msl-hd [data-cgrip]') && document.querySelectorAll('#milestones li.msl-row').length > 0"), 20))
                    got = js("""(() => { const h = [...document.querySelectorAll('#milestones .msl-hd [data-cw-head]')].map((e) => e.getBoundingClientRect()), c = document.querySelector('#milestones .msl-cells'),
                        k = [...c.children].filter((e) => e.matches('.msl-date, .msl-name, .mst, .msl-prog')).map((e) => e.getBoundingClientRect()), hd = document.querySelector('#milestones .msl-hd').getBoundingClientRect(), b = document.querySelector('#milestones .msl').getBoundingClientRect();
                        return {heads: h.map((r) => r.left), cells: k.map((r) => r.left), words: [...document.querySelectorAll('#milestones .msl-hd [data-cw-head]')].map((e) => e.textContent), gap: b.top - hd.bottom}; })()""")
                    self.assertEqual(got["words"], ["Date", "Milestone", "State", "Progress"])
                    for a, b in zip(got["heads"], got["cells"]):
                        self.assertLess(abs(a - b), 2, "each heading sits over its column of the rows")
                    self.assertLess(abs(got["gap"]), 2, "the heading row is joined to the rows")

    def test_the_published_page_has_no_handles(self):
        view = (Path(page.__file__).parent / "page-view.html").read_text(encoding="utf-8")
        self.assertNotIn("cgrip", view)
        self.assertNotIn("Width of the", view)


if __name__ == "__main__":
    unittest.main()
