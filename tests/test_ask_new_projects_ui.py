"""Row 1294: asking for new projects, the settings rows and the panel, in a real browser at 1400 and 900.

Run: python3 dev/run_tests.py test_ask_new_projects_ui
All projects tab: the row "Asking for new projects" (a switch, on) with Undo. A project's tab: "Asking is on for ABC." with its own button; the computer-wide switch keeps
its own words. The panel reads the project's own value before anything is sent. Chrome is required."""
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from _editor_checks import for_project
from test_ask_panel import Stub
from test_ask_settings import make_db, service
from test_page import DATA, navigate
from test_report_editor import Base
from test_server import Running, chrome, wait

from clark import page

WIDTHS = (1400, 900)


class Settings(unittest.TestCase):
    THEME = "prototype-2.0"           # Classic: the rows for new projects and the long words are drawn only here

    def setUp(self):
        self.s = Running(data_for=lambda code, archived=None: DATA.get(code), page_html=lambda: page.page_html(tempfile.mkdtemp(), theme=self.THEME))
        self.addCleanup(self.s.close)
        d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, d, True)
        self.svc = self.s.httpd.app_settings = service(make_db(d))

    def show(self, cdp):
        self.sid = navigate(cdp, self.s.port, for_project("#settings&p=ABC&s=claude"))
        js = lambda e: cdp.js(e, self.sid)          # noqa: E731
        self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ask-tab]')"), 20), "the tabs are on the page")
        return js

    def until(self, js, expr, what):
        self.assertTrue(wait(lambda: js(expr), 20), f"{what}: {expr}")

    def test_the_all_projects_row_is_a_switch_that_saves_and_undoes(self):
        with chrome() as cdp:
            js = self.show(cdp)
            js("document.querySelector('[data-ask-tab=all]').click()")
            self.until(js, "!!document.querySelector('[data-new-switch]')", "the row's switch")
            self.assertEqual(js("document.querySelector('#ask-new-all .folder-now').textContent"), "Asking for new projects")
            self.assertEqual(js("document.querySelector('#ask-new-line').textContent"), "A project can still turn asking off in its own tab.")
            self.assertEqual(js("document.querySelector('[data-new-switch]').getAttribute('aria-checked')"), "true")
            self.assertEqual(js("document.querySelector('[data-new-switch]').getAttribute('aria-label')"), "Asking for new projects")
            for w in WIDTHS:
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                self.until(js, "document.documentElement.scrollWidth <= window.innerWidth", f"no sideways scroll at {w}")
            js("document.querySelector('[data-new-switch]').click()")
            self.until(js, "document.querySelector('[data-new-switch]').getAttribute('aria-checked') === 'false' && !!document.querySelector('[data-new-undo]')", "off, with Undo")
            self.assertFalse(self.svc.read_new()[1]["on"])
            self.assertFalse(self.svc.read_new("ABC")[1]["off_here"], "a project that exists is not changed")
            js("document.querySelector('[data-new-undo]').click()")
            self.until(js, "document.querySelector('[data-new-switch]').getAttribute('aria-checked') === 'true'", "Undo puts it back")
            self.assertTrue(self.svc.read_new()[1]["on"])

    def test_the_project_tab_has_its_own_button_and_the_computer_wide_switch_keeps_its_words(self):
        with chrome() as cdp:
            js = self.show(cdp)
            self.until(js, "!!document.querySelector('[data-ask-here]')", "the project's button")
            self.assertEqual(js("document.querySelector('#ask-here-state').textContent"), "Asking is on for ABC.")
            self.assertEqual(js("document.querySelector('#ask-new-here .muted').textContent"), "The default for new projects is set under All projects.")
            self.assertEqual(js("document.querySelector('[data-ask-here]').innerText"), "Turn off asking")
            self.assertEqual(js("document.querySelector('[data-ask-switch]').innerText"), "Turn off asking for all projects")
            self.assertEqual(js("document.querySelector('#ask-state').textContent"), "Asking is on for all projects.")
            js("document.querySelector('[data-ask-here]').click()")
            self.until(js, "document.querySelector('#ask-here-state').textContent === 'Asking is off for ABC.'", "off for the project")
            self.assertEqual(js("document.querySelector('[data-ask-here]').innerText"), "Turn on asking")
            self.assertEqual(js("document.querySelector('[data-ask-switch]').innerText"), "Turn off asking for all projects", "the computer-wide switch is untouched")
            self.assertTrue(self.svc.read_new("ABC")[1]["off_here"])
            self.assertFalse(js("!!document.querySelector('#ask-new-all')"), "the starting value is on the All projects tab only")
            for w in WIDTHS:
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                self.until(js, "document.documentElement.scrollWidth <= window.innerWidth", f"no sideways scroll at {w}")


    def test_essentials_row_names_all_projects(self):
        with chrome() as cdp:
            self.sid = navigate(cdp, self.s.port, for_project("#settings&p=ABC&s=profile"))
            js = lambda e: cdp.js(e, self.sid)          # noqa: E731
            self.until(js, "!!document.querySelector('[data-ess-ask]') && !document.querySelector('[data-ess-ask]').disabled", "the Asking row")
            self.assertTrue(js("document.getElementById('theme') !== null"), "this is the Classic page")
            self.assertEqual(js("document.querySelector('[data-ess-ask]').innerText"), "Turn off asking for all projects")
            self.assertEqual(js("document.querySelector('#ess-ask-line').textContent"), "Asking is on for all projects.")


