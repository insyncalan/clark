"""A project name of 120 letters with no spaces: the Dashboard cover shows all of it (breaks inside the band), and at 900 the Settings Projects table
keeps its Open, Edit and Archive buttons whole (a button never breaks inside a word) and the page does not scroll sideways.

Run: python3 dev/run_tests.py test_projects_long_name
Chrome is required: this fails, never skips, without it. Widths 1400 and 900 only.
"""
import tempfile
import unittest

from _editor_checks import for_url
from clark import page
from test_server import Running, chrome, wait
from test_work_items import FIXED_DATE, page_target

LONG = "W" * 120
NAMES = {"LNG": LONG, "OKA": "Fabrikam Customer Portal"}


class Browser(unittest.TestCase):
    def _run(self, hash_, width, probe):
        data = {c: {"project": {"code": c, "name": n, "client_name": "Fizzlewick Ltd"}, "workstreams": [], "items": []} for c, n in NAMES.items()}
        s = Running(data_for=lambda code, **kw: data.get(code), projects=lambda archived=False: [] if archived else [{"code": c, "name": n} for c, n in NAMES.items()],
                    page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(s.close)
        with chrome() as cdp:
            sid = page_target(cdp)
            cdp.call("Page.enable", {}, sid)
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
            cdp.call("Page.navigate", {"url": "about:blank"}, sid)
            cdp.call("Page.navigate", {"url": for_url(f"http://127.0.0.1:{s.httpd.server_port}/{hash_}")}, sid)
            return probe(cdp, sid)

    def test_C_cover_shows_the_whole_long_name(self):      # item 1177: the banner is gone; the long name is the header's project button, cut with an ellipsis inside the header
        for width in (1400, 900):
            with self.subTest(width=width):
                def probe(cdp, sid):
                    sel = "document.querySelector('.top .hdr-project')"
                    self.assertTrue(wait(lambda: bool(cdp.js(f"!!{sel} && {sel}.textContent.length > 100", sid)), 30), "the header drew")
                    return (cdp.js("document.documentElement.scrollWidth - window.innerWidth", sid),
                            cdp.js(f"{sel}.getBoundingClientRect().right - document.querySelector('.top').getBoundingClientRect().right", sid))
                sideways, edge = self._run("#dashboard&p=LNG", width, probe)
                self.assertLessEqual(sideways, 0, "the page does not scroll sideways")
                self.assertLessEqual(edge, 0, "the name ends inside the header")

    def test_C_settings_buttons_stay_whole_at_900(self):
        def probe(cdp, sid):
            self.assertTrue(wait(lambda: bool(cdp.js("document.querySelectorAll('#projects-table td.acts .btn').length >= 2", sid)), 30), "the table drew")
            return (cdp.js("[...document.querySelectorAll('#projects-table td.acts .btn')].map(b => [b.textContent, Math.round(b.getBoundingClientRect().height), b.scrollWidth <= b.clientWidth + 1])", sid),
                    cdp.js("document.documentElement.scrollWidth - window.innerWidth", sid))
        btns, sideways = self._run("#settings&p=OKA", 900, probe)
        for text, height, whole in btns:
            self.assertLess(height, 48, f"{text} is one line")
            self.assertTrue(whole, f"{text} fits its box")
        self.assertLessEqual(sideways, 0, "no sideways scroll at 900")


if __name__ == "__main__":
    unittest.main()
