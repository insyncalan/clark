"""Row 1503 (the screen part of row 1294): a change the server cannot save says so in words, leaves the switch or button where it was and offers no Undo.

Run: python3 dev/run_tests.py test_ask_new_projects_ui_1503
Classic only, at 1400 and 900. The server refuses the change two ways: a 409 with its own message, and a 500 with no message. Chrome is required."""
import os
import shutil
import tempfile
import threading
import unittest
from pathlib import Path

from _editor_checks import for_project
from test_ask_settings import make_db, service
from test_page import DATA, navigate
from test_server import Running, chrome, wait

from clark import page

WIDTHS = (1400, 900)


class CannotBeSaved(unittest.TestCase):
    def setUp(self):
        self.s = Running(data_for=lambda code, archived=None: DATA.get(code), page_html=lambda: page.page_html(tempfile.mkdtemp(), theme="prototype-2.0"))
        self.addCleanup(self.s.close)
        d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, d, True)
        self.svc = self.s.httpd.app_settings = service(make_db(d))

    def until(self, js, expr, what):
        self.assertTrue(wait(lambda: js(expr), 20), f"{what}: {expr}")

    def refused(self, status, body):
        """Every change is refused; a read still answers."""
        real = self.svc.change_new
        self.svc.change_new = lambda b: (status, body)
        self.addCleanup(setattr, self.svc, "change_new", real)

    def check(self, js, width):
        """Both controls, one after the other: the words appear, the control stays, no Undo."""
        js("document.querySelector('[data-ask-tab=all]').click()")
        self.until(js, "!!document.querySelector('[data-new-switch]')", f"the row's switch at {width}")
        js("document.querySelector('[data-new-switch]').click()")
        self.until(js, "!!document.querySelector('#ask-new-all .error')", f"words on the row at {width}")
        self.assertEqual(js("document.querySelector('[data-new-switch]').getAttribute('aria-checked')"), "true", "the switch stays where it was")
        self.assertFalse(js("!!document.querySelector('[data-new-undo]')"), "no Undo on the row")
        self.assertTrue(js("document.querySelector('#ask-new-all .error').textContent.trim().length > 0"), "the words are not empty")
        words_row = js("document.querySelector('#ask-new-all .error').textContent")
        js("document.querySelector('[data-ask-tab]:not([data-ask-tab=all])').click()")
        self.until(js, "!!document.querySelector('[data-ask-here]')", f"the project's button at {width}")
        js("document.querySelector('[data-ask-here]').click()")
        self.until(js, "!!document.querySelector('#ask-new-here .error')", f"words on the project at {width}")
        self.assertEqual(js("document.querySelector('#ask-here-state').textContent"), "Asking is on for ABC.", "the button state stays")
        self.assertEqual(js("document.querySelector('[data-ask-here]').innerText"), "Turn off asking")
        self.assertFalse(js("!!document.querySelector('[data-new-undo]')"), "no Undo on the project")
        self.assertEqual(js("document.querySelector('#ask-new-here .error').textContent"), words_row)
        return words_row

    def run_case(self):
        with chrome() as cdp:
            self.sid = navigate(cdp, self.s.port, for_project("#settings&p=ABC&s=claude"))
            js = lambda e: cdp.js(e, self.sid)          # noqa: E731
            self.until(js, "!!document.querySelector('[data-ask-tab]')", "the tabs")
            said = []
            for w in WIDTHS:
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                said.append(self.check(js, w))
                self.until(js, "document.documentElement.scrollWidth <= window.innerWidth", f"no sideways scroll at {w}")
        self.assertTrue(self.svc.read_new()[1]["on"], "nothing was saved")
        self.assertFalse(self.svc.read_new("ABC")[1]["off_here"], "nothing was saved for the project")
        return said

    def test_a_change_that_cannot_be_saved_says_so_and_offers_no_undo(self):
        body = self.svc.fail("busy")
        self.refused(409, body)
        self.assertEqual(self.run_case(), [body["message"]] * 2)

    def test_a_server_error_with_no_words_still_says_so_and_offers_no_undo(self):
        self.refused(500, {})
        said = self.run_case()
        self.assertEqual(said[0], said[1])
        self.assertEqual(said[0], "Something went wrong while this was working. Nothing was changed. If it happens again, restart clark.")

    def open_all(self, cdp):
        self.sid = navigate(cdp, self.s.port, for_project("#settings&p=ABC&s=claude"))
        js = lambda e: cdp.js(e, self.sid)          # noqa: E731
        self.until(js, "!!document.querySelector('[data-ask-tab]')", "the tabs")
        js("document.querySelector('[data-ask-tab=all]').click()")
        self.until(js, "!!document.querySelector('[data-new-switch]')", "the row's switch")
        return js

    def test_a_refused_change_takes_away_the_undo_of_the_one_before(self):
        with chrome() as cdp:
            js = self.open_all(cdp)
            js("document.querySelector('[data-new-switch]').click()")
            self.until(js, "!!document.querySelector('[data-new-undo]')", "the Undo of the saved change")
            self.refused(409, self.svc.fail("busy"))
            js("document.querySelector('[data-new-switch]').click()")
            self.until(js, "!!document.querySelector('#ask-new-all .error')", "the words")
            self.assertFalse(js("!!document.querySelector('[data-new-undo]')"), "the old Undo is gone")

    def test_an_undo_offers_no_second_undo(self):
        real = self.svc.change_new

        def with_step(body):
            status, got = real(body)
            return status, dict(got, apply_id="x1") if status == 200 else got
        self.svc.change_new = with_step
        self.addCleanup(setattr, self.svc, "change_new", real)
        with chrome() as cdp:
            js = self.open_all(cdp)
            js("document.querySelector('[data-new-switch]').click()")
            self.until(js, "!!document.querySelector('[data-new-undo]')", "the Undo")
            self.svc.change_new = lambda body: with_step({"on": True}) if body.get("undo") else with_step(body)
            js("document.querySelector('[data-new-undo]').click()")
            self.until(js, "document.querySelector('[data-new-switch]').getAttribute('aria-checked') === 'true'", "put back")
            self.assertFalse(js("!!document.querySelector('[data-new-undo]')"), "no Undo of an Undo")

    def test_an_answer_that_is_not_a_200_is_not_a_saved_change(self):
        self.refused(500, {"ok": True, "on": False, "off_here": False, "apply_id": "x1"})
        with chrome() as cdp:
            js = self.open_all(cdp)
            js("document.querySelector('[data-new-switch]').click()")
            self.until(js, "!!document.querySelector('#ask-new-all .error')", "the words")
            self.assertEqual(js("document.querySelector('[data-new-switch]').getAttribute('aria-checked')"), "true")
            self.assertFalse(js("!!document.querySelector('[data-new-undo]')"))

    def test_a_read_that_is_not_a_200_shows_no_switch(self):
        real = self.svc.read_new
        self.svc.read_new = lambda project=None: (500, {"ok": True, "on": True, "off_here": False})
        self.addCleanup(setattr, self.svc, "read_new", real)
        with chrome() as cdp:
            self.sid = navigate(cdp, self.s.port, for_project("#settings&p=ABC&s=claude"))
            js = lambda e: cdp.js(e, self.sid)          # noqa: E731
            self.until(js, "!!document.querySelector('[data-ask-tab]')", "the tabs")
            self.until(js, "!!document.querySelector('#ask-state')", "the project tab")
            js("document.querySelector('[data-ask-tab=all]').click()")
            self.until(js, "!!document.querySelector('#ask-new-all')", "the row")
            self.assertFalse(wait(lambda: js("!!document.querySelector('[data-new-switch]')"), 3), "no switch for a value that was not read")
            js("document.querySelector('[data-ask-tab]:not([data-ask-tab=all])').click()")
            self.until(js, "!!document.querySelector('#ask-state')", "the project tab again")
            self.assertFalse(wait(lambda: js("!!document.querySelector('[data-ask-here]')"), 3), "no button for a value that was not read")

    def test_the_switch_is_shut_while_a_change_is_being_saved(self):
        real, gate, entered = self.svc.change_new, threading.Event(), threading.Event()

        def slow(body):
            entered.set()
            gate.wait(20)
            return real(body)
        self.svc.change_new = slow
        self.addCleanup(setattr, self.svc, "change_new", real)
        self.addCleanup(gate.set)
        with chrome() as cdp:
            js = self.open_all(cdp)
            js("document.querySelector('[data-new-switch]').click()")
            self.assertTrue(entered.wait(20))
            self.until(js, "document.querySelector('[data-new-switch]').disabled === true", "shut while saving")
            gate.set()
            self.until(js, "document.querySelector('[data-new-switch]').disabled === false", "open again")


if __name__ == "__main__":
    unittest.main()
