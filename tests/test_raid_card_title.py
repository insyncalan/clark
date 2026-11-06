"""A published risk or issue card with no client wording still shows its title (and nothing owner-only).

Run: python3 dev/run_tests.py test_raid_card_title
A real project is published with RAID cards (three and four across) for a risk with an empty client wording, an issue with a
whitespace-only one, and a risk with a wording set. The finished file is opened in headless Chrome and each card's text is read as
drawn: the title is the heading once, the wording paragraph is there only when there are words, and the item's owner-only
response action never reaches the card. All rows are fictional.
"""
import json
import unittest

from _demo import USER
from _publish import PublishedFile
import test_glance_page as glance
from test_server import chrome

SECRET = "PRIVATEWORDSONLY"


class RaidCardTitle(PublishedFile, glance.Setup):
    def seed(self):
        rows = {}
        with self.store.step("dashboard", USER) as st:
            rows["empty"] = st.create("raid", {"project": "ABC", "type": "Risk", "description": "Kiln roof may leak", "raised": "2026-10-01",
                                               "source": "demo", "client_message": "", "response_action": SECRET})
            rows["blank"] = st.create("raid", {"project": "ABC", "type": "Issue", "description": "Harbour crane is down", "raised": "2026-10-01",
                                               "source": "demo", "client_message": "  \n ", "response_action": SECRET})
            rows["words"] = st.create("raid", {"project": "ABC", "type": "Risk", "description": "Tide table may change", "raised": "2026-10-01",
                                               "source": "demo", "client_message": "We are watching the tides.", "response_action": SECRET})
            for kind, n in (("raid3", 3), ("raid4", 4)):
                ref = st.create("report_sections", {"project": "ABC", "type": kind, "title": "Fictional cards %d" % n, "sort_order": 990 + n})
                st.update("report_sections", ref, {"body": json.dumps({"v": 1, "cards": [{"id": rows[k], "source": "client"} for k in ("empty", "blank", "words")]})})
        return rows

    def read(self, p):
        return p.js("""[...document.querySelectorAll('.raid-card')].map(c => ({
            text: c.textContent,
            titles: [...c.querySelectorAll('.raid-title')].map(e => e.textContent),
            words: [...c.querySelectorAll('.raid-text')].map(e => e.textContent)}))""")

    def test_an_empty_client_wording_still_shows_the_title(self):
        self.seed()
        path = self.publish()
        with chrome() as cdp:
            p = self.draw(cdp, path)
            cards = self.read(p)
        self.assertEqual(len(cards), 6, "three cards in each of the two sections")
        want = {"Kiln roof may leak": [], "Harbour crane is down": [], "Tide table may change": ["We are watching the tides."]}
        for c in cards:
            self.assertEqual(len(c["titles"]), 1, c)
            title = c["titles"][0].strip()
            self.assertIn(title, want, c)
            self.assertEqual(c["text"].count(title), 1, "the title is drawn once: " + c["text"])
            self.assertEqual([w.strip() for w in c["words"]], want[title], c)
            self.assertNotIn(SECRET, c["text"], "the owner-only response action is not in the card")
        self.assertEqual(sorted(c["titles"][0].strip() for c in cards), sorted(list(want) * 2))


if __name__ == "__main__":
    unittest.main()
