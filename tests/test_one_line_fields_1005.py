"""Row 1005: the Movement form's Who agreed it, Reason and Source (saved as one line of plain text) are the one-line editor: no / menu, no
formatting buttons, bubble, Cmd+B, Cmd+I, markdown input rules or pasted blocks, because what they save is plain words. 1400 and 900.
(Row 1288: a picture's caption and a RAID card's Own words moved to the Full editor: tests/test_rich_storage_1288c_page.py.) Fictional data only.

Run: python3 dev/run_tests.py test_one_line_fields_1005
"""
import json
import unittest

from _pictures import GOOD
from _pictures_cases import PicturePage
import test_movement_page as tmp
import test_p1005b_eye as eye
from test_row_words_1005 import plain_only
from test_server import chrome

WIDTHS = (1400, 900)


def widths(p):
    for w in WIDTHS:
        p.cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        yield f"{w}"


class Caption(PicturePage):
    KIND = "imagecap"
    HTML = "<p>Fine <strong>words</strong></p><p>second line</p>"

    def stored(self, ref):
        return self.body(ref).get("caption", "")

    def wait_for(self, fn, seconds=10):
        import time
        end = time.time() + seconds
        while time.time() < end:
            if fn():
                return True
            time.sleep(0.1)
        return False

    def test_a_caption_is_the_full_editor_and_saves_its_html(self):
        """Row 1288: a caption is the Full editor; an older plain caption is shown as the same words and left alone; Ctrl+B and the toolbar are
        there; what is saved is the editor's HTML and one Undo puts the older caption back."""
        ref = self.add({"v": 1, "caption": "Fictional caption", "pictures": {"image": GOOD}})
        with self.chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            view = f"[data-id={json.dumps(ref)}] [data-rich=caption]"
            p.until(f"!!document.querySelector({json.dumps(view)})", "the caption")
            for where in widths(p):
                p.js(f"document.querySelector({json.dumps(view)}).click()")
                p.until("document.activeElement.classList.contains('ProseMirror')", "opened with the focus in it")
                self.assertEqual(p.js("document.activeElement.innerText.trim()"), "Fictional caption", f"{where}: shown as the same words")
                self.assertTrue(p.js("!!document.querySelector('.rt-bar [aria-label=\"Bold\"]')"), f"{where}: the Full toolbar")
                p.key("Escape", code="Escape", vk=27)
                p.until(f"!document.querySelector('[data-id={json.dumps(ref)}] .ProseMirror')", "closed")
                self.assertEqual(self.stored(ref), "Fictional caption", f"{where}: opening and leaving it changes nothing")
            p.js(f"document.querySelector({json.dumps(view)}).click()")
            p.until("document.activeElement.classList.contains('ProseMirror')", "opened")
            p.js(f"document.activeElement.cxed.editor.commands.setContent({json.dumps(self.HTML)})")
            p.key("Enter", modifiers=2, code="Enter", vk=13)
            self.assertTrue(self.wait_for(lambda: self.stored(ref) == self.HTML), "saved as the editor's HTML")
            p.until("!!document.querySelector('.toast [data-undo]')", "the Undo is offered")
            p.js("document.querySelector('.toast [data-undo]').click()")
            self.assertTrue(self.wait_for(lambda: self.stored(ref) == "Fictional caption"), "one Undo puts the older caption back")


class Move(tmp.Base):
    form, box = (eye.Movement.__dict__[k] for k in ("form", "box"))

    def test_who_reason_and_source_are_the_one_line_editor(self):
        with chrome() as cdp:
            p = self.form(cdp)
            for where in widths(p):
                for k in ("who", "reason", "source"):
                    p.js("document.getElementById('mv-%s').click()" % k)
                    p.until("!!document.querySelector(%s)" % json.dumps(self.box(k)), f"{k} opened")
                    p.js("document.querySelector(%s).focus()" % json.dumps(self.box(k)))
                    p.until("document.activeElement === document.querySelector(%s)" % json.dumps(self.box(k)), f"{k} has the focus")
                    plain_only(self, p, f"{k} {where}")
                    p.key("Escape", code="Escape", vk=27)
                    p.until("!document.querySelector(%s)" % json.dumps(self.box(k)), f"{k} closed")
                    p.until("document.activeElement.id === 'mv-%s'" % k, f"the focus is back on {k}")


class HelpSaysSo(unittest.TestCase):
    def test_the_editor_controls_table_names_the_one_line_fields(self):
        from pathlib import Path
        text = (Path(__file__).resolve().parent.parent / "src" / "clark" / "page" / "src" / "help" / "helpContent.json").read_text(encoding="utf-8")
        self.assertIn("One-line fields (the Client wording on a row, picture captions, Movement words and the Own words of risks and issues) "
                      "have no / menu and no formatting buttons. Enter or a click away saves.", text)


if __name__ == "__main__":
    unittest.main()
