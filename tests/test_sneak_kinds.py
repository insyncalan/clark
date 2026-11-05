"""#728: Sneak peek's reader for a milestone and for a use case (clark/sneak.py): words in, from -> to out, by plain code.
Run: python3 dev/run_tests.py test_sneak_kinds

A milestone: forecast date, achieved date and status (its owner and agreed date are left out: the change route does not take them).
A use case: status, headline and commitment. Done on either asks first. Nothing is read from a store here.
"""
import unittest
from datetime import date

from _paths import ROOT  # noqa: F401
from clark import changes, sneak

NOW = date(2026, 10, 28)
DATA = {"actions": [], "raid": [], "decisions": [],
        "milestones": [{"id": "M-1", "status": "Planned", "forecast_date": "2026-11-01", "actual_date": None, "owner": "Jo Ellis"},
                       {"id": "M-2", "status": "Done", "forecast_date": "2026-10-01", "actual_date": "2026-10-02", "owner": None}],
        "use_cases": [{"id": "U-1", "status": "On track", "headline": "Going well", "commitment": None},
                      {"id": "U-2", "status": "Flag", "headline": "", "commitment": "Candidate"}]}


def read(item, words):
    return sneak.read(DATA, item, words, NOW)


def fields(r):
    return {c["field"]: c["to"] for c in r["changes"]}


class Milestone(unittest.TestCase):
    def test_a_forecast_date_in_each_form(self):
        for words in ("forecast 30-10-2026", "forecast 2026-10-30", "move to Friday", "forecast date Friday"):
            with self.subTest(words=words):
                r = read("M-1", words)
                self.assertEqual((r["ok"], r["table"], fields(r)), (True, "milestones", {"forecast_date": "2026-10-30"}))
                self.assertFalse(r["confirm"])
        self.assertEqual(read("M-1", "forecast 30-10-2026")["changes"][0]["from_text"], "01-11-2026")

    def test_done_asks_first_and_takes_the_day_it_was_achieved_on(self):
        r = read("M-1", "done")
        self.assertEqual((fields(r), r["confirm"]), ({"status": "Done"}, True))
        r = read("M-1", "achieved on 20-10-2026")
        self.assertEqual(fields(r), {"actual_date": "2026-10-20", "status": "Done"})
        self.assertTrue(r["confirm"])

    def test_a_done_milestone_takes_a_date_as_its_achieved_date_and_reopens(self):
        self.assertEqual(fields(read("M-2", "20-10-2026")), {"actual_date": "2026-10-20"})
        r = read("M-2", "reopen, forecast 2026-12-01")
        self.assertEqual((fields(r), r["confirm"]), ({"forecast_date": "2026-12-01", "status": "Planned"}, False))

    def test_each_refusal_says_why_and_nothing_is_offered(self):
        for words, part in (("forecast 31-02-2026", "isn't a real day"), ("forecast 1-1-1999", "year looks wrong"),
                            ("forecast Friday and 02-11-2026", "which day"), ("cancel it", "cancelled"),
                            ("agreed date 03-11-2026", "agreed date isn't changed"), ("not done", "which status"),
                            ("done and reopen", "which status"), ("done on 30-12-2026", "after today"), ("gibberish", "forecast date")):
            with self.subTest(words=words):
                r = read("M-1", words)
                self.assertFalse(r["ok"])
                self.assertIn(part, r["message"])

    def test_the_owner_is_left_out_but_the_rest_is_read(self):
        r = read("M-1", "owner Bo Hart, forecast 30-10-2026")
        self.assertEqual(fields(r), {"forecast_date": "2026-10-30"})
        self.assertIn("owner isn't changed here", r["note"])
        self.assertIn("owner isn't changed here", read("M-1", "owner Bo Hart")["message"])

    def test_an_unchanged_value_is_said_so(self):
        self.assertIn("already Done", read("M-2", "done")["message"])

    def test_every_field_it_offers_is_one_the_change_route_takes(self):
        for words in ("done", "achieved on 20-10-2026", "forecast Friday", "reopen"):
            for item in ("M-1", "M-2"):
                r = read(item, words)
                for f in (r.get("changes") or []):
                    self.assertIn(f["field"], changes.CHANGE_KINDS["milestones"]["update"])


class UseCase(unittest.TestCase):
    def test_a_status_in_each_form(self):
        for words, status in (("high risk", "High risk"), ("flag it", "Flag"), ("flagged", "Flag"), ("Done", "Done"), ("completed", "Done")):
            with self.subTest(words=words):
                r = read("U-1", words)
                self.assertEqual((r["ok"], r["table"], fields(r)), (True, "use_cases", {"status": status}))
                self.assertEqual(r["confirm"], status == "Done")
        self.assertEqual(fields(read("U-2", "on track")), {"status": "On track"})

    def test_a_headline_is_everything_after_the_word(self):
        for words in ("headline: waiting on the vendor", "headline is waiting on the vendor", "headline to “waiting on the vendor”"):
            with self.subTest(words=words):
                self.assertEqual(fields(read("U-1", words)), {"headline": "waiting on the vendor"})
        r = read("U-1", "flag, headline: all done now")
        self.assertEqual(fields(r), {"status": "Flag", "headline": "all done now"})
        self.assertFalse(r["confirm"], "a status word inside the headline is not read as a status")

    def test_a_commitment_in_each_form_and_cleared(self):
        for words, word in (("committed", "Committed"), ("candidate", "Candidate"), ("planned 2027", "Planned 2027")):
            with self.subTest(words=words):
                self.assertEqual(fields(read("U-1", words)), {"commitment": word})
        r = read("U-2", "no commitment")
        self.assertEqual((fields(r), r["changes"][0]["to_text"]), ({"commitment": None}, "None"))

    def test_each_refusal_says_why_and_nothing_is_offered(self):
        for words, part in (("not done", "which status"), ("done and flag", "which status"), ("candidate committed", "which one"),
                            ("headline:", "headline needs words"), ("headline: " + "x" * 301, "headline needs words"),
                            ("due 31-02-2026", "isn't a real day"), ("gibberish", "status, headline and commitment"), ("delete it", "Nothing is removed")):
            with self.subTest(words=words):
                r = read("U-1", words)
                self.assertFalse(r["ok"])
                self.assertIn(part, r["message"])

    def test_a_date_owner_or_priority_is_left_out_with_a_note(self):
        r = read("U-1", "high risk, owner Jo Ellis, due Friday, high priority")
        self.assertEqual(fields(r), {"status": "High risk"})
        self.assertIn("so that part was left out", r["note"])

    def test_every_field_it_offers_is_one_the_change_route_takes(self):
        r = read("U-1", "high risk, committed, headline: x")
        for f in r["changes"]:
            self.assertIn(f["field"], changes.CHANGE_KINDS["use_cases"]["update"])

    def test_the_headline_has_no_hidden_characters(self):
        self.assertEqual(fields(read("U-1", "headline: a‮b​c  d")), {"headline": "abc d"})


class Seam(unittest.TestCase):
    def test_the_seam_reads_a_milestone_and_a_use_case_by_id(self):
        seam = sneak.make_read(lambda code: DATA if code == "ABC" else None)
        self.assertEqual(seam({"project": "ABC", "id": "U-1", "text": "flag"})[1]["table"], "use_cases")
        self.assertEqual(seam({"project": "ABC", "id": "M-1", "text": "done"})[1]["table"], "milestones")
        self.assertIn("isn't in this project", seam({"project": "ABC", "id": "X-9", "text": "done"})[1]["message"])


if __name__ == "__main__":
    unittest.main()
