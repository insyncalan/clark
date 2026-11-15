"""Item 1194: the type badge text reaches 4.5:1 on every file kind, in the published file (css) and in the editor icon (docIcons.jsx)."""
import re
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src" / "clark" / "page"
KINDS = "PDF DOC XLS PPT JPG PNG TXT URL MAIL FILE".split()


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
    return dict(re.findall(r'(\w+): "(#[0-9A-Fa-f]{3,6})"', body))


class BadgeContrast(unittest.TestCase):
    def test_the_published_badge_text_reaches_4_5_on_every_kind(self):
        css = (SRC / "shell.css").read_text()
        for kind in KINDS:
            rule = re.search(r"\.tpl-badge\.tpl-ic-%s \{([^}]*)\}" % kind, css)
            self.assertTrue(rule, kind)
            bg = re.search(r"background:\s*(#[0-9A-Fa-f]{3,6})", rule.group(1)).group(1)
            fg = re.search(r"(?<!-)color:\s*(#[0-9A-Fa-f]{3,6})", rule.group(1))
            r = ratio(fg.group(1) if fg else "#fff", bg)
            self.assertGreaterEqual(r, 4.5, "%s published badge %.2f:1" % (kind, r))

    def test_the_editor_icon_band_text_reaches_4_5_on_every_kind(self):
        src = (SRC / "src" / "templates" / "docIcons.jsx").read_text()
        band, text = table(src, "BAND"), table(src, "BAND_TEXT")
        for kind in KINDS:
            self.assertIn(kind, band)
            r = ratio(text.get(kind, "#fff"), band[kind])
            self.assertGreaterEqual(r, 4.5, "%s editor icon band %.2f:1" % (kind, r))


if __name__ == "__main__":
    unittest.main()
