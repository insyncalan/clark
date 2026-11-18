"""Rows 1310 and 1311: the Classic (prototype-2.0) Theme has the Whisper page gradient, and every other visible section of the dashboard is a panel with no gutter rule.

Run: python3 dev/run_tests.py test_theme_banding_1311

Contrast is computed from the real token values: the band's translucent white is composited over the page gradient (its two ends and the middle,
the gradient runs across the window so the width does not change the colours, 1400 and 900 give the same range) and the text tokens are measured on it.
"""
import re
import tempfile
import time
import unittest
from pathlib import Path

from _paths import ROOT
from clark import page
from test_server import chrome

FOLDER = ROOT / "src" / "clark" / "themes" / "prototype-2.0"
TOKENS = (FOLDER / "tokens.css").read_text(encoding="utf-8")
RULES = (FOLDER / "rules.css").read_text(encoding="utf-8")
BRAND = (ROOT / "src" / "clark" / "brand" / "tokens.css").read_text(encoding="utf-8")
SEL = ".secs > .sec:nth-child(odd of :not(.is-hidden)):not(.is-hidden):not(.drag-slot)"
BLOCKS = {
    "light": r"^:root \{(.*?)^\}",
    "dark": r":root\[data-theme=dark\]\s*\{(.*?)\n\}",
    "auto": r":root\[data-theme=auto\]\s*\{(.*?)\n  \}",
}


def decls(text):
    return {n: re.sub(r"\s+", " ", v.strip()) for n, v in re.findall(r"(--[a-z0-9-]+)\s*:\s*([^;]+);", text)}


def theme(name):
    return decls(re.search(BLOCKS[name], TOKENS, re.S | re.M).group(1))


def brand(name):
    pat = {"light": r"^:root \{(.*?)^\}", "dark": r":root\[data-theme=dark\]\s*\{(.*?)\n\}"}[name]
    return decls(re.search(pat, BRAND, re.S | re.M).group(1))


def rule(selector, prefix=r"^"):
    m = re.search(prefix + re.escape(selector) + r" \{([^}]*)\}", RULES, re.M)
    assert m, selector
    return [d.strip() for d in m.group(1).split(";") if d.strip()]


