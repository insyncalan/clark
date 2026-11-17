"""Row 1182 (with 1183): a closed risk or issue says "<colour> kept" as the small line of its STATUS chip; the Rating chip has none.
Run: CLARK_CHROME=$CREAITE_CHROME python3 dev/run_tests.py test_peek_status_kept_1182.py   (headless Chrome, set CLARK_CHROME)
"""
import unittest

import test_inline_edits as T
from test_inline_edits import chrome


class StatusKept(unittest.TestCase):
    setUp = T.Live.setUp
    read = T.Live.read
    open_page = T.Live.open_page
    until = T.Live.until

    def peek(self, cdp, sid, ref):
        cdp.js(f"clarkPage.openPeek('{ref}', 'item')", sid)
        self.until(cdp, sid, "!!document.querySelector('#peek .pk-chips')", "the peek drew")

    def sub(self, cdp, sid, row):
        return cdp.js(f"(document.querySelector('#peek .pk-chips [data-row={row}] .pkc-sub') || {{}}).textContent || ''", sid)

    def test_kept_is_on_status_for_closed_risk_and_issue(self):
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400)
            for ref, want in (("TUL-008", "Amber kept"), ("TUL-012", "Red kept")):
                self.peek(cdp, sid, ref)
                self.assertEqual(self.sub(cdp, sid, "status"), want, ref)
                self.assertEqual(self.sub(cdp, sid, "priority"), "", f"{ref}: the Rating chip carries no sub-line")

    def test_an_open_risk_has_no_kept_line(self):
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400)
            self.peek(cdp, sid, "TUL-007")
            self.assertEqual(self.sub(cdp, sid, "status"), "")

    def test_a_made_or_withdrawn_decision_has_no_kept_line(self):
        """Only a risk or an issue keeps its rating. A decision that is Made (TUL-D-013, priority Medium) is closed too and must show no 'kept' line.
        (A closed action cannot kill this: actions draw their own chips.) Killer for: the kind check dropped from the kept line of the Status chip."""
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400)
            for ref in ("TUL-D-013", "TUL-D-014"):
                self.peek(cdp, sid, ref)
                self.assertEqual(self.sub(cdp, sid, "status"), "", ref)

    def test_kept_is_a_red_pill_from_the_tokens(self):
        """Row 1256-A2 (ticket 1d): the 'kept' line is a pill in the red tint with the red text, from the status tokens, at 1400 and 900 wide.
        Killer for: the kept line drawn as plain muted text (no subTone)."""
        probe = ("(() => { const p = document.createElement('i'); p.style.cssText = 'background:var(--status-red-tint);color:var(--status-red-text)';"
                 " document.body.appendChild(p); const c = getComputedStyle(p); const o = [c.backgroundColor, c.color]; p.remove(); return o; })()")
        read = ("(() => { const e = document.querySelector('#peek .pk-chips [data-row=status] .pkc-sub'); const c = getComputedStyle(e);"
                " return [c.backgroundColor, c.color, c.borderTopLeftRadius, c.fontSize, c.fontWeight]; })()")
        with chrome() as cdp:
            for width in (1400, 900):
                sid = self.open_page(cdp, width)
                want = cdp.js(probe, sid)
                for ref in ("TUL-008", "TUL-012"):
                    self.peek(cdp, sid, ref)
                    bg, fg, radius, size, weight = cdp.js(read, sid)
                    self.assertEqual([bg, fg], want, f"{ref} at {width}: red tint and red text from the tokens")
                    self.assertGreaterEqual(float(radius.replace("px", "")), 9, f"{ref} at {width}: a pill (radius 999)")
                    self.assertGreaterEqual(float(size.replace("px", "")), 13, f"{ref} at {width}: 13 px floor")
                    self.assertEqual(weight, "700", f"{ref} at {width}")
                    print(f"MEASURED {width} {ref}: bg={bg} fg={fg} radius={radius} size={size} weight={weight}")


if __name__ == "__main__":
    unittest.main()
