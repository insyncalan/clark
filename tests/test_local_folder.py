"""Row 852: Settings, Publishing: a Local folder box with Choose folder, saved once (projects.publish_local), built like the client folder.

The route is POST /api/client-folder with two more actions, "choose_local" and "clear_local". A chosen folder is saved as one step
(so /api/undo puts the old one back; the reply carries its apply_id) and the Save window of Publish then opens there. The system's
folder window is never the real one: the Rig's fake dialog answers, and an osascript that does nothing is first on PATH.

Run: python3 dev/run_tests.py test_local_folder
"""
import os
import unittest
from pathlib import Path
from unittest import mock

from test_publish_route import Rig, USER
from clark import publish_flow

M = publish_flow.MESSAGES
NODIALOG = "/tmp/nodialog"


class Base(unittest.TestCase):
    def setUp(self):
        if Path(NODIALOG, "osascript").exists():
            patch = mock.patch.dict(os.environ, {"PATH": NODIALOG + os.pathsep + os.environ.get("PATH", "")})
            patch.start()
            self.addCleanup(patch.stop)
        self.rig = Rig(self, saved=False)
        self.mine = self.rig.root / "My reports"
        self.mine.mkdir()
        with self.rig.store.step("dashboard", USER) as st:      # the plant carries a made-up Local folder; this starts with none
            st.update("projects", "PUB", {"publish_local": None})

    def local(self):
        return self.rig.store.read("projects", ref="PUB")["publish_local"]

    def ask(self, action, **more):
        return self.rig.call("POST", "/api/client-folder", {"project": "PUB", "action": action, **more})


class TheWords(unittest.TestCase):
    def test_the_words(self):
        self.assertEqual((M["local_saved"], M["local_cleared"]), ("Local folder saved", "Local folder cleared"))


class Choosing(Base):
    def test_a_chosen_folder_is_saved_once_with_an_undo(self):
        self.rig.pick = self.mine
        status, got = self.ask("choose_local")
        self.assertEqual((status, got["ok"], got["changed"], got["folder"], got["message"]), (200, True, True, str(self.mine), "Local folder saved"))
        self.assertEqual(got["folder_name"], "My reports")
        self.assertEqual(self.local(), str(self.mine))
        self.assertIsNone(self.rig.store.read("projects", ref="PUB")["publish_client"], "the client folder is not touched")
        self.assertEqual(self.rig.listing(self.mine), [], "nothing is written into it")
        status, back = self.ask("undo_local", apply_id=got["apply_id"])
        self.assertEqual((status, back["ok"], back["folder"]), (200, True, None), back)
        self.assertIsNone(self.local(), "Undo puts the old one back")
        self.assertEqual(self.ask("undo_local", apply_id=got["apply_id"])[0], 409, "a step is undone once")

    def test_undo_takes_only_a_local_folder_step(self):
        self.rig.pick = self.rig.client
        _, got = self.ask("choose")
        self.assertNotIn("apply_id", got)
        with self.rig.store.step("dashboard", USER) as st:
            st.update("projects", "PUB", {"publish_client": None})
            other = st.peek_apply_id()
        self.assertEqual(self.ask("undo_local", apply_id=other)[0], 409)
        self.assertEqual(self.ask("undo_local", apply_id="1")[0], 400)
        self.assertEqual(self.ask("undo_local")[0], 400)

    def test_cancel_and_the_same_folder_change_nothing(self):
        self.rig.pick = None
        self.assertEqual(self.ask("choose_local"), (200, {"ok": True, "changed": False, "folder": None}))
        self.rig.pick = self.mine
        self.ask("choose_local")
        status, got = self.ask("choose_local")
        self.assertEqual((status, got["changed"]), (200, False))
        self.assertNotIn("apply_id", got)

    def test_the_window_starts_at_the_saved_folder(self):
        self.rig.pick = self.mine
        self.ask("choose_local")
        self.ask("choose_local")
        self.assertEqual(self.rig.picks[-1][1], str(self.mine))

    def test_a_pick_that_is_not_a_folder_is_refused(self):
        f = self.rig.root / "a file.txt"
        f.write_text("x", encoding="utf-8")
        self.rig.pick = f
        status, got = self.ask("choose_local")
        self.assertEqual((status, got["ok"], got["message"]), (409, False, M["paste_unknown"]))
        self.assertIsNone(self.local())

    def test_clear(self):
        self.rig.pick = self.mine
        self.ask("choose_local")
        status, got = self.ask("clear_local")
        self.assertEqual((status, got["changed"], got["message"], got["folder"]), (200, True, "Local folder cleared", None))
        self.assertIsNone(self.local())
        self.assertEqual(self.ask("clear_local")[1]["changed"], False)

    def test_no_pasted_path_for_the_local_folder(self):
        status, got = self.ask("choose_local", value=str(self.mine))
        self.assertEqual((status, got["code"]), (400, "bad_action"))
        self.assertIsNone(self.local())

    def test_the_client_folder_is_as_it_was(self):
        self.rig.pick = self.rig.client
        status, got = self.ask("choose")
        self.assertEqual((status, got["changed"], got["message"]), (200, True, M["folder_saved"]))
        self.assertIsNone(self.local())


class Publishing(Base):
    def test_the_save_window_opens_in_the_saved_folder(self):
        self.rig.pick = self.mine
        self.ask("choose_local")
        status, got = self.rig.publish()
        self.assertEqual(status, 200, got)
        self.assertEqual(self.rig.saves[-1][2], str(self.mine))

    def test_a_saved_folder_that_is_gone_falls_back_to_where_it_was_last_saved(self):
        self.rig.publish()
        self.rig.pick = self.mine
        self.ask("choose_local")
        self.mine.rmdir()
        self.rig.publish()
        self.assertEqual(self.rig.saves[-1][2], str(self.rig.local))

    def test_with_none_saved_it_is_as_before(self):
        self.rig.publish()
        self.assertIsNone(self.rig.saves[0][2])


if __name__ == "__main__":
    unittest.main()
