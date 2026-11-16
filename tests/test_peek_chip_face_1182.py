"""Row 1182: the chip face of an OPEN risk or issue is its colour word with the level as a small pill ("Red" + "High"), as in the design
image; the icon keeps the level's tone. A closed one keeps its old face. Run: CLARK_CHROME=$CREAITE_CHROME python3 dev/run_tests.py test_peek_chip_face_1182.py
Measured in headless Chrome (CLARK_CHROME) at 1400 and 900 px with the demo data (fictional).
"""
import unittest

import test_inline_edits as T
from test_inline_edits import chrome

FACE = """(() => { const c = document.querySelector('#peek .pk-chips [data-row=priority]'); if (!c) return null;
  const v = c.querySelector('.pkc-v'), s = c.querySelector('.pkc-sub'), ic = c.querySelector('.pkc-ic');
  return { v: v && v.textContent.trim(), sub: s && s.textContent.trim(), subCls: s ? s.className : '', pill: s ? getComputedStyle(s).borderTopLeftRadius : '', ic: ic ? ic.className : '' }; })()"""


class ChipFace(unittest.TestCase):
    setUp = T.Live.setUp
    read = T.Live.read
    row = T.Live.row
    steps = T.Live.steps
    open_page = T.Live.open_page
    until = T.Live.until

    def face(self, cdp, sid, ref):
        cdp.js(f"clarkPage.openPeek('{ref}', 'item')", sid)
        self.until(cdp, sid, f"document.querySelector('#peek').dataset.peek === '{ref}' && !!document.querySelector('#peek .pk-chips [data-row=priority] .pkc-v')", "the peek drew")
        return cdp.js(FACE, sid)

    def test_an_open_risk_and_issue_show_the_colour_with_a_level_pill(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.open_page(cdp, width)
                for ref, level in (("TUL-007", "High"), ("TUL-010", None)):
                    got = self.face(cdp, sid, ref)
                    self.assertIn(got["v"], ("Red", "Amber", "Green"), ref)
                    self.assertIn("lvl", got["subCls"], ref)
                    self.assertIn(got["sub"], ("Urgent", "High", "Medium", "Low"), ref)
                    self.assertNotEqual(got["pill"], "0px", f"{ref}: the level is a pill")
                    if level:
                        self.assertEqual((got["v"], got["sub"]), ("Red", level))

    def test_a_closed_risk_keeps_its_old_face(self):
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400)
            got = self.face(cdp, sid, "TUL-008")
            self.assertEqual(got["sub"] or "", "", "a closed risk's Rating chip has no small line: its colour kept is on the Status chip")
            kept = cdp.js("(() => { const s = document.querySelector('#peek .pk-chips [data-row=status] .pkc-sub'); return s ? s.textContent.trim() : ''; })()", sid)
            self.assertRegex(kept, r"kept$")


if __name__ == "__main__":
    unittest.main()
