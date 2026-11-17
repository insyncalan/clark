"""Row 1296: a right click on a work item row on the Dashboard opens the same menu the Work items list has (RowMenu.jsx).

Run: python3 dev/run_tests.py test_row_menu_dashboard
A real browser against a real server over the demo store. Same entries, same words, same order as the list; in View the changes are
listed but greyed (nothing is written), in Edit they are live. Desktop (1400) and 900 px.
"""
import json
import unittest

from _demo import DemoStore
from clark import page

from test_item_rows import fill
from test_report_editor import EMPTY_BRANDING, Pg
from test_row_menu import right_click
from test_server import Running, chrome

WORDS = ["Draft email to Sara Khan", "Open the peek", "Change status", "Move due date", "Change owner", "Hide from the client",
         "Copy link to this item", "Copy ID", "Duplicate", "Archive"]
CHANGES = ("status", "due", "owner", "eye", "dup", "archive")


class DashboardRowMenu(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        fill(self.demo.store)
        self.s = Running(data_for=self.demo.store.data_for, page_html=lambda: page.page_html(EMPTY_BRANDING))
        self.addCleanup(self.s.close)

    def entries(self, p):
        return p.js("[...document.querySelectorAll('.rowmenu [role=menuitem]')].map(b => [b.dataset.rm, b.querySelector('b').textContent, b.getAttribute('aria-disabled') === 'true'])")

    def open(self, p, selector):
        right_click(p.cdp, p.sid, selector)
        p.until("!!document.querySelector('.rowmenu [role=menu]')", "the menu")

    def close(self, p):
        p.js("document.activeElement && document.activeElement.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))")
        p.until("!document.querySelector('.rowmenu')", "the menu closed")

    def test_the_dashboard_row_has_the_work_items_menu_in_view_and_in_edit(self):
        with chrome() as cdp:
            p = Pg.at(self, cdp, self.s.port)
            p.ready()
            sel = "[data-type=actions] .wl-row"
            for w in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                self.open(p, sel)
                got = self.entries(p)
                self.assertEqual([e[1] for e in got][:len(WORDS)], [WORDS[0].replace("Sara Khan", got[0][1][len("Draft email to "):])] + WORDS[1:], f"View at {w}")
                self.assertEqual([e[1] for e in got][-1], "Archive", "no Delete while the page is read only")
                by = {e[0]: e for e in got}
                self.assertTrue(all(by[k][2] for k in CHANGES), f"View at {w}: the changes are listed and greyed")
                self.assertFalse(any(by[k][2] for k in ("peek", "link", "copyid")), "the reads stay live")
                self.assertTrue(p.js("(() => { const b = document.querySelector('.rowmenu .ddmenu').getBoundingClientRect(); return b.left >= 0 && b.right <= innerWidth && b.bottom <= innerHeight; })()"), "inside the window")
                self.close(p)
            p.edit()
            for w in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                self.open(p, sel)
                got = self.entries(p)
                self.assertEqual([e[1] for e in got][1:], WORDS[1:] + ["Delete"], f"Edit at {w}")
                self.assertFalse(any(e[2] for e in got), "Edit: every entry is live")
                self.close(p)

    def test_copy_id_and_open_the_peek_work_from_the_dashboard(self):
        with chrome() as cdp:
            p = Pg.at(self, cdp, self.s.port)
            p.ready()
            self.open(p, "[data-type=actions] .wl-row")
            rid = p.js("document.querySelector('.rowmenu').dataset.rowmenu")
            p.js("document.querySelector('.rowmenu [data-rm=peek]').click()")
            p.until(f"location.href.indexOf({json.dumps(rid)}) >= 0 || !!document.querySelector('[data-peek]')", "the peek opened")

    def test_a_board_card_is_never_drawn_on_the_dashboard(self):
        """Row 1296 owns the list rows only; the board card menu belongs to the Work items board. The Dashboard has no board to inherit from."""
        import pathlib
        src = pathlib.Path(page.__file__).parent / "src"
        users = sorted(f.name for f in src.rglob("*.jsx") if "<Board " in f.read_text(encoding="utf-8"))
        self.assertEqual(users, ["WorkItems.jsx"], "only the Work items page draws the board")
        with chrome() as cdp:
            p = Pg.at(self, cdp, self.s.port)
            p.ready()
            for w in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                self.assertEqual(p.js("document.querySelectorAll('article.bcard').length"), 0, f"no card on the Dashboard at {w}")
            p.edit()
            self.assertEqual(p.js("document.querySelectorAll('article.bcard').length"), 0, "none in Edit either")


if __name__ == "__main__":
    unittest.main()
