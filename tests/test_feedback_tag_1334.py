"""Row 1334: the Feedback tag's dialog is the 1298 mock-up (mockups/1298-feedback-tag/html/feedback-tag.html): the message box fills the 360 px dialog
(324 px, level with the Added automatically box), 4 rows, padding 7 x 10, radius 8, border 1, and the other measured differences are closed (a to d below).
Classic only; no stretch, no drag edge, no remembered width (out of the row). Light and dark, at 1400 and 900 px only.
Run: python3 dev/run_tests.py test_feedback_tag_1334
The mock-up's values are pinned here as numbers (the mock-up file is not in this repository)."""
import json
import unittest

import test_feedback_tag_browser_1298 as B
import test_filter_line_keys as K
from test_filter_line_keys import tearDownModule  # noqa: F401
from test_server import chrome, wait

import _testpage as testpage
from clark import page, theme as themes

BAR, DLG = B.BAR, B.DLG
TA = "document.querySelector('#fbt-message')"
ADDED = "document.querySelector('#fbt-added')"

# One call: computed style and box of a selector, as JSON.
PROBE = """((sel, props) => { const e = document.querySelector(sel); if (!e) return JSON.stringify(null); const cs = getComputedStyle(e), r = e.getBoundingClientRect(), o = {left: r.left, right: r.right, top: r.top, width: r.width, height: r.height};
  for (const p of props) o[p] = cs[p]; return JSON.stringify(o); })"""


