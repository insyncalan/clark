"""#1366 review fixes: modes of a folder made earlier, the worker's connection on a failed read, and the reasons given for files left out.
Made-up files only. Run: python3 dev/run_tests.py test_ask_index_review_1366"""
import os
import stat
import unittest
from unittest import mock

from _paths import SRC  # noqa: F401

from test_ask_index_1366 import Base, FAKE_KEY, ix


class Modes(Base):
    def test_an_index_folder_and_file_made_looser_are_put_back_to_0700_and_0600(self):
        d = self.data / "ask-index"
        d.mkdir()
        os.chmod(d, 0o755)
        f = ix.path_for(self.data, "P1")
        f.write_bytes(b"")
        os.chmod(f, 0o644)
        self.put("a.txt", "zqone")
        ix.build(self.data, "P1", [self.box])
        self.assertEqual(stat.S_IMODE(d.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(f.stat().st_mode), 0o600)
