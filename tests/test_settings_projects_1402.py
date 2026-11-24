"""Row 1402 in the Classic Theme: the Settings Projects card as the prototype draws it (issue 1402, Classic audit 19-11), on the REAL Settings page, as Chrome
computes it at 1400 (the spec) and 900 (also checked), light and dark; Cards as the control.
Values (light, 1400): header rule 1px rgb(217, 224, 239) under the header, no vertical dividers between header cells; body cell padding 8px 10px 8px 0, header padding 6px 10px 6px 0, header weight 600 in the muted colour, 1px --line-soft rule under each body cell (row 1317);
Add project is navy rgb(6, 47, 58), white text, radius 8. Dark keeps the Theme's tokens for colours.

Run: python3 dev/run_tests.py test_settings_projects_1402"""
import time
import unittest

import test_theme_classic_1317 as t13
from test_theme_classic_1317 import NAME, page_target, for_url, wait, FIXED_DATE
from test_server import Running, chrome  # noqa: F401  the browser harness, named so the browser tier reads this file as a browser test

PROBE = """(() => { const q = (s) => document.querySelector(s), g = (e, p) => getComputedStyle(e)[p];
  const ths = [...document.querySelectorAll('#projects-table thead th')], th = ths[0], th2 = ths[1], td = q('#projects-table tbody td'), td2 = q('#projects-table tbody td + td'), btn = q('#npBtn');
  const pad = (e) => ['paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft'].map((p) => g(e, p)).join(' ');
  const tok = (v, p) => { const i = document.createElement('i'); i.style[p] = v; document.body.appendChild(i); const r = getComputedStyle(i)[p]; i.remove(); return r; };
  return { thBottom: [g(th, 'borderBottomWidth'), g(th, 'borderBottomStyle'), g(th, 'borderBottomColor')].join(' '), thLeft2: g(th2, 'borderLeftWidth'), thRight: g(th, 'borderRightWidth'),
    tdLeft: g(td2, 'borderLeftWidth'), thPad: pad(th), thPad2: pad(th2), tdPad: pad(td), tdPad2: pad(td2),
    thWeight: g(th, 'fontWeight'), thWeight2: g(th2, 'fontWeight'), thColor: g(th, 'color'), thColor2: g(th2, 'color'), tdBottom: [g(td, 'borderBottomWidth'), g(td, 'borderBottomStyle'), g(td, 'borderBottomColor')].join(' '), tdBottom2: [g(td2, 'borderBottomWidth'), g(td2, 'borderBottomStyle'), g(td2, 'borderBottomColor')].join(' '), muted: tok('var(--text-muted)', 'color'), lineSoft: tok('var(--line-soft)', 'borderTopColor'),
    btnBg: g(btn, 'backgroundColor'), btnColor: g(btn, 'color'), btnRadius: g(btn, 'borderTopLeftRadius'), brand: tok('var(--brand-blue)', 'backgroundColor'), grey200: tok('var(--grey-200)', 'borderTopColor') }; })()"""


