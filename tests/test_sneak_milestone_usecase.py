"""Sneak peek on a milestone and a use case: the reader in plain code (clark/sneak.py), then a real store round trip: the reading is
applied as ONE change with ONE Undo that puts everything back, and a refused reading writes nothing.
Run: python3 dev/run_tests.py test_sneak_milestone_usecase
"""
import sqlite3
import unittest
from datetime import date

from _demo import USER, DemoStore
from clark import changes, sneak

NOW = date(2026, 10, 28)
DATA = {
    "milestones": [{"id": "M-1", "status": "Planned", "forecast_date": "2026-11-10", "actual_date": None, "baseline_date": "2026-11-01", "owner": "Jo Ellis"},
                   {"id": "M-2", "status": "Done", "forecast_date": None, "actual_date": "2026-10-01"},
                   {"id": "M-3", "status": "Planned", "forecast_date": None, "actual_date": None}],
    "use_cases": [{"id": "U-1", "status": "On track", "headline": "Steady", "commitment": None, "client_visible": 1},
                  {"id": "U-2", "status": "Flag", "headline": "", "commitment": "Committed", "client_visible": 0},
                  {"id": "U-3", "status": "Flag", "headline": "", "commitment": "Committed", "client_visible": 1}],
    "report_hidden": ["M-3"],
}
GONE = {"milestones": [{"id": "M-9"}], "use_cases": [{"id": "U-9"}]}


def read(item, words, archived=None):
    return sneak.read(DATA, item, words, NOW, archived=archived)


def lines(r):
    return {c["field"]: (c["from_text"], c["to_text"]) for c in r["changes"]}


