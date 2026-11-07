"""Row 946: the small primary buttons (.pk-btn.pri) take the aqua pill like .btn.pri, and the focus rings of .again and .tpl-band-btn are
visible. Text is 4.5:1 or more, a focus ring 3:1 or more against what it sits on, at 1400 and 900 px, light and dark.

Run: python3 dev/run_tests.py test_dark_primary
Headless Chrome (required: fails, never skips, without it). The colours are computed in the page from the real styles.
"""
import json
import re
import unittest

from _paths import ROOT
from test_report_editor import Base
from test_server import chrome

PAGE = ROOT / "src" / "clark" / "page"
CSS_FILES = (PAGE / "shell.css", PAGE / "src" / "edit" / "edit.css")
CASES = [(w, s) for w in (1400, 900) for s in ("light", "dark")]

# Colour maths in the page: every colour goes through a canvas so any CSS colour syntax reads; a gradient counts at its worst stop.
MEASURE = r"""(function () {
  const cv = document.createElement('canvas'); cv.width = cv.height = 1; const x = cv.getContext('2d', {willReadFrequently: true});
  const parse = (c) => { x.clearRect(0, 0, 1, 1); x.fillStyle = '#000'; x.fillStyle = c; x.fillRect(0, 0, 1, 1); const d = x.getImageData(0, 0, 1, 1).data; return [d[0], d[1], d[2], d[3] / 255]; };
  const over = (t, b) => [0, 1, 2].map((i) => t[i] * t[3] + b[i] * (1 - t[3])).concat([1]);
  const lum = (c) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]); };
  const ratio = (a, b) => { const p = lum(a), q = lum(b); return (Math.max(p, q) + 0.05) / (Math.min(p, q) + 0.05); };
  const stops = (img) => /gradient/.test(img) ? (img.match(/(?:rgba?|color|oklab|oklch|lab|lch)\([^)]*\)/g) || []).map(parse) : [];
  // the colours that can sit under `el`'s own box (self true) or just around it
  function colours(el, self) {
    const chain = []; for (let e = self ? el : el.parentElement; e; e = e.parentElement) chain.unshift(e);
    let base = [[255, 255, 255, 1]];
    for (const e of chain) {
      const cs = getComputedStyle(e), bg = parse(cs.backgroundColor), st = stops(cs.backgroundImage), next = [];
      for (const b of base) { const solid = over(bg, b); if (st.length) st.forEach((s) => next.push(over(s, solid))); else next.push(solid); }
      base = next;
    }
    return base;
  }
  const worst = (fg, bgs) => Math.min.apply(null, bgs.map((b) => ratio(over(fg, b), b)));
  return (sel) => {
    const el = document.querySelector(sel), cs = getComputedStyle(el);
    const around = colours(el, false), fills = colours(el, true);
    return {text: worst(parse(cs.color), fills), ring: cs.outlineStyle === 'none' ? null : worst(parse(cs.outlineColor), around),
            ringWidth: parseFloat(cs.outlineWidth), image: cs.backgroundImage.slice(0, 60)};
  };
})()"""


