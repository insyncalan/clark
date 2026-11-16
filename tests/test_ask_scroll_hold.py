"""Row 1219: scrolling over the ask panel never moves the page behind it.

Run (browser test, headless Chrome through the shared harness): python3 dev/run_tests.py test_ask_scroll_hold
At 1400 and 900 px, with the page made taller than the window and scrolled to the middle: real wheel events over the panel, in
an empty panel, in a panel whose answer is taller than the log at its top and at its bottom, leave the page's scroll position
unchanged; the keys Space, Page Up, Page Down, Home, End and the arrows, with focus in the panel, leave it too (and move the
answers when they overflow); a sideways wheel (the Back and Forward swipe, item 1136) is not stopped. A source check holds the
CSS on the panel, its answers and saved chats, the Peek and the other panels over the page, and that none sets a sideways containment.
"""
import re
import time
import unittest

from _paths import SRC
from test_report_editor import Base
from test_ask_panel import Stub
from test_server import chrome

SETTLE = "document.querySelector('#ask-box') && !document.querySelector('#ask-send').disabled"
LONG = "\n\n".join(f"Line {n}: the pilot goes live in March, and the plan holds." for n in range(120))
PAGE_Y = "Math.round(window.scrollY)"


class Hold(Base):
    def setUp(self):
        super().setUp()
        self.stub = Stub()
        self.s.httpd.ask = self.stub

    def open_panel(self, cdp, width):
        p = self.visit(cdp)
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]}, p.sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        p.js("(() => { const s = document.createElement('div'); s.id = 'spacer-1219'; s.style.height = '4000px'; document.body.appendChild(s); window.scrollTo(0, 600); })()")
        p.key("/", code="Slash", vk=191)
        p.until("!!document.querySelector('#ask-panel')", "the panel opened on /")
        p.until(SETTLE, "the panel is ready")
        self.assertEqual(p.js(PAGE_Y), 600, "the page can scroll (the test's own check)")
        return p

    def focus_panel(self, p):
        """Put the focus on the panel itself and wait until it stays there: the panel gives the focus to its own box a moment after it opens
        (on a slow runner after this test's first focus), and a key then goes to the box and the page, not to the panel under test."""
        for _ in range(20):
            p.js("document.querySelector('#ask-panel').focus()")
            time.sleep(0.25)
            if p.js("document.activeElement && document.activeElement.id") == "ask-panel":
                time.sleep(0.25)
                if p.js("document.activeElement && document.activeElement.id") == "ask-panel":
                    return
        self.fail("the focus would not stay on the panel")

    def wheel(self, p, dy, dx=0, over="#ask-panel", at=None):
        """A real wheel turn over the centre of `over`: the pointer is moved there first (a bare mouseWheel does nothing in this
        headless Chrome), then the scrolling is waited out (settle)."""
        x, y = at or p.js(f"(() => {{ const r = document.querySelector({over!r}).getBoundingClientRect(); return [Math.round(r.left + r.width / 2), Math.round(r.top + r.height / 2)]; }})()")
        p.cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y}, p.sid)
        p.cdp.call("Input.dispatchMouseEvent", {"type": "mouseWheel", "x": x, "y": y, "deltaX": dx, "deltaY": dy, "pointerType": "mouse"}, p.sid)
        self.settle(p)

    def settle(self, p):
        """Wait out smooth scrolling: until neither the page nor the log has moved for 300 ms."""
        read = "(() => { const l = document.querySelector('#ask-log'); return [Math.round(window.scrollY), l ? Math.round(l.scrollTop) : 0]; })()"
        last, still, end = None, 0, time.time() + 5
        while still < 3 and time.time() < end:
            time.sleep(0.1)
            now = p.js(read)
            still = still + 1 if now == last else 0
            last = now

    def scrolled_log(self, p, where):
        p.js(f"(() => {{ const l = document.querySelector('#ask-log'); l.scrollTop = {where}; }})()")
        self.settle(p)

    def test_the_wheel_used_here_really_scrolls_the_page_outside_the_panel(self):
        """The control for every 'the page never moves' check below: the same wheel, over the page beside the panel, does move it."""
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.open_panel(cdp, width)
                self.wheel(p, 300, at=(40, 450))
                self.assertGreater(p.js(PAGE_Y), 600, f"{width}: a wheel over the page outside the panel scrolls it")

    def test_wheel_over_an_empty_panel_never_moves_the_page(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.open_panel(cdp, width)
                for dy in (-300, 300, -1200, 1200):
                    self.wheel(p, dy)
                    self.assertEqual(p.js(PAGE_Y), 600, f"{width}: wheel {dy} over the empty panel moved the page")

    def test_wheel_over_a_long_answer_at_its_top_and_bottom_never_moves_the_page(self):
        self.stub.answer = LONG
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.open_panel(cdp, width)
                p.js("document.querySelector('#ask-box').focus()")
                p.type("How does the pilot look?")
                p.js("document.querySelector('#ask-send').click()")
                p.until("document.querySelectorAll('#ask-log .ask-turn.assistant').length > 0", "the answer is in")
                self.assertTrue(p.js("(() => { const l = document.querySelector('#ask-log'); return l.scrollHeight > l.clientHeight + 200; })()"), "the answer overflows the log")
                self.scrolled_log(p, 0)
                for dy in (-400, -1200):
                    self.wheel(p, dy, over="#ask-log")
                    self.assertEqual(p.js(PAGE_Y), 600, f"{width}: wheel {dy} at the top of the answer moved the page")
                self.wheel(p, 300, over="#ask-log")
                self.assertGreater(p.js("document.querySelector('#ask-log').scrollTop"), 0, f"{width}: the answer itself still scrolls")
                self.assertEqual(p.js(PAGE_Y), 600)
                self.scrolled_log(p, 999999)
                for dy in (400, 1200):
                    self.wheel(p, dy, over="#ask-log")
                    self.assertEqual(p.js(PAGE_Y), 600, f"{width}: wheel {dy} at the bottom of the answer moved the page")

    def test_keys_in_the_panel_never_move_the_page(self):
        self.stub.answer = LONG
        keys = [("PageDown", "PageDown", 34), ("PageUp", "PageUp", 33), ("End", "End", 35), ("Home", "Home", 36),
                ("ArrowDown", "ArrowDown", 40), ("ArrowUp", "ArrowUp", 38), (" ", "Space", 32)]
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.open_panel(cdp, width)
                self.focus_panel(p)
                for key, code, vk in keys:                     # the empty panel
                    p.key(key, code=code, vk=vk)
                    self.settle(p)
                    self.assertEqual(p.js(PAGE_Y), 600, f"{width}: {code} in the empty panel moved the page")
                p.js("document.querySelector('#ask-box').focus()")
                p.type("How does the pilot look?")
                p.js("document.querySelector('#ask-send').click()")
                p.until("document.querySelectorAll('#ask-log .ask-turn.assistant').length > 0", "the answer is in")
                self.scrolled_log(p, 0)
                self.focus_panel(p)
                p.key("PageDown", code="PageDown", vk=34)
                self.settle(p)
                self.assertGreater(p.js("document.querySelector('#ask-log').scrollTop"), 100, f"{width}: Page Down scrolls the answers")
                p.key("End", code="End", vk=35)
                self.settle(p)
                self.assertGreater(p.js("(() => { const l = document.querySelector('#ask-log'); return l.scrollHeight - l.clientHeight - l.scrollTop; })()") , -2)
                self.assertLess(p.js("(() => { const l = document.querySelector('#ask-log'); return l.scrollHeight - l.clientHeight - l.scrollTop; })()"), 2, f"{width}: End goes to the bottom of the answers")
                for key, code, vk in keys:                     # at the bottom, then every key again
                    p.key(key, code=code, vk=vk)
                    self.settle(p)
                    self.assertEqual(p.js(PAGE_Y), 600, f"{width}: {code} over the answers moved the page")

    def test_a_sideways_wheel_is_left_to_the_browser(self):
        with chrome() as cdp:
            p = self.open_panel(cdp, 1400)
            got = p.js("(() => { const t = document.querySelector('#ask-panel'); const out = {};"
                       " for (const [n, dx, dy] of [['side', 60, 0], ['mostly side', 80, 10], ['up', 0, -60], ['down', 0, 60]]) {"
                       " const e = new WheelEvent('wheel', { deltaX: dx, deltaY: dy, bubbles: true, cancelable: true }); t.dispatchEvent(e); out[n] = e.defaultPrevented; }"
                       " return out; })()")
            self.assertFalse(got["side"], "a sideways swipe (Back and Forward, item 1136) is not stopped")
            self.assertFalse(got["mostly side"])
            self.assertTrue(got["up"] and got["down"], "an up or down wheel in an empty panel is stopped")


class Source(unittest.TestCase):
    CSS = (SRC / "clark" / "page" / "shell.css").read_text(encoding="utf-8") + (SRC / "clark" / "page" / "src" / "edit" / "edit.css").read_text(encoding="utf-8")

    def rule(self, selector):
        m = re.search(r"(?m)^" + re.escape(selector) + r"\s*\{([^}]*)\}", self.CSS)
        self.assertTrue(m, selector)
        return m.group(1)

    def test_every_panel_over_the_page_contains_vertical_overscroll(self):
        for sel in (".peek", ".pk-body", ".ad-scrim", ".dlg"):
            self.assertIn("overscroll-behavior-y: contain", self.rule(sel), sel)
        m = re.search(r"(?m)^\.ask-panel, \.ask-hist, \.ask-log \{([^}]*)\}", self.CSS)
        self.assertTrue(m and "overscroll-behavior-y: contain" in m.group(1), "ask panel, answers and chats")

    def test_none_sets_a_sideways_containment(self):
        self.assertNotRegex(self.CSS, r"overscroll-behavior(-x)?\s*:\s*(none|contain)")

    def test_the_peek_and_the_ask_panel_use_the_hold(self):
        for f in ("components/Peek.jsx", "edit/AskPanel.jsx"):
            self.assertIn("holdScroll(", (SRC / "clark" / "page" / "src" / f).read_text(encoding="utf-8"), f)


if __name__ == "__main__":
    unittest.main()
