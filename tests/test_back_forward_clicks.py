"""Row 1136: real mouse clicks on Work items, Milestones, then a use case move the address one entry each, and Back and Forward step through them.

Run: python3 dev/run_tests.py test_back_forward_clicks
The served page (a real server over a real store, fictional data) at 1400 and 900 px. history.back() and history.forward() are what
the mouse's buttons and the trackpad swipe call.
"""
import unittest
from unittest import mock

from _demo import DemoStore
import _testpage as testpage
from _real_server import real_server

from clark import server as sv
from test_page import navigate
from test_server import chrome, wait


class Clicks(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.demo.action(description="Agree the cut-over plan", owner="Sam Rivers")
        self.s = real_server(self.demo.store.path, self.demo.store.data_for, page_html=lambda: testpage.html())
        self.addCleanup(self.s.close)
        quiet = mock.patch.object(sv.LOG, "disabled", True)
        quiet.start()
        self.addCleanup(quiet.stop)

    def js(self, expr):
        return self.cdp.js(expr, self.sid)

    def until(self, expr, what, seconds=10):
        self.assertTrue(wait(lambda: self.js(expr), seconds), f"{what}: {expr}")

    def press(self, sel):
        """A real mouse click at the middle of `sel`, as a person makes it."""
        x, y = self.js(f"(function(){{var e=document.querySelector({sel!r}); e.scrollIntoView({{block:'center'}});"
                       "var r=e.getBoundingClientRect(); return [r.left+r.width/2, r.top+r.height/2];})()")
        self.cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y}, self.sid)
        for kind in ("mousePressed", "mouseReleased"):
            self.cdp.call("Input.dispatchMouseEvent", {"type": kind, "x": x, "y": y, "button": "left", "clickCount": 1,
                                                       "buttons": 1 if kind == "mousePressed" else 0}, self.sid)

    def test_typing_in_the_filter_line_adds_no_entry_and_back_still_leaves_the_page(self):
        with chrome() as cdp:
            self.cdp = cdp
            self.sid = navigate(cdp, self.s.port, "#dashboard&p=ABC")
            self.until("document.documentElement.dataset.ready === '1' && !!document.querySelector('h1') && "
                       "document.querySelector('h1').textContent !== 'Loading'", "the page drew")
            self.press("[data-view=work]")
            self.until("location.hash.startsWith('#work') && !!document.getElementById('fline-input')", "Work items" + self.js("document.body.innerText.slice(0,300)"))
            n = self.js("history.length")
            self.press("#fline-input")
            for ch in "owner":
                cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "text": ch, "key": ch}, self.sid)
                cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": ch}, self.sid)
            self.assertEqual(self.js("history.length"), n, "no step per key")
            self.press("[data-view=milestones]")
            self.until("location.hash.startsWith('#milestones')", "Milestones")
            self.press("[data-view=work]")
            self.until("location.hash.startsWith('#work')", "Work items again")
            self.assertEqual(self.js("history.length"), n + 2)
            self.js("history.back()")
            self.until("location.hash.startsWith('#milestones')", "Back to Milestones")
            self.js("history.back()")
            self.until("location.hash.startsWith('#work')", "Back to Work items")
            self.js("history.back()")
            self.until("location.hash.startsWith('#dashboard')", "Back to the Dashboard")

    def test_clicks_push_one_entry_each_and_back_and_forward_step_through_them(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                self.cdp = cdp
                self.sid = navigate(cdp, self.s.port, "#dashboard&p=ABC")
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                self.until("document.documentElement.dataset.ready === '1' && !!document.querySelector('h1') && "
                           "document.querySelector('h1').textContent !== 'Loading'", "the page drew")
                n = self.js("history.length")
                self.press("[data-view=work]")
                self.until("location.hash.startsWith('#work')", "Work items")
                self.press("[data-view=milestones]")
                self.until("location.hash.startsWith('#milestones')", "Milestones")
                self.press("[data-view=usecases]")
                self.until("location.hash.startsWith('#usecases')", "Use cases")
                self.until("!!document.querySelector('.ucl-go')", "a use case in the list")
                self.press(".ucl-go")
                self.until("location.hash.includes('&uc=')", "a use case")
                self.assertEqual(self.js("history.length"), n + 4, "each click added one entry")
                for want in ("#usecases", "#milestones", "#work", "#dashboard"):
                    self.js("history.back()")
                    self.until(f"location.hash.startsWith('{want}') && !location.hash.includes('&uc=')", f"Back to {want}")
                    self.until(f"document.querySelector('.tab[aria-selected=true]').dataset.view === '{want[1:]}'", f"{want} drawn")
                for want in ("#work", "#milestones", "#usecases"):
                    self.js("history.forward()")
                    self.until(f"location.hash.startsWith('{want}')", f"Forward to {want}")
                    self.until(f"document.querySelector('.tab[aria-selected=true]').dataset.view === '{want[1:]}'", f"{want} drawn")
                self.js("history.forward()")
                self.until("location.hash.includes('&uc=')", "Forward to the use case")
                self.assertEqual(self.js("history.length"), n + 4, "Back and Forward add nothing")


if __name__ == "__main__":
    unittest.main()
