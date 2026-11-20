"""Row 1279 (Classic): the Settings Feedback card draws each label above its own box, both boxes the card's content width, the message
box several lines tall and both boxes in the one clark input look. Computed styles at 1400 and 900, light and dark.

Run: python3 dev/run_tests.py test_feedback_card_1279
The card runs in headless Chrome on the harness of test_feedback_tab.py with the Classic Theme layered in <style id="theme">.
"""
import json
import unittest

from clark import theme

import test_feedback_tab as base
from test_server import chrome  # noqa: F401  (the harness: this file drives Chrome through the base class above, so the tier reader sees it)

MEASURE = """(function () {
  const r = (s) => document.querySelector(s).getBoundingClientRect();
  const cs = (s) => getComputedStyle(document.querySelector(s));
  const card = document.querySelector('#feedback'), c = getComputedStyle(card);
  const inner = card.getBoundingClientRect().width - parseFloat(c.paddingLeft) - parseFloat(c.paddingRight)
    - parseFloat(c.borderLeftWidth) - parseFloat(c.borderRightWidth);
  const lab = (f) => r('label[for="' + f + '"]'), box = (f) => r('#' + f);
  const look = (s) => { const x = cs(s); return {radius: x.borderTopLeftRadius, color: x.borderTopColor, width: x.borderTopWidth, bg: x.backgroundColor, font: x.fontSize, fam: x.fontFamily}; };
  return JSON.stringify({
    inner: inner,
    msgGap: box('feedback-message').top - lab('feedback-message').bottom,
    conGap: box('feedback-contact').top - lab('feedback-contact').bottom,
    betweenGap: lab('feedback-contact').top - box('feedback-message').bottom,
    msgW: box('feedback-message').width, conW: box('feedback-contact').width,
    msgH: box('feedback-message').height, lineH: parseFloat(cs('#feedback-message').lineHeight) || 20,
    labelDisplay: cs('label[for="feedback-message"]').display,
    msg: look('#feedback-message'), con: look('#feedback-contact'),
  });
})()"""


class Classic(base.InBrowser):
    @classmethod
    def setUpClass(cls):
        base.test_page_html()
        html = base._PAGE["html"]
        css = theme.css("prototype-2.0").replace("</style", "<\\/style")
        base._PAGE["html"] = html.replace("</style></head>", f"</style><style id=\"theme\">\n{css}\n</style></head>", 1)
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        base._PAGE.pop("html", None)

    def measure(self, width, dark=False):
        self.cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
        self.js(f"document.documentElement.dataset.theme = {json.dumps('dark' if dark else 'light')}")
        self.js("T.mount('1.3.0', 'Win32'); document.getElementById('root').classList.add('set-cards')")
        self.assertTrue(base.wait(lambda: self.js("!!document.querySelector('#feedback-message')"), 5), "the card is drawn")
        self.assertTrue(self.js("!!document.getElementById('theme')"), "the Classic layer is on")
        return json.loads(self.js(MEASURE))

    def test_each_label_sits_above_its_own_box_with_a_gap_at_1400_and_900(self):
        for w in (1400, 900):
            with self.subTest(width=w):
                m = self.measure(w)
                self.assertEqual(m["labelDisplay"], "block")
                self.assertGreaterEqual(m["msgGap"], 4, m)
                self.assertGreaterEqual(m["conGap"], 4, m)
                self.assertGreaterEqual(m["betweenGap"], 12, m)

    def test_both_boxes_are_the_full_width_of_the_card_at_1400_and_900(self):
        for w in (1400, 900):
            with self.subTest(width=w):
                m = self.measure(w)
                self.assertAlmostEqual(m["msgW"], m["inner"], delta=1, msg=m)
                self.assertAlmostEqual(m["conW"], m["inner"], delta=1, msg=m)

    def test_the_message_box_is_several_lines_tall_at_1400_and_900(self):
        for w in (1400, 900):
            with self.subTest(width=w):
                m = self.measure(w)
                self.assertGreaterEqual(m["msgH"], 4 * m["lineH"], m)

    def test_the_message_box_has_the_contact_boxs_clark_input_look_light_and_dark(self):
        for dark in (False, True):
            with self.subTest(dark=dark):
                m = self.measure(1400, dark)
                self.assertEqual(m["msg"], m["con"], m)
                self.assertEqual(m["msg"]["radius"], "8px", m)
                self.assertEqual(m["msg"]["width"], "1px", m)


HINT = """(function () {
  const h = document.querySelector('[data-feedback-hint]');
  const probe = document.createElement('i'); probe.style.color = 'var(--text-muted)'; document.body.appendChild(probe);
  const want = getComputedStyle(probe).color; probe.remove();
  const b = document.querySelector('[data-feedback-copy]');
  if (!h) return JSON.stringify({present: false, disabled: b.disabled});
  const c = getComputedStyle(h), hr = h.getBoundingClientRect(), br = b.getBoundingClientRect();
  return JSON.stringify({present: true, disabled: b.disabled, text: h.textContent, size: c.fontSize, color: c.color, want: want,
    below: hr.top >= br.bottom - 1, visible: hr.width > 0 && hr.height > 0});
})()"""
FILL = """(function () {
  const t = document.querySelector('#feedback-message'); t.value = %s; t.dispatchEvent(new Event('input', {bubbles: true}));
})()"""


class Hint(Classic):
    def hint(self, width, text=""):
        self.measure(width)
        if text:
            self.js(FILL % json.dumps(text))
            self.settle()
        return json.loads(self.js(HINT))

    def test_the_muted_line_under_the_disabled_copy_button_at_1400_and_900(self):
        for w in (1400, 900):
            with self.subTest(width=w):
                m = self.hint(w)
                self.assertTrue(m["disabled"], m)
                self.assertTrue(m["present"], m)
                self.assertEqual(m["text"], self.val("T.logic.NOTHING_YET"), m)
                self.assertEqual(m["size"], "13px", m)
                self.assertEqual(m["color"], m["want"], m)
                self.assertTrue(m["below"] and m["visible"], m)

    def test_the_line_is_gone_when_the_button_is_enabled_at_1400_and_900(self):
        for w in (1400, 900):
            with self.subTest(width=w):
                m = self.hint(w, "the page is slow")
                self.assertFalse(m["disabled"], m)
                self.assertFalse(m["present"], m)


class Cards(base.InBrowser):
    def test_cards_has_no_line_at_1400_and_900(self):
        for w in (1400, 900):
            with self.subTest(width=w):
                self.cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                self.js("T.mount('1.3.0', 'Win32')")
                self.assertTrue(base.wait(lambda: self.js("!!document.querySelector('#feedback-message')"), 5), "the card is drawn")
                self.assertFalse(self.js("!!document.getElementById('theme')"))
                m = json.loads(self.js(HINT))
                self.assertTrue(m["disabled"], m)
                self.assertFalse(m["present"], m)


if __name__ == "__main__":
    unittest.main()
