"""

Run: python3 dev/run_tests.py test_font
The font checks: every file in vendor/fonts/readex-pro/ matches its manifest, the licence is there, the built page carries one
@font-face per vendored font file as `data:` URIs and nothing from outside, and in headless Chrome (required, never skipped)
the page body is set in Readex Pro. The size checks parse the CSS the build inlines (the demo tokens and the shell's styles)
and fail on any font-size, or size inside a font shorthand, below the design system's floor of 13 px.
"""
import base64
import hashlib
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import ROOT, SRC, TOOLS

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402

from clark import page, server as sv  # noqa: E402
from test_page import DATA, navigate  # noqa: E402
from test_server import Running, _Collect, chrome, wait  # noqa: E402

FONTS = ROOT / "vendor" / "fonts" / "readex-pro"
MANIFEST = json.loads((FONTS / "manifest.json").read_text(encoding="utf-8"))
FLOOR = 13.0                                           # px: the design system's floor for any text (design review F7, F8)


def tokens_in(css):
    """Every custom property declared in `css`, name to value (the last declaration wins, as in the demo brand)."""
    return {m.group(1): m.group(2).strip() for m in re.finditer(r"(--[a-z0-9-]+)\s*:\s*([^;}]+)", css)}


def size_px(value, tokens, depth=0):
    """A CSS font size in px: px, rem (16 px), pt, a var() of a token, or None when it can't be worked out (em, %, calc, a keyword)."""
    value = value.strip()
    m = re.fullmatch(r"var\(\s*(--[a-z0-9-]+)\s*(?:,\s*(.+))?\)", value)
    if m:
        inner = tokens.get(m.group(1), m.group(2))
        return size_px(inner, tokens, depth + 1) if inner is not None and depth < 5 else None
    m = re.fullmatch(r"(\d*\.?\d+)(px|rem|pt)", value)
    if not m:
        return None
    return float(m.group(1)) * {"px": 1, "rem": 16, "pt": 4 / 3}[m.group(2)]