class ProjectsCard(t13.RealSettings):
    test_classic_settings_sidebar_cards_table_and_add_project = test_classic_projects_code_cell_stays_on_one_line = None
    test_classic_projects_table_never_breaks_a_word_in_the_middle = test_cards_keeps_its_own_settings_look = test_the_cards_page_is_byte_for_byte_what_it_was = None

    def look(self, cdp, port, width, scheme):
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
        cdp.call("Page.navigate", {"url": "about:blank"}, sid)
        cdp.call("Page.navigate", {"url": for_url(f"http://127.0.0.1:{port}/#settings&p=TUL")}, sid)
        self.assertTrue(wait(lambda: bool(cdp.js("!!document.querySelector('#projects-table tbody tr') && !!document.querySelector('#npBtn')", sid)), 30), "timed out waiting for Settings")
        cdp.js("document.querySelectorAll('#npBtn').forEach((e) => { e.style.transition = 'none'; })", sid)
        r = cdp.js(PROBE, sid)
        rest = cdp.js("(() => { const b = document.querySelector('#npBtn'); const g = (p) => getComputedStyle(b)[p]; return { bg: g('backgroundColor'), tr: g('transform'), sh: g('boxShadow') }; })()", sid)
        box = cdp.js("(() => { const r = document.querySelector('#npBtn').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; })()", sid)
        cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": box[0], "y": box[1]}, sid)
        time.sleep(0.3)
        r["rest"] = rest
        r["hover"] = cdp.js("(() => { const b = document.querySelector('#npBtn'); const g = (p) => getComputedStyle(b)[p]; const i = document.createElement('i'); i.style.boxShadow = 'var(--pill-glow-hover)'; document.body.appendChild(i); const glow = getComputedStyle(i).boxShadow; i.remove(); return { bg: g('backgroundColor'), tr: g('transform'), sh: g('boxShadow'), glow: glow, hov: b.matches(':hover') }; })()", sid)
        cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": 1, "y": 1}, sid)
        cdp.js("document.documentElement.dataset.motion = 'reduce'", sid)  # clark's own reduced-motion setting, the same attribute the page paints at load
        cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": box[0], "y": box[1]}, sid)
        time.sleep(0.3)
        r["reduced"] = cdp.js("(() => { const b = document.querySelector('#npBtn'); const g = (p) => getComputedStyle(b)[p]; return { tr: g('transform'), sh: g('boxShadow'), hov: b.matches(':hover') }; })()", sid)
        return r

    def test_classic_projects_card(self):
        for tag, c in self.each(NAME):
            light = "light" in tag
            self.assertEqual((c["thLeft2"], c["thRight"], c["tdLeft"]), ("0px", "0px", "0px"), tag + ": no dividers between cells")
            self.assertTrue(c["thBottom"].startswith("1px solid "), tag + ": 1px rule under the header, got " + c["thBottom"])
            self.assertEqual(c["thBottom"], "1px solid " + ("rgb(217, 224, 239)" if light else c["grey200"]), tag)
            self.assertEqual((c["thPad"], c["thPad2"]), ("6px 10px 6px 0px",) * 2, tag + ": header padding 6px 10px 6px 0 (row 1317)")
            self.assertEqual((c["tdPad"], c["tdPad2"]), ("8px 10px 8px 0px",) * 2, tag + ": body cell padding 8px 10px 8px 0")
            self.assertEqual((c["thWeight"], c["thWeight2"]), ("600", "600"), tag + ": header weight 600 (row 1317)")
            self.assertEqual((c["thColor"], c["thColor2"]), (c["muted"],) * 2, tag + ": header in the muted text colour (row 1317)")
            self.assertEqual((c["tdBottom"], c["tdBottom2"]), ("1px solid " + c["lineSoft"],) * 2, tag + ": body cell 1px --line-soft rule (row 1317)")
            if light:
                self.assertEqual(c["lineSoft"], "rgb(233, 237, 246)", tag + ": --line-soft is #E9EDF6")
            self.assertEqual(c["btnRadius"], "8px", tag)
            if light:
                self.assertEqual((c["btnBg"], c["btnColor"]), ("rgb(6, 47, 58)", "rgb(255, 255, 255)"), tag + ": navy Add project, white text")
            else:
                self.assertEqual(c["btnBg"], c["brand"], tag + ": dark keeps the Theme's brand token")

    def test_add_project_hover_is_the_primary_button_hover(self):
        # the other Classic primary buttons (.btn.pri) keep their fill on hover, lift 1px and take the hover glow; the focus ring is untouched
        for tag, c in self.each(NAME):
            h = c["hover"]
            self.assertTrue(h["hov"], tag + ": the pointer is over the button")
            self.assertEqual(h["bg"], c["rest"]["bg"], tag + ": hover keeps the fill")
            self.assertEqual(h["tr"], "matrix(1, 0, 0, 1, 0, -1)", tag + ": hover lifts 1px")
            self.assertEqual(h["sh"], h["glow"], tag + ": hover takes the glow token")
            self.assertEqual(c["rest"]["tr"], "none", tag + ": at rest no lift")
            # the token compared with itself cannot fail, so the real value is pinned: --pill-glow-hover in brand/tokens.css line 6 is 0 0 44px rgba(56, 224, 238, .55)
            self.assertEqual(h["sh"], "rgba(56, 224, 238, 0.55) 0px 0px 44px 0px", tag + ": the hover glow is the brand token's value")
            self.assertNotEqual(h["sh"], "none", tag + ": a glow is drawn")
            self.assertNotEqual(h["sh"], c["rest"]["sh"], tag + ": the glow differs from rest")

    def test_add_project_hover_is_still_when_motion_is_reduced(self):
        # clark's own setting (data-motion=reduce on the root) removes the lift and the glow, as for the other primary buttons
        for tag, c in self.each(NAME):
            m = c["reduced"]
            self.assertTrue(m["hov"], tag + ": the pointer is over the button")
            self.assertEqual(m["tr"], "none", tag + ": no lift when motion is reduced")
            self.assertEqual(m["sh"], c["rest"]["sh"], tag + ": no glow when motion is reduced")

    def test_cards_projects_card_unchanged(self):
        for tag, c in self.each(None):
            dark = "dark" in tag
            # the values below were measured on origin/main (Cards, real computed styles, 1400 and 900 alike), not guessed
            want = {"thBottom": "0px none " + ("rgb(169, 203, 212)" if dark else "rgb(71, 85, 119)"), "thLeft2": "0px", "thRight": "0px", "tdLeft": "0px",
                    "thPad": "8px 10px 8px 4px", "thPad2": "8px 10px 8px 10px", "tdPad": "9px 10px 9px 4px", "tdPad2": "9px 10px 9px 10px",
                    "btnBg": "rgb(14, 45, 56)" if dark else "rgb(255, 255, 255)", "btnColor": "rgb(183, 169, 255)" if dark else "rgb(74, 55, 194)", "btnRadius": "8px"}
            self.assertEqual({k: c[k] for k in want}, want, tag + ": the Cards Projects card is what main computes")


if __name__ == "__main__":
    unittest.main()
