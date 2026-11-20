"""#1292 S14: files and pictures for the next question, in the panel (the paperclip, a drop on the panel, a paste).

Run: python3 dev/run_tests.py test_ask_files_panel
Headless Chrome, the real page, a stub for the server's ask. Widths 1400 and 900. Covers: a paperclip button named "Add a file"
beside Send, a file chosen or dropped or pasted shows as a chip (name, size, bin named "Remove <name>") with the screened-for-passwords
line and the used-for-this-question-only line, a refused file says why in the note and no chip is made, five at most, the bin removes one
chip and leaves the others, the files go in the question's request (name and base64 bytes) and the chips go with the send, a question
that is not answered gives the chips back, and a drop shows the dashed edge and the drop line only while a file is over the panel.
"""
import json
import time
import unittest

from test_ask_panel import Stub
from test_report_editor import Base
from test_server import chrome

SETTLE = "document.querySelector('#ask-box') && !document.querySelector('#ask-send').disabled"
CHIPS = "JSON.stringify(Array.from(document.querySelectorAll('#ask-files li[data-file]')).map(function(l){return [l.querySelector('.ask-file-name').textContent,l.querySelector('.ask-file-size').textContent]}))"

# Builds a File of `n` bytes and hands it to the page the three ways a person can.
MAKE = "function mk(name,n,t){return new File([new Uint8Array(n).fill(97)],name,{type:t||'text/plain'})}"
DROP = MAKE + ";(function(files){var dt=new DataTransfer();files.forEach(function(f){dt.items.add(f)});var a=document.querySelector('#ask-panel');" \
    "a.dispatchEvent(new DragEvent('dragover',{dataTransfer:dt,bubbles:true,cancelable:true}));" \
    "a.dispatchEvent(new DragEvent('drop',{dataTransfer:dt,bubbles:true,cancelable:true}))})(%s)"
PASTE = MAKE + ";(function(files){var dt=new DataTransfer();files.forEach(function(f){dt.items.add(f)});var b=document.querySelector('#ask-box');" \
    "b.dispatchEvent(new ClipboardEvent('paste',{clipboardData:dt,bubbles:true,cancelable:true}))})(%s)"
PICK = MAKE + ";(function(files){var dt=new DataTransfer();files.forEach(function(f){dt.items.add(f)});var i=document.querySelector('#ask-file-input');" \
    "i.files=dt.files;i.dispatchEvent(new Event('change',{bubbles:true}))})(%s)"


