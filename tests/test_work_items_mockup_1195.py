"""Row 1195: the Work items section's Edit and View as the approved mock-up draws them (header order, tabs, the + and its menu, Configure, table cells).

Run: python3 dev/run_tests.py test_work_items_mockup_1195
The look is Classic only: every rule is in the Classic theme layer (src/clark/themes/prototype-2.0/rules.css), shell.css and edit.css are untouched,
and the Cards page is proved unchanged (its style blocks by md5 and its rendered Work items DOM, in Edit and View with the Add menu open, at 1400 and 900).
The rules are pinned by their CSS text; the order and the look are pinned in the served Classic page.
"""
import hashlib
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

import test_server  # noqa: F401  this file drives Chrome through the template harness (the browser tier reads this line)

from _new_page import reload_to_new_page
from _paths import SRC
from clark import changes, page, publish, theme
import test_tpl_workitems as T
from test_report_editor import Pg
from test_server import wait
from _real_server import real_server
import _testpage as testpage

PAGE = SRC / "clark" / "page"
NAME = "prototype-2.0"
RULES = (SRC / "clark" / "themes" / NAME / "rules.css").read_text(encoding="utf-8")
SHELL_CSS = (PAGE / "shell.css").read_text(encoding="utf-8")
EDIT_CSS = (PAGE / "src" / "edit" / "edit.css").read_text(encoding="utf-8")
JSX = (PAGE / "src" / "edit" / "templates" / "WorkItemsList.jsx").read_text(encoding="utf-8")
ROWS_JSX = (PAGE / "src" / "templates" / "WorkItemsList.jsx").read_text(encoding="utf-8")


# Every rule line this row adds, as written in the Classic theme's rules.css (comments dropped, white space folded).
GOLDEN_LINES = [
    ".wil { --wil-th: rgb(85, 103, 122); --wil-pr-bg: rgb(246, 248, 252); --wil-pr-fg: rgb(14, 36, 48); --wil-pr-bd: rgb(217, 224, 239); --wil-prh-bg: rgb(254, 240, 199); --wil-prh-fg: rgb(181, 71, 8); --wil-prh-bd: rgb(242, 217, 138); --wil-pru-bg: rgb(253, 236, 234); --wil-pru-fg: rgb(180, 35, 24); --wil-pru-bd: rgb(244, 199, 194); --wil-ta-bg: rgb(237, 233, 255); --wil-ta-fg: rgb(75, 58, 181); --wil-tr-bg: rgb(253, 236, 234); --wil-tr-fg: rgb(180, 35, 24); --wil-ti-bg: rgb(107, 31, 42); --wil-ti-fg: rgb(255, 255, 255); --wil-td-bg: rgb(231, 246, 236); --wil-td-fg: rgb(6, 118, 71); --wil-th-bg: rgb(238, 240, 244); --wil-th-fg: rgb(152, 162, 179); --wil-add-bd: rgb(152, 162, 179); --wil-add-fg: rgb(91, 71, 216); }",
    ":root[data-theme=dark] .wil { --wil-th: var(--text-muted); --wil-pr-bg: var(--surface); --wil-pr-fg: var(--text); --wil-pr-bd: var(--grey-500); --wil-prh-bg: var(--tone-amber-tint); --wil-prh-fg: var(--tone-amber-text); --wil-prh-bd: color-mix(in srgb, var(--tone-amber-text) 30%, transparent); --wil-pru-bg: var(--tone-red-tint); --wil-pru-fg: var(--tone-red-text); --wil-pru-bd: color-mix(in srgb, var(--tone-red-text) 30%, transparent); --wil-ta-bg: var(--brand-blue-tint); --wil-ta-fg: var(--status-blue-text); --wil-tr-bg: var(--tone-red-tint); --wil-tr-fg: var(--tone-red-text); --wil-ti-bg: var(--tone-urgent); --wil-ti-fg: var(--tone-on-urgent); --wil-td-bg: var(--tone-green-tint); --wil-td-fg: var(--tone-green-text); --wil-th-bg: var(--tone-grey-tint); --wil-th-fg: var(--tone-grey-text); --wil-add-bd: var(--grey-500); --wil-add-fg: var(--status-blue-text); }",
    "@media (prefers-color-scheme: dark) { :root[data-theme=auto] .wil { --wil-th: var(--text-muted); --wil-pr-bg: var(--surface); --wil-pr-fg: var(--text); --wil-pr-bd: var(--grey-500); --wil-prh-bg: var(--tone-amber-tint); --wil-prh-fg: var(--tone-amber-text); --wil-prh-bd: color-mix(in srgb, var(--tone-amber-text) 30%, transparent); --wil-pru-bg: var(--tone-red-tint); --wil-pru-fg: var(--tone-red-text); --wil-pru-bd: color-mix(in srgb, var(--tone-red-text) 30%, transparent); --wil-ta-bg: var(--brand-blue-tint); --wil-ta-fg: var(--status-blue-text); --wil-tr-bg: var(--tone-red-tint); --wil-tr-fg: var(--tone-red-text); --wil-ti-bg: var(--tone-urgent); --wil-ti-fg: var(--tone-on-urgent); --wil-td-bg: var(--tone-green-tint); --wil-td-fg: var(--tone-green-text); --wil-th-bg: var(--tone-grey-tint); --wil-th-fg: var(--tone-grey-text); --wil-add-bd: var(--grey-500); --wil-add-fg: var(--status-blue-text); } }",
    ".wil-table th { font-size: calc(var(--size-caption) - 1.5px); color: var(--wil-th); }",
    ".wil-table td.wil-c-id, .wil-c-id { font-family: ui-monospace, Menlo, Consolas, monospace; font-size: var(--size-caption); font-weight: var(--weight-medium); font-variant-numeric: tabular-nums; color: var(--status-blue); }",
    ".wil-pr { border: 1px solid var(--wil-pr-bd); border-radius: 6px; background: var(--wil-pr-bg); color: var(--wil-pr-fg); font-size: calc(var(--size-caption) - 1px); font-weight: var(--weight-medium); }",
    ".wil-pr.h { border-color: var(--wil-prh-bd); background: var(--wil-prh-bg); color: var(--wil-prh-fg); }",
    ".wil-pr.u { border-color: var(--wil-pru-bd); background: var(--wil-pru-bg); color: var(--wil-pru-fg); }",
    ".wil-off .wil-pr { border-color: var(--grey-200); }",
    ".wil-table tr.wil-k-action:not(.wil-off) .ico, .wil-lines li.wil-k-action:not(.wil-off) .ico { background: var(--wil-ta-bg); color: var(--wil-ta-fg); }",
    ".wil-table tr.wil-k-risk:not(.wil-off) .ico, .wil-lines li.wil-k-risk:not(.wil-off) .ico { background: var(--wil-tr-bg); color: var(--wil-tr-fg); }",
    ".wil-table tr.wil-k-issue:not(.wil-off) .ico, .wil-lines li.wil-k-issue:not(.wil-off) .ico { background: var(--wil-ti-bg); color: var(--wil-ti-fg); }",
    ".wil-table tr.wil-k-decision:not(.wil-off) .ico, .wil-lines li.wil-k-decision:not(.wil-off) .ico { background: var(--wil-td-bg); color: var(--wil-td-fg); }",
    ".wil-table .wil-c-eye .ib { color: var(--text); }",
    ".wil-off .wil-c-eye .ib { color: var(--grey-500); }",
    "@media (max-width: 1100px) { .wil-table .wil-c-owner { width: 150px; } }",
    "@media (max-width: 1000px) {",
    "  .wil-table td.wil-c-due { white-space: nowrap; overflow-wrap: normal; }",
    "  .wil-table .wil-c-due { width: 116px; }",
    "}",
    ".wil:has(> .wil-views) { display: grid; grid-template-columns: minmax(0, 1fr); }",
    ".wil:has(> .wil-views) > * { order: 3; }",
    ".wil:has(> .wil-views) > .wil-say, .wil:has(> .wil-views) > .wil-form { order: 0; }",
    ".wil:has(> .wil-views) > .wil-views { order: 1; margin-top: var(--space-3); }",
    ".wil:has(> .wil-views) > .wil-line { order: 2; margin: 0 0 var(--space-3); }",
    ".wil-form { display: block; margin: 0; padding: 0; border: 0; background: none; }",
    ".wil-cw { position: absolute; top: var(--sec-pad-t); right: var(--sec-px); z-index: 6; display: flex; justify-content: flex-end; }",
    ".wil-gear { border: 0; background: transparent; color: var(--text-muted); }",
    ".wil-gear:hover, .wil-gear[aria-expanded=true] { background: var(--grey-100); color: var(--text); }",
    ".wil-cfg { width: min(calc(var(--space-4) * 19), calc(100vw - var(--space-6))); }",
    ".wil-cfg h4 { font-family: var(--font-head); font-weight: var(--weight-semibold); color: var(--heading); }",
    ".wil-cfg .wil-sel > span, .wil-cfg .wil-f legend { font-weight: var(--weight-medium); color: var(--text-muted); }",
    ".wil-cfg .wil-opts input[type=\"checkbox\"] { width: var(--space-4); height: var(--space-4); margin: 0; accent-color: var(--brand-blue); }",
    ".wil-cfg .wil-sel select:focus-visible, .wil-cfg .wil-sel input:focus-visible { outline: 2px solid var(--brand-blue); outline-offset: 1px; }",
    ".wil-cacts button { background-color: var(--pill-color); background-image: var(--pill-bg); color: var(--pill-fg); font-weight: var(--weight-semibold); }",
    ".wil-cfg .wil-opts label { order: 8; }",
    ".wil-cfg .wil-opts label:has(> input[value=\"status\"]) { order: 1; }",
    ".wil-cfg .wil-opts label:has(> input[value=\"owner\"]) { order: 2; }",
    ".wil-cfg .wil-opts label:has(> input[value=\"due\"]) { order: 3; }",
    ".wil-cfg .wil-opts label:has(> input[value=\"priority\"]) { order: 4; }",
    ".wil-cfg .wil-opts label:has(> input[value=\"workstream\"]) { order: 5; }",
    ".wil-cfg .wil-opts label:has(> input[value=\"milestone\"]) { order: 6; }",
    ".wil-cfg .wil-opts label:has(> input[value=\"id\"]) { order: 7; }",
    ".wil-add .newb { box-sizing: border-box; width: 34px; height: 34px; min-width: 0; padding: 0; justify-content: center; border: 1px dashed var(--wil-add-bd); border-radius: 6px; background: none; color: var(--wil-add-fg); }",
    ".wil-add .newb:hover, .wil-add .newb:focus-visible, .wil-add .newb[aria-expanded=\"true\"] { background: var(--grey-50); border-color: var(--wil-add-bd); color: var(--wil-add-fg); }",
    ".wil-add .newb:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; }",
    ".wil-add .newb .w, .wil-add .newb:hover .w, .wil-add .newb:focus-visible .w, .wil-add .newb[aria-expanded=\"true\"] .w, .wil-add .newb .nch { display: none; }",
    ".wil-add .ddmenu { min-width: calc(var(--space-8) * 2); padding: var(--space-1); border: 1px solid var(--grey-200); border-radius: var(--radius-lg); background: var(--surface); box-shadow: 0 10px 30px rgba(6, 47, 58, .2); }",
    ".wil-add .ddmenu [role=\"menuitem\"] { display: flex; align-items: center; gap: var(--space-2); min-height: calc(var(--space-6) + var(--space-3)); padding: 0 var(--space-2); border-radius: var(--radius); font-weight: var(--weight-medium); color: var(--text); }",
    ".wil-add .ddmenu [role=\"menuitem\"]:hover, .wil-add .ddmenu [role=\"menuitem\"]:focus-visible { background: var(--grey-50); color: var(--text); }",
    ".wil-add .ddmenu [role=\"menuitem\"]:focus-visible { outline: 0; }",
    ".wil-views .vtab { font-weight: var(--weight-medium); }",
    ".wil-views .vtab em { font-weight: var(--weight-regular); color: var(--text-muted); }",
    ".wil-views .vnew { color: var(--status-blue-text); font-weight: var(--weight-medium); }",
    ".wil-views .vnew:hover { color: var(--status-blue-text); }",
    ".wil-views .vtabs { flex-wrap: wrap; overflow: visible; }",
    ".wil-views .vt { gap: 0; }",
    ".wil-views .vt:has(> .wil-vopts) .vtab { padding-right: calc(var(--space-5) + var(--space-1)); }",
    ".wil-views .vt > .wil-vopts { margin-left: calc(-1 * (var(--space-5) + var(--space-1))); }",
    "#report[data-mode=\"view\"] .wil-scroll { scrollbar-width: none; }",
    "#report[data-mode=\"view\"] .wil-scroll::-webkit-scrollbar { display: none; }",
    ".wil-half { width: 16px; height: 16px; }",
    ".wil-table th.wil-drop { box-shadow: inset 3px 0 var(--brand-blue); }",
    ".wil-table th.wil-dragging { opacity: 0.4; }",
    ".wil-table th[draggable=\"true\"] { cursor: grab; }",
    ".wil-table .wil-c-type, .wil-cfg .wil-opts label:has(> input[value=\"type\"]) { display: none; }",
    ".wil-table .wil-own .nm { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }",
    ".wil-lines li { grid-template-columns: calc(var(--space-5) + var(--space-1)) minmax(0, 1fr) auto; }",
    ".wil-lines .wil-t { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }",
    ".wil-lines .wil-hpr { grid-column: 3; grid-row: 1; justify-self: end; align-self: center; }",
    ".wil-lines .wil-m { grid-column: 2 / span 2; display: flex; flex-wrap: wrap; gap: 2px var(--space-3); }",
    ".wil-lines .wil-m > span { white-space: nowrap; }",
    ".wil-cap { font-size: calc(var(--size-caption) - 1.5px); color: rgb(85, 103, 122); }",
    ":root[data-theme=dark] .wil-cap { color: var(--text-muted); }",
    "@media (prefers-color-scheme: dark) { :root[data-theme=auto] .wil-cap { color: var(--text-muted); } }",
    ".wil-table .ico, .wil-lines .ico { width: calc(var(--space-5) + var(--space-1)); height: calc(var(--space-5) + var(--space-1)); border-radius: 7px; }",
    ".wil-table tr.wil-off .ico, .wil-lines li.wil-off .ico { background: var(--wil-th-bg); color: var(--wil-th-fg); }",
    ".wil-table .wil-c-owner { width: 170px; }",
    ".wil-table .wil-c-due { width: 104px; }",
    ".wil-table .wil-c-priority { width: 84px; }",
    ".wil-table .wil-c-id { width: 84px; }",
    ".wil-all-b { color: var(--status-blue); font-weight: var(--weight-medium); min-height: var(--space-6); padding: 6px 0; }",
]

