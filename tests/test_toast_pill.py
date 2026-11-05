"""Row 781, the change toast is a pill centred at the foot of the window (no coloured left edge), with Undo and Close kept.

Run: python3 dev/run_tests.py test_toast_pill
The real page in headless Chrome; the toast's markup is the one ToastCard.jsx draws, put in the page so its look is read as the page
styles it. 1400 and 900 px, light and dark, View and Edit. The words of a toast are not touched here.
"""
import json
import re
import unittest

from _paths import SRC
from test_server import chrome
from test_work_board_page import Base

CSS = (SRC / "clark" / "page" / "shell.css").read_text(encoding="utf-8")
MARKUP = ("(() => { const r = document.createElement('div'); r.className = 'toasts'; r.id = 'row781';"
          " r.innerHTML = '<div class=\"toast KIND\"><span class=\"toast-text\">At a glance left out</span>"
          "<button type=\"button\" class=\"toast-btn\" data-undo>Undo</button>"
          "<button type=\"button\" class=\"toast-btn\" data-dismiss aria-label=\"Dismiss this message\">Close</button></div>';"
          " document.body.appendChild(r); })()")
MEASURE = ("(() => { const t = document.querySelector('#row781 .toast'), b = t.getBoundingClientRect(), s = getComputedStyle(t);"
           " return {mid: (b.left + b.right) / 2, win: document.documentElement.clientWidth, gap: innerHeight - b.bottom, h: b.height,"
           " edge: parseFloat(s.borderLeftWidth), radius: parseFloat(s.borderTopLeftRadius), left: b.left, right: b.right,"
           " undo: !!t.querySelector('[data-undo]'), close: !!t.querySelector('[data-dismiss]'), live: !!t.closest('[role=status], .toasts')}; })()")


class ToastPill(Base):
    def test_source_has_no_left_edge_and_a_pill_radius(self):
        rule = re.search(r"\n\.toast \{[^}]*\}", CSS).group(0)
        self.assertNotIn("border-left: 4px", rule)
        self.assertIn("var(--radius-pill)", rule)

    def test_pill_is_centred_at_the_foot(self):
        for width in (1400, 900):
            for edit in (False, True):
                for theme in ("light", "dark"):
                    for kind in ("done", "problem"):
                        where = f"{width} px, {'Edit' if edit else 'View'}, {theme}, {kind}"
                        with chrome() as cdp:
                            sid = self.visit(cdp, width=width, edit=edit)
                            cdp.js(f"document.documentElement.dataset.theme = {json.dumps(theme)}", sid)
                            cdp.js(MARKUP.replace("KIND", kind), sid)
                            m = cdp.js(MEASURE, sid)
                            self.assertLess(abs(m["mid"] - m["win"] / 2), 2, f"{where}: centred {m}")
                            self.assertEqual(round(m["gap"]), 16, f"{where}: 16 px from the foot {m}")
                            self.assertEqual(m["edge"], 1, f"{where}: an even rim, no 4 px edge")
                            self.assertGreaterEqual(m["radius"], m["h"] / 2 - 1, f"{where}: a pill {m}")
                            self.assertTrue(m["left"] >= 16 - 1 and m["right"] <= m["win"] - 16 + 1, where)
                            self.assertTrue(m["undo"] and m["close"] and m["live"], where)


if __name__ == "__main__":
    unittest.main()
