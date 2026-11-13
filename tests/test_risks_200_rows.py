"""Hunt result: Work items with 200 risks, long titles (some with no space in them) and no owner, at 900 and 1400 px in a real browser.

Run: python3 dev/run_tests.py test_risks_200_rows
Titles wrap inside their cell with no sideways scroll, rows are in Due date then ID order, and keyboard focus stays on a cell after an edit that moves its row."""
import json
import sys
import unittest

from _demo import USER, DemoStore
from _paths import TOOLS

sys.path.insert(0, str(TOOLS))
from clark.store import open_store  # noqa: E402
import _testpage as testpage  # noqa: E402
from _editor_checks import for_url  # noqa: E402
from _real_server import real_server  # noqa: E402
from test_server import chrome, wait  # noqa: E402
from test_work_items import FIXED_DATE, page_target  # noqa: E402

CODE = "RSK"
N = 200


def title(i):
    if i % 10 == 0:
        return f"Risk{i:03d}" + "Supercalifragilisticexpialidocious" * 5
    return f"Risk {i:03d} " + "Confirm the cut-over plan with every supplier and the hosting team before the freeze " * 3


def seed(store):
    with store.step("dashboard", USER) as st:
        st.create("projects", {"code": CODE, "name": "Many risks", "health": "On track"})
        for i in range(N):
            day = 1 + (i * 7) % 28
            st.create("raid", {"project": CODE, "type": "Risk", "description": title(i), "owner": "", "due_date": f"2027-{1 + i % 12:02d}-{day:02d}",
                               "impact": "High", "likelihood": "Medium", "raised": "2026-10-01", "client_message": title(i), "source": "demo"})


class Risks(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store
        seed(self.store)
        def read(code):
            st = open_store(self.demo.dir / "clark.db", onedrive_roots=[])
            try:
                return st.data_for(code)
            finally:
                st.close()
        self.s = real_server(self.demo.dir / "clark.db", read, projects=lambda archived=False: [{"code": CODE, "name": "Many risks"}],
                             page_html=lambda: testpage.html())
        self.addCleanup(self.s.close)

    def open_page(self, cdp, width):
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, sid)
        cdp.call("Page.navigate", {"url": for_url(f"http://127.0.0.1:{self.s.port}/#work&p={CODE}&f=mode:all")}, sid)
        self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('#work tbody tr[data-id]').length", sid) > 0), "the list drew")
        return sid

    OVER = """(() => { const out = [];
      document.querySelectorAll('#work tbody tr[data-id]').forEach(r => {
        const c = r.querySelector('.c-item'), cb = c.getBoundingClientRect(), rg = document.createRange();
        rg.selectNodeContents(r.querySelector('.t'));
        if (rg.getBoundingClientRect().right > cb.right + 1 || c.scrollWidth > c.clientWidth + 1) out.push(r.dataset.id);
      });
      return {over: out, sideways: document.documentElement.scrollWidth - document.documentElement.clientWidth}; })()"""
    IDS = "[...document.querySelectorAll('#work tbody tr[data-id]')].map(r => r.dataset.id)"

    def test_long_titles_wrap_inside_their_cell_at_900_and_1400(self):
        for w in (1400, 900):
            with chrome() as cdp:
                sid = self.open_page(cdp, w)
                self.assertEqual(len(cdp.js(self.IDS, sid)), N)
                self.assertEqual(cdp.js(self.OVER, sid), {"over": [], "sideways": 0}, f"at {w}")
                # the check can fail: a title with no space in it, once the cell may not break it, runs out of its cell
                cdp.js("(() => { const x = new CSSStyleSheet(); x.replaceSync('table.items td{overflow-wrap:normal}'); document.adoptedStyleSheets = [...document.adoptedStyleSheets, x]; })()", sid)
                broke = cdp.js(self.OVER, sid)
                self.assertTrue(broke["over"] or broke["sideways"], f"at {w}: the check sees a title that runs over: {broke}")

    def test_rows_are_in_due_date_order_then_by_id(self):
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400)
            rows = self.demo.store.data_for(CODE)["raid"]
            want = [r["id"] for r in sorted(rows, key=lambda r: (r["due_date"], r["id"]))]
            self.assertEqual(cdp.js(self.IDS, sid), want)

    def test_keyboard_focus_stays_on_the_cell_after_an_edit_that_moves_the_row(self):
        from test_inline_edits import key, WHERE
        for w in (1400, 900):
            with chrome() as cdp:
                sid = self.open_page(cdp, w)
                rid = cdp.js(self.IDS, sid)[120]
                cdp.js(f"document.querySelector('[data-cell=\"{rid}:status\"]').focus()", sid)
                key(cdp, sid, "Enter")
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-pop]')", sid)), "the picker opened")
                key(cdp, sid, "ArrowDown")
                key(cdp, sid, "Enter")
                self.assertTrue(wait(lambda: cdp.js(self.IDS, sid).index(rid) != 120), f"at {w}: the row moved")
                self.assertTrue(wait(lambda: cdp.js(WHERE, sid) == f"BUTTON {rid}:status"), f"at {w}: focus is on {rid}'s Status cell, not {cdp.js(WHERE, sid)}")
                self.assertTrue(cdp.js("(b => b.top >= 0 && b.bottom <= innerHeight)(document.activeElement.getBoundingClientRect())", sid), "and it is on screen")


if __name__ == "__main__":
    unittest.main()
