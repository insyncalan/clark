"""Settings > People with 300 people and the longest names and emails the card accepts, at 900 px in a real browser: the table and the paste
preview wrap inside the card, the page has no sideways scroll, and the focus lands on Paste from Excel after an add.
Run: python3 dev/run_tests.py test_people_many_long_900     Chrome is required: fails, never skips."""
import json
import unittest

import test_people_card as base
from test_page import navigate
from test_server import chrome, wait

from clark import store as st

LONG_NAME = "N" * 120
LONG_EMAIL = "e" * 64 + "@" + "d" * 60 + ".example.com"
LOOK = """(() => {
  const card = document.querySelector('#people').getBoundingClientRect();
  const wide = [...document.querySelectorAll('#people table, #people td, #people th')].filter(e => e.getBoundingClientRect().right > card.right + 1).length;
  return {page: document.documentElement.scrollWidth - window.innerWidth, wide: wide, rows: document.querySelectorAll('#ppTable tbody tr').length};
})()"""


class ManyLong(base.PeopleCard):
    def setUp(self):
        super().setUp()
        store = st.open_store(self.db, onedrive_roots=[])
        with store.step("dashboard", "tester", place="menu") as s:
            for i in range(297):
                s.add_person(name=(f"{i:03d}" + LONG_NAME)[:120], email=f"{i:03d}" + LONG_EMAIL[3:], organisation="O" * 100, role="R" * 100, source="test")
        store.close()

    test_the_card_has_the_prototypes_words_table_and_count_line_at_both_widths = None      # the inherited tests are not this file's
    test_paste_from_excel_previews_adds_in_one_step_and_one_undo_takes_it_back = None
    test_keys_escape_in_the_paste_box_folds_it_away_and_the_focus_goes_back_to_the_button = None
    test_a_bad_row_is_named_in_plain_words_and_nothing_is_added = None

    def test_300_long_people_wrap_at_900_and_focus_returns_after_add(self):
        with chrome() as cdp:
            js = self.show(cdp)
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": 900, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
            self.assertTrue(wait(lambda: js("document.querySelectorAll('#ppTable tbody tr').length") >= 300, 20))
            look = js(LOOK)
            self.assertLessEqual(look["page"], 0, "no sideways page scroll with 300 long people")
            self.assertEqual(look["wide"], 0, "every cell stays inside the card")
            js("document.querySelector('#ppPasteBtn').click()")
            rows = "\n".join(f"P{i}{LONG_NAME[:110]}\t{i}{LONG_EMAIL[len(str(i)):]}\t{'O' * 100}\t{'R' * 100}" for i in range(40))
            self.fill(js, rows)
            self.assertTrue(wait(lambda: js("!!document.querySelector('#ppPreview')"), 10))
            look = js(LOOK)
            self.assertLessEqual(look["page"], 0, "no sideways scroll with the long preview open")
            self.assertEqual(look["wide"], 0, "the preview stays inside the card")
            js("document.querySelector('#ppAdd').click()")
            self.assertTrue(wait(lambda: js("document.querySelectorAll('#ppTable tbody tr').length") >= 340, 20))
            self.assertTrue(wait(lambda: js("document.activeElement && document.activeElement.id") == "ppPasteBtn", 5), "focus returns to Paste from Excel after an add")
            self.assertLessEqual(js(LOOK)["page"], 0)


if __name__ == "__main__":
    unittest.main()
