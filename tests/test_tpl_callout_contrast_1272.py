"""Row 1272 item 3: the Callout's text keeps 4.5:1 and its edge-drawn controls 3:1, in light and in dark, and the two decoration edges are pinned.

Computed from the committed brand tokens (src/clark/brand/tokens.css) and the Callout rules (shell.css), never from a typed colour. The box edge of a
tinted callout is a decoration (its words carry the meaning), so its figures are pinned, not held to 3:1.
Run: python3 dev/run_tests.py test_tpl_callout_contrast_1272
"""
import re
import unittest

from _paths import SRC
from test_dark_contrast import blend, dark_blocks, ratio

TOKENS = (SRC / "clark" / "brand" / "tokens.css").read_text(encoding="utf-8")
SHELL = (SRC / "clark" / "page" / "shell.css").read_text(encoding="utf-8")
TEXT, UI = 4.5, 3.0
PINNED = {"violet": 6.29, "amber": 2.22, "red": 5.44, "green": 4.5, "grey": 2.89}


def light():
    m = re.search(r":root\s*\{(.*?)\n\s*\}", TOKENS, re.S)
    return {n: v.upper() for n, v in re.findall(r"(--[\w-]+):\s*(#[0-9A-Fa-f]{6})\b", m.group(1))}


def themes():
    return [("light", light())] + [("dark", b) for b in dark_blocks(TOKENS)]


def kinds():
    """{colour: (fill token, ink token, edge status token or None)} read from the .tpl-callout.k-* rules."""
    out = {}
    for k, body in re.findall(r"\.tpl-callout\.k-(\w+) \{([^}]*)\}", SHELL):
        fill = re.search(r"--cc-fill: var\((--[\w-]+)\)", body)
        ink = re.search(r"--cc-ink: var\((--[\w-]+)\)", body)
        edge = re.search(r"--cc-edge: color-mix\(in srgb, var\((--[\w-]+)\) 45%", body)
        if fill and ink:
            out[k] = (fill.group(1), ink.group(1), edge.group(1) if edge else None)
    return out


def edge(t, fill, status):
    return blend(t[status], t[fill], 0.45)


class Contrast(unittest.TestCase):
    def test_the_five_tinted_kinds_are_read(self):
        self.assertEqual(sorted(kinds()), ["amber", "green", "grey", "red", "violet"])

    def test_ink_on_fill_is_4_5_in_both_themes_for_every_kind(self):
        for name, t in themes():
            for k, (fill, ink, _) in kinds().items():
                r = ratio(t[ink], t[fill])
                print(f"1272 callout text {k} {name}: {r:.2f}:1")
                self.assertGreaterEqual(r, TEXT, f"{k} {name}")

    def test_body_text_on_fill_is_4_5_in_both_themes(self):
        for name, t in themes():
            for k, (fill, _, _) in kinds().items():
                self.assertGreaterEqual(ratio(t["--text"], t[fill]), TEXT, f"{k} {name}")

    def test_the_edit_field_edge_is_3_to_1_on_the_surface_in_both_themes(self):
        for name, t in themes():
            r = ratio(t["--control-edge"], t.get("--surface", "#FFFFFF"))
            print(f"1272 control edge {name}: {r:.2f}:1")
            self.assertGreaterEqual(r, UI, name)
        self.assertLess(ratio(light()["--grey-300"], "#FFFFFF"), UI, "the old edge fell short")

    def test_the_swatch_edges_are_decorations_and_their_light_figures_are_pinned(self):
        # the colour buttons' swatch is the status colour against the page; the word beside it names the colour, so amber (2.22) and grey (2.89) stay decorations
        t = light()
        got = {k: round(ratio(t[status], t.get("--surface", "#FFFFFF")), 2) for k, (_, _, status) in kinds().items() if status}
        print("1272 swatch edge vs the page, light:", got)
        self.assertEqual(got, PINNED)
        self.assertLess(got["amber"], UI)
        self.assertLess(got["grey"], UI)


if __name__ == "__main__":
    unittest.main()
