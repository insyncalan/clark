"""Item 1194: the type badge text reaches 4.5:1 on every file kind, in the Classic theme's rules-2.css (the published file and the editor's View) and in the editor icon (docIcons.jsx)."""
import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


SRC = Path(__file__).resolve().parent.parent / "src" / "clark" / "page"
THEMES = Path(__file__).resolve().parent.parent / "src" / "clark" / "themes" / "prototype-2.0"
RULES_2 = THEMES / "rules-2.css"      # Row 1194's rules sit in rules-2.css (rules.css is at its size limit); the colours there are rgb()
KINDS = "PDF DOC XLS PPT JPG PNG TXT URL MAIL FILE".split()
# Row 1546 (ruled 23-11): the five fills the mock-up drew below 4.5:1 (PDF 4.04, XLS 3.59, PPT 3.43, PNG 4.16, TXT 2.08) are darkened, same hue, to the lightest value
# that reaches 4.5:1; the named exemption (MOCK_BELOW_4_5) is gone, all ten kinds assert 4.5:1.
FIVE = {"pdf": "#DA3D0B", "xls": "#1A8842", "ppt": "#C95014", "png": "#DD2582", "txt": "#A06C00"}

def as_hex(c):
    """A colour as #RRGGBB: rules-2.css writes rgb(r, g, b), the brand tokens write hex."""
    m = re.fullmatch(r"rgb\((\d+), (\d+), (\d+)\)", c)
    return "#%02X%02X%02X" % tuple(int(x) for x in m.groups()) if m else c


COLOUR = r"(#[0-9A-Fa-f]{3,6}|rgb\(\d+, \d+, \d+\))"


def tokens(css):
    """{--name: #RRGGBB} for every colour custom property in the css."""
    return {k: as_hex(v) for k, v in re.findall(r"(--[a-z-]+):\s*" + COLOUR, css)}


def lum(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    chan = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    chan = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in chan]
    return 0.2126 * chan[0] + 0.7152 * chan[1] + 0.0722 * chan[2]


def ratio(a, b):
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def table(src, name):
    body = re.search(r"export const %s = \{(.*?)\};" % name, src, re.S).group(1)
    return dict(re.findall(r'(\w+): "var\((--[a-z-]+)\)"', body))


class BadgeContrast(unittest.TestCase):
    def test_the_published_badge_text_reaches_4_5_on_every_kind(self):
        """Code measurement, not mock: the mock draws white text; this pins white on each fill at 4.5:1 or more (a TXT fill the mock does not have is one of them)."""
        css = RULES_2.read_text(encoding="utf-8")
        for kind in KINDS:
            rule = re.search(r"\.tpl-badge\.tpl-ic-%s \{([^}]*)\}" % kind, css)
            self.assertTrue(rule, kind)
            tok = tokens(css + (SRC.parent / "brand" / "tokens.css").read_text(encoding="utf-8"))
            val = lambda v: tok[v] if v.startswith("--") else v
            bg = val(re.search(r"background:\s*var\((--badge-[a-z]+)\)", rule.group(1)).group(1))
            fg = re.search(r"(?<!-)color:\s*var\((--badge-ink)\)", rule.group(1))
            r = ratio(val(fg.group(1)) if fg else "#fff", bg)
            self.assertGreaterEqual(r, 4.5, "%s published badge %.2f:1" % (kind, r))

    def test_the_editor_icon_band_text_reaches_4_5_on_every_kind(self):
        """Code measurement, not mock: the same 4.5:1 rule for the drawn page icon's band."""
        src = (SRC / "src" / "templates" / "docIcons.jsx").read_text(encoding="utf-8")
        band, text = table(src, "BAND"), table(src, "BAND_TEXT")
        tok = tokens(RULES_2.read_text(encoding="utf-8") + (SRC.parent / "brand" / "tokens.css").read_text(encoding="utf-8"))
        for kind in KINDS:
            self.assertIn(kind, band)
            r = ratio(tok[text.get(kind, "--white")], tok[band[kind]])
            self.assertGreaterEqual(r, 4.5, "%s editor icon band %.2f:1" % (kind, r))


    def test_the_editor_page_icon_band_is_the_tile_colour_on_every_kind(self):
        """Row 1194 round 3 (the approved mock-up, 18-11; five fills darkened by row 1546): the editor's page icon and the published tile use one palette (DA3D0B 1A8842 C95014 6B46C1 DD2582 A06C00, white text); the outline ink is 0E2430."""
        src = (SRC / "src" / "templates" / "docIcons.jsx").read_text(encoding="utf-8")
        band = table(src, "BAND")
        css = RULES_2.read_text(encoding="utf-8")
        tok = tokens(css)
        for kind in KINDS:
            rule = re.search(r"\.tpl-badge\.tpl-ic-%s \{([^}]*)\}" % kind, css)
            self.assertEqual(band[kind], re.search(r"background:\s*var\((--badge-[a-z]+)\)", rule.group(1)).group(1), "%s: page icon band token = tile token" % kind)
        self.assertEqual([tok["--badge-" + k].upper() for k in ("pdf", "xls", "ppt", "jpg", "png", "txt")], ["#DA3D0B", "#1A8842", "#C95014", "#6B46C1", "#DD2582", "#A06C00"])
        self.assertEqual(tok["--badge-ink"].upper(), "#0E2430")
        self.assertEqual(table(src, "BAND_TEXT"), {}, "white text on every band")

    def test_the_five_fills_are_the_measured_values(self):
        """Row 1546 AP1-AP5: each of the five fills is exactly the lightest value (one RGB step lighter in every channel fails) that reaches 4.5:1 with white; the other five are unchanged."""
        tok = tokens(RULES_2.read_text(encoding="utf-8"))
        for k, hexv in FIVE.items():
            self.assertEqual(tok["--badge-" + k].upper(), hexv, k)
            self.assertGreaterEqual(ratio("#ffffff", hexv), 4.5, k)
            lighter = "#" + "".join("%02X" % min(255, int(hexv[i:i + 2], 16) + 1) for i in (1, 3, 5))
            self.assertLess(ratio("#ffffff", lighter), 4.5, "%s: one step lighter must fail" % k)
        self.assertEqual({k: tok["--badge-" + k].upper() for k in ("doc", "jpg", "url", "mail", "file")},
                         {"doc": "#1F5FBF", "jpg": "#6B46C1", "url": "#5B47D8", "mail": "#0E7C86", "file": "#5A6B77"})

if __name__ == "__main__":
    unittest.main()
