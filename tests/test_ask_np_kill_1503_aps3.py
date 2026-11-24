"""Row 1503, askPanelState.js, slice 3 (the late-answer guard in the panel's own-project read).

Run: python3 dev/run_tests.py test_ask_np_kill_1503_aps3
The panel stays open while the page moves to another project; the read for the first project (asking off there) arrives late and must not make the panel
read off for the project it is now on. Classic, 1400. Chrome is required."""
import threading

from test_ask_panel import Stub
import ask_np_settings_base_1503 as base
from test_report_editor import Pg
from test_server import chrome, wait


class LateReadAfterMove(base.SettingsBase):
    def test_a_read_for_the_project_left_does_not_decide_the_panel_that_stayed_open(self):
        """Signed out (nothing kept), so the read for ABC is held. The page moves to XYZ with the panel still open; ABC's answer (asking off for ABC) arrives.
        The panel does not read off: it is still waiting on a read that never comes for XYZ, so it shows no off line."""
        gate, entered = threading.Event(), threading.Event()

        def held(project=None):
            if project == "ABC":
                entered.set()
                gate.wait(20)
                return 200, {"ok": True, "on": True, "off_here": True}
            return 200, {"ok": True, "on": True, "off_here": False}
        self.addCleanup(gate.set)
        with chrome() as cdp:
            js = self.show(cdp)
            self.until(js, "!!document.querySelector('[data-ask-here]')", "the project's button has read")
            self.svc.read_new = held
            js("document.activeElement.blur()")
            self.s.httpd.ask = Stub()
            self.s.httpd.ask.connected = False
            pg = Pg(self, cdp, self.sid)
            pg.key("/", code="Slash", vk=191)
            self.until(js, "!!document.querySelector('#ask-panel')", "the panel opened on /")
            self.assertTrue(entered.wait(20), "the read for ABC is out")
            self.move_to(js, "XYZ")
            self.until(js, "location.hash.indexOf('p=XYZ') >= 0", "the page is on XYZ")
            self.assertTrue(js("!!document.querySelector('#ask-panel')"), "the panel stayed open on the move")
            gate.set()
            self.assertFalse(wait(lambda: js("!!document.querySelector('#ask-off')"), 3), "ABC's answer did not make the panel read off for XYZ")
            self.assertTrue(js("!!document.querySelector('#ask-panel')"), "the panel is still there")
