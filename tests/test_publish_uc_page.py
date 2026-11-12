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


# anything in the peek that takes input, or a button that is not one of the peek's own step, width and close controls
PEEK_RO = ("[...document.querySelectorAll('[data-peek] *')].filter(e => e.matches('input, textarea, select, [contenteditable]:not([contenteditable=false]), [role=textbox], [role=combobox]')"
           " || (e.matches('button, [role=button]') && !e.matches('[data-pk-prev], [data-pk-next], [data-pk-wide], [data-pk-close]'))).length")


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
                    heads = js(cdp, sid, "[...document.querySelectorAll('[data-ucf] .ucf-ch')].map(e => (e.firstElementChild || e).textContent.trim())")
                    self.assertEqual(heads, ["Where it stands", "Work items", "Milestones"], "the real words, not the uppercased look")
                    # and the cards are drawn: the file has its own rules for them (an unstyled page has no border, no grid)
                    look = js(cdp, sid, "(() => { const c = getComputedStyle(document.querySelector('[data-ucf] .ucf-card')); const g = getComputedStyle(document.querySelector('[data-ucf] .ucf-grid')); return [c.borderTopWidth, g.display, g.gridTemplateColumns.split(' ').length]; })()")
                    self.assertEqual(look, ["1px", "grid", 2 if width == 1400 else 1], "a bordered card; two columns at 1400, one at 900 (the 1100 px rule)")
                    self.assertEqual(js(cdp, sid, "document.querySelectorAll('[data-archive], [data-eye], .ucf-acts, [contenteditable]:not([contenteditable=false]), textarea, input, select').length"), 0, "no editing control")
                    # every button on the file is one of the navigation openers: a work item tile, a milestone name, the open-all link
                    loose = js(cdp, sid, "[...document.querySelectorAll('[data-ucf] button, [data-ucf] [role=button], [data-ucf] [role=textbox], [data-ucf] [role=combobox]')].filter(b => !b.matches('[data-item], [data-ms-open], [data-open-all]')).length")
                    self.assertEqual(loose, 0, "no button on the file other than the tiles, the milestone names and open-all")
                    self.assertNotIn("HISTORY", page.upper(), "no History in a published file")
                    self.assertNotIn("CHANGE STATUS", page.upper())
                    self.assertEqual(js(cdp, sid, "document.querySelectorAll('[data-item]').length"), 2, "its two shared next steps, as work items")
                    for marker in ("ZQ-OFF-STEP", "ZQ-SENSITIVE-STEP", "ZQ-HIDDEN-USECASE-MILESTONE", "ZQ-USECASE-HISTORY"):
                        self.assertNotIn(marker, page)
                    want = js(cdp, sid, "document.querySelector('[data-item]').dataset.item")
                    js(cdp, sid, "document.querySelector('[data-item]').click()")
                    self.assertTrue(wait(lambda: js(cdp, sid, "!!document.querySelector('[data-peek]')")), "the read only peek opened")
                    self.assertEqual(js(cdp, sid, "document.querySelector('[data-peek]').dataset.peek"), want, "the peek is the clicked item")
                    self.assertEqual(js(cdp, sid, PEEK_RO), 0, "the peek is read only")
                    js(cdp, sid, "document.querySelector('[data-pk-close]').click()")
                    self.assertTrue(wait(lambda: js(cdp, sid, "!document.querySelector('[data-peek]')")), "the peek closed")
                    wantms = js(cdp, sid, "document.querySelector('[data-ucf] [data-ms-open]').dataset.msOpen")
                    js(cdp, sid, "document.querySelector('[data-ucf] [data-ms-open]').click()")
                    self.assertTrue(wait(lambda: js(cdp, sid, "!!document.querySelector('[data-peek]')")), "a milestone opened its peek")
                    self.assertEqual(js(cdp, sid, "document.querySelector('[data-peek]').dataset.peek"), wantms, "the peek is the clicked milestone")
                    self.assertTrue(js(cdp, sid, "!!document.querySelector('#peek [data-ms-head]')"), "it is the milestone peek")
                    self.assertEqual(js(cdp, sid, PEEK_RO), 0, "the milestone peek is read only")
                    self.assertTrue(js(cdp, sid, "document.documentElement.scrollWidth <= window.innerWidth"))


if __name__ == "__main__":
    unittest.main()
