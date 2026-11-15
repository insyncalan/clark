"""Row 1215: the ask clark question box with a message of several lines.

Run: python3 dev/run_tests.py test_ask_box_grow
At 1400 and 900 px, and with the panel at its narrowest: the box is one line high when empty, two lines have room above the first line and
below the last (padding both sides, nothing hidden), six lines stop at the cap (five lines) and scroll inside, the Ask button stays at the
bottom right and level with the box's foot, the focus ring is drawn outside the box, and Enter / Shift+Enter work as before.
"""
import json
import unittest

from test_report_editor import Base
from test_ask_panel import Stub
from test_server import chrome

SETTLE = "document.querySelector('#ask-box') && !document.querySelector('#ask-send').disabled"
PUT = "(function(v){var b=document.querySelector('#ask-box');b.focus();b.value=v;b.dispatchEvent(new Event('input',{bubbles:true}));})(%s)"
READ = ("JSON.stringify((function(){var b=document.querySelector('#ask-box'),r=b.getBoundingClientRect(),s=document.querySelector('#ask-send').getBoundingClientRect(),"
        "f=document.querySelector('.ask-form').getBoundingClientRect(),cs=getComputedStyle(b);"
        "return {h:r.height,top:r.top,bottom:r.bottom,right:r.right,pt:parseFloat(cs.paddingTop),pb:parseFloat(cs.paddingBottom),lh:parseFloat(cs.lineHeight),"
        "sh:b.scrollHeight,ch:b.clientHeight,oy:cs.overflowY,sb:s.bottom,sr:s.right,sw:s.width,formTop:f.top,formRight:f.right,formBottom:f.bottom};})())")


class Grow(Base):
    def setUp(self):
        super().setUp()
        self.stub = Stub()
        self.s.httpd.ask = self.stub

    def opened(self, cdp, width, narrow):
        p = self.visit(cdp)
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]}, p.sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        if narrow:                       # the width the grip keeps in this browser: the panel's smallest
            p.js("localStorage.setItem('clark.askWidth', '320')")
            p.reload()
        p.key("/", code="Slash", vk=191)
        p.until("!!document.querySelector('#ask-panel')", "the panel opened on /")
        p.until(SETTLE, "the panel is ready")
        if narrow:
            self.assertEqual(p.js("document.querySelector('#ask-panel').getBoundingClientRect().width"), 320)
        return p

    def read(self, p):
        return json.loads(p.js(READ))

    def each(self):
        return [(w, n) for w in (1400, 900) for n in (False, True)]

    def test_empty_is_one_line_two_lines_have_room_six_lines_scroll_at_the_cap(self):
        for width, narrow in self.each():
            with chrome() as cdp:
                what = f"{width} px, {'narrowest panel' if narrow else 'default panel'}"
                p = self.opened(cdp, width, narrow)
                one = self.read(p)
                self.assertEqual(one["h"], 44, f"{what}: one line high when empty")
                self.assertGreater(one["pt"], 0)
                p.js(PUT % json.dumps("one\ntwo"))
                p.until("document.querySelector('#ask-box').getBoundingClientRect().height > 50", f"{what}: two lines made the box taller")
                two = self.read(p)
                self.assertEqual(two["h"], 2 * two["lh"] + two["pt"] + two["pb"] + 2, f"{what}: two lines plus padding plus border ({two})")
                self.assertGreaterEqual(two["pt"], 8, f"{what}: room above the first line")
                self.assertGreaterEqual(two["pb"], 8, f"{what}: room below the last line")
                self.assertGreaterEqual(two["lh"], 20, f"{what}: a sensible line height")
                self.assertEqual(two["sh"], two["ch"], f"{what}: nothing of the two lines is hidden")
                self.assertAlmostEqual(two["sb"], two["bottom"], delta=1, msg=f"{what}: Ask stays level with the box foot")
                self.assertGreater(two["sr"], two["right"], f"{what}: Ask is to the right of the box")
                self.assertLessEqual(two["sr"], two["formRight"], f"{what}: Ask is inside the panel")
                self.assertLessEqual(two["sb"], two["formBottom"], f"{what}: Ask is in reach")
                p.js(PUT % json.dumps("\n".join("line %d" % i for i in range(6))))
                p.until("document.querySelector('#ask-box').scrollHeight > document.querySelector('#ask-box').clientHeight", f"{what}: six lines scroll")
                six = self.read(p)
                self.assertEqual(six["h"], 5 * six["lh"] + six["pt"] + six["pb"] + 2, f"{what}: stops at five lines ({six})")
                self.assertIn(six["oy"], ("auto", "scroll"), f"{what}: scrolls inside")
                self.assertLessEqual(six["sb"], six["formBottom"], f"{what}: Ask in reach at the cap")
                self.assertGreater(six["top"], six["formTop"], f"{what}: the box stays inside the form")
                p.js(PUT % json.dumps(""))
                p.until("document.querySelector('#ask-box').getBoundingClientRect().height === 44", f"{what}: back to one line when emptied")

    def test_a_long_wrapped_line_grows_the_box_too(self):
        for width, narrow in self.each():
            with chrome() as cdp:
                what = f"{width} px, {'narrowest panel' if narrow else 'default panel'}"
                p = self.opened(cdp, width, narrow)
                p.js(PUT % json.dumps("a very long question " * 5))
                p.until("document.querySelector('#ask-box').getBoundingClientRect().height > 50", f"{what}: wrapping made the box taller")
                r = self.read(p)
                self.assertEqual(r["sh"], r["ch"] if r["h"] < 132 else r["sh"], what)
                self.assertLessEqual(r["h"], 132)

    def test_the_focus_ring_is_outside_the_text(self):
        with chrome() as cdp:
            p = self.opened(cdp, 1400, False)
            p.js(PUT % json.dumps("one\ntwo"))
            p.until("document.querySelector('#ask-box').getBoundingClientRect().height > 50", "grown")
            p.until("/0px 0px 0px [1-9]/.test(getComputedStyle(document.querySelector('#ask-box')).boxShadow)", "the ring settled")
            ring = p.js("getComputedStyle(document.querySelector('#ask-box')).boxShadow")
            self.assertRegex(ring, r"0px 0px 0px [1-9][\d.]*px", "the ring is a shadow outside the border")
            self.assertEqual(p.js("getComputedStyle(document.querySelector('#ask-box')).outlineStyle"), "none")
            self.assertGreaterEqual(p.js("parseFloat(getComputedStyle(document.querySelector('#ask-box')).paddingLeft)"), 12)

    def test_enter_sends_and_shift_enter_adds_a_line_as_before(self):
        with chrome() as cdp:
            p = self.opened(cdp, 1400, False)
            p.js(PUT % json.dumps("first"))
            p.js("document.querySelector('#ask-box').setSelectionRange(5,5)")
            for kind in ("keyDown", "keyUp"):
                cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13, "modifiers": 8,
                                                    **({"text": "\r"} if kind == "keyDown" else {})}, p.sid)
            p.until("document.querySelector('#ask-box').value.indexOf('\\n') > 0", "Shift+Enter added a line")
            self.assertFalse([c for c in self.stub.calls if c[0] == "ask"], "and nothing was sent")
            p.key("Enter", code="Enter", vk=13)
            p.until("!document.querySelector('#ask-box').value", "Enter sent it")
            self.assertTrue([c for c in self.stub.calls if c[0] == "ask"])


if __name__ == "__main__":
    unittest.main()
