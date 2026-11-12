"""#437: the Publish words that follow the prototype (system/prototype/io.js), without a browser.

Rows 29 and 56: the warning's second sentence, built once. Rows 27 and 57: the finished state (a tick and "Published (Publication N)"
on the button, then the dialog closes by itself and a note says what was done, with no Undo). The page's own behaviour is read in
a browser in tests/test_publish_dialog.py (class Finished); here the source of the words and the timing is pinned.

Run: python3 dev/run_tests.py test_publish_words
"""
import re
import unittest

from _paths import SRC
from clark import page, to_client

PAGE_SRC = SRC / "clark" / "page" / "src"
PROTOTYPE = (SRC.parent / "system" / "prototype" / "io.js").read_text(encoding="utf-8")
SECOND = "Only what is shown in View mode is included."
WARNING = "The client will see this page. " + SECOND


def src(name):
    return (PAGE_SRC / name).read_text(encoding="utf-8")


class TheWarning(unittest.TestCase):
    def test_the_prototype_says_it_this_way(self):
        self.assertIn(f'id="pubWarn" style="font-size:13px;margin:10px 0 0" hidden>{WARNING}</p>', PROTOTYPE)

    def test_the_dialog_model_and_the_page_say_both_sentences(self):
        self.assertEqual(to_client.MESSAGES["client_sees"], WARNING)
        jsx = src("edit/Publish.jsx")
        # the warning is one sentence, with the Word report named when it is ticked; each ends with the second sentence
        self.assertIn(f'"{WARNING}"', jsx)
        self.assertIn(f'"The client will see this page and the Word report. {SECOND}"', jsx)
        self.assertEqual(jsx.count(SECOND), 2, "the second sentence ends each of the two variants")
        self.assertNotIn("this page and the PDF", jsx, "item 438: the browser makes the PDF, so none goes to the client folder")
        self.assertIn('s.phase !== "clash" && s.phase !== "wordclash" && s.ticked', jsx, "the warning is hidden while either question is asked")
        # row 1: which sentence goes with which state, not just that both exist (swapping the branches kept every string above)
        self.assertRegex(jsx, r'\{s\.word \? "The client will see this page and the Word report\. [^"]*" : "The client will see this page\. ')
        ticked = to_client.dialog_step(to_client.new_dialog_state("/x/Harbour Bridge"), "tick", True)
        self.assertEqual(to_client.to_client_dialog(ticked)["line"], WARNING)
        # and the line goes again when the tick does
        unticked = to_client.dialog_step(ticked, "tick", False)
        self.assertIsNone(to_client.to_client_dialog(unticked)["line"])

    def test_a_published_file_carries_no_dialog_words(self):
        self.assertNotIn(SECOND, page.VIEW_PAGE.read_text(encoding="utf-8"))


class TheFinishedState(unittest.TestCase):
    def test_the_prototype_closes_after_1200_ms_with_no_undo_on_the_toast(self):
        self.assertIn("Published (Publication ${n})`", PROTOTYPE)
        self.assertIn("setTimeout(() => { if (d.open && form.isConnected) d.close(); }, 1200)", PROTOTYPE)
        self.assertIn("no Undo on the toast", PROTOTYPE)

    def test_the_page_waits_the_same_and_closes_only_its_own_dialog(self):
        state = src("edit/publishState.js")
        self.assertIn("export const CLOSE_MS = 1200;", state)
        self.assertRegex(state, r"mine === finished && now && now\.phase === \"done\"\) close\(\)", "a late timer never closes a later dialog")
        self.assertRegex(state, r"close\(\); \}, Math\.max\(0, closeAfter\.ms\)\);", "the timer waits exactly closeAfter.ms, no more")
        self.assertRegex(state, r"closeAfter = \{ ms: CLOSE_MS \}", "and closeAfter starts at CLOSE_MS")

    def test_the_note_is_the_menus_and_has_no_undo(self):
        state, note = src("edit/publishState.js"), src("edit/menuNote.js")
        self.assertIn('import { say } from "./menuNote.js";', state)
        self.assertRegex(state, r'say\(message\.kind === "error" \? "problem" : message\.kind === "info" \? "note" : "done", message\.text\)')
        self.assertRegex(state, r'finish\(\{ kind: s\.pdf && !printed \? "info" : "success", text', "the web page's end")
        self.assertEqual(len(re.findall(r"finish\(\{ kind:", state)), 4, "the web page and the three ends of the Word step all finish the same way")
        self.assertRegex(note, r"export function say\(kind, text\)", "the menu's note takes no Undo")
        self.assertNotIn("undo", re.sub(r"//.*", "", note).lower())

    def test_only_the_test_build_holds_the_dialog_open(self):
        hook = src("testhook.js")
        self.assertIn("closeAfter.ms = null;", hook)
        self.assertNotIn("testhook", src("main.jsx"), "the served page never installs the hook")
        for built in (page.PAGE, page.VIEW_PAGE):
            self.assertNotIn("publishCloseMs", built.read_text(encoding="utf-8"), built.name)


if __name__ == "__main__":
    unittest.main()
