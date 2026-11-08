"""Row 983: "I sent it" writes one detailed History sentence, once, and keeps what the email was about. Fictional data only.
Run: python3 dev/run_tests.py test_sent_note

Asserted: the sentence (the person's name from their record, the day as dd-mm-yyyy, the subject the server composed), no address and
no body in it; the old line when no subject; a quote, a long subject, a line break and a hidden mark in the subject; an unknown person;
the repeat press writes nothing more; the seam takes person/tone/reply_by only in shape, takes no subject from the page, and composes
the subject itself; the item's Activity shows the sentence as an "Email sent" row.
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
SUBJECT = "Example Programme · ABC-A-004 · Chase: Order the laptops"


class Note(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store
        self.a = self.demo.action(description="Share the plan")
        with self.store.step("dashboard", USER) as st:
            self.person = st.create("people", {"name": "Pat Example", "source": "test"})

    def send(self, **kw):
        kw.setdefault("subject", SUBJECT)
        kw.setdefault("person", self.person)
        return self.store.log_email_sent("ABC", [self.a], "chase", "2026-10-29", "Sam Lee", today=TODAY, **kw)

    def rows(self):
        con = sqlite3.connect(f"file:{self.store.path}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        try:
            return history.activity_for_item(con, self.a)["rows"]
        finally:
            con.close()

    def sentence(self):
        got = [r for r in self.rows() if r["kind"] == "Email sent"]
        self.assertEqual(len(got), 1)
        return got[0]["to"]

    def test_the_sentence_has_the_name_the_day_and_the_subject(self):
        self.send()
        self.assertEqual(self.sentence(), 'Emailed Pat Example on 29-10-2026, "' + SUBJECT + '"')

    def test_no_person_gives_the_sentence_without_a_name(self):
        self.send(person=None)
        self.assertEqual(self.sentence(), 'Emailed on 29-10-2026, "' + SUBJECT + '"')

    def test_a_person_not_on_file_gives_no_name(self):
        self.send(person="P-999")
        self.assertEqual(self.sentence(), 'Emailed on 29-10-2026, "' + SUBJECT + '"')

    def test_no_subject_keeps_the_old_line(self):
        self.send(subject=None)
        self.assertEqual(self.sentence(), "Emailed 29-10-2026 (chasing) about " + self.a)

    def test_a_quote_a_break_and_a_hidden_mark_in_the_subject_cannot_break_the_line(self):
        self.send(subject='Say "hi"\n‮ now​ ok')
        self.assertEqual(self.sentence(), "Emailed Pat Example on 29-10-2026, \"Say 'hi' now ok\"")

    def test_a_long_subject_is_cut_with_an_ellipsis_to_fit(self):
        self.send(subject="x" * 900)
        s = self.sentence()
        self.assertLessEqual(len(s), store_module.EMAIL_NOTE_MAX)
        self.assertTrue(s.endswith('…"'))

    def test_the_repeat_press_writes_one_sentence(self):
        first = self.send()
        self.assertEqual(self.send(), first)
        self.assertEqual(self.sentence()[:6], "Emaile")

    def test_the_sentence_is_written_once_and_the_record_still_holds_ids_mode_and_day_only(self):
        self.send()
        con = sqlite3.connect(self.store.path)
        try:
            cols = [c[1] for c in con.execute("PRAGMA table_info(email_sent)")]
            self.assertEqual(cols, [c for c in cols if c in ("seq", "at", "project", "day", "mode", "by_user")])
            self.assertEqual(con.execute("SELECT count(*) FROM item_events WHERE place = 'email'").fetchone()[0], 1)
        finally:
            con.close()


class Seam(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store
        self.a = self.demo.action(description="Share the plan", owner="Pat Example", status="Open")
        self.asked = []

        def subject_for(code, ids, mode, tone, reply_by):
            self.asked.append((code, list(ids), mode, tone, reply_by))
            return SUBJECT
        self.seam = feed.make_sent(self.store.path, [], by_user="Sam Lee", today=TODAY, subject_for=subject_for)

    def body(self, **over):
        return {"project": "ABC", "ids": [self.a], "mode": "chase", "day": "2026-10-28", **over}

    def test_tone_and_reply_by_reach_the_subject_and_the_note_is_written(self):
        status, reply = self.seam(self.body(tone=1, reply_by="2026-11-02"))
        self.assertEqual((status, reply["ok"]), (200, True))
        self.assertEqual(self.asked, [("ABC", [self.a], "chase", 1, "2026-11-02")])
        self.assertEqual(len(self.store.email_sent_for("ABC")), 1)

    def test_a_subject_or_name_or_address_from_the_page_is_refused(self):
        for key in ("subject", "name", "address", "body", "to"):
            with self.subTest(key=key):
                self.assertEqual(self.seam(self.body(**{key: "x"}))[0], 400)
        self.assertEqual(len(self.store.email_sent_for("ABC")), 0)

    def test_a_person_that_is_not_a_people_id_is_refused(self):
        for bad in ("Pat Example", "p-001", "P-1", "P-0001", 7, ["P-001"], ""):
            with self.subTest(person=bad):
                self.assertEqual(self.seam(self.body(person=bad))[0], 400)

    def test_tone_and_reply_by_must_have_their_shape(self):
        for over in ({"tone": 3}, {"tone": True}, {"tone": "1"}, {"reply_by": "soon"}, {"reply_by": "2026-02-31"}, {"reply_by": 5}):
            with self.subTest(over=over):
                self.assertEqual(self.seam(self.body(**over))[0], 400)
        self.assertEqual(len(self.store.email_sent_for("ABC")), 0)

    def test_a_failing_subject_seam_still_records_the_press_with_the_old_line(self):
        self.seam = feed.make_sent(self.store.path, [], by_user="Sam Lee", today=TODAY, subject_for=lambda *a: "")
        self.assertEqual(self.seam(self.body())[0], 200)
        con = sqlite3.connect(self.store.path)
        try:
            self.assertEqual(con.execute("SELECT count(*) FROM item_events WHERE place = 'email'").fetchone()[0], 0)
        finally:
            con.close()


class Whole(unittest.TestCase):
    """The real subject seam (subject_of over draft_email_feed.make): the server composes the subject; the sentence holds it, no address."""

    def test_the_server_composes_the_subject_and_the_sentence_holds_it(self):
        demo = DemoStore()
        self.addCleanup(demo.close)
        store = demo.store
        a = demo.action(description="Share the plan", owner="Pat Example", status="Open")
        draft = feed.make(store.data_for, clock=lambda: "2026-10-28 09:00")
        seam = feed.make_sent(store.path, [], by_user="Sam Lee", today=TODAY, subject_for=feed.subject_of(draft))
        self.assertEqual(seam({"project": "ABC", "ids": [a], "mode": "chase", "day": "2026-10-28", "tone": 0})[0], 200)
        con = sqlite3.connect(f"file:{store.path}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        try:
            got = [r["to"] for r in history.activity_for_item(con, a)["rows"] if r["kind"] == "Email sent"]
        finally:
            con.close()
        self.assertEqual(len(got), 1)
        self.assertTrue(got[0].startswith('Emailed on 28-10-2026, "'), got[0])
        self.assertNotIn("@", got[0])
        self.assertIn(a, got[0])


if __name__ == "__main__":
    unittest.main()
