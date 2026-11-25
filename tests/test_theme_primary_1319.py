"""Row 1319, Classic theme: the primary buttons .again, .btn.primary and .btn.pri are 8px navy rectangles (white text), not aqua pills, light and dark.

Run: python3 dev/run_tests.py test_theme_primary_1319
Fails, never skips, without Chrome. Computed styles at 1400 and 900, light and dark; hover and press are pinned in the CSS source
(a pointer state cannot be forced reliably); Cards (no Theme layer) keeps the look it has today.
"""
import re
import unittest
from pathlib import Path

from _paths import ROOT  # noqa: F401
from test_server import chrome
import test_theme_global_1319 as g
from test_theme_global_1319 import NAME, SIZES, FOLDER, ratio, parse
import test_theme_global_1319 as _test_theme_global_1319

from clark import page, theme

EXTRA = """(() => { const d = document.createElement('div'); d.id = 'extra';
  d.innerHTML = '<button class="btn pri ok" id="e-ok">Done</button><button class="btn pri" id="e-off" disabled>Off</button>' +
    '<button class="again" id="e-aoff" disabled>Off</button><button class="btn pri" id="e-go" data-go><span class="spin"></span>Go</button>' +
    '<button class="btn pri ok" id="e-tick"><i class="pub-tick"></i></button>';
  document.body.appendChild(d); })()"""
PRIMARY = ("#b2", "#b3", "#b4")
RULES = (FOLDER / "rules.css").read_text(encoding="utf-8")
BLOCK = RULES[RULES.index("/* Row 1319, primary buttons"):].split("\n/* Row 1316", 1)[0]     # rows stacked after the Row 1316 blocks are not this row's


