"""Help coverage of the rows merged on 10-11 to 12-11 (queue item 8): the Work items entry tells where archived work went, with the owner's own sentence,
and every place Help points at (a link, a Next entry, a Settings card, a screen) is one the page has.

Run: python3 dev/run_tests.py test_help_gaps
Quick tier: reads files, starts no browser.
"""
import re
import unittest

from _help_shown import RAW, shown_content
from _paths import ROOT

SRC = ROOT / "src" / "clark" / "page" / "src"
ARCHIVED = "Archived work is not in the list. To see it, type is:archived on the filter line."
WORK_ITEMS = next(s for s in RAW["reference"]["sections"] if s["id"] == "work-items")
SCREENS = {"dashboard", "dashboard+edit", "work", "milestones", "usecases", "settings", "publish", "preview", "ask"}


def paragraphs(section):
    return [x for block in section["b"] if block[0] == "p" for x in block[1:]]


def places():
    return ({"howto-" + t["id"] for t in RAW["howto"]["tasks"]} | {"ref-" + t["id"] for t in RAW["reference"]["sections"]}
            | {"guide-" + g["id"] for g in RAW["guides"]})


class ArchivedWork(unittest.TestCase):
    def test_work_items_says_where_archived_work_went(self):
        self.assertIn(ARCHIVED, paragraphs(WORK_ITEMS))

    def test_the_page_has_the_filter_word_the_sentence_names(self):
        self.assertRegex((SRC / "logic" / "filterLine.js").read_text(encoding="utf-8"), r'archived: "Archived work"')

    def test_the_entry_is_shown_not_held(self):
        self.assertIn("work-items", {s["id"] for s in shown_content()["reference"]["sections"]})


class EveryPlaceHelpPointsAtExists(unittest.TestCase):
    def test_links_and_next_entries_name_an_entry_that_is_there(self):
        import json
        text = json.dumps(RAW, ensure_ascii=False)
        known = places()
        for link in set(re.findall(r"\]\(#([a-z0-9-]+)\)", text)):
            self.assertIn(link, known, f"a link to {link}: no such entry")
        for task in RAW["howto"]["tasks"]:
            for n in task.get("next", []):
                self.assertIn(n, known, f"{task['id']} lists {n} as next: no such entry")

    def test_go_and_page_names_a_screen_or_a_settings_card_the_page_draws(self):
        views = (SRC / "components" / "Views.jsx").read_text(encoding="utf-8")
        cards = set(re.findall(r'"([\w-]+)-h"\]', views))      # profile, personal, update, people ...
        cards |= {re.sub(r"-card$", "", c) for c in cards}     # the Data card's heading is data-card-h; Help says settings#data
        for entry in RAW["howto"]["tasks"] + RAW["reference"]["sections"]:
            for where in [entry.get("go")] + entry.get("page", []):
                if not where:
                    continue
                screen, _, card = where.partition("#")
                self.assertIn(screen, SCREENS, f"{entry['id']}: {where}")
                if card:
                    self.assertIn(card, cards, f"{entry['id']}: {where}: no such Settings card")
        for c in RAW["context"]:
            self.assertIn(c["page"], SCREENS, c["page"])
            if c.get("full"):
                self.assertIn(c["full"], places())


if __name__ == "__main__":
    unittest.main()