class Milestone(unittest.TestCase):
    def test_row_776_every_change_has_a_phrase_that_is_part_of_the_typed_words(self):
        for words in ("forecast 30-11-2026", "done and forecast Friday", "achieved yesterday"):
            r = read("M-1", words)
            self.assertTrue(r["ok"], words)
            for c in r["changes"]:
                self.assertTrue(c["phrase"], (words, c["field"]))
                self.assertIn(c["phrase"], words)
        self.assertEqual(read("M-1", "forecast 30-11-2026")["changes"][0]["phrase"], "forecast 30-11-2026")

    def test_a_forecast_date_is_a_from_to_line(self):
        r = read("M-1", "forecast 30-11-2026")
        self.assertEqual((r["ok"], lines(r), r["confirm"]), (True, {"forecast_date": ("10-11-2026", "30-11-2026")}, False))
        self.assertEqual(lines(read("M-1", "move to Friday"))["forecast_date"], ("10-11-2026", "30-10-2026"))

    def test_a_date_that_is_not_a_day_is_refused(self):
        for w in ("forecast 31-02-2026", "forecast 2026-02-31", "achieved 99-99-2026"):
            r = read("M-1", w)
            self.assertFalse(r["ok"])
            self.assertEqual(r["message"], sneak.BAD_DATE)
        self.assertEqual(read("M-1", "forecast 01-01-1999")["message"], sneak.BAD_YEAR)
        self.assertEqual(read("M-1", "forecast 01-12-2026 or 02-12-2026")["message"], sneak.TWO_DATES)

    def test_past_and_future_words(self):
        past = read("M-1", "forecast yesterday")
        self.assertIn("is in the past.", past["note"])
        self.assertIn("Read as", read("M-1", "forecast tomorrow")["note"])
        self.assertEqual(read("M-1", "achieved on 30-11-2026")["message"], changes.ACHIEVED_DATE)

    def test_achieved_asks_first_and_fills_the_date_the_way_the_store_does(self):
        r = read("M-1", "achieved")
        self.assertTrue(r["confirm"])
        self.assertEqual(lines(r), {"status": ("Planned", "Achieved"), "actual_date": ("—", "28-10-2026")})
        self.assertEqual(lines(read("M-1", "done on 20-10-2026"))["actual_date"], ("—", "20-10-2026"))

    def test_done_with_no_date_uses_a_forecast_that_has_passed(self):
        data = {"milestones": [{"id": "M-4", "status": "Planned", "forecast_date": "2026-10-20"}]}
        self.assertEqual(lines(sneak.read(data, "M-4", "done", NOW))["actual_date"], ("—", "20-10-2026"))

    def test_reopening_clears_the_achieved_date(self):
        r = read("M-2", "reopen")
        self.assertEqual(lines(r), {"status": ("Achieved", "Planned"), "actual_date": ("01-10-2026", "—")})
        self.assertTrue(r["confirm"])               # leaving Achieved needs the same OK as reaching it
        self.assertTrue(read("M-2", "planned")["confirm"])
        self.assertFalse(read("M-1", "planned, forecast 30-11-2026")["confirm"])   # already Planned: no status change
        self.assertIsNone(next(c for c in r["changes"] if c["field"] == "actual_date")["to"])

    def test_a_date_on_a_done_milestone_is_its_achieved_date_unless_it_says_forecast(self):
        self.assertEqual(list(lines(read("M-2", "on 15-10-2026"))), ["actual_date"])
        self.assertEqual(list(lines(read("M-2", "forecast 15-12-2026"))), ["forecast_date"])

    def test_the_agreed_date_and_cancelling_are_refused_in_words(self):
        self.assertEqual(read("M-1", "agreed date 01-12-2026")["message"], sneak.WORDS["agreed_date"])
        self.assertEqual(read("M-1", "cancel it")["message"], sneak.WORDS["no_cancel"])

    def test_the_owner_is_left_out_with_a_note(self):
        r = read("M-1", "forecast 30-11-2026, owner Sam Reed")
        self.assertEqual(list(lines(r)), ["forecast_date"])
        self.assertIn(sneak.WORDS["owner_left_out"], r["note"])
        self.assertEqual(read("M-1", "owner Sam Reed")["message"], sneak.WORDS["owner_left_out"])

    def test_unclear_and_empty_words(self):
        self.assertEqual(read("M-1", "done and reopen")["message"], sneak.UNSURE_STATUS)
        self.assertEqual(read("M-1", "not done")["message"], sneak.UNSURE_STATUS)
        self.assertEqual(read("M-1", "hello")["message"], sneak.WORDS["nothing_milestone"])
        self.assertEqual(read("M-1", "x" * 401)["message"], sneak.TOO_LONG)
        self.assertIn("already", read("M-2", "achieved")["message"])

    def test_hidden_archived_and_other_projects_are_refused(self):
        self.assertEqual(read("M-3", "forecast 30-11-2026")["message"], sneak.WORDS["hidden"].format(what="milestone"))
        self.assertEqual(read("M-9", "done", archived=lambda: GONE)["message"], changes.ARCHIVED_MILESTONE)
        self.assertIn("isn't in this project", read("X-M-1", "done")["message"])


