"""#153 (One filter line for Work items), the pure part: reading a line, the chips, what to suggest, the plain-words messages, the
line and the older filter state in both directions, saved views per project and the session memory of the line
(src/clark/page/src/logic/filterLine.js). Nothing here draws anything.

Run: python3 dev/run_tests.py test_filter_line
The repo has no Node, so the logic runs inside headless Chrome (as test_board does): bundled with the pinned esbuild into a
temporary folder and put on a page the harness server serves. Chrome is required: these tests fail, never skip, without it.
"""
import contextlib
import json
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
DEMO = ROOT / "tests" / "fixtures" / "filterline_demo.js"
TODAY = "2026-10-29"
ME = "Owner One"
CTX = {"today": TODAY, "me": ME, "isReady": True}
NOBODY = {"today": TODAY, "me": "", "isReady": True}
OFF = {"today": TODAY, "me": ME}   # the page has not switched the `is:` data on
_PAGE = {}


def row(id, kind, title, status, owner, priority=None, due=None, **more):
    r = {"id": id, "kind": kind, "title": title, "status": status, "owner": owner, "priority": priority, "workstream": "", "uc": "",
         "milestone": "", "client": False, "due_date": due}
    r.update(more)
    return r


# Fictional. Today is a Thursday.
ROWS = [
    row("T-A-001", "action", "Draft the cut-over plan", "Open", ME, "High", "2026-10-20", workstream="Build", uc="Use case 1", milestone="Go live"),
    row("T-A-002", "action", "Book the training room", "Open", "TBC", "Low", "2026-11-01"),
    row("T-A-003", "action", "Send the invitations", "Delayed", "Owner Two", "Urgent", "2026-11-05", workstream="Data"),
    row("T-A-004", "action", "Order the laptops", "Open", ME, "Medium", "2026-12-01", workstream="Data", client=True),
    row("T-A-005", "action", "Archive the old files", "Closed", "Owner Two", "Medium", "2026-10-05"),
    row("T-R-001", "risk", "Supplier slips", "Open", ME, "High", "2026-11-03", workstream="Build", reviewed="2026-10-01", client_action=True),
    row("T-R-002", "issue", "Test system is down", "Open", "", "High"),
    row("T-R-003", "assumption", "Users have laptops", "Open", "Owner Two", "Low", workstream="Data"),
    row("T-D-001", "decision", "Use the new tool", "Pending", ME, None, None, needed_by="2026-11-20"),
    row("T-D-002", "decision", "Pick a supplier", "Pending", "Owner Two", None, None),
    row("T-D-003", "decision", "Use the shared calendar", "Made", "Owner Two", None, None, date="2026-10-01"),
    row("T-D-004", "decision", "Go with the old plan", "Withdrawn", "Owner Two", None, None),
]
ALL = [r["id"] for r in ROWS]


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


