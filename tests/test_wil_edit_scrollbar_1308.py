"""Row 1308: a scrolling work-item list shows no scroll bar in Edit either (Classic only; Cards keeps what it has).

Run: python3 dev/run_tests.py test_wil_edit_scrollbar_1308
Row 1195 hid the bar in View only; the ticket asks for none visible, scrolling still working. The Edit rule is in the Classic
theme layer (src/clark/themes/prototype-2.0/rules.css); shell.css and edit.css are untouched.
"""
import re
import unittest

import test_server  # noqa: F401  this file drives Chrome through the template harness (the browser tier reads this line)

from _paths import SRC
import test_tpl_workitems as T
import test_work_items_mockup_1195 as M

RULES = ((SRC / "clark" / "themes" / "prototype-2.0" / "rules.css").read_text(encoding="utf-8") + (SRC / "clark" / "themes" / "prototype-2.0" / "rules-2.css").read_text(encoding="utf-8"))
EDIT_RULES = [
    '#report[data-mode="edit"] .wil-scroll { scrollbar-width: none; }',
    '#report[data-mode="edit"] .wil-scroll::-webkit-scrollbar { display: none; }',
]
LIST = {"mode": "all", "max": 2, "columns": ["id", "owner"], "owner": ["Pat Demo", "Lee Demo"]}


def probe(sec):
    return (f"(() => {{ const e = document.querySelector('{sec} .wil-scroll'); return [getComputedStyle(e).scrollbarWidth, "
            f"e.scrollHeight > e.clientHeight, e.offsetWidth - e.clientWidth, e.tabIndex, getComputedStyle(e).overflowY]; }})()")


class Source(unittest.TestCase):
    def test_the_edit_rules_are_in_the_classic_layer_between_the_1318_block_and_the_1314_block(self):
        norm = lambda s: re.sub(r"\s+", " ", s).strip()
        lines = [norm(x) for x in RULES.splitlines()]
        for want in EDIT_RULES:
            self.assertIn(norm(want), lines)
        at = lines.index(norm(EDIT_RULES[0]))
        self.assertGreater(at, next(i for i, x in enumerate(lines) if x.startswith("/* Row 1318")))
        self.assertLess(at, next(i for i, x in enumerate(lines) if x.startswith("/* Row 1314")))


class Classic(M.Look):
    def test_view_and_edit_show_no_scroll_bar_and_still_scroll_at_1400_and_900(self):
        ref = self.add(LIST)
        for width in (1400, 900):
            with T.chrome() as cdp:
                p = self.show(cdp, width)
                sec = f'[data-id="{ref}"]'
                p.until(f"!!document.querySelector('{sec} .wil-scroll')", "View drew")
                width_v, scrolls, bar, tab, ov = p.js(probe(sec))
                self.assertEqual((width_v, scrolls, bar, tab, ov), ("none", True, 0, 0, "auto"), f"View {width}")
                p.edit()
                p.until(f"!!document.querySelector('{sec} .wil-scroll') && document.querySelector('#report').dataset.mode === 'edit'", "Edit drew")
                width_e, scrolls, bar, tab, ov = p.js(probe(sec))
                self.assertEqual((width_e, scrolls, bar, tab, ov), ("none", True, 0, 0, "auto"), f"Edit {width}")
                p.js(f"document.querySelector('{sec} .wil-scroll').scrollTop = 40")
                self.assertGreater(p.js(f"document.querySelector('{sec} .wil-scroll').scrollTop"), 0, f"Edit still scrolls at {width}")


class Cards(M.Look):
    classic = False

    def test_cards_keeps_its_scroll_bar_setting_in_view_and_edit_at_1400_and_900(self):
        ref = self.add(LIST)
        for width in (1400, 900):
            with T.chrome() as cdp:
                p = self.show(cdp, width)
                sec = f'[data-id="{ref}"]'
                p.until(f"!!document.querySelector('{sec} .wil-scroll')", "View drew")
                self.assertEqual(p.js(probe(sec))[0], "auto", f"Cards View {width}")
                p.edit()
                p.until(f"!!document.querySelector('{sec} .wil-scroll') && document.querySelector('#report').dataset.mode === 'edit'", "Edit drew")
                self.assertEqual(p.js(probe(sec))[0], "auto", f"Cards Edit {width}")


if __name__ == "__main__":
    unittest.main()
