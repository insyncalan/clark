"""#1195 S5: the half-circle icon before the status word on the live Work items page, coloured as the status pill.

Run: python3 dev/run_tests.py test_status_mark_1195
Quick tier: no browser. statusMark(row, pill) in workItems.js, bundled and run in node (skipped when node is not on the machine).
"""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT, SRC, TOOLS

import sys
sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402

ENTRY = ROOT / "tests" / "fixtures" / "statusmark_node.js"
PAGE_SRC = SRC / "clark" / "page" / "src"
_BUNDLE = {}
TODAY = "2026-11-17"


def bundle():
    if "code" not in _BUNDLE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "sm.js"
            done = esbuild.run(["--bundle", "--format=iife", "--global-name=SM", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(ENTRY), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            _BUNDLE["code"] = out.read_text(encoding="utf-8")
    return _BUNDLE["code"]


def mark(row, pill=None):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "probe.js"
        script.write_text(bundle() + ";\nconst row = %s; const pill = %s || SM.clientPill(row, %s); console.log(JSON.stringify(SM.statusMark(row, pill)));" % (json.dumps(row), json.dumps(pill), json.dumps(TODAY)),
                          encoding="utf-8")
        done = subprocess.run([node, str(script)], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout)


def action(status, due):
    return {"kind": "action", "status": status, "due_date": due, "priority": "Medium"}


class StatusMark(unittest.TestCase):
    def test_open_action_past_its_date_is_red(self):
        self.assertEqual(mark(action("Open", "2026-11-10")), {"word": "Overdue", "tone": "r"})

    def test_due_within_seven_days_is_amber(self):
        self.assertEqual(mark(action("Open", "2026-11-24"))["tone"], "a")
        self.assertEqual(mark(action("Open", "2026-11-17")), {"word": "Due soon", "tone": "a"})

    def test_eight_days_out_is_blue(self):
        self.assertEqual(mark(action("Open", "2026-11-25")), {"word": "On track", "tone": "b"})

    def test_delayed_is_amber(self):
        self.assertEqual(mark(action("Delayed", "2026-12-30")), {"word": "Delayed", "tone": "a"})

    def test_completed_is_green_and_reads_completed_even_past_its_date(self):
        self.assertEqual(mark(action("Completed", "2026-11-01")), {"word": "Completed", "tone": "g"})
        self.assertEqual(mark(action("Completed", "2026-12-30")), {"word": "Completed", "tone": "g"})

    def test_made_decision_is_green_pending_is_blue(self):
        self.assertEqual(mark({"kind": "decision", "status": "Made"}), {"word": "Made", "tone": "g"})
        self.assertEqual(mark({"kind": "decision", "status": "Pending"})["tone"], "b")

    def test_closed_cancelled_withdrawn_are_grey(self):
        self.assertEqual(mark(action("Closed", "2026-11-01")), {"word": "Closed", "tone": "n"})
        self.assertEqual(mark(action("Cancelled", "2026-11-01")), {"word": "Cancelled", "tone": "n"})
        self.assertEqual(mark({"kind": "decision", "status": "Withdrawn"}), {"word": "Withdrawn", "tone": "n"})

    def test_other_open_status_follows_the_pill(self):
        self.assertEqual(mark(action("Blocked", "2026-12-30")), {"word": "Blocked", "tone": "a"})   # the pill reads Blocked amber
        self.assertEqual(mark(action("In progress", "2026-12-30"))["tone"], "b")

    def test_risk_keeps_red_and_amber_else_blue(self):
        r = {"kind": "risk", "status": "Open", "priority": "High"}
        self.assertEqual(mark(r)["tone"], "r")
        self.assertEqual(mark(dict(r, priority="Low"))["tone"], "b")


ODD = {"text": "Elsewhere", "class": "n"}   # a pill whose word is not the status, so a mark that reads the pill instead of the status shows


class StatusMarkWordsAndSource(unittest.TestCase):
    def test_finished_and_closed_statuses_say_their_own_word_not_the_pills(self):
        for status, tone in (("Completed", "g"), ("Made", "g"), ("Closed", "n"), ("Cancelled", "n"), ("Withdrawn", "n")):
            with self.subTest(status=status):
                self.assertEqual(mark({"kind": "action", "status": status}, ODD), {"word": status, "tone": tone})

    def test_open_statuses_say_the_pills_word_and_its_red_or_amber(self):
        row = {"kind": "action", "status": "Open"}
        self.assertEqual(mark(row, {"text": "Elsewhere", "class": "r"}), {"word": "Elsewhere", "tone": "r"})
        self.assertEqual(mark(row, {"text": "Elsewhere", "class": "a"}), {"word": "Elsewhere", "tone": "a"})
        for cls in ("g", "n", "b"):
            self.assertEqual(mark(row, {"text": "Elsewhere", "class": cls})["tone"], "b", cls)

    def test_each_tone_has_its_own_colour_for_the_icon(self):
        css = (PAGE_SRC.parent / "shell.css").read_text(encoding="utf-8")
        for tone, name in (("r", "red"), ("a", "amber"), ("g", "green"), ("b", "blue"), ("n", "grey")):
            self.assertIn(".st-word.%s .sti { color: var(--tone-%s-text); }" % (tone, name), css)
        self.assertRegex(css, r"\.st-word \.sti \{[^}]*fill: none;[^}]*stroke: currentColor;")

    def test_status_column_is_wide_enough_for_icon_plus_word(self):
        shell = (PAGE_SRC.parent / "shell.css").read_text(encoding="utf-8")
        edit = (PAGE_SRC / "edit" / "edit.css").read_text(encoding="utf-8")
        self.assertIn("table.items .c-status { width: 156px; }", shell)
        self.assertIn("table.items .c-prio { width: 93px; } table.items .c-status { width: 146px; }", shell)
        self.assertIn("table.items .c-prio { width: 101px; } table.items .c-status { width: 146px; }", edit)

    def test_cell_draws_the_half_circle_after_the_icon_for_the_pill(self):
        jsx = (PAGE_SRC / "components" / "WorkItems.jsx").read_text(encoding="utf-8")
        self.assertIn('<span class={`st-word ${m.tone}`}><svg class="sti" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M12 3a9 9 0 0 1 0 18z" fill="currentColor" /></svg>{m.word}</span>', jsx)
        self.assertIn("const m = statusMark(row, pill);", jsx)
        self.assertEqual(jsx.count("<StatusWord row={row} pill={pill} />"), 1)
        i = jsx.index("<StatusWord row={row} pill={pill} />")
        td = jsx[jsx.rindex('<td class="c-status"', 0, i):i]
        self.assertIn("<ItemIcon", td, "the word follows the icon, inside the status cell")
        self.assertNotIn("</td>", td)


if __name__ == "__main__":
    unittest.main()
