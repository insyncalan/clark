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
# The spacing tokens (--space-N) stand for fixed pixel values; the checks below read them as pixels.
CSS = re.sub(r"var\(--space-(\d)\)", lambda m: re.search(r"--space-" + m.group(1) + r": (\d+px)", TOKENS).group(1), CSS)


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

    def test_the_gap_between_cards_is_a_token_and_the_side_gap_leaves_room_for_the_control(self):
        self.assertIn("gap: var(--secs-gap)", rule(".secs"))
        token = re.search(r":root \{ --secs-gap: 12px 24px;", CSS)
        self.assertTrue(token, "12 px between rows, 24 px (a right-hand section's control) between columns, in both densities")

    def test_the_section_spacing_comes_from_tokens_that_comfortable_redefines(self):
        sec = rule(".sec")
        for want in ("padding: var(--sec-pad-t) var(--sec-px) var(--sec-pad-b)", "--sec-px: var(--sec-inset)"):
            self.assertIn(want, sec)
        root = re.search(r":root \{ --secs-gap[^}]*\}", CSS).group(0)
        for want in ("--sec-inset: 0px", "--sec-pad-t: 12px", "--sec-pad-b: 4px", "--secs-pad: 4px 0 12px"):
            self.assertIn(want, root, "Compact is the default")
        comfortable = rule('html[data-density="comfortable"]')
        for want in ("--sec-inset: 20px", "--sec-pad-t: 14px", "--sec-pad-b: 10px", "--secs-pad: 0"):
            self.assertIn(want, comfortable)
        self.assertNotIn("secstyle", CSS.replace(".secstyles", ""), "the four section looks are gone: one density attribute")

    def test_one_square_before_each_heading_from_a_token(self):
        square = rule(".sec-head::before")
        self.assertIn("background: var(--brand-blue)", square)
        self.assertEqual(len(re.findall(r"\.sec-head::before|\.sec-h::before|\.sec::before", CSS.replace(".sec.drop-before.slot-left::before", ""))), 1)
        self.assertNotIn("#", re.sub(r"/\*.*?\*/", "", square), "a token, never a hard-coded colour")

    def test_the_square_stays_when_a_section_is_left_out(self):
        """Dimming the whole heading row would fade the square below 3 to 1, so only the title and the body dim."""
        self.assertIn("opacity: .75", rule(".sec.is-hidden > :not(.sec-ctl):not(.sec-head), .sec.is-hidden .sec-h"))
        self.assertIn("border-style: dashed", rule(".sec.is-hidden"))

    def test_a_left_out_title_keeps_4_5_to_1_on_the_card(self):
        """.75 keeps the title's text above 4.5 to 1 on the card surface in light (.65 gave 4.37 on the band)."""
        self.assertIn("opacity: .75", rule(".sec.is-hidden > :not(.sec-ctl):not(.sec-head), .sec.is-hidden .sec-h"))

    def test_compact_keeps_the_drag_drop_line(self):
        """The flat One card rule sets box-shadow: none on .sec and outranks .sec.drop-before, so it restates the line."""
        self.assertIn("box-shadow: 0 -3px 0 var(--brand-cyan)", rule('html:not([data-density="comfortable"]) .sec.drop-before'))

    def test_the_report_frame_steps_back_so_cards_are_not_inside_a_card(self):
        self.assertIn('html[data-density="comfortable"] .frame.report { padding: 4px 28px 0; background: transparent; border: 0; box-shadow: none; }', CSS)


class Styles(unittest.TestCase):
    def test_one_card_takes_the_cards_away_and_keeps_one_frame(self):
        """The report's own frame (.frame.report) is the one border; the inner .secs box draws none, so there are never two."""
        sec = rule('html:not([data-density="comfortable"]) .sec')
        for want in ("background: transparent", "border: 0", "box-shadow: none", "border-radius: 0", "border-top: 1px solid var(--grey-200)"):
            self.assertIn(want, sec)
        secs = rule('html:not([data-density="comfortable"]) .secs')
        for want in ("border: 0", "border-radius: 0", "background: transparent"):
            self.assertIn(want, secs)
        self.assertNotIn("1px solid", secs, "the inner box has no border of its own")
        self.assertNotIn('html:not([data-density="comfortable"]) .frame.report', CSS, "the frame keeps its own look: border, surface and padding")

    def test_a_pair_has_one_unbroken_line_and_the_first_row_has_none(self):
        first = rule('html:not([data-density="comfortable"]) .secs > .sec:first-child, html:not([data-density="comfortable"]) .secs > .sec.slot-left:first-child + .sec.slot-right')
        self.assertIn("border-top: 0", first, "no line in the first row, for either half of a pair")
        self.assertIn("margin-left: -24px; padding-left: 24px", CSS, "the right half reaches back across the 24 px gap, so the line has no break")
        self.assertIn("@media (min-width: 901px) {\n  html:not([data-density=\"comfortable\"]) .sec.slot-right { margin-left: -24px; padding-left: 24px; }", CSS)
        self.assertIn('html:not([data-density="comfortable"]) .sec.slot-right > .sec-ctl { left: 0; }', CSS, "the right half's control sits in the gap, inside its own box")
        self.assertIn(".secs { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: var(--secs-gap);", CSS, "the gap the right half reaches back across is 24 px")

    def test_the_edit_gutter_is_the_frames_side_padding_not_the_inner_boxs(self):
        """1400: the frame's 28 px side padding holds the 24 px control (left: -26px, from the base rule). 900: the frame widens to 36 px in Edit."""
        self.assertIn("left: -26px", rule(".sec-ctl").split("opacity")[0])
        self.assertIn("padding: 24px 28px", rule(".frame"))
        self.assertIn('html:not([data-density="comfortable"]) #report[data-mode="edit"] { padding-left: 36px; }', CSS)
        self.assertIn('html:not([data-density="comfortable"]) #report[data-mode="edit"] .sec { --sec-px: 0px; padding-left: 0; }', CSS)
        self.assertIn("left: -30px", CSS[CSS.index('html:not([data-density="comfortable"]) #report[data-mode="edit"] .sec > .sec-ctl'):])

    def test_the_density_rules_name_only_what_they_change(self):
        self.assertNotIn("::before", "".join(re.findall(r'html[^{,]*data-density[^{]*\{', CSS)), "the square is drawn once, in every density")

    def test_edit_at_900_keeps_the_card_padding_in_one_variable(self):
        self.assertIn('#report[data-mode="edit"] .sec { --sec-px: 32px; padding-left: 32px; }', CSS)

    def test_the_settings_words_describe_the_default(self):
        jsx = (ROOT / "src" / "clark" / "page" / "src" / "edit" / "Personal.jsx").read_text(encoding="utf-8")
        self.assertIn('["compact", "Compact", "The Dashboard sections run on in one flat page, with thin lines between them, so more fits on the screen."]', jsx)


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
