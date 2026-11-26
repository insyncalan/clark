"""Row 1533: the author's Board switch (projects.show_board_client) reaches the published file through the REAL publish.read_inputs.

publish.read_inputs asks the store only for the columns in PUBLISH_FIELDS and GATES, so a switch that is in neither is never read and
the file never gets a board, however many tests patch read_inputs. Fictional data only.

Run: python3 dev/run_tests.py test_publish_board_client_1533
"""
import unittest

from _demo import USER, DemoStore
from clark import changes, publish

DAY = "2026-10-28"


class BoardSwitchReachesTheFile(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.change = changes.make_change(self.s.path, [], USER)

    def switch(self, value):
        status, body = self.change({"project": "ABC", "kind": "projects", "op": "update", "changes": {"show_board_client": value}})
        self.assertEqual(status, 200, body)

    def published(self):
        """The data block's project, made from the real read (no patch anywhere)."""
        return publish.select(publish.read_inputs(self.s, "ABC", DAY))["data"]["project"]

    def test_the_switch_is_read_by_the_real_read_inputs(self):
        self.switch(1)
        self.assertEqual(publish.read_inputs(self.s, "ABC", DAY)["data"]["project"].get("show_board_client"), 1)

    def test_switch_on_puts_the_board_in_the_published_project(self):
        self.switch(1)
        self.assertEqual(self.published().get("board"), 1)

    def test_switch_off_or_never_set_puts_no_board_in_it(self):
        self.assertNotIn("board", self.published())
        self.switch(1)
        self.switch(0)
        self.assertNotIn("board", self.published())

    def test_the_switch_is_decided_on_and_never_copied_as_a_project_field(self):
        self.switch(1)
        self.assertNotIn("show_board_client", self.published())


if __name__ == "__main__":
    unittest.main()
