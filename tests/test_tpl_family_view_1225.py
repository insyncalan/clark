"""Row 1225 AP3: every template's View is its Edit look without the controls (1400 and 900 px, light and dark).

All 24 templates, filled, on the served page. In View no section holds a control (a button, field, select, link-less handle, draggable or
role=button/menuitem/switch). The few templates that do hold some today are named in FINDINGS with the controls measured: the test pins
them so a template that gains a control fails, and one that loses its controls says to remove its line.
The 900 px half skips while PAUSED_900 is set (test_server.py), as every 900 px case does.
Run: python3 dev/run_tests.py test_tpl_family_view_1225
"""
import unittest

import _tpl_family as F
from test_report_editor import tearDownModule  # noqa: F401
from test_server import Running  # noqa: F401

# Measured on the 24 templates as built (the same at 1400 and 900, light and dark): template id -> {control: count}
FINDINGS = {
    "gallery": {"button.tpl-gal-open": 1},
    "work-items": {"th.wil-c-type": 1, "th.wil-c-owner": 1, "th.wil-c-due": 1, "th.wil-c-priority": 1, "th.wil-c-id": 1,
                   "tr.wil-k-action": 1, "tr.wil-k-risk": 1, "button.wil-review": 1},
    "gantt": {"button.gt-ib": 7, "button.gt-zf": 1, "button.gt-wd": 1, "button.gt-tflag": 1, "div.gt-b.gt-b-phase": 1, "div.gt-b.gt-b-task": 1},
    "gantt-table": {"button": 3},
}


def counts(names):
    out = {}
    for n in names:
        out[n] = out.get(n, 0) + 1
    return out


class ViewIsEditWithoutControls(F.Family):
    def check(self, width):
        for dark in (False, True):
            with self.subTest(width=width, theme="dark" if dark else "light"):
                got = self.read(width, dark, F.READ_JS)
                self.assertEqual(sorted(got["view"]), sorted(got["edit"]), "the same 24 templates in both")
                self.assertEqual(len(got["view"]), 24)
                for tid, view in got["view"].items():
                    edit = got["edit"][tid]
                    with self.subTest(template=tid):
                        self.assertIsNotNone(view, f"{tid}: View draws the section")
                        self.assertIsNotNone(edit, f"{tid}: Edit draws the section")
                        self.assertEqual(view["type"], edit["type"], f"{tid}: View and Edit draw the same kind of section")
                        self.assertTrue(view["words"], f"{tid}: View shows words")
                        self.assertTrue(any(c.startswith("div.sec-ctl") or c.startswith("button.handle") for c in edit["controls"]), f"{tid}: Edit has its controls")
                        self.assertEqual(counts(view["controls"]), FINDINGS.get(tid, {}), f"{tid}: controls in View (a finding when listed in FINDINGS)")

    def test_view_holds_no_control_at_1400(self):
        self.check(1400)

    def test_view_holds_no_control_at_900(self):
        self.check(900)


if __name__ == "__main__":
    unittest.main()
