"""Row 1306 used: the answer carries what the real connector run did (the Used line, what was used and not used, and the from_connector
flag per part read), data only: no connector content. With no connector On and found the answer is byte-identical to today.

The command is faked (nothing is started); the run goes through the real ClaudeCommand and the real stream screen. Fictional data only.
Run: python3 dev/run_tests.py test_ask_connector_used
"""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401

import _publish_fixture as plant
from clark import ask, ask_claude as ac, ask_connector_screen as scr, ask_connectors, ask_service
from clark import ask_connector_stream as cs
from clark.store import open_store
from test_ask_connector_wiring import LIST_M365, P, PATH, final, got, stream, use

LINE = "Used: Read your mail (3 messages)"


def mail(i="1", text='[{"s": "a"}, {"s": "b"}, {"s": "c"}]'):
    return [use(i, f"{P}__outlook_email_search"), got(i, text)]


class Base(unittest.TestCase):
    def setUp(self):
        ask_connectors.clear_cache()
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.db = plant.build_db(self.d / "clark.db")
        self.provider = ac.ClaudeCommand(places=(), env={}, limit=5)
        self.provider.connector_runner = lambda: LIST_M365
        self.out = stream(final("The plan is on track.\nCITE: P1"))
        for p in (mock.patch.object(self.provider, "usable", return_value=(PATH, None)),
                  mock.patch.object(ac, "run", side_effect=lambda *a, **k: ("ok", self.out, 0))):
            p.start()
            self.addCleanup(p.stop)
        self.service = ask_service.AskService(self.db, self.provider, [])

    def turn_on(self, name="mail"):
        s = open_store(self.db, onedrive_roots=[])
        try:
            s.con.execute("UPDATE connector_switches SET is_on = 1 WHERE connector = ?", (name,))
            s.con.commit()
        finally:
            s.close()

    def ask(self):
        status, body = self.service.ask({"project": "PUB", "question": "What is the state of the plan?"})
        self.assertEqual(status, 200, body)
        return body


class TheAnswer(Base):
    def test_a_clean_read_is_named_flagged_and_added_to_the_notes(self):
        self.turn_on()
        self.out = stream(*mail(), final("The plan is on track.\nCITE: P1"))
        body = self.ask()
        self.assertTrue(body["ok"], body)
        self.assertEqual(body["used"], {"line": LINE, "used": ["Mail"], "not_used": [],
                                        "sources": [{"part": "Mail", "from_connector": True}]})
        self.assertEqual(body["notes"][-1], LINE)
        self.assertEqual(body["notes"].count(LINE), 1)

    def test_the_line_follows_the_other_notes(self):
        self.turn_on()
        self.out = stream(*mail(), final("Fine.\nCITE: P1"))
        with mock.patch.object(ask_service, "left_out_note", return_value="Some data was left out."):
            body = self.ask()
        self.assertEqual(body["notes"], ["Some data was left out.", LINE])

    def test_no_connector_content_is_in_the_answer_data(self):
        self.turn_on()
        self.out = stream(*mail(text='[{"s": "SECRET-SUBJECT"}]'), final("Fine.\nCITE: P1"))
        body = self.ask()
        self.assertNotIn("SECRET-SUBJECT", json.dumps(body))

    def test_two_parts_are_both_named(self):
        self.turn_on("mail")
        self.turn_on("calendar")
        self.provider.connector_runner = lambda: LIST_M365
        self.out = stream(*mail(), use("2", f"{P}__outlook_calendar_search"), got("2", '[{"e": 1}]'), final("Fine.\nCITE: P1"))
        body = self.ask()
        self.assertEqual(body["used"]["line"], "Used: Read your mail (3 messages), Read your calendar (1 event)")
        self.assertEqual(body["used"]["used"], ["Mail", "Calendar"])
        self.assertEqual([s["part"] for s in body["used"]["sources"]], ["Mail", "Calendar"])
        self.assertTrue(all(s["from_connector"] is True for s in body["used"]["sources"]))

    def test_a_countless_answer_shows_no_count(self):
        self.turn_on()
        self.out = stream(*mail(text="Subject: Lunch"), final("Fine.\nCITE: P1"))
        self.assertEqual(self.ask()["used"]["line"], "Used: Read your mail")

    def test_a_connector_on_but_nothing_called_carries_empty_used_and_no_note(self):
        self.turn_on()
        body = self.ask()
        self.assertEqual(body["used"], {"line": "", "used": [], "not_used": [], "sources": []})
        self.assertNotIn("", body["notes"])
        self.assertEqual(body["notes"], [])

    def test_a_refused_run_is_no_answer_with_no_used_data(self):
        self.turn_on()
        self.out = stream(*mail(text="a​b"), final("Fine.\nCITE: P1"))
        status, body = self.service.ask({"project": "PUB", "question": "What is the state of the plan?"})
        self.assertFalse(body["ok"])
        self.assertNotIn("used", body)


class WithNoConnector(Base):
    def test_off_is_byte_identical_to_a_run_with_no_connector_code(self):
        body = self.ask()
        self.assertNotIn("used", body)
        self.assertEqual(body["notes"], [])
        # the same service with a provider that has no last_line at all gives the same bytes
        plain = ask_service.AskService(self.db, ask.StubProvider(reply="The plan is on track.\nCITE: P1"), [])
        other = plain.ask({"project": "PUB", "question": "What is the state of the plan?"})[1]
        self.assertEqual(sorted(body), sorted(other))

    def test_a_stale_line_from_an_earlier_run_does_not_reach_the_next_answer(self):
        self.turn_on()
        self.out = stream(*mail(), final("Fine.\nCITE: P1"))
        self.assertIn("used", self.ask())
        s = open_store(self.db, onedrive_roots=[])
        try:
            s.con.execute("UPDATE connector_switches SET is_on = 0")
            s.con.commit()
        finally:
            s.close()
        ask_connectors.clear_cache()
        self.out = stream(final("Fine.\nCITE: P1"))
        body = self.ask()
        self.assertNotIn("used", body)
        self.assertEqual(body["notes"], [])

    def test_the_helper_carries_not_used_and_names_only_the_parts_used(self):
        line = scr.used_line(scr.screen_all([("outlook_email_search", "[1]"), ("teams_list_chats", "a\u200bb")]))
        self.assertEqual(ask_service.connector_used(line),
                         {"line": "Used: Read your mail (1 message). Not used: Teams chats has hidden characters", "used": ["Mail"],
                          "not_used": ["Teams chats has hidden characters"], "sources": [{"part": "Mail", "from_connector": True}]})

    def test_the_connector_used_helper_is_none_for_none(self):
        self.assertIsNone(ask_service.connector_used(None))


class Stream(unittest.TestCase):
    def test_inspect_keeps_the_whole_line_and_checked_its_text(self):
        out = stream(*mail(), final("x"))
        ok, line, result = cs.inspect(out, {"Mail"})
        self.assertTrue(ok)
        self.assertEqual(line.used, ("Mail",))
        self.assertEqual(cs.checked(out, {"Mail"})[1], line.text)
        self.assertEqual(line.text, LINE)

    def test_a_refusal_keeps_the_line_and_gives_no_result(self):
        ok, line, result = cs.inspect(stream(*mail(text="a​b"), final("x")), {"Mail"})
        self.assertFalse(ok)
        self.assertIsNone(result)
        self.assertEqual(line.text, "Not used: Mail has hidden characters")


if __name__ == "__main__":
    unittest.main()
