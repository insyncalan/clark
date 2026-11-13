"""Plan 1139: the words of a status icon (components/ItemRows.jsx iconWords, statusWord): an Urgent item says Urgent, never Red as well.

Run: python3 dev/run_tests.py test_icon_words_node
Quick tier: no browser. Bundled by the pinned esbuild and run in node (skipped when node is not on the machine).
The rule: only the colour word (Red, Amber, Green) gives way to Urgent; the item's own status words (Blocked, In progress, Delayed,
Overdue, Pending ...) stay, in the order they had. A rule for an item that is not Urgent is unchanged. All rows are fictional.
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT, SRC, TOOLS

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402

ENTRY = ROOT / "tests" / "fixtures" / "iconwords_node.js"
PAGE_SRC = SRC / "clark" / "page" / "src"
_BUNDLE = {}
TODAY = "2026-11-10"
SHIM = "globalThis.addEventListener = () => {}; globalThis.removeEventListener = () => {};\n"      # the page's stores listen to the window; node has none
PAST, FUTURE = "2026-11-01", "2026-11-30"


def bundle():
    if "code" not in _BUNDLE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "iw.js"
            done = esbuild.run(["--bundle", "--format=iife", "--global-name=IW", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(ENTRY), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            _BUNDLE["code"] = out.read_text(encoding="utf-8")
    return _BUNDLE["code"]


def words(row, pill=None):
    """The tooltip, the accessible name and the visible word for a row, with the pill the page works out unless one is given."""
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    probe = ("(() => { const row = %s, pill = %s || IW.clientPill(row, %s); const w = IW.iconWords(row, pill, %s);"
             " return {tip: w.tip, name: w.name, word: IW.statusWord(row, pill)}; })()") % (json.dumps(row), json.dumps(pill), json.dumps(TODAY), json.dumps(TODAY))
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "probe.js"
        script.write_text(SHIM + bundle() + ";\nconsole.log(JSON.stringify(" + probe + "));", encoding="utf-8")
        done = subprocess.run([node, str(script)], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout)


def item(kind, **kw):
    base = {"kind": kind, "status": "Open", "priority": None, "due_date": FUTURE}
    base.update(kw)
    return base


class UrgentSaysUrgentOnce(unittest.TestCase):
    def test_an_urgent_risk_that_is_not_overdue_says_urgent_and_not_red(self):
        w = words(item("risk", priority="Urgent"))
        self.assertEqual((w["tip"], w["name"], w["word"]), ("Risk · Urgent", "Risk, Urgent", "Urgent"))

    def test_an_urgent_overdue_risk_says_urgent_then_overdue(self):
        w = words(item("risk", priority="Urgent", due_date=PAST))
        self.assertEqual((w["tip"], w["word"]), ("Risk · Urgent · Overdue", "Urgent"))

    def test_an_urgent_blocked_action_keeps_blocked(self):
        w = words(item("action", priority="Urgent", status="Blocked"))
        self.assertEqual((w["tip"], w["word"]), ("Action · Blocked · Urgent", "Blocked"))
        self.assertEqual(words(item("action", priority="Urgent", status="Blocked", due_date=PAST))["tip"], "Action · Blocked · Urgent · Overdue")

    def test_an_urgent_in_progress_action_keeps_in_progress(self):
        self.assertEqual(words(item("action", priority="Urgent", status="In progress"))["tip"], "Action · In progress · Urgent")

    def test_an_urgent_delayed_action_keeps_delayed(self):
        w = words(item("action", priority="Urgent", status="Delayed"))
        self.assertEqual((w["tip"], w["word"]), ("Action · Delayed · Urgent", "Delayed"))

    def test_an_urgent_overdue_action_keeps_its_order_overdue_then_urgent(self):
        w = words(item("action", priority="Urgent", due_date=PAST))
        self.assertEqual((w["tip"], w["word"]), ("Action · Overdue · Urgent", "Overdue"))

    def test_an_urgent_decision_keeps_pending(self):
        w = words(item("decision", priority="Urgent", status="Pending", needed_by=FUTURE))
        self.assertEqual((w["tip"], w["name"], w["word"]), ("Decision · Pending · Urgent", "Decision, Pending, Urgent", "Pending"))

    def test_an_urgent_item_given_an_amber_or_green_colour_word_loses_the_colour_word_too(self):
        for colour in ("Amber", "Green"):
            w = words(item("issue", priority="Urgent"), {"text": colour, "class": colour[0].lower()})
            self.assertEqual((w["tip"], w["word"]), ("Issue · Urgent", "Urgent"), colour)
            self.assertNotIn(colour, w["name"])

    def test_a_risk_that_is_not_urgent_still_says_its_colour(self):
        for priority, colour in (("High", "Red"), ("Medium", "Amber"), ("Low", "Green")):
            w = words(item("risk", priority=priority, due_date=PAST))
            self.assertEqual((w["tip"], w["word"]), ("Risk · " + colour, colour), priority)
            self.assertNotIn("Urgent", w["name"])

    def test_a_completed_urgent_item_is_not_urgent(self):
        w = words(item("action", priority="Urgent", status="Completed"))
        self.assertNotIn("Urgent", w["tip"])


if __name__ == "__main__":
    unittest.main()