class Line(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack = contextlib.ExitStack()
        cls.server = Running(page_html=page_html)
        cls.stack.callback(cls.server.close)
        cls.cdp = cls.stack.enter_context(chrome())
        tid = next(t["targetId"] for t in cls.cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        cls.sid = cls.cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cls.cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{cls.server.port}/"}, cls.sid)
        assert wait(lambda: cls.cdp.js("!!(window.T && window.T.fl)", cls.sid)), "the test bundle ran"

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    def val(self, expr):
        got = self.cdp.js(f"(function(){{ try {{ return JSON.stringify({expr}); }} catch (e) {{ return 'ERROR ' + e.message; }} }})()", self.sid)
        self.assertIsNotNone(got, expr)
        self.assertFalse(got.startswith("ERROR"), f"{expr}: {got}")
        return json.loads(got)

    def parse(self, line, ctx=CTX):
        return self.val(f"T.fl.parse({lit(line)}, {lit(ROWS)}, {lit(ctx)})")

    def ids(self, line, ctx=CTX):
        return [r["id"] for r in self.val(f"T.fl.apply({lit(ROWS)}, {lit(line)}, {lit(ctx)})")]

    def one_error(self, line, ctx=CTX):
        p = self.parse(line, ctx)
        self.assertEqual(len(p["errors"]), 1, p)
        return p["errors"][0]["msg"]


class Fields(Line):
    def test_each_field(self):
        self.assertEqual(self.ids("type:decision"), ["T-D-001", "T-D-002", "T-D-003", "T-D-004"])
        self.assertEqual(self.ids("type:risk,issue"), ["T-R-001", "T-R-002"])
        self.assertEqual(self.ids("status:Delayed"), ["T-A-003"])
        self.assertEqual(self.ids("owner:\"Owner One\" type:action"), ["T-A-001", "T-A-004"])
        self.assertEqual(self.ids("priority:Urgent"), ["T-A-003"])
        self.assertEqual(self.ids("workstream:Build"), ["T-A-001", "T-R-001"])
        self.assertEqual(self.ids("usecase:\"Use case 1\""), ["T-A-001"])
        self.assertEqual(self.ids("milestone:\"Go live\""), ["T-A-001"])
        self.assertEqual(self.ids("client:shown"), ["T-A-004"])
        self.assertEqual(self.ids("client:internal"), [i for i in ALL if i != "T-A-004"])
        self.assertEqual(self.ids("is:closed"), ["T-A-005", "T-D-003", "T-D-004"])

    def test_the_start_line_is_the_open_items(self):
        self.assertEqual(self.ids("is:open"), [i for i in ALL if i not in ("T-A-005", "T-D-003", "T-D-004")])
        self.assertEqual(self.ids(""), ALL)

    def test_aliases(self):
        self.assertEqual(self.ids("ws:Build"), self.ids("workstream:Build"))
        self.assertEqual(self.ids("uc:\"Use case 1\""), ["T-A-001"])
        self.assertEqual(self.ids("prio:Urgent"), ["T-A-003"])
        self.assertEqual(self.ids("state:Delayed"), ["T-A-003"])

    def test_case_does_not_matter_and_the_stored_word_is_kept(self):
        p = self.parse("STATUS:delayed")
        self.assertEqual(p["chips"][0]["values"], ["Delayed"])
        self.assertEqual(p["chips"][0]["text"], "status:Delayed")

    def test_not(self):
        self.assertEqual(self.ids("-status:Closed type:action"), ["T-A-001", "T-A-002", "T-A-003", "T-A-004"])
        self.assertEqual(self.ids("-owner:\"Owner One\" type:action"), ["T-A-002", "T-A-003", "T-A-005"])

    def test_two_negations_on_one_field_leave_out_both(self):
        p = self.parse("-status:Closed -status:Made")
        self.assertEqual(len(p["chips"]), 1)
        self.assertEqual(p["chips"][0]["text"], "-status:Closed,Made")

    def test_no_field_finds_the_items_with_nothing_there(self):
        self.assertEqual(self.ids("no:owner"), ["T-R-002"])
        self.assertEqual(self.ids("no:due is:open type:action"), [])
        self.assertEqual(self.ids("no:priority"), ["T-D-001", "T-D-002", "T-D-003", "T-D-004"])
        self.assertEqual(self.ids("no:workstream type:action"), ["T-A-002", "T-A-005"])
        self.assertEqual(self.ids("-no:owner type:risk,issue"), ["T-R-001"])

    def test_either(self):
        self.assertEqual(self.ids("status:Open,Pending type:decision"), ["T-D-001", "T-D-002"])
        self.assertEqual(self.ids("owner:none,\"Owner One\" type:risk,issue"), ["T-R-001", "T-R-002"])

    def test_a_later_chip_on_a_field_replaces_an_earlier_one(self):
        p = self.parse("status:Open status:Delayed")
        self.assertEqual([c["text"] for c in p["chips"]], ["status:Delayed"])

    def test_is_chips_all_have_to_hold(self):
        self.assertEqual(self.ids("is:open is:overdue"), ["T-A-001"])
        self.assertEqual(len(self.parse("is:open is:overdue")["chips"]), 2)

    def test_quoted_values_and_commas(self):
        p = self.parse('owner:"Owner Two","Owner One"')
        self.assertEqual(p["chips"][0]["values"], ["Owner Two", "Owner One"])
        self.assertEqual(p["chips"][0]["text"], 'owner:"Owner Two","Owner One"')


class Dates(Line):
    """Closed work is never overdue or due soon; a missing date is only `none`."""

    def test_overdue(self):
        self.assertEqual(self.ids("due:overdue"), ["T-A-001"])

    def test_today_and_the_next_seven_days(self):
        rows = [row("X-1", "action", "Today one", "Open", ME, "Low", TODAY), row("X-2", "action", "Seventh day", "Open", ME, "Low", "2026-11-05"),
                row("X-3", "action", "Eighth day", "Open", ME, "Low", "2026-11-06"), row("X-4", "action", "Yesterday", "Open", ME, "Low", "2026-10-28"),
                row("X-5", "action", "Closed today", "Closed", ME, "Low", TODAY)]
        def got(line):
            return [r["id"] for r in self.val(f"T.fl.apply({lit(rows)}, {lit(line)}, {lit(CTX)})")]
        self.assertEqual(got("due:today"), ["X-1"])
        self.assertEqual(got("due:next-7-days"), ["X-1", "X-2"])
        self.assertEqual(got("due:later"), ["X-3"])
        self.assertEqual(got("due:overdue"), ["X-4"])

    def test_next_7_days_on_the_project(self):
        self.assertEqual(self.ids("due:next-7-days"), ["T-A-002", "T-A-003", "T-R-001"])
        self.assertEqual(self.ids("due:later"), ["T-A-004", "T-D-001"])

    def test_no_date(self):
        self.assertEqual(self.ids("due:none"), self.ids("no:due"))
        self.assertIn("T-R-002", self.ids("no:due"))
        self.assertEqual(self.ids("due:no-date"), self.ids("no:due"))

    def test_a_decision_uses_the_date_it_is_needed_by(self):
        self.assertIn("T-D-001", self.ids("due:later"))
        self.assertNotIn("T-D-003", self.ids("due:overdue"))

    def test_the_words_come_back_as_typed(self):
        self.assertEqual(self.parse("due:next-7-days")["chips"][0]["text"], "due:next-7-days")
        self.assertEqual(self.parse("due:next-7-days")["chips"][0]["values"], ["soon"])


class Words(Line):
    def test_plain_words_search_titles_and_ids(self):
        self.assertEqual(self.ids("supplier"), ["T-R-001", "T-D-002"])
        self.assertEqual(self.ids("laptops"), ["T-A-004", "T-R-003"])
        self.assertEqual(self.ids("T-A-003"), ["T-A-003"])

    def test_every_word_has_to_be_there(self):
        self.assertEqual(self.ids("laptops the"), ["T-A-004"])
        self.assertEqual(self.ids("supplier slips"), ["T-R-001"])
        self.assertEqual(self.ids("supplier nothing-like-this"), [])

    def test_a_quoted_phrase_is_one_word(self):
        self.assertEqual(self.parse('"the old"')["words"], ["the old"])
        self.assertEqual(self.ids('"the old"'), ["T-A-005", "T-D-004"])
        self.assertEqual(self.ids('"old the"'), [])
        self.assertEqual(self.ids("old the"), ["T-A-005", "T-D-004"])

    def test_words_and_fields_together(self):
        self.assertEqual(self.ids("is:open supplier"), ["T-R-001", "T-D-002"])


class Messages(Line):
    """Every refusal is one plain sentence, and a word with an error is not applied, so the list never goes empty without a reason."""

    def test_a_wrong_status(self):
        self.assertEqual(self.one_error("status:Opne"), "No status is called Opne. Try Open, Pending, Delayed, Closed, Cancelled, Made or Withdrawn.")

    def test_the_wrong_status_sentence_for_a_project_with_only_the_five(self):
        rows = [r for r in ROWS if r["status"] in ("Open", "Closed")]
        p = self.val(f"T.fl.parse('status:x', {lit(rows)}, {lit(CTX)})")
        self.assertTrue(p["errors"][0]["msg"].startswith("No status is called x. Try Open, Pending, Delayed, Closed or Cancelled"), p)

    def test_the_issue_wording_with_the_five_statuses(self):
        msg = self.val("T.fl.badValue('status', 'X', [], {})")
        self.assertEqual(msg, "No status is called X. Try Open, Pending, Delayed, Closed or Cancelled.")

    def test_a_wrong_value_for_a_fixed_field(self):
        self.assertEqual(self.one_error("is:old"), "“old” is not a value for Is. Try open, closed, overdue, quiet, incomplete or archived.")
        self.assertEqual(self.one_error("due:sooon"), "“sooon” is not a value for Due. Try overdue, today, next-7-days, later or none.")
        self.assertEqual(self.one_error("type:bug"), "“bug” is not a value for Type. Try action, risk, issue, assumption, dependency or decision.")
        self.assertEqual(self.one_error("client:maybe"), "“maybe” is not a value for Client. Try shown or internal.")

    def test_a_wrong_owner_lists_at_most_eight(self):
        msg = self.one_error("owner:Nobody")
        self.assertTrue(msg.startswith("No owner is called Nobody. Try "), msg)
        self.assertIn("Owner Two", msg)
        rows = [row(f"X-{n}", "action", "t", "Open", f"Person {n:02d}") for n in range(12)]
        big = self.val(f"T.fl.parse('owner:Zed', {lit(rows)}, {lit(CTX)})")["errors"][0]["msg"]
        self.assertIn("and others. Type owner: to see them all.", big)
        self.assertNotIn("Person 09", big)

    def test_a_mistyped_field_says_what_can_be_used(self):
        msg = self.one_error("stauts:Open")
        self.assertEqual(msg, "There is no “stauts” filter. Did you mean status? You can filter by type:, status:, owner:, priority:, due:, "
                              "workstream:, usecase:, milestone:, client: and is:, or type plain words to search titles.")
        self.assertNotIn(":?", msg)

    def test_a_field_with_no_near_match(self):
        msg = self.one_error("zzzz:1")
        self.assertNotIn("Did you mean", msg)
        self.assertIn("type plain words to search titles", msg)

    def test_a_word_with_an_error_is_not_applied(self):
        self.assertEqual(self.ids("stauts:Open"), ALL)
        self.assertEqual(self.ids("is:open status:Opne"), self.ids("is:open"))

    def test_a_field_with_no_value(self):
        self.assertEqual(self.one_error("status:"), "Say what status to find, for example status:Open.")
        self.assertTrue(self.parse("status:")["errors"][0]["partial"])

    def test_no_needs_a_field_that_can_be_empty(self):
        self.assertEqual(self.one_error("no:"), "Say which field: no:owner finds items with no owner. It works with owner, priority, due, workstream, usecase and milestone.")
        self.assertEqual(self.one_error("no:status"), "Every item has a status, so no:status would find nothing. no: works with owner, priority, due, workstream, usecase and milestone.")
        self.assertEqual(self.one_error("no:banana"), "There is no “banana” field. no: works with owner, priority, due, workstream, usecase and milestone.")

    def test_owner_me_without_a_name(self):
        self.assertEqual(self.parse("owner:me", NOBODY)["notes"], ["Set your name in Settings to see your actions."])
        self.assertEqual(self.parse("owner:me", CTX)["notes"], [])
        self.assertEqual(self.ids("owner:me type:action", CTX), ["T-A-001", "T-A-004"])
        self.assertEqual(self.ids("owner:me", NOBODY), [], "no name: nothing is mine, and the note says why")
        self.assertEqual(self.val("T.fl.NO_ME"), "Set your name in Settings to see your actions.")

    def test_the_two_glossed_values_say_what_they_mean(self):
        self.assertEqual(self.parse("is:quiet")["chips"][0]["say"], "Not reviewed in 14 days")
        self.assertEqual(self.parse("is:incomplete")["chips"][0]["say"], "No owner or no date")
        sug = {s["label"]: s["gloss"] for s in self.val(f"T.fl.suggest('is:', {lit(ROWS)}, {lit(CTX)})")}
        self.assertEqual(sug["quiet"], "Not reviewed in 14 days")

    def test_a_project_with_no_values_yet_says_so(self):
        for field, plural in (("workstream", "workstreams"), ("usecase", "use cases"), ("milestone", "milestones"), ("owner", "owners")):
            self.assertEqual(self.val(f"T.fl.badValue('{field}', 'Build', [], {{}})"), f"This project has no {plural} yet.")
        self.assertEqual(self.one_error("workstream:Nope"), "No workstream is called Nope. Try Build or Data.")

    def test_quiet_archived_wait_for_the_page(self):
        for w, say in (("archived", "Archived work"),):
            self.assertEqual(self.one_error(f"is:{w}", OFF), f"{say} is not available on this page yet.")
        # is:quiet waits for a row that carries a date to count from (here none does); the rows of ROWS have one, so it is on
        undated = [r for r in ROWS if "reviewed" not in r]
        p = self.val(f"T.fl.parse('is:open,quiet', {lit(undated)}, {lit(OFF)})")
        self.assertEqual([e["msg"] for e in p["errors"]], ["Not reviewed in 14 days is not available on this page yet."])
        self.assertEqual(self.parse("is:quiet", OFF)["errors"], [])
        self.assertEqual(self.parse("is:open is:incomplete", OFF)["errors"], [])
        off = [s["label"] for s in self.val(f"T.fl.suggest('is:', {lit(undated)}, {lit(OFF)})")]
        self.assertEqual(off, ["open", "closed", "overdue", "incomplete"])
        on = [s["label"] for s in self.val(f"T.fl.suggest('is:', {lit(ROWS)}, {lit(OFF)})")]
        self.assertEqual(on, ["open", "closed", "overdue", "quiet", "incomplete"])
        self.assertEqual(self.val("typeof T.fl.hints + typeof T.fl.HINTS"), "undefinedundefined", "the Try chip data is gone with the chip line")

    def test_quiet_incomplete(self):
        self.assertEqual(self.ids("is:quiet"), ["T-R-001"])
        self.assertEqual(self.ids("is:incomplete"), ["T-A-002", "T-R-002", "T-D-002"], "a missing date counts for actions and decisions only; a missing owner for every type")
        self.assertTrue(self.parse("is:needed", dict(OFF, isReady=True))["errors"], "item 1158: needed is no longer a value of Is")
        self.assertEqual(self.ids("is:archived"), [])

    def test_no_message_starts_with_the_product_name_or_holds_a_date_or_a_name(self):
        msgs = [self.one_error(x) for x in ("status:Opne", "is:old", "stauts:x", "no:", "status:", "owner:Nobody")]
        msgs += [self.val("T.fl.NO_ME")]
        for m in msgs:
            self.assertFalse(m.lower().startswith("clark"), m)
            self.assertNotRegex(m, r"\d{2}-\d{2}-\d{4}|\d{4}-\d{2}-\d{2}", m)
            self.assertTrue(m.endswith((".", ")")) or m[-1].isalpha(), m)


class Chips(Line):
    def test_a_chip_model(self):
        c = self.parse("-status:Closed owner:me")["chips"]
        self.assertEqual([(x["field"], x["not"], x["values"], x["text"]) for x in c],
                         [("status", True, ["Closed"], "-status:Closed"), ("owner", False, ["me"], "owner:me")])
        self.assertEqual(c[0]["say"], "Status is not Closed")
        self.assertEqual(c[1]["say"], "Owner is Me (Owner One)")

    def test_no_chip_reads_as_words(self):
        c = self.parse("no:owner -no:due")["chips"]
        self.assertEqual([x["say"] for x in c], ["No owner", "Due is set"])
        self.assertEqual([x["text"] for x in c], ["no:owner", "-no:due"])

    def test_remove_a_chip(self):
        self.assertEqual(self.val(f"T.fl.removeChip('is:open status:Delayed supplier', 1, {lit(ROWS)}, {lit(CTX)})"), "is:open supplier")
        self.assertEqual(self.val(f"T.fl.removeChip('is:open', 9, {lit(ROWS)}, {lit(CTX)})"), "is:open")

    def test_backspace_removes_the_last_chip(self):
        self.assertEqual(self.val(f"T.fl.removeLast('is:open status:Delayed', {lit(ROWS)}, {lit(CTX)})"), "is:open")
        self.assertEqual(self.val(f"T.fl.removeLast('supplier', {lit(ROWS)}, {lit(CTX)})"), "supplier")
        self.assertEqual(self.val(f"T.fl.removeLast('', {lit(ROWS)}, {lit(CTX)})"), "")

    def test_the_line_is_written_back_the_same_way(self):
        for line in ("is:open", "is:open type:action owner:me", "-status:Closed,Cancelled due:overdue", "no:owner supplier",
                     'owner:"Owner Two" due:next-7-days', "is:open is:quiet", "client:shown workstream:Data"):
            once = self.val(f"T.fl.normalise({lit(line)}, {lit(ROWS)}, {lit(CTX)})")
            self.assertEqual(once, line)
            self.assertEqual(self.val(f"T.fl.normalise({lit(once)}, {lit(ROWS)}, {lit(CTX)})"), once)

    def test_clear_goes_back_to_the_start(self):
        self.assertEqual(self.val("T.fl.BASE"), "is:open")
        self.assertFalse(self.val(f"T.fl.canClear('is:open', {lit(ROWS)}, {lit(CTX)})"))
        self.assertFalse(self.val(f"T.fl.canClear('  is:open ', {lit(ROWS)}, {lit(CTX)})"))
        self.assertTrue(self.val(f"T.fl.canClear('is:open supplier', {lit(ROWS)}, {lit(CTX)})"))
        self.assertTrue(self.val(f"T.fl.canClear('', {lit(ROWS)}, {lit(CTX)})"))

    def test_the_word_being_typed_is_not_read_yet(self):
        self.assertEqual(self.val("T.fl.settled('is:open stat')"), "is:open ")
        self.assertEqual(self.val("T.fl.settled('is:open status:Open ')"), "is:open status:Open ")
        self.assertEqual(self.val("T.fl.settled('')"), "")

    def test_add_a_chip_replaces_the_one_for_the_same_field(self):
        self.assertEqual(self.val(f"T.fl.addText('is:open status:Open', 'status:Delayed', {lit(ROWS)}, {lit(CTX)})"), "is:open status:Delayed")


class Suggest(Line):
    def sug(self, w, ctx=CTX):
        return self.val(f"T.fl.suggest({lit(w)}, {lit(ROWS)}, {lit(ctx)})")

    def test_fields_first(self):
        got = self.sug("")
        self.assertEqual([s["label"] for s in got], ["is:", "type:", "status:", "owner:", "priority:", "due:", "workstream:", "usecase:", "milestone:", "client:", "no:"], "#640: an empty box lists every field, is first")
        self.assertEqual(got[0]["note"], "Open, closed, overdue, not reviewed…")
        self.assertTrue(all(s["note"] for s in got), "each field has its one-line note")
        self.assertEqual([s["label"] for s in self.sug("st")], ["status:"])
        self.assertEqual([s["label"] for s in self.sug("n")], ["no:"])
        self.assertEqual([s["ins"] for s in self.sug("-st")], ["-status:"])
        self.assertEqual(self.sug("supplier 1"), [])

    def test_then_values_with_counts(self):
        got = {s["label"]: s["n"] for s in self.sug("status:")}
        self.assertEqual((got["Open"], got["Pending"], got["Delayed"], got["Closed"], got["Cancelled"]), (6, 2, 1, 1, 0))
        self.assertEqual({s["label"]: s["n"] for s in self.sug("priority:")}["High"], 3)
        self.assertEqual({s["label"]: s["n"] for s in self.sug("due:")}["overdue"], 1)

    def test_values_narrow_as_you_type_and_keep_the_chips_before_them(self):
        got = self.sug("status:Del")
        self.assertEqual([s["ins"] for s in got], ["status:Delayed"])
        got = self.sug("status:Open,Pend")
        self.assertNotIn("status:Open,Open", [s["ins"] for s in self.sug("status:Open,O")])
        self.assertEqual([s["ins"] for s in got], ["status:Open,Pending"])

    def test_owner_offers_me_first_and_says_how_to_set_it(self):
        first = self.sug("owner:")[0]
        self.assertEqual((first["label"], first["note"], first["n"]), ("me", "Me (Owner One)", 4))
        self.assertEqual(self.sug("owner:", NOBODY)[0]["note"], "Me (set your name in Settings)")

    def test_no_offers_the_fields_that_can_be_empty(self):
        got = {s["label"]: s["n"] for s in self.sug("no:")}
        self.assertEqual(list(got), ["owner", "priority", "due", "workstream", "usecase", "milestone"])
        self.assertEqual(got["owner"], 1)

    def test_values_with_a_space_are_quoted(self):
        self.assertEqual([s["ins"] for s in self.sug("owner:Owner T")], ['owner:"Owner Two"'])

    def test_a_negated_field_keeps_its_dash(self):
        self.assertEqual([s["ins"] for s in self.sug("-status:Cl")], ["-status:Closed"])

    def test_an_unknown_field_offers_nothing(self):
        self.assertEqual(self.sug("banana:"), [])


class WithTheOlderFilters(Line):
    """Every one of the older filters (the Open / Closed / All switch, the type switch and the eight boxes) is reachable from the line,
    and a state and its line give the same rows."""

    def state(self, **kw):
        s = {"mode": "open", "type": "all", "filters": {}, "not": {}}
        s.update(kw)
        return s

    def same_rows(self, state):
        line = self.val(f"T.fl.fromState({lit(state)})")
        by_state = [r["id"] for r in self.val(f"T.filters.applyFilters({lit(ROWS)}, {lit(state)}, {lit(TODAY)})")]
        self.assertEqual(self.ids(line), by_state, line)
        self.assertEqual(self.parse(line)["errors"], [], line)
        return line

    def test_the_switches(self):
        self.assertEqual(self.same_rows(self.state()), "is:open")
        self.assertEqual(self.same_rows(self.state(mode="closed")), "is:closed")
        self.assertEqual(self.same_rows(self.state(mode="all")), "")
        self.assertEqual(self.same_rows(self.state(type="action")), "is:open type:action")
        self.assertEqual(self.same_rows(self.state(type="decision", mode="all")), "type:decision")
        self.assertEqual(self.same_rows(self.state(type="risk", mode="all")), "type:risk,issue,assumption,dependency")

    def test_each_of_the_eight_boxes(self):
        cases = {
            "workstream": (["Build"], "workstream:Build"), "status": (["Delayed", "Pending"], "status:Delayed,Pending"),
            "due": (["overdue", "soon"], "due:overdue,next-7-days"), "owner": (["Owner Two"], 'owner:"Owner Two"'),
            "priority": (["Urgent", "High"], "priority:Urgent,High"), "use_case": (["Use case 1"], 'usecase:"Use case 1"'),
            "milestone": (["Go live"], 'milestone:"Go live"'), "client": (["yes"], "client:shown"),
        }
        for field, (vals, text) in cases.items():
            line = self.same_rows(self.state(mode="all", filters={field: vals}))
            self.assertEqual(line, text)
            line = self.same_rows(self.state(mode="all", filters={field: vals}, **{"not": {field: True}}))
            self.assertEqual(line, "-" + text)

    def test_none_choices(self):
        for field, text in (("owner", "no:owner"), ("due", "no:due"), ("workstream", "no:workstream"), ("priority", "no:priority"),
                            ("milestone", "no:milestone"), ("use_case", "no:usecase")):
            self.assertEqual(self.same_rows(self.state(mode="all", filters={field: ["(none)" if field != "due" else "none"]})), text)
        self.assertEqual(self.same_rows(self.state(mode="all", filters={"owner": ["(none)", "Owner Two"]})), 'owner:none,"Owner Two"')

    def test_the_tiles_land_on_a_line_that_shows_what_they_counted(self):
        tiles = {"overdue": ("is:open type:action due:overdue", ["T-A-001"]),
                 "risks": ("is:open type:risk,issue,assumption,dependency priority:Urgent,High", ["T-R-001", "T-R-002"]),
                 "decisions": ("is:open type:decision status:Pending", ["T-D-001", "T-D-002"])}
        import_state = {
            "overdue": self.state(type="action", filters={"due": ["overdue"]}),
            "risks": self.state(type="risk", filters={"priority": ["Urgent", "High"]}),
            "decisions": self.state(type="decision", filters={"status": ["Pending"]}),
        }
        for key, (line, want) in tiles.items():
            self.assertEqual(self.val(f"T.fl.fromState({lit(import_state[key])})"), line)
            self.assertEqual(self.ids(line), want, key)
        # and the tiles' own states (the dashboard's) give the same line

    def test_a_line_as_the_older_state(self):
        got = self.val(f"T.fl.toState('is:closed type:action owner:\"Owner Two\" -priority:Low', {lit(ROWS)}, {lit(CTX)})")
        self.assertTrue(got["exact"])
        self.assertEqual(got["state"], {"mode": "closed", "type": "action", "filters": {"owner": ["Owner Two"], "priority": ["Low"]}, "not": {"priority": True}})
        got = self.val(f"T.fl.toState('type:risk,issue,assumption,dependency', {lit(ROWS)}, {lit(CTX)})")
        self.assertEqual((got["state"]["mode"], got["state"]["type"], got["exact"]), ("all", "risk", True))

    def test_what_the_older_state_cannot_hold_is_listed(self):
        got = self.val(f"T.fl.toState('is:open supplier is:quiet due:today', {lit(ROWS)}, {lit(CTX)})")
        self.assertFalse(got["exact"])
        self.assertEqual(got["rest"], ["due:today", "supplier"])
        self.assertEqual(got["state"]["filters"], {"reviewed": ["stale"]}, "is:quiet is the Freshness filter")
        self.assertEqual(got["state"]["mode"], "open")

    def test_state_to_line_to_state(self):
        for st in (self.state(), self.state(mode="closed", type="action", filters={"status": ["Closed"]}),
                   self.state(mode="all", filters={"workstream": ["Build", "Data"], "owner": ["Owner One"]}, **{"not": {"owner": True}})):
            line = self.val(f"T.fl.fromState({lit(st)})")
            got = self.val(f"T.fl.toState({lit(line)}, {lit(ROWS)}, {lit(CTX)})")
            self.assertEqual(got["state"], st)


class SavedViews(Line):
    def v(self, expr):
        return self.val(f"T.fl.{expr}")

    def test_a_project_starts_with_the_five_core_views_then_three_of_its_own(self):
        """#640: the core five first, in this order, then Overdue and My actions as ordinary views (item 1158: no Waiting on the client)."""
        views = self.v("viewsGet(null, 'ABC')")
        self.assertEqual([x["name"] for x in views], ["Open items", "Actions", "Risks and issues", "Decisions", "All work items", "Overdue", "My actions"])
        self.assertEqual([x["line"] for x in views[:5]], ["is:open", "type:action is:open", "type:risk,issue is:open", "type:decision is:open", ""])
        self.assertEqual([bool(x.get("core")) for x in views], [True] * 5 + [False] * 2)
        for x in views:
            self.assertEqual(self.parse(x["line"])["errors"], [], x)

    def test_core_views_keep_their_line_can_be_renamed_and_deleted_and_are_stored_apart(self):
        views = self.v("viewsGet(null, 'ABC')")
        for cid in ("core-open", "core-actions", "core-risks", "core-decisions", "core-all"):
            self.assertFalse(self.v(f"saveView({lit(views)}, {lit(cid)}, 'is:open owner:me')")["ok"], cid)
            self.assertTrue(self.v(f"renameView({lit(views)}, {lit(cid)}, 'Mine')")["ok"], cid)
            self.assertEqual(len(self.v(f"deleteView({lit(views)}, {lit(cid)})")["views"]), 6, cid)
        got = self.val("(function(){ var s = {store: {}, getItem(k) { return k in this.store ? this.store[k] : null; }, setItem(k, v) { this.store[k] = String(v); }};"
                       f" T.fl.viewsPut(s, 'ABC', {lit(views)}); return JSON.parse(s.store['clark.fviews']).ABC.map(function (v) {{ return v.id; }}); }})()")
        self.assertEqual(got, ["overdue", "mine"], "only the person's own views are stored")

    def test_a_renamed_or_deleted_core_view_is_remembered_in_its_own_key_and_a_plain_set_stores_nothing_extra(self):
        fake = "{store: {}, getItem(k) { return k in this.store ? this.store[k] : null; }, setItem(k, v) { this.store[k] = String(v); }}"
        got = self.val(f"(function(){{ var s = {fake}; var v = T.fl.viewsGet(s, 'ABC'); T.fl.viewsPut(s, 'ABC', v); var plain = JSON.parse(s.store['clark.fcore']);"
                       " v = T.fl.renameView(v, 'core-actions', 'Tasks').views; v = T.fl.deleteView(v, 'core-open').views; T.fl.viewsPut(s, 'ABC', v);"
                       " return [plain, JSON.parse(s.store['clark.fcore']), T.fl.viewsGet(s, 'ABC').map(function (x) { return x.name; }), T.fl.viewsGet(s, 'DEF').length]; })()")
        self.assertEqual(got[0], {}, "nothing changed: nothing extra is stored")
        self.assertEqual(got[1], {"ABC": {"names": {"core-actions": "Tasks"}, "gone": ["core-open"]}})
        self.assertEqual(got[2], ["Tasks", "Risks and issues", "Decisions", "All work items", "Overdue", "My actions"])
        self.assertEqual(got[3], 7, "another project is untouched")

    def test_a_stored_set_keeps_its_views_after_the_core_five(self):
        """#640: nothing stored is lost; an older stored plain Open items is replaced by the core one, a changed one stays."""
        stored = [{"id": "open", "name": "Open items", "line": "is:open"}, {"id": "overdue", "name": "Late", "line": "is:open due:overdue"},
                  {"id": "open2", "name": "Mine", "line": "owner:me", "archived": True}, {"id": "open", "name": "My open", "line": "is:open owner:me"}]
        got = self.val("(function(){ var s = {getItem() { return JSON.stringify({ABC: %s}); }, setItem() {}}; return T.fl.viewsGet(s, 'ABC'); })()" % json.dumps(stored))
        self.assertEqual([x["name"] for x in got], ["Open items", "Actions", "Risks and issues", "Decisions", "All work items", "Late", "Mine", "My open"])
        self.assertEqual([x["id"] for x in got[5:]], ["overdue", "open2", "open"])
        self.assertTrue(got[6]["archived"])

    def test_the_starting_views_show_what_their_names_say(self):
        views = {x["id"]: x["line"] for x in self.v("DEFAULT_VIEWS")}
        self.assertEqual(self.ids(views["overdue"]), ["T-A-001"])
        self.assertEqual(self.ids(views["mine"]), ["T-A-001", "T-A-004"])
        self.assertEqual(self.v(f"viewCount({lit(self.v('DEFAULT_VIEWS')[0])}, {lit(ROWS)}, {lit(CTX)})"), 1)

    def test_a_view_the_line_cannot_read_says_why_in_plain_words(self):
        """#589: it is listed with a message, not hidden. A view that reads gives no message."""
        old = {"id": "old", "name": "Old", "line": "is:open colour:red"}
        said = self.v(f"viewTrouble({lit(old)}, {lit(ROWS)}, {lit(CTX)})")
        self.assertTrue(said.startswith("This view cannot be used any more. There is no \u201ccolour\u201d filter."), said)
        self.assertTrue(said.endswith(" Rename it or delete it."), said)
        self.assertNotIn("Did you mean", said, "the message keeps to its first sentence")
        self.assertEqual(self.v(f"viewTrouble({lit(self.v('DEFAULT_VIEWS')[1])}, {lit(ROWS)}, {lit(CTX)})"), "")
        self.assertEqual(self.v(f"viewTrouble(null, {lit(ROWS)}, {lit(CTX)})"), "")
        archived = {"id": "arch", "name": "Archived", "line": "is:archived"}
        self.assertIn("is not available on this page yet.", self.v(f"viewTrouble({lit(archived)}, {lit(ROWS)}, {lit(OFF)})"))
        self.assertEqual(self.v(f"viewTrouble({lit(archived)}, {lit(ROWS)}, {lit(CTX)})"), "", "once the page can answer it, it reads")

    def test_a_stored_waiting_on_the_client_view_stays_listed_and_says_it_cannot_be_used(self):
        """Item 1158: is:needed is gone. A person's stored copy of the old starting view is kept (nothing is deleted) and says why it does nothing."""
        old = {"id": "client", "name": "Waiting on the client", "line": "is:open is:needed"}
        said = self.v(f"viewTrouble({lit(old)}, {lit(ROWS)}, {lit(CTX)})")
        self.assertTrue(said.startswith("This view cannot be used any more."), said)
        self.assertFalse(self.v(f"heldBack({lit(old)}, {lit(ROWS)}, {lit(CTX)})"), "it is not a starting view any more, so it stays in the tabs")
        stored = [old, {"id": "overdue", "name": "Overdue", "line": "is:open due:overdue"}]
        got = self.val("(function(){ var s = {getItem() { return JSON.stringify({ABC: %s}); }, setItem() {}}; return T.fl.viewsGet(s, 'ABC').map(function (x) { return x.id; }); })()" % json.dumps(stored))
        self.assertIn("client", got)

    def test_no_starting_view_is_held_back(self):
        """#589, then item 1158: every starting view reads on a page that can answer is:archived or not, so none is held back."""
        for ctx in (OFF, CTX):
            self.assertTrue(all(not self.v(f"heldBack({lit(v)}, {lit(ROWS)}, {lit(ctx)})") for v in self.v("DEFAULT_VIEWS")))
        self.assertFalse(self.v(f"heldBack({lit({'id': 'old', 'name': 'Old', 'line': 'colour:red'})}, {lit(ROWS)}, {lit(OFF)})"))

    def test_the_dot(self):
        view = {"id": "o", "name": "Overdue", "line": "is:open due:overdue"}
        def differs(line):
            return self.v(f"differs({lit(view)}, {lit(line)}, {lit(ROWS)}, {lit(CTX)})")
        self.assertFalse(differs("is:open due:overdue"))
        self.assertFalse(differs("due:overdue   is:open"), "spacing and order do not count")
        self.assertFalse(differs("IS:OPEN DUE:Overdue"))
        self.assertTrue(differs("is:open"))
        self.assertTrue(differs("is:open due:overdue supplier"))
        self.assertTrue(differs("is:open due:later"))
        self.assertTrue(differs("-is:open due:overdue"))
        self.assertFalse(self.v(f"differs(null, 'is:open', {lit(ROWS)}, {lit(CTX)})"))

    def test_add(self):
        got = self.v(f"addView({lit(self.v('DEFAULT_VIEWS'))}, '  Build   risks ', 'workstream:Build')")
        self.assertTrue(got["ok"])
        self.assertEqual(got["views"][-1], {"id": got["id"], "name": "Build risks", "line": "workstream:Build"})
        self.assertEqual(len(got["views"]), 3)
        self.assertEqual(len({x["id"] for x in got["views"]}), 3)

    def test_add_refusals_are_plain_and_change_nothing(self):
        base = self.v("DEFAULT_VIEWS")
        self.assertEqual(self.v(f"addView({lit(base)}, '   ', 'is:open')"), {"ok": False, "message": "Give the view a name."})
        self.assertEqual(self.v(f"addView({lit(base)}, 'overdue', 'is:open')"), {"ok": False, "message": "A view called overdue already exists. Choose another name."})
        self.assertEqual(self.v(f"addView({lit(base)}, {lit('x' * 41)}, 'is:open')")["message"], "Keep the name to 40 characters or fewer.")
        full = [{"id": f"v{n}", "name": f"View {n}", "line": ""} for n in range(20)]
        self.assertEqual(self.v(f"addView({lit(full)}, 'One more', '')")["message"], "You can keep 20 saved views. Delete one to make room.")

    def test_save_over_a_view(self):
        got = self.v(f"saveView({lit(self.v('DEFAULT_VIEWS'))}, 'overdue', 'is:open due:overdue owner:me')")
        self.assertEqual(next(x for x in got["views"] if x["id"] == "overdue")["line"], "is:open due:overdue owner:me")
        self.assertEqual(self.v(f"saveView({lit(self.v('DEFAULT_VIEWS'))}, 'zzz', '')")["message"], "That view is not there any more.")

    def test_rename(self):
        base = self.v("DEFAULT_VIEWS")
        got = self.v(f"renameView({lit(base)}, 'mine', 'Mine')")
        self.assertEqual(next(x for x in got["views"] if x["id"] == "mine")["name"], "Mine")
        self.assertEqual(self.v(f"renameView({lit(base)}, 'mine', 'Overdue')")["message"], "A view called Overdue already exists. Choose another name.")
        self.assertTrue(self.v(f"renameView({lit(base)}, 'mine', 'my actions')")["ok"], "the same name in other capitals is its own name")
        self.assertEqual(self.v(f"renameView({lit(base)}, 'mine', '')")["message"], "Give the view a name.")

    def test_row_1071_views_are_reordered_across_core_and_own_and_the_order_is_kept_per_project(self):
        base = self.v("viewsGet(null, 'ABC')")
        ids = [x["id"] for x in base]
        got = self.v(f"reorderViews({lit(base)}, ['core-all', 'core-open'])")
        self.assertTrue(got["ok"])
        self.assertEqual([x["id"] for x in got["views"]][:5], ["core-all", "core-actions", "core-risks", "core-decisions", "core-open"], "the two take each other's places")
        self.assertEqual(self.v(f"reorderViews({lit(base)}, ['nope'])")["ok"], False)
        fake = "{store: {}, getItem(k) { return k in this.store ? this.store[k] : null; }, setItem(k, v) { this.store[k] = String(v); }}"
        out = self.val(f"(function(){{ var s = {fake}; var v = T.fl.viewsGet(s, 'ABC'); v = T.fl.reorderViews(v, ['mine', 'core-open']).views; T.fl.viewsPut(s, 'ABC', v);"
                       " return [T.fl.viewsGet(s, 'ABC').map(function (x) { return x.id; }), T.fl.viewsGet(s, 'DEF').map(function (x) { return x.id; }), T.fl.viewsPut(s, 'ABC', T.fl.addView(T.fl.viewsGet(s, 'ABC'), 'Late', '').views), T.fl.viewsGet(s, 'ABC').map(function (x) { return x.id; })]; })()")
        self.assertEqual(out[0][0], "mine")
        self.assertEqual(out[0][-1], "core-open")
        self.assertEqual(out[1], ids, "another project keeps its own order")
        self.assertEqual(out[3][-1], "v8", "a new view goes last")
        self.assertEqual(out[3][0], "mine", "and the order stays")

    def test_row_1071_a_duplicate_is_called_name_copy_sits_next_to_it_and_is_the_persons_own(self):
        base = self.v("viewsGet(null, 'ABC')")
        got = self.v(f"duplicateView({lit(base)}, 'core-actions')")
        self.assertTrue(got["ok"])
        names = [x["name"] for x in got["views"]]
        self.assertEqual(names[1:3], ["Actions", "Actions copy"])
        copy = got["views"][2]
        self.assertEqual(copy["line"], "type:action is:open")
        self.assertFalse(copy.get("core"), "a copy of a core view is not core")
        again = self.v(f"duplicateView({lit(got['views'])}, 'core-actions')")
        self.assertEqual([x["name"] for x in again["views"]][1:4], ["Actions", "Actions copy 2", "Actions copy"])
        self.assertFalse(self.v(f"duplicateView({lit(base)}, 'zzz')")["ok"])

    def test_mutation_proof_reorder_refuses_a_list_that_names_a_view_twice(self):
        base = self.v("viewsGet(null, 'ABC')")
        got = self.v(f"reorderViews({lit(base)}, ['core-all', 'core-all'])")
        self.assertFalse(got["ok"], "one view twice would put it in two places")

    def test_mutation_proof_duplicate_is_refused_when_the_person_already_keeps_the_most(self):
        full = [{"id": f"v{n}", "name": f"View {n}", "line": ""} for n in range(20)]
        got = self.v(f"duplicateView({lit(full)}, 'v3')")
        self.assertFalse(got["ok"])
        self.assertEqual(got["message"], "You can keep 20 saved views. Delete one to make room.")

    def test_mutation_proof_the_starting_order_stores_nothing_and_going_back_to_it_clears_the_stored_order(self):
        fake = "{store: {}, getItem(k) { return k in this.store ? this.store[k] : null; }, setItem(k, v) { this.store[k] = String(v); }}"
        out = self.val("(function(){ var s = %s; var v = T.fl.viewsGet(s, 'ABC'); T.fl.viewsPut(s, 'ABC', v);"
                       " var a = JSON.parse(s.getItem('clark.forder') || '{}');"
                       " var ids = v.map(function (x) { return x.id; }); ids[0] = v[1].id; ids[1] = v[0].id;"
                       " T.fl.viewsPut(s, 'ABC', T.fl.reorderViews(v, ids.slice(0, 2)).views);"
                       " var b = JSON.parse(s.getItem('clark.forder') || '{}');"
                       " T.fl.viewsPut(s, 'ABC', v);"
                       " var c = JSON.parse(s.getItem('clark.forder') || '{}');"
                       " return [a, b, c]; })()" % fake)
        self.assertNotIn("ABC", out[0], "the order a project starts with is not stored")
        self.assertIn("ABC", out[1], "a changed order is stored")
        self.assertNotIn("ABC", out[2], "putting it back to the start clears what was stored")

    def test_a_deleted_view_is_gone_and_there_is_no_way_back(self):
        base = self.v("DEFAULT_VIEWS")
        gone = self.v(f"deleteView({lit(base)}, 'mine')")
        self.assertEqual([x["id"] for x in gone["views"]], ["overdue"])
        self.assertFalse(self.v(f"deleteView({lit(gone['views'])}, 'mine')")["ok"])
        keys = self.val("Object.keys(T.fl)")
        for name in ("archiveView", "restoreView", "archivedViews"):
            self.assertNotIn(name, keys)

    def test_insert_a_deleted_view_back_where_it_was(self):
        """Row 1071: the Undo after Delete view puts the tab back at its place."""
        base = self.v("viewsGet(null, 'ABC')")
        gone = self.v(f"deleteView({lit(base)}, 'core-risks')")["views"]
        back = self.v(f"insertView({lit(gone)}, {lit(base[2])}, 2)")
        self.assertEqual(back["views"], base)
        self.assertFalse(self.v(f"insertView({lit(base)}, {lit(base[2])}, 2)")["ok"], "already there")

    def test_insert_a_deleted_view_at_the_end(self):
        """Row 1071: Undo of deleting the last tab puts it last again (the place is the length, not the last index)."""
        base = self.v("viewsGet(null, 'ABC')")
        gone = self.v(f"deleteView({lit(base)}, 'mine')")["views"]
        back = self.v(f"insertView({lit(gone)}, {lit(base[-1])}, {len(gone)})")
        self.assertEqual(back["views"], base)

    def test_row_1071_reorder_refuses_a_repeated_or_empty_list_and_insert_stays_inside_the_list(self):
        base = self.v("viewsGet(null, 'ABC')")
        self.assertFalse(self.v(f"reorderViews({lit(base)}, ['core-all', 'core-all'])")["ok"], "one view named twice")
        self.assertFalse(self.v(f"reorderViews({lit(base)}, [])")["ok"], "nothing to place")
        gone = self.v(f"deleteView({lit(base)}, 'core-risks')")["views"]
        first = self.v(f"insertView({lit(gone)}, {lit(base[2])}, -5)")["views"]
        self.assertEqual(first[0]["id"], "core-risks", "a place before the start is the start")
        last = self.v(f"insertView({lit(gone)}, {lit(base[2])}, 99)")["views"]
        self.assertEqual(last[-1]["id"], "core-risks", "a place past the end is the end")
        self.assertEqual(len(last), len(base))

    def test_row_1071_a_copy_of_a_long_name_still_fits_the_name_limit(self):
        base = self.v("viewsGet(null, 'ABC')")
        added = self.v(f"addView({lit(base)}, {lit('y' * 40)}, '')")["views"]
        got = self.v(f"duplicateView({lit(added)}, {lit(added[-1]['id'])})")
        self.assertTrue(got["ok"], got)
        copy = got["views"][len(added)]
        self.assertLessEqual(len(copy["name"]), 40)
        self.assertTrue(copy["name"].endswith(" copy"))

    def test_row_1071_the_starting_order_stores_nothing_extra(self):
        fake = "{store: {}, getItem(k) { return k in this.store ? this.store[k] : null; }, setItem(k, v) { this.store[k] = String(v); }}"
        out = self.val(f"(function(){{ var s = {fake}; var v = T.fl.viewsGet(s, 'ABC'); T.fl.viewsPut(s, 'ABC', T.fl.addView(v, 'Late', '').views);"
                       " var a = JSON.parse(s.store['clark.forder'] || '{}'); T.fl.viewsPut(s, 'ABC', T.fl.reorderViews(T.fl.viewsGet(s, 'ABC'), ['mine', 'core-open']).views);"
                       " return [a.ABC === undefined, JSON.parse(s.store['clark.forder']).ABC !== undefined]; })()")
        self.assertEqual(out, [True, True], "the natural order (core first, then own) keeps no order; a changed one does")

    def test_a_deleted_views_id_is_never_given_to_a_new_view(self):
        """Row 1071: after Delete view, a new view must not take the id the deleted one had, or its Undo could not put it back."""
        three = [{"id": "v1", "name": "One", "line": ""}, {"id": "v2", "name": "Two", "line": ""}, {"id": "v3", "name": "Three", "line": ""}]
        gone = self.v(f"deleteView({lit(three)}, 'v3')")["views"]
        new = self.v(f"addView({lit(gone)}, 'Four', '')")
        self.assertNotEqual(new["id"], "v3")
        dup = self.v(f"duplicateView({lit(gone)}, 'v1')")
        self.assertNotEqual(dup["id"], "v3")
        back = self.v(f"insertView({lit(new['views'])}, {lit(three[2])}, 2)")
        self.assertTrue(back["ok"], "the deleted view can still come back after a new one was made")
        self.assertEqual(sorted(x["id"] for x in back["views"]), sorted(["v1", "v2", "v3", new["id"]]))

    def test_insert_refuses_a_name_a_view_already_has(self):
        """Row 1071: Undo must not make two views with one name (addView and renameView forbid that too); it says why."""
        base = [{"id": "a1", "name": "Alpha", "line": ""}, {"id": "b1", "name": "Beta", "line": ""}]
        gone = self.v(f"deleteView({lit(base)}, 'b1')")["views"]
        other = self.v(f"addView({lit(gone)}, 'beta', '')")["views"]
        got = self.v(f"insertView({lit(other)}, {lit(base[1])}, 1)")
        self.assertFalse(got["ok"])
        self.assertIn("already exists", got["message"])

    def test_insert_refuses_a_twenty_first_view(self):
        """Row 1071: Undo must not take a person past 20 saved views (addView and duplicateView stop there too); a core view is not counted."""
        full = [{"id": f"v{n}", "name": f"View {n}", "line": ""} for n in range(20)]
        gone = {"id": "old", "name": "Old one", "line": ""}
        got = self.v(f"insertView({lit(full)}, {lit(gone)}, 3)")
        self.assertFalse(got["ok"])
        self.assertEqual(got["message"], "You can keep 20 saved views. Delete one to make room.")
        core = {"id": "core-all", "name": "All", "line": "", "core": True}
        self.assertTrue(self.v(f"insertView({lit(full)}, {lit(core)}, 0)")["ok"], "a core view does not count toward the 20")
        self.assertTrue(self.v(f"insertView({lit(full[:19])}, {lit(gone)}, 3)")["ok"], "19 plus one is 20 and fits")

    def test_a_view_added_or_missing_from_the_stored_order_still_shows(self):
        fake = "{store: {'clark.forder': JSON.stringify({ABC: ['mine', 'gone', 'core-all']}) }, getItem(k) { return k in this.store ? this.store[k] : null; }, setItem(k, v) { this.store[k] = String(v); }}"
        got = self.val(f"T.fl.viewsGet({fake}, 'ABC').map(function (x) {{ return x.id; }})")
        self.assertEqual(got, ["mine", "core-all", "core-open", "core-actions", "core-risks", "core-decisions", "overdue"])

    def test_new_ids_never_repeat(self):
        views = self.v("DEFAULT_VIEWS")
        a = self.v(f"addView({lit(views)}, 'A', '')")
        b = self.v(f"addView({lit(a['views'])}, 'B', '')")
        self.assertNotEqual(a["id"], b["id"])

    def test_the_functions_do_not_change_what_they_are_given(self):
        base = self.v("DEFAULT_VIEWS")
        self.assertEqual(self.val(f"(function(){{ var v = {lit(base)}; T.fl.addView(v, 'A', ''); T.fl.deleteView(v, 'mine'); T.fl.renameView(v, 'mine', 'Z'); return v; }})()"), base)

    def test_hostile_view_names_never_throw_and_never_store_more_than_the_limit(self):
        """Hostile input on the saved-view name path (add, rename, duplicate): empty, huge, unicode, control characters, quotes, markup."""
        names = ["", "   ", "\n\t ", "x" * 41, "x" * 100000, "caf\u00e9 \u202e rtl \U0001F600", "a\u0000b", "a\nb\tc  d", "'; DROP TABLE v; --",
                 '"quoted"', "<img src=x onerror=alert(1)>", "</script><b>", "{{x}}", "${1+1}"]
        for n in names:
            got = self.v(f"addView([], {lit(n)}, '')")
            clean = " ".join(n.split())
            if not clean or len(clean) > 40:
                self.assertFalse(got["ok"], repr(n[:20]))
                self.assertTrue(got["message"], repr(n[:20]))
            else:
                self.assertTrue(got["ok"], repr(n))
                self.assertEqual(got["views"][0]["name"], clean, "white space (newlines, tabs) is folded to single spaces; the text is kept as typed")
            base = [{"id": "a1", "name": "Alpha", "line": ""}]
            r = self.v(f"renameView({lit(base)}, 'a1', {lit(n)})")
            self.assertEqual(r["ok"], bool(clean) and len(clean) <= 40, repr(n[:20]))
        dup = self.v(f"duplicateView({lit([{'id': 'a1', 'name': 'x' * 40, 'line': ''}])}, 'a1')")
        self.assertTrue(dup["ok"])
        self.assertLessEqual(len(dup["views"][1]["name"]), 40, "a copy of a name at the limit still fits the limit")

    def test_hostile_insert_places_and_views_never_throw(self):
        """Undo of a delete with a bad place or a bad view: the place is clamped, a missing or nameless view is refused."""
        base = [{"id": "a1", "name": "Alpha", "line": ""}, {"id": "b1", "name": "Beta", "line": ""}]
        gone = {"id": "c1", "name": "Gamma", "line": ""}
        for at, want in [(-5, 0), (0, 0), (1, 1), (99, 2), ("x", 0), (None, 0), (1.9, 1), (float("inf"), 2)]:
            lit_at = "Infinity" if at == float("inf") else lit(at)
            got = self.v(f"insertView({lit(base)}, {lit(gone)}, {lit_at})")
            self.assertTrue(got["ok"], at)
            self.assertEqual([x["id"] for x in got["views"]].index("c1"), want, at)
        for bad in ["null", "{}", "{id: 'z', name: ''}", "{id: 'z', name: '" + "x" * 5000 + "'}"]:
            self.assertFalse(self.v(f"insertView({lit(base)}, {bad}, 0)")["ok"], bad[:30])
        self.assertTrue(self.v(f"insertView(null, {lit(gone)}, 0)")["ok"])

    def test_hostile_line_words_for_archived_are_read_without_throwing(self):
        """The line words that the archived list now depends on: markup, quotes, control characters and a huge line never throw."""
        for line in ["is:archived", "is:archived " + "x" * 50000, "is:archived \u0000 \n\t", "is:\"archived\"", "is:<b>archived</b>", "-is:archived", "is:archived is:archived", "\U0001F600 is:archived"]:
            p = self.val(f"T.fl.parse({lit(line)}, {lit(ROWS)}, {lit(dict(CTX, archivedReady=True))})")
            self.assertIn("errors", p, line[:20])
        ok = self.parse("is:archived", dict(OFF, archivedReady=True))
        self.assertEqual(ok["errors"], [], "the Edit page answers is:archived")
        self.assertTrue(self.parse("is:archived", OFF)["errors"], "a page that cannot answer it says so, never silently matches")

    def test_archivedReady_turns_on_is_archived_and_nothing_else(self):
        """Mutation audit of PR 1333: archivedReady is the Edit page saying it can answer is:archived. It must not also switch on
        any other word that waits for isReady; a flag that opened every held-back word survived the old tests."""
        on = dict(OFF, archivedReady=True)
        self.assertTrue(self.val(f"T.fl.isOn('archived', {lit(on)}, [])"))
        self.assertFalse(self.val(f"T.fl.isOn('archived', {lit(OFF)}, [])"))
        self.assertTrue(self.parse("is:needed", on)["errors"], "item 1158: is:needed is an unknown state, with or without archivedReady")
        self.assertEqual(self.parse("is:archived", on)["errors"], [])


class Memory(Line):
    """Storage is passed in. Here a plain object stands in for it; a broken one stands in for a private window."""
    FAKE = "{store: {}, getItem(k) { return k in this.store ? this.store[k] : null; }, setItem(k, v) { this.store[k] = String(v); }}"
    BROKEN = "{getItem() { throw new Error('no'); }, setItem() { throw new Error('no'); }}"

    def test_the_line_is_kept_per_project(self):
        got = self.val(f"(function(){{ var s = {self.FAKE}; T.fl.linePut(s, 'ABC', 'is:open owner:me'); T.fl.linePut(s, 'DEF', 'is:closed');"
                       " return [T.fl.lineGet(s, 'ABC'), T.fl.lineGet(s, 'DEF'), T.fl.lineGet(s, 'GHI')]; })()")
        self.assertEqual(got, ["is:open owner:me", "is:closed", "is:open"])

    def test_a_browser_that_refuses_storage_still_works(self):
        got = self.val(f"(function(){{ var s = {self.BROKEN}; return [T.fl.linePut(s, 'ABC', 'x'), T.fl.lineGet(s, 'ABC'), T.fl.viewsPut(s, 'ABC', []), T.fl.viewsGet(s, 'ABC').length, T.fl.linePut(null, 'A', 'x'), T.fl.lineGet(null, 'A')]; }})()")
        self.assertEqual(got, [False, "is:open", False, 7, False, "is:open"])

    def test_bad_stored_data_gives_the_start(self):
        got = self.val("(function(){ var s = {getItem() { return '[1,2'; }, setItem() {}}; return [T.fl.lineGet(s, 'A'), T.fl.viewsGet(s, 'A').length]; })()")
        self.assertEqual(got, ["is:open", 7])
        got = self.val("(function(){ var s = {getItem() { return JSON.stringify({A: 5}); }, setItem() {}}; return [T.fl.lineGet(s, 'A'), T.fl.viewsGet(s, 'A').length]; })()")
        self.assertEqual(got, ["is:open", 7])
        got = self.val("(function(){ var s = {getItem() { return JSON.stringify({A: [{id: 1}]}); }, setItem() {}}; return T.fl.viewsGet(s, 'A').length; })()")
        self.assertEqual(got, 7)

    def test_views_are_kept_per_project(self):
        got = self.val(f"(function(){{ var s = {self.FAKE}; var a = T.fl.addView(T.fl.viewsGet(s, 'ABC'), 'Mine too', 'owner:me').views; T.fl.viewsPut(s, 'ABC', a);"
                       " return [T.fl.viewsGet(s, 'ABC').length, T.fl.viewsGet(s, 'DEF').length]; })()")
        self.assertEqual(got, [8, 7])

    def test_a_long_line_is_cut_not_refused(self):
        got = self.val(f"(function(){{ var s = {self.FAKE}; T.fl.linePut(s, 'A', 'x'.repeat(2000)); return T.fl.lineGet(s, 'A').length; }})()")
        self.assertLessEqual(got, 600)


class Hardening(Line):
    PROTO = ["constructor", "__proto__", "toString", "hasOwnProperty", "valueOf"]

    def test_words_on_the_object_prototype_are_plain_errors_never_a_throw(self):
        for w in self.PROTO:
            for line in (f"{w}:x", f"-{w}:x", f"no:{w}", f"-no:{w}", f"status:{w}", f"owner:{w},Open", f"is:{w}", f"due:{w}", f"client:{w}",
                         f"type:{w}", f"{w}:{w}", f'workstream:"{w}"'):
                p = self.parse(line)
                self.assertEqual(p["chips"], [], line)
                self.assertTrue(p["errors"] or p["words"], line)
                self.assertTrue(all(isinstance(e["msg"], str) and e["msg"] for e in p["errors"]), line)
                self.assertIsInstance(self.val(f"T.fl.normalise({lit(line)}, {lit(ROWS)}, {lit(CTX)})"), str)
                self.assertIsInstance(self.val(f"T.fl.suggest({lit(line)}, {lit(ROWS)}, {lit(CTX)})"), list)
                if not p["words"]:
                    self.assertEqual(self.ids(line), ALL, line)

    def test_a_row_value_named_like_a_prototype_key_is_just_a_value(self):
        rows = [row("T-A-001", "action", "One", "Open", "constructor", workstream="__proto__"), row("T-A-002", "action", "Two", "Open", "Owner Two")]
        p = self.val(f"T.fl.parse('owner:constructor workstream:__proto__', {lit(rows)}, {lit(CTX)})")
        self.assertEqual(p["errors"], [])
        self.assertEqual([c["glosses"] for c in p["chips"]], [[], []])
        got = [r["id"] for r in self.val(f"T.fl.apply({lit(rows)}, 'owner:constructor', {lit(CTX)})")]
        self.assertEqual(got, ["T-A-001"])

    AWKWARD = ['owner:"First', 'owner:"First Last', '"', '""', '"""', 'a"b', 'status:"Open', 'status:Open"', 'status:"Open"" x', '"unbalanced words here',
               'x "y', 'x"y z"', 'status:"Open,Pending', 'status:Open,"Pending', 'no:"owner', '-status:"Closed', 'owner:"', 'is:"open', '"is:open',
               'a b" c d"', 'owner:me "', 'workstream:"Build', '  "  ', 'due:"overdue" "', 'T-A-001"', '"T-A-001', 'owner:"Owner One" "', "it's", 'q"" "q', '"" x', 'x ""', '"" ""', 'x "" y', '"" status:Open', 'status:Open ""', '"',  '" "', '"owner:me', '"status:Open b', '"-status:Closed x', 'a "no:owner', '"is:open', 'x "due:overdue" y"']

    def test_normalising_twice_is_the_same_as_once(self):
        for line in self.AWKWARD:
            once = self.val(f"T.fl.normalise({lit(line)}, {lit(ROWS)}, {lit(CTX)})")
            twice = self.val(f"T.fl.normalise({lit(once)}, {lit(ROWS)}, {lit(CTX)})")
            self.assertEqual(once, twice, line)

    def test_two_thousand_chips_parse_quickly(self):
        line = " ".join(["is:open"] * 2000)
        many = [row(f"T-A-{i:03d}", "action", f"Item {i}", "Open", f"Owner {i % 7}", "High", "2026-11-01", workstream=f"Stream {i % 5}") for i in range(500)]
        got = self.val(f"(function(){{ var t = Date.now(); var p = T.fl.parse({lit(line)}, {lit(many)}, {lit(CTX)}); return [p.chips.length, Date.now() - t]; }})()")
        self.assertLess(got[1], 1000, got)
        self.assertEqual(got[0], 2000)


class Rulings(Line):
    """"""

    def sug(self, w, ctx=CTX):
        return self.val(f"T.fl.suggest({lit(w)}, {lit(ROWS)}, {lit(ctx)})")

    def test_quiet_is_fourteen_days_or_more(self):      # the line's own rule: exactly 14 days is quiet, 13 is not, 15 is
        rows = [row("Q-1", "risk", "a", "Open", ME, reviewed="2026-10-15"), row("Q-2", "risk", "b", "Open", ME, reviewed="2026-10-16"),
                row("Q-3", "risk", "c", "Open", ME, reviewed="2026-10-14"), row("Q-4", "risk", "d", "Closed", ME, reviewed="2026-10-01"),
                row("Q-5", "risk", "e", "Open", ME, last_reviewed="2026-10-15"), row("Q-6", "risk", "f", "Open", ME, last_reviewed="2026-10-16")]
        got = self.val(f"T.fl.apply({lit(rows)}, 'is:quiet', {lit(CTX)})")
        self.assertEqual([r["id"] for r in got], ["Q-1", "Q-3", "Q-5"])

    def test_a_typed_use_case_number_is_written_back_as_typed(self):
        rows = self.uc_rows()
        def back(line):
            p = self.val(f"T.fl.parse({lit(line)}, {lit(rows)}, {lit(CTX)})")
            return p["chips"][0]["text"], self.val(f"T.fl.normalise({lit(line)}, {lit(rows)}, {lit(CTX)})")
        self.assertEqual(back("usecase:1.1"), ("usecase:1.1", "usecase:1.1"))
        self.assertEqual(back("usecase:1"), ("usecase:1", "usecase:1"))
        self.assertEqual(back('usecase:"Use case 1.2"'), ('usecase:"Use case 1.2"', 'usecase:"Use case 1.2"'))
        self.assertEqual(back("uc:1.2,2")[1], "usecase:1.2,2")
        self.assertEqual(back("-usecase:1.1")[1], "-usecase:1.1")
        self.assertEqual(self.val(f"T.fl.normalise('-usecase:1.1 -usecase:2', {lit(rows)}, {lit(CTX)})"), "-usecase:1.1,2")
        got = self.val(f"T.fl.toState('usecase:1.1', {lit(rows)}, {lit(CTX)})")
        self.assertEqual(got["state"]["filters"], {"use_case": ["Use case 1.1"]})
        self.assertEqual(self.val(f"T.fl.addText('is:open', 'usecase:1.1', {lit(rows)}, {lit(CTX)})"), "is:open usecase:1.1")

    def test_a_chosen_status_is_not_offered_again(self):
        got = [s["ins"] for s in self.val(f"T.fl.suggest('status:Open,', {lit(ROWS)}, {lit(CTX)})")]
        self.assertNotIn("status:Open,Open", got)
        self.assertIn("status:Open,Pending", got)
        got = [s["ins"] for s in self.val(f"T.fl.suggest('status:Open,Pending,', {lit(ROWS)}, {lit(CTX)})")]
        self.assertFalse([g for g in got if g.endswith(",Open") or g.endswith(",Pending")], got)

    def test_the_risks_tile_keeps_all_four_kinds(self):
        st = self.val("T.tiles.FILTERS.risks")
        line = self.val(f"T.fl.fromState({lit(st)})")
        self.assertIn("type:risk,issue,assumption,dependency", line)
        back = self.val(f"T.fl.toState({lit(line)}, {lit(ROWS)}, {lit(CTX)})")
        self.assertEqual((back["state"]["type"], back["exact"]), ("risk", True))

    def uc_rows(self):
        return [row("U-1", "action", "a", "Open", ME, uc="Use case 1"), row("U-2", "action", "b", "Open", ME, uc="Use case 1.1"),
                row("U-3", "action", "c", "Open", ME, uc="Use case 1.2"), row("U-4", "action", "d", "Open", ME, uc="Use case 10"),
                row("U-5", "action", "e", "Open", ME, uc="Use case 2")]

    def uc(self, line):
        p = self.val(f"T.fl.parse({lit(line)}, {lit(self.uc_rows())}, {lit(CTX)})")
        self.assertEqual(p["errors"], [], line)
        return [r["id"] for r in self.val(f"T.fl.apply({lit(self.uc_rows())}, {lit(line)}, {lit(CTX)})")]

    def test_a_use_case_is_typed_as_its_number_or_its_group(self):
        self.assertEqual(self.uc("usecase:1.1"), ["U-2"])
        self.assertEqual(self.uc("usecase:1"), ["U-1", "U-2", "U-3"], "the group: 1, 1.1 and 1.2, not 10")
        self.assertEqual(self.uc("usecase:2"), ["U-5"])
        self.assertEqual(self.uc('usecase:"Use case 1.2"'), ["U-3"])
        self.assertEqual(self.uc("uc:1.2,2"), ["U-3", "U-5"])
        err = self.val(f"T.fl.parse('usecase:7', {lit(self.uc_rows())}, {lit(CTX)})")["errors"]
        self.assertEqual(len(err), 1)
        self.assertTrue(err[0]["msg"].startswith("No use case is called 7. Try "), err)

    def test_workstreams_come_from_the_project_in_its_order(self):
        ctx = dict(CTX, workstreams=["Legal", "Build", "Data", "Training"])
        self.assertEqual(self.val(f"T.fl.parse('workstream:Legal', {lit(ROWS)}, {lit(ctx)})")["errors"], [])
        self.assertEqual(self.ids("workstream:Legal", ctx), [])
        self.assertEqual(self.ids("workstream:Build", ctx), ["T-A-001", "T-R-001"])
        msg = self.val(f"T.fl.parse('workstream:Nope', {lit(ROWS)}, {lit(ctx)})")["errors"][0]["msg"]
        self.assertEqual(msg, "No workstream is called Nope. Try Legal, Build, Data or Training.")
        self.assertEqual([s["label"] for s in self.sug("workstream:", ctx)], ["Legal", "Build", "Data", "Training", "none"])
        extra = dict(ctx, workstreams=["Legal"])
        self.assertEqual([s["label"] for s in self.sug("workstream:", extra)], ["Legal", "Build", "Data", "none"], "a value only the rows have follows")
        self.assertEqual([s["label"] for s in self.sug("workstream:")], ["Build", "Data", "none"], "without a project list: the rows, sorted")

    def test_no_priority_finds_the_decisions(self):
        self.assertEqual(self.ids("no:priority"), ["T-D-001", "T-D-002", "T-D-003", "T-D-004"])
        self.assertEqual(self.parse("no:priority")["errors"], [])
        self.assertEqual(self.parse("no:priority")["chips"][0]["text"], "no:priority")

    def test_the_messages_keep_their_curly_quotes(self):
        self.assertIn("There is no “stauts” filter.", self.one_error("stauts:Open"))
        self.assertTrue(self.one_error("is:zzq").startswith("“zzq” is not a value for Is."))
        self.assertTrue(self.one_error("no:zzq").startswith("There is no “zzq” field."))

    def test_the_owner_list_keeps_me_and_the_milestone_list_is_in_date_order(self):
        msg = self.one_error("owner:Nobody")
        self.assertTrue(msg.startswith("No owner is called Nobody. Try me, \"Owner One\", \"Owner Two\""), msg)
        ctx = dict(CTX, milestones=[{"name": "Go live", "date": "2026-12-01"}, {"name": "Kick-off", "date": "2026-09-01"}, {"name": "Pilot", "date": "2026-10-20"}, {"name": "Later", "date": ""}])
        msg = self.val(f"T.fl.parse('milestone:Nope', {lit(ROWS)}, {lit(ctx)})")["errors"][0]["msg"]
        self.assertEqual(msg, "No milestone is called Nope. Try Kick-off, Pilot, \"Go live\" or Later.")
        plain = self.val(f"T.fl.parse('milestone:Nope', {lit(ROWS)}, {lit(CTX)})")["errors"][0]["msg"]
        self.assertEqual(plain, "No milestone is called Nope. Try \"Go live\".")
        self.assertEqual(self.ids("milestone:Pilot", ctx), [])

    def test_due_soon_is_refused_and_next_7_days_works(self):
        msg = self.one_error("due:soon")
        self.assertEqual(msg, "“soon” is not a value for Due. Say next-7-days instead. Try overdue, today, next-7-days, later or none.")
        self.assertEqual(self.ids("due:soon"), ALL, "refused, so not applied")
        self.assertEqual(self.ids("due:next-7-days"), ["T-A-002", "T-A-003", "T-R-001"])
        self.assertEqual(self.parse("due:next-7-days")["errors"], [])
        self.assertEqual(self.val(f"T.fl.fromState({lit({'mode': 'all', 'type': 'all', 'filters': {'due': ['soon']}, 'not': {}})})"), "due:next-7-days")

    def test_status_suggestions_offer_every_status_the_types_can_have(self):
        rows = [r for r in ROWS if r["status"] not in ("Withdrawn", "Made")]
        got = [s["ins"] for s in self.val(f"T.fl.suggest('status:Open,', {lit(rows)}, {lit(CTX)})")]
        self.assertIn("status:Open,Withdrawn", got)
        self.assertIn("status:Open,Made", got)
        self.assertNotIn("status:Open,Open", got)
        actions = [r for r in ROWS if r["kind"] == "action"]
        got = [s["ins"] for s in self.val(f"T.fl.suggest('status:Open,', {lit(actions)}, {lit(CTX)})")]
        self.assertEqual(got, ["status:Open,Pending", "status:Open,Delayed", "status:Open,Closed", "status:Open,Cancelled"], "no decisions: the five")

    def test_the_tiles_land_on_a_line_that_shows_what_they_counted_too(self):
        want = {"overdue": "is:open type:action due:overdue", "risks": "is:open type:risk,issue,assumption,dependency priority:Urgent,High",
                "decisions": "is:open type:decision status:Pending"}
        for key, line in want.items():
            self.assertEqual(self.val(f"T.fl.fromState(T.tiles.FILTERS.{key})"), line)
            by_state = [r["id"] for r in self.val(f"T.filters.applyFilters({lit(ROWS)}, T.tiles.FILTERS.{key}, {lit(TODAY)})")]
            self.assertEqual(self.ids(line), by_state, key)

    def test_the_freshness_tile_can_be_written_as_a_line(self):
        st = {"mode": "open", "type": "all", "filters": {}, "not": {}, "is": ["quiet"]}
        line = self.val(f"T.fl.fromState({lit(st)})")
        self.assertEqual(line, "is:open is:quiet")
        self.assertEqual(self.ids(line), ["T-R-001"])
        self.assertEqual(self.val(f"T.fl.fromState({lit(dict(st, **{'is': ['stale', 'gap']}))})"), "is:open is:quiet is:incomplete")
        self.assertEqual(self.val(f"T.fl.fromState({lit(dict(st, **{'is': ['banana']}))})"), "is:open", "a word the line does not know is left out")
        self.assertEqual(self.val("T.fl.fromState({mode: 'open', type: 'all', filters: {}, not: {}})"), "is:open")


class Freshness(Line):
    """The older Freshness filter (filters.js `reviewed`: stale, incomplete) and the line's two words are one thing."""

    def line(self, st):
        return self.val(f"T.fl.fromStateNote({lit(st)})")

    def state(self, **filters):
        return {"mode": "open", "type": "all", "filters": filters, "not": {}}

    def test_each_old_value_becomes_its_word(self):
        self.assertEqual(self.line(self.state(reviewed=["stale"])), {"line": "is:open is:quiet", "dropped": []})
        self.assertEqual(self.line(self.state(reviewed=["incomplete"]))["line"], "is:open is:incomplete")
        self.assertEqual(self.line(self.state(reviewed=["stale", "incomplete"]))["line"], "is:open is:quiet,incomplete", "either one, as the filter box said")
        st = dict(self.state(reviewed=["stale"]), **{"not": {"reviewed": True}})
        self.assertEqual(self.line(st)["line"], "is:open -is:quiet")

    def test_the_chips_say_it_in_plain_words(self):
        says = [c["say"] for c in self.parse("is:quiet is:incomplete")["chips"]]
        self.assertEqual(says, ["Not reviewed in 14 days", "No owner or no date"])
        self.assertEqual(self.parse("is:quiet,incomplete")["chips"][0]["say"], "Not reviewed in 14 days or No owner or no date")

    def test_the_line_goes_back_to_the_freshness_filter(self):
        got = self.val(f"T.fl.toState('is:open is:incomplete', {lit(ROWS)}, {lit(CTX)})")
        self.assertTrue(got["exact"])
        self.assertEqual(got["state"]["filters"], {"reviewed": ["incomplete"]})
        got = self.val(f"T.fl.toState('is:quiet is:incomplete', {lit(ROWS)}, {lit(CTX)})")
        self.assertEqual((got["state"]["filters"], got["rest"]), ({"reviewed": ["stale"]}, ["is:incomplete"]), "two separate conditions do not fit one filter")

    def test_the_freshness_state_finds_what_the_old_filter_found(self):
        # the rows carry `last_reviewed`, as the page's own data will; the old filter and the line count the same items
        rows = [dict(r, last_reviewed=r.pop("reviewed", "2026-10-28")) for r in (dict(x) for x in ROWS)]
        st = self.state(reviewed=["stale"])
        line = self.line(st)["line"]
        got = self.val(f"T.fl.apply({lit(rows)}, {lit(line)}, {lit(CTX)})")
        want = self.val(f"T.filters.applyFilters({lit(rows)}, {lit(st)}, {lit(TODAY)})")
        self.assertEqual([r["id"] for r in got], [r["id"] for r in want])
        self.assertEqual([r["id"] for r in got], ["T-R-001"])

    def test_a_field_or_value_it_does_not_know_is_dropped_and_said(self):
        bad = [{"mode": "open", "type": "all", "filters": {"banana": ["x"], "owner": "Owner One", "reviewed": ["stale", "old"], "status": [None, "Open"]}, "not": None},
               {"mode": "weird", "type": "other", "filters": None}, {}, None, "text", 7, {"filters": [], "is": "stale"}, {"is": ["stale", 5, None, {}]}]
        for st in bad:
            got = self.val(f"T.fl.fromStateNote({lit(st)})")
            self.assertIsInstance(got["line"], str)
            self.assertIsInstance(got["dropped"], list)
        got = self.line(bad[0])
        self.assertEqual(got["line"], "is:open status:Open is:quiet")
        self.assertEqual(got["dropped"], ["the banana filter", "a value in the status filter", "the owner filter", "the old Freshness value"])
        self.assertEqual(self.val("T.fl.fromState({mode: 'open', filters: {reviewed: 'stale'}})"), "is:open")

    def test_the_publish_dialogs_show_them_state_goes_through(self):
        # #159's showState: setFilter(initial(), "reviewed", [value], false), written out here so this holds with or without that branch
        for value in ("incomplete", "stale"):
            st = self.val(f"T.filters.setFilter(T.filters.initial(), 'reviewed', [{lit(value)}], false)")
            got = self.line(st)
            self.assertEqual(got["dropped"], [])
            self.assertEqual(got["line"], "is:open is:" + ("quiet" if value == "stale" else "incomplete"))
            self.assertEqual(self.parse(got["line"])["errors"], [])


class ShowThem(Line):
    """#159's Show them calls openWork(showState(value)); showState is setFilter(initial(), "reviewed", [value], false). Run here in the
    page's own store: the dialog must close on Work items with a working line, never on a TypeError."""

    def open_work(self, value, with_dates=False):
        rows = [{"id": "S-A-1", "description": "Book the room", "status": "Open", "owner": "", "due_date": "2026-11-01"},
                {"id": "S-A-2", "description": "Send the invitations", "status": "Open", "owner": "Owner One", "due_date": None},
                {"id": "S-A-3", "description": "Order the laptops", "status": "Open", "owner": "Owner One", "due_date": "2026-11-05"}]
        if with_dates:
            rows[2]["freshness"] = {"raised": "2026-09-01", "last_reviewed": "2026-10-01", "not_reviewed": True, "days": 14}
        data = {"actions": rows, "raid": [{"id": "S-R-1", "type": "Risk", "description": "No date on a risk", "status": "Open", "owner": "Owner One", "due_date": None}],
                "decisions": [], "workstreams": [], "milestones": []}
        return self.val("(function(){ var R = T.report; history.replaceState(null, '', '#dashboard&p=TUL'); R.project.value = 'TUL'; R.data.value = " + lit(data) + "; "
                        f"R.openWork(T.filters.setFilter(T.filters.initial(), 'reviewed', [{lit(value)}], false)); "
                        "return { view: R.view.value, line: R.lineText.value, hash: location.hash, shown: T.fl.apply(R.rows.value, R.lineText.value, R.filterCtx()).map(function (r) { return r.id; }), "
                        "errors: T.fl.parse(R.lineText.value, R.rows.value, R.filterCtx()).errors.length }; })()")

    def test_show_them_for_no_owner_or_no_date_opens_work_items_on_those_items(self):
        got = self.open_work("incomplete")
        self.assertEqual((got["view"], got["line"], got["errors"]), ("work", "is:open is:incomplete", 0), got)
        self.assertIn("#work", got["hash"])
        self.assertEqual(got["shown"], ["S-A-1", "S-A-2"], "an action with no date counts; a risk with no date does not")

    def test_show_them_for_not_reviewed_opens_work_items_when_the_data_has_dates(self):
        got = self.open_work("stale", with_dates=True)
        self.assertEqual((got["view"], got["line"], got["errors"]), ("work", "is:open is:quiet", 0), got)
        self.assertEqual(got["shown"], ["S-A-3"])

    def test_show_them_for_not_reviewed_with_no_dates_still_opens_work_items_with_a_plain_line(self):
        got = self.open_work("stale")
        self.assertEqual((got["view"], got["errors"]), ("work", 0), got)
        self.assertEqual(got["line"], "is:open", "the word the page cannot answer yet is left out, not an error")


class Cost(Line):
    """The parse builds each field's offers and known values once, however long the line is (counted, not timed)."""

    def work(self, chips, line_word="is:open", rows=500):
        many = [row(f"T-A-{i:03d}", "action", f"Item {i}", "Open", f"Owner {i % 7}", "High", "2026-11-01", workstream=f"Stream {i % 5}") for i in range(rows)]
        line = " ".join([line_word] * chips)
        return self.val(f"(function(){{ var w = {{}}; var c = Object.assign({{}}, {lit(CTX)}, {{ work: w }}); var p = T.fl.parse({lit(line)}, {lit(many)}, c); "
                        "return { chips: p.chips.length, errors: p.errors.length, w: w }; })()")

    def test_two_thousand_is_chips_build_each_field_once(self):
        got = self.work(2000)
        self.assertEqual(got["chips"], 2000)
        self.assertEqual(got["w"], {"offers": 1, "known": 1}, got)

    def test_doubling_the_chips_does_not_add_work(self):
        a, b = self.work(1000), self.work(2000)
        self.assertEqual(a["w"], b["w"], (a, b))
        c = self.work(2000, rows=1000)
        self.assertEqual(c["w"], b["w"], "and more rows do not add builds, only a longer pass")

    def test_each_field_is_built_once_when_the_line_mixes_fields(self):
        many = [row(f"T-A-{i:03d}", "action", f"Item {i}", "Open", f"Owner {i % 7}", "High", "2026-11-01", workstream=f"Stream {i % 5}") for i in range(500)]
        line = " ".join(["is:open", "status:Open", "owner:me", "workstream:Stream", "priority:High"] * 400)
        got = self.val(f"(function(){{ var w = {{}}; var c = Object.assign({{}}, {lit(CTX)}, {{ work: w }}); var p = T.fl.parse({lit(line)}, {lit(many)}, c); return w; }})()")
        self.assertEqual(got, {"offers": 5, "known": 5}, "five fields on the line: one build each")

    def test_two_thousand_wrong_words_also_build_once(self):
        got = self.work(2000, "is:old")
        self.assertEqual(got["errors"], 2000)
        self.assertEqual(got["w"], {"offers": 1, "known": 1}, got)


class Source(unittest.TestCase):
    def test_no_name_or_date_in_the_source_or_the_tests(self):
        import re
        for p in (PAGE_SRC / "logic" / "filterLine.js", Path(__file__)):
            body = p.read_text(encoding="utf-8")
            for m in re.finditer(r"^\s*(//|#).*$", body, re.M):
                self.assertNotRegex(m.group(0), r"\b\d{2}-\d{2}-\d{4}\b|\b20\d{2}-\d{2}-\d{2}\b", f"{p.name}: a date in a comment")

    def test_the_line_carries_no_press_slash_hint(self):
        # #286: "/" opens ask clark in the app, so the line must not advertise it. A plain click or Tab reaches the line.
        import re
        jsx = (PAGE_SRC / "components" / "FilterLine.jsx").read_text(encoding="utf-8")
        for m in re.finditer(r"^(?!\s*//).*$", jsx, re.M):
            self.assertNotRegex(m.group(0), r"(?i)press\s*(<kbd>)?\s*/|class=\"fkey\"|aria-keyshortcuts", "the line advertises a key")
        css = (SRC / "clark" / "page" / "shell.css").read_text(encoding="utf-8")
        self.assertNotIn(".fkey", css)

    def test_it_is_pure(self):
        body = (PAGE_SRC / "logic" / "filterLine.js").read_text(encoding="utf-8")
        for bad in ("document.", "window.", "new Date(", "Date.now", "fetch(", "local" + "Storage", "session" + "Storage"):
            self.assertNotIn(bad, body)


if __name__ == "__main__":
    unittest.main()