def font_sizes(css, tokens=None):
    """[(where, size as written, px or None)] for every font-size and every font shorthand with a size in `css`."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    tokens = tokens if tokens is not None else tokens_in(css)
    out = []
    for m in re.finditer(r"(?<![-\w])font-size\s*:\s*([^;}]+)", css):
        value = m.group(1).strip()
        if value.lower() not in ("inherit", "initial", "unset", "revert"):
            out.append(("font-size", value, size_px(value, tokens)))
    for m in re.finditer(r"(?<![-\w])font\s*:\s*([^;}]+)", css):
        value = m.group(1).strip()
        if value.lower() in ("inherit", "initial", "unset", "revert"):
            continue
        # the size is the part before a "/" line height, or the first length or var(--size-*) in the value
        s = re.search(r"((?:\d*\.?\d+(?:px|rem|em|pt|%))|var\(\s*--size-[a-z0-9-]+\s*\)|(?:xx-small|x-small|small|medium|large|x-large|xx-large|smaller|larger))(?=\s*(?:/|\s|$))", value)
        out.append(("font", value, size_px(s.group(1), tokens) if s else None))
    return out


def too_small(css, tokens=None):
    return [f"{where}: {value}" for where, value, px in font_sizes(css, tokens) if px is None or px < FLOOR]


class Vendored(unittest.TestCase):
    def test_every_vendored_file_matches_its_manifest_and_nothing_else_is_there(self):
        on_disk = {p.name for p in FONTS.iterdir() if p.is_file()} - {"manifest.json"}
        self.assertEqual(on_disk, set(MANIFEST["files"]))
        for name, sha in MANIFEST["files"].items():
            self.assertEqual(hashlib.sha256((FONTS / name).read_bytes()).hexdigest(), sha, name)

    def test_the_licence_is_there_with_its_copyright_line_and_the_manifest_says_where_everything_came_from(self):
        text = (FONTS / "OFL.txt").read_text(encoding="utf-8")
        self.assertTrue(text.strip())
        self.assertIn("Copyright 2018 The Readex Pro Project Authors (https://github.com/ThomasJockin/readexpro)", text)
        self.assertIn("SIL Open Font License, Version 1.1", text)
        pkg = MANIFEST["package"]
        self.assertEqual((pkg["family"], pkg["licence"], pkg["from_creaite"]), ("Readex Pro", "OFL-1.1", False))
        self.assertIn("not from creaite", pkg["note"])
        self.assertTrue(pkg["source"].startswith("https://") and pkg["file_source"].startswith("https://"))
        for f in MANIFEST["fonts"]:
            self.assertIn(f["file"], MANIFEST["files"])
            self.assertEqual((FONTS / f["file"]).read_bytes()[:4], b"wOF2", "a woff2 file")

    def test_the_font_is_not_in_the_reuse_record_because_it_is_not_from_creaite(self):
        self.assertNotIn("Readex", (ROOT / "docs" / "REUSE-FROM-CREAITE.md").read_text(encoding="utf-8"))


class Built(unittest.TestCase):
    def setUp(self):
        self.html = page.PAGE.read_text(encoding="utf-8")

    def test_one_font_face_per_vendored_font_as_a_data_uri_and_no_outside_address(self):
        faces = re.findall(r"@font-face\s*\{[^}]*\}", self.html)
        self.assertEqual(len(faces), len(MANIFEST["fonts"]))
        for f, face in zip(MANIFEST["fonts"], faces):
            self.assertIn(f'font-family: "{f["family"]}"', face)
            self.assertIn(f'font-weight: {f["weight"]}', face)
            uris = re.findall(r"url\(([^)]*)\)", face)
            self.assertEqual(len(uris), 1)
            self.assertTrue(uris[0].startswith("data:font/woff2;base64,"), uris[0][:40])
            self.assertEqual(base64.b64decode(uris[0].split(",", 1)[1]), (FONTS / f["file"]).read_bytes())
        self.assertNotRegex(self.html, r"(?i)url\(\s*[\"']?(https?:)?//")
        self.assertNotIn("fonts.g", self.html)
        self.assertNotRegex(re.sub(r"data:font/woff2;base64,[A-Za-z0-9+/=]+", "", self.html), r"""(?i)\bsrc\s*:\s*url\(\s*[^d\s)]""")

    def test_the_font_faces_are_in_the_demo_block_the_policy_hashes_and_the_token_names_the_font(self):
        with tempfile.TemporaryDirectory() as none:
            hashes = sv.csp_hashes(sv.with_boot(page.page_html(none)))
        self.assertEqual(len(hashes["style"]), 1)
        self.assertLess(self.html.index("@font-face"), self.html.index("</style>"))
        self.assertIn("--font: \"Readex Pro\", Arial, \"Helvetica Neue\", sans-serif;", self.html)
        self.assertIn("font-src 'self' data:", sv.csp_policy(self.html))

    def test_the_build_is_repeatable_with_the_font_in(self):
        self.assertEqual(build_page.build(), build_page.build())
        self.assertEqual(self.html, build_page.build())


class RealBrowser(unittest.TestCase):
    def test_the_page_is_set_in_readex_pro_and_nothing_is_blocked(self):
        s = Running(data_for=DATA.get, page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(s.close)
        blocked = []
        handler = _Collect(blocked)
        sv.LOG.addHandler(handler)
        sv.LOG.setLevel("INFO")
        self.addCleanup(sv.LOG.removeHandler, handler)
        with mock.patch.dict(sv.CSP_REPORTS, since=__import__("time").time(), n=0, dropped=0):
            with chrome() as cdp:
                sid = navigate(cdp, s.port, "#dashboard&p=ABC")
                self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.ready", sid) == "1"), "the bundle ran")
                self.assertTrue(wait(lambda: cdp.js("document.fonts.status", sid) == "loaded"),
                                "the font loaded")
                for weight in (300, 400, 500):
                    self.assertIs(cdp.js(f"document.fonts.check('{weight} 15px \"Readex Pro\"')", sid), True, weight)
                self.assertTrue(cdp.js("getComputedStyle(document.body).fontFamily", sid).startswith('"Readex Pro"'))
                self.assertIs(cdp.js("[...document.fonts].some(f => f.family.replace(/\"/g, '') === 'Readex Pro' && f.status === 'loaded')", sid), True,
                              "the data: font is the one in use, not Arial")
                self.assertEqual(blocked, [], f"nothing was blocked by the policy, the font included: {blocked}")


class FontSizes(unittest.TestCase):
    """The floor: 13 px (design review F7 and F8: table headings were 12 px, type badges 11 px in the prototype)."""

    def inlined(self):
        css = build_page.page_css()
        css = re.sub(r"@font-face\s*\{[^}]*\}", "", css)           # the font data holds no sizes; keep the sums short
        return css

    def test_no_font_size_in_the_inlined_css_is_below_13px(self):
        css = self.inlined()
        found = font_sizes(css)
        self.assertGreater(len(found), 5, "the parser found the shell's sizes")
        self.assertEqual(too_small(css), [])

    def test_no_script_sets_a_font_size_below_13px(self):
        for p in sorted((build_page.SRC).rglob("*.js*")):
            text = p.read_text(encoding="utf-8")
            for m in re.finditer(r"""(?:fontSize|font-size)['"]?\s*[:=]\s*['"]?([^;,'"}\)]+)""", text):
                px = size_px(m.group(1) if re.search(r"[a-z]", m.group(1)) else m.group(1) + "px", {})
                self.assertTrue(px is not None and px >= FLOOR, f"{p.name}: {m.group(0)}")

    def test_the_check_itself_sees_px_rem_tokens_and_the_font_shorthand(self):
        tokens = ":root { --size-body: 15px; --size-caption: 12px; --size-small: 13px; }"
        self.assertEqual(too_small(".a { font-size: 12px }" + tokens), ["font-size: 12px"])
        self.assertEqual(too_small(".a { font-size: .75rem; }"), ["font-size: .75rem"])
        self.assertEqual(too_small(".a { font-size: 0.8125rem; }"), [])                          # 13 px exactly
        self.assertEqual(too_small(".a { font-size: var(--size-caption); }" + tokens), ["font-size: var(--size-caption)"])
        self.assertEqual(too_small(".a { font-size: var(--size-small); }" + tokens), [])
        self.assertEqual(too_small(".a { font: 300 11px/1.5 Arial; }"), ["font: 300 11px/1.5 Arial"])
        self.assertEqual(too_small(".a { font: 400 var(--size-caption)/1.2 var(--font); }" + tokens), ["font: 400 var(--size-caption)/1.2 var(--font)"])
        self.assertEqual(too_small(".a { font: 300 var(--size-body)/1.5 var(--font); }" + tokens), [])
        self.assertEqual(too_small(".a { font: inherit; } .b { font-size: inherit; }"), [])
        self.assertEqual(too_small(".a { font-size: 0.8em; }"), ["font-size: 0.8em"])              # can't be worked out: refused
        self.assertEqual(too_small(".a { font-size: 12px } /* font-size: 8px */ .b { line-height: 1.2; font-weight: 500 }"), ["font-size: 12px"])


if __name__ == "__main__":
    unittest.main()
