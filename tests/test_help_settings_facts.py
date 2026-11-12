"""Help review of the Settings entries: the Settings reference table follows the cards the page draws, and the facts it states match the page.

Run: python3 dev/run_tests.py test_help_settings_facts
Quick tier: reads files, starts no browser.
"""
import re
import unittest

from _help_shown import LATER, RAW, shown_content
from _paths import ROOT

SRC = ROOT / "src" / "clark" / "page" / "src"
PAGES = (SRC / "edit" / "settingsPages.js").read_text(encoding="utf-8")
SECTION = next(s for s in RAW["reference"]["sections"] if s["id"] == "settings")
ROWS = {r[0]: r[1] for r in SECTION["b"][1][2]}
PROFILE_TASK = next(t for t in RAW["howto"]["tasks"] if t["id"] == "set-your-profile")


def chips():
    """The name of each Settings page, in the order the menu draws them (edit/settingsPages.js GROUPS), then Quit, which the Version and updates page carries."""
    return re.findall(r'\["[\w-]+", "([^"]*)", \[', PAGES) + ["Quit"]


class TheSettingsTable(unittest.TestCase):
    def test_every_page_has_a_row_in_the_order_the_menu_draws_them(self):
        want = [n for n in chips() if n != "Claude and AI"]
        i = want.index("Logs and diagnostics")
        want[i:i] = ["Brands", "AI (on Claude and AI)"]      # Help keeps a Brands row (the zip and Downloads review) after Export and import, and one AI row for the Claude and AI page
        self.assertEqual(list(ROWS), want)

    def test_the_intro_lists_the_same_pages(self):
        intro = SECTION["b"][0][1]
        for name in chips():
            if name != "Quit":
                self.assertIn(name, intro)

    def test_the_export_row_names_the_buttons_of_the_card(self):
        card = (SRC / "logic" / "dataCard.js").read_text(encoding="utf-8")
        words = re.findall(r'(?:export|import): "([^"]+)"', card.split("export const IMPORT =")[0])
        self.assertEqual(words, ["Export workbook", "Import workbook"])
        for word in words:
            self.assertIn(f"**{word}**", ROWS["Export and import"])
        self.assertNotIn("Export to Excel", ROWS["Export and import"])

    def test_the_profile_card_has_the_three_boxes_it_has(self):
        """The Profile card holds Your name, Alias and Your email: no phone number and no organisation."""
        text = " ".join(PROFILE_TASK["s"]) + " " + ROWS["Profile"]
        for word in ("Phone", "Organisation"):
            self.assertNotIn(word, text)
        for word in ("**Your name**", "**Alias**", "**Your email**"):
            self.assertIn(word, text)

    def test_the_freshness_and_gantt_rows_quote_the_cards(self):
        fresh = (SRC / "edit" / "ReviewDays.jsx").read_text(encoding="utf-8")
        gantt = (SRC / "edit" / "GanttSetting.jsx").read_text(encoding="utf-8")
        row = ROWS["Reports"]
        names = re.findall(r"\*\*(.+?)\*\*", row)
        self.assertIn("**Not reviewed after (days)**", row)
        for name in names:
            self.assertTrue(name in fresh or name in gantt, name)

    def test_the_diagnostics_row_names_the_log_buttons(self):
        diag = (SRC / "edit" / "Diagnostics.jsx").read_text(encoding="utf-8")
        for name in re.findall(r"\*\*(.+?)\*\*", ROWS["Logs and diagnostics"]):
            self.assertIn(f">{name}<", diag)

    def test_the_settings_entries_are_released(self):
        shown = shown_content()
        ids = {x["id"] for x in shown["reference"]["sections"]}
        tasks = {x["id"] for x in shown["howto"]["tasks"]}
        self.assertTrue({"settings", "people", "updating-clark"} <= ids)
        self.assertTrue({"change-the-layout-and-look", "set-up-a-project", "set-your-profile", "add-people-details", "update-clark"} <= tasks)
        self.assertEqual(sorted(set(LATER["reference"]) & {"settings", "people", "updating-clark"}), [])


if __name__ == "__main__":
    unittest.main()