class PrimaryRect(_test_theme_global_1319.Computed):
    def classic(self, cdp, w, scheme, html):
        sid = self.load(cdp, w, scheme, html)
        cdp.js(EXTRA, sid)
        return sid

    def test_each_primary_selector_is_the_navy_rect_at_each_width_in_light_and_dark(self):
        html = page.page_html(branding=page.NO_BRAND, theme=NAME)
        want = {"borderTopWidth": "0px", "borderRadius": "8px", "paddingLeft": "22px", "paddingRight": "22px", "minHeight": "38px",
                "fontWeight": "800", "letterSpacing": "0.56px", "backgroundColor": {"light": "rgb(6, 47, 58)", "dark": "rgb(4, 32, 42)"},
                "backgroundImage": "none", "color": "rgb(255, 255, 255)",
                "boxShadow": {"light": "none", "dark": "rgb(111, 127, 163) 0px 0px 0px 1px inset"}}
        with chrome() as cdp:
            for scheme in ("light", "dark"):
                for w in SIZES:
                    sid = self.classic(cdp, w, scheme, html)
                    tag = f"{scheme} {w}"
                    for sel in PRIMARY:
                        for prop, val in want.items():
                            val = val[scheme] if isinstance(val, dict) else val
                            self.assertEqual(self.style(cdp, sid, sel, prop), val, f"{tag} {sel} {prop}")
                        cdp.js("document.querySelector(%r).focus()" % sel, sid)
                        self.assertEqual(self.style(cdp, sid, sel, "outlineColor"), "rgb(91, 71, 216)" if scheme == "light" else "rgb(143, 123, 255)", f"{tag} {sel}")
                        self.assertEqual(self.style(cdp, sid, sel, "outlineStyle"), "solid", f"{tag} {sel}")
                        self.assertEqual(self.style(cdp, sid, sel, "outlineWidth"), "2px", f"{tag} {sel}")
                        self.assertEqual(self.style(cdp, sid, sel, "outlineOffset"), "2px", f"{tag} {sel}")
                    # the plain button keeps its 8px corner
                    self.assertEqual(self.style(cdp, sid, "#b1", "borderRadius"), "8px", tag)
                    self.assertTrue(cdp.js("document.documentElement.scrollWidth <= window.innerWidth", sid), tag)

    def test_disabled_finished_spinner_and_tick(self):
        html = page.page_html(branding=page.NO_BRAND, theme=NAME)
        green = {"light": "rgb(0, 107, 94)", "dark": "rgb(79, 209, 189)"}
        with chrome() as cdp:
            for scheme in ("light", "dark"):
                for w in SIZES:
                    sid = self.classic(cdp, w, scheme, html)
                    tag = f"{scheme} {w}"
                    self.assertEqual(self.style(cdp, sid, "#e-off", "opacity"), "0.55", tag)
                    self.assertEqual(self.style(cdp, sid, "#e-aoff", "opacity"), "0.55", tag)
                    self.assertEqual(self.style(cdp, sid, "#e-ok", "backgroundColor"), green[scheme], tag)
                    self.assertEqual(self.style(cdp, sid, "#e-ok", "backgroundImage"), "none", tag)
                    self.assertEqual(self.style(cdp, sid, "#e-ok", "color"), "rgb(255, 255, 255)" if scheme == "light" else "rgb(4, 34, 42)", tag)
                    self.assertEqual(self.style(cdp, sid, "#e-ok", "borderRadius"), "8px", tag)
                    self.assertEqual(self.style(cdp, sid, "#e-go .spin", "borderTopColor"), "rgb(255, 255, 255)", tag)
                    self.assertEqual(self.style(cdp, sid, "#e-tick .pub-tick", "backgroundColor"), "rgb(255, 255, 255)", tag)
                    self.assertEqual(self.style(cdp, sid, "#e-tick .pub-tick", "color"), green[scheme], tag)

    def test_dark_ring_and_finished_text_are_fixed_and_light_is_as_proto(self):
        html = page.page_html(branding=page.NO_BRAND, theme=NAME)
        with chrome() as cdp:
            for w in SIZES:
                sid = self.classic(cdp, w, "dark", html)
                for sel in PRIMARY:
                    cdp.js("document.querySelector(%r).focus()" % sel, sid)
                    ring = self.style(cdp, sid, sel, "outlineColor")
                    self.assertEqual(ring, "rgb(143, 123, 255)", f"dark {w} {sel}")
                    self.assertGreaterEqual(ratio(parse(ring), (14, 22, 32)), 3, f"dark {w} {sel}")
                ok = self.style(cdp, sid, "#e-ok", "color")
                self.assertEqual(ok, "rgb(4, 34, 42)", w)
                self.assertGreaterEqual(ratio(parse(ok), parse(self.style(cdp, sid, "#e-ok", "backgroundColor"))), 8.8, w)
                self.assertEqual(self.style(cdp, sid, "#e-tick .pub-tick", "backgroundColor"), "rgb(255, 255, 255)", w)
                sid = self.classic(cdp, w, "light", html)
                cdp.js("document.querySelector('#b2').focus()", sid)
                self.assertEqual(self.style(cdp, sid, "#b2", "outlineColor"), "rgb(91, 71, 216)", f"light {w}")
                self.assertEqual(self.style(cdp, sid, "#e-ok", "color"), "rgb(255, 255, 255)", f"light {w}")

    def test_dark_rules_exist_for_dark_and_auto(self):
        self.assertIn(":root[data-theme=dark] .btn.pri.ok { color: #04222A; }", BLOCK)
        self.assertIn("@media (prefers-color-scheme: dark) { :root[data-theme=auto] .again:focus-visible, :root[data-theme=auto] .btn.primary:focus-visible, :root[data-theme=auto] .btn.pri:focus-visible { outline-color: var(--focus); } :root[data-theme=auto] .btn.pri.ok { color: #04222A; } }", BLOCK)

    def test_text_contrast_on_both_navy_fills_and_the_ring(self):
        for fill in ((6, 47, 58), (4, 32, 42)):
            self.assertGreaterEqual(ratio((255, 255, 255), fill), 12, fill)
        self.assertGreaterEqual(ratio((91, 71, 216), (246, 248, 252)), 5.9)
        self.assertGreaterEqual(ratio((255, 255, 255), (0, 107, 94)), 6.4)

    def test_reduced_motion_has_no_transform_or_transition(self):
        html = page.page_html(branding=page.NO_BRAND, theme=NAME)
        with chrome() as cdp:
            sid = self.classic(cdp, 1400, "light", html)
            cdp.js("document.documentElement.setAttribute('data-motion', 'reduce')", sid)
            for sel in PRIMARY:
                self.assertEqual(self.style(cdp, sid, sel, "transform"), "none", sel)
                self.assertEqual(self.style(cdp, sid, sel, "transitionDuration"), "0s", sel)
            cdp.js("document.documentElement.removeAttribute('data-motion')", sid)
            self.assertNotEqual(self.style(cdp, sid, "#b2", "transitionDuration"), "0s")

    def test_hover_and_press_are_pinned_in_the_source(self):
        sels = (".again", ".btn.primary", ".btn.pri")
        guard = ':root:not([data-motion="reduce"]) '
        hover = ", ".join(guard + s + (":hover:not(:disabled)" if s == ".btn.pri" else ":hover") for s in sels) + " { transform: translateY(-1px); }"
        press = ", ".join(guard + s + (":active:not(:disabled)" if s == ".btn.pri" else ":active") for s in sels) + " { transform: translateY(1px); }"
        calm = ':root[data-motion="reduce"] .again, :root[data-motion="reduce"] .btn.primary, :root[data-motion="reduce"] .btn.pri { transition: none; transform: none; }'
        lines = BLOCK.split("\n")
        for want in (hover, press, calm):
            self.assertIn(want, lines)
        # no transform outside the motion guard
        for l in lines[1:]:
            if "transform:" in l and "transform: none" not in l:
                self.assertTrue(l.startswith(guard), l)

    def test_block_is_separate_and_the_8px_line_no_longer_names_the_primaries(self):
        self.assertIn(".btn, .seg { border-radius: var(--radius); }", RULES)
        self.assertNotIn(".again, .btn.primary, .btn.pri { border-radius: var(--radius)", RULES)
        self.assertEqual(len(re.findall(r"^/\* Row 1319, primary buttons", RULES, re.M)), 1)
        self.assertEqual(sorted(re.findall(r"#[0-9a-fA-F]{3,8}\b", BLOCK)), ["#04222A"] * 2 + ["#5B47D8"])

    def test_cards_keeps_its_own_primary_buttons(self):
        html = page.page_html(branding=page.NO_BRAND)
        with chrome() as cdp:
            for w in SIZES:
                sid = self.classic(cdp, w, "light", html)
                for sel in PRIMARY:
                    self.assertEqual(self.style(cdp, sid, sel, "borderRadius"), "999px", f"{w} {sel}")
                self.assertEqual(self.style(cdp, sid, "#b1", "borderRadius"), "999px", w)
                self.assertEqual(self.style(cdp, sid, "#e-ok", "color"), "rgb(255, 255, 255)", w)
                self.assertEqual(self.style(cdp, sid, "#e-go .spin", "borderTopColor"), "rgb(4, 34, 42)", w)

    def test_cards_page_has_none_of_the_block(self):
        self.assertNotIn("background-color: var(--brand-navy); background-image: none; color: var(--white); box-shadow: none", page.page_html(branding=page.NO_BRAND))
        self.assertIn("background-color: var(--brand-navy); background-image: none; color: var(--white); box-shadow: none", theme.css(NAME))


if __name__ == "__main__":
    unittest.main()
