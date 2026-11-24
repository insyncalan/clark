"""Row 1503: the survivors of the mutation sweep over the new-projects screen and the panel's own-project read, each killed by a browser test.

Run: python3 dev/run_tests.py test_ask_new_projects_kill_1503
Panel: what the panel says when the read of the project's own value fails in the ways the other tests leave out, when the connection check is kept, when the
connection is signed out, and when the answer comes late for another project. Settings: the project's button, the words' role, the Undo while a change is
being saved, and the read for another project. Classic for Settings, 1400 and 900. Chrome is required."""
import os
import shutil
import tempfile
import threading
import unittest
from pathlib import Path

from test_ask_panel import Stub
from test_ask_settings import make_db, service
from test_page import navigate
from test_report_editor import Base, Pg
from test_server import chrome, wait

from ask_np_settings_base_1503 import SettingsBase

WIDTHS = (1400, 900)
BOX = "!!document.querySelector('#ask-box') && !document.querySelector('#ask-box').disabled && !document.querySelector('#ask-send').disabled"
SHUT = "!!document.querySelector('#ask-box') && document.querySelector('#ask-box').disabled"


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

    def read_gives(self, status, body):
        self.svc.read_new = lambda project=None: (status, body) if project else (200, {"ok": True, "on": True})

    def shut_and_silent(self, p):
        """The read has answered and failed: the box is shut, no off line, no signed-out line, nothing asked."""
        p.until(SHUT, "the panel reads as unknown: the box is shut")
        self.assertFalse(p.js("!!document.querySelector('#ask-off, #ask-signed-out')"), "it claims neither off nor signed out")
        self.assertTrue(p.js("!document.querySelector('#ask-send') || document.querySelector('#ask-send').disabled"), "send is off")
        self.assertEqual(self.stub.count("ask"), 0, "nothing was asked")

    def test_an_answer_that_is_not_a_good_one_is_unknown_whatever_value_it_carries(self):
        """A 500 that still says ok and a boolean, and a 200 that does not say ok, are not a read of the value."""
        cases = (("500 with ok and asking on", 500, {"ok": True, "off_here": False}),
                 ("500 with ok and asking off", 500, {"ok": True, "off_here": True}),
                 ("200 that says not ok, asking on", 200, {"ok": False, "off_here": False}),
                 ("200 that says not ok, asking off", 200, {"ok": False, "off_here": True}),
                 ("200 with no ok, asking on", 200, {"off_here": False}),
                 ("200 with ok as a word, asking on", 200, {"ok": "true", "off_here": False}))
        for name, status, body in cases:
            with self.subTest(name):
                self.read_gives(status, body)
                with chrome() as cdp:
                    p = self.open_panel(cdp)
                    self.shut_and_silent(p)

    def test_a_kept_connection_check_still_reads_the_project(self):
        """Opened once and ready (the check is kept), then the project's own asking is turned off, then opened again at once: it reads off, not ready."""
        with chrome() as cdp:
            p = self.open_panel(cdp)
            p.until(BOX, "ready the first time")
            p.key("Escape", code="Escape", vk=27)
            p.until("document.querySelector('#ask-panel') === null", "closed")
            self.assertEqual(self.stub.count("status"), 1)
            self.svc.change_new({"project": "ABC", "off_here": True})
            p.key("/", code="Slash", vk=191)
            p.until("!!document.querySelector('#ask-panel')", "opened again")
            p.until("!!document.querySelector('#ask-off')", "it reads off from the project's own value")
            self.assertEqual(self.stub.count("status"), 1, "the connection was not asked again: the check was kept")
            self.assertTrue(p.js("document.querySelector('#ask-send') === null || document.querySelector('#ask-send').disabled"))
            self.assertEqual(self.stub.count("ask"), 0)

    def test_a_signed_out_connection_still_reads_the_project(self):
        """Signed out and the project's own asking off: it says off. Signed out and the read failing: it claims nothing. Signed out and asking on: it stays signed out."""
        self.stub.connected = False
        with self.subTest("own asking off"):
            self.svc.change_new({"project": "ABC", "off_here": True})
            with chrome() as cdp:
                p = self.open_panel(cdp)
                p.until("!!document.querySelector('#ask-off')", "off for the project")
                self.assertFalse(p.js("!!document.querySelector('#ask-signed-out')"))
        with self.subTest("the read fails"):
            self.read_gives(500, {"ok": False})
            with chrome() as cdp:
                p = self.open_panel(cdp)
                self.shut_and_silent(p)
        with self.subTest("own asking on"):
            self.svc.read_new = lambda project=None: (200, {"ok": True, "on": True, "off_here": False})
            with chrome() as cdp:
                p = self.open_panel(cdp)
                p.until("!!document.querySelector('#ask-signed-out')", "still signed out")
                self.assertFalse(p.js("!!document.querySelector('#ask-off')"))
                self.assertTrue(p.js("document.querySelector('#ask-send') === null || document.querySelector('#ask-send').disabled"), "not ready: nothing can be sent")

    def test_a_network_error_on_the_read_stops_checking(self):
        """The read fails with no answer at all: the panel stops saying it is checking (unknown claims nothing)."""
        with chrome() as cdp:
            p = self.visit(cdp)
            p.js("(() => { const f = globalThis.fetch; globalThis.fetch = (u, i) => String(u).includes('ask-new-projects') ? Promise.reject(new Error('down')) : f(u, i); })()")
            p.key("/", code="Slash", vk=191)
            p.until("!!document.querySelector('#ask-panel')", "the panel opened on /")
            self.shut_and_silent(p)
            self.assertFalse(wait(lambda: p.js("document.querySelector('#ask-panel').textContent.indexOf('Checking whether you can ask') >= 0"), 3), "it is no longer checking")

    def test_a_200_that_is_not_json_reads_as_unknown(self):
        """The server answers 200 with words that are not JSON (no body at all to the page): the panel reads unknown and stops checking."""
        with chrome() as cdp:
            p = self.visit(cdp)
            p.js("(() => { const f = globalThis.fetch; globalThis.fetch = (u, i) => String(u).includes('ask-new-projects') ? Promise.resolve(new Response('oops', {status: 200})) : f(u, i); })()")
            p.key("/", code="Slash", vk=191)
            p.until("!!document.querySelector('#ask-panel')", "the panel opened on /")
            self.shut_and_silent(p)
            self.assertFalse(wait(lambda: p.js("document.querySelector('#ask-panel').textContent.indexOf('Checking whether you can ask') >= 0"), 3), "it is no longer checking")

    def test_signed_out_and_a_server_with_no_settings_store_stays_signed_out(self):
        self.stub.connected = False
        self.read_gives(404, {"ok": False, "code": "not_found"})
        with chrome() as cdp:
            p = self.open_panel(cdp)
            p.until("!!document.querySelector('#ask-signed-out')", "still signed out")
            self.assertFalse(p.js("!!document.querySelector('#ask-off')"))

    def test_a_late_read_does_not_undo_a_newer_answer(self):
        """Signed out (so nothing is kept). The read is held; the panel is closed, asking is turned off on the computer, the panel is opened again and reads off; then the held read
        (asking on for the project) arrives: the panel still reads off."""
        self.stub.connected = False
        gate, entered = threading.Event(), threading.Event()

        def held(project=None):
            if project and not entered.is_set():
                entered.set()
                gate.wait(20)
            return 200, {"ok": True, "on": True, "off_here": False}
        self.svc.read_new = held
        self.addCleanup(gate.set)
        with chrome() as cdp:
            p = self.open_panel(cdp)
            self.assertTrue(entered.wait(20), "the first read is out")
            p.key("Escape", code="Escape", vk=27)
            p.until("document.querySelector('#ask-panel') === null", "closed")
            self.stub.enabled = False
            p.key("/", code="Slash", vk=191)
            p.until("!!document.querySelector('#ask-off')", "the second open reads off")
            gate.set()
            self.assertFalse(wait(lambda: p.js("!document.querySelector('#ask-off')"), 3), "the late read did not undo it")


