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
SCREENS = {"dashboard", "dashboard+edit", "work", "milestones", "settings", "publish", "preview", "ask"}


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


def strings(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for v in x.values():
            yield from strings(v)
    elif isinstance(x, (list, tuple)):
        for v in x:
            yield from strings(v)


def one(start):
    found = [t for t in strings(RAW) if t.startswith(start)]
    assert len(found) == 1, (start, len(found))
    return found[0]


class WorkItemsHelpMatchesTheCode(unittest.TestCase):
    def test_peek_top_bar_names_delete(self):
        self.assertIn("**Delete**", one("At the top: **Previous item** and **Next item**"))

    def test_right_click_menu_names_open_the_peek(self):
        text = one("The right-click menu has a small picture")
        row_menu = (SRC / "edit" / "RowMenu.jsx").read_text(encoding="utf-8")
        self.assertIn('name: "Open the peek"', row_menu)
        self.assertIn("Open the peek", text)

    def test_single_letter_keys_row_says_single_key_shortcuts_switch(self):
        row = next(r for r in RAW["reference"]["keys"] if isinstance(r, list) and "[[O]]" in r[0])
        self.assertIn("Single-key shortcuts is off", row[1])


if __name__ == "__main__":
    unittest.main()
