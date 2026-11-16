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


if __name__ == "__main__":
    unittest.main()
