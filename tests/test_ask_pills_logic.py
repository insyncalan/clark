"""Row 1332 (rows 1-8 of the plan): the pure pills(view, turns, help, state) in src/clark/page/src/edit/askPills.js.

Run: python3 dev/run_tests.py test_ask_pills_logic
Quick tier: no browser. The module is bundled by the pinned esbuild and run in node (skips without node).
Draft killers: they fail while askPills.js does not exist. The words are the words in askWords.js today and stand in for the ruled ones.
"""
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _paths import SRC

import esbuild  # noqa: E402  (dev/tools)

EDIT = SRC / "clark" / "page" / "src" / "edit"
PAGES = ("dashboard", "work", "milestones", "usecases", "gantt")


def probe(expr):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    entry = EDIT / "askPills.js"
    assert entry.is_file(), "row 1: askPills.js (the pure pills) does not exist"
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "ap.js"
        done = esbuild.run(["--bundle", "--format=iife", "--global-name=AP", str(entry), f"--outfile={out}"], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        script = Path(tmp) / "probe.js"
        script.write_text(out.read_text(encoding="utf-8") + ";\nconsole.log(JSON.stringify(" + expr + "));", encoding="utf-8")
        got = subprocess.run([node, str(script)], capture_output=True, text=True)
        assert got.returncode == 0, got.stderr
        return json.loads(got.stdout)


def pills(view, turns=(), help_open=False, state=None):
    args = [json.dumps(view), json.dumps(list(turns)), json.dumps(help_open)]
    if state is not None:
        args.append(json.dumps(state))
    return probe("AP.pills(" + ", ".join(args) + ")")


def user(text):
    return {"role": "user", "text": text}


def reply(text="Fine."):
    return {"role": "assistant", "text": text}


WORDS = (EDIT / "askWords.js").read_text(encoding="utf-8")


def subject_lists():
    block = WORDS[WORDS.index("export const PILLS_BY_SUBJECT = {"):]
    block = block[:block.index("\n};")]
    return {m.group(1): re.findall(r'"([^"]+)"', m.group(2)) for m in re.finditer(r"^  (\w+): \[(.*)\],$", block, re.M)}


def general():
    return re.findall(r'^  "(.+)",$', WORDS[WORDS.index("export const SUGGESTIONS = ["):].split("\n];")[0], re.M)


class Selection(unittest.TestCase):
    def test_each_page_gets_its_own_exact_list(self):
        lists = subject_lists()
        for page in PAGES:
            self.assertEqual(pills(page), lists[page], page)

    def test_a_page_without_a_list_keeps_the_general_suggestions(self):
        for page in ("settings", "file", ""):
            self.assertEqual(pills(page), general(), page)

    def test_the_last_question_names_the_subject_and_beats_the_page(self):
        lists = subject_lists()
        for text, subject in (("Any issues?", "risks"), ("Any tasks left?", "work"), ("Any use case stuck?", "usecases"), ("Which RISKS are red?", "risks"), ("Which milestones carry a risk?", "milestones")):
            self.assertEqual(pills("work", [user(text), reply()]), lists[subject], text)

    def test_only_the_last_user_question_counts_and_a_question_naming_nothing_falls_back_to_the_page(self):
        lists = subject_lists()
        self.assertEqual(pills("work", [user("Any risks?"), reply(), user("Thank you"), reply()]), lists["work"])
        self.assertEqual(pills("gantt", [user("Any risks?"), reply(), user("Any milestones?"), reply()]), lists["milestones"])
        self.assertEqual(pills("settings", [reply("Risks are red."), ]), general(), "an answer's own words do not name the subject")

    def test_it_is_pure(self):
        turns = [user("Any risks?"), reply()]
        self.assertEqual(probe("(function(){var t=" + json.dumps(turns) + ";var a=AP.pills('work',t,false);var b=AP.pills('work',t,false);return [a,b,t.length]})()"),
                         [subject_lists()["risks"], subject_lists()["risks"], 2])


class HelpSet(unittest.TestCase):
    def test_help_open_draws_its_own_set_not_the_fallback_and_not_the_page(self):
        lists = subject_lists()
        got = pills("work", [], True)
        self.assertNotEqual(got, general(), "row 7: Help must not fall back to the general list")
        self.assertNotEqual(got, lists["work"])
        self.assertTrue(got and len(got) <= 6)
        self.assertEqual(got, pills("dashboard", [], True), "the Help set does not depend on the page behind it")

    def test_help_beats_the_last_question(self):
        self.assertEqual(pills("work", [user("Any risks?"), reply()], True), pills("work", [], True))

    def test_the_help_set_is_a_named_export_in_the_words_file(self):
        self.assertIn("export const PILLS_HELP", WORDS)
        self.assertEqual(pills("work", [], True), re.findall(r'"([^"]+)"', WORDS[WORDS.index("export const PILLS_HELP"):].split("];")[0]))


class StateOrder(unittest.TestCase):
    """Rows 2-6: the starting set of a work-item page is put in order by what the project holds (state: overdue, red, noOwner counts)."""

    def test_a_dashboard_with_overdue_work_asks_about_overdue_first_and_without_it_does_not(self):
        with_overdue = pills("dashboard", [], False, {"overdue": 2, "red": 0, "noOwner": 0})
        without = pills("dashboard", [], False, {"overdue": 0, "red": 0, "noOwner": 0})
        self.assertEqual(with_overdue[0], "What is overdue?")
        self.assertNotEqual(without[0], "What is overdue?")

    def test_red_and_overdue_are_not_swapped(self):
        red = pills("dashboard", [], False, {"overdue": 0, "red": 3, "noOwner": 0})
        over = pills("dashboard", [], False, {"overdue": 3, "red": 0, "noOwner": 0})
        self.assertEqual(red[0], "Which risks are red?")
        self.assertEqual(over[0], "What is overdue?")

    def test_the_larger_count_goes_first_and_a_tie_goes_to_overdue(self):
        self.assertEqual(pills("dashboard", [], False, {"overdue": 1, "red": 3, "noOwner": 0})[0], "Which risks are red?")
        self.assertEqual(pills("dashboard", [], False, {"overdue": 3, "red": 1, "noOwner": 0})[0], "What is overdue?")
        self.assertEqual(pills("dashboard", [], False, {"overdue": 2, "red": 2, "noOwner": 0})[:2], ["What is overdue?", "Which risks are red?"])

    def test_work_items_with_no_owner_put_that_question_first(self):
        got = pills("work", [], False, {"overdue": 0, "red": 0, "noOwner": 4})
        self.assertEqual(got[0], "Which work items have no owner?")

    def test_state_only_reorders_and_never_adds_or_drops_a_pill(self):
        for page in PAGES:
            base = pills(page)
            for state in ({"overdue": 1, "red": 0, "noOwner": 0}, {"overdue": 0, "red": 1, "noOwner": 1}):
                self.assertEqual(sorted(pills(page, [], False, state)), sorted(base), page)

    def test_an_empty_state_is_the_plain_set(self):
        for page in PAGES:
            self.assertEqual(pills(page, [], False, {"overdue": 0, "red": 0, "noOwner": 0}), subject_lists()[page], page)


class SixAtMost(unittest.TestCase):
    def test_never_more_than_six_and_no_duplicates(self):
        for page in PAGES + ("settings",):
            for help_open in (False, True):
                for turns in ([], [user("Any risks?"), reply()], [user("Any use case stuck?"), reply()]):
                    got = pills(page, turns, help_open, {"overdue": 5, "red": 5, "noOwner": 5})
                    self.assertLessEqual(len(got), 6, (page, help_open))
                    self.assertEqual(len(got), len(set(got)), (page, help_open))
                    self.assertTrue(got)


if __name__ == "__main__":
    unittest.main()
