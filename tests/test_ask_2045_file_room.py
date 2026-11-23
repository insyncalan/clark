"""Row 1367 (PR 2045 CHANGES): a project that fills the passage limit still has room for a file added to the question.

Run: python3 dev/run_tests.py test_ask_2045_file_room
Fictional data only.
"""
import unittest
from unittest import mock

from _paths import SRC  # noqa: F401

from clark import ask, ask_data, ask_passages, ask_service, store as st
from test_ask_files_route import f
from test_ask_route import Base, CODE


class FileRoom(Base):
    def fill(self, n):
        store = st.open_store(self.db, onedrive_roots=[])
        try:
            with store.step("dashboard", "tester", place="menu") as s:
                for i in range(n):
                    s.create("actions", {"project": CODE, "description": f"ZQ-FILL-{i:03d} " + "lorem ipsum " * 40, "raised": "2026-10-01", "source": "demo", "status": "Open"})
        finally:
            store.close()

    def test_a_project_at_the_passage_limit_plus_a_file_is_not_refused(self):
        self.fill(300)
        seen, p1, p2 = self.spy()
        with mock.patch.object(ask_service, "PROJECT_SHARE", 600000), p1, p2:      # a share wide enough that the passage limit, not the characters, is what stops the project
            status, got = self.question("What is open?", files=[f("note.txt", b"ZQ-FILE-ROOM the vendor moved")])
        self.assertEqual(status, 200, got)
        self.assertEqual(seen["project_passages"], ask.MAX_PASSAGES - 1)      # the project filled every place but the file's
        (text,) = self.provider.sent
        self.assertIn("ZQ-FILE-ROOM", text)

    def spy(self):
        """Record what the service hands to the project read and to the folder read (a folder reader that finds nothing)."""
        seen = {}
        real = ask_data.project_data

        def project(*a, **k):
            seen["project"] = (a, k)
            out = real(*a, **k)
            seen["project_passages"] = len(out.passages)
            seen["project_chars"] = sum(len(x.text) for x in out.passages)
            return out

        def folders(*a, **k):
            seen["folders"] = (a, k)
            return ask_passages.FolderData(passages=())

        return seen, mock.patch.object(ask_data, "project_data", project), mock.patch.object(ask_service.ask_passages, "folder_data", folders)

    def fill_big(self, n, size):
        store = st.open_store(self.db, onedrive_roots=[])
        try:
            with store.step("dashboard", "tester", place="menu") as s:
                for i in range(n):
                    s.create("actions", {"project": CODE, "description": f"ZQ-BIG-{i:03d} " + "lorem ipsum " * (size // 12), "raised": "2026-10-01", "source": "demo", "status": "Open"})
        finally:
            store.close()

    def test_files_take_their_characters_off_the_project_share_and_the_request_is_not_refused(self):
        self.fill_big(100, 3600)                     # the project alone would take its whole share
        texts = [("ZQ-BIGFILE-%d " % i + "lorem ipsum " * 320) for i in range(5)]      # a file passage is at most 4,000 characters (ask.MAX_PASSAGE)
        added = sum(len(t) for t in texts)
        seen, p1, p2 = self.spy()
        with mock.patch.object(ask, "BUDGET", 30000), mock.patch.object(ask_service, "PROJECT_SHARE", 15000), p1, p2:     # a small budget, so five files can fill it
            status, got = self.question("What is open?", files=[f("f%d.txt" % i, t.encode()) for i, t in enumerate(texts)])
        self.assertEqual(status, 200, got)           # without the reserve: project 15,000 + files 19,000 is over the 30,000 budget and is refused
        left = 30000 - added
        self.assertLess(left, 15000)
        self.assertEqual(seen["project"][0][3], left)
        self.assertLessEqual(seen["project_chars"] + added, 30000)
        self.assertGreater(seen["project_chars"], 0)

    def test_the_folders_get_what_the_file_and_the_project_leave_in_characters_and_in_passages(self):
        self.fill(5)
        text = "ZQ-FOLDERFILE " + "lorem ipsum " * 250
        second = "ZQ-SECOND the vendor moved"
        seen, p1, p2 = self.spy()
        with p1, p2:
            status, got = self.question("What is open?", files=[f("a.txt", text.encode()), f("b.txt", second.encode())])
        self.assertEqual(status, 200, got)
        (args, _kw) = seen["folders"]
        self.assertEqual(args[3], ask.BUDGET - len(text) - len(second) - seen["project_chars"])
        self.assertEqual(args[5], ask.MAX_PASSAGES - 2 - seen["project_passages"])
        self.assertGreater(seen["project_passages"], 1)

    def test_a_too_long_request_keeps_the_file_that_shares_no_word_with_the_question(self):
        """Item 1292: the service tells the request how many of its passages are files, so a file the question does not name is cut last, not first."""
        folder = ask_passages.FolderData(passages=tuple(ask.Passage("notes/f%d.md" % i, "ZQ-PLAIN%d " % i + "lorem " * 200) for i in range(3)), left_out=0)
        data = ("ZQ-UPLOADED the vendor moved " + "lorem " * 200).encode()
        with mock.patch.object(ask_service.ask_passages, "folder_data", return_value=folder):
            status, got = self.question("What is open?", files=[f("note.txt", data)])
            self.assertEqual(status, 200, got)
            full = len(self.provider.sent[-1])
            with mock.patch.object(ask, "request_cap", return_value=full - 1):
                status, got = self.question("What is open?", files=[f("note.txt", data)])
        self.assertEqual(status, 200, got)
        self.assertIn("ZQ-UPLOADED", self.provider.sent[-1])
        self.assertLess(len(self.provider.sent[-1]), full)

    def test_without_a_file_the_project_still_takes_the_whole_limit(self):
        self.fill(300)
        store = st.open_store(self.db, onedrive_roots=[])
        try:
            self.assertEqual(len(ask_data.project_data(store, CODE, "open", ask.BUDGET).passages), ask.MAX_PASSAGES)
            self.assertEqual(len(ask_data.project_data(store, CODE, "open", ask.BUDGET, limit=ask.MAX_PASSAGES - 1).passages), ask.MAX_PASSAGES - 1)
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()
