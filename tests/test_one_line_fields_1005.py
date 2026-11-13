"""Row 1005: the other fields saved as one line of plain text (a picture's caption, the Movement form's Who agreed it, Reason and Source, a RAID
card's Own words) are the one-line editor too: no / menu, no formatting buttons, bubble, Cmd+B, Cmd+I, markdown input rules or pasted blocks,
because what they save is plain words. 1400 and 900. Fictional data only.

Run: python3 dev/run_tests.py test_one_line_fields_1005
"""
import json
import unittest

from _pictures import GOOD
from _pictures_cases import PicturePage
import test_movement_page as tmp
import test_p1005b_eye as eye
from test_report_editor import Base as PageBase
from test_row_words_1005 import plain_only
from test_server import chrome

WIDTHS = (1400, 900)


def widths(p):
    for w in WIDTHS:
        p.cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        yield f"{w}"


class Caption(PicturePage):
    KIND = "imagecap"

    def test_a_caption_is_the_one_line_editor(self):
        ref = self.add({"v": 1, "caption": "Fictional caption", "pictures": {"image": GOOD}})
        with self.chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            view = f"[data-id={json.dumps(ref)}] [data-rich=caption]"
            p.until(f"!!document.querySelector({json.dumps(view)})", "the caption")
            for where in widths(p):
                p.js(f"document.querySelector({json.dumps(view)}).click()")
                p.until("document.activeElement.classList.contains('ProseMirror')", "opened with the focus in it")
                plain_only(self, p, f"caption {where}")
                p.key("Escape", code="Escape", vk=27)
                p.until(f"!document.querySelector('[data-id={json.dumps(ref)}] .ProseMirror')", "closed")


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


class Own(PageBase):
    seed, stored, wait_for, open_editor = (eye.Raid.__dict__[k] for k in ("seed", "stored", "wait_for", "open_editor"))

    def test_own_words_is_the_one_line_editor(self):
        self.seed("Old words")
        with chrome() as cdp:
            p, view, box = self.open_editor(cdp)
            for where in widths(p):
                p.js(f"document.querySelector({json.dumps(view)}).click()")
                p.until(f"document.activeElement === document.querySelector({json.dumps(box)})", "opened")
                plain_only(self, p, f"own words {where}")
                p.key("Escape", code="Escape", vk=27)
                p.until(f"!document.querySelector({json.dumps(box)})", "closed")


if __name__ == "__main__":
    unittest.main()
