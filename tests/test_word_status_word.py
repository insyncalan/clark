"""Row 1021: the Word copy carries each item's status as the same WORD the page shows.

Run: python3 dev/run_tests.py test_word_status_word
The ruling: the published file, the PDF and the Word copy always carry the item status as a word, the same word the page shows.
On the page (logic/sectionRows.js clientPill over workItems.pillOf): an action reads Overdue, Delayed, Due soon or On track; a risk
or issue reads Red, Amber or Green (its priority); a decision reads Pending, Made or Withdrawn. The rule is written once in Python
(glance.client_pill) and pinned here against the page's own JS, case by case, run by Node. Source and Activity text never reach the file.
"""
import copy
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

from _paths import SRC  # noqa: F401  (puts src/ on the path)

import test_docx_build as t
from clark import docx_build, glance
from test_work_items import bundled

SECTION_ROWS = SRC / "clark" / "page" / "src" / "logic" / "sectionRows.js"
TODAY = "2026-10-28"


def word_status(mutate):
    """The Status word of every action and raid row in the Word copy, by id."""
    plant = t.fx.load()
    mutate(plant["data"])
    blocks = t.blocks(docx_build.build(t.published(plant)))
    out = {}
    for b in blocks:
        if b["kind"] == "table" and b["rows"] and b["rows"][0][-1] == "Status" and b["rows"][0][0] in ("ID", "Id"):
            out.update({r[0]: r[-1] for r in b["rows"][1:]})
    return out


def edit(table, ident, **fields):
    def go(data):
        for r in data[table]:
            if r["id"] == ident:
                r.update(fields)
    return go


def several(*fns):
    return lambda d: [f(d) for f in fns]


