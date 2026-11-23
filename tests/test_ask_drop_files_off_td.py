"""Tech debt 1506: a file dropped on the ask panel with Files off is cancelled (the browser does not open it), lights nothing and says nothing.

Run: python3 dev/run_tests.py test_ask_drop_files_off_td
With Files on a drop is taken as before (a chip, the highlight on the drag). Widths 1400 and 900. Chrome is required: fails, never skips.
"""
import time
import unittest

import test_ask_files_panel_1294 as P      # the module only: its test classes are not imported to run twice
from test_server import chrome

# dragover then drop of one text file on the panel; returns what the page did with each event
OVER = ("(function(){var dt=new DataTransfer();dt.items.add(new File(['a'],'a.txt',{type:'text/plain'}));window.__dt=dt;"
        "var a=document.querySelector('#ask-panel');var o=new DragEvent('dragover',{dataTransfer:dt,bubbles:true,cancelable:true});a.dispatchEvent(o);return o.defaultPrevented})()")
DROP_IT = ("(function(){var a=document.querySelector('#ask-panel');var d=new DragEvent('drop',{dataTransfer:window.__dt,bubbles:true,cancelable:true});a.dispatchEvent(d);return d.defaultPrevented})()")
LIT = "document.querySelector('#ask-panel').getAttribute('data-drop')"
NOTE = "(document.querySelector('#ask-files-note,.ask-files-note')||{textContent:''}).textContent.trim()"


CHIPS_N, HERE, GONE = P.CHIPS_N, P.HERE, P.GONE


class DropFilesOff(P.Base):      # the Panel helpers without the 1294 tests it carries
    def setUp(self):
        super().setUp()
        self.stub = P.Stub()
        self.s.httpd.ask = self.stub

    open_panel = P.Panel.open_panel


    def drag(self, mode, width):
        with chrome() as cdp:
            p = self.open_panel(cdp, mode, width)
            p.until(GONE if mode == "denied" else HERE, "the panel knows the Files switch")
            over = p.js(OVER)
            time.sleep(0.4)      # the highlight is drawn by the next render
            lit = p.js(LIT)
            dropped = p.js(DROP_IT)
            time.sleep(0.4)
            return {"over": over, "drop": dropped, "lit": lit, "after": p.js(LIT)}, p.js(CHIPS_N), p.js(NOTE)

    def test_a_file_dropped_with_files_off_is_cancelled_and_nothing_is_added(self):
        for w in (1400, 900):
            with self.subTest(width=w):
                r, chips, _ = self.drag("denied", w)
                self.assertTrue(r["over"], "dragover is cancelled, so the drop reaches the panel and the browser does not open the file")
                self.assertTrue(r["drop"], "the drop is cancelled")
                self.assertEqual(chips, 0, "no file chip")

    def test_a_file_dropped_with_files_on_is_taken_as_before(self):
        for w in (1400, 900):
            with self.subTest(width=w):
                r, chips, _ = self.drag("allowed", w)
                self.assertTrue(r["over"] and r["drop"])
                self.assertEqual(r["lit"], "true", "the drop highlight shows on the drag")
                self.assertEqual(chips, 1, "the file becomes a chip")

    def test_no_highlight_and_no_message_with_files_off(self):
        for w in (1400, 900):
            with self.subTest(width=w):
                r, _, note = self.drag("denied", w)
                self.assertIsNone(r["lit"], "no highlight on the drag")
                self.assertIsNone(r["after"])
                self.assertEqual(note, "", "no words appear")


if __name__ == "__main__":
    unittest.main()
