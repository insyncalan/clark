"""Row 1260, step 3, mutation survivors: the prototype-2.0 Theme folder keeps its exact token values and its exact rules.

Run: python3 dev/run_tests.py test_theme_prototype_pinned

The values are the prototype's rows as written into the folder; a change to any of them is a change of the look and must change this file too.
"""
import re
from collections import Counter
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
        '--tone-urgent': '#6B1D2A',
        '--size-body': '14px',
        '--bar-end': '#0B3F4C',
        '--accent-line': '#38E0EE',
        '--pill-bg': '#9CF0F4',
        '--pill-fg': '#062F3A',
        '--shadow': '0 8px 24px rgba(6, 47, 58, .18)',
        '--radius-lg': '12px',
        '--page-bg': '#f7f9fc',
        '--page-grad': 'linear-gradient(90deg, #fcfdfe, #f7f9fc)',
        '--band-bg': '#F3F5FB',
        '--line-soft': '#E9EDF6',
        '--gutter-rule': '#EEEBFB',
        '--sec-number-color': 'var(--brand-blue)',
        '--sec-number-size': '20px',
        # Re-pinned for row 1395 (spec Design rules 19-11, design lead, table row 2: pressed layout tile fill #ECE9FB, glyph #5B47D8).
        '--tile-on-bg': '#ECE9FB',
        '--tile-on-fg': 'var(--brand-blue)',
        '--pill-track': '#ECEFF6',
        '--pill-on-fg': '#4F35C9',
        '--sec-band-bg': 'rgba(255, 255, 255, .72)',
        '--ms-amber-shape': '#C58A00',
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
        '--page-bg': '#121a2a',
        '--page-grad': 'linear-gradient(90deg, #0f1523, #121a2a)',
        '--band-bg': '#1A2638',
        '--line-soft': '#222E42',
        '--gutter-rule': '#2A2650',
        '--sec-number-color': 'var(--brand-blue)',
        '--sec-number-size': '20px',
        '--tile-on-bg': 'var(--brand-blue-tint)',
        '--tile-on-fg': 'var(--brand-blue)',
        '--pill-track': '#1C3040',
        '--pill-on-fg': '#A99BFF',
        '--sec-band-bg': 'rgba(255, 255, 255, .04)',
        '--ms-amber-shape': '#E0A620',
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
        '.fline { border: 0; border-bottom: 1px solid #8994b0; border-radius: 0; background: none; padding: 8px 0; gap: 6px; }',
        '.fk.k-txt { display: inline-flex; align-items: center; gap: 4px; box-sizing: border-box; min-height: 25px; padding: 0 4px 0 9px; margin: 0 -4px 0 -9px; border-radius: 6px; background: #eef0f6; color: #1d2433; box-shadow: none; }',
        '.fhi { inset: 0 0 0 -9px; padding-left: 9px; }',
        ':root[data-theme=dark] .fline { border-bottom-color: var(--grey-500); }',
        ':root[data-theme=dark] .fk.k-txt { background: var(--grey-100); color: var(--text); }',
        '@media (prefers-color-scheme: dark) { :root[data-theme=auto] .fline { border-bottom-color: var(--grey-500); } :root[data-theme=auto] .fk.k-txt { background: var(--grey-100); color: var(--text); } }',
        '.fline-tail { margin-right: 0; }',
        '.vicons .lsw, .vicons .btn.sm.vgb { border-radius: var(--radius); }',
        '.vicons .seg.lsw button[aria-pressed="true"] { background-color: var(--grey-100); background-image: none; color: var(--heading); }',
        '.vicons .lsw button[aria-pressed="true"]:focus-visible { outline-color: var(--brand-blue); outline-offset: -2px; }',
        'table.items thead th + th, .wil-table thead th + th { border-left: 1px solid var(--grey-200); }',
        'html[data-mode="view"] .cover { display: none; }',
        'html[data-mode="view"] .sec { border-left: 2px solid var(--gutter-rule); padding-left: 20px; }',
        '@media print { html[data-mode="view"] .sec { border-left: 0; padding-left: 0; } }',
        "/* Row 1195: the Work items section as the approved mock-up draws it, Classic only (Cards keeps today's rules and markup). Table cells, in the page and in Edit. */",
        "/* Row 1195: the mock-up's measured colours, light; dark keeps the Theme's own tokens. */",
        '.wil { --wil-th: rgb(85, 103, 122); --wil-pr-bg: rgb(246, 248, 252); --wil-pr-fg: rgb(14, 36, 48); --wil-pr-bd: rgb(217, 224, 239); --wil-prh-bg: rgb(254, 240, 199); --wil-prh-fg: rgb(181, 71, 8); --wil-prh-bd: rgb(242, 217, 138); --wil-pru-bg: rgb(253, 236, 234); --wil-pru-fg: rgb(180, 35, 24); --wil-pru-bd: rgb(244, 199, 194); --wil-ta-bg: rgb(237, 233, 255); --wil-ta-fg: rgb(75, 58, 181); --wil-tr-bg: rgb(253, 236, 234); --wil-tr-fg: rgb(180, 35, 24); --wil-ti-bg: rgb(107, 31, 42); --wil-ti-fg: rgb(255, 255, 255); --wil-td-bg: rgb(231, 246, 236); --wil-td-fg: rgb(6, 118, 71); --wil-th-bg: rgb(238, 240, 244); --wil-th-fg: rgb(152, 162, 179); --wil-add-bd: rgb(152, 162, 179); --wil-add-fg: rgb(91, 71, 216); }',
        ':root[data-theme=dark] .wil { --wil-th: var(--text-muted); --wil-pr-bg: var(--surface); --wil-pr-fg: var(--text); --wil-pr-bd: var(--grey-500); --wil-prh-bg: var(--tone-amber-tint); --wil-prh-fg: var(--tone-amber-text); --wil-prh-bd: color-mix(in srgb, var(--tone-amber-text) 30%, transparent); --wil-pru-bg: var(--tone-red-tint); --wil-pru-fg: var(--tone-red-text); --wil-pru-bd: color-mix(in srgb, var(--tone-red-text) 30%, transparent); --wil-ta-bg: var(--brand-blue-tint); --wil-ta-fg: var(--status-blue-text); --wil-tr-bg: var(--tone-red-tint); --wil-tr-fg: var(--tone-red-text); --wil-ti-bg: var(--tone-urgent); --wil-ti-fg: var(--tone-on-urgent); --wil-td-bg: var(--tone-green-tint); --wil-td-fg: var(--tone-green-text); --wil-th-bg: var(--tone-grey-tint); --wil-th-fg: var(--tone-grey-text); --wil-add-bd: var(--grey-500); --wil-add-fg: var(--status-blue-text); }',
        '@media (prefers-color-scheme: dark) { :root[data-theme=auto] .wil { --wil-th: var(--text-muted); --wil-pr-bg: var(--surface); --wil-pr-fg: var(--text); --wil-pr-bd: var(--grey-500); --wil-prh-bg: var(--tone-amber-tint); --wil-prh-fg: var(--tone-amber-text); --wil-prh-bd: color-mix(in srgb, var(--tone-amber-text) 30%, transparent); --wil-pru-bg: var(--tone-red-tint); --wil-pru-fg: var(--tone-red-text); --wil-pru-bd: color-mix(in srgb, var(--tone-red-text) 30%, transparent); --wil-ta-bg: var(--brand-blue-tint); --wil-ta-fg: var(--status-blue-text); --wil-tr-bg: var(--tone-red-tint); --wil-tr-fg: var(--tone-red-text); --wil-ti-bg: var(--tone-urgent); --wil-ti-fg: var(--tone-on-urgent); --wil-td-bg: var(--tone-green-tint); --wil-td-fg: var(--tone-green-text); --wil-th-bg: var(--tone-grey-tint); --wil-th-fg: var(--tone-grey-text); --wil-add-bd: var(--grey-500); --wil-add-fg: var(--status-blue-text); } }',
        '.wil-table th { font-size: calc(var(--size-caption) - 1.5px); color: var(--wil-th); }',
        '.wil-table td.wil-c-id, .wil-c-id { font-family: ui-monospace, Menlo, Consolas, monospace; font-size: var(--size-caption); font-weight: var(--weight-medium); font-variant-numeric: tabular-nums; color: var(--status-blue); }',
        '.wil-pr { border: 1px solid var(--wil-pr-bd); border-radius: 6px; background: var(--wil-pr-bg); color: var(--wil-pr-fg); font-size: calc(var(--size-caption) - 1px); font-weight: var(--weight-medium); }',
        '.wil-pr.h { border-color: var(--wil-prh-bd); background: var(--wil-prh-bg); color: var(--wil-prh-fg); }',
        '.wil-pr.u { border-color: var(--wil-pru-bd); background: var(--wil-pru-bg); color: var(--wil-pru-fg); }',
        '.wil-off .wil-pr { border-color: var(--grey-200); }',
        '.wil-table tr.wil-k-action:not(.wil-off) .ico, .wil-lines li.wil-k-action:not(.wil-off) .ico { background: var(--wil-ta-bg); color: var(--wil-ta-fg); }',
        '.wil-table tr.wil-k-risk:not(.wil-off) .ico, .wil-lines li.wil-k-risk:not(.wil-off) .ico { background: var(--wil-tr-bg); color: var(--wil-tr-fg); }',
        '.wil-table tr.wil-k-issue:not(.wil-off) .ico, .wil-lines li.wil-k-issue:not(.wil-off) .ico { background: var(--wil-ti-bg); color: var(--wil-ti-fg); }',
        '.wil-table tr.wil-k-decision:not(.wil-off) .ico, .wil-lines li.wil-k-decision:not(.wil-off) .ico { background: var(--wil-td-bg); color: var(--wil-td-fg); }',
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
        '.wil-gear { border: 0; background: transparent; color: var(--text-muted); }',
        '.wil-gear:hover, .wil-gear[aria-expanded=true] { background: var(--grey-100); color: var(--text); }',
        "/* Row 1338: the gear is the mock-up's 32 px, and the title row keeps its right end free for it, so the Changed tag stands left of the gear and never under it. */",
        '.wil-gear { min-width: var(--space-6); min-height: var(--space-6); }',
        '.sec:has(.wil-cw) > .sec-head { padding-right: calc(var(--space-6) + var(--space-2) + 2px); }',
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
        '/* The + stays the 34 px dashed square at every width and in every state, and the Add menu draws the + icon on each line (item 1273 item 4, design lead ruling 20-11: the letter chips are gone). */',
        '.wil-add .newb { box-sizing: border-box; width: 34px; height: 34px; min-width: 0; padding: 0; justify-content: center; border: 1px dashed var(--wil-add-bd); border-radius: 6px; background: none; color: var(--wil-add-fg); }',
        '.wil-add .newb:hover, .wil-add .newb:focus-visible, .wil-add .newb[aria-expanded="true"] { background: var(--grey-50); border-color: var(--wil-add-bd); color: var(--wil-add-fg); }',
        '.wil-add .newb:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; }',
        '.wil-add .newb .w, .wil-add .newb:hover .w, .wil-add .newb:focus-visible .w, .wil-add .newb[aria-expanded="true"] .w, .wil-add .newb .nch { display: none; }',
        '.wil-add .ddmenu { min-width: calc(var(--space-8) * 2); padding: var(--space-1); border: 1px solid var(--grey-200); border-radius: var(--radius-lg); background: var(--surface); box-shadow: 0 10px 30px rgba(6, 47, 58, .2); }',
        '.wil-add .ddmenu [role="menuitem"] { display: flex; align-items: center; gap: var(--space-2); min-height: calc(var(--space-6) + var(--space-3)); padding: 0 var(--space-2); border-radius: var(--radius); font-weight: var(--weight-medium); color: var(--text); }',
        '.wil-add .ddmenu [role="menuitem"]:hover, .wil-add .ddmenu [role="menuitem"]:focus-visible { background: var(--grey-50); color: var(--text); }',
        '.wil-add .ddmenu [role="menuitem"]:focus-visible { outline: 0; }',
        "/* The saved-views tabs: medium-weight tabs, grey count pills, a violet + New view, and the open tab's caret inside its underline. */",
        '.wil-views .vtab { font-weight: var(--weight-medium); }',
        '.wil-views .vtab em { font-weight: var(--weight-regular); color: var(--text-muted); }',
        '.wil-views .vnew { color: var(--status-blue-text); font-weight: var(--weight-medium); }',
        '.wil-views .vnew:hover { color: var(--status-blue-text); }',
        '.wil-views .vtabs { flex-wrap: wrap; overflow: visible; }',
        '.wil-views .vt { gap: 0; }',
        '.wil-views .vt:has(> .wil-vopts) .vtab { padding-right: calc(var(--space-5) + var(--space-1)); }',
        '.wil-views .vt > .wil-vopts { margin-left: calc(-1 * (var(--space-5) + var(--space-1))); }',
        "/* Row 1195, the mock-up's last changes (Classic only): the View list's scroll bar is hidden, the status half-circle is 16 px, a dragged column heading is dimmed with a drop mark, Type is not drawn, an owner name is one line with an ellipsis, and a half-width row is the mock-up's two lines. */",
        '#report[data-mode="view"] .wil-scroll { scrollbar-width: none; }',
        '#report[data-mode="view"] .wil-scroll::-webkit-scrollbar { display: none; }',
        '.wil-half { width: 16px; height: 16px; }',
        '.wil-table th.wil-drop { box-shadow: inset 3px 0 var(--brand-blue); }',
        '.wil-table th.wil-dragging { opacity: 0.4; }',
        '.wil-table th[draggable="true"] { cursor: grab; }',
        '.wil-table .wil-c-type, .wil-cfg .wil-opts label:has(> input[value="type"]) { display: none; }',
        '.wil-table .wil-own .nm { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }',
        '.wil-lines li { grid-template-columns: calc(var(--space-5) + var(--space-1)) minmax(0, 1fr) auto; }',
        '.wil-lines .wil-t { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }',
        '.wil-lines .wil-hpr { grid-column: 3; grid-row: 1; justify-self: end; align-self: center; }',
        '.wil-lines .wil-m { grid-column: 2 / span 2; display: flex; flex-wrap: wrap; gap: 2px var(--space-3); }',
        '.wil-lines .wil-m > span { white-space: nowrap; }',
        '.wil-cap { font-size: calc(var(--size-caption) - 1.5px); color: rgb(85, 103, 122); }',
        ':root[data-theme=dark] .wil-cap { color: var(--text-muted); }',
        '@media (prefers-color-scheme: dark) { :root[data-theme=auto] .wil-cap { color: var(--text-muted); } }',
        '.wil-table .ico, .wil-lines .ico { width: calc(var(--space-5) + var(--space-1)); height: calc(var(--space-5) + var(--space-1)); border-radius: 7px; }',
        '.wil-table tr.wil-off .ico, .wil-lines li.wil-off .ico { background: var(--wil-th-bg); color: var(--wil-th-fg); }',
        '.wil-table .wil-c-owner { width: 170px; }',
        '.wil-table .wil-c-due { width: 104px; }',
        '.wil-table .wil-c-priority { width: 84px; }',
        '.wil-table .wil-c-id { width: 84px; }',
        '.wil-all-b { color: var(--status-blue); font-weight: var(--weight-medium); min-height: var(--space-6); padding: 6px 0; }',
        '/* Row 1311 (ruling 19-11): every other visible section, the summary (the Current state block, type current) left out, is a white panel on the page gradient: the class .band is set by logic/banding.js (CSS cannot count only the visible sections), so it follows a section shown or hidden. A pair (This week | Next week) is banded as one row. No radius, no left rule; a line between each visible section and the one above. */',
        '.secs > .sec.band { --sec-pad-t: 20px; --sec-px: 22px; background: var(--sec-band-bg); border-left: 0; border-radius: 0; padding: 20px 22px 18px; }',
        '.secs > .sec:not(.is-hidden):not(.drag-slot) ~ .sec:not(.is-hidden):not(.drag-slot) { border-top: 1px solid var(--line-soft); }',
        '.secs > .sec[data-type="current"] { padding: 0 0 18px; border-left: 0; }',
        '.secs > .sec.band .wil-cw { right: 22px; }      /* Edit sets --sec-px to 32px on a section, but the band\'s right padding is the literal 22px, so the gear stays 22px from the edge and the 10px gap to the Changed tag holds */',
        '@media (min-width: 901px) { html[data-density="comfortable"] .secs > .sec.slot-left.band { box-shadow: var(--space-5) 0 0 0 var(--sec-band-bg); } }',
        '@media print { .secs > .sec.band, .secs > .sec.slot-left, .secs > .sec.slot-right { background: none; border-radius: 0; box-shadow: none; } .secs > .sec.band, .secs > .sec[data-type="current"] { padding: 0; } }',
        '.wil-table td { padding-top: 9px; padding-bottom: 9px; }',
        '.wil-table tbody tr { height: 49px; }',
        '.wil-table td.wil-c-due { font-size: var(--size-caption); line-height: normal; }',
        '.wil-table .num { font-family: ui-monospace, Menlo, Consolas, monospace; font-size: var(--size-caption); line-height: normal; }',
        '.wil-table .due-l { font-size: calc(var(--size-caption) - 1.5px); line-height: normal; }',
            "/* Row 1319, Classic type and controls (generic; Cards layers none of this). Weight 600 for headings; buttons and segments take the 8px --radius instead of the pill (the three primary buttons are 8px navy rectangles too, see the block below); the chosen segment (not the top bar's Dashboard and Edit switch) is --brand-navy with --white text instead of aqua; crumbs are plain, not tracked capitals. */",
        'h1, h2, h3 { font-weight: var(--weight-medium); }',
        '.btn, .seg { border-radius: var(--radius); }',
        ':root:not([data-motion="reduce"]) .modes.seg.glide::before { border-radius: var(--radius); }',
        '.seg:not(.modes) button[aria-pressed="true"], .seg:not(.modes) button[aria-checked="true"], .cal-sc button[aria-current="true"] { background-color: var(--brand-navy); background-image: none; color: var(--white); }',
        '.seg:not(.modes) button[aria-pressed="true"] em, .seg:not(.modes) button[aria-checked="true"] em { color: var(--white); }',
        '.seg:not(.icons):not(.modes) button[aria-pressed="true"]:focus-visible, .seg:not(.icons):not(.modes) button[aria-checked="true"]:focus-visible, .cal-sc button[aria-current="true"]:focus-visible { outline-color: var(--white); outline-offset: -3px; }',
        '.crumbs, .ucd-crumb, .ucf-crumb { text-transform: none; letter-spacing: normal; }',
        '/* Row 1260 G4: Classic shows no sentence under the Milestones title in the Plan view; the Movement hint stays. */',
        '.wbar:has([data-mspv="plan"][aria-pressed="true"]) [data-mspage-hint] { display: none; }',
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

    def test_every_rule_line_is_exact(self):
        """Looked up by content, not position: a row added or moved above or between these lines changes nothing here, only a line that is missing,
        changed, extra or doubled does (each is named in the failure)."""
        older = RULES.split("\n/* Row 1318", 1)[0]      # the rows above this one are pinned here; this row's block, and any after it, are pinned in their own test files
        lines = Counter(l for l in older.split("\n")[1:] if l.strip())
        want = Counter(RULE_LINES)
        self.assertEqual(sorted((want - lines).elements()), [], "pinned lines missing or changed in rules.css")
        self.assertEqual(sorted((lines - want).elements()), [], "lines in rules.css that are not pinned")


if __name__ == "__main__":
    unittest.main()