def rgb(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


def lin(c):
    c /= 255
    return c / 12.92 if c <= .03928 else ((c + .055) / 1.055) ** 2.4


def lum(c):
    r, g, b = (lin(x) for x in c)
    return .2126 * r + .7152 * g + .0722 * b


def ratio(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + .05) / (lb + .05)


def over(rgba, under):
    r, g, b, a = rgba
    return [c * a + u * (1 - a) for c, u in zip((r, g, b), under)]


def band(value):
    n = [float(x) for x in re.search(r"rgba\((.*?)\)", value).group(1).split(",")]
    return n


def ends(grad):
    a, b = re.findall(r"#[0-9a-fA-F]{6}", grad)
    A, B = rgb(a), rgb(b)
    return [A, [(x + y) / 2 for x, y in zip(A, B)], B]


class Whisper(unittest.TestCase):
    def test_page_colour_and_gradient(self):
        self.assertEqual({k: (theme(k)["--page-bg"], theme(k)["--page-grad"]) for k in BLOCKS}, {
            "light": ("#f7f9fc", "linear-gradient(90deg, #fcfdfe, #f7f9fc)"),
            "dark": ("#121a2a", "linear-gradient(90deg, #0f1523, #121a2a)"),
            "auto": ("#121a2a", "linear-gradient(90deg, #0f1523, #121a2a)")})

    def test_page_colour_is_the_gradient_end(self):
        for k in BLOCKS:
            self.assertEqual(theme(k)["--page-bg"], re.findall(r"#[0-9a-f]{6}", theme(k)["--page-grad"])[-1])

    def test_body_is_fixed_no_repeat(self):
        self.assertEqual(rule("body"), ["background: var(--page-bg) var(--page-grad) fixed no-repeat"])


class Banding(unittest.TestCase):
    def test_band_tokens(self):
        self.assertEqual(theme("light")["--sec-band-bg"], "rgba(255, 255, 255, .72)")
        self.assertEqual(theme("dark")["--sec-band-bg"], "rgba(255, 255, 255, .04)")
        self.assertEqual(theme("auto")["--sec-band-bg"], theme("dark")["--sec-band-bg"])

    def test_band_declarations(self):
        self.assertEqual(rule(SEL), ["background: var(--sec-band-bg)", "border-left: 0", "border-radius: var(--radius-lg)"])

    def test_print_has_no_band(self):
        self.assertEqual(rule(SEL, prefix=r"^@media print \{ "), ["background: none", "border-radius: 0"])

    def test_odd_visible_sections_only(self):
        self.assertIn(":nth-child(odd of :not(.is-hidden))", SEL)
        self.assertIn(":not(.is-hidden)", SEL)
        self.assertIn(":not(.drag-slot)", SEL)
        self.assertNotIn(":nth-child(even)", RULES)

    def test_band_after_the_plain_section_and_view_rules(self):
        at = RULES.index("\n" + SEL)
        self.assertGreater(at, RULES.index("\n.sec { background: none;"))
        self.assertGreater(at, RULES.index('\nhtml[data-mode="view"] .sec {'))

    def test_other_sections_keep_the_gutter_rule(self):
        self.assertIn("border-left: 2px solid var(--gutter-rule)", rule(".sec"))
        self.assertEqual(theme("light")["--gutter-rule"], "#EEEBFB")
        self.assertEqual(theme("dark")["--gutter-rule"], "#2A2650")

    def test_band_has_no_literal_colour_in_rules(self):
        self.assertIsNone(re.search(r"#[0-9a-fA-F]{3,8}\b|rgba?\(", "\n".join(l for l in RULES.split("\n") if SEL in l)))


class Contrast(unittest.TestCase):
    def check(self, mode):
        t = theme(mode)
        b = brand("dark" if mode != "light" else "light")
        tok = lambda n: t.get(n) or b[n]
        worst = {}
        for under in ends(t["--page-grad"]):
            panel = over(band(t["--sec-band-bg"]), under)
            for name, need in (("--text", 4.5), ("--heading", 4.5), ("--text-muted", 4.5)):
                r = ratio(rgb(tok(name)), panel)
                worst[name] = min(worst.get(name, 99), r)
                self.assertGreaterEqual(r, need, (mode, name, r))
        return worst

    def test_light(self):
        print("contrast light", self.check("light"))

    def test_dark(self):
        print("contrast dark", self.check("dark"))

    def test_auto(self):
        print("contrast auto", self.check("auto"))

    def test_the_check_can_fail(self):
        self.assertLess(ratio(rgb("#bbbbbb"), [255, 255, 255]), 4.5)


class RealColours(unittest.TestCase):
    """The same ratios from what Chrome computes: the band's background, the text colours, and the page gradient's stops, at 1400 and 900."""

    def load(self, cdp, width, scheme):
        html = page.page_html(branding=page.NO_BRAND, theme="prototype-2.0")
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
        cdp.js("""(() => { document.documentElement.setAttribute('data-theme', %r); document.documentElement.setAttribute('data-mode', 'view');
            const secs = document.createElement('div'); secs.className = 'secs';
            secs.innerHTML = '<div class="sec"><div class="sec-head">One</div><p class="muted">m</p></div><div class="sec"><div class="sec-head">Two</div></div><div class="sec"><div class="sec-head">Three</div></div><div class="sec"><div class="sec-head">Four</div></div><div class="sec is-hidden"><div class="sec-head">Hidden</div></div>';
            document.body.appendChild(secs); })()""" % scheme, sid)
        return sid

    def test_the_band_follows_the_odd_visible_sections_and_text_reaches_4_5(self):
        nums = lambda v: [float(x) for x in re.findall(r"[\d.]+", v)]
        with chrome() as cdp:
            for scheme in ("light", "dark"):
                for w in (1400, 900):
                    sid = self.load(cdp, w, scheme)
                    tag = f"{scheme} {w}"
                    rows = cdp.js("[...document.querySelectorAll('.secs > .sec')].map((e) => { const s = getComputedStyle(e); return [s.backgroundColor, s.borderLeftWidth, s.borderTopLeftRadius]; })", sid)
                    self.assertNotEqual(rows[0][0], "rgba(0, 0, 0, 0)", tag)
                    self.assertEqual(rows[0][1:], ["0px", rows[0][2]], tag)
                    self.assertEqual(rows[1][0], "rgba(0, 0, 0, 0)", tag)      # the 2nd is not banded
                    self.assertEqual(rows[1][1], "2px", tag)
                    self.assertNotEqual(rows[2][0], "rgba(0, 0, 0, 0)", tag)      # the 3rd is
                    self.assertEqual(rows[3][0], "rgba(0, 0, 0, 0)", tag)
                    self.assertEqual(rows[4][0], "rgba(0, 0, 0, 0)", tag)      # an odd hidden one is not banded
                    self.assertNotEqual(rows[0][2], "0px", tag)
                    grad = cdp.js("getComputedStyle(document.body).backgroundImage", sid)
                    stops = [nums(x)[:3] for x in re.findall(r"rgb\([^)]*\)", grad)]
                    band = nums(rows[0][0])
                    text = {n: nums(cdp.js("getComputedStyle(document.querySelector(%r)).color" % q, sid))[:3]
                            for n, q in (("body text", ".secs .sec-head"), ("muted", ".secs .muted"))}
                    for under in stops:
                        panel = [c * band[3] + u * (1 - band[3]) for c, u in zip(band[:3], under)]
                        for n, c in text.items():
                            r = ratio(c, panel)
                            print(f"real {tag} {n} {r:.2f}")
                            self.assertGreaterEqual(r, 4.5, f"{tag} {n}")


class HiddenSectionsKeepTheAlternation(unittest.TestCase):
    """Row 1311 follow-up: the section numbers skip hidden sections, so the band must too (Edit draws hidden sections, dashed, in the list)."""

    load = RealColours.load

    def test_edit_with_hidden_sections_bands_the_odd_numbered_sections(self):
        with chrome() as cdp:
            for scheme in ("light", "dark"):
                sid = self.load(cdp, 1400, scheme)
                cdp.js("""(() => { document.documentElement.setAttribute('data-mode', 'edit');
                    document.querySelector('.secs').innerHTML = ['sec', 'sec is-hidden', 'sec', 'sec', 'sec is-hidden', 'sec'].map((c) => '<div class="' + c + '"><div class="sec-head">T</div></div>').join(''); })()""", sid)
                got = cdp.js("[...document.querySelectorAll('.secs > .sec')].map((e) => getComputedStyle(e).backgroundColor !== 'rgba(0, 0, 0, 0)')", sid)
                # visible sections are numbered 1, 2, 3, 4: the 1st and 3rd are banded (DOM positions 0 and 3), never a hidden one
                self.assertEqual(got, [True, False, False, True, False, False], scheme)


if __name__ == "__main__":
    unittest.main()
