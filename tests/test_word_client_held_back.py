"""#607 (PR 475 MEDIUM). Case a: a client-visible action whose own text names the ID of an action that is hidden from the client. The ID
is on the web publish's held-back list (publish_flow.markers_for lists the ID of every row that select() left out), so a web
publish with To client ticked refuses it ("Nothing was published. The report has something in it that must not go to the
client ..."). The Word export (word_route._do_export) builds from the same select(); it now runs the same held-back check on
the file's own text (word_route._held_back, with the same markers) before it writes either copy, and refuses in the same words.

Case b: a risk whose working note (response_action, one of publish_flow.NOTE_FIELDS) is also pasted into its client-visible
description; markers_for lists every row's note, so the web publish and the Word export both refuse.
Not here, because the web publish does not refuse them either (no assertion it would fail): case c, the main text of a left-out
row pasted into a client-visible row (it is then part of kept text, so it is not a marker), and case d, a hidden report section's
body quoted in a visible row or section (markers_for reads no hidden section). In both the Word copy carries the text as the web
file does.

Fictional data only: the demo store's project ABC, a few rows, a client folder and Local folders in a temporary folder.
Run: python3 dev/run_tests.py test_word_client_held_back
"""
import re
import shutil
import sqlite3
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

NOTE_TEXT = "Supplier may walk away in March"


