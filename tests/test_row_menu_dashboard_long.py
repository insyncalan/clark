"""Row 1296: a Dashboard row with unbroken long text gives a menu inside the window and no entry wider than its box.

Run: python3 dev/run_tests.py test_row_menu_dashboard_long
A real browser against a real server over the demo store, at 1400 and 900 px."""
import unittest

from _demo import DemoStore
from clark import page

from test_item_rows import fill, USER
from test_report_editor import Pg
from test_row_menu import right_click
from test_server import Running, chrome
import _testpage as testpage

INSIDE = ("(() => { const m = document.querySelector('.rowmenu .ddmenu') || document.querySelector('.rowmenu'), b = m.getBoundingClientRect();"
          " return [b.left, b.top, b.right, b.bottom, innerWidth, innerHeight]; })()")
LONG = "Unbroken" + "x" * 400


class Base(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.prepare(self.demo.store)
        self.s = Running(data_for=self.demo.store.data_for, page_html=lambda: testpage.html())
        self.addCleanup(self.s.close)

    def prepare(self, store):
        fill(store)

    def size(self, p, w, h=900):
        p.cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": h, "deviceScaleFactor": 1, "mobile": False}, p.sid)

    def menu_open(self, p, what):
        p.until("!!document.querySelector('.rowmenu [role=menu]')", what)

    def click_at(self, p, x, y):
        for t, b in (("mouseMoved", "none"), ("mousePressed", "right"), ("mouseReleased", "right")):
            p.cdp.call("Input.dispatchMouseEvent", {"type": t, "x": x, "y": y, "button": b, "buttons": 2 if t == "mousePressed" else 0, "clickCount": 1}, p.sid)

    def esc(self, p):
        p.js("(document.activeElement || document.body).dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))")

    def assert_inside(self, p, where):
        l, t, r, b, w, h = p.js(INSIDE)
        self.assertGreaterEqual(l, 0, f"{where}: left edge {l}")
        self.assertGreaterEqual(t, 0, f"{where}: top edge {t}")
        self.assertLessEqual(r, w, f"{where}: right edge {r} of {w}")
        self.assertLessEqual(b, h, f"{where}: bottom edge {b} of {h}")


class LongText(Base):
    def prepare(self, store):
        fill(store)
        self.demo.plant_builtin_sections()      # a new project's Open actions is a Work items list; this row is in the built-in section (row 1193)
        with store.step("dashboard", USER) as st:
            st.create("actions", {"project": "ABC", "description": LONG, "owner": "Owner " + LONG[:120], "due_date": "2026-11-05",
                                  "raised": "2026-10-01", "client_message": LONG, "source": "demo"})

    def test_a_row_with_unbroken_long_text_gives_a_menu_inside_the_window_and_no_sideways_scroll(self):
        with chrome() as cdp:
            p = Pg.at(self, cdp, self.s.port)
            p.ready()
            p.edit()
            for w in (1400, 900):
                self.size(p, w)
                sel = "[data-type=actions] .wl-row[data-id]"
                rid = p.js("[...document.querySelectorAll('[data-type=actions] .wl-row')].find(r => r.textContent.includes('Unbroken')).dataset.id")
                self.assertTrue(rid, f"the long row is drawn at {w}")
                row = f"[data-type=actions] .wl-row[data-id='{rid}']"
                right_click(cdp, p.sid, row)
                self.menu_open(p, f"the menu at {w}")
                self.assertEqual(p.js("document.querySelector('.rowmenu').dataset.rowmenu"), rid)
                self.assert_inside(p, f"long text at {w}")
                over = p.js("[...document.querySelectorAll('.rowmenu [role=menuitem]')].filter(b => b.scrollWidth > b.clientWidth + 1).map(b => b.dataset.rm)")
                self.assertEqual(over, [], f"no entry overflows its box at {w}")
                self.assertLessEqual(p.js("document.documentElement.scrollWidth"), w, f"no sideways scroll at {w}")
                self.esc(p)
                p.until("!document.querySelector('.rowmenu')", f"closed at {w}")


if __name__ == "__main__":
    unittest.main()