# The Cards page as main serves it: the md5 of every <style> block of page_html(branding=NO_BRAND, theme=None), and the md5 of
# the rendered Work items section (Edit; View; the Add menu opened) with its section id folded to REF and the day count of a due date ("In 1149 days", it changes every day) folded to "In N days", at 1400 and 900 (CARDS_DOM below).
# This row must not change any of them. If one differs after a merge of main, re-measure on origin/main: a difference with no CSS or Work items
# change in main is a Cards change made by this row.
CARDS_STYLE_MD5 = {"blocks": ["7195b3107c3b5022f3b40ad1dfbbe484"]}
_DOM = {"view": "64d2815a7699b1d8efb201c8607c24c8", "edit": "5b1ebb0f52c9019e2270e46bf675aaab", "menu": "d8ab40593e7d9a00a06ab21d88883d75"}
CARDS_DOM_MD5 = {1400: _DOM, 900: _DOM}      # the markup does not depend on the width (the width is CSS); both are measured and kept


def rule(css, selector):
    """The body of the first rule whose selector list is exactly `selector`."""
    m = re.search(r"(?:^|\n)" + re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert m, selector
    return m.group(1)


def norm(s):
    return re.sub(r"\s+", " ", re.sub(r"/\*.*?\*/", "", s)).strip()


def style_md5s(html):
    return [hashlib.md5(b.encode("utf-8")).hexdigest() for b in re.findall(r"<style[^>]*>(.*?)</style>", html, re.S)]


def menu_walk(test, p, ref):
    """Open the Add menu in Edit; return (the data-kind of its items in markup order, the kinds the ArrowDown key lands on, in order)."""
    sec = f'[data-id="{ref}"]'
    p.edit()
    p.until(f"!!document.querySelector('{sec} .wil-add .newb')", "drew")
    p.js(f"document.querySelector('{sec} .wil-add .newb').click()")
    p.until(f"!!document.querySelector('{sec} .wil-add .ddmenu')", "menu")
    dom = json.loads(p.js("JSON.stringify([...document.querySelectorAll('" + sec + " .wil-add .ddmenu [role=menuitem]')].map(e => e.dataset.kind))"))
    walked = []
    for _ in range(6):
        kind = p.js("(document.activeElement.dataset || {}).kind || ''")
        if kind and kind not in walked:
            walked.append(kind)
        p.key("ArrowDown", code="ArrowDown", vk=40)
        kind = p.js("(document.activeElement.dataset || {}).kind || ''")
        if kind and kind not in walked:
            walked.append(kind)
    return dom, walked


ITEM_LABEL = "Item column. Drag its right edge or press Ctrl with an arrow key to resize"
HEAD_LABEL = "%s column. Drag to move it; Alt with an arrow key moves it; drag its right edge or press Ctrl with an arrow key to resize"      # the mock-up's words (work-items-mockup.html, the .hc heading)


class SourceRules(unittest.TestCase):
    def test_the_shared_files_carry_none_of_the_mockups_rules(self):
        for css in (SHELL_CSS, EDIT_CSS):
            for gone in ("wil-k-", ".wil-add .newb .w", "wil-cw { position: absolute", ".wil-views .vtab", "row 1195 (", "row 1195: bold mono"):
                self.assertNotIn(gone, css)

    def test_the_header_order_is_css_only_gear_then_tabs_then_filter_then_table(self):
        order = {sel: int(re.search(r"order: (\d+)", rule(RULES, sel)).group(1)) for sel in (".wil:has(> .wil-views) > .wil-views", ".wil:has(> .wil-views) > .wil-line", ".wil:has(> .wil-views) > *")}
        self.assertEqual(rule(RULES, ".wil:has(> .wil-views) > .wil-say, .wil:has(> .wil-views) > .wil-form").strip(), "order: 0;")
        self.assertLess(0, order[".wil:has(> .wil-views) > .wil-views"])
        self.assertLess(order[".wil:has(> .wil-views) > .wil-views"], order[".wil:has(> .wil-views) > .wil-line"])
        self.assertLess(order[".wil:has(> .wil-views) > .wil-line"], order[".wil:has(> .wil-views) > *"])
        gear, tabs, line, rows = (JSX.index(x) for x in ('<div class="wil-form">', "<Tabs add=", '<div class="wil-line"', "<Listing"))
        self.assertLess(line, tabs, "the markup is Cards' markup: the filter line stays before the tabs and the gear form after them")
        self.assertLess(tabs, gear)
        self.assertLess(gear, rows)

    def test_the_gear_is_in_the_title_row_and_the_form_bar_is_gone(self):
        cw = rule(RULES, ".wil-cw")
        self.assertIn("position: absolute", cw)
        self.assertIn("right: var(--sec-px)", cw)
        form = rule(RULES, ".wil-form")
        for gone in ("background: var(--grey-50)", "border: 1px solid", "padding: var(--space-3)"):
            self.assertNotIn(gone, form)
        self.assertIn("border: 0", rule(RULES, ".wil-gear"))

    def test_tabs_are_medium_with_grey_count_pills_and_a_violet_new_view(self):
        self.assertIn("font-weight: var(--weight-medium)", rule(RULES, ".wil-views .vtab"))
        self.assertIn("color: var(--text-muted)", rule(RULES, ".wil-views .vtab em"))
        new = rule(RULES, ".wil-views .vnew")
        self.assertIn("color: var(--status-blue-text)", new)
        self.assertIn("font-weight: var(--weight-medium)", new)
        self.assertIn("border-bottom-color: var(--brand-blue)", rule(SHELL_CSS, '.vtab[aria-pressed="true"]'))

    def test_the_plus_is_a_dashed_square_in_every_state_and_never_a_filled_pill(self):
        base = rule(RULES, ".wil-add .newb")
        self.assertIn("border: 1px dashed", base)
        self.assertIn("width: 34px; height: 34px", base)
        open_ = rule(RULES, '.wil-add .newb:hover, .wil-add .newb:focus-visible, .wil-add .newb[aria-expanded="true"]')
        self.assertIn("var(--grey-50)", open_)
        self.assertNotIn("brand-blue", open_)
        self.assertIn("display: none", rule(RULES, '.wil-add .newb .w, .wil-add .newb:hover .w, .wil-add .newb:focus-visible .w, .wil-add .newb[aria-expanded="true"] .w, .wil-add .newb .nch'))

    def test_the_add_menu_is_white_with_a_shadow_medium_labels_and_a_soft_grey_hover(self):
        box = rule(RULES, ".wil-add .ddmenu")
        self.assertIn("background: var(--surface)", box)
        self.assertIn("box-shadow: 0 10px 30px rgba(6, 47, 58, .2)", box)
        self.assertIn("font-weight: var(--weight-medium)", rule(RULES, '.wil-add .ddmenu [role="menuitem"]'))
        hov = rule(RULES, '.wil-add .ddmenu [role="menuitem"]:hover, .wil-add .ddmenu [role="menuitem"]:focus-visible')
        self.assertIn("background: var(--grey-50)", hov)
        self.assertIn("outline: 0", rule(RULES, '.wil-add .ddmenu [role="menuitem"]:focus-visible'))

    def test_configure_lists_the_columns_in_the_mockup_order_by_css_and_the_markup_keeps_the_saved_order(self):
        want = ["status", "owner", "due", "priority", "workstream", "milestone", "id"]
        for n, col in enumerate(want, 1):
            self.assertIn(f"order: {n}", rule(RULES, f'.wil-cfg .wil-opts label:has(> input[value="{col}"])'))
        self.assertIn("order: 8", rule(RULES, ".wil-cfg .wil-opts label"))
        self.assertIn("values={COLUMNS}", JSX)
        self.assertNotIn("SHOWN_COLUMNS", JSX)

    def test_configure_done_is_the_aqua_pill_and_the_checkboxes_are_16_wide_violet(self):
        done = rule(RULES, ".wil-cacts button")
        self.assertIn("background-image: var(--pill-bg)", done)
        self.assertIn("color: var(--pill-fg)", done)
        box = rule(RULES, '.wil-cfg .wil-opts input[type="checkbox"]')
        self.assertIn("accent-color: var(--brand-blue)", box)

    def test_the_id_is_bold_mono_violet_and_the_priority_pill_has_a_border(self):
        idr = rule(RULES, ".wil-table td.wil-c-id, .wil-c-id")
        self.assertIn("monospace", idr)
        self.assertIn("font-weight: var(--weight-medium)", idr)      # the mock-up: 600 13px mono (the medium token), colour var(--blue) = #5B47D8 = the status-blue token
        self.assertIn("color: var(--status-blue);", idr)
        self.assertIn("border: 1px solid var(--wil-pr-bd)", rule(RULES, ".wil-pr"))
        self.assertIn("border-color: var(--wil-prh-bd)", rule(RULES, ".wil-pr.h"))
        self.assertIn("border-color: var(--wil-pru-bd)", rule(RULES, ".wil-pr.u"))

    def test_the_medium_pill_is_white_with_a_dark_border_and_bold_dark_text(self):
        pr = rule(RULES, ".wil-pr")
        for want in ("background: var(--wil-pr-bg)", "color: var(--wil-pr-fg)", "font-weight: var(--weight-medium)", "border: 1px solid var(--wil-pr-bd)", "border-radius: 6px"):
            self.assertIn(want, pr)
        self.assertNotIn("grey-100", pr)
        self.assertIn("background: var(--wil-prh-bg)", rule(RULES, ".wil-pr.h"))
        self.assertIn("background: var(--wil-pru-bg)", rule(RULES, ".wil-pr.u"))
        self.assertIn("--wil-pr-bg: rgb(246, 248, 252)", RULES)      # the mock-up's pill ground; dark keeps the Theme's surface

    def test_the_letter_tile_is_coloured_by_the_kind_in_the_rows_and_in_the_add_menu_and_only_classic_marks_a_row_with_its_kind(self):
        def tile(kind):
            return rule(RULES, f".wil-table tr.wil-k-{kind}:not(.wil-off) .ico, .wil-lines li.wil-k-{kind}:not(.wil-off) .ico")
        for kind, k in (("action", "ta"), ("risk", "tr"), ("issue", "ti"), ("decision", "td")):
            self.assertIn(f"background: var(--wil-{k}-bg); color: var(--wil-{k}-fg)", tile(kind))
        self.assertNotIn('.wil-add .ddmenu [role="menuitem"][data-kind=', RULES)      # item 1273: the Add menu draws the + icon, not a letter chip
        self.assertIn('document.getElementById("theme")', ROWS_JSX)
        self.assertIn('kinds ? ` wil-k-${row.kind}` : ""', ROWS_JSX)

    def test_the_open_tabs_caret_sits_inside_the_tab_underline_right_after_the_tab_words(self):
        self.assertIn("gap: 0", rule(RULES, ".wil-views .vt"))
        self.assertIn("padding-right: calc(var(--space-5) + var(--space-1))", rule(RULES, ".wil-views .vt:has(> .wil-vopts) .vtab"))
        self.assertIn("margin-left: calc(-1 * (var(--space-5) + var(--space-1)))", rule(RULES, ".wil-views .vt > .wil-vopts"))

    def test_the_heading_row_is_caption_size_caps(self):
        self.assertIn("font-size: calc(var(--size-caption) - 1.5px)", rule(RULES, ".wil-table th"))      # the mock-up: 11.5px
        self.assertIn("color: var(--wil-th)", rule(RULES, ".wil-table th"))

    def test_at_1100_and_below_the_owner_keeps_its_width_and_at_1000_the_date_stays_on_one_line(self):
        self.assertIn("@media (max-width: 1100px) { .wil-table .wil-c-owner { width: 150px; } }", RULES)
        self.assertIn("width: 150px", rule(SHELL_CSS, ".wil-table .wil-c-owner"))
        m = re.search(r"@media \(max-width: 1000px\) \{(.*?)\n\}", RULES[RULES.index("@media (max-width: 1000px)"):], re.S)
        self.assertIn("td.wil-c-due { white-space: nowrap", m.group(1))
        self.assertIn(".wil-table .wil-c-due { width: 116px; }", m.group(1))

    def test_no_bare_px_font_size_and_no_looping_animation_in_what_this_row_added(self):
        for ln in RULES.splitlines():
            if "wil-" in ln:
                self.assertNotRegex(ln, r"font-size:\s*\d+px")
                self.assertNotIn("infinite", ln)

    def test_the_rules_hold_no_hash_number(self):
        # only this row's own lines: from a Row 1195 comment to the next comment of another row (other rows stack after it and may hold colours)
        mine, on = [], False
        for line in RULES.split("\n"):
            if line.startswith("/* Row "):
                on = line.startswith("/* Row 1195")
            if on:
                mine.append(line)
        self.assertTrue(mine)
        self.assertIsNone(re.search(r"#\d", "\n".join(mine)))


class EveryAddedRuleIsPinned(unittest.TestCase):
    """Row 1195: each rule line this row added must stay exactly as drawn (a colour token, a selector, a size, a breakpoint): a changed or dropped declaration fails here."""

    def test_every_added_rule_line_is_present_as_written(self):
        have = {norm(ln) for ln in RULES.splitlines()}
        have |= {norm(x) for x in re.findall(r"@media[^{]*\{[^{}]*\{[^}]*\}\s*\}", RULES)}
        for want in GOLDEN_LINES:
            self.assertIn(norm(want), have)


class CardsStyleBlocks(unittest.TestCase):
    """The Cards page (theme=None) is byte for byte what main serves: the Classic look is only in the theme layer."""

    def test_every_style_block_of_the_cards_page_has_the_md5_main_has(self):
        got = style_md5s(page.page_html(branding=page.NO_BRAND, theme=None))
        self.assertEqual(got, CARDS_STYLE_MD5["blocks"])

    def test_the_classic_page_adds_only_the_theme_block_and_has_the_mockups_rules(self):
        cards = page.page_html(branding=page.NO_BRAND, theme=None)
        classic = page.page_html(branding=page.NO_BRAND, theme=NAME)
        self.assertNotIn('id="theme"', cards)
        self.assertIn('id="theme"', classic)
        mine = style_md5s(classic)
        self.assertEqual([m for m in mine if m not in CARDS_STYLE_MD5["blocks"]].__len__(), 1, "one block more: the Theme")
        self.assertIn(".wil-add .ddmenu", theme.css(NAME))


class Look(T.PageBase):
    """Serves the test page with the Classic theme layered (or without it, for Cards) and the demo Work items."""
    classic = True
    add = T.InThePage.add
    show = T.InThePage.show
    rows = T.InThePage.rows

    def setUp(self):
        super().setUp()
        T.plant(self)
        self.s.close()
        css = theme.css(NAME)
        self.s = real_server(self.store.path, self.store.data_for,
                             page_html=lambda: page.layer_theme(testpage.html(), css) if self.classic else testpage.html(), seam=self.seam)
        self.addCleanup(self.s.close)


class ClassicFile(T.PublishedFile):
    """A Classic published file has no Show all items link, even when its section lists more rows than it draws (the Foot is the served page's too)."""

    def test_a_classic_file_never_shows_the_link_and_its_rows_keep_scrolling(self):
        # a file's section carries its rows (View then takes Most rows from them), so the link cannot show there today; the gate is pinned in the source too
        self.assertIn("classicTheme() && !fromFile.value && count > max", ROWS_JSX)
        self.store.con.execute("UPDATE app_settings SET theme = 'classic' WHERE id = 1")
        status, got = self.real_change({"project": "ABC", "kind": "report_sections", "op": changes.NEW, "values": {"type": "workitems", "title": "Due soon"}, "after": None})
        ref = got["ref"]
        body = {"mode": "all", "max": 3, "owner": ["Pat Demo", "Lee Demo"]}
        status, got = self.real_change({"project": "ABC", "kind": "report_sections", "op": changes.UPDATE, "id": ref, "changes": {"body": json.dumps(body)}})
        self.assertEqual(status, 200, got)
        out = tempfile.mkdtemp(prefix="clark-1195-file-")
        self.addCleanup(shutil.rmtree, out, ignore_errors=True)
        path = Path(publish.publish(self.store, "ABC", out, by_user=T.USER, now=T.TODAY, branding=T.EMPTY_BRANDING)["path"])
        text = path.read_text(encoding="utf-8")
        head = '<script type="application/json" id="clark-data">'
        start = text.index(head) + len(head)
        end = text.index("</script>", start)
        data = json.loads(text[start:end])
        sec = next(s for s in data["sections"] if s["id"] == ref)
        self.assertEqual(len(sec["items"]), 3, "the file carries three rows")
        sec["body"] = T.stored(dict(body, max=2))      # the filter now says Most rows 2 over the three rows the file carries
        raw = json.dumps(data).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
        path.write_text(text[:start] + raw + text[end:], encoding="utf-8")
        with T.chrome() as cdp:
            tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
            sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": 1400, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, sid)
            cdp.call("Page.navigate", {"url": path.as_uri()}, sid)
            p = Pg(self, cdp, sid)
            p.until("document.documentElement.dataset.ready === '1' && !!document.querySelector('h1')", "the file drew")
            p.until(f"document.querySelectorAll('[data-id=\"{ref}\"] .wil-table tbody tr').length === 3", "the list drew its rows")
            self.assertTrue(p.js("!!document.getElementById('theme')"), "the file is Classic")
            self.assertFalse(p.js(f"!!document.querySelector('[data-id=\"{ref}\"] [data-wil-all]')"), "a file has no Show all items link")


    def test_a_classic_file_has_no_draggable_headings_no_tab_stops_and_no_width_handles(self):      # row 1195 ruling: the published page is out
        self.store.con.execute("UPDATE app_settings SET theme = 'classic' WHERE id = 1")
        status, got = self.real_change({"project": "ABC", "kind": "report_sections", "op": changes.NEW, "values": {"type": "workitems", "title": "Due soon"}, "after": None})
        ref = got["ref"]
        body = {"mode": "all", "columns": ["owner", "due", "id"], "owner": ["Pat Demo", "Lee Demo"]}
        status, got = self.real_change({"project": "ABC", "kind": "report_sections", "op": changes.UPDATE, "id": ref, "changes": {"body": json.dumps(body)}})
        self.assertEqual(status, 200, got)
        out = tempfile.mkdtemp(prefix="clark-1195-file-")
        self.addCleanup(shutil.rmtree, out, ignore_errors=True)
        path = Path(publish.publish(self.store, "ABC", out, by_user=T.USER, now=T.TODAY, branding=T.EMPTY_BRANDING)["path"])
        text = path.read_text(encoding="utf-8")
        self.assertNotIn("cgrip", text)
        self.assertNotIn("Drag to move it", text)
        with T.chrome() as cdp:
            tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
            sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": 1400, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, sid)
            cdp.call("Page.navigate", {"url": path.as_uri()}, sid)
            p = Pg(self, cdp, sid)
            p.until("document.documentElement.dataset.ready === '1' && !!document.querySelector('h1')", "the file drew")
            p.until(f"document.querySelectorAll('[data-id=\"{ref}\"] .wil-table thead th').length > 3", "the list drew its headings")
            self.assertTrue(p.js("!!document.getElementById('theme')"), "the file is Classic")
            sec = f'[data-id="{ref}"] .wil-table thead'
            self.assertEqual(p.js(f"document.querySelectorAll('{sec} [draggable=true], {sec} [tabindex], {sec} [data-cw-head], {sec} .cgrip, {sec} [aria-label*=\"Drag\"]').length"), 0)


class Classic(Look):
    LIST = {"mode": "all", "columns": ["id", "owner", "due", "priority"], "owner": ["Pat Demo", "Lee Demo"]}

    def test_edit_draws_tabs_then_filter_then_table_with_the_gear_in_the_title_row_and_the_plus_square(self):
        ref = self.add(self.LIST)
        for width in (1400, 900):
            with T.chrome() as cdp:
                p = self.show(cdp, width)
                sec = f'[data-id="{ref}"]'
                p.edit()
                p.until(f"!!document.querySelector('{sec} [data-wil-gear]')", "drew")
                got = json.loads(p.js("JSON.stringify((() => { const q = (s) => document.querySelector(`" + sec + " ${s}`).getBoundingClientRect();"
                    "const sec = document.querySelector('" + sec + "').getBoundingClientRect(), h = document.querySelector('" + sec + " .sec-head').getBoundingClientRect(), g = q('[data-wil-gear]'), t = q('.fviews'), l = q('[data-wil-line]'), r = q('.wil-table'), a = q('.wil-add .newb');"
                    "return {gearTop: g.top - h.top, gearRight: sec.right - g.right, gearBelowHead: g.bottom <= t.top + 1, tabs: t.top, line: l.top, table: r.top, plus: [a.width, a.height]}; })())"))
                self.assertLess(got["tabs"], got["line"], width)
                self.assertLess(got["line"], got["table"], width)
                self.assertTrue(got["gearBelowHead"], got)
                self.assertLess(abs(got["gearTop"]), 20, got)
                self.assertGreater(got["gearRight"], 10, got)
                self.assertEqual(got["plus"], [34, 34], got)
                self.assertFalse(p.js(f"!!document.querySelector('{sec} .wil-form') && getComputedStyle(document.querySelector('{sec} .wil-form')).backgroundColor !== 'rgba(0, 0, 0, 0)'"), "no pale bar")
                p.js(f"document.querySelector('{sec} .wil-add .newb').click()")
                p.until(f"!!document.querySelector('{sec} .wil-add .ddmenu')", "menu")
                kinds = p.js("[...document.querySelectorAll('" + sec + " .wil-add .ddmenu [role=menuitem]')].map(e => e.dataset.kind[0].toUpperCase()).join('')")
                self.assertEqual(kinds, "RAID", "RAID order in the markup, so in the arrow keys too")
                icons = p.js("[...document.querySelectorAll('" + sec + " .wil-add .ddmenu [role=menuitem]')].map(e => getComputedStyle(e, '::before').content + ':' + (e.querySelector('.mi') ? Math.round(e.querySelector('.mi').getBoundingClientRect().width) : 0)).join(' ')")
                self.assertNotIn('"', icons, "item 1273: no letter chip is drawn in the Add menu")
                self.assertNotIn(":0", icons, icons)
                self.assertEqual(p.js(f"Math.round(document.querySelector('{sec} .wil-add .newb').getBoundingClientRect().width)"), 34, "open: still the square")

    def test_configure_lists_the_columns_in_the_mockup_order(self):
        ref = self.add({"mode": "all", "columns": ["id", "owner"], "owner": ["Pat Demo"]})
        with T.chrome() as cdp:
            p = self.show(cdp, 1400)
            sec = f'[data-id="{ref}"]'
            p.edit()
            p.until(f"!!document.querySelector('{sec} [data-wil-gear]')", "drew")
            p.js(f"document.querySelector('{sec} [data-wil-gear]').click()")
            p.until(f"!!document.querySelector('{sec} .wil-cfg .wil-opts label')", "open")
            seen = json.loads(p.js("JSON.stringify([...document.querySelectorAll('" + sec + " .wil-cfg [data-field=columns] label')].map(e => [e.querySelector('input').value, Number(getComputedStyle(e).order)]).sort((a, b) => a[1] - b[1]).map(x => x[0]))"))
            self.assertEqual(seen, ["status", "owner", "due", "priority", "workstream", "milestone", "id", "type"])

    def test_the_table_cells_the_id_priority_owner_and_due_at_900(self):
        ref = self.add(self.LIST)
        with T.chrome() as cdp:
            p = self.show(cdp, 900)
            sec = f'[data-id="{ref}"]'
            p.edit()
            p.until(f"!!document.querySelector('{sec} .wil-table td.wil-c-id')", "drew")
            idc = json.loads(p.js(f"JSON.stringify((() => {{ const s = getComputedStyle(document.querySelector('{sec} .wil-table td.wil-c-id')); return [s.fontFamily, s.fontWeight, s.color]; }})())"))
            self.assertIn("monospace", idc[0])
            self.assertEqual(idc[1], "600")
            vio = p.js("(() => { const e = document.createElement('i'); e.style.color = getComputedStyle(document.documentElement).getPropertyValue('--status-blue'); document.body.append(e); const c = getComputedStyle(e).color; e.remove(); return c; })()")
            self.assertEqual(idc[2], vio)
            self.assertNotEqual(p.js(f"getComputedStyle(document.querySelector('{sec} .wil-pr')).borderTopWidth"), "0px")
            own = json.loads(p.js(f"JSON.stringify([...document.querySelectorAll('{sec} .wil-table td.wil-c-owner .nm')].map(e => [e.scrollWidth, e.clientWidth]))"))
            for sw, cw in own:
                self.assertLessEqual(sw, cw, "an owner name is not cut")
            due = json.loads(p.js(f"JSON.stringify([...document.querySelectorAll('{sec} .wil-table td.wil-c-due .num')].map(e => e.getClientRects().length))"))
            for n in due:
                self.assertEqual(n, 1, "a date is on one line")

    def test_the_add_menu_is_risk_action_issue_decision_in_the_markup_and_the_arrow_keys_walk_it(self):
        ref = self.add(self.LIST)
        with T.chrome() as cdp:
            p = self.show(cdp, 1400)
            self.assertEqual(menu_walk(self, p, ref), (["risk", "action", "issue", "decision"], ["risk", "action", "issue", "decision"]))

    def test_show_all_items_is_a_link_under_the_table_only_when_there_are_more_rows_than_most_rows(self):
        few = self.add({"mode": "all", "max": 10, "columns": ["id", "owner"], "owner": ["Pat Demo", "Lee Demo"]})
        many = self.add({"mode": "all", "max": 2, "columns": ["id", "owner"], "owner": ["Pat Demo", "Lee Demo"]})
        with T.chrome() as cdp:
            p = self.show(cdp, 1400)
            p.until(f"!!document.querySelector('[data-id=\"{many}\"] .wil-scroll')", "View drew")
            self.assertFalse(p.js(f"!!document.querySelector('[data-id=\"{few}\"] .wil-all-b')"), "3 rows, Most rows 10: no link")
            sec = f'[data-id="{many}"]'
            word = lambda: p.js(f"document.querySelector('{sec} .wil-all-b').textContent")
            box = lambda: p.js(f"document.querySelector('{sec} .wil-scroll').style.maxHeight")
            self.assertEqual(word(), "Show all items")
            self.assertTrue(box(), "closed: the box is as tall as the first Most rows")
            self.assertEqual(p.js(f"document.querySelector('{sec} .wil-scroll').getAttribute('role')"), "region")
            self.assertTrue(p.js(f"document.querySelector('{sec} .wil-all-b').getBoundingClientRect().top >= document.querySelector('{sec} .wil-scroll').getBoundingClientRect().bottom - 1"), "under the table")
            p.js(f"document.querySelector('{sec} .wil-all-b').click()")
            p.until(f"document.querySelector('{sec} .wil-all-b').textContent === 'Show only 2'", "open reads Show only N")
            self.assertEqual(box(), "", "open: every row is in view")
            rows = json.loads(p.js(f"JSON.stringify((() => {{ const b = document.querySelector('{sec} .wil-scroll'), r0 = b.getBoundingClientRect(); return [...b.querySelectorAll('.wil-table tbody tr')].map(r => [r.offsetHeight, r.getBoundingClientRect().bottom <= r0.bottom + 1, b.scrollHeight <= b.clientHeight + 1]); }})())"))
            self.assertEqual(len(rows), 3)
            for h, inside, whole in rows:
                self.assertGreater(h, 0, "every row is drawn")
                self.assertTrue(inside and whole, "every row is inside the open box, nothing is left to scroll")
            self.assertEqual(p.js(f"[document.querySelector('{sec} .wil-scroll').getAttribute('role'), document.querySelector('{sec} .wil-scroll').getAttribute('aria-label'), document.querySelector('{sec} .wil-scroll').tabIndex]"), [None, None, -1], "open: it no longer scrolls, so it is not a region")
            p.js(f"document.querySelector('{sec} .wil-all-b').click()")
            p.until(f"document.querySelector('{sec} .wil-all-b').textContent === 'Show all items'", "back")
            self.assertTrue(box())
            p.edit()
            p.until(f"!!document.querySelector('{sec} [data-wil-gear]') && !!document.querySelector('{sec} .wil-all-b')", "Edit has the link too")

    def test_most_rows_50_with_51_items_draws_50_rows_then_show_all_gives_51_and_show_only_50_gives_50_at_1400_and_900(self):      # row 1359
        for k in range(51):
            self.demo.action(description=f"Kim step {k}", owner="Kim Demo", due_date="2030-02-01")
        ref = self.add({"mode": "all", "max": 50, "columns": ["id", "owner"], "owner": ["Kim Demo"]})
        for width in (1400, 900):
            with T.chrome() as cdp:
                p = self.show(cdp, width)
                sec = f'[data-id="{ref}"]'
                p.until(f"!!document.querySelector('{sec} .wil-all-b')", f"{width}: the link is drawn")
                n = lambda: p.js(f"(() => {{ const b = document.querySelector('{sec} .wil-scroll'), r0 = b.getBoundingClientRect(); return [...b.querySelectorAll('.wil-table tbody tr')].filter(r => r.getBoundingClientRect().top < r0.bottom - 2).length; }})()")      # rows that start inside the box
                word = lambda: p.js(f"document.querySelector('{sec} .wil-all-b').textContent")
                self.assertEqual((n(), word()), (50, "Show all items"), width)
                p.js(f"document.querySelector('{sec} .wil-all-b').click()")
                p.until(f"document.querySelector('{sec} .wil-all-b').textContent === 'Show only 50'", f"{width}: open")
                self.assertEqual(n(), 51, width)
                p.js(f"document.querySelector('{sec} .wil-all-b').click()")
                p.until(f"document.querySelector('{sec} .wil-all-b').textContent === 'Show all items'", f"{width}: closed")
                self.assertEqual(n(), 50, width)

    def test_view_draws_only_the_rows_no_tabs_filter_add_or_gear_and_edit_draws_all_four(self):      # row 1195: the mock-up's .viewmode hides .fviews, .fline-wrap, .addb and .cw
        ref = self.add({"mode": "all", "max": 2, "columns": ["id", "owner"], "owner": ["Pat Demo", "Lee Demo"]})
        probe = lambda sec: f"(() => {{ const s = document.querySelector('{sec}'); const v = (q) => [...s.querySelectorAll(q)].filter((e) => e.offsetParent).length; return [v('.wil-views'), v('[data-wil-line]'), v('[data-wil-add], .wil-add'), v('[data-wil-gear]')]; }})()"
        with T.chrome() as cdp:
            p = self.show(cdp, 1400)
            sec = f'[data-id="{ref}"]'
            p.until(f"!!document.querySelector('{sec} .wil-scroll')", "View drew")
            self.assertEqual(p.js(probe(sec)), [0, 0, 0, 0], "View: no tabs, filter, + or gear")
            p.edit()
            p.until(f"!!document.querySelector('{sec} [data-wil-gear]')", "Edit drew")
            got = p.js(probe(sec))
            self.assertTrue(got[0] and got[1] and got[2] and got[3], f"Edit has tabs, filter, + and gear: {got}")

    def test_foot_words_in_view_and_edit_at_1400_and_900_say_showing_all_of_n_when_nothing_is_cut_and_after_show_all_and_scroll_words_only_while_cut(self):      # row 1195: ruling NEW-WORDS 04:2x, WO-M8328
        for owner, n in (("Zed Demo", 25), ("Yan Demo", 8), ("Xi Demo", 1)):
            for k in range(n):
                self.demo.action(description=f"Foot step {owner} {k}", owner=owner, due_date="2030-02-01")
        lists = {n: self.add({"mode": "all", "max": 10, "columns": ["id", "owner"], "owner": [o]}) for o, n in (("Zed Demo", 25), ("Yan Demo", 8), ("Xi Demo", 1))}
        for width in (1400, 900):
            with self.subTest(width=width), T.chrome() as cdp:
                p = self.show(cdp, width)
                for ref in lists.values():
                    p.until(f"!!document.querySelector('[data-id=\"{ref}\"] [data-wil-scroll], [data-id=\"{ref}\"] .wil-scroll')", "View drew")
                foot = lambda n: p.js(f"document.querySelector('[data-id=\"{lists[n]}\"] [data-wil-count]').textContent")
                btn = lambda n: f"document.querySelector('[data-id=\"{lists[n]}\"] .wil-all-b')"
                for mode in ("View", "Edit"):
                    if mode == "Edit":
                        p.edit()
                        p.until(f"!!document.querySelector('[data-id=\"{lists[25]}\"] [data-wil-gear]')", "Edit drew")
                    p.until(f"!!document.querySelector('[data-id=\"{lists[25]}\"] [data-wil-count]')", f"{mode} has the foot words")
                    self.assertEqual(foot(8), "Showing all of 8", f"{mode}: fits")
                    self.assertEqual(foot(1), "Showing all of 1", f"{mode}: one item fits")
                    self.assertEqual(foot(25), "Showing 10 of 25, scroll for the rest", f"{mode}: cut")
                    p.js(f"{btn(25)}.click()")
                    p.until(f"document.querySelector('[data-id=\"{lists[25]}\"] [data-wil-count]').textContent === 'Showing all of 25'", f"{mode}: Show all items")
                    self.assertEqual(foot(8), "Showing all of 8")
                    p.js(f"{btn(25)}.click()")
                    p.until(f"document.querySelector('[data-id=\"{lists[25]}\"] [data-wil-count]').textContent === 'Showing 10 of 25, scroll for the rest'", f"{mode}: closed again")

    def test_the_views_list_scroll_bar_is_hidden_in_view_and_in_edit_row_1308(self):
        ref = self.add({"mode": "all", "max": 2, "columns": ["id", "owner"], "owner": ["Pat Demo", "Lee Demo"]})
        with T.chrome() as cdp:
            p = self.show(cdp, 1400)
            sec = f'[data-id="{ref}"]'
            p.until(f"!!document.querySelector('{sec} .wil-scroll')", "View drew")
            probe = f"(() => {{ const e = document.querySelector('{sec} .wil-scroll'); return [getComputedStyle(e).scrollbarWidth, e.scrollHeight > e.clientHeight, e.offsetWidth - e.clientWidth]; }})()"
            width, scrolls, bar = p.js(probe)
            self.assertTrue(scrolls, "the rows still scroll")
            self.assertEqual((width, bar), ("none", 0), "View: no scroll bar")
            p.edit()
            p.until(f"!!document.querySelector('{sec} .wil-scroll') && document.querySelector('#report').dataset.mode === 'edit'", "Edit drew")
            self.assertEqual(p.js(probe)[0], "none", "Edit: no scroll bar either (Row 1308)")

    def test_the_status_half_circle_is_16_px(self):      # the mock-up's .sti
        ref = self.add({"mode": "all", "columns": ["status", "id"], "owner": ["Pat Demo", "Lee Demo"]})
        with T.chrome() as cdp:
            p = self.show(cdp, 1400)
            p.until(f"!!document.querySelector('[data-id=\"{ref}\"] .wil-table .wil-half')", "View drew")
            self.assertEqual(p.js(f"(() => {{ const r = document.querySelector('[data-id=\"{ref}\"] .wil-table .wil-half').getBoundingClientRect(); return [r.width, r.height]; }})()"), [16, 16])

    def _heads(self, p, ref):
        return p.js(f"[...document.querySelectorAll('[data-id=\"{ref}\"] .wil-table thead th[data-cw-head]')].map(h => h.dataset.cwHead)")

    def test_a_heading_dragged_onto_another_moves_the_column_and_the_order_is_kept(self):      # README: drag a heading to re-order
        ref = self.add({"mode": "all", "columns": ["owner", "due", "priority", "id"], "owner": ["Pat Demo", "Lee Demo"]})
        with T.chrome() as cdp:
            p = self.show(cdp, 1400)
            p.edit()
            p.until(f"!!document.querySelector('[data-id=\"{ref}\"] .wil-table th[data-cw-head=due]')", "Edit drew")
            self.assertEqual(self._heads(p, ref), ["title", "owner", "due", "priority", "id"])
            h = lambda c: f"document.querySelector('[data-id=\"{ref}\"] .wil-table th[data-cw-head={c}]')"
            self.assertEqual(p.js(f"{h('id')}.draggable"), True)
            ev = lambda t, c: p.js(f"{h(c)}.dispatchEvent(new DragEvent('{t}', {{bubbles: true, cancelable: true, dataTransfer: new DataTransfer()}}))")
            ev("dragstart", "id")
            ev("dragover", "owner")
            p.until(f"{h('owner')}.classList.contains('wil-drop')", "the drop mark shows on the target heading")
            ev("drop", "owner")
            ev("dragend", "id")
            p.until(f"{h('owner')}.previousElementSibling.dataset.cwHead === 'id'", "the ID column moved before Owner")
            self.assertEqual(self._heads(p, ref), ["title", "id", "owner", "due", "priority"])
            body = p.js(f"[...document.querySelectorAll('[data-id=\"{ref}\"] .wil-table tbody tr:first-child td')].map(c => c.className.replace('wil-c-', ''))")
            self.assertEqual([c for c in body if c in ("id", "owner", "due", "priority")], ["id", "owner", "due", "priority"], "the cells follow the headings")
            reload_to_new_page(p.js, "!!document.querySelector('#report')", "the page reloaded")
            p.edit()
            p.until(f"!!document.querySelector('[data-id=\"{ref}\"] .wil-table th[data-cw-head=due]')", "Edit drew again")
            self.assertEqual(self._heads(p, ref), ["title", "id", "owner", "due", "priority"], "kept on this computer")

    def test_alt_with_an_arrow_moves_a_heading_and_ctrl_with_an_arrow_resizes_it(self):      # README: Ctrl and an arrow to resize; Alt and an arrow moves it
        ref = self.add({"mode": "all", "columns": ["owner", "due", "id"], "owner": ["Pat Demo", "Lee Demo"]})
        with T.chrome() as cdp:
            p = self.show(cdp, 1400)
            p.edit()
            h = lambda c: f"document.querySelector('[data-id=\"{ref}\"] .wil-table th[data-cw-head={c}]')"
            key = lambda c, k, **m: p.js(f"{h(c)}.dispatchEvent(new KeyboardEvent('keydown', {{key: '{k}', bubbles: true, cancelable: true, {', '.join(f'{a}: true' for a in m)}}}))")
            p.until(f"!!{h('due')}", "Edit drew")
            key("due", "ArrowRight", altKey=True)
            self.assertTrue(wait(lambda: self._heads(p, ref) == ["title", "owner", "id", "due"]), "Alt+Right moved Due one place right")
            self.assertEqual(p.js(f"{h('due')}.style.width"), "", "and did not resize it")
            self.assertEqual(p.js("document.activeElement && document.activeElement.dataset.cwHead"), "due", "the heading keeps the focus")
            key("due", "ArrowLeft", altKey=True)
            self.assertTrue(wait(lambda: self._heads(p, ref) == ["title", "owner", "due", "id"]), "Alt+Left moved it back")
            key("owner", "ArrowRight", ctrlKey=True)
            p.until(f"{h('owner')}.style.width !== ''", "Ctrl+Right sets the Owner width")
            self.assertEqual(self._heads(p, ref), ["title", "owner", "due", "id"], "and did not move it")
            self.assertIsNone(p.js(f"{h('owner')}.getAttribute('aria-description')"), "the old sentence is gone")
            self.assertEqual(p.js(f"{h('owner')}.tabIndex"), 0, "the heading is a tab stop")
            self.assertEqual(p.js(f"{h('owner')}.getAttribute('aria-label')"), HEAD_LABEL % "Owner")
            self.assertEqual(p.js(f"{h('title')}.getAttribute('aria-label')"), "Item column. Drag its right edge or press Ctrl with an arrow key to resize", "the Item heading does not move")

    def test_the_two_heading_labels_are_the_exact_aria_label_in_view_and_edit_at_1400_and_900_and_the_edge_handle_has_none(self):      # row 1195: Approved: WO-M8361, logged NEW-WORDS
        ref = self.add({"mode": "all", "columns": ["owner", "due", "priority", "id"], "owner": ["Pat Demo", "Lee Demo"]})
        for width in (1400, 900):
            with self.subTest(width=width), T.chrome() as cdp:
                p = self.show(cdp, width)
                for mode in ("View", "Edit"):
                    if mode == "Edit":
                        p.edit()
                    p.until(f"!!document.querySelector('[data-id=\"{ref}\"] .wil-table th[data-cw-head=due]')", f"{mode} drew")
                    got = p.js(f"Object.fromEntries([...document.querySelectorAll('[data-id=\"{ref}\"] .wil-table thead th[data-cw-head]')].map(h => [h.dataset.cwHead, h.getAttribute('aria-label')]))")
                    self.assertEqual(got, {"title": ITEM_LABEL, "owner": HEAD_LABEL % "Owner", "due": HEAD_LABEL % "Due", "priority": HEAD_LABEL % "Priority", "id": HEAD_LABEL % "ID"}, f"{mode} at {width}")
                    self.assertEqual(p.js(f"[...document.querySelectorAll('[data-id=\"{ref}\"] .cgrip')].map(g => [g.getAttribute('aria-hidden'), g.getAttribute('aria-label')])"), [["true", None]] * 5, f"{mode}: the edge handles stay aria-hidden, no label")

    def test_an_empty_match_says_the_mockups_words_in_view_and_the_long_sentence_in_edit_at_1400_and_900(self):      # row 1195: WO-M8425, the words are the mock-up's
        ref = self.add({"owner": ["Nobody Demo"]})
        for width in (1400, 900):
            with self.subTest(width=width), T.chrome() as cdp:
                p = self.show(cdp, width)
                say = f"document.querySelector('[data-id=\"{ref}\"] [data-wil-none]')"
                p.until(f"!!{say}", "View says it")
                self.assertEqual(p.js(f"{say}.textContent"), "No work items match this filter.")
                p.edit()
                say = f"document.querySelector('[data-id=\"{ref}\"] [data-wil-say=none]')"
                p.until(f"!!{say} && {say}.textContent.length > 40", "Edit says the long sentence")
                self.assertEqual(p.js(f"{say}.textContent"), "No work items match this filter, so this section is left out of the published page. Change the filter to list some.")

    def _edit(self, cdp, columns):
        ref = self.add({"mode": "all", "columns": columns, "owner": ["Pat Demo", "Lee Demo"]})
        p = self.show(cdp, 1400)
        p.edit()
        p.until(f"!!document.querySelector('[data-id=\"{ref}\"] .wil-table th[data-cw-head=due]')", "Edit drew")
        return p, ref

    def _where(self, p, ref, c, at="mid"):
        """[x, y] of a heading: near its left end, or with at="grip" the middle of its width handle."""
        sel = f"document.querySelector('[data-id=\"{ref}\"] .wil-table th[data-cw-head={c}]')"
        p.js(f"{sel}.scrollIntoView({{block: 'center'}})")      # the list sits low on the page: a mouse press needs the heading on screen
        if at == "grip":
            return p.js(f"(() => {{ const r = {sel}.querySelector('.cgrip').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }})()")
        return p.js(f"(() => {{ const r = {sel}.getBoundingClientRect(); return [r.left + 12, r.top + r.height / 2]; }})()")

    def _pointer_drag(self, p, x0, y0, x1, y1, steps=12, release=True):
        """A real press and moves through Input.dispatchMouseEvent: the browser itself starts the drag (a real dragstart on the pressed heading).
        Chrome does not run its own drag loop under automation, so the drag is intercepted (Input.setInterceptDrags) and the target
        is then reached with Input.dispatchDragEvent; the test never makes a DragEvent itself."""
        data = {"items": [], "dragOperationsMask": 1}
        p.cdp.call("Input.setInterceptDrags", {"enabled": True}, p.sid)
        p.mouse("mouseMoved", x0, y0)
        p.mouse("mousePressed", x0, y0, buttons=1)
        for i in range(1, steps + 1):
            x, y = x0 + (x1 - x0) * i / steps, y0 + (y1 - y0) * i / steps
            p.mouse("mouseMoved", x, y, buttons=1)
            if p.js("!!window.__drag") or i == steps:
                break
        for kind in ("dragEnter", "dragOver"):
            p.cdp.call("Input.dispatchDragEvent", {"type": kind, "x": x1, "y": y1, "data": data}, p.sid)
        if release:
            p.cdp.call("Input.dispatchDragEvent", {"type": "drop", "x": x1, "y": y1, "data": data}, p.sid)
            p.mouse("mouseReleased", x1, y1, buttons=1)

    def test_a_real_pointer_drag_of_a_heading_moves_the_column_and_the_item_heading_neither_drags_nor_takes_a_drop(self):      # row 1195 spec check defect 3
        with T.chrome() as cdp:
            p, ref = self._edit(cdp, ["owner", "due", "priority", "id"])
            self.assertEqual(self._heads(p, ref), ["title", "owner", "due", "priority", "id"])
            p.js("window.__drag = 0; document.addEventListener('dragstart', (e) => { if (e.isTrusted) window.__drag++; }, true)")
            x0, y0 = self._where(p, ref, "id")
            x1, y1 = self._where(p, ref, "owner")
            self._pointer_drag(p, x0, y0, x1, y1)
            self.assertEqual(p.js("window.__drag"), 1, "the browser started one real drag")
            self.assertTrue(wait(lambda: self._heads(p, ref) == ["title", "id", "owner", "due", "priority"]), "a pointer drag of ID onto Owner put ID before Owner")
            self.assertEqual(p.js("document.querySelectorAll('.wil-dragging, .wil-drop').length"), 0, "no drag mark is left after the drop")
            body = p.js(f"[...document.querySelectorAll('[data-id=\"{ref}\"] .wil-table tbody tr:first-child td')].map(c => c.className.replace('wil-c-', ''))")
            self.assertEqual([c for c in body if c in ("id", "owner", "due", "priority")], ["id", "owner", "due", "priority"], "the cells follow")
            self.assertEqual(p.js(f"document.querySelector('[data-id=\"{ref}\"] .wil-table th[data-cw-head=title]').draggable"), False)
            tx, ty = self._where(p, ref, "title")
            ox, oy = self._where(p, ref, "due")
            self._pointer_drag(p, tx, ty, ox, oy)
            self.assertEqual(self._heads(p, ref), ["title", "id", "owner", "due", "priority"], "dragging the Item heading changed no order")
            self._pointer_drag(p, ox, oy, tx, ty)
            self.assertEqual(self._heads(p, ref)[0], "title", "nothing is dropped before the Item column")

    def test_the_drag_marks_show_during_a_real_pointer_drag_and_the_width_handle_never_starts_a_move(self):      # row 1195 spec check defect 3
        with T.chrome() as cdp:
            p, ref = self._edit(cdp, ["owner", "due", "id"])
            p.js("window.__drag = 0; document.addEventListener('dragstart', (e) => { if (e.isTrusted) window.__drag++; }, true)")
            x0, y0 = self._where(p, ref, "id")
            x1, y1 = self._where(p, ref, "owner")
            self._pointer_drag(p, x0, y0, x1, y1, release=False)
            p.until(f"document.querySelector('[data-id=\"{ref}\"] .wil-table th[data-cw-head=id]').classList.contains('wil-dragging')", "the dragged heading is dimmed")
            p.until(f"document.querySelector('[data-id=\"{ref}\"] .wil-table th[data-cw-head=owner]').classList.contains('wil-drop')", "the target heading carries the drop mark")
            p.cdp.call("Input.dispatchDragEvent", {"type": "drop", "x": x1, "y": y1, "data": {"items": [], "dragOperationsMask": 1}}, p.sid)
            p.mouse("mouseReleased", x1, y1, buttons=1)
            p.until("document.querySelectorAll('.wil-dragging, .wil-drop').length === 0", "the marks go at the drop")
            self.assertTrue(wait(lambda: self._heads(p, ref) == ["title", "id", "owner", "due"]), "and the drop moved ID before Owner")
        with T.chrome() as cdp:
            p, ref = self._edit(cdp, ["owner", "due", "id"])
            width = lambda: p.js(f"document.querySelector('[data-id=\"{ref}\"] .wil-table th[data-cw-head=owner]').getBoundingClientRect().width")
            w0 = width()
            gx, gy = self._where(p, ref, "owner", "grip")
            p.js("window.__ds = 0; window.__drag = 0; document.addEventListener('dragstart', () => { window.__ds++; }, true)")
            self._pointer_drag(p, gx, gy, gx + 40, gy)
            self.assertTrue(wait(lambda: abs(width() - (w0 + 40)) < 2), "the handle drag widened Owner by the distance")
            self.assertEqual(p.js("window.__ds"), 0, "no drag started from the handle")
            self.assertEqual(self._heads(p, ref), ["title", "owner", "due", "id"], "the order is unchanged")

    def test_ctrl_with_an_arrow_steps_12_px_and_stops_at_the_minimum_and_alt_moves_without_resizing(self):      # row 1195 spec check defect 3
        with T.chrome() as cdp:
            p, ref = self._edit(cdp, ["owner", "due", "id"])
            w = lambda c: p.js(f"document.querySelector('[data-id=\"{ref}\"] .wil-table th[data-cw-head={c}]').getBoundingClientRect().width")
            CTRL = 2                                                       # Input.dispatchKeyEvent modifiers: Ctrl
            p.js(f"document.querySelector('[data-id=\"{ref}\"] .wil-table th[data-cw-head=owner]').focus()")
            start = w("owner")
            p.key("ArrowRight", CTRL, code="ArrowRight", vk=39)
            self.assertTrue(wait(lambda: abs(w("owner") - (start + 12)) < 1), "one Ctrl+Right is 12 px wider")
            p.key("ArrowLeft", CTRL, code="ArrowLeft", vk=37)
            p.key("ArrowLeft", CTRL, code="ArrowLeft", vk=37)
            self.assertTrue(wait(lambda: abs(w("owner") - (start - 12)) < 1), "two Ctrl+Left are 24 px back")
            for _ in range(60):
                p.key("ArrowLeft", CTRL, code="ArrowLeft", vk=37)
            self.assertTrue(wait(lambda: abs(w("owner") - 60) < 1), "the width stops at the mock-up's minimum of 60 px (ruling 20-11; the older 48 px minimum was the shared default)")
            for _ in range(40):
                p.key("ArrowRight", CTRL, code="ArrowRight", vk=39)
            self.assertTrue(wait(lambda: abs(w("owner") - 360) < 1), "and at the maximum of 360 px, not 1200")
            before = w("owner")
            p.key("ArrowRight", 1, code="ArrowRight", vk=39)               # Alt+Right moves the heading, it never resizes
            self.assertTrue(wait(lambda: self._heads(p, ref) == ["title", "due", "owner", "id"]), "Alt+Right moved Owner")
            self.assertLess(abs(w("owner") - before), 1, "and left its width alone")

    def _view(self, cdp, columns):
        ref = self.add({"mode": "all", "columns": columns, "owner": ["Pat Demo", "Lee Demo"]})
        p = self.show(cdp, 1400)
        p.until(f"!!document.querySelector('[data-id=\"{ref}\"] .wil-table th[data-cw-head=due]')", "View drew")
        self.assertEqual(p.js("document.querySelector('#report').dataset.mode"), "view")
        return p, ref

    def _bodies(self):
        return self.store.con.execute("SELECT id, body FROM report_sections ORDER BY id").fetchall()

    def test_view_a_real_pointer_drag_of_a_heading_moves_the_column_and_saves_nothing_in_the_document(self):      # row 1195 ruling: View too, unsaved
        with T.chrome() as cdp:
            p, ref = self._view(cdp, ["owner", "due", "priority", "id"])
            before = self._bodies()
            self.assertEqual(self._heads(p, ref), ["title", "owner", "due", "priority", "id"])
            self.assertEqual(p.js(f"document.querySelector('[data-id=\"{ref}\"] .wil-table th[data-cw-head=id]').draggable"), True)
            p.js("window.__drag = 0; document.addEventListener('dragstart', (e) => { if (e.isTrusted) window.__drag++; }, true)")
            x0, y0 = self._where(p, ref, "id")
            x1, y1 = self._where(p, ref, "owner")
            self._pointer_drag(p, x0, y0, x1, y1)
            self.assertEqual(p.js("window.__drag"), 1, "the browser started one real drag in View")
            self.assertTrue(wait(lambda: self._heads(p, ref) == ["title", "id", "owner", "due", "priority"]), "ID moved before Owner in View")
            body = p.js(f"[...document.querySelectorAll('[data-id=\"{ref}\"] .wil-table tbody tr:first-child td')].map(c => c.className.replace('wil-c-', ''))")
            self.assertEqual([c for c in body if c in ("id", "owner", "due", "priority")], ["id", "owner", "due", "priority"], "the cells follow")
            self.assertEqual(p.js("document.querySelector('#report').dataset.mode"), "view", "still View")
            self.assertEqual(self._bodies(), before, "nothing was written to the document")
            reload_to_new_page(p.js, f"!!document.querySelector('[data-id=\"{ref}\"] .wil-table th[data-cw-head=due]')", "View drew again")
            self.assertEqual(self._heads(p, ref), ["title", "id", "owner", "due", "priority"], "kept on this computer")

    def test_view_the_width_handle_alt_move_and_ctrl_resize_work_and_the_heading_says_so(self):      # row 1195 ruling: View too, unsaved
        with T.chrome() as cdp:
            p, ref = self._view(cdp, ["owner", "due", "id"])
            before = self._bodies()
            h = lambda c: f"document.querySelector('[data-id=\"{ref}\"] .wil-table th[data-cw-head={c}]')"
            w = lambda c: p.js(f"{h(c)}.getBoundingClientRect().width")
            self.assertEqual(p.js(f"{h('owner')}.tabIndex"), 0, "a heading is a tab stop in View")
            self.assertEqual(p.js(f"{h('owner')}.getAttribute('aria-label')"), HEAD_LABEL % "Owner")
            self.assertIsNone(p.js(f"{h('owner')}.getAttribute('aria-description')"))
            w0 = w("owner")
            gx, gy = self._where(p, ref, "owner", "grip")
            self._pointer_drag(p, gx, gy, gx + 40, gy)
            self.assertTrue(wait(lambda: abs(w("owner") - (w0 + 40)) < 2), "the handle drag widened Owner in View")
            self.assertEqual(self._heads(p, ref), ["title", "owner", "due", "id"], "and moved nothing")
            CTRL = 2
            p.js(f"{h('due')}.focus()")
            start = w("due")
            p.key("ArrowRight", CTRL, code="ArrowRight", vk=39)
            self.assertTrue(wait(lambda: abs(w("due") - (start + 12)) < 1), "one Ctrl+Right is 12 px wider in View")
            before_w = w("due")
            p.key("ArrowRight", 1, code="ArrowRight", vk=39)
            self.assertTrue(wait(lambda: self._heads(p, ref) == ["title", "owner", "id", "due"]), "Alt+Right moved Due in View")
            self.assertLess(abs(w("due") - before_w), 1, "without resizing it")
            self.assertEqual(self._bodies(), before, "nothing was written to the document")

    def test_the_type_column_is_not_drawn_nor_offered_in_configure(self):
        ref = self.add({"mode": "all", "columns": ["type", "id", "owner"], "owner": ["Pat Demo", "Lee Demo"]})
        with T.chrome() as cdp:
            p = self.show(cdp, 1400)
            sec = f'[data-id="{ref}"]'
            p.edit()
            p.until(f"!!document.querySelector('{sec} [data-wil-gear]') && !!document.querySelector('{sec} .wil-table td.wil-c-id')", "drew")
            self.assertEqual(p.js(f"[...document.querySelectorAll('{sec} .wil-table .wil-c-type')].filter(e => e.offsetParent).length"), 0, "no Type cell or heading is visible")
            self.assertTrue(p.js(f"document.querySelectorAll('{sec} .wil-table .wil-c-type').length > 0"), "the saved column stays in the markup, as Cards has it")
            p.js(f"document.querySelector('{sec} [data-wil-gear]').click()")
            p.until(f"!!document.querySelector('{sec} .wil-cfg .wil-opts label')", "open")
            self.assertEqual(p.js(f"[...document.querySelectorAll('{sec} .wil-cfg [data-field=columns] label')].filter(e => e.offsetParent).map(e => [e.querySelector('input').value, Number(getComputedStyle(e).order)]).sort((a, b) => a[1] - b[1]).map(x => x[0]).join()"),
                             "status,owner,due,priority,workstream,milestone,id")

    def test_a_long_owner_name_is_one_line_with_an_ellipsis_at_900_and_1400(self):
        self.demo.action(description="Long name step", owner="Alexandria Montgomery-Featherstonehaugh", due_date="2030-01-10", priority="High")
        for width in (1400, 900):
            ref = self.add({"mode": "all", "columns": ["id", "owner", "due", "priority"], "owner": ["Alexandria Montgomery-Featherstonehaugh"]})
            with T.chrome() as cdp:
                p = self.show(cdp, width)
                sec = f'[data-id="{ref}"]'
                p.until(f"!!document.querySelector('{sec} .wil-table td.wil-c-owner .nm')", "drew")
                got = json.loads(p.js(f"JSON.stringify((() => {{ const e = document.querySelector('{sec} .wil-table td.wil-c-owner .nm'), s = getComputedStyle(e); return [e.scrollWidth > e.clientWidth, s.textOverflow, s.whiteSpace]; }})())"))
                self.assertEqual(got, [True, "ellipsis", "nowrap"], (width, got))

    def test_a_half_width_row_is_the_mockups_two_lines_with_the_rating_beside_the_title(self):
        with self.store.step("dashboard", T.USER) as st:
            text = st.create("report_sections", {"project": "ABC", "type": "text", "title": "Fictional notes", "sort_order": 1})
        ref = self.add({"mode": "all", "columns": ["type", "id", "owner", "due", "priority"], "owner": ["Pat Demo", "Lee Demo"]}, after=text, beside=1)
        with T.chrome() as cdp:
            p = self.show(cdp, 1400)
            sec = f'[data-id="{ref}"]'
            p.until(f"!!document.querySelector('{sec} .wil-lines li .wil-hpr')", "the half rows drew")
            got = json.loads(p.js("JSON.stringify((() => { const li = document.querySelector('" + sec + " .wil-lines li'), r = (s) => li.querySelector(s).getBoundingClientRect(), t = r('.wil-t'), h = r('.wil-hpr'), m = r('.wil-m');"
                "const w = [...li.querySelectorAll('.wil-m > span')].map(e => e.textContent), s = getComputedStyle(li.querySelector('.wil-m'));"
                "return {words: w, beside: h.left >= t.right - 1 && Math.abs((h.top + h.bottom) / 2 - (t.top + t.bottom) / 2) < 14, below: m.top >= t.bottom - 1, flex: s.display, gap: s.columnGap, pr: li.querySelector('.wil-hpr').textContent}; })())"))
            self.assertTrue(got["beside"] and got["below"], got)
            self.assertEqual(got["flex"], "flex")
            self.assertNotEqual(got["gap"], "0px")
            self.assertEqual(got["pr"], "High")
            self.assertNotIn("High", got["words"], "the rating is not repeated on the second line")
            self.assertNotIn("Action", got["words"], "no Type word")
            self.assertIn("Pat Demo", got["words"])

    def half(self):
        with self.store.step("dashboard", T.USER) as st:
            text = st.create("report_sections", {"project": "ABC", "type": "text", "title": "Fictional notes", "sort_order": 1})
        return self.add({"mode": "all", "columns": ["type", "id", "owner", "due", "priority"], "owner": ["Pat Demo", "Lee Demo"]}, after=text, beside=1)

    def test_a_half_row_draws_the_rating_chip_only_for_a_rated_item_by_the_same_rule_as_the_table_cell(self):
        # the store never holds an unrated action or decision (priority is NOT NULL, checked), so the rule is pinned in the source and the rated chips in the page
        self.assertIn('kinds && columns.includes("priority") && ratedRow(row) ? <span class="wil-hpr">', ROWS_JSX)
        ref = self.half()
        with T.chrome() as cdp:
            p = self.show(cdp, 1400)
            sec = f'[data-id="{ref}"]'
            p.until(f"!!document.querySelector('{sec} .wil-lines li .wil-hpr')", "the half rows drew")
            got = json.loads(p.js("JSON.stringify([...document.querySelectorAll('" + sec + " .wil-lines li .wil-hpr')].map(e => e.textContent))"))
            self.assertIn("High", got)
            self.assertNotIn("—", got)

    def test_in_edit_at_900_the_eye_does_not_cover_the_rating_chip_of_a_half_row(self):
        ref = self.half()
        for width in (1400, 900):
            with T.chrome() as cdp:
                p = self.show(cdp, width)
                sec = f'[data-id="{ref}"]'
                p.edit()
                p.until(f"!!document.querySelector('{sec} .wil-lines li .wil-hpr') && !!document.querySelector('{sec} .wil-lines li .wil-eye')", "drew")
                got = json.loads(p.js("JSON.stringify([...document.querySelectorAll('" + sec + " .wil-lines li')].filter(li => li.querySelector('.wil-hpr')).map(li => { const e = li.querySelector('.wil-eye').getBoundingClientRect(), h = li.querySelector('.wil-hpr').getBoundingClientRect();"
                    "return [h.right <= e.left + 1 || h.left >= e.right - 1 || h.bottom <= e.top + 1 || h.top >= e.bottom - 1, e.width > 0, h.width > 0]; }))"))
                self.assertTrue(got)
                for apart, eye, chip in got:
                    self.assertTrue(eye and chip)
                    self.assertTrue(apart, f"the Edit eye and the rating chip overlap at {width}")

    def test_the_measured_values_of_the_mockup_caption_id_pill_tiles_plus_menu_and_columns(self):
        with self.store.step("dashboard", T.USER) as st:
            st.create("report_sections", {"project": "ABC", "type": "text", "title": "Fictional notes", "sort_order": 1})
        ref = self.add({"mode": "all", "columns": ["id", "owner", "due", "priority"], "caption": "What is due", "owner": ["Pat Demo", "Lee Demo", "Kim Demo"]})
        with T.chrome() as cdp:
            p = self.show(cdp, 1400)
            sec = f'[data-id="{ref}"]'
            p.edit()
            p.until(f"!!document.querySelector('{sec} .wil-table td.wil-c-id') && !!document.querySelector('{sec} .wil-pr')", "drew")
            q = lambda e, *props: json.loads(p.js("JSON.stringify((() => { const s = getComputedStyle(document.querySelector(" + json.dumps(f"{sec} {e}") + ")); return " + json.dumps(list(props)) + ".map(k => s[k]); })())"))
            self.assertEqual(q(".wil-cap", "fontSize", "color"), ["11.5px", "rgb(85, 103, 122)"], "caption")
            self.assertEqual(q("td.wil-c-id", "fontSize", "color", "fontWeight"), ["13px", "rgb(91, 71, 216)", "600"], "ID")
            self.assertIn("monospace", q("td.wil-c-id", "fontFamily")[0])
            self.assertEqual(q(".wil-pr", "borderTopLeftRadius", "fontSize", "fontWeight"), ["6px", "12px", "600"], "priority pill, in Edit too")
            self.assertEqual(q(".wil-table tbody tr:not(.wil-off) .ico", "width", "height", "borderTopLeftRadius"), ["28px", "28px", "7px"], "tile")
            self.assertEqual(q(".wil-add .newb", "borderTopLeftRadius"), ["6px"], "+ button")
            self.assertEqual(q("th.wil-c-owner", "width"), ["170px"])
            self.assertEqual(q("th.wil-c-due", "width"), ["104px"])
            self.assertEqual(q("th.wil-c-priority", "width"), ["84px"])
            self.assertEqual(q("th.wil-c-id", "width"), ["84px"])
            p.js(f"document.querySelector('{sec} .wil-add .newb').click()")
            p.until(f"!!document.querySelector('{sec} .wil-add .ddmenu')", "menu")
            self.assertEqual(q(".wil-add .ddmenu [role=menuitem]", "height"), ["44px"], "menu item")
            self.assertEqual(q(".wil-add .ddmenu", "boxShadow"), ["rgba(6, 47, 58, 0.2) 0px 10px 30px 0px"], "menu shadow")

    # The values below were measured in Chrome on work-items-mockup.html at 1400 and 900.
    # Row 1409: the priority chips take the one mapping the rating matrix has (pr is Medium amber, prh High red, pru Urgent maroon), not the mock-up's grey / amber / red
    MOCK = {"th": ["11.5px", "rgb(85, 103, 122)"], "pr": ["rgb(252, 239, 207)", "rgb(138, 90, 0)", "rgb(252, 239, 207)", "12px", "600", "6px"],
            "prh": ["rgb(246, 224, 221)", "rgb(163, 48, 31)", "rgb(246, 224, 221)"], "pru": ["rgb(107, 29, 42)", "rgb(255, 255, 255)", "rgb(107, 29, 42)"],
            "tA": ["rgb(237, 233, 255)", "rgb(75, 58, 181)"], "tR": ["rgb(253, 236, 234)", "rgb(180, 35, 24)"], "tI": ["rgb(107, 31, 42)", "rgb(255, 255, 255)"],
            "tD": ["rgb(231, 246, 236)", "rgb(6, 118, 71)"], "hid": ["rgb(238, 240, 244)", "rgb(152, 162, 179)"], "add": ["rgb(152, 162, 179)", "rgb(91, 71, 216)", "6px", "dashed"]}

    def test_colours_row_height_and_the_due_cell_equal_the_mockups_at_1400_and_900_in_view_and_edit(self):
        with self.store.step("dashboard", T.USER) as st:
            st.create("raid", {"project": "ABC", "type": "Issue", "description": "Server down", "raised": "2026-10-01", "source": "demo", "impact": "High", "likelihood": "High", "owner": "Pat Demo", "priority": "Urgent"})
            st.create("decisions", {"project": "ABC", "decision": "Pick the vendor", "date": "2026-10-01", "made_by": "Pat Demo", "source": "demo", "status": "Made"})
        self.demo.action(description="Urgent step", owner="Pat Demo", due_date="2030-01-10", priority="Urgent")
        self.demo.action(description="Medium step", owner="Pat Demo", due_date="2030-01-10", priority="Medium")
        hidden = self.demo.action(description="Hidden step", owner="Pat Demo", due_date="2030-01-10", priority="Medium")
        self.store.con.execute("INSERT INTO report_hidden (project, item_id) VALUES ('ABC', ?)", (hidden,))
        self.store.con.commit()
        ref = self.add({"mode": "all", "max": 50, "columns": ["id", "owner", "due", "priority"], "owner": ["Pat Demo"]})
        for width in (1400, 900):
            with T.chrome() as cdp:
                p = self.show(cdp, width)
                sec = f'[data-id="{ref}"]'
                p.until(f"!!document.querySelector('{sec} .wil-table tbody tr')", "View drew")
                for mode in ("view", "edit"):
                    if mode == "edit":
                        p.edit()
                        p.until(f"!!document.querySelector('{sec} [data-wil-gear]') && !!document.querySelector('{sec} .wil-table tbody tr')", "Edit drew")
                    q = lambda e, *props: json.loads(p.js("JSON.stringify((() => { const x = document.querySelector(" + json.dumps(f"{sec} {e}") + "); if (!x) return null; const s = getComputedStyle(x); return " + json.dumps(list(props)) + ".map(k => s[k]); })())"))
                    tag = (width, mode)
                    M = self.MOCK
                    self.assertEqual(q("th.wil-c-id", "fontSize", "color"), M["th"], tag)
                    self.assertEqual(q(".wil-pr:not(.h):not(.u)", "backgroundColor", "color", "borderTopColor", "fontSize", "fontWeight", "borderTopLeftRadius"), M["pr"], tag)
                    self.assertEqual(q(".wil-pr.h", "backgroundColor", "color", "borderTopColor"), M["prh"], tag)
                    self.assertEqual(q(".wil-pr.u", "backgroundColor", "color", "borderTopColor"), M["pru"], tag)
                    self.assertEqual(q("tr.wil-k-action:not(.wil-off) .ico", "backgroundColor", "color"), M["tA"], tag)
                    self.assertEqual(q("tr.wil-k-risk:not(.wil-off) .ico", "backgroundColor", "color"), M["tR"], tag)
                    self.assertEqual(q("tr.wil-k-issue:not(.wil-off) .ico", "backgroundColor", "color"), M["tI"], tag)
                    self.assertEqual(q("tr.wil-k-decision:not(.wil-off) .ico", "backgroundColor", "color"), M["tD"], tag)
                    if mode == "edit":
                        self.assertEqual(q("tr.wil-off .ico", "backgroundColor", "color"), M["hid"], tag)
                        self.assertEqual(q(".wil-add .newb", "borderTopColor", "color", "borderTopLeftRadius", "borderTopStyle"), M["add"], tag)
                    heights = json.loads(p.js(f"JSON.stringify([...document.querySelectorAll('{sec} .wil-table tbody tr')].map(e => e.getBoundingClientRect().height))"))
                    self.assertTrue(heights and all(48 <= h <= 49.5 for h in heights), (tag, heights))
                    cell = json.loads(p.js(f"JSON.stringify([...document.querySelectorAll('{sec} .wil-table td.wil-c-due')].map(e => [e.clientWidth, e.scrollWidth, Math.round(e.getBoundingClientRect().width)]))"))
                    for client, scroll, width_ in cell:
                        self.assertEqual(width_, 104, (tag, cell))
                        self.assertLessEqual(scroll, client, (tag, "the Due cell holds its content", cell))

    def test_a_row_the_client_eye_hides_has_a_grey_tile_even_when_its_status_is_green(self):
        with self.store.step("dashboard", T.USER) as st:
            item = st.create("decisions", {"project": "ABC", "decision": "Pick the vendor", "date": "2026-10-01", "made_by": "Pat Demo", "source": "demo", "status": "Made"})
        self.store.con.execute("INSERT INTO report_hidden (project, item_id) VALUES ('ABC', ?)", (item,))
        self.store.con.commit()
        ref = self.add({"mode": "all", "columns": ["id", "owner"], "owner": ["Pat Demo"]})
        with T.chrome() as cdp:
            p = self.show(cdp, 1400)
            sec = f'[data-id="{ref}"]'
            p.edit()
            p.until(f"!!document.querySelector('{sec} .wil-table tr.wil-off .ico')", "a hidden row drew")
            got = json.loads(p.js("JSON.stringify((() => { const s = getComputedStyle(document.querySelector('" + sec + " .wil-table tr.wil-off .ico')); return [s.backgroundColor, s.color]; })())"))
            self.assertEqual(got, self.MOCK["hid"])

    def test_the_tiles_are_coloured_by_kind_the_medium_pill_is_white_and_the_caret_is_inside_the_underline(self):
        for width in (1400, 900):
            ref = self.add(self.LIST)      # a tab pick saves the view's filter, so each width gets its own list
            with T.chrome() as cdp:
                p = self.show(cdp, width)
                sec = f'[data-id="{ref}"]'
                p.edit()
                p.until(f"!!document.querySelector('{sec} .vtab')", "tabs")
                p.js(f"document.querySelector('{sec} .vtab').click()")
                p.until(f"!!document.querySelector('{sec} .vt .vtabmenu')", "open tab")
                got = json.loads(p.js("JSON.stringify((() => { const c = (v) => { const e = document.createElement('i'); e.style.color = v; document.body.append(e); const r = getComputedStyle(e).color; e.remove(); return r; };"
                    "const tok = (n) => c('var(' + n + ')');"
                    "const tiles = {}; for (const tr of document.querySelectorAll('" + sec + " .wil-table tbody tr:not(.wil-off)')) { const k = tr.className.match(/wil-k-(\\w+)/)[1], i = getComputedStyle(tr.querySelector('.ico')); tiles[k] = [i.backgroundColor, i.color]; }"
                    "const med = [...document.querySelectorAll('" + sec + " .wil-pr:not(.h):not(.u)')].map((e) => { const s = getComputedStyle(e); return [s.backgroundColor, s.color, s.fontWeight, s.borderTopColor]; });"
                    "const vt = document.querySelector('" + sec + " .vt:has(.vtabmenu)'), tab = vt.querySelector('.vtab').getBoundingClientRect(), car = vt.querySelector('summary').getBoundingClientRect(), em = vt.querySelector('.vtab').lastElementChild.getBoundingClientRect();"
                    "return {tiles, med, want: {a: [tok('--brand-blue-tint'), tok('--status-blue-text')], r: [tok('--tone-red-tint'), tok('--tone-red-text')], i: [tok('--tone-urgent'), tok('--tone-on-urgent')], surface: tok('--surface'), text: tok('--text'), edge: tok('--grey-500')},"
                    "caret: [car.left - tab.left, tab.right - car.right, car.left - em.right]}; })())"))
                w = got["want"]
                self.assertEqual(got["tiles"].get("action"), self.MOCK["tA"], got)
                self.assertEqual(got["tiles"].get("risk"), self.MOCK["tR"], got)
                if "issue" in got["tiles"]:
                    self.assertEqual(got["tiles"]["issue"], self.MOCK["tI"], got)
                self.assertTrue(got["med"], "a Medium pill is listed")
                for bg, fg, weight, edge in got["med"]:
                    self.assertEqual((bg, fg, edge), tuple(self.MOCK["pr"][:3]), got)
                    self.assertGreaterEqual(int(weight), 600, got)
                left, right, after_count = got["caret"]
                self.assertGreaterEqual(left, 0, got)
                self.assertGreaterEqual(right, 0, "the caret is inside the tab's underline")
                self.assertLess(after_count, 10, "right after the last thing in the tab (the count pill, or the unsaved dot)")

    CONTRAST = ("(() => { const rgb = (s) => s.match(/[\\d.]+/g).map(Number); const lin = (c) => { c /= 255; return c <= .03928 ? c / 12.92 : ((c + .055) / 1.055) ** 2.4; };"
                "const lum = (c) => .2126 * lin(c[0]) + .7152 * lin(c[1]) + .0722 * lin(c[2]);"
                "const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + .05) / (Math.min(x, y) + .05); };"
                "const bgOf = (e) => { for (; e; e = e.parentElement) { const c = rgb(getComputedStyle(e).backgroundColor); if (c.length < 4 || c[3] > .5) return c; } return [255, 255, 255]; };"
                "const out = []; const pairs = [['.wil-table td.wil-c-id'], ['.wil-table .wil-pr:not(.h):not(.u)'], ['.wil-table .wil-pr.h'], ['.wil-table .wil-pr.u'], ['.wil-table tbody tr:not(.wil-off) .ico'], ['.wil-views .vtab'], ['.wil-views .vnew'], ['.wil-table th']];"
                "for (const [s] of pairs) for (const e of document.querySelectorAll('SEC ' + s)) { if (!e.offsetParent) continue; const cs = getComputedStyle(e); out.push([s, ratio(rgb(cs.color), bgOf(e))]); }"
                "return JSON.stringify(out); })()")

    def test_text_keeps_4_5_to_1_on_its_ground_in_light_and_dark_at_both_widths(self):
        ref = self.add(self.LIST)
        for width in (1400, 900):
            for dark in (False, True):
                with T.chrome() as cdp:
                    p = self.show(cdp, width, dark)
                    sec = f'[data-id="{ref}"]'
                    p.edit()
                    p.until(f"!!document.querySelector('{sec} .wil-table td.wil-c-id')", "drew")
                    got = json.loads(p.js(self.CONTRAST.replace("SEC", sec)))
                    self.assertGreater(len(got), 8, got)
                    for what, r in got:
                        self.assertGreaterEqual(r, 4.5, f"{what} at {width} dark={dark}: {r:.2f}")


class Cards(Look):
    classic = False

    def test_a_cards_view_still_leaves_an_empty_match_out(self):      # row 1195: the mock-up's words are Classic only
        ref = self.add({"owner": ["Nobody Demo"]})
        with T.chrome() as cdp:
            p = self.show(cdp, 1400)
            self.assertFalse(p.js(f"!!document.querySelector('[data-id=\"{ref}\"]')"), "Cards View leaves it out")
            p.edit()
            p.until(f"!!document.querySelector('[data-id=\"{ref}\"] [data-wil-say=none]')", "Edit says it")
            self.assertEqual(p.js(f"document.querySelector('[data-id=\"{ref}\"] [data-wil-say=none]').textContent"), "No work items match this filter, so this section is left out of the published page. Change the filter to list some.")

    def test_a_cards_heading_has_no_aria_label_and_keeps_its_alt_sentence(self):      # row 1195: the new heading labels are Classic only
        ref = self.add({"mode": "all", "columns": ["owner", "due"], "owner": ["Pat Demo", "Lee Demo"]})
        with T.chrome() as cdp:
            p = self.show(cdp, 1400)
            p.edit()
            h = f"document.querySelector('[data-id=\"{ref}\"] .wil-table th[data-cw-head=owner]')"
            p.until(f"!!{h}", "Edit drew")
            self.assertIsNone(p.js(f"{h}.getAttribute('aria-label')"))
            self.assertEqual(p.js(f"{h}.getAttribute('aria-description')"), "Width of the Owner column. Alt with Left or Right arrow changes it.")
            self.assertEqual(p.js(f"{h}.tabIndex"), -1)

    def capture(self, width):
        ref = self.add(Classic.LIST)
        out = {}
        with T.chrome() as cdp:
            p = self.show(cdp, width)
            sec = f'[data-id="{ref}"]'
            p.until(f"!!document.querySelector('{sec} .wil-table')", "view drew")
            out["view"] = p.js(f"document.querySelector('{sec}').outerHTML")
            p.edit()
            p.until(f"!!document.querySelector('{sec} [data-wil-gear]')", "edit drew")
            out["edit"] = p.js(f"document.querySelector('{sec}').outerHTML")
            p.js(f"document.querySelector('{sec} .wil-add .newb').click()")
            p.until(f"!!document.querySelector('{sec} .wil-add .ddmenu')", "menu")
            out["menu"] = p.js(f"document.querySelector('{sec} .wil-add').outerHTML")
        return {k: hashlib.md5(re.sub(r"In \d+ days", "In N days", v.replace(ref, "REF")).encode("utf-8")).hexdigest() for k, v in out.items()}, out

    def test_the_rendered_work_items_dom_is_the_dom_main_renders_at_1400_and_900(self):
        for width in (1400, 900):
            got, html = self.capture(width)
            self.assertNotIn("wil-k-", "".join(html.values()), "a Cards row carries no kind class")
            self.assertEqual(got, CARDS_DOM_MD5[width], width)

    def test_the_cards_add_menu_keeps_the_old_order_in_the_markup_and_for_the_arrow_keys(self):
        ref = self.add(Classic.LIST)
        with T.chrome() as cdp:
            p = self.show(cdp, 1400)
            self.assertEqual(menu_walk(self, p, ref), (["action", "risk", "issue", "decision"], ["action", "risk", "issue", "decision"]))

    def test_cards_has_no_show_all_items_link(self):
        ref = self.add({"mode": "all", "max": 2, "columns": ["id", "owner"], "owner": ["Pat Demo", "Lee Demo"]})
        with T.chrome() as cdp:
            p = self.show(cdp, 1400)
            p.until(f"!!document.querySelector('[data-id=\"{ref}\"] .wil-scroll')", "View drew")
            self.assertFalse(p.js(f"!!document.querySelector('[data-id=\"{ref}\"] .wil-all-b')"))

    def test_cards_keeps_the_old_scroll_box_markup_and_the_classic_changes_are_gated_by_classicTheme(self):
        # Cards: more rows than Most rows keeps role region, aria-label and a tab stop (the old expression); the Classic-only open-box rule is behind classicTheme()
        self.assertIn("const scrolls = classicTheme() ? count > max && !all : count > max;", ROWS_JSX)
        self.assertIn("const on = classicTheme() && !fromFile.value && count > max;", ROWS_JSX)
        self.assertIn('{kinds && columns.includes("priority") && ratedRow(row)', ROWS_JSX)
        self.assertIn('const kinds = classicTheme();', ROWS_JSX)
        ref = self.add({"mode": "all", "max": 2, "columns": ["id", "owner"], "owner": ["Pat Demo", "Lee Demo"]})
        with T.chrome() as cdp:
            p = self.show(cdp, 1400)
            p.until(f"!!document.querySelector('[data-id=\"{ref}\"] .wil-scroll')", "View drew")
            self.assertEqual(p.js(f"(() => {{ const b = document.querySelector('[data-id=\"{ref}\"] .wil-scroll'); return [b.getAttribute('role'), b.getAttribute('aria-label'), b.tabIndex]; }})()"), ["region", "Work items, scroll for more", 0])
            self.assertFalse(p.js(f"!!document.querySelector('[data-id=\"{ref}\"] .wil-hpr')"), "a Cards row has no half-row chip")

    def test_a_cards_page_has_no_theme_block_and_so_no_kind_class(self):
        self.assertNotIn('id="theme"', testpage.html())