class Setup:
    """The demo store, a client folder and two Local folders, and the web publish and Word export calls. A case sets plant()."""

    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store
        self.tmp = Path(tempfile.mkdtemp(prefix="clark-held-back-")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.local, self.word_local, self.client = self.tmp / "Local", self.tmp / "WordLocal", self.tmp / "Client"
        for folder in (self.local, self.word_local, self.client):
            folder.mkdir()
        self.plant()
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


class Cases(Setup):
    """The checks for one planted case. A case sets: plant() (the rows), leak (text that must not reach a client file),
    look_at (the ID the web refusal names), visible (the client-visible sentence the Word copy holds) and absent (texts that
    select() already drops, so the Word copy does not hold them)."""
    absent = ()

    def word_files_holding_the_leak(self):
        return [p for folder in (self.word_local, self.client) for p in folder.glob("*.docx")
                if self.leak in self.word_text(p)]

    def test_a_web_publish_to_the_client_refuses_it(self):
        status, got = self.web_publish()
        self.assertEqual((status, got["ok"], got["action"]), (409, False, "refused"), got)
        held = to_client.MESSAGES["held_back"].format(what="text that was meant to be left out")
        self.assertTrue(got["message"].startswith(held), got["message"])
        self.assertIn(self.look_at, got["message"], "it names the item to look at")
        self.assertEqual(self.names(self.client), [], NOTHING_WRITTEN)
        self.assertEqual(self.names(self.local), [], "and no Local file either")

    def test_the_word_client_copy_refuses_it(self):
        status, got = self.word_export()
        self.assertEqual((status, got["ok"], got["code"]), (409, False, "refused"), got)
        held = to_client.MESSAGES["held_back"].format(what="text that was meant to be left out")
        self.assertTrue(got["message"].startswith(held), got["message"])
        self.assertTrue(got["message"].endswith(" Nothing was saved."), got["message"])
        self.assertEqual(self.names(self.client), [], NOTHING_WRITTEN)
        self.assertEqual(self.word_files_holding_the_leak(), [], "no Word file holds the held-back text")

    def test_the_word_refusal_names_the_item_to_look_at_as_the_web_publish_does(self):
        _, web = self.web_publish()
        _, word = self.word_export()
        look = publish_flow.MESSAGES["look_at"].format(items=self.look_at)
        self.assertIn(look, web["message"])
        self.assertIn(look, word["message"])

    def test_the_refusal_writes_nothing_in_either_folder(self):
        self.word_export()
        self.assertEqual(self.names(self.word_local), [], "no Local file either, as the web publish writes nothing")
        self.assertEqual(self.names(self.client), [])
        with sqlite3.connect(self.store.path) as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM publications").fetchone()[0], 0, "and no publication is recorded")

    def test_with_to_client_off_the_same_data_still_saves_the_local_file(self):
        seam = word_route.make_word_export(self.store.path, [], USER, today=lambda: TODAY,
                                           choose_folder=lambda prompt: str(self.word_local))
        status, got = seam({"project": "ABC", "to_client": False})
        self.assertEqual((status, got["ok"]), (200, True), got)
        self.assertEqual(self.names(self.word_local), [got["name"]])
        self.assertEqual(self.names(self.client), [], "the check is for the client copy; Local is as before")


class HiddenId(Cases, unittest.TestCase):
    """Case a: a visible action names the ID of an action hidden from the client; markers_for always lists a left-out row's ID."""
    leak, absent = None, (HIDDEN_TEXT,)

    def plant(self):
        self.demo.action(description=HIDDEN_TEXT, client_visible=0)            # left out of every client file
        (hidden,) = [r for r in self.store.read("actions", "ABC") if r["description"] == HIDDEN_TEXT]
        self.leak = self.look_at = hidden["id"]
        self.visible = f"Book the review room after {self.leak} is settled"
        self.demo.action(description=self.visible, client_visible=1)


class NotePastedIntoText(Cases, unittest.TestCase):
    """Case b: a visible risk whose working note is also pasted into its own client-visible description."""
    leak, absent = NOTE_TEXT, ()

    def plant(self):
        self.visible = f"Watch this: {NOTE_TEXT}"
        with self.store.step("dashboard", USER) as st:
            st.create("raid", {"project": "ABC", "type": "Risk", "description": self.visible, "response_action": NOTE_TEXT,
                                     "client_visible": 1, "raised": "2026-10-01", "source": "demo"})
        (risk,) = self.store.read("raid", "ABC")
        self.look_at = risk["id"]


class CleanReport(Setup, unittest.TestCase):
    """A clean report with a client-visible document and a current state (rich text) that links to it still saves in both folders: the
    check refuses leaks, not a legitimate link (its address is the document's own, which is part of what is published)."""
    LINK = "https://example.org/plan"

    def plant(self):
        self.visible = "See the plan"
        with self.store.step("dashboard", USER) as st:
            st.create("documents", {"project": "ABC", "title": "Delivery plan", "kind": "Plan", "url": self.LINK, "sort_order": 1})
        self.demo.update("projects", "ABC", {"current_state": f'<p>{self.visible}: <a href="{self.LINK}">the delivery plan</a></p>'})

    def test_the_word_copy_saves_in_both_folders_with_its_link(self):
        status, got = self.word_export()
        self.assertEqual((status, got["ok"], got["client_failed"]), (200, True, False), got)
        self.assertEqual(self.names(self.word_local), [got["name"]])
        self.assertEqual(self.names(self.client), [got["client_name"]])
        with zipfile.ZipFile(self.client / got["client_name"]) as z:
            self.assertIn(self.LINK, z.read("word/_rels/document.xml.rels").decode("utf-8"), "the legitimate link is in the copy")
            self.assertIn(self.visible, z.read("word/document.xml").decode("utf-8"))

    def test_the_text_the_check_reads_holds_the_words_and_the_link_targets_but_no_markup(self):
        self.word_export()
        (copy,) = self.client.glob("*.docx")
        text = word_route._file_text(copy.read_bytes()).decode("utf-8")
        self.assertIn(self.visible, text)
        self.assertIn(self.LINK, text, "a hyperlink's address is in a relationship, not in the text")
        self.assertNotIn("<w:", text)


# Not covered here, and not refused by either path today (the web publish does not refuse them either): case c, a left-out row's
# main text pasted into a client-visible row (it is then kept text, so it is not a marker: by design in markers_for), and case d,
# a hidden report section's text quoted in a visible row (markers_for reads no hidden section). For the Head to decide separately.


if __name__ == "__main__":
    unittest.main()
