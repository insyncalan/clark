"""Row 1111: in a published file a client who opens a use case sees the editor's use case page, read only: the status and counts, Where it
stands, the Work items card (a click opens the read only peek), the Milestones card; no editing control and no History.

Run: python3 dev/run_tests.py test_publish_uc_page
Same plant and file as test_publish_usecases. Laptop widths only: 1400 and 900 px.
"""
import tempfile
import unittest
from pathlib import Path

import copy

from test_publish import chrome, opened, wait
from test_publish_usecases import made, planted
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


def plant_two(plant):
    """The usual plant, plus a use case with nothing in it (1.6) and one with 500 shared work items (1.7)."""
    planted(plant)
    d = plant["data"]
    for id_, ref in (("PUB-U-006", "1.6"), ("PUB-U-007", "1.7")):
        row = copy.deepcopy(d["use_cases"][0])
        row.update(id=id_, ref=ref, title="ZQ-EMPTY-ONE" if ref == "1.6" else "ZQ-BIG-ONE", headline="", standing="", sort_order=int(ref[-1]))
        d["use_cases"].append(row)
    for n in range(500):
        row = copy.deepcopy(d["actions"][0])
        row.update(id=f"PUB-A-9{n:03d}", description=f"ZQ-BULK {n} " + "a long line that goes on " * 6, client_message=None, use_case="PUB-U-007", milestone=None, status="Open")
        d["actions"].append(row)


