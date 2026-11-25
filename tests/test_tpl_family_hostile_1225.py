"""Row 1225 hostile pass: pins the slice 1 to 3 lines the first tests let through.

A stored Image with caption (store type imagecap, a body of version 1), empty, shows the Gallery starting lines in Edit (the picture slot
and the caption field) and View draws none of them: the Image with caption entry left STARTING_TEXT, so ImageCap.jsx reads the Gallery
one by its id.
Orphans: nothing in the page's own lists (TEMPLATES, SKETCHES, STARTING_TEXT, the Help template table) still names the removed image-caption id.
Run: python3 dev/run_tests.py test_tpl_family_hostile_1225
"""
import json
import unittest

import _tpl_family as F
from _classic_page import classic
from _demo import USER
from _paths import SRC
from _pictures import GOOD
from test_report_editor import Base, tearDownModule  # noqa: F401
from test_server import chrome

PAGE_SRC = SRC / "clark" / "page" / "src"
SLOT = "(function(s){var r=document.querySelector(s);return r?JSON.stringify([...r.querySelectorAll('.tpl-pic-slot-empty')].map(function(e){return e.textContent})):null})"


class ImageStartingLine(Base):
    def setUp(self):
        super().setUp()
        classic(self)

    def make(self, title):
        with self.store.step("dashboard", USER) as st:
            return st.create("report_sections", {"project": "ABC", "type": "imagecap", "title": title, "sort_order": 999 + len(title)})

    def test_the_empty_picture_slot_and_caption_have_their_lines_in_edit_and_view_has_none(self):
        refs = [self.make("Fictional cap one")]      # a body of version 2 draws its own Full width Edit part, read in FullWidthImageWithAPicture below
        with chrome() as cdp:
            p = self.visit(cdp)
            for width in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                p.edit()
                for ref in refs:
                    sel = f"[data-id={json.dumps(ref)}]"
                    p.until(f"!!document.querySelector({json.dumps(sel)})", "the section is drawn")
                    self.assertEqual(json.loads(p.js(f"{SLOT}({json.dumps(sel)})")), ["Add a picture."], f"{ref} at {width}")
                    html = p.js(f"document.querySelector({json.dumps(sel)}).outerHTML")
                    self.assertIn("Say what the picture shows.", html, f"{ref}: the caption field's starting line at {width}")
                p.view()
            self.assertNotIn("Add a picture.", p.js("document.body.innerText"))


class NoOrphanOfTheRemovedId(unittest.TestCase):
    def test_no_list_names_image_caption(self):
        for name in ("logic/templates.js", "edit/startingText.js"):
            self.assertNotIn("image-caption", (PAGE_SRC / name).read_text(encoding="utf-8"), name)
        help_ = json.loads((PAGE_SRC / "help" / "helpContent.json").read_text(encoding="utf-8"))
        self.assertNotIn("Image with caption", json.dumps(help_), "the Help template table lists no Image with caption row")


class FullWidthImageWithAPicture(F.Family):
    """The family tests reach the id full-image through a body of version 1 (add_all reuses the one imagecap section of its type), so
    the Full width image (version 2, with a picture) is read here: no control in View and its text 4.5 to 1, light and dark."""

    def check(self, width):
        with self.store.step("dashboard", USER) as st:
            ref = st.create("report_sections", {"project": "ABC", "type": "imagecap", "title": "Fictional full", "sort_order": 1999,
                                                "body": json.dumps({"v": 2, "caption": "Fictional caption", "alt": "Fictional plan", "pictures": {"original": GOOD, "image": GOOD}})})
        self.family_refs = {"full-v2": ref}
        for dark in (False, True):
            got = self.read(width, dark, F.READ_JS)
            self.assertEqual(got["view"]["full-v2"]["controls"], [], f"View holds no control (dark={dark})")
            self.assertIn("Fictional caption", got["view"]["full-v2"]["words"])
            low = [t for t in self.read(width, dark, F.CONTRAST_JS, modes=("view",))["view"]["full-v2"] if t["ratio"] < 4.5 or t["image"]]
            self.assertEqual(low, [], f"text 4.5 to 1 (dark={dark})")

    def test_at_1400(self):
        self.check(1400)

    def test_at_900(self):
        self.check(900)


if __name__ == "__main__":
    unittest.main()