class WordCarriesThePageWord(unittest.TestCase):
    def test_an_overdue_action_says_Overdue(self):
        self.assertEqual(word_status(edit("actions", "PUB-A-001", due_date="2026-10-20"))["PUB-A-001"], "Overdue")

    def test_a_delayed_action_not_yet_late_says_Delayed(self):
        self.assertEqual(word_status(edit("actions", "PUB-A-001", status="Delayed", due_date="2026-12-20"))["PUB-A-001"], "Delayed")

    def test_an_action_due_within_a_week_says_Due_soon(self):
        self.assertEqual(word_status(edit("actions", "PUB-A-001", due_date="2026-10-30"))["PUB-A-001"], "Due soon")

    def test_an_action_with_time_in_hand_says_On_track(self):
        self.assertEqual(word_status(edit("actions", "PUB-A-001", due_date="2026-12-20"))["PUB-A-001"], "On track")

    def test_a_plain_status_reads_On_track_but_an_own_status_keeps_its_word(self):
        """Option B: On track only where the record is open, not late/delayed/due soon and its status is plain (Open, Planned, none)."""
        for status, word in (("Open", "On track"), ("Planned", "On track"), (None, "On track"), ("Blocked", "Blocked"), ("In progress", "In progress")):
            self.assertEqual(word_status(edit("actions", "PUB-A-001", status=status, due_date="2026-12-20"))["PUB-A-001"], word, status)

    def test_an_own_status_wins_over_late_and_due_soon_but_not_over_delayed_or_closed(self):
        self.assertEqual(word_status(edit("actions", "PUB-A-001", status="Blocked", due_date="2026-10-20"))["PUB-A-001"], "Blocked")
        self.assertEqual(word_status(edit("actions", "PUB-A-001", status="In progress", due_date="2026-10-30"))["PUB-A-001"], "In progress")
        self.assertEqual(word_status(edit("actions", "PUB-A-001", status="Delayed", due_date="2026-12-20"))["PUB-A-001"], "Delayed")

    def test_a_risk_with_its_own_status_keeps_the_word_and_a_plain_one_reads_its_colour(self):
        self.assertEqual(word_status(edit("raid", "PUB-001", status="Blocked", priority="Low"))["PUB-001"], "Blocked")
        self.assertEqual(word_status(edit("raid", "PUB-001", status="Open", priority="Low"))["PUB-001"], "Green")

    def test_the_cell_colours_follow_the_final_rule(self):
        """Blocked is amber, In progress green, On track green; the cell holds the word."""
        def cell_fill(status, word):
            plant = t.fx.load()
            edit("actions", "PUB-A-001", status=status, due_date="2026-12-20")(plant["data"])
            doc = t.parts(docx_build.build(t.published(plant)))["word/document.xml"].decode("utf-8")
            cells = [c for c in re.findall(r"<w:tc>(?:(?!</w:tc>).)*</w:tc>", doc, re.S) if f">{word}<" in c]
            self.assertTrue(cells, word)
            return cells[0]
        for status, word, tone in (("Blocked", "Blocked", "amber"), ("In progress", "In progress", "green"), ("Open", "On track", "green")):
            c = cell_fill(status, word)
            self.assertIn(f'w:fill="{docx_build.TOKENS["tone-" + tone + "-tint"]}"', c, word)
            self.assertIn(docx_build.TOKENS["tone-" + tone + "-text"], c, word)

    def test_the_risks_table_uses_the_pages_header_words(self):
        plant = t.fx.load()
        heads = [b["rows"][0] for b in t.blocks(docx_build.build(t.published(plant))) if b["kind"] == "table" and b["rows"][0][:2] == ["Id", "Type"]]
        self.assertEqual(len(heads), 1)
        for w in ("Id", "Title", "Review by"):
            self.assertIn(w, heads[0])
        for w in ("ID", "Item", "Due"):
            self.assertNotIn(w, heads[0])

    def test_a_risk_says_Red_Amber_or_Green_by_priority(self):
        for priority, word in (("Urgent", "Red"), ("High", "Red"), ("Medium", "Amber"), ("Low", "Green")):
            self.assertEqual(word_status(edit("raid", "PUB-001", priority=priority))["PUB-001"], word, priority)

    def test_a_priority_that_is_not_text_reads_Not_rated_and_does_not_break_the_build(self):
        """Hostile data (a list, a dict, a number) in a risk's priority: the Word build must not raise (unhashable list in a dict lookup)."""
        for bad in (["High"], {"a": 1}, 3, 1.5, True):
            with self.subTest(bad=bad):
                self.assertEqual(word_status(edit("raid", "PUB-001", priority=bad))["PUB-001"], "Not rated")

    def test_the_status_is_never_the_record_status_for_an_action_or_risk(self):
        got = word_status(lambda d: None)
        self.assertTrue(got)
        self.assertFalse({"Open"} & set(got.values()), got)

    def test_no_source_or_activity_text_reaches_the_file(self):
        plant = t.fx.load()
        for r in plant["data"]["actions"] + plant["data"]["raid"]:
            r["source"] = "ZQ-SOURCE-TEXT"
            r["activity"] = "ZQ-ACTIVITY-TEXT"
        text = t.every_text(docx_build.build(t.published(plant)))
        self.assertNotIn("ZQ-SOURCE-TEXT", text)
        self.assertNotIn("ZQ-ACTIVITY-TEXT", text)


CASES = []
for kind in ("action", "risk", "issue", "decision"):
    for status in ("Open", "Planned", "Blocked", "In progress", "Delayed", "Pending", "Made", "Withdrawn", "Closed", "Cancelled"):
        for priority in (None, "Urgent", "High", "Medium", "Low"):
            for due in (None, "2026-10-20", "2026-10-28", "2026-10-29", "2026-11-04", "2026-11-05", "2026-12-31", "soon"):
                CASES.append({"kind": kind, "status": status, "priority": priority, "due_date": due})


class ParityWithThePage(unittest.TestCase):
    def test_client_pill_matches_the_pages_clientPill_for_every_case(self):
        if shutil.which("node") is None:
            self.skipTest("node is not installed on this computer (CI has it)")
        script = bundled(SECTION_ROWS, "SR") + ";console.log(JSON.stringify(%s.map((r) => SR.clientPill(r, %s))))" % (json.dumps(CASES), json.dumps(TODAY))
        done = subprocess.run(["node", "-e", script], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        want = json.loads(done.stdout)
        self.assertEqual(len(want), len(CASES))
        for row, js in zip(CASES, want):
            self.assertEqual(glance.client_pill(copy.deepcopy(row), TODAY), {"text": js["text"], "class": js["class"]}, row)


if __name__ == "__main__":
    unittest.main()
