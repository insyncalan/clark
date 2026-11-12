"""Row 1111: in a published file a client who opens a use case sees the editor's use case page, read only: the status and counts, Where it
stands, the Work items card (a click opens the read only peek), the Milestones card; no editing control and no History.

Run: python3 dev/run_tests.py test_publish_uc_page
Same plant and file as test_publish_usecases. Laptop widths only: 1400 and 900 px.
"""
import tempfile
import unittest
from pathlib import Path

from test_publish import chrome, opened, wait
from test_publish_usecases import made
import test_server  # noqa: F401  (this file drives Chrome: it is in the browser tier)


def js(cdp, sid, code):
    return cdp.js(code, sid)


class TheFilesUseCasePage(unittest.TestCase):
    def test_a_client_opens_the_page_and_sees_it_read_only(self):
        plant, pub, text = made()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "r.html"
            path.write_text(text, encoding="utf-8")
            for width in (1400, 900):
                with self.subTest(width=width), chrome() as cdp:
                    sid = opened(cdp, path.as_uri())
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1000, "deviceScaleFactor": 1, "mobile": False}, sid)
                    self.assertTrue(wait(lambda: js(cdp, sid, "document.documentElement.dataset.ready") == "1"))
                    js(cdp, sid, "document.querySelector('[data-view=usecases]').click()")
                    self.assertTrue(wait(lambda: js(cdp, sid, "!!document.querySelector('[data-uc-page]')")))
                    js(cdp, sid, "document.querySelector('.ucp summary').click()")
                    js(cdp, sid, "document.querySelector('[data-uc-page]').click()")
                    self.assertTrue(wait(lambda: js(cdp, sid, "!!document.querySelector('[data-ucf]')")), "the use case page opened")
                    page = js(cdp, sid, "document.querySelector('[data-ucf]').innerText")
                    for word in ("ZQ-KEEP-USECASE-1", "ZQ-KEEP-STANDING", "ZQ-KEEP-MILESTONE-1"):
                        self.assertIn(word, page)
                    # the card headings are read from the headings themselves, so the same words elsewhere on the page do not satisfy this
                    heads = js(cdp, sid, "[...document.querySelectorAll('[data-ucf] .ucf-ch')].map(e => e.firstChild.textContent.trim().toUpperCase())")
                    self.assertEqual(heads, ["WHERE IT STANDS", "WORK ITEMS", "DETAILS", "MILESTONES"])
                    # and the cards are drawn: the file has its own rules for them (an unstyled page has no border, no grid)
                    look = js(cdp, sid, "(() => { const c = getComputedStyle(document.querySelector('[data-ucf] .ucf-card')); const g = getComputedStyle(document.querySelector('[data-ucf] .ucf-grid')); return [c.borderTopWidth, g.display, g.gridTemplateColumns.split(' ').length]; })()")
                    self.assertEqual(look, ["1px", "grid", 2 if width == 1400 else 1], "a bordered card; two columns at 1400, one at 900 (the 1100 px rule)")
                    self.assertEqual(js(cdp, sid, "document.querySelectorAll('[data-archive], [data-eye], .ucf-acts, [contenteditable=true], textarea, input').length"), 0, "no editing control")
                    # row 1111: the Details card is read only and holds only what the file carries (status, and commitment when set), never an owner or a last change
                    uc = pub["data"]["use_cases"][0]
                    det = js(cdp, sid, "(() => { const c = document.querySelector('[data-ucf-details]'); return c ? {labels: [...c.querySelectorAll('dt')].map(e => e.textContent), text: c.innerText, controls: c.querySelectorAll('input, textarea, select, button, a, [contenteditable=true]').length} : null; })()")
                    self.assertIsNotNone(det, "a Details card")
                    self.assertEqual(det["labels"], ["Status"] + (["Commitment"] if uc.get("commitment") else []))
                    self.assertIn(uc["status"], det["text"])
                    self.assertEqual(det["controls"], 0, "the Details card is read only")
                    for word in ("OWNER", "LAST CHANGE", "DASHBOARD"):
                        self.assertNotIn(word, det["text"].upper(), "a field the file does not carry")
                    self.assertNotIn("HISTORY", page.upper(), "no History in a published file")
                    self.assertNotIn("CHANGE STATUS", page.upper())
                    self.assertEqual(js(cdp, sid, "document.querySelectorAll('[data-item]').length"), 2, "its two shared next steps, as work items")
                    for marker in ("ZQ-OFF-STEP", "ZQ-SENSITIVE-STEP", "ZQ-HIDDEN-USECASE-MILESTONE", "ZQ-USECASE-HISTORY"):
                        self.assertNotIn(marker, page)
                    js(cdp, sid, "document.querySelector('[data-item]').click()")
                    self.assertTrue(wait(lambda: js(cdp, sid, "!!document.querySelector('[data-peek]')")), "the read only peek opened")
                    self.assertEqual(js(cdp, sid, "document.querySelectorAll('[data-peek] textarea, [data-peek] [contenteditable=true]').length"), 0, "the peek is read only")
                    self.assertTrue(js(cdp, sid, "document.documentElement.scrollWidth <= window.innerWidth"))


if __name__ == "__main__":
    unittest.main()
