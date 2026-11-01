"""A-D18: a tile's status word ("Overdue", "High", "On track") is drawn as a small bordered chip beside the figure (and in the label row on Project health), as in the prototype.

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
        # the 13 px caption size (var(--size-caption)): the former 13 px places use it, not the 14 px small size
        self.assertIn("font-size: var(--size-caption)", chip, "13 px, not smaller")
        self.assertNotIn("align-self", chip, "the chip is placed by its row (beside the figure), not on a line of its own")
        self.assertNotIn("background", chip, "no fill over the tile")
        for rag, token in (("g", "green"), ("a", "amber"), ("r", "red")):
            self.assertIn(f".fig.rag-{rag} .tw {{ color: var(--status-{token}-text); }}", self.css)

    def test_the_chip_sits_beside_the_figure_and_in_the_label_row_on_project_health(self):
        self.assertIn("display: flex; align-items: center;", rule(self.css, ".fig .vrow"), "the figure and its chip share a row, centred on each other")
        self.assertIn("margin-left: auto", rule(self.css, ".fig .vrow .tw, .fig .k .tw"), "at the right of the row, as the prototype's .k .sw")
        jsx = (PAGE / "src" / "components" / "Glance.jsx").read_text(encoding="utf-8")
        self.assertRegex(jsx, r'<span class="vrow">\s*<span class="v num">\{t\.value\}</span>\s*\{t\.word \? <span class="tw" aria-hidden="true">', "figure then chip, in one row")
        self.assertIn('Project health{t.word ? <span class="tw">{t.word}</span> : null}</span>', jsx, "Project health's chip is in its label row")
        self.assertNotIn("</div>\n      {t.word", jsx, "no chip on a line of its own under Project health")
        self.assertIn('#report[data-mode="edit"] .fig.health-fig .k { padding-right:', self.css, "in Edit the label row stops short of the move grip")

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
            self.assertIn("border: 1px solid currentColor; border-radius: var(--radius-sm); font-size: var(--size-caption); font-weight: var(--weight-medium)", text, name)
            self.assertIn(".fig.rag-r .tw { color: var(--status-red-text); }", text, name)
            self.assertIn('class:"tw","aria-hidden":"true"', text, name)


class Chip(G.Setup):
    script = """(() => {
      const rgb = (c) => c.match(/[\\d.]+/g).slice(0, 3).map(Number);
      const lum = ([r, g, b]) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
      const ratio = (a, b) => { const x = lum(rgb(a)), y = lum(rgb(b)); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
      const box = (e) => { if (!e) return null; const r = e.getBoundingClientRect(); return { l: r.left, t: r.top, r: r.right, b: r.bottom }; };
      const out = [];
      for (const key of ['overdue', 'risks', 'health']) {
        const fig = document.querySelector('[data-fig=' + key + ']'), w = fig && fig.querySelector('.tw');
        if (!w) { out.push({ key, missing: true }); continue; }
        const cs = getComputedStyle(w), ts = getComputedStyle(fig), cell = fig.closest('.tcell');
        out.push({ key, text: w.textContent, border: cs.borderTopStyle, width: cs.borderTopWidth, size: parseFloat(cs.fontSize),
                   edge: ratio(cs.borderTopColor, ts.backgroundColor), words: ratio(cs.color, ts.backgroundColor), hidden: w.getAttribute('aria-hidden'),
                   label: fig.getAttribute('aria-label'), chip: box(w), fig: box(fig), v: box(fig.querySelector('.v')), k: box(fig.querySelector('.k')),
                   dd: box(fig.querySelector('.dd')), grip: box(cell.querySelector('.tgrip')), eye: box(cell.querySelector('.teye')) });
      }
      return out;
    })()"""

    def colour_health_by_hand(self, p):
        """Project health's chip shows only when its colour is set by hand to another colour than its pill (On track): set it red in Edit."""
        p.edit()
        p.js("document.querySelector('[data-tile=health]').dispatchEvent(new MouseEvent('contextmenu', {bubbles: true, cancelable: true}))")
        p.until("!!document.querySelector('.tilemenu')", "the colour menu")
        p.js("document.querySelector('.tilemenu [data-outline=R]').click()")
        p.until("!!document.querySelector('[data-fig=health] .tw')", "Project health's chip")

    def look(self, r, width, dark, mode):
        where = f"{r['key']} {width}px {'dark' if dark else 'light'} {mode}"
        c = r["chip"]
        mid = (c["t"] + c["b"]) / 2
        self.assertEqual((r["border"], r["width"]), ("solid", "1px"), where)
        self.assertGreaterEqual(r["size"], 13, where)
        self.assertGreaterEqual(r["edge"], 3, f"{where}: edge against the tile")
        self.assertGreaterEqual(r["words"], 4.5, f"{where}: word against the tile")
        self.assertLess(c["r"] - c["l"], r["fig"]["r"] - r["fig"]["l"] - 20, f"{where}: the chip is as wide as its word, not the tile")
        self.assertLessEqual(c["r"], r["fig"]["r"], f"{where}: inside the tile")
        if r["key"] == "health":
            self.assertEqual(r["hidden"], None, f"{where}: Project health's chip stays readable")
            self.assertTrue(r["k"]["t"] <= mid <= r["k"]["b"], f"{where}: the chip is in the label row")
            self.assertGreater(c["l"], r["k"]["l"] + 80, f"{where}: right of the label, which is at the left")
            self.assertGreater(c["l"] - r["fig"]["l"], (r["fig"]["r"] - c["r"]) + 20, f"{where}: at the right of the row, not the left")
            if mode == "edit":
                self.assertLessEqual(c["r"], r["grip"]["l"], f"{where}: the move grip does not cover the chip")
        else:
            self.assertEqual(r["hidden"], "true", where)
            self.assertTrue(r["label"].endswith(". " + r["text"]) or (". " + r["text"] + ". Opens") in r["label"], f"{where}: the spoken name ends with the word, once")
            self.assertTrue(r["v"]["t"] <= mid <= r["v"]["b"], f"{where}: the chip's centre is in the figure's row")
            self.assertGreaterEqual(c["l"], r["v"]["r"], f"{where}: the chip is right of the figure, not under it")
            self.assertGreater(c["l"] - r["fig"]["l"], (r["fig"]["r"] - c["r"]) + 20, f"{where}: at the right of the row, not the left")
            self.assertLessEqual(c["b"], r["dd"]["t"] + 1, f"{where}: not over the detail line")
            if mode == "edit":
                self.assertGreaterEqual(c["t"], r["eye"]["b"] - 1, f"{where}: under the grip and eye, not over them")

    def test_the_word_is_a_chip_beside_the_figure_at_1400_and_900_in_light_and_dark_in_view_and_edit(self):
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark), chrome() as cdp:
                    p = self.show(cdp, width, dark)
                    self.colour_health_by_hand(p)
                    p.view()
                    for r in p.js(self.script):
                        self.assertFalse(r.get("missing"), f"{r['key']} has its chip")
                        self.look(r, width, dark, "view")
                    p.edit()
                    for r in p.js(self.script):
                        self.assertFalse(r.get("missing"), f"{r['key']} has its chip")
                        self.look(r, width, dark, "edit")


if __name__ == "__main__":
    unittest.main()
