"""Row 1089: Help has an entry (with its id) for the user-visible features of the rows merged on 11-11 that had none.

Run: python3 dev/run_tests.py test_help_gaps_11_11
Quick tier: reads files, starts no browser. Each case names the row, the Help id that must carry the words, and the page source that
makes the feature true, so a Help line cannot outlive the feature or be missing from it.
"""
import json
import re
import unittest

from _help_shown import LATER, shown_content
from _paths import ROOT

PAGE = ROOT / "src" / "clark" / "page" / "src"
SOURCE = json.loads((PAGE / "help" / "helpContent.json").read_text(encoding="utf-8"))
IDS = {"howto": {t["id"] for t in SOURCE["howto"]["tasks"]}, "reference": {s["id"] for s in SOURCE["reference"]["sections"]}}


def entry_text(kind, ident):
    items = SOURCE["howto"]["tasks"] if kind == "howto" else SOURCE["reference"]["sections"]
    return json.dumps([i for i in items if i["id"] == ident], ensure_ascii=False)


class HelpGaps(unittest.TestCase):
    def test_the_entries_exist_and_are_shown(self):
        for kind, ident in (("reference", "work-items"), ("reference", "status-words"), ("howto", "run-clark-with-docker")):
            self.assertIn(ident, IDS[kind])
            self.assertNotIn(ident, LATER.get(kind, {}), ident)
        self.assertTrue(shown_content()["reference"]["sections"])

    def test_row_1048_draft_email_says_where_the_to_line_comes_from(self):
        """The To line is the owner's email from the People list; with none it is left empty and the menu says so (logic/rowMenu.js)."""
        rowmenu = (PAGE / "logic" / "rowMenu.js").read_text(encoding="utf-8")
        self.assertIn("has no email on the People list, so the To line is left empty", rowmenu)
        text = entry_text("reference", "work-items")
        self.assertRegex(text, r"To line[^\"]{0,80}People")
        self.assertRegex(text, r"no email[^\"]{0,80}empty")

    def test_row_1021_report_rows_say_on_track_and_days_late(self):
        """An open action neither late, delayed nor due soon reads On track on the report's rows; a late one says how many days late."""
        rows = (PAGE / "logic" / "sectionRows.js").read_text(encoding="utf-8")
        self.assertIn('text: "On track", class: "g"', rows)
        self.assertIn("d late", rows)
        text = entry_text("reference", "status-words")
        self.assertRegex(text, r"On track[^\"]{0,200}(Open|action)")
        self.assertIn("d late", text)

    def test_row_1080_docker_says_it_comes_back_with_docker(self):
        """docker/compose.yaml restarts the container with Docker (unless-stopped); only the Stop line stops it for good."""
        compose = (ROOT / "docker" / "compose.yaml").read_text(encoding="utf-8")
        self.assertIn("unless-stopped", compose)
        text = entry_text("howto", "run-clark-with-docker")
        self.assertRegex(text, r"Docker Desktop[^\"]{0,120}(restart|starts? again|comes back)")


if __name__ == "__main__":
    unittest.main()
