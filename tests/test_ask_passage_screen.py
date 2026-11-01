"""A passage that looks like a key or a password is left out of the ask request before anything is sent (Hawkeye's finding on #187).

`ask.build_request` is the one place passages become request text, so the screen sits there: each passage (and its label) is
checked, a refused one is dropped (the question goes ahead without it), and only a count is kept. The fake key is built from
pieces so this file holds no real-looking secret. Fictional data only.

Run: python3 dev/run_tests.py test_ask_passage_screen
"""
import logging
import unittest

from _paths import SRC  # noqa: F401  (puts src/ on the path)

from unittest import mock

import test_ask_route as route_base
from clark import ask, ask_data

FAKE_KEY = "sk-" + "ant-api03-" + "A1b2C3d4E5f6G7h8I9j0" + "-xyz"
FAKE_PASSWORD = "password" + ": " + "hunter22"
CLEAN = [("Plan", "The supplier confirmed the delivery for Friday."), ("Risks", "ABC-R-001 is open and owned by Sam.")]


class Sink(logging.Handler):
    def __init__(self):
        super().__init__(logging.DEBUG)
        self.lines = []

    def emit(self, record):
        self.lines.append(record.getMessage())


class Recorder(ask.Provider):
    def __init__(self):
        self.sent = []

    def status(self):
        return {"connected": True, "why": ""}

    def ask(self, request):
        self.sent.append(request.text)
        return "Fine.\nCITE: P1"


class PassageScreen(unittest.TestCase):
    def test_a_passage_with_a_key_is_dropped_and_the_rest_still_go(self):
        passages = [CLEAN[0], ("Notes", "Use " + FAKE_KEY + " for the feed"), CLEAN[1]]
        req = ask.build_request("What is late?", passages)
        self.assertNotIn(FAKE_KEY, req.text)
        self.assertIn("What is late?", req.text)
        self.assertIn(CLEAN[0][1], req.text)
        self.assertIn(CLEAN[1][1], req.text)
        self.assertEqual((req.left_out_secret, req.kept), (1, (0, 2)))
        self.assertEqual([label for _p, label in req.passages], ["Plan", "Risks"])
        self.assertEqual(req.passage_ids, ("P1", "P2"))

    def test_a_password_and_a_key_in_a_label_are_dropped_too(self):
        passages = [CLEAN[0], ("Login", FAKE_PASSWORD), ("Row " + FAKE_KEY, "Harmless words.")]
        req = ask.build_request("Q?", passages)
        self.assertEqual((req.left_out_secret, req.kept), (2, (0,)))
        self.assertNotIn("hunter22", req.text)
        self.assertNotIn(FAKE_KEY, req.text)

    def test_the_fake_provider_never_receives_the_dropped_passage(self):
        prov = Recorder()
        req = ask.build_request("What is late?", [("Notes", FAKE_KEY), *CLEAN])
        got = ask.ask_provider(prov, req, ["ABC"], lambda ref: True)
        self.assertIsInstance(got, ask.Reply)
        self.assertEqual(len(prov.sent), 1)
        self.assertNotIn(FAKE_KEY, prov.sent[0])
        self.assertIn("What is late?", prov.sent[0])
        self.assertIn(CLEAN[1][1], prov.sent[0])

    def test_clean_passages_are_unchanged(self):
        req = ask.build_request("Q?", CLEAN)
        self.assertEqual((req.left_out_secret, req.kept, ask.secret_note(req.left_out_secret)), (0, (0, 1), ""))
        self.assertEqual(req.text, ask.build_request("Q?", CLEAN).text)
        self.assertEqual(req.passage_ids, ("P1", "P2"))

    def test_every_passage_dropped_still_asks_the_question(self):
        req = ask.build_request("Q?", [("A", FAKE_KEY), ("B", FAKE_PASSWORD)])
        self.assertEqual((req.left_out_secret, req.passages), (2, ()))
        self.assertIn("PASSAGES: none were found", req.text)

    def test_the_count_is_in_plain_words(self):
        self.assertEqual(ask.secret_note(0), "")
        said = ("Part of your report was left out because it looks like a password or a key, so the answer may be missing something. "
                "Take the password out of the item if you want it included.")
        for n in (1, 3):
            self.assertEqual(ask.secret_note(n), said)
        self.assertNotIn("passage", said)

    def test_nothing_is_logged_with_the_text(self):
        sink, root = Sink(), logging.getLogger()
        level = root.level
        root.addHandler(sink)
        root.setLevel(logging.DEBUG)
        try:
            ask.ask_provider(Recorder(), ask.build_request("Q?", [("Notes", FAKE_KEY), *CLEAN]), ["ABC"], lambda ref: True)
        finally:
            root.removeHandler(sink)
            root.setLevel(level)
        self.assertNotIn(FAKE_KEY, "\n".join(sink.lines))


