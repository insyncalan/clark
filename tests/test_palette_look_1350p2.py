"""Row 1350 part 2: the quick bar list look in the Classic Theme, as the prototype draws it (mock-up app.css lines 1562-1565), at 1400 and 900.

Run: python3 dev/run_tests.py test_palette_look_1350p2
The real page with the Classic Theme layered, in Chrome, fictional data; computed styles are read off the drawn quick bar. Pinned: the query box padding
12px 14px, the input (38px tall, 15px text, padding 6px 10px), the list (padding 6px, longest 420px = min(52vh, 420px) on a 900px-tall window), the row
(grid 96px / flexible / auto, gap 4px 12px, padding 8px 10px, radius 6px, text 14px), the kind (12px, uppercase, .04em, muted), the hint (12px), the chosen
row (grey-100 fill, 2px focus ring, offset -2px). Cards, which is unmaintained, is the control: its quick bar keeps today's flex row. Chrome is required:
it fails, never skips, without it (set CLARK_CHROME)."""
import json
import re
import tempfile
import unittest

from _paths import ROOT
from clark import page, theme
from test_palette import DATA, LIST, Base
from test_server import Running, chrome

RULES = ((ROOT / "src" / "clark" / "themes" / "prototype-2.0" / "rules.css").read_text(encoding="utf-8") + (ROOT / "src" / "clark" / "themes" / "prototype-2.0" / "rules-2.css").read_text(encoding="utf-8"))
PROBE = """(() => { const q = (s) => document.querySelector(s), g = (e, k) => getComputedStyle(e)[k];
  const tok = (v, k) => { const i = document.createElement('i'); i.style[k] = v; document.body.appendChild(i); const r = getComputedStyle(i)[k]; i.remove(); return r; };
  const row = q('#palette .pal-row.on'), hint = q('#palette .pal-row .pal-more'), hrow = hint.parentElement, kind = row.querySelector('.pal-kind'), inp = q('.pal-q input'), box = q('.pal-q'), list = q('.pal-list');
  return { qPad: ['paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft'].map((k) => g(box, k)).join(' '),
    inMin: g(inp, 'minHeight'), inH: g(inp, 'height'), inFont: g(inp, 'fontSize'), inPad: ['paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft'].map((k) => g(inp, k)).join(' '),
    listPad: ['paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft'].map((k) => g(list, k)).join(' '), listMax: g(list, 'maxHeight'), vh: innerHeight,
    display: g(row, 'display'), cols: g(hrow, 'gridTemplateColumns').split(' '), gap: g(row, 'rowGap') + ' ' + g(row, 'columnGap'),
    pad: ['paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft'].map((k) => g(row, k)).join(' '), radius: g(row, 'borderTopLeftRadius'), font: g(row, 'fontSize'),
    kindFont: g(kind, 'fontSize'), kindCase: g(kind, 'textTransform'), kindTrack: g(kind, 'letterSpacing'), kindColor: g(kind, 'color'), hintFont: g(hint, 'fontSize'),
    onBg: g(row, 'backgroundColor'), onOutline: g(row, 'outlineWidth') + ' ' + g(row, 'outlineStyle') + ' ' + g(row, 'outlineColor'), onOffset: g(row, 'outlineOffset'),
    grey100: tok('var(--grey-100)', 'backgroundColor'), focus: tok('var(--focus)', 'outlineColor'), muted: tok('var(--text-muted)', 'color'), px12: tok('12px', 'fontSize'), em04: 0.04 * 12 + 'px' }; })()"""


