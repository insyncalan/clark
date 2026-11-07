"""#633: in the Docker container Settings > Update offers nothing to install: the clark folder is shared in read-only, so an
update is a newer clark folder started in its place. Status says so in the Update row's own words (the page then hides Update
from file and Undo update); review, install and Undo update refuse in the same words and touch nothing.

Run: python3 dev/run_tests.py test_update_container
No Docker: container_mode is stood in for. Every folder is a temporary one (the fixture of test_updater).
"""
import unittest
from unittest import mock

from _paths import SRC  # noqa: F401  (puts src/ on the path)

from clark import platform, updater as up
from test_updater import Rig


class InContainer(Rig):
    def setUp(self):
        super().setUp()
        patch = mock.patch.object(platform, "container_mode", return_value=True)
        patch.start()
        self.addCleanup(patch.stop)

    def test_the_status_blocks_with_the_docker_sentence_and_offers_no_update(self):
        status, body = self.up.status()
        self.assertEqual(status, 200)
        self.assertEqual(body["blocked"], up.CONTAINER)
        self.assertIsNone(body["available"])
        self.assertIsNone(body["last"])
        self.assertTrue(body["installed"].startswith("Version 0.3.0"))

    def test_a_last_update_carried_in_with_the_data_offers_no_undo(self):
        with mock.patch.object(platform, "container_mode", return_value=False):
            self.installed()
            now = self.make(version="0.3.1")
            self.assertIsNotNone(now.status()[1]["last"])
        self.assertIsNone(now.status()[1]["last"])

    def test_the_sentence_is_plain_and_says_the_newer_folder_and_that_nothing_changed(self):
        self.assertIn("starting from the newer clark folder", up.CONTAINER)
        self.assertTrue(up.CONTAINER.endswith("Nothing was changed."))

    def test_review_from_downloads_or_a_file_is_refused_and_no_window_opens(self):
        asked = []
        self.up = self.make(choose=lambda prompt, start=None: asked.append(prompt))
        for source in ("downloads", "file"):
            status, body = self.up.review({"from": source})
            self.assertEqual((status, body["code"], body["message"]), (409, "blocked", up.CONTAINER), source)
        self.assertEqual(asked, [])

    def test_install_arm_and_undo_are_refused_even_with_a_valid_looking_request(self):
        for status, body in (self.up.install({"review_id": "x"}), self.up.arm_undo({}), self.up.undo({"arm_id": "x"})):
            self.assertEqual((status, body["code"], body["message"]), (409, "blocked", up.CONTAINER))
        self.assertEqual(self.started, [])


class OutsideContainer(Rig):
    def test_nothing_changes_without_the_container(self):
        status, body = self.up.status()
        self.assertIsNone(body["blocked"])
        self.assertEqual(body["available"], {"version": "0.3.1", "label": "Review 0.3.1"})
        self.reviewed()


if __name__ == "__main__":
    unittest.main()
