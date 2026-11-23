"""Row 1503: the survivors of the mutation sweep over the hook that reads a project's own asking value (the first lines of the new-projects screen).

Run: python3 dev/run_tests.py test_ask_np_kill_1503_npA
The project's tab stays on the screen when the address moves from one project to another (a typed address, or Back): the line and the button are then the same
mounted parts and must follow the project they name. The old project's value is cleared while the next is read, a late answer for the project that was left is
dropped, and the next project is read again. Classic for Settings. Chrome is required, 1400 only."""
import threading
import unittest

import ask_np_settings_base_1503 as base
from test_server import chrome, wait

LINE = "document.querySelector('#ask-here-state')"


class FollowsTheAddress(base.SettingsBase):
    def go(self, js, code):
        """Move in place to another project's Settings page for Claude and AI by the address alone, with the project's tab shown."""
        js("window.sameDocument = true")
        js(f"history.replaceState(null, '', '/?project={code}#settings&p={'XYZ' if code == 'ABC' else 'ABC'}&s=claude')")      # the address already names the project the page is served for: no load of another page
        js(f"location.hash = '#settings&p={code}&s=claude'")
        self.until(js, f"location.hash.indexOf('p={code}') >= 0", f"the address names {code}")

    def project_tab_mounted(self, js, code):
        self.until(js, f"!!document.querySelector('[data-ask-tab]:not([data-ask-tab=all])') && document.querySelector('[data-ask-tab]:not([data-ask-tab=all])').textContent === '{code}'", f"the tab names {code}")

    def held_for(self, held, values):
        """read_new answers each project from `values` ({code: off_here}); a project in `held` waits for its gate, and says when its read is out."""
        gates = {c: threading.Event() for c in held}
        entered = {c: threading.Event() for c in held}

        def read(project=None):
            if project in gates:
                entered[project].set()
                gates[project].wait(20)
            return 200, {"ok": True, "on": True, "off_here": values.get(project, False)}
        self.svc.read_new = read
        for g in gates.values():
            self.addCleanup(g.set)
        return gates, entered

    def test_the_old_projects_value_is_cleared_while_the_next_is_read(self):
        """ABC has asking off and is shown; the address moves to XYZ, whose read is held: the line and the button for ABC are gone, not shown under XYZ's name."""
        gates, entered = self.held_for(["XYZ"], {"ABC": True, "XYZ": False})
        with chrome() as cdp:
            js = self.show(cdp)
            self.until(js, f"!!{LINE} && {LINE}.textContent === 'Asking is off for ABC.'", "ABC reads off")
            self.go(js, "XYZ")
            self.assertTrue(entered["XYZ"].wait(20), "the read for XYZ is out")
            self.project_tab_mounted(js, "XYZ")
            self.assertTrue(js("window.sameDocument === true"), "the same document")
            self.assertFalse(wait(lambda: js(f"!!{LINE} || !!document.querySelector('[data-ask-here]')"), 3), "nothing of ABC's value is shown while XYZ is read")
            gates["XYZ"].set()
            self.until(js, f"!!{LINE} && {LINE}.textContent === 'Asking is on for XYZ.'", "XYZ reads on")

    def test_a_late_answer_for_the_project_that_was_left_is_dropped(self):
        """The read for ABC is held; the address moves to XYZ, which answers at once (asking on); then ABC's answer (asking off) arrives. XYZ stays on."""
        gates, entered = self.held_for(["ABC"], {"ABC": True, "XYZ": False})
        with chrome() as cdp:
            self.sid = base.navigate(cdp, self.s.port, "#settings&p=ABC&s=claude")
            js = lambda e: cdp.js(e, self.sid)          # noqa: E731
            self.until(js, "!!document.querySelector('[data-ask-tab]')", "the tabs")
            self.assertTrue(entered["ABC"].wait(20), "the read for ABC is out")
            self.go(js, "XYZ")
            self.until(js, f"!!{LINE} && {LINE}.textContent === 'Asking is on for XYZ.'", "XYZ is read")
            self.assertTrue(js("window.sameDocument === true"), "the same document")
            gates["ABC"].set()
            self.assertFalse(wait(lambda: js(f"/off/.test({LINE}.textContent)"), 3), "ABC's late answer did not land on XYZ")
            self.assertEqual(js(f"{LINE}.textContent"), "Asking is on for XYZ.")
            self.assertEqual(js("document.querySelector('[data-ask-here]').getAttribute('aria-pressed')"), "true")

    def test_a_project_tab_that_stays_reads_again_for_the_next_project(self):
        """ABC has asking off and XYZ has it on; the address moves from ABC to XYZ and back with the tab kept: each is read again and shows its own value."""
        self.held_for([], {"ABC": True, "XYZ": False})
        with chrome() as cdp:
            js = self.show(cdp)
            self.until(js, f"!!{LINE} && {LINE}.textContent === 'Asking is off for ABC.'", "ABC reads off")
            self.go(js, "XYZ")
            self.until(js, f"!!{LINE} && {LINE}.textContent === 'Asking is on for XYZ.'", "XYZ reads on")
            self.assertEqual(js("document.querySelector('[data-ask-here]').textContent"), "Turn off asking")
            self.go(js, "ABC")
            self.until(js, f"!!{LINE} && {LINE}.textContent === 'Asking is off for ABC.'", "ABC reads off again")
            self.assertTrue(js("window.sameDocument === true"), "the same document")

    def test_the_undo_goes_when_the_next_change_begins(self):
        """A change is saved and offers Undo; the next change is refused: the Undo of the first is gone and the words say why."""
        real = self.svc.change_new
        with chrome() as cdp:
            js = self.show(cdp)
            js("document.querySelector('[data-ask-tab=all]').click()")
            self.until(js, "!!document.querySelector('[data-new-switch]')", "the switch")
            js("document.querySelector('[data-new-switch]').click()")
            self.until(js, "!!document.querySelector('[data-new-undo]')", "the Undo is offered")
            self.svc.change_new = lambda b: (409, self.svc.fail("busy"))
            self.addCleanup(setattr, self.svc, "change_new", real)
            js("document.querySelector('[data-new-switch]').click()")
            self.until(js, "!!document.querySelector('#ask-new-all .error')", "the words")
            self.assertFalse(js("!!document.querySelector('[data-new-undo]')"), "the first change's Undo is gone")

    def test_the_words_go_when_an_undo_begins(self):
        """A change is refused (words shown); a later change is saved and offers Undo; the Undo then being saved clears nothing it should not and the old words stay gone."""
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
            self.until(js, "!!document.querySelector('[data-new-undo]')", "saved, Undo offered")
            self.assertFalse(js("!!document.querySelector('#ask-new-all .error')"), "the old words are gone")


if __name__ == "__main__":
    unittest.main()
