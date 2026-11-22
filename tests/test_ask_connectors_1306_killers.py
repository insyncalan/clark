"""Row 1306, slice C1: killers for the connector switches' store readers. Fictional data only.

Run: python3 dev/run_tests.py test_ask_connectors_1306_killers
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from clark.store import open_store


class Readers(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.s = open_store(self.dir / "clark.db", onedrive_roots=[])
        self.addCleanup(self.s.close)

    def test_a_missing_switch_row_means_not_ready_and_everything_off(self):
        self.s.con.execute("UPDATE connector_switches SET is_on = 1")
        self.assertTrue(self.s.connector_allowed("mail", "ABC"))
        self.s.con.execute("DELETE FROM connector_switches WHERE connector = 'todoist'")
        self.assertFalse(self.s.connectors_ready())
        self.assertFalse(self.s.connector_allowed("mail", "ABC"))
        self.assertEqual(self.s.connector_switches(), {c: False for c in ("mail", "calendar", "teams", "sharepoint", "todoist")})

    def test_a_database_error_is_not_ready(self):
        self.s.con.close()
        self.assertIs(self.s.connectors_ready(), False)


if __name__ == "__main__":
    unittest.main()
