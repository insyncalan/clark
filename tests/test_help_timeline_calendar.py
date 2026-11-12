"""Help section timeline-calendar says what the timeline label and the list line really show.

Run: python3 dev/run_tests.py test_help_timeline_calendar
No browser: it reads src/clark/page/src/help/helpContent.json.
"""
import json
import pathlib
import unittest

HELP = pathlib.Path(__file__).resolve().parent.parent / "src/clark/page/src/help/helpContent.json"


def section():
    data = json.loads(HELP.read_text(encoding="utf-8"))
    for s in data["reference"]["sections"]:
        if s["id"] == "timeline-calendar":
            return json.dumps(s, ensure_ascii=False)
    raise AssertionError("section missing")


class TimelineCalendarHelp(unittest.TestCase):
    def test_label_wording_matches_the_page(self):
        t = section()
        self.assertNotIn("its label reads, for example, 3 days later, then Expected and the date", t)
        self.assertIn("its label adds, for example, +3 days", t)
        self.assertIn("the list below gives the Expected date and how many days later", t)

    def test_reset_is_said_to_appear_after_zooming(self):
        self.assertIn("**Reset** (shown once you have zoomed)", section())


if __name__ == "__main__":
    unittest.main()
