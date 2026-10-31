"""Tech debt #222: the Publish dialog lists no incomplete or stale items, and shows no sentence about them.

Run: python3 dev/run_tests.py test_publish_no_warnings
Part 1 (no browser): Publish.jsx no longer holds the warning words, the helper module or its styles, and the published file (page-view.html)
holds none of the old words or styles. Part 2: a project with open items that have no owner, no date and no review opens the real dialog
(the publish rig over a plant with such items) at 1400 and 900 px, light and dark: none of those words, no Show them link, and Publish is
never blocked. Part 3: every line the dialog shows is plain words: no jargon and no sentence that starts with the product name.
Chrome is required for parts 2 and 3: they fail, never skip, without it. The Freshness filter (#119, #159) is unchanged and its own tests
still run.
"""
import re
import unittest
from pathlib import Path
from unittest import mock

import _publish_fixture as fx
from _paths import SRC  # noqa: F401  (puts src/ on the path)
from test_publish_dialog import Base, WIDTHS
from test_server import chrome

from clark import page

PAGE_SRC = SRC / "clark" / "page" / "src"
GONE = ("Show them", "no owner or no date", "have not been reviewed", "has not been reviewed", "publishCheck", "pub-fresh", "ANYWAY",
        "publish anyway")
REAL_LOAD = fx.load
JARGON = re.compile(r"(?i)\(\{reason\}\)|\bpath\b|\brequest\b|true or false|\btag\b|\battribute\b|\bstylesheet\b|\bcss\b|tokens\.css|"
                    r"\bkey of this session|permission denied|errno|oserror|\bjson\b|\bapi\b|\bhttp\b")


def planted():
    """The publish plant with open items that have no owner and no date, one closed and one archived (never listed before)."""
    plant = REAL_LOAD()
    for r in plant["data"]["actions"]:
        if r["id"] == "PUB-A-001":
            r["owner"] = "TBC"
        elif r["id"] == "PUB-A-002":
            r["due_date"] = None
        elif r["id"] == "PUB-A-014":
            r.update(status="Closed", owner="TBC", due_date=None)
        elif r["id"] == "PUB-A-016":
            r.update(owner="TBC", due_date=None)
    return plant


class SourceAndFile(unittest.TestCase):
    def test_the_dialog_code_has_no_stale_or_incomplete_list(self):
        source = (PAGE_SRC / "edit" / "Publish.jsx").read_text(encoding="utf-8")
        for words in GONE:
            self.assertNotIn(words, source, words)
        self.assertFalse((PAGE_SRC / "edit" / "publishCheck.js").exists(), "the helper module is gone")

    def test_the_published_file_holds_none_of_it(self):
        view = page.VIEW_PAGE.read_text(encoding="utf-8")
        for words in GONE:
            self.assertNotIn(words, view, words)
        edit = page.PAGE.read_text(encoding="utf-8")
        for words in ("Show them", "no owner or no date", "pub-fresh"):
            self.assertNotIn(words, edit, words)


class Dialog(Base):
    def setUp(self):
        with mock.patch.object(fx, "load", planted):
            super().setUp()

    def test_the_dialog_says_nothing_about_incomplete_or_stale_items_and_never_blocks(self):
        with chrome() as cdp:
            p = self.page(cdp, "#dashboard&p=PUB")
            for w in WIDTHS:
                for scheme in ("light", "dark"):
                    cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, p.sid)
                    p.width(w)
                    p.open_publish()
                    where = f"{w} px, {scheme}"
                    text = p.dialog_text()
                    for words in ("Show them", "no owner or no date", "not been reviewed", "anyway"):
                        self.assertNotIn(words, text, f"{where}: {words}")
                    self.assertEqual(p.js("document.querySelectorAll('#pub-fresh, [data-fresh], [data-show]').length"), 0, where + ": no list, no link")
                    self.assertFalse(p.js("document.querySelector('[data-go]').disabled"), where + ": Publish is never blocked")
                    self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"), where + ": no sideways scroll")
                    p.js("document.querySelector('[data-cancel]').click()")
                    p.until("!document.querySelector('#publish-dialog')", "the dialog closed")

    def test_every_line_the_dialog_shows_is_plain_words(self):
        with chrome() as cdp:
            p = self.page(cdp, "#dashboard&p=PUB")
            p.open_publish()
            lines = [x.strip() for x in p.dialog_text().splitlines() if x.strip()]
            self.assertTrue(lines)
            for line in lines:
                self.assertIsNone(JARGON.search(line), f"jargon in the dialog: {line}")
                for sentence in re.split(r"(?<=[.!?])\s+", line):
                    self.assertFalse(sentence.lower().startswith("clark "), f"a sentence starts with the product name: {sentence}")


if __name__ == "__main__":
    unittest.main()
