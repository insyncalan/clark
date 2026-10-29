"""#108: the dark-mode brand blue keeps white button text readable (WCAG AA) and the blue stays visible on dark surfaces.

Run: python3 dev/run_tests.py test_dark_contrast

Computed from the committed tokens (and the built page), never hard-coded ratios.
"""
import re
import unittest

from _paths import ROOT

TOKENS = ROOT / "src" / "clark" / "brand" / "tokens.css"
PAGE = ROOT / "src" / "clark" / "page" / "page.html"


def dark_blocks(css):
    """Every dark token block: the data-theme=dark one and the one inside the prefers-color-scheme media query.

    Each is {name: '#RRGGBB'}. A page can carry more than one copy, so tests must check them all.
    """
    blocks = re.findall(r":root\[data-theme=(?:dark|auto)\]\s*\{(.*?)\n\s*\}", css, re.S)
    return [{n: v.upper() for n, v in re.findall(r"(--[\w-]+):\s*(#[0-9A-Fa-f]{6})\b", b)} for b in blocks]


def dark_tokens(css):
    """The first dark block (kept for the single-value checks); see dark_blocks for all of them."""
    return dark_blocks(css)[0]


def luminance(hex_colour):
    channels = [int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def ratio(a, b):
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


class DarkBrandBlue(unittest.TestCase):
    def test_every_dark_block_is_read_and_has_the_new_blue(self):
        for label, path in (("tokens", TOKENS), ("page", PAGE)):
            blocks = dark_blocks(path.read_text(encoding="utf-8"))
            self.assertGreaterEqual(len(blocks), 2, label)
            for block in blocks:
                self.assertEqual(block["--brand-blue"], "#3962FE", label)
                self.assertEqual(block["--status-blue"], "#3962FE", label)

    def test_offline_page_uses_the_new_blue(self):
        text = (ROOT / "src" / "clark" / "app" / "offline.html").read_text(encoding="utf-8")
        self.assertNotIn("5B7BF5", text.upper())

    def test_border_use_is_visible_on_surface_but_not_on_grey_200(self):
        """Recorded limit (#108): the blue is 3.37:1 on the surface, but under 3:1 on grey-200, so a blue border there needs another cue."""
        for block in dark_blocks(TOKENS.read_text(encoding="utf-8")):
            self.assertGreaterEqual(ratio(block["--brand-blue"], block["--surface"]), 3.0)
            self.assertLess(ratio(block["--brand-blue"], block["--grey-200"]), 3.0)

    def setUp(self):
        self.dark = dark_tokens(TOKENS.read_text(encoding="utf-8"))

    def test_white_button_text_passes_aa(self):
        for block in dark_blocks(TOKENS.read_text(encoding="utf-8")):
            self.assertGreaterEqual(round(ratio("#FFFFFF", block["--brand-blue"]), 2), 4.83)

    def test_blue_as_ring_or_border_stays_visible_on_dark_surfaces(self):
        for name in ("--surface", "--grey-50", "--grey-100"):
            self.assertGreaterEqual(ratio(self.dark["--brand-blue"], self.dark[name]), 3.0, name)

    def test_link_and_pill_text_colour_is_unchanged(self):
        self.assertEqual(self.dark["--status-blue-text"], "#8FA6FF")

    def test_built_page_carries_the_same_dark_blue(self):
        pages = dark_blocks(PAGE.read_text(encoding="utf-8"))
        want = dark_blocks(TOKENS.read_text(encoding="utf-8"))
        self.assertEqual(len(pages), len(want))
        for page, tok in zip(pages, want):
            for name in ("--brand-blue", "--status-blue", "--status-blue-text"):
                self.assertEqual(page[name], tok[name], name)


if __name__ == "__main__":
    unittest.main()
