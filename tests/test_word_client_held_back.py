"""#607 (PR 475 MEDIUM): a client-visible action whose own text names the ID of an action that is hidden from the client. The ID
is on the web publish's held-back list (publish_flow.markers_for lists the ID of every row that select() left out), so a web
publish with To client ticked refuses it ("Nothing was published. The report has something in it that must not go to the
client ..."). The Word export (word_route._do_export) builds from the same select() but checks only the client folder
(to_client.preflight) before it writes the client copy: it never calls markers_for or to_client.check_copy.

Fictional data only: the demo store's project ABC, two actions, a client folder and Local folders in a temporary folder.
Run: python3 dev/run_tests.py test_word_client_held_back
"""
import re
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from _demo import DemoStore
from _paths import SRC  # noqa: F401  (puts src/ on the path)
from clark import publish_flow, to_client, word_route

USER = "Sam Carter"
TODAY = "2026-10-29"
HIDDEN_TEXT = "Hidden supplier review"
NOTHING_WRITTEN = "Nothing was written to the client folder."


class HeldBack(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store
        self.tmp = Path(tempfile.mkdtemp(prefix="clark-held-back-")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.local, self.word_local, self.client = self.tmp / "Local", self.tmp / "WordLocal", self.tmp / "Client"
        for folder in (self.local, self.word_local, self.client):
            folder.mkdir()
        self.demo.action(description=HIDDEN_TEXT, client_visible=0)            # left out of every client file
        (hidden,) = [r for r in self.store.read("actions", "ABC") if r["description"] == HIDDEN_TEXT]
        self.hidden_id = hidden["id"]
        self.demo.action(description=f"Book the review room after {self.hidden_id} is settled", client_visible=1)
        self.demo.update("projects", "ABC", {"publish_client": str(self.client)})

    def web_publish(self):
        publisher = publish_flow.Publisher(self.store.path, [], choose_save_file=lambda prompt, name, start=None: self.local / name,
                                           today=lambda: TODAY, by_user=lambda: USER, data_dir=Path(self.store.path).parent)
        return publisher.publish({"project": "ABC", "to_client": True})

    def word_export(self):
        seam = word_route.make_word_export(self.store.path, [], USER, today=lambda: TODAY,
                                           choose_folder=lambda prompt: str(self.word_local))
        return seam({"project": "ABC", "to_client": True})

    def names(self, folder):
        return sorted(p.name for p in folder.iterdir())

    def word_text(self, path):
        with zipfile.ZipFile(path) as z:
            return z.read("word/document.xml").decode("utf-8")

    def word_files_holding_the_id(self):
        return [p for folder in (self.word_local, self.client) for p in folder.glob("*.docx")
                if self.hidden_id in self.word_text(p)]

    def test_a_web_publish_to_the_client_refuses_it(self):
        status, got = self.web_publish()
        self.assertEqual((status, got["ok"], got["action"]), (409, False, "refused"), got)
        held = to_client.MESSAGES["held_back"].format(what="text that was meant to be left out")
        self.assertTrue(got["message"].startswith(held), got["message"])
        self.assertIn(self.hidden_id, got["message"], "it names the item to look at")
        self.assertEqual(self.names(self.client), [], NOTHING_WRITTEN)
        self.assertEqual(self.names(self.local), [], "and no Local file either")

    @unittest.expectedFailure       # #607/PR 475 MEDIUM: the Word export has no held-back check yet; remove this mark with the fix (word_route.py, guarded)
    def test_the_word_client_copy_refuses_it(self):
        status, got = self.word_export()
        self.assertNotEqual(status, 200, got)
        self.assertFalse(got.get("ok"), got)
        self.assertEqual(self.names(self.client), [], NOTHING_WRITTEN)
        self.assertEqual(self.word_files_holding_the_id(), [], "no Word file holds the held-back ID")

    def test_what_the_word_client_copy_does_today_is_pinned(self):
        """#607: records what the Word export does today (it saves the copy, ID and all). Delete this test with the fix, when
        test_the_word_client_copy_refuses_it passes and loses its expectedFailure mark."""
        status, got = self.word_export()
        self.assertEqual((status, got["ok"]), (200, True), got)
        self.assertFalse(got["client_failed"])
        (copy,) = self.client.glob("*.docx")
        self.assertEqual(copy.name, got["client_name"])
        text = self.word_text(copy)
        self.assertIn(self.hidden_id, text, "the hidden item's ID is in the client copy")
        self.assertRegex(text, re.escape("Book the review room after " + self.hidden_id))
        self.assertNotIn(HIDDEN_TEXT, text, "the hidden item's own words are not (select() dropped them)")


if __name__ == "__main__":
    unittest.main()
