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
        "/* Row 1195: the Work items section as the approved mock-up draws it, Classic only (Cards keeps today's rules and markup). Table cells, in the page and in Edit. */",
        '.wil-table th { font-size: var(--size-caption); }',
        '.wil-table td.wil-c-id, .wil-c-id { font-family: ui-monospace, Menlo, Consolas, monospace; font-weight: var(--weight-medium); font-variant-numeric: tabular-nums; color: var(--status-blue-text); }',
        '.wil-pr { border: 1px solid var(--grey-500); background: var(--surface); color: var(--text); font-weight: var(--weight-semibold); }',
        '.wil-pr.h, .wil-pr.u { border-color: color-mix(in srgb, currentColor 30%, transparent); }',
        '.wil-off .wil-pr { border-color: var(--grey-200); }',
        '.wil-table tr.wil-k-action:not(.wil-off) .ico, .wil-lines li.wil-k-action:not(.wil-off) .ico { background: var(--brand-blue-tint); color: var(--status-blue-text); }',
        '.wil-table tr.wil-k-risk:not(.wil-off) .ico, .wil-lines li.wil-k-risk:not(.wil-off) .ico { background: var(--tone-red-tint); color: var(--tone-red-text); }',
        '.wil-table tr.wil-k-issue:not(.wil-off) .ico, .wil-lines li.wil-k-issue:not(.wil-off) .ico { background: var(--tone-urgent); color: var(--tone-on-urgent); }',
        '.wil-table tr.wil-k-decision:not(.wil-off) .ico, .wil-lines li.wil-k-decision:not(.wil-off) .ico { background: var(--tone-green-tint); color: var(--tone-green-text); }',
        '.wil-table .wil-c-eye .ib { color: var(--text); }',
        '.wil-off .wil-c-eye .ib { color: var(--grey-500); }',
        '@media (max-width: 1100px) { .wil-table .wil-c-owner { width: 150px; } }',
        '@media (max-width: 1000px) {',
        '  .wil-table td.wil-c-due { white-space: nowrap; overflow-wrap: normal; }',
        '  .wil-table .wil-c-due { width: 116px; }',
        '}',
        "/* Row 1195: the Edit header order is the gear in the title row, the saved-views tabs, the filter line, then the table (grid order only; the markup is Cards' markup). */",
        '.wil:has(> .wil-views) { display: grid; grid-template-columns: minmax(0, 1fr); }',
        '.wil:has(> .wil-views) > * { order: 3; }',
        '.wil:has(> .wil-views) > .wil-say, .wil:has(> .wil-views) > .wil-form { order: 0; }',
        '.wil:has(> .wil-views) > .wil-views { order: 1; margin-top: var(--space-3); }',
        '.wil:has(> .wil-views) > .wil-line { order: 2; margin: 0 0 var(--space-3); }',
        '.wil-form { display: block; margin: 0; padding: 0; border: 0; background: none; }',
        '.wil-cw { position: absolute; top: var(--sec-pad-t); right: var(--sec-px); z-index: 6; display: flex; justify-content: flex-end; }',
        '.wil-gear { border: 1.5px solid var(--grey-200); }',
        '.wil-cfg { width: min(calc(var(--space-4) * 19), calc(100vw - var(--space-6))); }',
        '.wil-cfg h4 { font-family: var(--font-head); font-weight: var(--weight-semibold); color: var(--heading); }',
        '.wil-cfg .wil-sel > span, .wil-cfg .wil-f legend { font-weight: var(--weight-medium); color: var(--text-muted); }',
        '.wil-cfg .wil-opts input[type="checkbox"] { width: var(--space-4); height: var(--space-4); margin: 0; accent-color: var(--brand-blue); }',
        '.wil-cfg .wil-sel select:focus-visible, .wil-cfg .wil-sel input:focus-visible { outline: 2px solid var(--brand-blue); outline-offset: 1px; }',
        '.wil-cacts button { background-color: var(--pill-color); background-image: var(--pill-bg); color: var(--pill-fg); font-weight: var(--weight-semibold); }',
        "/* Configure lists the columns in the mock-up's order (Status, Owner, Due, Priority, Workstream, Milestone, ID); Type, which the mock-up does not draw, follows. What is saved and its order are unchanged. */",
        '.wil-cfg .wil-opts label { order: 8; }',
        '.wil-cfg .wil-opts label:has(> input[value="status"]) { order: 1; }',
        '.wil-cfg .wil-opts label:has(> input[value="owner"]) { order: 2; }',
        '.wil-cfg .wil-opts label:has(> input[value="due"]) { order: 3; }',
        '.wil-cfg .wil-opts label:has(> input[value="priority"]) { order: 4; }',
        '.wil-cfg .wil-opts label:has(> input[value="workstream"]) { order: 5; }',
        '.wil-cfg .wil-opts label:has(> input[value="milestone"]) { order: 6; }',
        '.wil-cfg .wil-opts label:has(> input[value="id"]) { order: 7; }',
        '/* The + stays the 34 px dashed square at every width and in every state, and the Add menu draws each kind as the letter tile the rows use. */',
        '.wil-add .newb { box-sizing: border-box; width: 34px; height: 34px; min-width: 0; padding: 0; justify-content: center; border: 1px dashed var(--grey-500); border-radius: var(--radius); background: none; color: var(--status-blue-text); }',
        '.wil-add .newb:hover, .wil-add .newb:focus-visible, .wil-add .newb[aria-expanded="true"] { background: var(--grey-50); border-color: var(--grey-500); color: var(--status-blue-text); }',
        '.wil-add .newb:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; }',
        '.wil-add .newb .w, .wil-add .newb:hover .w, .wil-add .newb:focus-visible .w, .wil-add .newb[aria-expanded="true"] .w, .wil-add .newb .nch { display: none; }',
        '.wil-add .ddmenu { min-width: calc(var(--space-8) * 2); padding: var(--space-1); border: 1px solid var(--grey-200); border-radius: var(--radius-lg); background: var(--surface); box-shadow: var(--shadow); }',
        '.wil-add .ddmenu [role="menuitem"] { display: flex; align-items: center; gap: var(--space-2); min-height: calc(var(--space-6) + var(--space-2)); padding: 0 var(--space-2); border-radius: var(--radius); font-weight: var(--weight-medium); color: var(--text); }',
        '.wil-add .ddmenu [role="menuitem"]:hover, .wil-add .ddmenu [role="menuitem"]:focus-visible { background: var(--grey-50); color: var(--text); }',
        '.wil-add .ddmenu [role="menuitem"]:focus-visible { outline: 0; }',
        '.wil-add .ddmenu [role="menuitem"] .mi { display: none; }',
        '.wil-add .ddmenu [role="menuitem"]::before { content: attr(data-kind); display: inline-grid; place-items: center; flex: none; width: var(--space-5); height: var(--space-5); border-radius: 6px; font-size: var(--size-caption); font-weight: var(--weight-semibold); line-height: 1; background: var(--tone-grey-tint); color: var(--tone-grey-text); }',
        '.wil-add .ddmenu [role="menuitem"][data-kind="action"]::before { content: "A"; background: var(--brand-blue-tint); color: var(--status-blue-text); }',
        '.wil-add .ddmenu [role="menuitem"][data-kind="risk"]::before { content: "R"; background: var(--tone-red-tint); color: var(--tone-red-text); }',
        '.wil-add .ddmenu [role="menuitem"][data-kind="issue"]::before { content: "I"; background: var(--tone-urgent); color: var(--tone-on-urgent); }',
        '.wil-add .ddmenu [role="menuitem"][data-kind="decision"]::before { content: "D"; background: var(--tone-green-tint); color: var(--tone-green-text); }',
        "/* The saved-views tabs: medium-weight tabs, grey count pills, a violet + New view, and the open tab's caret inside its underline. */",
        '.wil-views .vtab { font-weight: var(--weight-medium); }',
        '.wil-views .vtab em { font-weight: var(--weight-regular); color: var(--text-muted); }',
        '.wil-views .vnew { color: var(--status-blue-text); font-weight: var(--weight-medium); }',
        '.wil-views .vnew:hover { color: var(--status-blue-text); }',
        '.wil-views .vtabs { flex-wrap: wrap; overflow: visible; }',
        '.wil-views .vt { gap: 0; }',
        '.wil-views .vt:has(> .wil-vopts) .vtab { padding-right: calc(var(--space-5) + var(--space-1)); }',
        '.wil-views .vt > .wil-vopts { margin-left: calc(-1 * (var(--space-5) + var(--space-1))); }',
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
        lines = [l for l in RULES.split("\n")[1:] if l.strip()]
        self.assertEqual(lines, RULE_LINES)


if __name__ == "__main__":
    unittest.main()
