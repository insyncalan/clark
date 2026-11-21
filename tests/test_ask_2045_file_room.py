"""Row 1367 (PR 2045 CHANGES): a project that fills the passage limit still has room for a file added to the question.

Run: python3 dev/run_tests.py test_ask_2045_file_room
Fictional data only.
"""
import unittest

from _paths import SRC  # noqa: F401

from clark import ask, ask_data, store as st
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
        status, got = self.question("What is open?", files=[f("note.txt", b"ZQ-FILE-ROOM the vendor moved")])
        self.assertEqual(status, 200, got)
        (text,) = self.provider.sent
        self.assertIn("ZQ-FILE-ROOM", text)

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
