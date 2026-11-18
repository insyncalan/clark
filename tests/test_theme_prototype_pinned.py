"""Row 1260, step 3, mutation survivors: the prototype-2.0 Theme folder keeps its exact token values and its exact rules.

Run: python3 dev/run_tests.py test_theme_prototype_pinned

The values are the prototype's rows as written into the folder; a change to any of them is a change of the look and must change this file too.
"""
import re
import unittest

from _paths import ROOT

FOLDER = ROOT / "src" / "clark" / "themes" / "prototype-2.0"
TOKENS = (FOLDER / "tokens.css").read_text(encoding="utf-8")
RULES = (FOLDER / "rules.css").read_text(encoding="utf-8")
DECL = re.compile(r"(--[a-z0-9-]+)\s*:\s*([^;]+);")
LIGHT = {
        '--text': '#1D2433',
        '--heading': '#0F1A2E',
        '--grey-50': '#F6F8FC',
        '--grey-100': '#E9EDF6',
        '--grey-500': '#8794B3',
        '--status-amber-text': '#8A5A00',
        '--tone-amber-text': '#8A5A00',
        '--tone-blue-text': '#2F4BB8',
        '--tone-red-tint': '#FBECEA',
        '--tone-amber-tint': '#FBF1DA',
        '--tone-green-tint': '#E0F3EF',
        '--tone-blue-tint': '#E8EDFB',
        '--tone-grey-tint': '#ECEFF5',
        '--tone-urgent': '#7A1B2E',
        '--size-body': '14px',
        '--bar-end': '#0B3F4C',
        '--accent-line': '#38E0EE',
        '--pill-bg': '#9CF0F4',
        '--pill-fg': '#062F3A',
        '--shadow': '0 8px 24px rgba(6, 47, 58, .18)',
        '--radius-lg': '12px',
        '--page-bg': '#F6F8FC',
        '--page-grad': 'linear-gradient(90deg, #F8F9FD 0%, #EFF3FA 100%)',
        '--band-bg': '#F3F5FB',
        '--line-soft': '#E9EDF6',
        '--gutter-rule': '#EEEBFB',
        '--sec-number-color': 'var(--brand-blue)',
        '--sec-number-size': '20px',
    }
DARK = {
        '--bg': '#0E1620',
        '--surface': '#121C28',
        '--grey-50': '#151F2C',
        '--grey-100': '#222E42',
        '--grey-200': '#2B3850',
        '--grey-500': '#6F7FA3',
        '--text': '#E6EBF5',
        '--text-muted': '#A9B6D3',
        '--heading': '#F2F5FB',
        '--brand-blue-tint': '#2A2650',
        '--status-red-text': '#FF9B8A',
        '--status-amber-text': '#F0BE5A',
        '--status-green-text': '#4FD1BD',
        '--tone-red-text': '#FF9B8A',
        '--tone-amber-text': '#F0BE5A',
        '--tone-green-text': '#4FD1BD',
        '--tone-blue-text': '#9DB0FF',
        '--tone-red-tint': '#3A1B17',
        '--tone-amber-tint': '#352A10',
        '--tone-green-tint': '#11302B',
        '--tone-blue-tint': '#1B2547',
        '--tone-grey-tint': '#222E42',
        '--tone-urgent': '#B93A52',
        '--shadow': '0 8px 24px rgba(0, 0, 0, .6)',
        '--page-bg': '#0E1620',
        '--page-grad': 'linear-gradient(90deg, #08232D 0%, #0B2832 100%)',
        '--band-bg': '#1A2638',
        '--line-soft': '#222E42',
        '--gutter-rule': '#2A2650',
        '--sec-number-color': 'var(--brand-blue)',
        '--sec-number-size': '20px',
    }
RULE_LINES = [
        'body { background: var(--page-bg) var(--page-grad) fixed no-repeat; }',
        '@media print { body { background: var(--white); } }',
        '.sec { background: none; border: 0; border-left: 2px solid var(--gutter-rule); border-radius: 0; box-shadow: none; padding-left: 20px; transition: border-color .2s; }',
        '.sec:hover, .sec:focus-within { border-left-color: color-mix(in srgb, var(--brand-blue) 35%, var(--gutter-rule)); }',
        '#report[data-mode="edit"] .sec { border-left-color: var(--brand-blue); }',
        '@media print { .sec { border-left: 0; padding-left: 0; } }',
        '.secs { counter-reset: secn; }',
        '.secs > .sec { counter-increment: secn; }',
        '.secs > .sec.is-hidden { counter-increment: none; }',
        '.secs .sec-head::before { content: counter(secn); width: auto; height: auto; margin-right: var(--space-1); background: none; color: var(--sec-number-color); font-size: var(--sec-number-size); font-weight: var(--weight-semibold); line-height: 1.25; font-variant-numeric: tabular-nums; }',
        '.col { background: var(--band-bg); border-top: 3px solid var(--line-soft); }',
        '.col-h { background: var(--band-bg); }',
        '.boardbox { scrollbar-width: none; }',
        '.boardbox::-webkit-scrollbar { display: none; }',
        'html[data-mode="view"] .cover { display: none; }',
        'html[data-mode="view"] .sec { border-left: 2px solid var(--gutter-rule); padding-left: 20px; }',
        '@media print { html[data-mode="view"] .sec { border-left: 0; padding-left: 0; } }',
    ]


def decls(text):
    return {n: re.sub(r"\s+", " ", v.strip()) for n, v in DECL.findall(text)}


class ThemePrototypePinned(unittest.TestCase):
    def test_light_values_are_exact(self):
        block = re.search(r"^:root \{(.*?)^\}", TOKENS, re.S | re.M).group(1)
        self.assertEqual(decls(block), LIGHT)

    def test_dark_values_are_exact(self):
        block = re.search(r":root\[data-theme=dark\]\s*\{(.*?)\n\}", TOKENS, re.S).group(1)
        self.assertEqual(decls(block), DARK)

    def test_auto_values_are_exact(self):
        block = re.search(r":root\[data-theme=auto\]\s*\{(.*?)\n  \}", TOKENS, re.S).group(1)
        self.assertEqual(decls(block), DARK)

    def test_every_rule_line_is_exact_and_in_order(self):
        older = RULES.split("/* Row 1313 block", 1)[0]      # the row 1313 lines are pinned in test_theme_dashboard_1313
        lines = [l for l in older.split("\n")[1:] if l.strip()]
        self.assertEqual(lines, RULE_LINES)


if __name__ == "__main__":
    unittest.main()