class Look(Base):
    classic = True

    def setUp(self):
        css = theme.css("prototype-2.0") if self.classic else None
        self.s = Running(data_for=lambda code, archived=None: DATA.get(code), page_html=lambda: page.layer_theme(page.page_html(tempfile.mkdtemp()), css), projects=lambda archived=False: LIST)
        self.addCleanup(self.s.close)

    def measure(self, widths=(1400, 900)):
        out = {}
        with chrome() as cdp:
            p = self.visit(cdp)
            for w in widths:
                p.width(w)
                p.show()
                p.key("ArrowDown", 0, "ArrowDown", 40)
                out[w] = p.js(PROBE)
                p.key("Escape", 0, "Escape", 27)
                p.until("!document.querySelector('#palette[open]')", "the palette closed")
        return out

    def test_classic_quick_bar_list_look(self):
        for w, m in self.measure().items():
            at = f"at {w} px: {json.dumps(m)}"
            self.assertEqual(m["qPad"], "12px 14px 12px 14px", at)
            self.assertEqual((m["inMin"], m["inH"], m["inFont"], m["inPad"]), ("38px", "38px", "15px", "6px 10px 6px 10px"), at)
            self.assertEqual(m["listPad"], "6px 6px 6px 6px", at)
            self.assertEqual(m["vh"], 900, at)
            self.assertEqual(m["listMax"], "420px", "min(52vh, 420px) with 52vh = 468px: " + at)
            self.assertEqual(m["display"], "grid", at)
            self.assertEqual(m["cols"][0], "96px", at)
            self.assertGreater(float(m["cols"][2][:-2]), 0, "the hint column is as wide as its text: " + at)
            self.assertEqual(m["gap"], "4px 12px", at)
            self.assertEqual(m["pad"], "8px 10px 8px 10px", at)
            self.assertEqual((m["radius"], m["font"]), ("6px", "14px"), at)
            self.assertEqual((m["kindFont"], m["kindCase"], m["kindTrack"], m["kindColor"]), ("12px", "uppercase", "0.48px", m["muted"]), at)
            self.assertEqual(m["hintFont"], "12px", at)
            self.assertEqual(m["onBg"], m["grey100"], at)
            self.assertEqual(m["onOutline"], "2px solid " + m["focus"], at)
            self.assertEqual(m["onOffset"], "-2px", at)


    def test_the_row_stays_three_columns_at_1400_and_900_and_the_narrow_rule_is_in_the_classic_css(self):
        probe = "(() => { const r = document.querySelector('#palette .pal-row'), k = r.querySelector('.pal-kind'); return { cols: getComputedStyle(r).gridTemplateColumns.split(' ').length, kind: getComputedStyle(k).gridColumnStart + ' / ' + getComputedStyle(k).gridColumnEnd, first: getComputedStyle(r).gridTemplateColumns.split(' ')[0] }; })()"
        out = {}
        with chrome() as cdp:
            p = self.visit(cdp)
            for w in (1400, 900):
                p.width(w)
                p.show()
                out[w] = p.js(probe)
                p.key("Escape", 0, "Escape", 27)
                p.until("!document.querySelector('#palette[open]')", "the palette closed")
        for w in (1400, 900):
            self.assertEqual((out[w]["cols"], out[w]["first"], out[w]["kind"]), (3, "96px", "auto / auto"), f"at {w} px: {out[w]}")
        self.assertRegex(RULES, r"@media \(max-width: 700px\) \{ \.pal-row \{ grid-template-columns: minmax\(0, 1fr\) auto; \} \.pal-kind \{ grid-column: 1 / -1; \} \}")


class CardsControl(Look):
    classic = False

    def test_the_row_stays_three_columns_at_1400_and_900_and_the_narrow_rule_is_in_the_classic_css(self):
        m = self.measure((900,))[900]
        self.assertEqual((m["display"], m["pad"]), ("flex", "6px 10px 6px 10px"), "Cards keeps the flex row at 900 px: " + json.dumps(m))

    def test_classic_quick_bar_list_look(self):
        for w, m in self.measure().items():
            at = f"at {w} px: {json.dumps(m)}"
            self.assertEqual((m["display"], m["radius"], m["pad"], m["gap"]), ("flex", "4px", "6px 10px 6px 10px", "4px 10px"), "Cards keeps the flex row: " + at)
            self.assertEqual((m["kindFont"], m["inMin"], m["listMax"]), ("13px", "36px", "none"), at)


class Source(unittest.TestCase):
    def test_the_block_sits_before_row_1314_which_stays_the_last_row_block(self):
        heads = [m.group(1) for m in re.finditer(r"^/\* (Row [0-9]+)", RULES, re.M)]
        self.assertEqual(heads[-1], "Row 1314")
        self.assertIn("Row 1350", heads)
        self.assertLess(RULES.index("/* Row 1350 part 2"), RULES.index("/* Row 1314"))
        self.assertNotRegex(RULES[RULES.index("/* Row 1350 part 2"):RULES.index("/* Row 1314")], r"#\d")


if __name__ == "__main__":
    unittest.main()