def css_blocks(path):
    text = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.S)
    return [(m.group(1).strip(), m.group(2)) for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", text)]


class Source(unittest.TestCase):
    def test_no_rule_pairs_the_navy_with_the_dark_theme_text_on_brand(self):
        """Dark text-on-brand is two hex digits from the navy: 1.02 to 1. The two are never set together."""
        for path in CSS_FILES:
            for sel, body in css_blocks(path):
                self.assertFalse("--brand-navy" in body and "--text-on-brand" in body, f"{path.name}: {sel}")

    def test_no_focus_ring_is_drawn_in_the_navy(self):
        """The navy ring vanishes on the dark surface (1.17 to 1); rings use --focus."""
        for path in CSS_FILES:
            for sel, body in css_blocks(path):
                for decl in body.split(";"):
                    self.assertFalse(decl.strip().startswith("outline") and "--brand-navy" in decl, f"{path.name}: {sel}")

    def test_the_small_primary_button_is_the_pill(self):
        rule = [b for s, b in css_blocks(PAGE / "shell.css") if s == ".pk-btn.pri:not(:disabled)"]
        self.assertEqual(len(rule), 1)
        for token in ("--pill-color", "--pill-bg", "--pill-fg"):
            self.assertIn(token, rule[0])


class Contrast(Base):
    def set_up(self, p, width, scheme):
        p.cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        p.cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, p.sid)
        p.js("(function(){var s=document.createElement('style');s.textContent='*,*::before,*::after{transition:none!important;animation:none!important}';"
             "document.head.appendChild(s); var r=document.documentElement; if (%s) r.dataset.theme='dark'; else delete r.dataset.theme;})()" % ("true" if scheme == "dark" else "false"))

    def measure(self, p, sel):
        return p.js(f"({MEASURE})({json.dumps(sel)})")

    def focus(self, p, sel):
        """Focus as the keyboard does: a Shift key press first makes the page treat focus as keyboard focus."""
        p.cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, p.sid)
        p.key("Shift", code="ShiftLeft", vk=16)
        p.js(f"document.querySelector({json.dumps(sel)}).focus({{focusVisible: true}})")
        p.until(f"document.querySelector({json.dumps(sel)}).matches(':focus-visible')", "keyboard focus")

    def test_the_add_section_button_label_and_ring_at_both_widths_in_both_themes(self):
        for width, scheme in CASES:
            with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                p = self.visit(cdp)
                p.edit()
                self.set_up(p, width, scheme)
                p.js("document.dispatchEvent(new CustomEvent('clark:add-section', {detail: {after: 'ABC-S-003', opener: null}, cancelable: true, bubbles: true}))")
                p.until("!!document.querySelector('.ad-add')", "the box opened")
                p.js("document.querySelector('[data-template=text] input').click()")
                p.until("!document.querySelector('[data-place]').disabled", "a template is chosen, so the button is on")
                p.until("document.getAnimations().length === 0", "settled")
                sel = ".ad-add [data-place]"
                p.js("document.activeElement.blur()")
                self.assertTrue(p.js(f"document.querySelector({json.dumps(sel)}).matches(':not(:hover)')"))
                idle = self.measure(p, sel)
                self.assertIn("gradient", idle["image"], "the aqua pill, not the navy")
                self.assertGreaterEqual(idle["text"], 4.5, f"idle label {idle}")
                x, y, _ = p.box(sel)
                p.mouse("mouseMoved", x, y)
                p.until(f"document.querySelector({json.dumps(sel)}).matches(':hover')", "hovered")
                self.assertGreaterEqual(self.measure(p, sel)["text"], 4.5, "hover label")
                p.mouse("mouseMoved", 1, 1)
                self.focus(p, sel)
                p.until(f"document.querySelector({json.dumps(sel)}).matches(':focus-visible')", "keyboard focus")
                got = self.measure(p, sel)
                self.assertIsNotNone(got["ring"], "a focus ring is drawn")
                self.assertGreaterEqual(got["ring"], 3.0, f"focus ring {got}")
                self.assertGreaterEqual(got["text"], 4.5, "focused label")

    def test_again_and_the_template_band_button_rings(self):
        for width, scheme in CASES:
            with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                p = self.visit(cdp)
                self.set_up(p, width, scheme)
                p.js("(function(){var d=document.createElement('div'); d.id='row946'; d.style.cssText='padding:24px;position:relative;z-index:99';"
                     "d.innerHTML='<button type=\"button\" class=\"again\">Try again</button>"
                     "<div class=\"tpl-band\"><a class=\"tpl-band-btn\" href=\"#x\">Read more</a></div>'; document.body.prepend(d);})()")
                self.focus(p, "#row946 .again")
                got = self.measure(p, "#row946 .again")
                self.assertGreaterEqual(got["ring"], 3.0, f".again ring {got}")
                self.assertGreaterEqual(got["text"], 4.5, ".again label")
                self.focus(p, "#row946 .tpl-band-btn")
                got = self.measure(p, "#row946 .tpl-band-btn")
                self.assertGreaterEqual(got["ring"], 3.0, f".tpl-band-btn ring {got}")
                p.js("(function(){var d=document.querySelector('#row946 .tpl-band'); d.insertAdjacentHTML('afterbegin','<p class=\"tpl-band-words\">Words</p>');return 1;})()")
                self.assertGreaterEqual(self.measure(p, "#row946 .tpl-band-words")["text"], 4.5, "the band's words")


if __name__ == "__main__":
    unittest.main()
