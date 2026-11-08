"""#560: the published file's data block carries only client wording for a client-visible item that has none.

For a client-visible action or risk with no client_message, the file's embedded data must not hold the team's own description
(or an action's latest_update): the page may draw nothing from them, and anyone reading the file's source sees them. The tests read
the file source from the real `publish.build`. Each is marked expectedFailure: PUBLISH_FIELDS still carries "description" (actions,
raid) and "latest_update" (actions). Open design question, not decided here: the page draws `description` as the item's title
(workItems.js, clientRisks.js) and, per #870, whether a row with no client wording shows its title is a pending ruling; the
Latest update is published on purpose by test_latest_update_publish (#457). The fix is blocked on both. All rows are fictional.

Run: python3 dev/run_tests.py test_publish_data_block_client_words
"""
import unittest
from unittest import mock

from _demo import USER, DemoStore
from clark import publish

TEAM_ONLY = "zz-team-only-wording-560"


class DataBlockClientWords(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store

    def source(self):
        return publish.build(self.s, "ABC", now="2026-10-29")["body"].decode("utf-8")

    def raid(self, **values):
        base = {"project": "ABC", "type": "Risk", "description": TEAM_ONLY, "raised": "2026-10-01", "source": "demo"}
        with self.s.step("dashboard", USER) as st:
            return st.create("raid", {**base, **values})

    @unittest.expectedFailure
    def test_action_description_not_in_source_without_client_message(self):
        self.demo.action(description=TEAM_ONLY)
        self.assertNotIn(TEAM_ONLY, self.source())

    @unittest.expectedFailure
    def test_action_latest_update_not_in_source_without_client_message(self):
        ref = self.demo.action(description="Plain title")
        self.demo.update("actions", ref, {"latest_update": TEAM_ONLY})
        self.assertNotIn(TEAM_ONLY, self.source())

    @unittest.expectedFailure
    def test_risk_description_not_in_source_without_client_message(self):
        self.raid()
        self.assertNotIn(TEAM_ONLY, self.source())

    def test_control_client_message_is_published(self):
        """Not a failure mark: the client's own wording is always in the file (guards the tests above from passing vacuously)."""
        self.raid(client_message="zz-client-wording-560")
        self.assertIn("zz-client-wording-560", self.source())

    def without(self, table, field):
        cut = {**publish.PUBLISH_FIELDS, table: tuple(f for f in publish.PUBLISH_FIELDS[table] if f != field)}
        return mock.patch.dict(publish.PUBLISH_FIELDS, cut)

    def test_mutation_actions_description(self):
        """Mutation per field: with the field out of PUBLISH_FIELDS the team text is gone, so the marked test above is red for that field alone."""
        self.demo.action(description=TEAM_ONLY)
        with self.without("actions", "description"):
            self.assertNotIn(TEAM_ONLY, self.source())

    def test_mutation_actions_latest_update(self):
        ref = self.demo.action(description="Plain title")
        self.demo.update("actions", ref, {"latest_update": TEAM_ONLY})
        with self.without("actions", "latest_update"):
            self.assertNotIn(TEAM_ONLY, self.source())

    def test_mutation_raid_description(self):
        self.raid()
        with self.without("raid", "description"):
            self.assertNotIn(TEAM_ONLY, self.source())


if __name__ == "__main__":
    unittest.main()
