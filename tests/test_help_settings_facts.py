"""Help review of the Settings entries: the Settings reference table follows the cards the page draws, and the facts it states match the page.

Run: python3 dev/run_tests.py test_help_settings_facts
Quick tier: reads files, starts no browser.
"""
import re
import unittest

from _help_shown import LATER, RAW, shown_content
from _paths import ROOT

SRC = ROOT / "src" / "clark" / "page" / "src"
VIEWS = (SRC / "components" / "Views.jsx").read_text(encoding="utf-8")
SECTION = next(s for s in RAW["reference"]["sections"] if s["id"] == "settings")
ROWS = {r[0]: r[1] for r in SECTION["b"][1][2]}
PROFILE_TASK = next(t for t in RAW["howto"]["tasks"] if t["id"] == "set-your-profile")


def chips():
    """The chip name of each card, in the order the page draws them (Views.jsx CARDS), with the cards that bring their own name."""
    own = {"Update": "Version and updates", "Brands": "Brands", "Quit": "Quit"}
    block = re.search(r"const CARDS = \[(.*?)\];", VIEWS, re.S).group(1)
    return [name or own[tool] for tool, name, _ in re.findall(r'\["(\w+)", "([^"]*)", "([\w-]+)"\]', block)]


class TheSettingsTable(unittest.TestCase):
    def test_every_card_has_a_row_in_the_order_the_page_draws_them(self):
        want = chips()
        want.insert(want.index("Asking") + 1, "AI (under Asking)")      # the AI card is drawn straight after Asking and has no link of its own
        self.assertEqual(list(ROWS), want)

    def test_the_intro_lists_the_same_cards(self):
        intro = SECTION["b"][0][1]
        listed = intro.split("): ")[1].split(", in the order")[0].replace(", Feedback and Quit", ", Feedback, Quit").split(", ")
        self.assertEqual(listed, chips())

    def test_the_data_row_names_the_buttons_of_the_card(self):
        card = (SRC / "logic" / "dataCard.js").read_text(encoding="utf-8")
        words = re.findall(r'(?:export|import): "([^"]+)"', card.split("export const IMPORT =")[0])
        self.assertEqual(words, ["Export workbook", "Import workbook"])
        for word in words:
            self.assertIn(f"**{word}**", ROWS["Data"])
        self.assertNotIn("Export to Excel", ROWS["Data"])

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
        for name in re.findall(r"\*\*(.+?)\*\*", ROWS["Freshness"]):
            self.assertIn(name, fresh)
        for name in re.findall(r"\*\*(.+?)\*\*", ROWS["Gantt"]):
            self.assertIn(name, gantt)

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