class UseCase(unittest.TestCase):
    def test_row_776_every_change_has_a_phrase_that_is_part_of_the_typed_words(self):
        words = "high risk, candidate, headline: Vendor is late"
        r = read("U-1", words)
        self.assertTrue(r["ok"])
        got = {c["field"]: c["phrase"] for c in r["changes"]}
        self.assertEqual(got, {"status": "high risk", "commitment": "candidate", "headline": "headline: Vendor is late"})
        for phrase in got.values():
            self.assertIn(phrase, words)

    def test_status_headline_and_commitment(self):
        r = read("U-1", "flagged, committed, headline: Late vendor")
        self.assertEqual(lines(r), {"status": ("On track", "Flag"), "headline": ("Steady", "Late vendor"), "commitment": ("No flag", "Committed")})
        self.assertFalse(r["confirm"])
        self.assertEqual(lines(read("U-1", "high risk"))["status"], ("On track", "High risk"))
        self.assertEqual(lines(read("U-1", 'headline to "Go-live is on plan"'))["headline"], ("Steady", "Go-live is on plan"))

    def test_done_asks_first(self):
        self.assertTrue(read("U-1", "done")["confirm"])
        self.assertFalse(read("U-1", "flag")["confirm"])

    def test_the_commitment_words_are_exact(self):
        for said, word in (("candidate", "Candidate"), ("COMMITTED", "Committed"), ("planned for 2027", "Planned 2027"), ("Planned 2027", "Planned 2027")):
            r = read("U-1", said)
            self.assertEqual(next(c for c in r["changes"] if c["field"] == "commitment")["to"], word)
            self.assertIn(word, changes.UC_COMMITMENTS)
        self.assertEqual(read("U-1", "candidate and committed")["message"], changes.UC_COMMITMENT_WORDS)
        self.assertEqual(read("U-1", "planned 2028")["message"], sneak.WORDS["nothing_use_case"])

    def test_no_flag_clears_the_commitment(self):
        r = read("U-3", "no flag")
        self.assertEqual(lines(r), {"commitment": ("Committed", "No flag")})
        self.assertIsNone(r["changes"][0]["to"])
        self.assertEqual(lines(read("U-3", "clear the commitment")), {"commitment": ("Committed", "No flag")})
        self.assertIn("already No flag", read("U-1", "no flag")["message"])

    def test_status_words_do_not_mix_up_with_the_commitment_flag(self):
        self.assertEqual(list(lines(read("U-3", "no flag, on track"))), ["status", "commitment"])
        self.assertEqual(read("U-1", "no flag, candidate")["message"], changes.UC_COMMITMENT_WORDS)

    def test_a_headline_that_is_too_long_is_refused_in_the_existing_words(self):
        self.assertEqual(read("U-1", "headline: " + "a" * 390)["message"], changes.UC_HEADLINE_WORDS)

    def test_unclear_and_empty_words(self):
        self.assertEqual(read("U-1", "done and flag")["message"], sneak.UNSURE_STATUS)
        self.assertEqual(read("U-1", "not done")["message"], sneak.UNSURE_STATUS)
        self.assertEqual(read("U-1", "hello")["message"], sneak.WORDS["nothing_use_case"])

    def test_hidden_archived_and_other_projects_are_refused(self):
        self.assertEqual(read("U-2", "done")["message"], sneak.WORDS["hidden"].format(what="use case"))
        self.assertEqual(read("U-9", "done", archived=lambda: GONE)["message"], changes.ARCHIVED_USE_CASE)
        self.assertIn("isn't in this project", read("U-77", "done")["message"])


class Forms(unittest.TestCase):
    """Parsing cases, some from the earlier partial of this row."""

    def test_a_forecast_date_in_each_form(self):
        for words in ("forecast 30-10-2026", "forecast 2026-10-30", "move to Friday", "forecast date Friday"):
            with self.subTest(words=words):
                self.assertEqual(read("M-1", words)["changes"][0]["to"], "2026-10-30")

    def test_a_done_milestone_can_be_reopened_with_a_new_forecast(self):
        r = read("M-2", "reopen, forecast 2026-12-01")
        self.assertEqual({c["field"] for c in r["changes"]}, {"forecast_date", "status", "actual_date"})
        self.assertTrue(r["confirm"])

    def test_done_with_a_forecast_also_shows_the_achieved_date(self):
        r = read("M-1", "done, forecast Friday")
        self.assertEqual(lines(r), {"forecast_date": ("10-11-2026", "30-10-2026"), "status": ("Planned", "Achieved"), "actual_date": ("—", "28-10-2026")})
        self.assertTrue(r["confirm"])

    def test_a_status_in_each_form(self):
        for words, status in (("high risk", "High risk"), ("flag it", "Flag"), ("flagged", "Flag"), ("completed", "Done"), ("flag it as high risk", "High risk")):
            with self.subTest(words=words):
                self.assertEqual(read("U-1", words)["changes"][0]["to"], status)

    def test_a_headline_is_everything_after_the_word_and_its_words_are_not_a_status(self):
        for words in ("headline: waiting on the vendor", "headline is waiting on the vendor", "headline to “waiting on the vendor”"):
            with self.subTest(words=words):
                self.assertEqual(lines(read("U-1", words)), {"headline": ("Steady", "waiting on the vendor")})
        r = read("U-1", "flag, headline: all done now")
        self.assertEqual(list(lines(r)), ["status", "headline"])
        self.assertFalse(r["confirm"])

    def test_every_field_offered_is_one_the_change_route_takes(self):
        for item, table in (("M-1", "milestones"), ("M-2", "milestones"), ("U-1", "use_cases"), ("U-3", "use_cases")):
            for words in ("done", "reopen", "forecast Friday", "achieved on 20-10-2026", "flag, candidate, headline: x", "no flag"):
                for c in (read(item, words).get("changes") or []):
                    self.assertIn(c["field"], changes.CHANGE_KINDS[table]["update"])