class PanelAmongProjects(SettingsBase):
    def test_an_answer_for_another_project_is_dropped(self):
        """The read for ABC is held; the page moves to XYZ and the panel is closed and opened again there, its own read held too; then ABC's answer
        (asking off) arrives. The panel does not read off for XYZ: it goes on checking until XYZ's own answer comes (asking on, ready)."""
        gates, entered, armed = {"ABC": threading.Event(), "XYZ": threading.Event()}, {"ABC": threading.Event(), "XYZ": threading.Event()}, threading.Event()

        def held(project=None):
            if not project or not armed.is_set():
                return 200, {"ok": True, "on": True, "off_here": False}
            entered[project].set()
            gates[project].wait(20)
            return 200, {"ok": True, "on": True, "off_here": project == "ABC"}
        self.svc.read_new = held
        for g in gates.values():
            self.addCleanup(g.set)
        with chrome() as cdp:
            js = self.show(cdp)
            self.until(js, "!!document.querySelector('[data-ask-here]')", "the project's button has read")
            js("document.activeElement.blur()")
            self.s.httpd.ask = self.stub = Stub()
            armed.set()
            pg = Pg(self, cdp, self.sid)
            pg.key("/", code="Slash", vk=191)
            self.until(js, "!!document.querySelector('#ask-panel')", "the panel opened on /")
            self.assertTrue(entered["ABC"].wait(20), "the read for ABC is out")
            js("window.sameDocument = true")
            self.move_to(js, "XYZ")
            self.until(js, "location.hash.indexOf('p=XYZ') >= 0", "the page is on XYZ")
            self.assertTrue(js("window.sameDocument === true"), "the same document: the page moved to XYZ without loading again")
            if js("!!document.querySelector('#ask-panel')"):
                pg.key("Escape", code="Escape", vk=27)
                self.until(js, "document.querySelector('#ask-panel') === null", "the panel closed")
            js("document.activeElement.blur()")
            pg.key("/", code="Slash", vk=191)
            self.until(js, "!!document.querySelector('#ask-panel')", "the panel opened again, on XYZ")
            self.assertTrue(entered["XYZ"].wait(20), "the read for XYZ is out")
            gates["ABC"].set()
            self.assertFalse(wait(lambda: js("!!document.querySelector('#ask-off')"), 3), "ABC's answer is not XYZ's")
            gates["XYZ"].set()
            self.until(js, "!!document.querySelector('#ask-box') && !document.querySelector('#ask-box').disabled && !document.querySelector('#ask-send').disabled", "XYZ's own answer: ready")
            self.assertFalse(js("!!document.querySelector('#ask-off')"))


