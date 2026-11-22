"""Row 1319, Classic theme, all pages: heading weight 600, 8px radius on buttons, 6px on segments with the lavender chosen half, plain crumbs.

Run: python3 dev/run_tests.py test_theme_global_1319
Fails, never skips, without Chrome. Computed styles at 1400 and 900, light and dark. Cards (no Theme layer) keeps today's page.
"""
import json
import re
import tempfile
import time
import unittest
from pathlib import Path

from _paths import ROOT  # noqa: F401
from test_server import chrome

from clark import page, theme

NAME = "prototype-2.0"
SIZES = (1400, 900)
FOLDER = ROOT / "src" / "clark" / "themes" / NAME
PROBE = """(() => { const r = document.documentElement; r.setAttribute('data-theme', %r);
  const d = document.createElement('div'); d.id = 'probe';
  d.innerHTML = '<h1>H1</h1><h2>H2</h2><h3>H3</h3><p class="crumbs">Project</p><nav class="ucd-crumb">Use cases</nav><nav class="ucf-crumb">Use cases</nav>' +
    '<div class="seg" id="sg"><button aria-pressed="true">On <em>3</em></button><button aria-pressed="false">Off</button></div>' +
    '<div class="seg" id="sc"><button aria-checked="true">On <em>2</em></button></div><div class="cal-sc seg" id="cs"><button aria-current="true">Month</button></div>' +
    '<div class="seg lsw" id="ls"><button aria-pressed="true">A</button><button aria-pressed="false">B</button></div>' +
    '<button class="btn" id="b1">Plain</button><button class="btn pri" id="b2">Main</button><button class="again" id="b3">Again</button><button class="btn primary" id="b4">Primary</button>' +
    '<div class="modes seg glide" id="md"><button class="mode" aria-pressed="true">A</button><button class="mode" aria-pressed="false">B</button></div>';
  document.body.appendChild(d); })()"""


def lum(rgb):
    def f(c):
        c /= 255
        return c / 12.92 if c <= .03928 else ((c + .055) / 1.055) ** 2.4
    r, g, b = rgb
    return .2126 * f(r) + .7152 * f(g) + .0722 * f(b)


def ratio(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + .05) / (lb + .05)


def parse(s):
    return tuple(int(float(x)) for x in re.findall(r"[\d.]+", s)[:3])


