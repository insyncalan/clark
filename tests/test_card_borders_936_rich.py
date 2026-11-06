"""#936, the rich text field: a quote inside the field being edited has no coloured or grey side stripe; it is a quiet panel in
italics, as the prototype draws .prose blockquote. Edit only: the published page has no rich text field.

Run: python3 dev/run_tests.py test_card_borders_936_rich
Needs Chrome (the #33 harness). Fictional data only. Laptop widths 1400 and 900 px, light and dark.
"""
import json
import unittest

import _rich_page as rp
import build_page
from test_server import chrome

READ = """(() => { const e = document.querySelector('.rt-host .ProseMirror blockquote'), c = getComputedStyle(e);
  return {left: c.borderLeftWidth, bg: c.backgroundColor, style: c.fontStyle, active: document.getAnimations().length}; })()"""


class Field(unittest.TestCase):
    def test_a_quote_in_the_field_has_no_side_stripe(self):
        with rp.Harness(chrome) as h:
            css = build_page.EDIT_CSS.read_text(encoding="utf-8")
            h.ev("(() => { const s = document.createElement('style'); s.textContent = %s; document.head.append(s); })()" % json.dumps(css))
            for width in (1400, 900):
                for theme in ("light", "dark"):
                    h.resize(width)
                    h.theme(theme)
                    h.mount("<blockquote><p>Fictional words.</p></blockquote>")
                    self.assertTrue(h.until("document.getAnimations().length === 0 && !!document.querySelector('.rt-host .ProseMirror blockquote')"))
                    got = h.ev(READ)
                    self.assertEqual(got["left"], "0px", (width, theme))
                    self.assertNotEqual(got["bg"], "rgba(0, 0, 0, 0)", (width, theme))
                    self.assertEqual(got["style"], "italic")


if __name__ == "__main__":
    unittest.main()
