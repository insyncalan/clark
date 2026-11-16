"""Row 1222 review of the columns menu (PR 1663): the open items that are settled, each as an assertion on a real page.

Not here: the Columns button at 800 px and below (the issue does not say whether the stacked layout shows the extra columns).

Run: python3 dev/run_tests.py test_columns_review
"""
import json
import re
import unittest
from pathlib import Path

import test_table_columns as T
from clark import page
from test_server import chrome, wait
from test_inline_edits import tearDownModule  # noqa: F401

SRC = Path(page.__file__).parent / "src"


class Review(unittest.TestCase):
    setUp = T.Columns.setUp
    read = T.Columns.read
    visit = T.Columns.visit
    open_table = T.Columns.open_table
    right_click = T.Columns.right_click
    press = T.Columns.press
    menu = T.Columns.menu
    pick = T.Columns.pick

    def test_an_extra_milestone_cell_is_named_for_a_screen_reader(self):
        with chrome() as cdp:
            sid, js = self.open_table(cdp, 1400, "light", "milestones")
            self.right_click(cdp, sid, "#milestones .msl-hd [data-col='state']")
            self.assertTrue(wait(lambda: self.menu(js), 5))
            self.pick(js, "Owner")
            self.assertTrue(wait(lambda: js("!!document.querySelector('#milestones .msl-x[data-col=owner]')"), 5))
            got = js("""(() => { const c = document.querySelector('#milestones .msl-x[data-col=owner]'), row = c.closest('.msl-cells');
                return {label: row.getAttribute('aria-label'), role: row.getAttribute('role'), before: getComputedStyle(c, '::before').content, text: c.textContent}; })()""")
            self.assertEqual(got["role"], "button")
            self.assertIn(f"Owner {got['text']}", got["label"], f"the extra value {got['text']!r} is not in the row's name: {got}")

    def test_escape_gives_the_focus_back_to_what_opened_the_menu(self):
        for table, sel in (("work", "#work th[data-col='owner']"), ("milestones", "#milestones .msl-hd [data-col='state']")):
            with self.subTest(table=table), chrome() as cdp:
                sid, js = self.open_table(cdp, 1400, "light", table)
                self.right_click(cdp, sid, sel)
                self.assertTrue(wait(lambda: self.menu(js), 5))
                self.press(cdp, sid, "Escape")
                self.assertTrue(wait(lambda: not self.menu(js), 5))
                self.assertEqual(js("document.activeElement.tagName"), js(f"document.querySelector({json.dumps(sel)}).tagName"), f"focus is on {js('document.activeElement.outerHTML.slice(0, 60)')}")
                self.assertTrue(js(f"document.activeElement.matches({json.dumps(sel)})"))

    def test_every_word_constant_is_used(self):
        words = (SRC / "logic" / "columnsWords.js").read_text(encoding="utf-8")
        rest = "\n".join(p.read_text(encoding="utf-8") for p in SRC.rglob("*") if p.suffix in (".js", ".jsx") and p.name != "columnsWords.js")
        for name in re.findall(r"export const (UNRULED_\w+)", words):
            self.assertIn(name, rest, f"{name} is never used")


if __name__ == "__main__":
    unittest.main()