class TheFilesUseCasePageOnTheEdges(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plant, cls.pub, text = made(plant_two)
        cls.dir = tempfile.TemporaryDirectory()
        cls.path = Path(cls.dir.name) / "r.html"
        cls.path.write_text(text, encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def each_width(self, check):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = opened(cdp, self.path.as_uri())
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1000, "deviceScaleFactor": 1, "mobile": False}, sid)
                self.assertTrue(wait(lambda: js(cdp, sid, "document.documentElement.dataset.ready") == "1"))
                check(cdp, sid, width)

    def at(self, cdp, sid, uc):
        js(cdp, sid, f"location.hash = '#usecases&p=PUB&uc={uc}'")
        self.assertTrue(wait(lambda: js(cdp, sid, "!!document.querySelector('[data-ucf]')")))

    def test_an_empty_use_case_says_so_in_each_card(self):
        def check(cdp, sid, width):
            self.at(cdp, sid, "1.6")
            page = js(cdp, sid, "document.querySelector('[data-ucf]').innerText")
            for phrase in ("No headline yet", "Not written yet.", "No work items are shared for this use case.", "No milestones are shared for this use case."):
                self.assertIn(phrase, page)
            self.assertEqual(js(cdp, sid, "document.querySelectorAll('[data-item], [data-open-all]').length"), 0)
        self.each_width(check)

    def test_five_hundred_work_items_are_all_drawn_and_the_page_does_not_overflow(self):
        def check(cdp, sid, width):
            self.at(cdp, sid, "1.7")
            self.assertEqual(js(cdp, sid, "document.querySelectorAll('[data-ucf] [data-item]').length"), 500)
            self.assertTrue(js(cdp, sid, "document.documentElement.scrollWidth <= window.innerWidth"))
            self.assertEqual(js(cdp, sid, "document.querySelector('[data-open-all]').textContent"), "Open all 500 in Work items")
            # a line too long for its box is cut with an ellipsis on screen, and carries its full text as a title
            t = js(cdp, sid, "(() => { const e = document.querySelector('.ucf-t'); return [e.title, e.textContent]; })()")
            self.assertEqual(t[0], t[1])
            self.assertTrue(t[0].startswith("ZQ-BULK 0"))
        self.each_width(check)

    def test_open_all_goes_to_the_work_items_of_that_use_case(self):
        def check(cdp, sid, width):
            self.at(cdp, sid, "1.1")
            n = js(cdp, sid, "document.querySelector('[data-open-all]').textContent")
            self.assertRegex(n, r"^Open all \d+ in Work items$")
            js(cdp, sid, "document.querySelector('[data-open-all]').click()")
            self.assertTrue(wait(lambda: js(cdp, sid, "!document.querySelector('[data-ucf]') && !!document.querySelector('[data-view=work].on, [data-view=work][aria-current], [data-view=work][aria-selected=true]')")))
            self.assertIn("work", js(cdp, sid, "location.hash"))
            self.assertIn("1.1", js(cdp, sid, "document.body.innerText"), "the filter on the use case is shown")
            self.assertEqual(js(cdp, sid, "document.querySelectorAll('[data-item]').length + document.querySelectorAll('tbody tr').length > 0"), True)
        self.each_width(check)

    def test_the_crumb_goes_back_to_the_list_and_an_address_naming_nothing_opens_the_list(self):
        def check(cdp, sid, width):
            self.at(cdp, sid, "1.1")
            self.assertEqual(js(cdp, sid, "document.querySelector('[data-uc-back]').textContent"), "Use cases")
            js(cdp, sid, "document.querySelector('[data-uc-back]').click()")
            self.assertTrue(wait(lambda: js(cdp, sid, "!document.querySelector('[data-ucf]') && !!document.querySelector('[data-uc-page]')")), "back on the list")
            js(cdp, sid, "location.hash = '#usecases&p=PUB&uc=9.9'")
            self.assertTrue(wait(lambda: js(cdp, sid, "!document.querySelector('[data-ucf]') && !!document.querySelector('[data-uc-page]')")), "an address that names nothing shows the list")
        self.each_width(check)

    def test_the_address_of_a_use_case_is_kept_on_the_use_cases_tab_only(self):
        def check(cdp, sid, width):
            self.at(cdp, sid, "1.1")
            # opening a work item on another tab rewrites the address from what the page holds: a kept use case address would reappear in it
            js(cdp, sid, "location.hash = '#work&p=PUB&uc=1.1'")
            self.assertTrue(wait(lambda: js(cdp, sid, "!document.querySelector('[data-ucf]') && !!document.querySelector('tr[data-id]')")))
            js(cdp, sid, "document.querySelector('tr[data-id] td:nth-child(3)').click()")
            self.assertTrue(wait(lambda: js(cdp, sid, "!!document.querySelector('[data-peek]')")))
            self.assertNotIn("uc=", js(cdp, sid, "location.hash"))
        self.each_width(check)

    def test_the_heading_takes_the_focus_on_arrival_and_not_on_a_redraw(self):
        def check(cdp, sid, width):
            self.at(cdp, sid, "1.1")
            self.assertTrue(wait(lambda: js(cdp, sid, "document.activeElement === document.querySelector('[data-ucf] h1')")))
            js(cdp, sid, "document.querySelector('[data-item]').focus()")
            js(cdp, sid, "window.dispatchEvent(new Event('resize'))")
            self.assertTrue(js(cdp, sid, "document.activeElement === document.querySelector('[data-item]')"), "the focus is left where it is")
        self.each_width(check)

    def test_on_paper_nothing_is_cut_nothing_overflows_and_the_crumb_is_left_off(self):
        def check(cdp, sid, width):
            self.at(cdp, sid, "1.7")
            cdp.call("Emulation.setEmulatedMedia", {"media": "print"}, sid)
            js(cdp, sid, "document.documentElement.classList.add('print-all')")
            r = js(cdp, sid, """(() => { const t = document.querySelector('.ucf-t'), c = getComputedStyle(t);
              return {crumb: getComputedStyle(document.querySelector('.ucf-crumb')).display, ws: c.whiteSpace, ov: c.overflow, cut: t.scrollWidth > t.clientWidth,
                      wide: document.documentElement.scrollWidth <= window.innerWidth}; })()""")
            self.assertEqual(r, {"crumb": "none", "ws": "normal", "ov": "visible", "cut": False, "wide": True})
        self.each_width(check)


if __name__ == "__main__":
    unittest.main()