class PanelWithNoProject(SettingsBase):
    def test_a_page_with_no_project_asks_nothing_about_a_project(self):
        """No project is open (none exist): the panel has no project's value to read, so it does not read one; it goes on as ready."""
        self.s.httpd.projects = lambda archived=False: []
        self.s.httpd.ask = Stub()
        reads = []
        real = self.svc.read_new
        self.svc.read_new = lambda project=None: (reads.append(project), real(project))[1]
        with chrome() as cdp:
            self.sid = navigate(cdp, self.s.port, "#settings")
            js = lambda e: cdp.js(e, self.sid)          # noqa: E731
            self.until(js, "document.body.innerText.indexOf('No project open') >= 0", "no project is open")
            Pg(self, cdp, self.sid).key("/", code="Slash", vk=191)
            self.until(js, "!!document.querySelector('#ask-panel')", "the panel opened")
            self.until(js, BOX, "ready")
            self.assertEqual(reads, [], "no read of a project's value")


class Settings(SettingsBase):
    def reply(self, status, body):
        real = self.svc.change_new
        self.svc.change_new = lambda b: (status, body)
        self.addCleanup(setattr, self.svc, "change_new", real)

    def test_a_value_that_is_not_a_boolean_is_not_off(self):
        real = self.svc.read_new
        self.svc.read_new = lambda project=None: (200, {"ok": True, "on": True, "off_here": "no"})
        self.addCleanup(setattr, self.svc, "read_new", real)
        with chrome() as cdp:
            js = self.show(cdp)
            self.until(js, "!!document.querySelector('#ask-here-state')", "the project's line")
            self.assertEqual(js("document.querySelector('#ask-here-state').textContent"), "Asking is on for ABC.")

    def test_a_saved_answer_with_a_value_that_is_not_a_boolean_is_not_off(self):
        self.reply(200, {"ok": True, "on": True, "off_here": "no"})
        with chrome() as cdp:
            js = self.show(cdp)
            self.until(js, "!!document.querySelector('[data-ask-here]')", "the button")
            js("document.querySelector('[data-ask-here]').click()")
            self.until(js, "!document.querySelector('[data-ask-here]').disabled", "saved")
            self.assertEqual(js("document.querySelector('#ask-here-state').textContent"), "Asking is on for ABC.")

    def test_an_answer_that_says_not_ok_is_not_a_saved_change(self):
        self.reply(200, {"ok": False, "on": False, "off_here": False, "apply_id": "x1"})
        with chrome() as cdp:
            js = self.show(cdp)
            js("document.querySelector('[data-ask-tab=all]').click()")
            self.until(js, "!!document.querySelector('[data-new-switch]')", "the switch")
            js("document.querySelector('[data-new-switch]').click()")
            self.until(js, "!!document.querySelector('#ask-new-all .error')", "the words")
            self.assertEqual(js("document.querySelector('[data-new-switch]').getAttribute('aria-checked')"), "true")
            self.assertFalse(js("!!document.querySelector('[data-new-undo]')"))

    def test_the_words_go_when_the_next_change_is_saved(self):
        real = self.svc.change_new
        with chrome() as cdp:
            js = self.show(cdp)
            js("document.querySelector('[data-ask-tab=all]').click()")
            self.until(js, "!!document.querySelector('[data-new-switch]')", "the switch")
            self.svc.change_new = lambda b: (409, self.svc.fail("busy"))
            js("document.querySelector('[data-new-switch]').click()")
            self.until(js, "!!document.querySelector('#ask-new-all .error')", "the words")
            self.svc.change_new = real
            js("document.querySelector('[data-new-switch]').click()")
            self.until(js, "document.querySelector('[data-new-switch]').getAttribute('aria-checked') === 'false'", "saved")
            self.assertFalse(js("!!document.querySelector('#ask-new-all .error')"), "the old words are gone")

    def test_the_project_button_is_shut_while_a_change_is_being_saved(self):
        real, gate, entered = self.svc.change_new, threading.Event(), threading.Event()

        def slow(body):
            entered.set()
            gate.wait(20)
            return real(body)
        self.svc.change_new = slow
        self.addCleanup(setattr, self.svc, "change_new", real)
        self.addCleanup(gate.set)
        with chrome() as cdp:
            js = self.show(cdp)
            self.until(js, "!!document.querySelector('[data-ask-here]')", "the button")
            js("document.querySelector('[data-ask-here]').click()")
            self.assertTrue(entered.wait(20))
            self.until(js, "document.querySelector('[data-ask-here]').disabled === true", "shut while saving")
            gate.set()
            self.until(js, "document.querySelector('[data-ask-here]').disabled === false", "open again")

    def test_the_computer_wide_switch_off_says_turn_on_for_all_projects(self):
        with chrome() as cdp:
            js = self.show(cdp)
            self.until(js, "!!document.querySelector('[data-ask-switch]') && !document.querySelector('[data-ask-switch]').disabled", "the switch")
            js("document.querySelector('[data-ask-switch]').click()")
            self.until(js, "document.querySelector('[data-ask-switch]').innerText === 'Turn on asking for all projects'", "the words when off")

    def test_the_project_button_says_whether_asking_is_pressed(self):
        with chrome() as cdp:
            js = self.show(cdp)
            self.until(js, "!!document.querySelector('[data-ask-here]')", "the project's button")
            for w in WIDTHS:
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                self.assertEqual(js("document.querySelector('[data-ask-here]').getAttribute('aria-pressed')"), "true", f"asking on: pressed at {w}")
            js("document.querySelector('[data-ask-here]').click()")
            self.until(js, "document.querySelector('#ask-here-state').textContent === 'Asking is off for ABC.'", "off for the project")
            for w in WIDTHS:
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                self.assertEqual(js("document.querySelector('[data-ask-here]').getAttribute('aria-pressed')"), "false", f"asking off: not pressed at {w}")

    def test_the_words_about_a_change_are_an_alert(self):
        for w in WIDTHS:
            with self.subTest(w), chrome() as cdp:
                js = self.show(cdp)
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                self.until(js, "!!document.querySelector('#ask-new-here .ask-new-msg')", "the project's words' place")
                self.assertEqual(js("document.querySelector('#ask-new-here .ask-new-msg').getAttribute('role')"), "alert", "the project's words")
                js("document.querySelector('[data-ask-tab=all]').click()")
                self.until(js, "!!document.querySelector('#ask-new-all .ask-new-msg')", "the row")
                self.assertEqual(js("document.querySelector('#ask-new-all .ask-new-msg').getAttribute('role')"), "alert", "the row's words")
                self.assertEqual(js("document.querySelector('#ask-new-all .ask-new-msg').getAttribute('aria-live')"), "polite")

    def test_the_undo_is_shut_while_it_is_being_saved(self):
        real, gate, entered = self.svc.change_new, threading.Event(), threading.Event()

        def slow(body):
            if body.get("undo"):
                entered.set()
                gate.wait(20)
            return real(body)
        self.svc.change_new = slow
        self.addCleanup(gate.set)
        with chrome() as cdp:
            js = self.show(cdp)
            js("document.querySelector('[data-ask-tab=all]').click()")
            self.until(js, "!!document.querySelector('[data-new-switch]')", "the switch")
            js("document.querySelector('[data-new-switch]').click()")
            self.until(js, "!!document.querySelector('[data-new-undo]') && !document.querySelector('[data-new-undo]').disabled", "the Undo is offered and open")
            js("document.querySelector('[data-new-undo]').click()")
            self.assertTrue(entered.wait(20), "the Undo is being saved")
            self.until(js, "!document.querySelector('[data-new-undo]') || document.querySelector('[data-new-undo]').disabled === true", "the Undo is shut while it is saved")
            self.until(js, "document.querySelector('[data-new-switch]').disabled === true", "the switch is shut too")
            gate.set()
            self.until(js, "document.querySelector('[data-new-switch]').disabled === false && document.querySelector('[data-new-switch]').getAttribute('aria-checked') === 'true'", "put back")

    def test_a_read_that_is_not_a_good_one_shows_no_switch_whatever_it_carries(self):
        """A 200 with ok but no boolean value, or with a value that is a word, is not a read of the switch."""
        for name, body in (("no value", {"ok": True, "off_here": False}), ("a word", {"ok": True, "on": "yes", "off_here": False}), ("a number", {"ok": True, "on": 1, "off_here": False})):
            with self.subTest(name):
                real = self.svc.read_new
                self.svc.read_new = lambda project=None, b=body: (200, b)
                self.addCleanup(setattr, self.svc, "read_new", real)
                with chrome() as cdp:
                    js = self.show(cdp)
                    self.until(js, "!!document.querySelector('#ask-state')", "the project tab")
                    js("document.querySelector('[data-ask-tab=all]').click()")
                    self.until(js, "!!document.querySelector('#ask-new-all')", "the row")
                    self.assertFalse(wait(lambda: js("!!document.querySelector('[data-new-switch]')"), 3), "no switch")
                    js("document.querySelector('[data-ask-tab]:not([data-ask-tab=all])').click()")
                    self.until(js, "!!document.querySelector('#ask-state')", "the project tab again")
                    self.assertFalse(wait(lambda: js("!!document.querySelector('[data-ask-here]')"), 3), "no button")

    def test_the_project_button_follows_the_project_and_not_a_late_answer_for_the_one_before(self):
        """The read for ABC is held; the page moves to XYZ, which answers at once (asking on); then ABC's answer (asking off) arrives. XYZ reads on."""
        gate, entered = threading.Event(), threading.Event()
        real = self.svc.read_new

        def read(project=None):
            if project == "ABC":
                entered.set()
                gate.wait(20)
                return 200, {"ok": True, "on": True, "off_here": True}
            return 200, {"ok": True, "on": True, "off_here": False}
        self.svc.read_new = read
        self.addCleanup(setattr, self.svc, "read_new", real)
        self.addCleanup(gate.set)
        with chrome() as cdp:
            js = self.show(cdp)
            self.assertTrue(entered.wait(20), "the read for ABC is out")
            self.move_to(js, "XYZ")
            self.back_to_asking(js)
            self.until(js, "document.querySelector('#ask-here-state') && document.querySelector('#ask-here-state').textContent === 'Asking is on for XYZ.'", "XYZ is read")
            gate.set()
            self.assertFalse(wait(lambda: js("document.querySelector('#ask-here-state') && /off/.test(document.querySelector('#ask-here-state').textContent)"), 3), "ABC's late answer did not land on XYZ")
            self.assertEqual(js("document.querySelector('#ask-here-state').textContent"), "Asking is on for XYZ.")

    def test_the_project_button_reads_again_for_another_project(self):
        """ABC has asking off, XYZ has it on; moving from ABC to XYZ shows XYZ's value."""
        real = self.svc.read_new
        self.svc.read_new = lambda project=None: (200, {"ok": True, "on": True, "off_here": project == "ABC"})
        self.addCleanup(setattr, self.svc, "read_new", real)
        with chrome() as cdp:
            js = self.show(cdp)
            self.until(js, "document.querySelector('#ask-here-state') && document.querySelector('#ask-here-state').textContent === 'Asking is off for ABC.'", "ABC reads off")
            self.move_to(js, "XYZ")
            self.back_to_asking(js)
            self.until(js, "document.querySelector('#ask-here-state') && document.querySelector('#ask-here-state').textContent === 'Asking is on for XYZ.'", "XYZ reads on")


if __name__ == "__main__":
    unittest.main()
