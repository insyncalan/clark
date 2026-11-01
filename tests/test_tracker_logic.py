"""#189 piece 3, the progress tracker's totals and the rules of its editor (src/clark/page/src/logic/tracker.js). Nothing here draws
anything. Fictional data.

Run: python3 dev/run_tests.py test_tracker_logic
The repo has no Node, so the logic runs inside headless Chrome (as test_filter_line does). Chrome is required: these tests fail, never
skip, without it.
"""
import contextlib
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT, SRC, TOOLS

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402

from test_server import Running, chrome, wait  # noqa: E402

PAGE_SRC = SRC / "clark" / "page" / "src"
DEMO = ROOT / "tests" / "fixtures" / "tracker_demo.js"
_PAGE = {}
JARGON = re.compile(r"\b(RAID|JSON|schema|id|IDs?|database|payload|null|token|API|SQL|field|fields|string|array|object|boolean|undefined|NaN|"
                    r"parse|checker|template|templates)\b|\bUI\b")


def page_html():
    if "html" not in _PAGE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "t.js"
            done = esbuild.run(["--bundle", "--format=iife", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(DEMO), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            script = out.read_text(encoding="utf-8").replace("</script", "<\\/script")
        _PAGE["html"] = ('<!doctype html>\n<html lang="en-GB"><head><meta charset="utf-8"><title>t</title></head>'
                         f'<body><div id="root"></div>\n<script>{script}</script>\n</body></html>\n')
    return _PAGE["html"]


def lit(x):
    return json.dumps(x)


def line(text, weight, planned, achieved, **more):
    return {"no": "", "text": text, "start": "2026-01-05", "end": "2026-03-27", "status": "inprogress", "weight": weight, "planned": planned,
            "achieved": achieved, "tasks": None, "agents": None, "workflows": None, **more}


# Fictional. Weights add up to 94% (940 tenths). Group A: planned 300, achieved 250; B: planned 200, achieved 200; C has no lines.
TRACKER = {
    "overall": {"actual": None, "planned": None, "health": "atrisk", "note": "Supplier slipped a week"},
    "columns": {"tasks": False, "agents": False, "workflows": False},
    "groups": [
        {"name": "Foundations", "lines": [line("Agree the plan", 200, 200, 200), line("Set up the site", 300, 100, 50)]},
        {"name": "Build", "lines": [line("Build the first release", 440, 200, 200)]},
        {"name": "Hand over", "lines": []},
    ],
}


class Totals(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack = contextlib.ExitStack()
        cls.server = Running(page_html=page_html)
        cls.stack.callback(cls.server.close)
        cls.cdp = cls.stack.enter_context(chrome())
        tid = next(t["targetId"] for t in cls.cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        cls.sid = cls.cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cls.cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{cls.server.port}/"}, cls.sid)
        assert wait(lambda: cls.cdp.js("!!(window.K && window.K.tracker)", cls.sid)), "the test bundle ran"

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    def val(self, expr):
        got = self.cdp.js(f"(function(){{ try {{ return JSON.stringify({expr}); }} catch (e) {{ return 'ERROR ' + e.message; }} }})()", self.sid)
        self.assertIsNotNone(got, expr)
        self.assertFalse(got.startswith("ERROR"), f"{expr}: {got}")
        return json.loads(got)

    def k(self, call):
        return self.val(f"K.tracker.{call}")

    def totals(self, tracker=TRACKER):
        return self.k(f"totals({lit(tracker)})")

    # ── totals ───────────────────────────────────────────────────────────────

    def test_group_totals_are_the_sums_of_their_lines(self):
        a, b, c = self.totals()["groups"]
        self.assertEqual((a["weight"], a["planned"], a["achieved"], a["behind"]), (500, 300, 250, 50))
        self.assertEqual((b["weight"], b["planned"], b["achieved"], b["behind"]), (440, 200, 200, 0))
        self.assertEqual((a["name"], a["none"], b["none"]), ("Foundations", False, False))

    def test_a_group_with_no_lines_is_zero_and_says_so(self):
        c = self.totals()["groups"][2]
        self.assertEqual((c["none"], c["weight"], c["planned"], c["achieved"], c["behind"], c["lines"]), (True, 0, 0, 0, 0, []))
        self.assertEqual(self.k("WORDS.noLines"), "No lines yet")

    def test_the_overall_is_the_sum_of_the_group_totals_whatever_was_typed(self):
        typed = {**TRACKER, "overall": {**TRACKER["overall"], "actual": 999, "planned": 999}}
        o = self.totals(typed)["overall"]
        self.assertEqual((o["actual"], o["planned"], o["fromLines"]), (450, 500, True))
        t = self.totals()
        self.assertEqual(o["actual"], sum(g["achieved"] for g in t["groups"]))
        self.assertEqual(o["planned"], sum(g["planned"] for g in t["groups"]))

    def test_points_behind_plan_are_in_the_overall_and_on_each_line(self):
        t = self.totals()
        self.assertEqual((t["overall"]["behind"], t["overall"]["behindWords"]), (50, "5 points behind plan"))
        self.assertEqual([x["behind"] for x in t["groups"][0]["lines"]], [0, 50])

    def test_ahead_of_plan_is_not_behind(self):
        ahead = {**TRACKER, "groups": [{"name": "Early", "lines": [line("Done early", 1000, 100, 400)]}]}
        t = self.totals(ahead)
        self.assertEqual((t["groups"][0]["behind"], t["groups"][0]["lines"][0]["behind"], t["overall"]["behind"], t["overall"]["behindWords"]), (0, 0, 0, ""))

    def test_the_words_for_points_behind(self):
        self.assertEqual(self.k("behindWords(10)"), "1 point behind plan")
        self.assertEqual(self.k("behindWords(25)"), "2.5 points behind plan")
        self.assertEqual(self.k("behindWords(5)"), "0.5 points behind plan")
        self.assertEqual(self.k("behindWords(0)"), "")

    def test_a_weights_note_appears_only_when_they_do_not_add_up(self):
        self.assertEqual(self.totals()["weightsNote"], "Weights add up to 94%")
        self.assertEqual(self.totals()["weights"], 940)
        whole = {**TRACKER, "groups": [{"name": "All", "lines": [line("One", 600, 0, 0), line("Two", 400, 0, 0)]}]}
        self.assertEqual(self.totals(whole)["weightsNote"], "")
        half = {**TRACKER, "groups": [{"name": "All", "lines": [line("One", 945, 0, 0)]}]}
        self.assertEqual(self.totals(half)["weightsNote"], "Weights add up to 94.5%")
        empty = {**TRACKER, "groups": [{"name": "Nothing yet", "lines": []}]}
        self.assertEqual(self.totals(empty)["weightsNote"], "")

    def test_with_no_lines_the_typed_overall_stands_and_nothing_typed_is_empty(self):
        typed = {**TRACKER, "overall": {**TRACKER["overall"], "actual": 400, "planned": 500}, "groups": []}
        o = self.totals(typed)["overall"]
        self.assertEqual((o["actual"], o["planned"], o["behind"], o["fromLines"]), (400, 500, 100, False))
        bare = self.totals({**TRACKER, "groups": []})["overall"]
        self.assertEqual((bare["actual"], bare["planned"], bare["behind"]), (None, None, 0))
        self.assertEqual((self.k("fill(null)"), self.k("fill(1200)"), self.k("fill(625)")), (0, 1000, 625))

    # ── percentages ──────────────────────────────────────────────────────────

    def test_a_percentage_is_whole_tenths_from_0_to_100(self):
        for text, want in [("0", 0), ("62", 620), ("62.5", 625), ("62,5", 625), ("62%", 620), (" 100 ", 1000), ("100.0", 1000), ("0.5", 5)]:
            self.assertEqual(self.k(f"pct({lit(text)})"), want, text)
        for text in ["", "abc", "-1", "100.1", "101", "1000", "62.55", "6 2", "1e2", ".5", "5."]:
            self.assertIsNone(self.k(f"pct({lit(text)})"), text)
        self.assertEqual([self.k(f"fmt({n})") for n in (0, 5, 625, 940, 1000)], ["0", "0.5", "62.5", "94", "100"])

    # ── reading ──────────────────────────────────────────────────────────────

    def test_a_stored_body_is_read_and_one_that_cannot_be_is_an_empty_tracker(self):
        t = self.k(f"trackerOf({{body: {lit(json.dumps({'v': 1, **TRACKER}))}}}, false)")
        self.assertEqual(t["groups"][0]["lines"][1]["text"], "Set up the site")
        self.assertEqual(t["overall"]["health"], "atrisk")
        for body in ["", "{", "[]", "null", '{"groups": 3}', '{"groups": [null, {"name": 4}, {"name": "A", "lines": [5, {"text": 6}]}]}']:
            r = self.k(f"trackerOf({{body: {lit(body)}}}, false)")
            self.assertEqual(r["columns"], {"tasks": False, "agents": False, "workflows": False}, body)
            self.assertTrue(all(not g["lines"] for g in r["groups"]), body)
        self.assertEqual(self.k("trackerOf(null, false)")["groups"], [])

    def test_odd_values_are_read_as_their_safe_default(self):
        body = {"groups": [{"name": "A", "lines": [{"text": "x", "status": "bogus", "weight": 5000, "planned": -3, "achieved": 1.5, "tasks": "7", "start": "2026-02-30"}]}],
                "overall": {"health": "great"}}
        r = self.k(f"trackerOf({{body: {lit(json.dumps(body))}}}, false)")["groups"][0]["lines"][0]
        self.assertEqual((r["status"], r["weight"], r["planned"], r["achieved"], r["tasks"], r["start"]), ("planned", 0, 0, 0, None, ""))
        self.assertEqual(self.k(f"trackerOf({{body: {lit(json.dumps(body))}}}, false)")["overall"]["health"], "")

    def test_a_published_copy_is_read_with_its_dates_written_day_first(self):
        shown = {"groups": [{"name": "A", "lines": [line("x", 100, 100, 100, start="05-01-2026", end="27-03-2026")]}]}
        r = self.k(f"trackerOf({{tracker: {lit(shown)}}}, true)")["groups"][0]["lines"][0]
        self.assertEqual((r["start"], r["end"]), ("2026-01-05", "2026-03-27"))

    # ── checking a line ──────────────────────────────────────────────────────

    def draft(self, **more):
        base = {"no": "1.1", "text": "Agree the plan", "start": "05-01-2026", "end": "27-03-2026", "status": "planned", "weight": "20", "planned": "20",
                "achieved": "10", "tasks": "", "agents": "", "workflows": ""}
        return {**base, **more}

    def problem(self, **more):
        return self.k(f"problem({lit(self.draft(**more))})")

    def test_a_good_line_has_no_problem_and_a_blank_one_is_all_zero(self):
        self.assertEqual(self.problem(), "")
        self.assertEqual(self.problem(weight="", planned="", achieved="", start="", end=""), "")
        made = self.k(f"made({lit(self.draft(weight='', planned='12.5', tasks='3'))})")
        self.assertEqual((made["weight"], made["planned"], made["achieved"], made["tasks"], made["agents"], made["start"]), (0, 125, 100, 3, None, "2026-01-05"))

    def test_each_refusal_is_in_plain_words(self):
        P = self.k("WORDS.problems")
        self.assertEqual(self.problem(text="  "), P["text"])
        self.assertEqual(self.problem(text="x" * 101), P["textLong"])
        self.assertEqual(self.problem(no="x" * 11), P["noLong"])
        self.assertEqual(self.problem(status="done"), P["status"])
        for k in ("weight", "planned", "achieved"):
            for bad in ("101", "-5", "lots", "12.34"):
                self.assertEqual(self.problem(**{k: bad}), "A percentage must be a number from 0 to 100.", f"{k} {bad}")
        self.assertEqual(self.problem(start="31-02-2026"), P["date"])
        self.assertEqual(self.problem(end="27-03-1999"), P["date"])
        self.assertEqual(self.problem(start="27-03-2026", end="05-01-2026"), P["order"])
        self.assertEqual(self.problem(tasks="-1"), P["count"])
        self.assertEqual(self.problem(agents="100000"), P["count"])
        self.assertEqual(self.problem(workflows="1.5"), P["count"])
        self.assertEqual(self.k("nameProblem('')"), P["name"])
        self.assertEqual(self.k(f"nameProblem({lit('x' * 81)})"), P["nameLong"])
        self.assertEqual(self.k("nameProblem('Build')"), "")

    def test_the_page_says_the_same_as_the_store_where_both_speak(self):
        from clark import section_bodies as sb
        P = self.k("WORDS.problems")
        self.assertEqual(P["percent"], sb.TRACKER_PERCENT)
        self.assertEqual(P["text"], sb.TRACKER_TEXT_MISSING)
        self.assertEqual(P["textLong"][:-1], sb.TRACKER_TEXT_LONG.split(" Shorten")[0][:-1])
        self.assertEqual(P["order"], sb.TRACKER_DATE_ORDER)
        self.assertEqual(P["status"], sb.TRACKER_STATUS)
        self.assertEqual(P["count"], sb.TRACKER_COUNT)
        self.assertEqual(P["name"], sb.TRACKER_NAME_MISSING)
        self.assertEqual(P["nameLong"], sb.TRACKER_NAME_LONG)
        self.assertEqual(P["noLong"], sb.TRACKER_NO_BAD)
        self.assertEqual((self.k("MAX_GROUPS"), self.k("MAX_LINES"), self.k("NAME_MAX"), self.k("TEXT_MAX"), self.k("NO_MAX"), self.k("NOTE_MAX")),
                         (sb.TRACKER_MAX_GROUPS, sb.TRACKER_MAX_LINES, sb.TRACKER_NAME_MAX, sb.TRACKER_TEXT_MAX, sb.TRACKER_NO_MAX, sb.TRACKER_NOTE_MAX))

    def test_what_the_page_sends_is_what_the_store_keeps(self):
        from clark import section_bodies as sb

        class Rules:
            visible = staticmethod(lambda s: bool(s.strip()))
        body = self.val(f"(function(t){{ return t.bodyOf(t.trackerOf({{body: {lit(json.dumps(TRACKER))}}}, false)); }})(K.tracker)")
        checked = sb._checked_tracker(json.loads(body), Rules)
        self.assertEqual(checked["groups"], TRACKER["groups"])
        self.assertEqual(checked["overall"], TRACKER["overall"])

    # ── one change each ──────────────────────────────────────────────────────

    def test_adding_removing_moving_and_renaming_each_give_one_new_tracker(self):
        T = lit(TRACKER)
        names = lambda t: [g["name"] for g in t["groups"]]       # noqa: E731
        texts = lambda t, g: [x["text"] for x in t["groups"][g]["lines"]]    # noqa: E731
        added = self.k(f"withLineAdded({T}, 2, {lit(line('Sign off', 0, 0, 0))})")
        self.assertEqual(texts(added, 2), ["Sign off"])
        self.assertEqual(texts(self.k(f"withoutLine({T}, 0, 0)"), 0), ["Set up the site"])
        self.assertEqual(texts(self.k(f"withLineMoved({T}, 0, 0, 1)"), 0), ["Set up the site", "Agree the plan"])
        self.assertIsNone(self.k(f"withLineMoved({T}, 0, 0, -1)"))
        self.assertIsNone(self.k(f"withLineMoved({T}, 0, 1, 1)"))
        self.assertEqual(names(self.k(f"withGroupMoved({T}, 2, -1)")), ["Foundations", "Hand over", "Build"])
        self.assertEqual(names(self.k(f"withoutGroup({T}, 1)")), ["Foundations", "Hand over"])
        self.assertEqual(names(self.k(f"withGroupRenamed({T}, 2, 'Close down')")), ["Foundations", "Build", "Close down"])
        self.assertEqual(names(self.k(f"withGroupAdded({T}, 'Extra')"))[-1], "Extra")
        self.assertEqual(self.k(f"withColumn({T}, 'tasks', true)")["columns"]["tasks"], True)
        self.assertEqual(self.k(f"withOverall({T}, {{health: 'ontrack'}})")["overall"]["note"], "Supplier slipped a week")
        for call in ("withoutLine(%s, 9, 0)", "withoutLine(%s, 0, 9)", "withoutGroup(%s, 9)", "withGroupRenamed(%s, -1, 'x')"):
            self.assertIsNone(self.k(call % T), call)
        self.assertEqual(texts(TRACKER, 0), ["Agree the plan", "Set up the site"], "the original is untouched")

    def test_the_limits_stop_another_line_or_group(self):
        full = {**TRACKER, "groups": [{"name": "Big", "lines": [line(f"Line {i}", 0, 0, 0) for i in range(47)]}, {"name": "Second", "lines": []}]}
        self.assertIsNone(self.k(f"withLineAdded({lit(full)}, 1, {lit(line('One more', 0, 0, 0))})"))
        many = {**TRACKER, "groups": [{"name": f"G{i}", "lines": []} for i in range(10)]}
        self.assertIsNone(self.k(f"withGroupAdded({lit(many)}, 'Eleven')"))

    # ── the words ────────────────────────────────────────────────────────────

    def test_every_word_is_plain_and_none_starts_with_the_product_name(self):
        words = [w for w in self.k("ALL_WORDS()") if w.strip()]
        self.assertGreater(len(words), 50)
        for word in words:
            self.assertFalse(re.match(r"\s*clark\b", word, re.I), word)
            self.assertIsNone(JARGON.search(word), word)
        self.assertEqual([w for _, w in self.k("STATUSES")], ["Planned", "In progress", "Completed", "Late"])
        self.assertEqual([w for _, w in self.k("HEALTH")], ["On track", "At risk", "Off track"])


if __name__ == "__main__":
    unittest.main()
