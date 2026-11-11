"""LOWs on the "I sent it" sentence (row 983, PR 977): the 100-character name cap, the person kept out of the subject, tone and
reply_by reaching the subject draft, and a subject draft that raises. Fictional data only.
Run: python3 dev/run_tests.py test_sent_note_caps
"""
import sqlite3
import unittest
from datetime import date

import _paths  # noqa: F401
from _demo import DemoStore, USER
from clark import draft_email_feed as feed
from clark import history
from clark import store as store_module

TODAY = date(2026, 10, 28)
SUBJECT = "Fabrikam Programme · ABC-A-004 · Chase: Order the laptops"


def sentences(store, item):
    con = sqlite3.connect(f"file:{store.path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        return [r["to"] for r in history.activity_for_item(con, item)["rows"] if r["kind"] == "Email sent"]
    finally:
        con.close()


class Base(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store
        self.a = self.demo.action(description="Share the plan", owner="Pat Example", status="Open")

    def person(self, name):
        with self.store.step("dashboard", USER) as st:
            return st.create("people", {"name": name, "source": "test"})


class NameCap(Base):
    def test_a_long_name_is_cut_to_the_cap_and_the_sentence_stays_whole(self):
        cap = store_module.EMAIL_NOTE_NAME_MAX
        self.assertEqual(cap, 100)
        pid = self.person("Q" * 115)
        self.store.log_email_sent("ABC", [self.a], "chase", "2026-10-29", "Sam Lee", today=TODAY, person=pid, subject=SUBJECT)
        self.assertEqual(sentences(self.store, self.a), ['Emailed ' + "Q" * cap + ' on 29-10-2026, "' + SUBJECT + '"'])

    def test_a_name_of_exactly_the_cap_is_kept_whole(self):
        pid = self.person("Z" * 100)
        self.store.log_email_sent("ABC", [self.a], "chase", "2026-10-29", "Sam Lee", today=TODAY, person=pid, subject=SUBJECT)
        self.assertIn("Emailed " + "Z" * 100 + " on ", sentences(self.store, self.a)[0])


class SubjectSeam(Base):
    def setUp(self):
        super().setUp()
        self.asked = []

        def subject_for(*args, **kw):
            self.asked.append((args, kw))
            return SUBJECT
        self.seam = feed.make_sent(self.store.path, [], by_user="Sam Lee", today=TODAY, subject_for=subject_for)

    def test_the_person_is_not_handed_to_the_subject(self):
        pid = self.person("Pat Example")
        body = {"project": "ABC", "ids": [self.a], "mode": "chase", "day": "2026-10-28", "person": pid, "tone": 2, "reply_by": "2026-11-02"}
        self.assertEqual(self.seam(body)[0], 200)
        args, kw = self.asked[0]
        self.assertEqual((args, kw), (("ABC", [self.a], "chase", 2, "2026-11-02"), {}))
        self.assertNotIn(pid, args)
        self.assertEqual(sentences(self.store, self.a), ['Emailed Pat Example on 28-10-2026, "' + SUBJECT + '"'])


class SubjectOf(unittest.TestCase):
    def run_subject(self, tone, reply_by, answer=(200, {"draft": {"subject": "S"}})):
        seen = []

        def draft(req):
            seen.append(dict(req))
            if isinstance(answer, Exception):
                raise answer
            return answer
        got = feed.subject_of(draft)("ABC", ["ABC-A-004", "ABC-A-005"], "chase", tone, reply_by)
        return got, seen

    def test_tone_and_reply_by_are_put_in_the_draft_request(self):
        got, seen = self.run_subject(1, "2026-11-02")
        self.assertEqual(got, "S")
        self.assertEqual(seen, [{"project": "ABC", "mode": "chase", "picked": ["ABC-A-004", "ABC-A-005"], "tone": 1, "reply_by": "2026-11-02"}])

    def test_tone_zero_is_still_sent_and_an_empty_reply_by_or_none_is_left_out(self):
        for tone, reply_by in ((0, ""), (0, None)):
            with self.subTest(reply_by=reply_by):
                _, seen = self.run_subject(tone, reply_by)
                self.assertEqual(seen[0]["tone"], 0)
                self.assertNotIn("reply_by", seen[0])
        _, seen = self.run_subject(None, "")
        self.assertEqual(set(seen[0]), {"project", "mode", "picked"})

    def test_no_name_address_or_subject_goes_in_the_draft_request(self):
        _, seen = self.run_subject(2, "2026-11-02")
        self.assertFalse(set(seen[0]) & {"name", "email", "owner", "item", "subject", "person"})

    def test_a_draft_that_raises_or_refuses_or_answers_oddly_gives_no_subject(self):
        for answer in (RuntimeError("boom"), (400, {"draft": {"subject": "S"}}), (200, None), (200, {"draft": {"subject": 5}}), (200, {})):
            with self.subTest(answer=repr(answer)):
                self.assertEqual(self.run_subject(1, "", answer)[0], "")

    def test_a_raising_draft_still_records_the_press_and_writes_no_sentence(self):
        demo = DemoStore()
        self.addCleanup(demo.close)
        a = demo.action(description="Share the plan", owner="Pat Example", status="Open")

        def draft(req):
            raise RuntimeError("boom")
        seam = feed.make_sent(demo.store.path, [], by_user="Sam Lee", today=TODAY, subject_for=feed.subject_of(draft))
        self.assertEqual(seam({"project": "ABC", "ids": [a], "mode": "chase", "day": "2026-10-28"})[0], 200)
        self.assertEqual(len(demo.store.email_sent_for("ABC")), 1)
        self.assertEqual(sentences(demo.store, a), ["Emailed 28-10-2026 (chasing) about " + a])      # the old line, no subject in it


if __name__ == "__main__":
    unittest.main()