class CardsSettings(Settings):
    """Cards is frozen (ruling of 20-11 03:26): main's words, no rows for new projects, on the Settings page and in Essentials."""
    THEME = None

    def test_the_all_projects_row_is_a_switch_that_saves_and_undoes(self):
        with chrome() as cdp:
            js = self.show(cdp)
            self.assertFalse(js("document.getElementById('theme') !== null"), "this is the Cards page")
            js("document.querySelector('[data-ask-tab=all]').click()")
            self.until(js, "!!document.querySelector('#ask-all')", "the All projects card")
            self.assertFalse(js("!!document.querySelector('#ask-new-all, [data-new-switch]')"), "no row for new projects under Cards")
            self.assertNotIn("Asking for new projects", js("document.body.innerText"))

    def test_the_project_tab_has_its_own_button_and_the_computer_wide_switch_keeps_its_words(self):
        with chrome() as cdp:
            js = self.show(cdp)
            self.until(js, "!!document.querySelector('[data-ask-switch]')", "the project's card")
            self.assertEqual(js("document.querySelector('[data-ask-switch]').innerText"), "Turn off asking")
            self.until(js, "document.querySelector('#ask-state').textContent === 'Asking is on.'", "the card's line, main's words")
            self.assertFalse(js("!!document.querySelector('#ask-new-here, [data-ask-here], #ask-here-state')"), "no per-project row under Cards")
            body = js("document.body.innerText")
            for word in ("Turn off asking for all projects", "Turn on asking for all projects", "Asking is on for all projects."):
                self.assertNotIn(word, body, "the long words are Classic only")
            self.assertNotIn("Asking is on for", body)
            for w in WIDTHS:
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                self.until(js, "document.documentElement.scrollWidth <= window.innerWidth", f"no sideways scroll at {w}")

    def test_essentials_row_names_all_projects(self):
        with chrome() as cdp:
            self.sid = navigate(cdp, self.s.port, for_project("#settings&p=ABC&s=profile"))
            js = lambda e: cdp.js(e, self.sid)          # noqa: E731
            self.until(js, "!!document.querySelector('[data-ess-ask]') && !document.querySelector('[data-ess-ask]').disabled", "the Asking row")
            self.assertFalse(js("document.getElementById('theme') !== null"))
            for w in WIDTHS:
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                self.assertEqual(js("document.querySelector('[data-ess-ask]').innerText"), "Turn off asking")
                self.assertEqual(js("document.querySelector('#ess-ask-line').textContent"), "Asking is on.")


class Panel(Base):
    def setUp(self):
        super().setUp()
        self.stub = Stub()
        self.s.httpd.ask = self.stub
        d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, d, True)
        self.svc = self.s.httpd.app_settings = service(make_db(d))

    def open_panel(self, cdp):
        p = self.visit(cdp)
        p.key("/", code="Slash", vk=191)
        p.until("!!document.querySelector('#ask-panel')", "the panel opened on /")
        return p

    def test_a_project_with_asking_off_reads_off_before_anything_is_sent(self):
        self.svc.change_new({"project": "ABC", "off_here": True})
        with chrome() as cdp:
            p = self.open_panel(cdp)
            p.until("!!document.querySelector('#ask-off')", "the panel says asking is off")
            self.assertTrue(p.js("document.querySelector('#ask-send') === null || document.querySelector('#ask-send').disabled"), "nothing can be sent")
            self.assertEqual([k for k, b in self.stub.calls if k == "ask"], [])

    def test_a_project_with_asking_on_is_ready(self):
        with chrome() as cdp:
            p = self.open_panel(cdp)
            p.until("document.querySelector('#ask-box') && !document.querySelector('#ask-send').disabled", "ready")
            self.assertFalse(p.js("!!document.querySelector('#ask-off')"))

    def read_gives(self, status, body):
        """Make the server's read of the project's own value answer `status` and `body` (the real route, the real page)."""
        self.svc.read_new = lambda project=None: (status, body) if project else (200, {"ok": True, "on": True})

    def test_a_read_that_fails_sends_nothing(self):
        cases = (("500", 500, {"ok": False, "code": "boom"}),
                 ("200 with a value that is not a boolean", 200, {"ok": True, "off_here": "no"}),
                 ("200 with no value", 200, {"ok": True}),
                 ("404 bad_project", 404, {"ok": False, "code": "bad_project"}))
        for name, status, body in cases:
            with self.subTest(name):
                self.read_gives(status, body)
                self.stub.calls.clear()
                with chrome() as cdp:
                    p = self.open_panel(cdp)
                    self.until_unknown(p)

    def test_a_network_error_on_the_read_sends_nothing(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.js("(() => { const f = globalThis.fetch; globalThis.fetch = (u, i) => String(u).includes('ask-new-projects') ? Promise.reject(new Error('down')) : f(u, i); })()")
            p.key("/", code="Slash", vk=191)
            p.until("!!document.querySelector('#ask-panel')", "the panel opened on /")
            self.until_unknown(p)

    def test_a_404_with_code_not_found_proceeds(self):
        self.read_gives(404, {"ok": False, "code": "not_found"})
        with chrome() as cdp:
            p = self.open_panel(cdp)
            p.until("document.querySelector('#ask-box') && !document.querySelector('#ask-send').disabled", "ready: a server with no per-project value proceeds")

    def until_unknown(self, p):
        """The read has answered and failed: the panel is no longer 'checking' and its box is shut (state unknown, which sends nothing)."""
        p.until("!!document.querySelector('#ask-box') && document.querySelector('#ask-box').disabled", "the panel reads as unknown")
        self.assertTrue(p.js("!document.querySelector('#ask-send') || document.querySelector('#ask-send').disabled"), "send is off")
        self.assertEqual([k for k, b in self.stub.calls if k == "ask"], [], "nothing was asked")


if __name__ == "__main__":
    unittest.main()