class FeedbackTag1334(unittest.TestCase):
    def setUp(self):
        B.FeedbackTagBrowser.setUp(self)
        # Row 1334 is Classic only: its values live in the Classic theme (rules-2.css), so the test page has that theme layered; the Cards page keeps edit.css as it was
        self.s.httpd.page_html = lambda: page.layer_theme(testpage.html(), themes.css("prototype-2.0"))

    read = B.FeedbackTagBrowser.read
    open_page = B.FeedbackTagBrowser.open_page
    press = B.FeedbackTagBrowser.press
    look = B.FeedbackTagBrowser.look
    has_tag = B.FeedbackTagBrowser.has_tag
    open_help = B.FeedbackTagBrowser.open_help
    each = B.FeedbackTagBrowser.each

    def probe(self, cdp, sid, sel, *props):
        return json.loads(cdp.js(f"{PROBE}({json.dumps(sel)}, {json.dumps(list(props))})", sid))

    def opened(self):
        """(cdp, sid, where) with the dialog open and its slide finished, for width x theme."""
        for cdp, sid, where in self.each():
            self.open_help(cdp, sid)
            cdp.js(f"{BAR}.click()", sid)
            self.assertTrue(wait(lambda: cdp.js(f"!!{DLG} && !!{TA}", sid)), where)
            yield cdp, sid, where

    def token(self, cdp, sid, prop, value):
        """The computed value of a style property set to value (for example a var(--token)) on a throw-away element."""
        return cdp.js(f"(() => {{ const p = document.createElement('span'); p.style[{json.dumps(prop)}] = {json.dumps(value)}; document.body.appendChild(p); const c = getComputedStyle(p)[{json.dumps(prop)}]; p.remove(); return c; }})()", sid)

    def type_text(self, cdp, sid, text):
        cdp.js(f"(() => {{ {TA}.focus(); document.execCommand('insertText', false, {json.dumps(text)}); }})()", sid)

    def test_feedback_tag_box_full_width_1334(self):
        """AP1: dialog 360, padding 18 each side, box 324 wide, level with the Added automatically box."""
        for cdp, sid, where in self.opened():
            d = self.probe(cdp, sid, "#feedback-tag-dialog", "paddingLeft", "paddingRight", "borderLeftWidth")
            t = self.probe(cdp, sid, "#fbt-message")
            a = self.probe(cdp, sid, "#fbt-added")
            self.assertEqual(round(d["width"]), 360, where)
            self.assertEqual((round(t["left"] - d["left"]), round(d["right"] - t["right"])), (18, 18), where + ": 18 px in from each edge of the dialog (the 1 px left border counts)")
            self.assertEqual(round(t["width"], 1), 324, where)
            self.assertEqual((round(t["left"]), round(t["right"])), (round(a["left"]), round(a["right"])), where + ": level with the Added automatically box")

    def test_feedback_tag_box_full_width_dark_1334(self):
        """AP7: the same in the dark theme, border 1 px, text 4.5 to 1 against the box."""
        lum = """(() => { const L = c => { const [r, g, b] = c.map(v => { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); }); return .2126 * r + .7152 * g + .0722 * b; };
          const rgb = s => (s.match(/[\\d.]+/g) || [0, 0, 0]).map(Number).slice(0, 3); const cs = getComputedStyle(document.querySelector('#fbt-message'));
          const a = L(rgb(cs.color)), b = L(rgb(cs.backgroundColor)); return (Math.max(a, b) + .05) / (Math.min(a, b) + .05); })()"""
        seen = 0
        for cdp, sid, where in self.opened():
            if "dark" not in where:
                continue
            seen += 1
            t = self.probe(cdp, sid, "#fbt-message", "borderTopWidth", "borderLeftWidth")
            self.assertEqual(round(t["width"], 1), 324, where)
            self.assertEqual((t["borderTopWidth"], t["borderLeftWidth"]), ("1px", "1px"), where)
            self.assertGreaterEqual(cdp.js(lum, sid), 4.5, where)
        self.assertTrue(seen, "a dark run happened")

    def test_feedback_tag_box_rows_1334(self):
        """AP3: 4 rows (4 lines tall) and vertical resize only."""
        for cdp, sid, where in self.opened():
            self.assertEqual(cdp.js(f"{TA}.rows", sid), 4, where)
            t = self.probe(cdp, sid, "#fbt-message", "resize", "lineHeight", "paddingTop", "paddingBottom", "borderTopWidth", "borderBottomWidth")
            self.assertEqual(t["resize"], "vertical", where)
            want = 4 * float(t["lineHeight"][:-2]) + 14 + 2
            self.assertAlmostEqual(t["height"], want, delta=1.5, msg=where + ": four lines, padding and border")

    def test_feedback_tag_box_style_1334(self):
        """AP4: padding 7 x 10, radius 8, border 1 px; the box takes the dialog's font and the page's text and surface colours (not the browser's)."""
        for cdp, sid, where in self.opened():
            t = self.probe(cdp, sid, "#fbt-message", "paddingTop", "paddingRight", "paddingBottom", "paddingLeft", "borderTopWidth", "borderTopStyle", "borderTopLeftRadius", "borderBottomRightRadius", "fontFamily", "fontSize", "color", "backgroundColor", "borderTopColor")
            d = self.probe(cdp, sid, "#feedback-tag-dialog", "fontFamily", "fontSize", "color", "backgroundColor")
            self.assertEqual((t["paddingTop"], t["paddingRight"], t["paddingBottom"], t["paddingLeft"]), ("7px", "10px", "7px", "10px"), where)
            self.assertEqual((t["borderTopWidth"], t["borderTopStyle"]), ("1px", "solid"), where)
            self.assertEqual(t["borderTopColor"], self.token(cdp, sid, "color", "var(--grey-200)"), where + ": the border is the grey-200 token")
            self.assertEqual((t["borderTopLeftRadius"], t["borderBottomRightRadius"]), ("8px", "8px"), where)
            self.assertEqual((t["fontFamily"], t["fontSize"], t["color"], t["backgroundColor"]), (d["fontFamily"], d["fontSize"], d["color"], d["backgroundColor"]), where)

    def test_feedback_tag_matches_mockup_1334(self):
        """AP5: the differences found in the side-by-side render of the built panel and the mock-up (1400 and 900, light and dark), each closed:
        a) head, lead line, kinds and label: sizes and spacing; b) the message box's text size and the red empty-send line; c) the Added automatically box and the mail note: sizes, padding, tight lines;
        d) the two buttons: one line, 8 px apart, 12 px under the note, level (centres line up; the pill heights stay as row 1319 set them). Already equal and pinned: 360 px wide, top 110 px, 0.4 s slide, the words."""
        for cdp, sid, where in self.opened():
            with self.subTest(where=where):
                # words as on main and in the mock-up
                words = json.loads(cdp.js(f"JSON.stringify({{h: document.querySelector('#fbt-h').textContent, x: document.querySelector('[data-fbt-close]').getAttribute('aria-label'), intro: document.querySelector('.fbt-head + p').textContent, kinds: [...document.querySelectorAll('[data-fbt-kind]')].map(b => b.textContent), label: {DLG}.querySelector('label').textContent, added: document.querySelector('#fbt-added b').textContent, note: {DLG}.querySelector('#fbt-added + p').textContent, copy: document.querySelector('[data-fbt-copy]').textContent, mail: document.querySelector('[data-fbt-mail]').textContent}})", sid))
                self.assertEqual(words, {"h": "Feedback", "x": "Close", "intro": "Tell us what is wrong or what you would like to see.", "kinds": ["Problem", "Idea", "Question"], "label": "What is wrong, or what would you suggest?", "added": "Added automatically", "note": "Your mail app opens with the message ready and you press send. Nothing is sent by clark itself.", "copy": "Copy as text", "mail": "Open in your mail app"}, where)
                # fixed by the mock-up: top 110 px, 360 px, 0.4 s slide
                d = self.probe(cdp, sid, "#feedback-tag-dialog", "paddingTop", "paddingBottom", "lineHeight", "fontSize")
                self.assertEqual((round(d["top"]), round(d["width"])), (110, 360), where)
                # a)
                self.assertEqual((d["paddingTop"], d["paddingBottom"]), ("16px", "14px"), where + " a) dialog padding 16 / 14")
                self.assertAlmostEqual(float(d["lineHeight"][:-2]), 1.45 * float(d["fontSize"][:-2]), 2, where + " a) line height 1.45 times the dialog's font size (14 px in the Classic page)")
                h = self.probe(cdp, sid, "#fbt-h", "fontSize", "fontWeight", "marginBottom")
                self.assertEqual((h["fontSize"], h["fontWeight"], h["marginBottom"]), ("17px", "600", "2px"), where + " a) title")
                x = self.probe(cdp, sid, "[data-fbt-close]", "fontSize", "fontWeight", "paddingLeft", "paddingRight", "paddingTop")
                self.assertEqual((x["fontSize"], x["fontWeight"], x["paddingLeft"], x["paddingRight"], x["paddingTop"]), ("20px", "600", "4px", "4px", "0px"), where + " a) close mark")
                s = self.probe(cdp, sid, ".fbt-head + p", "fontSize", "marginTop", "marginBottom")
                self.assertEqual((s["fontSize"], s["marginTop"], s["marginBottom"]), ("13px", "0px", "10px"), where + " a) lead line")
                k = self.probe(cdp, sid, ".fbt-kinds", "marginTop", "marginBottom", "gap")
                self.assertEqual((k["marginTop"], k["marginBottom"], k["gap"]), ("6px", "10px", "6px"), where + " a) kinds row")
                c = self.probe(cdp, sid, ".fbt-kind", "fontSize", "paddingTop", "paddingLeft")
                self.assertEqual((c["fontSize"], c["paddingTop"], c["paddingLeft"]), ("13.5px", "4px", "12px"), where + " a) kind chip")
                lab = self.probe(cdp, sid, "#feedback-tag-dialog label", "fontSize", "marginTop", "marginBottom", "display")
                self.assertEqual((lab["fontSize"], lab["marginTop"], lab["marginBottom"], lab["display"]), ("13.5px", "8px", "3px", "block"), where + " a) label")
                # b)
                cdp.js("document.querySelector('[data-fbt-copy]').click()", sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#fbt-error')", sid)), where)
                e = self.probe(cdp, sid, "#fbt-error", "fontSize", "marginTop", "color")
                red = cdp.js("(() => { const p = document.createElement('span'); p.style.color = 'var(--status-red-text)'; document.body.appendChild(p); const c = getComputedStyle(p).color; p.remove(); return c; })()", sid)
                self.assertEqual((e["fontSize"], e["marginTop"], e["color"]), ("13px", "4px", red), where + " b) empty-send line")
                ta = self.probe(cdp, sid, "#fbt-message", "fontSize", "display", "overflowY", "boxSizing")
                self.assertEqual((ta["fontSize"], ta["display"], ta["overflowY"], ta["boxSizing"]), (d["fontSize"], "block", "auto", "border-box"), where + " b) box text size (the dialog's, 14 px in the Classic page), block, scrolls when full")
                # c)
                ad = self.probe(cdp, sid, "#fbt-added", "fontSize", "paddingTop", "paddingRight", "paddingBottom", "paddingLeft", "marginTop", "borderTopLeftRadius")
                self.assertEqual((ad["fontSize"], ad["paddingTop"], ad["paddingRight"], ad["paddingBottom"], ad["paddingLeft"], ad["borderTopLeftRadius"]), ("12.5px", "8px", "10px", "8px", "10px", "8px"), where + " c) Added automatically box")
                tok = lambda prop, v: self.token(cdp, sid, prop, v)
                ad2 = self.probe(cdp, sid, "#fbt-added", "color")
                self.assertEqual(ad2["color"], tok("color", "var(--grey-700)"), where + " c) Added automatically text is the grey-700 token")
                ul = self.probe(cdp, sid, "#fbt-added ul", "marginTop", "marginBottom")
                self.assertEqual((ul["marginTop"], ul["marginBottom"]), (tok("marginTop", "var(--space-1)"),) * 2, where + " c) list margin is the space-1 token")
                self.assertNotEqual(ul["marginTop"], "0px", where + " c) list margin is not zero")
                self.assertEqual(self.probe(cdp, sid, "#fbt-added + p", "marginTop")["marginTop"], "6px", where + " c) mail note")
                li = self.probe(cdp, sid, "#fbt-added li", "paddingTop", "paddingBottom", "borderTopWidth", "marginTop")
                self.assertEqual((li["paddingTop"], li["paddingBottom"], li["borderTopWidth"], li["marginTop"]), ("0px", "0px", "0px", "0px"), where + " c) tight lines")
                note = self.probe(cdp, sid, "#fbt-added + p", "fontSize", "marginBottom")
                self.assertEqual((note["fontSize"], note["marginBottom"]), ("12.5px", "0px"), where + " c) mail note size")
                gap = self.probe(cdp, sid, "#fbt-added", "marginTop")["marginTop"]
                self.assertEqual(gap, "10px", where + " c) 10 px under the box")
                # d)
                row = self.probe(cdp, sid, ".fbt-dlg .row", "marginTop")
                self.assertEqual(row["marginTop"], "12px", where + " d) buttons row, 12 px under the note")
                cp = self.probe(cdp, sid, "[data-fbt-copy]", "paddingLeft", "paddingRight", "verticalAlign")
                ml = self.probe(cdp, sid, "[data-fbt-mail]", "paddingLeft", "paddingRight", "verticalAlign", "marginLeft")
                self.assertEqual((cp["paddingLeft"], cp["paddingRight"], cp["verticalAlign"]), ("14px", "14px", "middle"), where + " d) Copy as text")
                self.assertEqual((ml["paddingLeft"], ml["paddingRight"], ml["verticalAlign"], ml["marginLeft"]), ("22px", "22px", "middle", "8px"), where + " d) Open in your mail app (the pill of row 1319 keeps its padding)")
                self.assertEqual(round(cp["top"] + cp["height"] / 2), round(ml["top"] + ml["height"] / 2), where + " d) level: the two centres line up")
                self.assertEqual(round(ml["left"] - cp["right"]), 8, where + " d) 8 px apart")
                self.assertLessEqual(ml["right"], self.probe(cdp, sid, "#fbt-message")["right"] + 1, where + " d) both on one line inside the box")

    def test_feedback_tag_matches_mockup_slide_1334(self):
        """AP5, the slide: 0.4 s (read with motion allowed)."""
        with chrome() as cdp:
            for width in B.WIDTHS:
                self.open_page(cdp, width)
                sid = self.sid
                self.look(cdp, sid, "light", reduce=False)
                self.open_help(cdp, sid)
                cdp.js(f"{BAR}.click()", sid)
                self.assertTrue(wait(lambda: cdp.js(f"!!{DLG}", sid)))
                self.assertEqual(cdp.js(f"getComputedStyle({DLG}).animationDuration", sid), "0.4s", f"{width}")

    def test_feedback_tag_typed_text_kept_1334(self):
        """AP6: what is typed stays in the box when a kind is chosen, when Enter makes a new line and when Copy is pressed; Enter does not close; Esc closes."""
        for cdp, sid, where in self.opened():
            self.type_text(cdp, sid, "One")
            cdp.js("document.querySelector('[data-fbt-kind=Idea]').click()", sid)
            self.press(cdp, sid, "Enter") if cdp.js("document.activeElement.id", sid) == "fbt-message" else cdp.js(f"{TA}.focus()", sid)
            self.type_text(cdp, sid, "Two")
            cdp.js("document.querySelector('[data-fbt-copy]').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelector('#fbt-note').textContent", sid) != ""), where)
            self.assertTrue(cdp.js(f"!!{DLG}", sid), where + ": Enter did not close it")
            self.assertEqual(cdp.js(f"{TA}.value", sid).replace("\r", "").replace("\n", ""), "OneTwo", where)
            self.press(cdp, sid, "Escape")
            self.assertTrue(wait(lambda: cdp.js(f"!{DLG}", sid)), where + ": Esc closes")


if __name__ == "__main__":
    unittest.main()
