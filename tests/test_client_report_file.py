"""#433 The Client Requested Report View in a published file: the weekly snapshot tab.

Run: python3 dev/run_tests.py test_client_report_file
The file carries the tab (named "Weekly snapshot": a client has not asked for anything), reads only what the file holds, and shows
exactly the rows the file kept. Source tests pin the tab rule; the browser test opens the finished file from file:// with no
server, at 1400 and 900 px, light and dark, and reads the page as the client does.
"""
import tempfile
import time
import unittest
from pathlib import Path

import _publish_fixture as fx

from clark import page, publish
from test_publish import EMPTY_BRANDING, block, made, opened, tearDownModule  # noqa: F401  (the module's own clean-up of the brand-free folder)
from test_server import chrome, wait

NOTHING_FOR_THE_AUTHOR = r"on the Dashboard|Nothing written|Nothing here yet|not built|counts the same|Click to write"


def words(plant):
    """The fixture's text section becomes the Highlights box, and a second one the Planned for next week box."""
    plant["sections"][4]["title"] = "This week"
    plant["sections"][4]["body"] = "<p>ZQ-KEEP-HIGHLIGHT</p>"
    plant["sections"].append({**plant["sections"][4], "id": "s-next", "title": "Next week", "body": "<ul><li>ZQ-KEEP-NEXT</li></ul>", "sort_order": 99})


class Tab(unittest.TestCase):
    def test_the_file_carries_the_tab_after_the_use_cases(self):
        _, pub, text = made()
        self.assertEqual(pub["tabs"][-1], "clientreport")
        self.assertEqual(block(text)["tabs"], pub["tabs"])

    def test_a_hidden_milestones_section_leaves_the_tab_out(self):
        def hide(plant):
            for s in plant["sections"]:
                if s["type"] == "milestones":
                    s["hidden"] = 1
        _, pub, _ = made(hide)
        self.assertNotIn("clientreport", pub["tabs"])
        self.assertEqual(pub["data"]["milestones"], [])

    def test_nothing_the_view_needs_is_a_new_field(self):
        # the view reads milestones, risks and text sections: each is already published; no working note is added to the file
        for table in ("milestones", "raid"):
            self.assertNotIn("response_action", publish.PUBLISH_FIELDS[table])
        _, _, text = made()
        self.assertNotIn("response_action", text)


class RealBrowser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        plant = fx.load()
        words(plant)
        cls.plant = plant
        pub = publish.select(fx.inputs(plant))
        text = publish.render(pub, page.page_html(EMPTY_BRANDING), plant["as_at"], pub["data"]["project"]["name"])
        cls.pub = pub
        cls.path = Path(cls.tmp.name) / "report.html"
        cls.path.write_text(text, encoding="utf-8")

    def open_report(self, cdp, width=1400):
        sid = opened(cdp, self.path.as_uri(), width)
        self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.ready", sid) == "1"), "the page drew from the file alone")
        cdp.js("document.querySelector('[data-view=clientreport]').click()", sid)
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#clientreport .sec')", sid)), "the report view drew")
        return sid

    def test_the_view_in_the_file_shows_what_the_file_kept_and_nothing_for_the_author(self):
        with chrome() as cdp:
            sid = self.open_report(cdp)
            js = lambda e: cdp.js(e, sid)  # noqa: E731
            self.assertEqual(js("document.querySelector('[data-view=clientreport]').innerText"), "Weekly snapshot")
            self.assertEqual(js("[...document.querySelectorAll('#clientreport .sec')].map(e => e.dataset.sec)"), ["progress", "plans", "highlights", "nextweek", "raid"])
            self.assertEqual(js("document.querySelector('#clientreport .cr-band h1').textContent"), self.pub["data"]["project"]["name"])
            self.assertIn("WEEKLY PROGRESS SNAPSHOT", js("document.querySelector('.cr-band .cr-cover').textContent"))
            lines = js("[...document.querySelectorAll('[data-line]')].map(e => e.querySelector('.c-tx').textContent)")
            self.assertEqual(sorted(lines), ["Go live ZQ-KEEP-MILESTONE-2", "Pilot live ZQ-KEEP-MILESTONE-1"], "the rows the file kept, none of the others")
            self.assertEqual(js("document.querySelectorAll('[data-fig=actual], [data-fig=planned], [data-bar]').length"), 3)
            self.assertEqual(js("document.querySelectorAll('#cr-raid .wl-row').length"), 1)
            self.assertIn("Steel delivery may slip ZQ-KEEP-RISK-1", js("document.querySelector('#cr-raid').innerText"))
            self.assertIn("ZQ-KEEP-HIGHLIGHT", js("document.querySelector('#cr-highlights').innerText"))
            self.assertIn("ZQ-KEEP-NEXT", js("document.querySelector('#cr-nextweek').innerText"))
            shown = js("document.querySelector('#clientreport').innerText")
            for out in ("ZQ-HIDDEN-MILESTONE", "ZQ-FLAG-OFF-MILESTONE", "ZQ-FLAG-OFF-RISK"):
                self.assertNotIn(out, shown)
            self.assertNotRegex(shown, NOTHING_FOR_THE_AUTHOR)
            self.assertEqual(js("document.querySelectorAll('#clientreport input, #clientreport textarea, #clientreport select, #clientreport [contenteditable], #clientreport [data-placeholder]').length"), 0)
            self.assertEqual(js("window.violations"), [], "the policy blocked nothing")

    def test_it_fits_at_1400_and_900_light_and_dark(self):
        with chrome() as cdp:
            sid = self.open_report(cdp)
            for width in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
                for theme in ("light", "dark"):
                    cdp.js(f"document.documentElement.dataset.theme = '{theme}'", sid)
                    time.sleep(0.3)
                    where = f"{width}px {theme}"
                    self.assertEqual(cdp.js("document.documentElement.scrollWidth <= window.innerWidth", sid), True, f"{where}: no sideways scroll")
                    self.assertEqual(cdp.js("(() => { const f = document.querySelector('#clientreport').getBoundingClientRect();"
                                            " return [...document.querySelectorAll('#clientreport *')].filter(e => { const r = e.getBoundingClientRect();"
                                            " return r.width > 0 && (r.right > f.right + 1 || r.left < f.left - 1); }).length; })()", sid), 0, f"{where}: inside the frame")
                    dark = cdp.js("(() => { const c = getComputedStyle(document.querySelector('.cr-band')).backgroundColor.match(/\\d+/g).map(Number); return c[0] < 80 && c[1] < 80 && c[2] < 100; })()", sid)
                    self.assertTrue(dark, f"{where}: the band is dark")
                    small = cdp.js("[...document.querySelectorAll('#clientreport *')].filter(e => e.getBoundingClientRect().width > 0 && [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim()) && parseFloat(getComputedStyle(e).fontSize) < 13).length", sid)
                    self.assertEqual(small, 0, f"{where}: text at 13 px or more")


if __name__ == "__main__":
    unittest.main()