class ThroughTheRoute(route_base.Base):
    """POST /api/ask with a project passage that holds a key: dropped, the others sent, the count shown in notes, and the cited
    passage still matches its label (the IDs follow the passages that were sent)."""

    def test_a_project_passage_with_a_key_is_not_sent_and_is_counted(self):
        real = ask_data.project_data(*self._args())
        planted = ask.Passage("Planted", "Use " + FAKE_KEY + " for the feed")
        data = ask_data.ProjectData((planted,) + tuple(real.passages), real.facts, 0)
        with mock.patch.object(ask_data, "project_data", return_value=data):
            status, got = self.question("How is the plan?")
        self.assertEqual((status, got["ok"]), (200, True), got)
        (text,) = self.provider.sent
        self.assertNotIn(FAKE_KEY, text)
        self.assertIn("How is the plan?", text)
        self.assertIn(ask.secret_note(1), got["notes"])
        self.assertNotIn(FAKE_KEY, repr(got))
        self.assertEqual([s["label"] for s in got["sources"]], [real.passages[0].label])

    def test_a_real_stored_row_with_a_key_is_not_sent_nor_echoed_nor_logged(self):
        """The row goes in through the store, is published by the real report rules and read by the real route: no patched data."""
        from clark import store as st
        store = st.open_store(self.db, onedrive_roots=[])
        try:
            with store.step("dashboard", "tester", place="menu") as s:
                s.create("actions", {"project": route_base.CODE, "description": "Feed login " + FAKE_KEY + " ZQ-KEYROW",
                                     "raised": "2026-10-01", "client_visible": 1, "source": "demo"})
        finally:
            store.close()
        sink, root = Sink(), logging.getLogger()
        level = root.level
        root.addHandler(sink)
        root.setLevel(logging.DEBUG)
        try:
            status, got = self.question("What are the actions?")
        finally:
            root.removeHandler(sink)
            root.setLevel(level)
        self.assertEqual((status, got["ok"]), (200, True), got)
        (text,) = self.provider.sent
        self.assertIn("What are the actions?", text)
        self.assertIn("ZQ-KEEP-RISK-1", text)                 # the other passages still go (the actions passage holding the key is the one left out)
        self.assertNotIn(FAKE_KEY, text)
        self.assertNotIn("ZQ-KEYROW", text)
        self.assertIn(ask.secret_note(1), got["notes"])
        self.assertNotIn(FAKE_KEY, repr(got))
        self.assertNotIn(FAKE_KEY, "\n".join(sink.lines))

    def _row_across_the_cut(self):
        """Store an action whose description puts the password across the 4,000-character cut of its row."""
        from clark import store as st
        for pad in range(3800, 4000):
            row = {"id": "ZQ-A-1", "description": "ok " * (pad // 3) + FAKE_PASSWORD, "raised": "2026-10-01"}
            line = ask_data.row_line("actions", row)
            at = line.find("password")
            if 0 <= at < ask.MAX_PASSAGE < at + len(FAKE_PASSWORD):
                break
        else:
            self.fail("could not place the password across the cut")
        store = st.open_store(self.db, onedrive_roots=[])
        try:
            with store.step("dashboard", "tester", place="menu") as s:
                s.create("actions", {"project": route_base.CODE, "description": row["description"], "raised": "2026-10-01",
                                     "client_visible": 1, "source": "demo"})
        finally:
            store.close()

    def test_a_password_across_the_cut_of_a_real_row_is_not_sent(self):
        self._row_across_the_cut()
        status, got = self.question("What are the actions?")
        self.assertEqual((status, got["ok"]), (200, True), got)
        (text,) = self.provider.sent
        self.assertIn("ZQ-KEEP-RISK-1", text)                 # the other passages still go
        self.assertNotIn("hunter", text)
        self.assertNotIn("password", text)
        self.assertNotIn("hunter", repr(got))

    def test_a_long_line_with_a_password_is_left_out_and_counted(self):
        line = "ok " * 1400 + FAKE_PASSWORD
        passages, left = ask_data._cut_screened("L", [line, "a short line"])
        self.assertEqual(left, 1)
        self.assertEqual([p.text for p in passages], ["a short line"])

    def test_a_long_line_with_no_password_is_still_cut_and_kept(self):
        passages, left = ask_data._cut_screened("L", ["ok " * 2000])
        self.assertEqual(left, 0)
        self.assertEqual([len(p.text) for p in passages], [ask.MAX_PASSAGE])

    def _args(self):
        from clark import store as st
        store = st.open_store(self.db, onedrive_roots=[])
        self.addCleanup(store.close)
        return store, route_base.CODE, "How is the plan?", 40000


if __name__ == "__main__":
    unittest.main()
