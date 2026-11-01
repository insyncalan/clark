"""A-D3: each Dashboard section is its own card with a small coloured square before its heading (source and token checks, no browser).

Run: python3 dev/run_tests.py test_section_card_look
Pins the shared CSS (shell.css, so Edit's page and the published page both follow it), the four section styles, and that the square's
token keeps 3 to 1 against the card and the grey band in light and in dark. The drawn page is checked in test_section_card_look_page.
"""
import re
import unittest

from _paths import ROOT
from test_dark_contrast import dark_blocks, ratio

CSS = (ROOT / "src" / "clark" / "page" / "shell.css").read_text(encoding="utf-8")
TOKENS = (ROOT / "src" / "clark" / "brand" / "tokens.css").read_text(encoding="utf-8")


def rule(selector):
    """The declarations of the one rule whose selector is exactly `selector`."""
    found = re.findall(r"(?m)^" + re.escape(selector) + r" \{ (.*?) \}", CSS)
    assert len(found) == 1, f"{selector}: {len(found)} rules"
    return found[0]


def hexed(v):
    v = v.lstrip("#").upper()
    return "#" + ("".join(c * 2 for c in v) if len(v) == 3 else v)


def light(name):
    return hexed(re.search(r"(?<![\w-])" + re.escape(name) + r":\s*(#[0-9A-Fa-f]{3,6})\b", TOKENS).group(1))


class Card(unittest.TestCase):
    def test_a_section_is_a_card_by_default(self):
        sec = rule(".sec")
        for want in ("background: var(--surface)", "border: 1px solid var(--grey-200)", "border-radius: var(--radius-lg)", "box-shadow: var(--shadow)"):
            self.assertIn(want, sec)
        self.assertNotIn("border-top", sec, "no thin line between sections any more")

    def test_the_gap_between_cards_is_slim_and_roomy_is_roomier(self):
        slim = re.search(r"\.secs \{ display: grid;.*?gap: (\d+)px (\d+)px", CSS).groups()
        roomy = re.search(r'html\[data-secstyle="roomy"\] \.secs \{ gap: (\d+)px (\d+)px', CSS).groups()
        self.assertGreater(int(roomy[0]), int(slim[0]))
        self.assertGreaterEqual(int(slim[1]), 24, "the side gap leaves room for a right-hand section's control")

    def test_one_square_before_each_heading_from_a_token(self):
        square = rule(".sec-head::before")
        self.assertIn("background: var(--brand-blue)", square)
        self.assertEqual(len(re.findall(r"\.sec-head::before|\.sec-h::before|\.sec::before", CSS.replace(".sec.drop-before.slot-left::before", ""))), 1)
        self.assertNotIn("#", re.sub(r"/\*.*?\*/", "", square), "a token, never a hard-coded colour")

    def test_the_square_stays_when_a_section_is_left_out(self):
        """Dimming the whole heading row would fade the square below 3 to 1, so only the title and the body dim."""
        self.assertIn("opacity: .65", rule(".sec.is-hidden > :not(.sec-ctl):not(.sec-head), .sec.is-hidden .sec-h"))
        self.assertIn("border-style: dashed", rule(".sec.is-hidden"))

    def test_the_report_frame_steps_back_so_cards_are_not_inside_a_card(self):
        self.assertIn('html:not([data-secstyle="card"]) .frame.report { padding: 4px 28px 0; background: transparent; border: 0; box-shadow: none; }', CSS)


class Styles(unittest.TestCase):
    def test_grey_headers_put_the_band_on_the_heading_inside_the_card(self):
        self.assertIn("background: var(--grey-100)", rule('html[data-secstyle="grey"] .sec-head'))
        self.assertIn("padding-top: 0", rule('html[data-secstyle="grey"] .sec'))
        self.assertNotIn("border", rule('html[data-secstyle="grey"] .sec'), "the card's one border is not drawn again")

    def test_one_card_takes_the_cards_away_and_keeps_one_frame(self):
        sec = rule('html[data-secstyle="card"] .sec')
        for want in ("background: transparent", "border: 0", "box-shadow: none", "border-radius: 0", "border-top: 1px solid var(--grey-200)"):
            self.assertIn(want, sec)
        self.assertIn("border: 1px solid var(--grey-200)", rule('html[data-secstyle="card"] .secs'))
        self.assertIn("border-top: 0", rule('html[data-secstyle="card"] .secs > .sec:first-child'), "no line right under the frame's own edge")

    def test_each_style_names_only_what_it_changes(self):
        for style in ("roomy", "grey", "card"):
            self.assertNotIn("::before", "".join(re.findall(r'html\[data-secstyle="' + style + r'"\][^{]*\{', CSS)), "the square is drawn once, in every style")

    def test_edit_at_900_keeps_the_card_padding_in_one_variable(self):
        self.assertIn('#report[data-mode="edit"] .sec { --sec-px: 32px; padding-left: 32px; }', CSS)

    def test_the_settings_words_describe_the_default(self):
        jsx = (ROOT / "src" / "clark" / "page" / "src" / "edit" / "Personal.jsx").read_text(encoding="utf-8")
        self.assertIn('["slim", "Slim gaps", "Each section is its own card, close together."]', jsx)


class Contrast(unittest.TestCase):
    def test_the_square_has_3_to_1_on_every_ground_it_sits_on_in_light_and_dark(self):
        dark = dark_blocks(TOKENS)
        self.assertTrue(dark)
        for mode, get in [("light", light)] + [("dark", (lambda b: lambda n: b[n])(b)) for b in dark]:
            square = get("--brand-blue")
            for ground in ("--surface", "--grey-100"):
                self.assertGreaterEqual(ratio(square, get(ground)), 3.0, f"{mode}: square on {ground}")


if __name__ == "__main__":
    unittest.main()
