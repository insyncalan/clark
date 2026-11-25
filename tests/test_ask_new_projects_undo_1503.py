"""Row 1503 AP2 and AP4, the two checks the redo found missing: the Undo of the starting value for new projects runs at 1400 as well as at 900, and the project's own
button is absent on the All projects tab. Classic look (the rows are drawn only there). Fictional data.

Run: python3 dev/run_tests.py test_ask_new_projects_undo_1503        (needs Chrome; run only while the machine's load is under 70)
"""
import test_ask_new_projects_ui as ui
from test_server import chrome


class Undo(ui.Settings):
    def switch_state(self, js):
        return js("document.querySelector('[data-new-switch]').getAttribute('aria-checked')")

    def bodies(self):
        return self.svc.read_new(), self.svc.read_new("ABC")

    def open_all_tab(self, cdp, w):
        js = self.show(cdp)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
        js("document.querySelector('[data-ask-tab=all]').click()")
        self.until(js, "!!document.querySelector('[data-new-switch]')", "the row's switch")
        self.until(js, "document.documentElement.scrollWidth <= window.innerWidth", f"no sideways scroll at {w}")
        return js

    def test_turning_new_projects_off_changes_no_project_and_undo_puts_it_back_at_1400_and_900(self):
        for w in ui.WIDTHS:
            with self.subTest(width=w):
                self.setUp()                       # a fresh service and server for this width: nothing leaks between widths
                with chrome() as cdp:
                    js = self.open_all_tab(cdp, w)
                    before = self.bodies()
                    self.assertTrue(before[0][1]["on"])
                    js("document.querySelector('[data-new-switch]').click()")
                    self.until(js, "document.querySelector('[data-new-switch]').getAttribute('aria-checked') === 'false' && !!document.querySelector('[data-new-undo]')", "off, with Undo")
                    self.assertFalse(self.svc.read_new()[1]["on"])
                    self.assertFalse(self.svc.read_new("ABC")[1]["off_here"], "a project that exists is not changed")
                    self.assertEqual(js("document.querySelector('[data-new-undo]').innerText"), "Undo")
                    js("document.querySelector('[data-new-undo]').click()")
                    self.until(js, "document.querySelector('[data-new-switch]').getAttribute('aria-checked') === 'true' && !document.querySelector('[data-new-undo]')", "Undo puts it back")
                    self.assertTrue(self.svc.read_new()[1]["on"])
                    self.assertFalse(self.svc.read_new("ABC")[1]["off_here"], "Undo leaves the project's own button alone")
                    self.assertEqual(self.bodies(), before, "after Undo the service answers exactly as before the click")

    def test_turning_new_projects_on_and_then_undo_puts_it_back_off_at_1400_and_900(self):
        for w in ui.WIDTHS:
            with self.subTest(width=w):
                self.setUp()
                code, _ = self.svc.change_new({"on": False})
                self.assertEqual(code, 200, "the start: asking for new projects is off")
                with chrome() as cdp:
                    js = self.open_all_tab(cdp, w)
                    self.until(js, "document.querySelector('[data-new-switch]').getAttribute('aria-checked') === 'false'", "the page shows it off")
                    before = self.bodies()
                    self.assertFalse(before[0][1]["on"])
                    js("document.querySelector('[data-new-switch]').click()")
                    self.until(js, "document.querySelector('[data-new-switch]').getAttribute('aria-checked') === 'true' && !!document.querySelector('[data-new-undo]')", "on, with Undo")
                    self.assertTrue(self.svc.read_new()[1]["on"])
                    js("document.querySelector('[data-new-undo]').click()")
                    self.until(js, "document.querySelector('[data-new-switch]').getAttribute('aria-checked') === 'false' && !document.querySelector('[data-new-undo]')", "Undo puts it back off")
                    self.assertFalse(self.svc.read_new()[1]["on"])
                    self.assertFalse(self.svc.read_new("ABC")[1]["off_here"])
                    self.assertEqual(self.bodies(), before, "after Undo the service answers exactly as before the click")

    def test_the_projects_own_button_is_not_on_the_all_projects_tab_at_1400_and_900(self):
        words = ("[...document.querySelectorAll('section.setting')].filter(s => s.id !== 'ask-usage-all').some(s => /Turn (on|off) asking|Asking is (on|off) for /.test(s.textContent))")
        for w in ui.WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                self.setUp()
                js = self.show(cdp)
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                self.until(js, "!!document.querySelector('[data-ask-here]')", "control: the project tab has its button")
                self.assertTrue(js(words), "control: the words are on the project tab")
                js("document.querySelector('[data-ask-tab=all]').click()")
                self.until(js, "!!document.querySelector('[data-new-switch]')", "the All projects tab drew")
                self.assertFalse(js("!!document.querySelector('[data-ask-here], #ask-here-state, #ask-new-here')"), "the project's button, line and note are on a project tab only")
                self.assertFalse(js("[...document.querySelectorAll('button, [role=button], a, input')].some(e => /Turn (on|off) asking/i.test(e.textContent + ' ' + (e.getAttribute('aria-label') || '')))"), "no button of the project's, whatever its attributes")
                self.assertFalse(js(words), "no line that says asking is on or off for a project")
                self.assertEqual(js("[...document.querySelectorAll('#ask-new-all button, #ask-new-all [role=switch]')].map(e => e.hasAttribute('data-new-switch')).join()"), "true", "the new-projects card has the one switch and no other button")
                self.assertEqual(js("document.querySelectorAll('#ask-new-all [role=switch]').length"), 1)
                self.assertEqual(js("JSON.stringify([...document.querySelectorAll('#ask-all button, #ask-all [role=switch]')].filter(e => !e.closest('#ask-new-all')).length)"), "0", "the All card's own part has no other button")


for _name in dir(ui.Settings):      # the base class's own tests run in its own file
    if _name.startswith("test") and _name not in Undo.__dict__:
        setattr(Undo, _name, None)
