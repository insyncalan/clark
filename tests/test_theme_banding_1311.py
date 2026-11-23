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

import esbuild  # noqa: E402  (dev/tools)
from clark import page
from test_server import chrome

FOLDER = ROOT / "src" / "clark" / "themes" / "prototype-2.0"
TOKENS = (FOLDER / "tokens.css").read_text(encoding="utf-8")
RULES = (FOLDER / "rules.css").read_text(encoding="utf-8")
BRAND = (ROOT / "src" / "clark" / "brand" / "tokens.css").read_text(encoding="utf-8")
LOGIC = ROOT / "src" / "clark" / "page" / "src" / "logic" / "banding.js"
SEL = ".secs > .sec.band"
HID = ":not(.is-hidden):not(.drag-slot)"
CMF = 'html[data-density="comfortable"] '
BLOCKS = {
    "light": r"^:root \{(.*?)^\}",
    "dark": r":root\[data-theme=dark\]\s*\{(.*?)\n\}",
    "auto": r":root\[data-theme=auto\]\s*\{(.*?)\n  \}",
}


def bundled():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "bd.js"
        done = esbuild.run(["--bundle", "--format=iife", "--global-name=BD", str(LOGIC), f"--outfile={out}"], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        return out.read_text(encoding="utf-8")


BUNDLE = None


def bundle():
    global BUNDLE
    BUNDLE = BUNDLE or bundled()
    return BUNDLE


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
        self.assertEqual(rule(SEL), ["--sec-pad-t: 20px", "--sec-px: 22px", "background: var(--sec-band-bg)", "border-left: 0", "border-radius: 0", "padding: 20px 22px 18px"])


    def test_band_is_a_class_not_a_count(self):
        """Ruling 19-11: CSS cannot count only the visible sections, so no :nth-child band rule is left."""
        self.assertNotIn("nth-child", RULES)

    def test_line_between_visible_sections(self):
        self.assertEqual(rule(".secs > .sec" + HID + " ~ .sec" + HID), ["border-top: 1px solid var(--line-soft)"])

    def test_summary_keeps_no_padding_top_left_right(self):
        self.assertEqual(rule('.secs > .sec[data-type="current"]'), ["padding: 0 0 18px", "border-left: 0"])

    def test_pair_fills_the_comfortable_gap_from_the_left_half(self):
        self.assertEqual(rule(CMF + ".secs > .sec.slot-left.band", prefix=r"^@media \(min-width: 901px\) \{ "), ["box-shadow: var(--space-5) 0 0 0 var(--sec-band-bg)"])

    def test_print_has_no_band(self):
        self.assertEqual(rule(".secs > .sec.band, .secs > .sec.slot-left, .secs > .sec.slot-right", prefix=r"^@media print \{ "),
                         ["background: none", "border-radius: 0", "box-shadow: none"])

    def test_other_sections_keep_the_gutter_rule(self):
        self.assertIn("border-left: 2px solid var(--gutter-rule)", rule(".sec"))
        self.assertEqual(theme("light")["--gutter-rule"], "#EEEBFB")
        self.assertEqual(theme("dark")["--gutter-rule"], "#2A2650")

    def test_band_has_no_literal_colour_in_rules(self):
        self.assertIsNone(re.search(r"#[0-9a-fA-F]{3,8}\b|rgba?\(", "\n".join(l for l in RULES.split("\n") if SEL in l or "slot-left" in l and "sec-band-bg" in l)))


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
        cdp.js(bundle() + "; BD.applyBands(document)", sid)
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
                    self.assertEqual(rows[0][2], "0px", tag)      # row 1311: square corners
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

    def test_pair_is_banded_whole_row_with_square_corners_at_1400(self):
        nums = lambda v: [float(x) for x in re.findall(r"[\d.]+", v)]
        with chrome() as cdp:
            for lead, dens in ((0, "compact"), (1, "compact"), (0, "comfortable"), (1, "comfortable")):      # the pair starts at an odd place (1st, 2nd child) or an even one
                sid = self.load(cdp, 1400, "light")
                cdp.js("document.documentElement.setAttribute('data-density', %r)" % dens, sid)
                cdp.js("""(() => { const secs = document.querySelector('.secs'); secs.innerHTML = %s
                    + '<div class="sec slot-left"><div class="sec-head">This week</div></div><div class="sec slot-right"><div class="sec-head">Next week</div></div><div class="sec slot-full"><div class="sec-head">After</div></div>'; BD.applyBands(document); })()""" % ("''" if lead == 0 else "'<div class=\"sec slot-full\"><div class=\"sec-head\">Lead</div></div>'"), sid)
                rows = cdp.js("[...document.querySelectorAll('.secs > .sec')].map((e) => { const s = getComputedStyle(e), r = e.getBoundingClientRect(); return [s.backgroundColor, s.borderTopLeftRadius, s.borderTopRightRadius, s.borderBottomLeftRadius, s.borderBottomRightRadius, s.boxShadow, r.left, r.right, r.top, r.bottom]; })", sid)
                a, b = rows[lead], rows[lead + 1]
                tag = f"lead {lead} {dens}"
                gap = b[6] - a[7]
                self.assertAlmostEqual(gap, 24 if dens == "comfortable" else 0, delta=1.5, msg=f"{tag} {rows}")
                for r in rows:
                    self.assertEqual(r[1:5], ["0px"] * 4, tag)
                if lead == 0:
                    self.assertEqual([r[0] == "rgba(0, 0, 0, 0)" for r in rows], [False, False, True], tag)      # the pair is the 1st, After the 2nd
                else:
                    self.assertEqual([r[0] == "rgba(0, 0, 0, 0)" for r in rows], [False, True, True, False], tag)      # Lead 1st, the pair 2nd (both halves plain), After 3rd
                self.assertEqual(a[0], b[0], tag)
                if dens == "comfortable" and lead == 1:
                    self.assertEqual(a[5], "none", tag + " (a plain pair has no shadow)")
                elif dens == "comfortable":
                    self.assertTrue(a[5].endswith("24px 0px 0px 0px"), tag + " (the left half fills the gap) " + a[5])
                    self.assertEqual(b[5], "none", tag)
                else:
                    self.assertEqual(a[5], "none", tag + " (no gap, no shadow)")
                self.assertEqual(a[8], b[8], tag)
                self.assertEqual(a[9], b[9], tag)


if __name__ == "__main__":
    unittest.main()
