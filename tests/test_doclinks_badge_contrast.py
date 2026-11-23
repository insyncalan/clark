"""Item 1194: the type badge text reaches 4.5:1 on every file kind, in the Classic theme's rules-2.css (the published file and the editor's View) and in the editor icon (docIcons.jsx)."""
import re
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src" / "clark" / "page"
THEMES = Path(__file__).resolve().parent.parent / "src" / "clark" / "themes" / "prototype-2.0"
RULES_2 = THEMES / "rules-2.css"      # Row 1194's rules sit in rules-2.css (rules.css is at its size limit); the colours there are rgb()
KINDS = "PDF DOC XLS PPT JPG PNG TXT URL MAIL FILE".split()
# Row 1194 round 3 (approved mock-up 18-11; the product manager's ruling of 23-11 about 20:50): these page-icon fills are the
# mock's own and white text on them measures below 4.5:1 (PDF 4.04, XLS 3.59, PPT 3.43, PNG 4.16, TXT 2.08). The narrowest named exemption: exactly these five, so a
# sixth kind that falls under 4.5:1 still fails here.
MOCK_BELOW_4_5 = {"PDF", "XLS", "PPT", "PNG", "TXT"}

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
            if kind in MOCK_BELOW_4_5:
                self.assertLess(r, 4.5, "%s is named as below 4.5:1 in MOCK_BELOW_4_5: take it out of the exemption" % kind)
            else:
                self.assertGreaterEqual(r, 4.5, "%s published badge %.2f:1" % (kind, r))

    def test_the_editor_icon_band_text_reaches_4_5_on_every_kind(self):
        """Code measurement, not mock: the same 4.5:1 rule for the drawn page icon's band."""
        src = (SRC / "src" / "templates" / "docIcons.jsx").read_text(encoding="utf-8")
        band, text = table(src, "BAND"), table(src, "BAND_TEXT")
        tok = tokens(RULES_2.read_text(encoding="utf-8") + (SRC.parent / "brand" / "tokens.css").read_text(encoding="utf-8"))
        for kind in KINDS:
            self.assertIn(kind, band)
            r = ratio(tok[text.get(kind, "--white")], tok[band[kind]])
            if kind in MOCK_BELOW_4_5:
                self.assertLess(r, 4.5, "%s is named as below 4.5:1 in MOCK_BELOW_4_5: take it out of the exemption" % kind)
            else:
                self.assertGreaterEqual(r, 4.5, "%s editor icon band %.2f:1" % (kind, r))


    def test_the_editor_page_icon_band_is_the_tile_colour_on_every_kind(self):
        """Row 1194 round 3 (the approved mock-up, 18-11): the editor's page icon and the published tile use the mock's page-icon palette (E8410C 1E9B4B E8601C 6B46C1 E0358B F2A400, white text); the outline ink is 0E2430."""
        src = (SRC / "src" / "templates" / "docIcons.jsx").read_text(encoding="utf-8")
        band = table(src, "BAND")
        css = RULES_2.read_text(encoding="utf-8")
        tok = tokens(css)
        for kind in KINDS:
            rule = re.search(r"\.tpl-badge\.tpl-ic-%s \{([^}]*)\}" % kind, css)
            self.assertEqual(band[kind], re.search(r"background:\s*var\((--badge-[a-z]+)\)", rule.group(1)).group(1), "%s: page icon band token = tile token" % kind)
        self.assertEqual([tok["--badge-" + k].upper() for k in ("pdf", "xls", "ppt", "jpg", "png", "txt")], ["#E8410C", "#1E9B4B", "#E8601C", "#6B46C1", "#E0358B", "#F2A400"])
        self.assertEqual(tok["--badge-ink"].upper(), "#0E2430")
        self.assertEqual(table(src, "BAND_TEXT"), {}, "white text on every band")


if __name__ == "__main__":
    unittest.main()
