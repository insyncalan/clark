"""#619: a Local file saved inside the client folder. The web publish refuses it even with To client off (publish_flow
"same_folder"); the Word export now refuses it in the same words (with "Nothing was saved." for a Word file) and writes nothing.

Fictional data only: the demo store's project ABC, a client folder with a subfolder, and a Local folder outside it.
Run: python3 dev/run_tests.py test_word_local_in_client_folder
"""
import unittest

from _paths import SRC  # noqa: F401  (puts src/ on the path)
from clark import publish_flow, word_route
from test_word_client_held_back import TODAY, USER, Setup

WEB = "That is the client's folder. Save the local copy somewhere else. Nothing was published."       # literals: not read back from the code
WORD = "That is the client's folder. Save the local copy somewhere else. Nothing was saved."


class Cases(Setup, unittest.TestCase):
    def plant(self):
        self.inner = self.client / "Inner"
        self.inner.mkdir()

    def export(self, folder, to_client=False):
        seam = word_route.make_word_export(self.store.path, [], USER, today=lambda: TODAY, choose_folder=lambda prompt: str(folder))
        return seam({"project": "ABC", "to_client": to_client})

    def test_a_subfolder_of_the_client_folder_is_refused_and_nothing_is_written(self):
        status, got = self.export(self.inner)
        self.assertEqual((status, got["ok"]), (409, False), got)
        self.assertEqual(got["message"], WORD)
        self.assertEqual(self.names(self.inner), [])
        self.assertEqual(self.names(self.client), ["Inner"])

    def test_the_client_folder_itself_is_refused_and_nothing_is_written(self):
        status, got = self.export(self.client)
        self.assertEqual((status, got["ok"]), (409, False), got)
        self.assertEqual(got["message"], WORD)
        self.assertEqual(self.names(self.client), ["Inner"])

    def test_a_folder_outside_the_client_folder_still_saves(self):
        status, got = self.export(self.word_local)
        self.assertEqual((status, got["ok"]), (200, True), got)
        self.assertEqual(self.names(self.word_local), [got["name"]])

    def test_the_web_publish_refuses_the_same_with_to_client_off(self):
        seam = lambda folder: publish_flow.Publisher(
            self.store.path, [], choose_save_file=lambda prompt, name, start=None: folder / name, today=lambda: TODAY,
            by_user=lambda: USER, data_dir=self.store.path.parent)
        status, got = seam(self.inner).publish({"project": "ABC", "to_client": False})
        self.assertEqual((status, got["code"] if "code" in got else got.get("action"), got["message"]), (409, "same_folder", WEB), got)
        self.assertEqual(self.names(self.inner), [])
        status, got = seam(self.local).publish({"project": "ABC", "to_client": False})
        self.assertEqual(status, 200, got)


if __name__ == "__main__":
    unittest.main()
