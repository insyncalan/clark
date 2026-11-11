"""Help reference: the Publishing entry is shown (it was held for the Publish box, which the page has).

Run: python3 dev/run_tests.py test_help_publishing_released
Quick tier: reads files, starts no browser.
"""
import re
import unittest

from _help_shown import LATER, shown_content
from _paths import ROOT

PUBLISH_JSX = (ROOT / "src" / "clark" / "page" / "src" / "edit" / "Publish.jsx").read_text(encoding="utf-8")


def entry():
    return next((s for s in shown_content()["reference"]["sections"] if s["id"] == "publishing"), None)


class PublishingReleased(unittest.TestCase):
    def test_the_entry_is_not_held(self):
        self.assertNotIn("publishing", LATER["reference"])

    def test_the_entry_is_shown_in_the_publishing_group_before_published_reports(self):
        ids = [s["id"] for s in shown_content()["reference"]["sections"] if s["g"] == "Publishing"]
        self.assertEqual(ids[:2], ["publishing", "published-reports"])

    def test_every_tick_it_names_is_a_label_of_the_publish_box(self):
        e = entry()
        self.assertIsNotNone(e)
        text = " ".join(str(b) for b in e["b"])
        names = re.findall(r"\*\*(.+?)\*\*", text)
        self.assertIn("Local", names)
        for n in names:
            if n.rstrip(":") != "Preview the page in a new tab":
                self.assertIn(n.rstrip(":"), PUBLISH_JSX, n)


if __name__ == "__main__":
    unittest.main()
