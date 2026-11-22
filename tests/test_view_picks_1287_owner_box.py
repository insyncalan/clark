"""Row 1287 follow-up (ruled 18-11): at 900 the owner value in a Dashboard list in View is sized to its box, not wider than its anchor.
Written in the style of test_view_picks_1287; the 900 case is paused by the harness (not run). Fictional data only.

Run: python3 dev/run_tests.py test_view_picks_1287_owner_box
"""
import test_view_picks_1287 as V
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome


class OwnerBox(V.T.InThePage):
    def test_the_owner_value_stays_inside_its_box(self):
        V.classic(self)
        ref = self.add({"mode": "all", "columns": ["id", "owner", "due", "status", "priority"], "owner": ["Pat Demo", "Lee Demo"]})
        cell = f"[data-id=\"{ref}\"] .wil-table tbody tr[data-id=\"{self.a_due}\"] .cell-pick[data-cell$=\":owner\"]"
        for width in (900, 1400):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                p.until(f"!!document.querySelector('{cell}')", "the owner cell drew")
                over = p.js(f"(() => {{ const a = document.querySelector('{cell}'), v = a.querySelector('.cell-val') || a; return Math.round(v.getBoundingClientRect().right - a.getBoundingClientRect().right); }})()")
                self.assertLessEqual(over, 0, f"{width}px: the owner value runs {over}px past its anchor")
