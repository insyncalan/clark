"""Row 1294 slice 4: a question asked through POST /api/ask reads the folders for all projects as well as the project's own.
Run: python3 dev/run_tests.py test_ask_folders_all_ask_1294
The reader of the folders is replaced by one that notes which folders it was given; the folders for all projects are named by a stand-in.
"""
import unittest
from unittest import mock

from _paths import SRC  # noqa: F401
from test_ask_change_route import Base
from clark import ask_folders, ask_passages, ask_service


class AskReadsSharedFolders(Base):
    def test_a_question_is_given_the_folders_for_all_projects_first(self):
        seen = []

        def folder_data(folders, *_a, **_kw):
            seen.append(list(folders))
            return ask_passages.FolderData(passages=())

        self.provider.reply = "Here is what I found."
        with mock.patch.object(ask_folders, "shared_folders", lambda _dir: ["/shared/one", "/shared/two"]), \
                mock.patch.object(ask_service.ask_passages, "folder_data", folder_data):
            status, got = self.s.api("POST", "/api/ask", {"project": "ABC", "question": "What should change?"})
        self.assertEqual((status, got.get("ok")), (200, True), got)
        self.assertEqual(seen, [["/shared/one", "/shared/two"]], "the folders for all projects reach the reader, in order")


if __name__ == "__main__":
    unittest.main()
