"""Row 1294 (Classic only; Cards is frozen and keeps its switch row): the Defaults page (Essentials) has no "Asking on or off" row; one row "ask clark" opens the All projects tab, at 1400 and 900.

Run: python3 dev/run_tests.py test_essentials_ask_link_1294
Classic page. The words are the ruled ones (mock-up A8): row "ask clark", line "Connections, model, folders, instructions and slash commands for every project",
button "Open All projects". Chrome is required."""
import tempfile
import unittest

from _editor_checks import for_project
from test_page import DATA, navigate
from test_server import Running, chrome, wait

from clark import page

WIDTHS = (1400, 900)


class DefaultsLink(unittest.TestCase):
    THEME = "prototype-2.0"

    def setUp(self):
        self.s = Running(data_for=lambda code, archived=None: DATA.get(code), page_html=lambda: page.page_html(tempfile.mkdtemp(), theme=self.THEME))
        self.addCleanup(self.s.close)

    def until(self, js, expr, what):
        self.assertTrue(wait(lambda: js(expr), 20), f"{what}: {expr}")

    def test_no_asking_row_and_the_link_opens_the_all_projects_tab(self):
        with chrome() as cdp:
            for w in WIDTHS:
                sid = navigate(cdp, self.s.port, for_project("#settings&p=ABC&s=profile"))
                js = lambda e: cdp.js(e, sid)          # noqa: E731
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
                self.until(js, "!!document.querySelector('#essentials [data-ess-ask-link]')", f"the link at {w}")
                self.assertFalse(js("!!document.querySelector('[data-ess-ask], #ess-ask, #ess-ask-line')"), "the switch row is gone")
                self.assertNotIn("Asking on or off", js("document.getElementById('essentials').innerText"))
                self.assertEqual(js("document.querySelector('[data-ess-ask-link]').innerText"), "Open All projects")
                self.assertEqual(js("document.querySelector('#ess-ask-link-line').textContent"), "Connections, model, folders, instructions and slash commands for every project")
                self.assertEqual(js("document.querySelector('#essentials label[for=ess-ask-link]').textContent"), "ask clark")
                self.assertFalse(js("document.documentElement.scrollWidth > document.documentElement.clientWidth"), f"no sideways scroll at {w}")
                js("document.querySelector('[data-ess-ask-link]').click()")
                self.until(js, "!!document.querySelector('[data-ask-tab=all][aria-current=true]') && !!document.getElementById('ask-all')", f"the All projects tab is shown at {w}")


class CardsKeepsTheSwitch(DefaultsLink):
    """Cards is frozen (Jarvis 16:39): the old Asking switch row stays, with its words, and there is no link row."""
    THEME = None

    def test_no_asking_row_and_the_link_opens_the_all_projects_tab(self):
        with chrome() as cdp:
            for w in WIDTHS:
                sid = navigate(cdp, self.s.port, for_project("#settings&p=ABC&s=profile"))
                js = lambda e: cdp.js(e, sid)          # noqa: E731
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
                self.until(js, "!!document.querySelector('[data-ess-ask]')", f"the switch at {w}")
                self.assertFalse(js("document.getElementById('theme') !== null"), "this is the Cards page")
                self.assertFalse(js("!!document.querySelector('[data-ess-ask-link]')"), "no link row under Cards")
                self.assertIn("Asking on or off", js("document.getElementById('essentials').innerText"))


if __name__ == "__main__":
    unittest.main()
