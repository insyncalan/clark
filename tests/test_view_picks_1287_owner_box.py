"""Row 1287 follow-up (ruled 18-11): at 900 the owner value in a Dashboard list in View is sized to its box, not wider than its anchor.
Written in the style of test_view_picks_1287; runs at 900 and 1400 (PAUSED_900 is None on main). Asserted at both: the value's right edge is inside its anchor, neither the value nor the cell scrolls sideways, and the measured widths hold (value 97.3 px in an anchor 124.3 px, within 2 px). Fictional data only.

Run: python3 dev/run_tests.py test_view_picks_1287_owner_box
"""
import test_view_picks_1287 as V
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome


# Measured 23-11 on the served page, Classic View, owner "Pat Demo": the same at 1400 and 900.
MEASURED_VALUE, MEASURED_ANCHOR = 97.3, 124.3


class OwnerBox(V.T.InThePage):
    def test_the_owner_value_stays_inside_its_box(self):
        V.classic(self)
        ref = self.add({"mode": "all", "columns": ["id", "owner", "due", "status", "priority"], "owner": ["Pat Demo", "Lee Demo"]})
        cell = f"[data-id=\"{ref}\"] .wil-table tbody tr[data-id=\"{self.a_due}\"] .cell-pick[data-cell$=\":owner\"]"
        for width in (900, 1400):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                p.until(f"!!document.querySelector('{cell}')", "the owner cell drew")
                m = p.js(f"(() => {{ const a = document.querySelector('{cell}'), v = a.querySelector('.cell-val') || a; const ar = a.getBoundingClientRect(), vr = v.getBoundingClientRect(); return {{inside: Math.round(ar.right - vr.right), valW: Math.round(vr.width), anchorW: Math.round(ar.width), scrollW: a.scrollWidth, clientW: a.clientWidth, vScroll: v.scrollWidth, vClient: v.clientWidth}}; }})()")
                self.assertGreaterEqual(m["inside"], 0, f"{width}px: the owner value runs {-m['inside']}px past its anchor")
                self.assertLessEqual(m["valW"], m["anchorW"], f"{width}px: the owner value ({m['valW']}px) is wider than its anchor ({m['anchorW']}px)")
                self.assertLessEqual(m["vScroll"], m["vClient"], f"{width}px: the owner value scrolls sideways {m}")
                self.assertAlmostEqual(m["valW"], MEASURED_VALUE, delta=2, msg=f"{width}px: the owner value is {m['valW']}px, measured {MEASURED_VALUE}px")
                self.assertAlmostEqual(m["anchorW"], MEASURED_ANCHOR, delta=2, msg=f"{width}px: the owner anchor is {m['anchorW']}px, measured {MEASURED_ANCHOR}px")
                self.assertLessEqual(m["scrollW"], m["clientW"], f"{width}px: the owner cell scrolls sideways ({m['scrollW']} > {m['clientW']})")