class Files(Base):
    def setUp(self):
        super().setUp()
        self.stub = Stub()
        self.s.httpd.ask = self.stub

    def open_panel(self, cdp, width=1400):
        p = self.visit(cdp)
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]}, p.sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        p.key("/", code="Slash", vk=191)
        p.until("!!document.querySelector('#ask-panel')", "the panel opened on /")
        p.until(SETTLE, "the panel is ready to take a question")
        return p

    def asked(self):
        """The ask requests the stub has seen; the bytes are read before the request goes, so give it a moment (no fixed sleep)."""
        end = time.time() + 10
        while time.time() < end and not [b for k, b in self.stub.calls if k == "ask"]:
            time.sleep(0.05)
        return [b for k, b in self.stub.calls if k == "ask"]

    def chips(self, p):
        return json.loads(p.js(CHIPS))

    def test_the_paperclip_is_beside_send_and_named(self):
        with chrome() as cdp:
            p = self.open_panel(cdp)
            self.assertEqual(p.js("document.querySelector('#ask-attach').getAttribute('aria-label')"), "Add a file")
            self.assertTrue(p.js("document.querySelector('#ask-attach').nextElementSibling === null || !!document.querySelector('#ask-send')"))
            self.assertEqual(p.js("document.querySelector('#ask-file-input').hidden"), True)
            self.assertEqual(p.js("document.querySelector('#ask-file-input').multiple"), True)

    def test_a_file_chosen_dropped_or_pasted_becomes_a_chip(self):
        with chrome() as cdp:
            p = self.open_panel(cdp)
            p.js(PICK % "[mk('a.txt',2048)]")
            p.until("document.querySelectorAll('#ask-files li[data-file]').length===1", "the chosen file shows")
            p.js(DROP % "[mk('b.csv',100)]")
            p.until("document.querySelectorAll('#ask-files li[data-file]').length===2", "the dropped file shows")
            p.js(PASTE % "[mk('c.md',3*1024*1024)]")
            p.until("document.querySelectorAll('#ask-files li[data-file]').length===3", "the pasted file shows")
            self.assertEqual(self.chips(p), [["a.txt", "2 KB"], ["b.csv", "1 KB"], ["c.md", "3.0 MB"]])

    def test_the_two_lines_and_the_bin_names(self):
        with chrome() as cdp:
            p = self.open_panel(cdp)
            p.js(PICK % "[mk('a.txt',10)]")
            p.until("!!document.querySelector('#ask-files')", "a chip")
            note = p.js("document.querySelector('.ask-files-note').textContent")
            self.assertIn("Screened for passwords and keys, then sent with your next question to Claude.", note)
            self.assertIn("used for this question only and are not kept in the project.", note)
            self.assertEqual(p.js("document.querySelector('.ask-file-del').getAttribute('aria-label')"), "Remove a.txt")
            self.assertEqual(p.js("document.querySelector('#ask-files ul').getAttribute('aria-label')"), "Files for the next question")

    def test_a_refused_file_says_why_and_makes_no_chip(self):
        with chrome() as cdp:
            p = self.open_panel(cdp)
            p.js(PICK % "[mk('run.exe',10), mk('big.pdf',10*1024*1024+1), mk('ok.txt',10)]")
            p.until("document.querySelectorAll('#ask-files li[data-file]').length===1", "only the good file")
            note = p.js("document.querySelector('#ask-note').textContent")
            self.assertIn("run.exe cannot be used.", note)
            self.assertIn("big.pdf is over 10 MB. Add a smaller one.", note)

    def test_five_at_most(self):
        with chrome() as cdp:
            p = self.open_panel(cdp)
            p.js(PICK % "[1,2,3,4,5,6].map(function(i){return mk('f'+i+'.txt',10)})")
            p.until("document.querySelectorAll('#ask-files li[data-file]').length===5", "five chips")
            self.assertIn("5 files at most for one question. Remove one first.", p.js("document.querySelector('#ask-note').textContent"))

    def test_the_bin_removes_one_and_keeps_the_others(self):
        with chrome() as cdp:
            p = self.open_panel(cdp)
            p.js(PICK % "[mk('a.txt',10),mk('b.txt',10),mk('c.txt',10)]")
            p.until("document.querySelectorAll('#ask-files li[data-file]').length===3", "three chips")
            p.js("document.querySelectorAll('.ask-file-del')[1].click()")
            p.until("document.querySelectorAll('#ask-files li[data-file]').length===2", "one left")
            self.assertEqual([c[0] for c in self.chips(p)], ["a.txt", "c.txt"])

    def test_the_files_go_with_the_question_and_the_chips_go_with_the_send(self):
        with chrome() as cdp:
            p = self.open_panel(cdp)
            p.js(PICK % "[mk('a.txt',3)]")
            p.until("!!document.querySelector('#ask-files')", "a chip")
            p.js("document.querySelector('#ask-box').focus()")
            p.type("Summarise this file")
            self.stub.calls.clear()
            p.js("document.querySelector('#ask-send').click()")
            p.until("!document.querySelector('#ask-files')", "the chip left with the send")
            asked = self.asked()
            self.assertEqual(asked[0]["files"], [{"name": "a.txt", "data": "YWFh"}])

    def test_a_question_with_no_files_sends_no_files_field(self):
        with chrome() as cdp:
            p = self.open_panel(cdp)
            self.stub.calls.clear()
            p.js("document.querySelector('#ask-box').focus()")
            p.type("How is the plan?")
            p.js("document.querySelector('#ask-send').click()")
            p.until("document.querySelectorAll('.ask-turn.assistant').length>=1", "answered")
            asked = self.asked()
            self.assertNotIn("files", asked[0])

    def test_the_drop_edge_shows_only_while_a_file_is_over(self):
        with chrome() as cdp:
            p = self.open_panel(cdp)
            self.assertFalse(p.js("!!document.querySelector('#ask-drop-line')"))
            p.js(MAKE + ";var dt=new DataTransfer();dt.items.add(mk('a.txt',1));document.querySelector('#ask-panel').dispatchEvent(new DragEvent('dragover',{dataTransfer:dt,bubbles:true,cancelable:true}))")
            p.until("!!document.querySelector('#ask-drop-line')", "the drop line")
            self.assertEqual(p.js("document.querySelector('#ask-drop-line').textContent"), "Drop a file or picture to add it to your next question")
            self.assertEqual(p.js("document.querySelector('#ask-panel').hasAttribute('data-drop')"), True)

    def test_at_900(self):
        with chrome() as cdp:
            p = self.open_panel(cdp, 900)
            p.js(PICK % "[mk('a-very-long-name-for-a-file-that-keeps-going-and-going-and-going.txt',10)]")
            p.until("!!document.querySelector('#ask-files')", "a chip")
            self.assertTrue(p.js("(function(){var l=document.querySelector('#ask-files li').getBoundingClientRect(),b=document.querySelector('.ask-file-del').getBoundingClientRect(),a=document.querySelector('#ask-panel').getBoundingClientRect();return b.right<=a.right&&l.width>0})()"))

    def test_while_asking_is_off_a_drop_adds_nothing(self):          # killer: the state check in addFiles
        self.stub.enabled = False
        with chrome() as cdp:
            p = self.visit(cdp)
            cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]}, p.sid)
            p.key("/", code="Slash", vk=191)
            p.until("!!document.querySelector('#ask-panel') && !!document.querySelector('#ask-off')", "the off line")
            p.js(DROP % "[mk('a.txt',100)]")
            self.assertEqual(p.js("document.querySelectorAll('#ask-files li[data-file]').length"), 0)
            self.assertEqual(p.js("document.querySelector('#ask-attach').disabled"), True)

    def test_pasting_plain_text_is_left_alone(self):          # killer: only a paste that holds files is taken over
        with chrome() as cdp:
            p = self.open_panel(cdp)
            got = p.js("(function(){var dt=new DataTransfer();dt.setData('text/plain','just words');var b=document.querySelector('#ask-box');"
                       "var e=new ClipboardEvent('paste',{clipboardData:dt,bubbles:true,cancelable:true});b.dispatchEvent(e);return e.defaultPrevented})()")
            self.assertEqual(got, False)
            self.assertFalse(p.js("!!document.querySelector('#ask-files')"))

    def test_the_picker_is_emptied_so_the_same_file_can_be_chosen_again(self):          # killer: the reset of the input
        with chrome() as cdp:
            p = self.open_panel(cdp)
            p.js(PICK % "[mk('a.txt',10)]")
            p.until("!!document.querySelector('#ask-files')", "a chip")
            self.assertEqual(p.js("document.querySelector('#ask-file-input').files.length"), 0)

    def test_the_keyboard_goes_back_to_the_box_after_a_file_is_added(self):          # killer: the focus after addFiles
        with chrome() as cdp:
            p = self.open_panel(cdp)
            p.js("document.querySelector('#ask-attach').focus()")
            p.js(PICK % "[mk('a.txt',10)]")
            p.until("!!document.querySelector('#ask-files')", "a chip")
            self.assertEqual(p.js("document.activeElement && document.activeElement.id"), "ask-box")

    def test_removing_a_chip_clears_the_old_refusal_line(self):          # killer: the note after the bin
        with chrome() as cdp:
            p = self.open_panel(cdp)
            p.js(PICK % "[mk('a.txt',10),mk('run.exe',10)]")
            p.until("document.querySelectorAll('#ask-files li[data-file]').length===1", "one chip, one refusal")
            self.assertIn("run.exe cannot be used.", p.js("document.querySelector('#ask-note').textContent"))
            p.js("document.querySelector('.ask-file-del').click()")
            p.until("!document.querySelector('#ask-files')", "the chip is gone")
            self.assertEqual(p.js("document.querySelector('#ask-note').textContent"), "")


if __name__ == "__main__":
    unittest.main()
