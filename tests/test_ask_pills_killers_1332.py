"""Row 1332 killers, round 2: every operand of askPills.js and askPillState.js, in one file.

Run: python3 dev/run_tests.py test_ask_pills_killers_1332
Quick tier: no browser. The two modules are bundled by the pinned esbuild and run in node in one process per test (skips without node).
The words are the words in askWords.js today and stand in for the ruled ones.
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
WORDS = (EDIT / "askWords.js").read_text(encoding="utf-8")
TODAY = "2026-06-15"

_bundle = {}


def bundle():
    if "code" not in _bundle:
        node = shutil.which("node")
        if not node:
            raise unittest.SkipTest("no node")
        for name in ("askPills.js", "askPillState.js"):
            assert (EDIT / name).is_file(), name + " does not exist"
        with tempfile.TemporaryDirectory() as tmp:
            entry = Path(tmp) / "entry.js"
            entry.write_text('export { pills, asking } from "%s";\nexport { stateOf } from "%s";\n' % ((EDIT / "askPills.js").as_posix(), (EDIT / "askPillState.js").as_posix()), encoding="utf-8")
            out = Path(tmp) / "k.js"
            done = esbuild.run(["--bundle", "--format=iife", "--global-name=K", str(entry), f"--outfile={out}"], capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            _bundle["code"] = out.read_text(encoding="utf-8")
    return _bundle["code"]


def probe(exprs):
    """Evaluate several JS expressions (K.pills, K.stateOf) in one node run; returns their JSON results."""
    code = bundle()
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "probe.js"
        script.write_text(code + ";\nconsole.log(JSON.stringify([" + ",\n".join(exprs) + "]));", encoding="utf-8")
        got = subprocess.run([shutil.which("node"), str(script)], capture_output=True, text=True)
        assert got.returncode == 0, got.stderr
        return json.loads(got.stdout)


def one(expr):
    return probe([expr])[0]


def pills(view, turns=(), help_open=False, state=None):
    args = [json.dumps(view), json.dumps(turns if turns is None else list(turns)), json.dumps(help_open)]
    if state is not None:
        args.append(json.dumps(state))
    return "K.pills(" + ", ".join(args) + ")"


def user(text):
    return {"role": "user", "text": text}


def reply(text="Fine."):
    return {"role": "assistant", "text": text}


def lists():
    block = WORDS[WORDS.index("export const PILLS_BY_SUBJECT = {"):]
    block = block[:block.index("\n};")]
    return {m.group(1): re.findall(r'"([^"]+)"', m.group(2)) for m in re.finditer(r"^  (\w+): \[(.*)\],$", block, re.M)}


def front(base, *qs):
    """base with the questions qs moved to the front, in the order given, the rest in their own order."""
    return list(qs) + [q for q in base if q not in qs]


def st(overdue=0, red=0, noOwner=0):
    return {"overdue": overdue, "red": red, "noOwner": noOwner}


L = lists()
OVERDUE, RED = "What is overdue?", "Which risks are red?"
NO_OWNER_WORK = "Which work items have no owner?"
UC_RED, UC_NO_OWNER = "Which use cases have open risks?", "Which use cases have no owner?"
RISK_NO_OWNER = "Which risks have no owner?"
GANTT_LATE, GANTT_RISK = "Which work items are running late?", "Which milestones are at risk?"


class Order(unittest.TestCase):
    def check(self, cases):
        got = probe([pills(*c[0]) for c in cases])
        for (args, want), have in zip(cases, got):
            self.assertEqual(have, want, args)

    def test_larger_count_first_and_a_tie_goes_overdue_red_noowner(self):
        d = L["dashboard"]
        self.check([
            (("dashboard", [], False, st(2, 2, 0)), front(d, OVERDUE, RED)),
            (("dashboard", [], False, st(1, 3, 0)), front(d, RED, OVERDUE)),
            (("dashboard", [], False, st(3, 1, 0)), front(d, OVERDUE, RED)),
            (("work", [], False, st(1, 0, 5)), front(L["work"], NO_OWNER_WORK, OVERDUE)),
            (("work", [], False, st(5, 0, 1)), front(L["work"], OVERDUE, NO_OWNER_WORK)),
            (("work", [], False, st(2, 0, 2)), front(L["work"], OVERDUE, NO_OWNER_WORK)),
            (("usecases", [], False, st(0, 2, 2)), front(L["usecases"], UC_RED, UC_NO_OWNER)),
            (("usecases", [], False, st(0, 1, 2)), front(L["usecases"], UC_NO_OWNER, UC_RED)),
            (("dashboard", [user("Any risks?")], False, st(0, 1, 2)), front(L["risks"], RISK_NO_OWNER, RED)),
            (("gantt", [], False, st(2, 2, 0)), front(L["gantt"], GANTT_LATE, GANTT_RISK)),
            (("gantt", [], False, st(1, 4, 0)), front(L["gantt"], GANTT_RISK, GANTT_LATE)),
        ])

    def test_a_single_count_moves_only_its_own_question_up(self):
        d = L["dashboard"]
        self.check([
            (("dashboard", [], False, st(1, 0, 0)), front(d, OVERDUE)),
            (("dashboard", [], False, st(0, 1, 0)), front(d, RED)),
            (("dashboard", [], False, st(0, 3, 0)), front(d, RED)),
            (("work", [], False, st(0, 0, 1)), front(L["work"], NO_OWNER_WORK)),
            (("milestones", [], False, st(4, 0, 0)), front(L["milestones"], "Which milestones are late?")),
            (("gantt", [], False, st(0, 1, 0)), front(L["gantt"], GANTT_RISK)),
        ])

    def test_a_zero_a_negative_or_a_missing_count_does_not_reorder(self):
        d = L["dashboard"]
        self.check([
            (("dashboard", [], False, st(3, 0, 0)), front(d, OVERDUE)),  # red 0 must stay where it is (index 2), not follow overdue
            (("dashboard", [], False, st(0, 3, 0)), front(d, RED)),
            (("dashboard", [], False, st(-1, -1, -1)), d),
            (("dashboard", [], False, {}), d),
            (("dashboard", [], False, {"overdue": None, "red": "x"}), d),
            (("work", [], False, st(0, 0, 0)), L["work"]),
            (("work", [], False, st(0, 9, 0)), L["work"]),  # a count the subject has no question for
            (("milestones", [], False, st(0, 9, 9)), L["milestones"]),
        ])

    def test_state_uses_the_subject_of_the_last_question_not_the_page(self):
        self.check([
            (("work", [user("Any risks?"), reply()], False, st(0, 2, 0)), front(L["risks"], RED)),
            (("work", [user("Any risks?"), reply()], False, st(0, 0, 2)), front(L["risks"], RISK_NO_OWNER)),
            (("dashboard", [user("Any milestones?"), reply()], False, st(2, 5, 0)), front(L["milestones"], "Which milestones are late?")),
        ])

    def test_help_and_a_page_without_a_list_ignore_the_state(self):
        helps = re.findall(r'"([^"]+)"', WORDS[WORDS.index("export const PILLS_HELP"):].split("];")[0])
        sug = re.findall(r'^  "(.+)",$', WORDS[WORDS.index("export const SUGGESTIONS = ["):].split("\n];")[0], re.M)
        self.check([
            (("dashboard", [], True, st(9, 9, 9)), helps),
            (("settings", [], False, st(9, 9, 9)), sug),
            (("settings", [], False), sug),
            (("", [], False, st(1, 1, 1)), sug),
        ])
        self.assertEqual(len(helps), 6, "the Help set is exactly six questions")

    def test_every_list_is_six_long_and_the_cut_is_exactly_six(self):
        for name, items in L.items():
            self.assertEqual(len(items), 6, name)
        self.assertEqual(one("[K.pills('dashboard',[],false,{overdue:1,red:1,noOwner:1}).length, K.pills('x',[],true).length, K.pills('x',[],false).length]"), [6, 6, 6])

    def test_the_result_is_a_copy_and_the_words_are_not_changed(self):
        got = one("(function(){var a=K.pills('dashboard',[],false,{overdue:2,red:1,noOwner:0});a.reverse();a.push('x');var h=K.pills('x',[],true);h.pop();"
                  "var g=K.pills('x',[],false);g.pop();return [K.pills('dashboard',[],false,{overdue:2,red:1,noOwner:0}),K.pills('x',[],true).length,K.pills('x',[],false).length,K.pills('dashboard').length]})()")
        self.assertEqual(got[0], front(L["dashboard"], OVERDUE, RED))
        self.assertEqual(got[1:], [6, 6, 6])


class Subject(unittest.TestCase):
    def check(self, cases):
        got = probe([pills("work" if len(c) < 3 else c[2], [user(c[0]), reply()]) for c in cases])
        for c, have in zip(cases, got):
            self.assertEqual(have, L[c[1]], c[0])

    def test_names_match_as_whole_words_in_either_spelling_and_case(self):
        self.check([
            ("risk", "risks"), ("Any risk", "risks"), ("risk?", "risks"), ("RISKS", "risks"), ("Any Issues open?", "risks"),
            ("use-case", "usecases"), ("usecase", "usecases"), ("use case", "usecases"), ("use_case", "usecases"), ("use   cases", "usecases"),
            ("work-item", "work", "dashboard"), ("workitems", "work", "dashboard"), ("Tasks", "work", "dashboard"), ("Milestone", "milestones"),
        ])

    def test_a_longer_word_or_a_partial_word_names_nothing(self):
        self.check([
            ("brisk walk", "work"), ("risky", "work"), ("tasked", "work"), ("taskforce", "work"), ("milestoned", "work"),
            ("reuse cased", "work"), ("tissue", "work"), ("Thank you", "work"), ("", "work"),
        ])

    def test_the_first_named_subject_in_the_word_order_wins(self):
        self.check([("Any issue with the work items?", "risks"), ("risk of a milestone", "milestones"), ("task in a use case", "usecases")])

    def test_only_the_last_user_turn_with_text_counts_and_odd_turns_are_skipped(self):
        got = probe([
            pills("work", [user("Any risks?"), user("Any milestones?"), reply("Any risks?")]),
            pills("work", [user("Any milestones?"), user("Any risks?")]),
            pills("work", [user("Any risks?"), {"role": "user", "text": 5}, None, {"role": "assistant", "text": "milestones"}]),
            pills("work", [reply("Any risks?")]),
            pills("work", None),
            pills("work", [None, {"role": "user"}]),
        ])
        self.assertEqual(got, [L["milestones"], L["risks"], L["risks"], L["work"], L["work"], L["work"]])

    def test_help_beats_the_subject(self):
        self.assertEqual(one(pills("work", [user("Any risks?")], True)), one(pills("work", [], True)))
        self.assertNotEqual(one(pills("work", [], True)), L["work"])


def row(**kw):
    base = {"kind": "action", "status": "Open", "due_date": "", "owner": "Ann Lee", "priority": ""}
    base.update(kw)
    return base


def state_of(rows, today=TODAY):
    return one("K.stateOf(%s, %s)" % (json.dumps(rows), json.dumps(today)))


class StateOf(unittest.TestCase):
    def test_no_rows_or_not_a_list_is_all_zeros(self):
        zero = st()
        got = probe(["K.stateOf([], %s)" % json.dumps(TODAY), "K.stateOf(null, %s)" % json.dumps(TODAY), "K.stateOf(undefined, %s)" % json.dumps(TODAY),
                     "K.stateOf({length: 2}, %s)" % json.dumps(TODAY), "K.stateOf('ab', %s)" % json.dumps(TODAY)])
        self.assertEqual(got, [zero] * 5)

    def test_overdue_counts_open_rows_due_before_today_of_any_kind(self):
        rows = [
            row(due_date="2026-06-14"),  # late
            row(kind="risk", due_date="2026-01-01"),  # late, not an action
            row(kind="milestone", due_date="2026-06-01", status="Planned"),  # late
            row(due_date=TODAY),  # due today: not late
            row(due_date="2026-06-16"),  # tomorrow
            row(due_date="2026-06-01", status="Completed"),  # finished work is never late
            row(due_date="2026-06-01", status="Closed"),
            row(due_date="2026-06-01", status="Cancelled"),
            row(due_date=""), row(due_date="soon"),
        ]
        self.assertEqual(state_of(rows)["overdue"], 3)
        self.assertEqual(state_of(rows, "2026-06-17")["overdue"], 5, "today is the day the page holds, not the real day")
        self.assertEqual(state_of(rows, "2026-01-01")["overdue"], 0)

    def test_no_owner_counts_open_rows_with_no_owner_blank_or_tbc(self):
        rows = [
            row(owner=""), row(owner=None), row(owner="   "), row(owner="TBC"), row(owner="tbc"), row(kind="milestone", owner=""),
            row(status="Completed", owner=""),  # Completed is still open: counted
            row(owner="Ann Lee"), row(owner="Bo"), row(owner="Ann"),
            row(owner="", status="Closed"), row(owner="", status="Cancelled"), row(owner="", status="Made"), row(owner="", status="Withdrawn"),
        ]
        rows.append({"kind": "action", "status": "Open"})  # no owner key at all
        self.assertEqual(state_of(rows)["noOwner"], 8)

    def test_red_is_the_high_risks_tile_and_nothing_else(self):
        rows = [
            row(kind="risk", priority="High"), row(kind="risk", priority="Urgent"), row(kind="issue", priority="High"),
            row(kind="assumption", priority="Urgent"), row(kind="dependency", priority="High"),
            row(kind="risk", priority="Medium"), row(kind="risk", priority="Low"), row(kind="risk", priority=""),
            row(kind="risk", priority="High", status="Closed"),
            row(kind="action", priority="High"), row(kind="decision", priority="Urgent", status="Pending"),
        ]
        self.assertEqual(state_of(rows)["red"], 5)

    def test_the_three_counts_are_kept_apart(self):
        rows = [
            row(due_date="2026-06-01"), row(due_date="2026-06-02"), row(due_date="2026-06-03"), row(due_date="2026-06-04", kind="risk", priority="Low"),
            row(kind="risk", priority="High", owner=""), row(kind="issue", priority="Urgent", owner="TBC"),
            row(owner=""), row(owner="", kind="milestone"), row(owner="", status="Closed"), row(owner=""),
        ]
        self.assertEqual(state_of(rows), st(4, 2, 5))


if __name__ == "__main__":
    unittest.main()
