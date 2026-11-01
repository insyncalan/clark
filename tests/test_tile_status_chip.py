"""A-D18: a tile's status word ("Overdue", "High", "On track") is drawn as a small bordered chip under the figure.

Run: python3 dev/run_tests.py test_tile_status_chip
`Source` reads the code and needs no browser. `Chip` draws the page in headless Chrome at 1400 and 900 px, light and dark.
The chip is in shell.css, so the editor page and the published page both carry it.
"""
import re
import unittest

from _paths import SRC

import test_glance_page as G
from test_server import chrome

PAGE = SRC / "clark" / "page"


def rule(css, selector):
    m = re.search(r"(?m)^" + re.escape(selector) + r" \{([^}]*)\}", css)
    return m.group(1) if m else ""


class Source(unittest.TestCase):
    css = (PAGE / "shell.css").read_text(encoding="utf-8")

    def test_the_word_is_a_bordered_chip_in_the_words_own_colour(self):
        chip = rule(self.css, ".fig .tw")
        self.assertIn("border: 1px solid currentColor", chip, "the edge is the text colour, so it keeps the text's contrast")
        self.assertIn("border-radius: var(--radius-sm)", chip)
        self.assertIn("font-size: var(--size-small)", chip, "13 px, not smaller")
        self.assertIn("align-self: flex-start", chip, "a chip as wide as its word, not the tile")
        self.assertNotIn("background", chip, "no fill over the tile")
        for rag, token in (("g", "green"), ("a", "amber"), ("r", "red")):
            self.assertIn(f".fig.rag-{rag} .tw {{ color: var(--status-{token}-text); }}", self.css)

    def test_the_chip_uses_tokens_only(self):
        chip = rule(self.css, ".fig .tw")
        self.assertNotRegex(chip, r"#[0-9a-fA-F]{3,8}\b|rgb|hsl", "no hard-coded colour")

    def test_the_tile_names_the_word_once_for_a_screen_reader(self):
        jsx = (PAGE / "src" / "components" / "Glance.jsx").read_text(encoding="utf-8")
        self.assertIn('<span class="tw" aria-hidden="true">{t.word}</span>', jsx, "a figure's chip is hidden: its label already says the word")
        self.assertIn('${t.word ? ". " + t.word : ""}', jsx, "the figure's label carries the word")

    def test_both_built_pages_carry_the_css_and_the_markup(self):
        for name in ("page.html", "page-view.html"):
            text = (PAGE / name).read_text(encoding="utf-8")
            self.assertIn("border: 1px solid currentColor; border-radius: var(--radius-sm); font-size: var(--size-small); font-weight: var(--weight-medium)", text, name)
            self.assertIn(".fig.rag-r .tw { color: var(--status-red-text); }", text, name)
            self.assertIn('class:"tw","aria-hidden":"true"', text, name)


class Chip(G.Setup):
    script = """(() => {
      const rgb = (c) => c.match(/[\\d.]+/g).slice(0, 3).map(Number);
      const lum = ([r, g, b]) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
      const ratio = (a, b) => { const x = lum(rgb(a)), y = lum(rgb(b)); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
      const out = [];
      for (const key of ['overdue', 'risks']) {
        const fig = document.querySelector('[data-fig=' + key + ']'), w = fig && fig.querySelector('.tw');
        if (!w) { out.push({ key, missing: true }); continue; }
        const cs = getComputedStyle(w), ts = getComputedStyle(fig);
        out.push({ key, text: w.textContent, border: cs.borderTopStyle, width: cs.borderTopWidth, size: parseFloat(cs.fontSize),
                   edge: ratio(cs.borderTopColor, ts.backgroundColor), words: ratio(cs.color, ts.backgroundColor), hidden: w.getAttribute('aria-hidden'),
                   label: fig.getAttribute('aria-label'), wide: w.getBoundingClientRect().width < fig.getBoundingClientRect().width - 20 });
      }
      return out;
    })()"""

    def test_the_word_is_a_chip_that_reads_once_at_1400_and_900_in_light_and_dark(self):
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark), chrome() as cdp:
                    p = self.show(cdp, width, dark)
                    for r in p.js(self.script):
                        self.assertFalse(r.get("missing"), f"{r['key']} has its chip")
                        self.assertEqual((r["border"], r["width"]), ("solid", "1px"))
                        self.assertGreaterEqual(r["size"], 13)
                        self.assertGreaterEqual(r["edge"], 3, f"{r['key']} edge against the tile")
                        self.assertGreaterEqual(r["words"], 4.5, f"{r['key']} word against the tile")
                        self.assertEqual(r["hidden"], "true")
                        self.assertTrue(r["label"].endswith(". " + r["text"]) or (". " + r["text"] + ". Opens") in r["label"], "the spoken name ends with the word, once")
                        self.assertTrue(r["wide"], "the chip is as wide as its word, not the tile")


if __name__ == "__main__":
    unittest.main()