class Computed(unittest.TestCase):
    def load(self, cdp, width, scheme, html):
        path = Path(tempfile.mkdtemp(prefix="clark-test-")) / "p.html"
        path.write_text(html, encoding="utf-8")
        self.addCleanup(lambda: (path.unlink(), path.parent.rmdir()))
        tid = cdp.call("Target.createTarget", {"url": "about:blank"})["targetId"]
        sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Page.navigate", {"url": path.as_uri()}, sid)
        end = time.monotonic() + 20
        while cdp.js("document.readyState", sid) != "complete" and time.monotonic() < end:
            time.sleep(0.05)
        cdp.js(PROBE % scheme, sid)
        return sid

    def style(self, cdp, sid, sel, prop):
        return cdp.js("getComputedStyle(document.querySelector(%s))[%s]" % (json.dumps(sel), json.dumps(prop)), sid)

    def test_classic_at_each_width_in_light_and_dark(self):
        html = page.page_html(branding=page.NO_BRAND, theme=NAME)
        with chrome() as cdp:
            for scheme in ("light", "dark"):
                for w in SIZES:
                    sid = self.load(cdp, w, scheme, html)
                    tag = f"{scheme} {w}"
                    for h in ("h1", "h2", "h3"):
                        self.assertEqual(self.style(cdp, sid, "#probe " + h, "fontWeight"), "600", f"{tag} {h}")
                    for sel in ("#sg", "#sc", "#cs"):
                        self.assertEqual(self.style(cdp, sid, sel, "borderRadius"), "6px", f"{tag} {sel} (segments 6, ruled 20-11)")
                    for sel in ("#b1", "#md", "#ls"):
                        self.assertEqual(self.style(cdp, sid, sel, "borderRadius"), "8px", f"{tag} {sel} (the layout switch keeps 8)")
                    for sel in (".crumbs", ".ucd-crumb", ".ucf-crumb"):
                        self.assertEqual(self.style(cdp, sid, "#probe " + sel, "textTransform"), "none", f"{tag} {sel}")
                        self.assertEqual(self.style(cdp, sid, "#probe " + sel, "letterSpacing"), "normal", f"{tag} {sel}")
                    for sel in ("#sg button[aria-pressed=true]", "#sc button", "#cs button"):
                        bg, fg = (self.style(cdp, sid, sel, p) for p in ("backgroundColor", "color"))
                        self.assertEqual(self.style(cdp, sid, sel, "backgroundImage"), "none", f"{tag} {sel}")
                        self.assertGreaterEqual(ratio(parse(bg), parse(fg)), 4.5, f"{tag} {sel} {bg} {fg}")
                        self.assertEqual(bg, "rgb(4, 32, 42)" if scheme == "dark" else "rgb(6, 47, 58)", f"{tag} {sel}")
                        self.assertEqual(fg, "rgb(255, 255, 255)", f"{tag} {sel}")
                    self.assertEqual(cdp.js("getComputedStyle(document.querySelector('#md'), '::before').borderRadius", sid), "8px", tag)
                    cdp.js("document.querySelector('#sg button').focus()", sid)
                    self.assertEqual(self.style(cdp, sid, "#sg button[aria-pressed=true]", "outlineColor"), "rgb(255, 255, 255)", tag)
                    self.assertEqual(self.style(cdp, sid, "#sg button[aria-pressed=true]", "outlineOffset"), "-3px", tag)
                    cdp.js("document.documentElement.style.setProperty('--pill-bg', 'linear-gradient(red, blue)')", sid)
                    for sel in ("#sg button[aria-pressed=true]", "#sc button", "#cs button"):
                        self.assertEqual(self.style(cdp, sid, sel, "backgroundImage"), "none", f"{tag} gradient brand {sel}")
                    nv = "rgb(4, 32, 42)" if scheme == "dark" else "rgb(6, 47, 58)"
                    self.assertNotEqual(self.style(cdp, sid, "#md button[aria-pressed=true]", "backgroundColor"), nv, f"{tag} top-bar switch keeps its own look")
                    self.assertEqual(self.style(cdp, sid, "#sc em", "color"), "rgb(255, 255, 255)", tag)
                    cdp.js("document.querySelector('#cs button').focus()", sid)
                    self.assertEqual(self.style(cdp, sid, "#cs button", "outlineColor"), "rgb(255, 255, 255)", tag)
                    self.assertEqual(self.style(cdp, sid, "#cs button", "outlineOffset"), "-3px", tag)
                    cdp.js("document.querySelector('#sc button').focus()", sid)
                    self.assertEqual(self.style(cdp, sid, "#sc button", "outlineColor"), "rgb(255, 255, 255)", f"{tag} aria-checked focus")
                    self.assertEqual(self.style(cdp, sid, "#sc button", "outlineOffset"), "-3px", f"{tag} aria-checked focus")
                    em = self.style(cdp, sid, "#sg em", "color")
                    self.assertEqual(em, self.style(cdp, sid, "#sg button[aria-pressed=true]", "color"), tag)
                    self.assertEqual(self.style(cdp, sid, "#sg button[aria-pressed=false]", "backgroundColor"), "rgba(0, 0, 0, 0)", tag)
                    self.assertTrue(cdp.js("document.documentElement.scrollWidth <= window.innerWidth", sid), tag)

    def test_dark_chosen_segment_has_a_visible_edge_light_has_none(self):
        html = page.page_html(branding=page.NO_BRAND, theme=NAME)
        sels = ("#sg button[aria-pressed=true]", "#sc button", "#cs button")
        with chrome() as cdp:
            for scheme in ("light", "dark"):
                for w in SIZES:
                    sid = self.load(cdp, w, scheme, html)
                    tag = f"{scheme} {w}"
                    grounds = {n: parse(cdp.js("(() => { const d = document.createElement('i'); d.style.background = 'var(%s)'; document.body.appendChild(d); return getComputedStyle(d).backgroundColor; })()" % n, sid)) for n in ("--bg", "--surface", "--band-bg", "--page-bg")}
                    grad = cdp.js("getComputedStyle(document.documentElement).getPropertyValue('--page-grad')", sid)
                    for i, hx in enumerate(re.findall(r"#([0-9A-Fa-f]{6})", grad)):
                        grounds["grad%d" % i] = tuple(int(hx[k:k + 2], 16) for k in (0, 2, 4))
                    for sel in sels:
                        shadow = self.style(cdp, sid, sel, "boxShadow")
                        if scheme == "light":
                            self.assertEqual(shadow, "none", f"{tag} {sel}")
                            continue
                        self.assertRegex(shadow, r"^rgb\(111, 127, 163\) 0px 0px 0px 1px inset$", f"{tag} {sel}")
                        edge = parse(shadow)
                        for n, g in grounds.items():
                            self.assertGreaterEqual(ratio(edge, g), 3.0, f"{tag} {sel} edge on {n} {g}")
                        self.assertEqual(self.style(cdp, sid, sel, "color"), "rgb(255, 255, 255)", f"{tag} {sel}")
                        self.assertEqual(self.style(cdp, sid, sel, "borderTopWidth"), "0px", f"{tag} {sel} layout does not move")
                    self.assertEqual(self.style(cdp, sid, "#sg button[aria-pressed=false]", "boxShadow"), "none", tag)
                    self.assertEqual(self.style(cdp, sid, "#md button[aria-pressed=true]", "boxShadow") == "none", True, f"{tag} top-bar switch has no ring")
                    cdp.js("document.querySelector('#sg button').focus()", sid)
                    self.assertEqual(self.style(cdp, sid, "#sg button[aria-pressed=true]", "outlineColor"), "rgb(255, 255, 255)", tag)
                    self.assertEqual(self.style(cdp, sid, "#sg button[aria-pressed=true]", "outlineOffset"), "-3px", tag)
                    if scheme == "dark":
                        self.assertGreaterEqual(ratio((255, 255, 255), parse(self.style(cdp, sid, "#sg button[aria-pressed=true]", "boxShadow"))), 3.0, tag + " focus ring clear of the edge")

    def test_auto_follows_the_system_scheme(self):
        html = page.page_html(branding=page.NO_BRAND, theme=NAME)
        with chrome() as cdp:
            for scheme in ("dark", "light"):
                sid = self.load(cdp, 1400, "auto", html)
                cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
                for sel in ("#sg button[aria-pressed=true]", "#sc button", "#cs button"):
                    shadow = self.style(cdp, sid, sel, "boxShadow")
                    self.assertEqual(shadow != "none", scheme == "dark", f"auto {scheme} {sel} {shadow}")

    def test_cards_keeps_the_weight_the_pill_the_aqua_and_the_tracked_crumb(self):
        html = page.page_html(branding=page.NO_BRAND)
        with chrome() as cdp:
            for w in SIZES:
                sid = self.load(cdp, w, "light", html)
                self.assertEqual(self.style(cdp, sid, "#probe h2", "fontWeight"), "800", w)
                self.assertEqual(self.style(cdp, sid, "#b1", "borderRadius"), "999px", w)
                self.assertEqual(self.style(cdp, sid, "#sg", "borderRadius"), "999px", w)
                self.assertIn("gradient", self.style(cdp, sid, "#sg button[aria-pressed=true]", "backgroundImage"), w)
                self.assertEqual(self.style(cdp, sid, "#probe .crumbs", "textTransform"), "uppercase", w)
                self.assertEqual(self.style(cdp, sid, "#probe .ucd-crumb", "textTransform"), "uppercase", w)


class Layering(unittest.TestCase):
    def test_cards_page_is_the_page_with_no_theme_layer(self):
        plain = page.page_html(branding=page.NO_BRAND)
        self.assertEqual(plain, page.page_html(branding=page.NO_BRAND, theme=None))      # row 1363: the function still draws it; theme.name_for no longer asks for it
        self.assertNotIn('id="theme"', plain)
        self.assertNotIn("--weight-medium); }\n.btn, .seg", plain)

    def test_the_classic_block_is_the_end_of_rules_and_reaches_the_page(self):
        rules = (FOLDER / "rules.css").read_text(encoding="utf-8")
        lines = rules.rstrip("\n").split("\n")
        start = next(i for i, l in enumerate(lines) if l.startswith("/* Row 1319"))
        end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("/* Row ")), len(lines))
        self.assertEqual(end - start, 8, "the row's block is its comment and seven rules, up to the next row's comment (rows stack after it)")
        self.assertTrue(any(l.startswith("/* Row 1319, Classic type") for l in rules.split("\n")))
        self.assertIn("h1, h2, h3 { font-weight: var(--weight-medium); }", theme.css(NAME))


if __name__ == "__main__":
    unittest.main()