class Seam(unittest.TestCase):
    def test_the_route_seam_asks_for_the_archived_rows_only_when_the_item_is_not_live(self):
        asked = []

        def data_for(code, archived="hide"):
            asked.append(archived)
            return DATA if archived == "hide" else GONE
        seam = sneak.make_read(data_for)
        self.assertEqual(seam({"project": "ABC", "id": "M-9", "text": "done"})[1]["message"], changes.ARCHIVED_MILESTONE)
        self.assertEqual(seam({"project": "ABC", "id": "U-9", "text": "done"})[1]["message"], changes.ARCHIVED_USE_CASE)
        self.assertTrue(seam({"project": "ABC", "id": "M-1", "text": "done"})[1]["ok"])
        self.assertEqual(asked, ["hide", "only", "hide", "only", "hide"])


class RoundTrip(unittest.TestCase):
    """The reading applied through the existing writers, on a real store."""

    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.change = changes.make_change(self.s.path, [], USER)
        self.undo = changes.make_undo(self.s.path, [], USER)

    def counts(self):
        con = sqlite3.connect(str(self.s.path))
        try:
            return con.execute("SELECT (SELECT count(*) FROM applies), (SELECT count(*) FROM change_log)").fetchone()
        finally:
            con.close()

    def apply(self, kind, item, words):
        r = sneak.read(self.s.data_for("ABC"), item, words, date.today())
        self.assertTrue(r["ok"], r)
        return self.change({"project": "ABC", "kind": kind, "op": "update", "id": item, "changes": {c["field"]: c["to"] for c in r["changes"]}, "place": "peek"})

    def test_a_milestone_done_is_one_step_and_one_undo_puts_everything_back(self):
        m = self.demo.milestone
        before = self.s.read("milestones", ref=m)
        self.assertEqual(before["status"], "Planned")
        status, body = self.apply("milestones", m, "achieved")
        self.assertEqual((status, body["undoable"]), (200, True), body)
        now = self.s.read("milestones", ref=m)
        self.assertEqual((now["status"], bool(now["actual_date"])), ("Done", True))
        status, undone = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        self.assertEqual((status, undone["ok"]), (200, True), undone)
        again = self.s.read("milestones", ref=m)
        for f in ("status", "actual_date", "state", "forecast_date", "baseline_date"):
            self.assertEqual(again[f], before[f], f)
        reopened = self.apply("milestones", m, "achieved")[1]
        status, body = self.apply("milestones", m, "reopen")
        self.assertEqual(status, 200, body)
        self.assertIsNone(self.s.read("milestones", ref=m)["actual_date"])
        self.assertTrue(reopened["apply_id"] != body["apply_id"])

    def test_a_use_case_is_one_step_and_one_undo(self):
        u = self.demo.use_case
        before = self.s.read("use_cases", ref=u)
        data = self.s.data_for("ABC")
        if not before["client_visible"]:
            self.skipTest("the demo use case is hidden")
        status, body = self.apply("use_cases", u, "flag, committed, headline: Late vendor")
        self.assertEqual((status, body["undoable"]), (200, True), body)
        now = self.s.read("use_cases", ref=u)
        self.assertEqual((now["status"], now["commitment"], now["headline"]), ("Flag", "Committed", "Late vendor"))
        self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        again = self.s.read("use_cases", ref=u)
        self.assertEqual((again["status"], again["commitment"], again["headline"]), (before["status"], before["commitment"], before["headline"]))
        self.assertTrue(data)

    def test_a_refused_reading_writes_nothing(self):
        before = self.counts()
        data = self.s.data_for("ABC")
        for item, words in ((self.demo.milestone, "forecast 31-02-2026"), (self.demo.milestone, "agreed 01-12-2030"), (self.demo.use_case, "candidate and committed")):
            self.assertFalse(sneak.read(data, item, words, date.today())["ok"])
        self.assertEqual(self.counts(), before)


if __name__ == "__main__":
    unittest.main()
