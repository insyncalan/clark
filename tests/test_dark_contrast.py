"""#108, #186: the dark-mode brand colour (a light violet) keeps its button text readable (WCAG AA) and stays visible on dark surfaces.

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


def blend(top, bottom, alpha):
    """The colour of `top` drawn at `alpha` over `bottom`, as '#RRGGBB'."""
    return "#" + "".join("%02X" % round(int(top[i:i + 2], 16) * alpha + int(bottom[i:i + 2], 16) * (1 - alpha)) for i in (1, 3, 5))


class SectionControlAtRest(unittest.TestCase):
    def test_in_the_card_padding_it_reads_at_text_level_contrast_in_light_and_in_dark(self):
        """#285: at 900 px and below the section control rests at --sh-rest-narrow (.85 light, .75 dark); its --text-muted icon, drawn at that
        opacity on the card (--surface), is at least 4.5:1, the text bar and not only the 3:1 bar for a control."""
        css = TOKENS.read_text(encoding="utf-8")
        light = css.split(":root[data-theme=dark]")[0]
        alpha = float(re.search(r"--sh-rest-narrow:\s*([.\d]+)", light).group(1))
        self.assertAlmostEqual(alpha, 0.85, places=2)
        self.assertGreaterEqual(ratio(blend("#475577", "#FFFFFF", alpha), "#FFFFFF"), 4.5, "light")
        dark = re.findall(r"--sh-rest-narrow:\s*([.\d]+)", css)
        self.assertEqual(len(dark), 3, "light, dark and following a dark computer")
        for block, a in zip(dark_blocks(css), dark[1:]):
            self.assertGreaterEqual(ratio(blend(block["--text-muted"], block["--surface"], float(a)), block["--surface"]), 4.5, "dark")

    def test_the_shell_reads_the_token_at_900_px_and_below(self):
        shell = (ROOT / "src" / "clark" / "page" / "shell.css").read_text(encoding="utf-8")
        self.assertRegex(shell, r"@media \(max-width: 900px\)[^\n]*--sh-rest: var\(--sh-rest-narrow")


class DarkBrandBlue(unittest.TestCase):
    def test_every_dark_block_is_read_and_has_the_new_blue(self):
        for label, path in (("tokens", TOKENS), ("page", PAGE)):
            blocks = dark_blocks(path.read_text(encoding="utf-8"))
            self.assertGreaterEqual(len(blocks), 2, label)
            for block in blocks:
                self.assertEqual(block["--brand-blue"], "#8F7BFF", label)
                self.assertEqual(block["--status-blue"], "#8F7BFF", label)

    def test_offline_page_uses_the_new_blue(self):
        text = (ROOT / "src" / "clark" / "app" / "offline.html").read_text(encoding="utf-8")
        self.assertNotIn("5B7BF5", text.upper())

    def test_border_use_is_visible_on_surface_and_on_grey_200(self):
        """The light violet is well over 3:1 on the dark surface and on grey-200 (#108's limit, a blue under 3:1 there, no longer applies)."""
        for block in dark_blocks(TOKENS.read_text(encoding="utf-8")):
            self.assertGreaterEqual(ratio(block["--brand-blue"], block["--surface"]), 3.0)
            self.assertGreaterEqual(ratio(block["--brand-blue"], block["--grey-200"]), 3.0)

    def setUp(self):
        self.dark = dark_tokens(TOKENS.read_text(encoding="utf-8"))

    def test_button_text_on_the_brand_colour_passes_aa(self):
        """In dark mode the text on the brand colour is the dark --text-on-brand (white is under 3:1 on the light violet)."""
        for block in dark_blocks(TOKENS.read_text(encoding="utf-8")):
            self.assertGreaterEqual(ratio(block["--text-on-brand"], block["--brand-blue"]), 4.5)
            self.assertLess(ratio("#FFFFFF", block["--brand-blue"]), 4.5, "white would not do, which is why the token is dark here")

    def test_blue_as_ring_or_border_stays_visible_on_dark_surfaces(self):
        for name in ("--surface", "--grey-50", "--grey-100"):
            self.assertGreaterEqual(ratio(self.dark["--brand-blue"], self.dark[name]), 3.0, name)

    def test_link_and_pill_text_colour_is_unchanged(self):
        self.assertEqual(self.dark["--status-blue-text"], "#B7A9FF")

    def test_built_page_carries_the_same_dark_blue(self):
        pages = dark_blocks(PAGE.read_text(encoding="utf-8"))
        want = dark_blocks(TOKENS.read_text(encoding="utf-8"))
        self.assertEqual(len(pages), len(want))
        for page, tok in zip(pages, want):
            for name in ("--brand-blue", "--status-blue", "--status-blue-text"):
                self.assertEqual(page[name], tok[name], name)


if __name__ == "__main__":
    unittest.main()
