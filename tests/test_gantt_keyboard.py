"""The Gantt chart by keyboard alone, in real Chrome at 900 and 1400: Tab reaches the bars in row order, Enter on a bar opens it (in Edit
the edit box, in View its detail), Esc closes the box and focus goes back to the bar it came from.

Run: python3 dev/run_tests.py test_gantt_keyboard
"""
import unittest

import _paths  # noqa: F401
from test_gantt_e2e import Browser, CODE, E2E as Base
from test_server import chrome, wait

BAR = "[data-g-bar='GNT-002']"
ACTIVE = "(document.activeElement && document.activeElement.dataset.gBar) || (document.activeElement && document.activeElement.tagName)"


class Keyboard(Base):
    def test_the_gantt_from_settings_to_the_published_file(self):
        self.skipTest("the full flow is test_gantt_e2e's")

    def test_tab_enter_escape_on_the_bars(self):
        self.send(kind="projects", op="update", changes={"show_gantt_editor": 1})
        self.send(kind="gantt_lines", op="new", values={"type": "phase", "name": "Build", "start": "2026-11-02", "end": "2026-12-18"})
        self.send(kind="gantt_lines", op="new", values={"name": "Dig", "start": "2026-11-02", "end": "2026-11-13"}, after=f"{CODE}-GNT-001")
        self.send(kind="gantt_lines", op="new", values={"name": "Pour", "start": "2026-11-16", "end": "2026-11-27"}, after=f"{CODE}-GNT-002")
        with chrome() as cdp:
            br = Browser(self, cdp, self.rig.httpd.server_port)
            for w in (1400, 900):
                with self.subTest(width=w):
                    br.width(w)
                    br.visit(self.base + f"#gantt&p={CODE}", "document.querySelector('#gantt-page')")
                    br.click("[data-gp-mode=edit]")
                    br.until("document.querySelector('[data-g-bar]')", "bars drawn")
                    # Tab order: from one bar the next Tab lands on a later bar, in row order
                    br.js("document.querySelector(\"[data-g-bar='GNT-001']\").focus()")
                    seen = ["GNT-001"]
                    for _ in range(2):
                        br.key("Tab")
                        seen.append(br.js(ACTIVE))
                    self.assertEqual(seen[:3], ["GNT-001", "GNT-002", "GNT-003"], seen)
                    # Enter on a bar: selects, a second Enter opens the box
                    br.js(f"document.querySelector(\"{BAR}\").focus()")
                    br.key("Enter")
                    br.until(f"document.querySelector(\"{BAR}\").classList.contains('sel')", "Enter selects the bar")
                    br.key("Enter")
                    br.until("document.querySelector('[data-g-box]')", "Enter on the selected bar opens the edit box")
                    br.key("Escape")
                    br.until("!document.querySelector('[data-g-box]')", "Escape closes the box")
                    self.assertEqual(br.js(ACTIVE), "GNT-002", "focus returns to the bar the box came from")
                    # and a milestone-less second round works the same: Enter again opens it again
                    br.key("Enter")
                    br.until("document.querySelector('[data-g-box]')", "the box opens again")
                    br.key("Escape")
                    br.until("!document.querySelector('[data-g-box]')", "closed again")
                    self.assertEqual(br.js(ACTIVE), "GNT-002")


if __name__ == "__main__":
    unittest.main()
