"""#560: a client-visible item with no client wording publishes its title only.

Ruling: for a client-visible row with no client_message, the file holds the row's title (an action's or risk's own
sentence, a milestone's name) and nothing of its description or its Latest update, in the web file's data and in the Word copy
(which reads the same selected rows). A row with client wording is unchanged. A marker is put in every free-text field the
row has and the whole file source and the Word file's text are scanned. All rows are fictional.

Run: python3 dev/run_tests.py test_publish_data_block_client_words
"""
import io
import unittest
import zipfile
from unittest import mock

from _demo import USER, DemoStore
from clark import docx_build, publish

TEAM_ONLY = "zz-team-only-wording-560"
TITLE = "zz-plain-title-560"
CLIENT = "zz-client-wording-560"


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

    def word_text(self):
        pub = publish.select(publish.read_inputs(self.s, "ABC", "2026-10-29"))
        with zipfile.ZipFile(io.BytesIO(docx_build.build(pub))) as z:
            return "".join(z.read(n).decode("utf-8", "replace") for n in z.namelist() if n.endswith(".xml"))

    def test_action_latest_update_not_in_source_without_client_message(self):
        ref = self.demo.action(description=TITLE)
        self.demo.update("actions", ref, {"latest_update": TEAM_ONLY})
        self.assertNotIn(TEAM_ONLY, self.source())
        self.assertIn(TITLE, self.source())

    def test_action_latest_update_not_in_word_without_client_message(self):
        ref = self.demo.action(description=TITLE)
        self.demo.update("actions", ref, {"latest_update": TEAM_ONLY})
        self.assertNotIn(TEAM_ONLY, self.word_text())
        self.assertIn(TITLE, self.word_text())

    def test_milestone_description_not_in_source_or_word_without_client_message(self):
        self.demo.update("milestones", self.demo.milestone, {"description": TEAM_ONLY})
        self.assertNotIn(TEAM_ONLY, self.source())
        self.assertNotIn(TEAM_ONLY, self.word_text())
        self.assertIn("Pilot live", self.source())

    def test_a_blank_client_message_counts_as_none(self):
        ref = self.demo.action(description=TITLE, client_message="   ")
        self.demo.update("actions", ref, {"latest_update": TEAM_ONLY})
        self.assertNotIn(TEAM_ONLY, self.source())

    def test_risk_title_is_published_and_has_no_other_text(self):
        self.raid(description=TITLE)
        src = self.source()
        self.assertIn(TITLE, src)
        self.assertNotIn(TEAM_ONLY, src)

    def test_action_with_client_wording_keeps_its_latest_update(self):
        ref = self.demo.action(description=TITLE, client_message=CLIENT)
        self.demo.update("actions", ref, {"latest_update": TEAM_ONLY})
        self.assertIn(TEAM_ONLY, self.source())
        self.assertIn(TEAM_ONLY, self.word_text())

    def test_milestone_with_client_wording_keeps_its_description(self):
        self.demo.update("milestones", self.demo.milestone, {"description": TEAM_ONLY, "client_message": CLIENT})
        self.assertIn(TEAM_ONLY, self.source())

    def test_control_client_message_is_published(self):
        """Not a failure mark: the client's own wording is always in the file (guards the tests above from passing vacuously)."""
        self.raid(client_message=CLIENT)
        self.assertIn(CLIENT, self.source())

    def test_mutation_the_strip_is_what_removes_it(self):
        """Mutation: with the rule turned off the marker is in the file, so the tests above are red without the fix."""
        ref = self.demo.action(description=TITLE)
        self.demo.update("actions", ref, {"latest_update": TEAM_ONLY})
        self.demo.update("milestones", self.demo.milestone, {"description": TEAM_ONLY + "-m"})
        with mock.patch.object(publish, "WORDLESS_DROPS", {}):
            self.assertIn(TEAM_ONLY, self.source())
            self.assertIn(TEAM_ONLY + "-m", self.source())


if __name__ == "__main__":
    unittest.main()
