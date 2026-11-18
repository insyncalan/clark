"""Row 1195: the Work items section's Edit and View as the approved mock-up draws them (header order, tabs, the + and its menu, Configure, table cells).

Run: python3 dev/run_tests.py test_work_items_mockup_1195
The look is Classic only: every rule is in the Classic theme layer (src/clark/themes/prototype-2.0/rules.css), shell.css and edit.css are untouched,
and the Cards page is proved unchanged (its style blocks by md5 and its rendered Work items DOM, in Edit and View with the Add menu open, at 1400 and 900).
The rules are pinned by their CSS text; the order and the look are pinned in the served Classic page.
"""
import hashlib
import json
import re
import unittest

from _paths import SRC
from clark import page, theme
import test_tpl_workitems as T
from test_report_editor import Pg
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
    ".wil-table th { font-size: var(--size-caption); }",
    ".wil-table td.wil-c-id, .wil-c-id { font-family: ui-monospace, Menlo, Consolas, monospace; font-size: var(--size-caption); font-weight: var(--weight-medium); font-variant-numeric: tabular-nums; color: var(--status-blue); }",
    ".wil-pr { border: 1px solid var(--grey-500); border-radius: 6px; background: var(--surface); color: var(--text); font-size: calc(var(--size-caption) - 1px); font-weight: var(--weight-medium); }",
    ".wil-pr.h, .wil-pr.u { border-color: color-mix(in srgb, currentColor 30%, transparent); }",
    ".wil-off .wil-pr { border-color: var(--grey-200); }",
    ".wil-table tr.wil-k-action:not(.wil-off) .ico, .wil-lines li.wil-k-action:not(.wil-off) .ico { background: var(--brand-blue-tint); color: var(--status-blue-text); }",
    ".wil-table tr.wil-k-risk:not(.wil-off) .ico, .wil-lines li.wil-k-risk:not(.wil-off) .ico { background: var(--tone-red-tint); color: var(--tone-red-text); }",
    ".wil-table tr.wil-k-issue:not(.wil-off) .ico, .wil-lines li.wil-k-issue:not(.wil-off) .ico { background: var(--tone-urgent); color: var(--tone-on-urgent); }",
    ".wil-table tr.wil-k-decision:not(.wil-off) .ico, .wil-lines li.wil-k-decision:not(.wil-off) .ico { background: var(--tone-green-tint); color: var(--tone-green-text); }",
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
    ".wil-gear { border: 1.5px solid var(--grey-200); }",
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
    ".wil-add .newb { box-sizing: border-box; width: 34px; height: 34px; min-width: 0; padding: 0; justify-content: center; border: 1px dashed var(--grey-500); border-radius: 6px; background: none; color: var(--status-blue-text); }",
    ".wil-add .newb:hover, .wil-add .newb:focus-visible, .wil-add .newb[aria-expanded=\"true\"] { background: var(--grey-50); border-color: var(--grey-500); color: var(--status-blue-text); }",
    ".wil-add .newb:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; }",
    ".wil-add .newb .w, .wil-add .newb:hover .w, .wil-add .newb:focus-visible .w, .wil-add .newb[aria-expanded=\"true\"] .w, .wil-add .newb .nch { display: none; }",
    ".wil-add .ddmenu { min-width: calc(var(--space-8) * 2); padding: var(--space-1); border: 1px solid var(--grey-200); border-radius: var(--radius-lg); background: var(--surface); box-shadow: 0 10px 30px rgba(6, 47, 58, .2); }",
    ".wil-add .ddmenu [role=\"menuitem\"] { display: flex; align-items: center; gap: var(--space-2); min-height: calc(var(--space-6) + var(--space-3)); padding: 0 var(--space-2); border-radius: var(--radius); font-weight: var(--weight-medium); color: var(--text); }",
    ".wil-add .ddmenu [role=\"menuitem\"]:hover, .wil-add .ddmenu [role=\"menuitem\"]:focus-visible { background: var(--grey-50); color: var(--text); }",
    ".wil-add .ddmenu [role=\"menuitem\"]:focus-visible { outline: 0; }",
    ".wil-add .ddmenu [role=\"menuitem\"] .mi { display: none; }",
    ".wil-add .ddmenu [role=\"menuitem\"]::before { content: attr(data-kind); display: inline-grid; place-items: center; flex: none; width: var(--space-5); height: var(--space-5); border-radius: 6px; font-size: var(--size-caption); font-weight: var(--weight-semibold); line-height: 1; background: var(--tone-grey-tint); color: var(--tone-grey-text); }",
    ".wil-add .ddmenu [role=\"menuitem\"][data-kind=\"action\"]::before { content: \"A\"; background: var(--brand-blue-tint); color: var(--status-blue-text); }",
    ".wil-add .ddmenu [role=\"menuitem\"][data-kind=\"risk\"]::before { content: \"R\"; background: var(--tone-red-tint); color: var(--tone-red-text); }",
    ".wil-add .ddmenu [role=\"menuitem\"][data-kind=\"issue\"]::before { content: \"I\"; background: var(--tone-urgent); color: var(--tone-on-urgent); }",
    ".wil-add .ddmenu [role=\"menuitem\"][data-kind=\"decision\"]::before { content: \"D\"; background: var(--tone-green-tint); color: var(--tone-green-text); }",
    ".wil-views .vtab { font-weight: var(--weight-medium); }",
    ".wil-views .vtab em { font-weight: var(--weight-regular); color: var(--text-muted); }",
    ".wil-views .vnew { color: var(--status-blue-text); font-weight: var(--weight-medium); }",
    ".wil-views .vnew:hover { color: var(--status-blue-text); }",
    ".wil-views .vtabs { flex-wrap: wrap; overflow: visible; }",
    ".wil-views .vt { gap: 0; }",
    ".wil-views .vt:has(> .wil-vopts) .vtab { padding-right: calc(var(--space-5) + var(--space-1)); }",
    ".wil-views .vt > .wil-vopts { margin-left: calc(-1 * (var(--space-5) + var(--space-1))); }",
    ".wil-add .ddmenu.on { display: flex; flex-direction: column; }",
    ".wil-add .ddmenu [role=\"menuitem\"][data-kind=\"risk\"] { order: 1; }",
    ".wil-add .ddmenu [role=\"menuitem\"][data-kind=\"action\"] { order: 2; }",
    ".wil-add .ddmenu [role=\"menuitem\"][data-kind=\"issue\"] { order: 3; }",
    ".wil-add .ddmenu [role=\"menuitem\"][data-kind=\"decision\"] { order: 4; }",
    "#report[data-mode=\"view\"] .wil-scroll { scrollbar-width: none; }",
    "#report[data-mode=\"view\"] .wil-scroll::-webkit-scrollbar { display: none; }",
    ".wil-table .wil-c-type, .wil-cfg .wil-opts label:has(> input[value=\"type\"]) { display: none; }",
    ".wil-table .wil-own .nm { overflow: visible; text-overflow: clip; white-space: normal; overflow-wrap: anywhere; }",
    ".wil-lines li { grid-template-columns: calc(var(--space-5) + var(--space-1)) minmax(0, 1fr) auto; }",
    ".wil-lines .wil-t { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }",
    ".wil-lines .wil-hpr { grid-column: 3; grid-row: 1; justify-self: end; align-self: center; }",
    ".wil-lines .wil-m { grid-column: 2 / span 2; display: flex; flex-wrap: wrap; gap: 2px var(--space-3); }",
    ".wil-lines .wil-m > span { white-space: nowrap; }",
    ".wil-cap { font-size: calc(var(--size-caption) - 1.5px); color: rgb(85, 103, 122); }",
    ":root[data-theme=dark] .wil-cap { color: var(--text-muted); }",
    "@media (prefers-color-scheme: dark) { :root[data-theme=auto] .wil-cap { color: var(--text-muted); } }",
    ".wil-table .ico, .wil-lines .ico { width: calc(var(--space-5) + var(--space-1)); height: calc(var(--space-5) + var(--space-1)); border-radius: 7px; }",
    ".wil-table tr.wil-off .ico, .wil-lines li.wil-off .ico { background: var(--tone-grey-tint); color: var(--tone-grey-text); }",
    ".wil-table .wil-c-owner { width: 170px; }",
    ".wil-table .wil-c-due { width: 104px; }",
    ".wil-table .wil-c-priority { width: 84px; }",
    ".wil-table .wil-c-id { width: 84px; }",
]

# The Cards page as origin/main (305aa739a) serves it: the md5 of every <style> block of page_html(branding=NO_BRAND, theme=None), and the md5 of
# the rendered Work items section (Edit; View; the Add menu opened) with its section id folded to REF, at 1400 and 900 (CARDS_DOM below).
# This row must not change any of them. If one differs after a merge of main, re-measure on origin/main: a difference with no CSS or Work items
# change in main is a Cards change made by this row.
CARDS_STYLE_MD5 = {"blocks": ["a740a0333d7a944d2a661f3cb4c74d33"]}
_DOM = {"view": "8e6c915d4f6df112000e5150fe406783", "edit": "5f01b907b0a8519810c6ee5ecc0df512", "menu": "b03f939c186bd71f3069fe998036641e"}
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
        gear, tabs, line, rows = (JSX.index(x) for x in ('<div class="wil-form">', "<Tabs add=", '<div class="wil-line"', "<Scroller"))
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
        self.assertIn("border: 1.5px solid var(--grey-200)", rule(RULES, ".wil-gear"))

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
        self.assertIn("border: 1px solid var(--grey-500)", rule(RULES, ".wil-pr"))
        self.assertIn("border-color:", rule(RULES, ".wil-pr.h, .wil-pr.u"))

    def test_the_medium_pill_is_white_with_a_dark_border_and_bold_dark_text(self):
        pr = rule(RULES, ".wil-pr")
        for want in ("background: var(--surface)", "color: var(--text)", "font-weight: var(--weight-medium)", "border: 1px solid var(--grey-500)", "border-radius: 6px"):
            self.assertIn(want, pr)
        self.assertNotIn("grey-100", pr)
        self.assertIn("background: var(--tone-amber-tint)", rule(SHELL_CSS, ".wil-pr.h"))
        self.assertIn("background: var(--tone-red-tint)", rule(SHELL_CSS, ".wil-pr.u"))

    def test_the_letter_tile_is_coloured_by_the_kind_in_the_rows_and_in_the_add_menu_and_only_classic_marks_a_row_with_its_kind(self):
        def tile(kind):
            return rule(RULES, f".wil-table tr.wil-k-{kind}:not(.wil-off) .ico, .wil-lines li.wil-k-{kind}:not(.wil-off) .ico")
        self.assertIn("background: var(--brand-blue-tint); color: var(--status-blue-text)", tile("action"))
        self.assertIn("background: var(--tone-red-tint); color: var(--tone-red-text)", tile("risk"))
        self.assertIn("background: var(--tone-urgent); color: var(--tone-on-urgent)", tile("issue"))
        self.assertIn("background: var(--tone-green-tint); color: var(--tone-green-text)", tile("decision"))
        for kind, letter in (("action", "A"), ("risk", "R"), ("issue", "I"), ("decision", "D")):
            self.assertIn(f'content: "{letter}"', rule(RULES, f'.wil-add .ddmenu [role="menuitem"][data-kind="{kind}"]::before'))
        self.assertIn('document.getElementById("theme")', ROWS_JSX)
        self.assertIn('kinds ? ` wil-k-${row.kind}` : ""', ROWS_JSX)

    def test_the_open_tabs_caret_sits_inside_the_tab_underline_right_after_the_tab_words(self):
        self.assertIn("gap: 0", rule(RULES, ".wil-views .vt"))
        self.assertIn("padding-right: calc(var(--space-5) + var(--space-1))", rule(RULES, ".wil-views .vt:has(> .wil-vopts) .vtab"))
        self.assertIn("margin-left: calc(-1 * (var(--space-5) + var(--space-1)))", rule(RULES, ".wil-views .vt > .wil-vopts"))

    def test_the_heading_row_is_caption_size_caps(self):
        self.assertIn("font-size: var(--size-caption)", rule(RULES, ".wil-table th"))

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
        text = RULES[RULES.index("Row 1195"):]
        self.assertIsNone(re.search(r"#\d", text))


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
                tiles = p.js("[...document.querySelectorAll('" + sec + " .wil-add .ddmenu [role=menuitem]')].map(e => getComputedStyle(e, '::before').content).join('')")
                self.assertEqual(tiles, '"A""R""I""D"', "the markup keeps its order")
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

    def test_the_add_menu_shows_risk_action_issue_decision_by_css_order_and_the_markup_keeps_its_order(self):
        ref = self.add(self.LIST)
        with T.chrome() as cdp:
            p = self.show(cdp, 1400)
            sec = f'[data-id="{ref}"]'
            p.edit()
            p.until(f"!!document.querySelector('{sec} .wil-add .newb')", "drew")
            p.js(f"document.querySelector('{sec} .wil-add .newb').click()")
            p.until(f"!!document.querySelector('{sec} .wil-add .ddmenu')", "menu")
            got = json.loads(p.js("JSON.stringify([...document.querySelectorAll('" + sec + " .wil-add .ddmenu [role=menuitem]')].map(e => [e.dataset.kind, Math.round(e.getBoundingClientRect().top)]))"))
            self.assertEqual([k for k, _ in sorted(got, key=lambda x: x[1])], ["risk", "action", "issue", "decision"], got)
            self.assertEqual([k for k, _ in got], ["action", "risk", "issue", "decision"], "the markup (and the arrow keys) keep the page's order")

    def test_the_views_list_scroll_bar_is_hidden_in_view_and_not_in_edit(self):
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
            self.assertEqual(p.js(probe)[0], "auto", "Edit keeps its scroll bar")

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

    def test_a_long_owner_name_is_wrapped_never_cut_at_900_and_1400(self):
        self.demo.action(description="Long name step", owner="Alexandria Montgomery-Featherstonehaugh", due_date="2030-01-10", priority="High")
        for width in (1400, 900):
            ref = self.add({"mode": "all", "columns": ["id", "owner", "due", "priority"], "owner": ["Alexandria Montgomery-Featherstonehaugh"]})
            with T.chrome() as cdp:
                p = self.show(cdp, width)
                sec = f'[data-id="{ref}"]'
                p.until(f"!!document.querySelector('{sec} .wil-table td.wil-c-owner .nm')", "drew")
                got = json.loads(p.js(f"JSON.stringify((() => {{ const e = document.querySelector('{sec} .wil-table td.wil-c-owner .nm'), s = getComputedStyle(e); return [e.scrollWidth <= e.clientWidth, s.textOverflow, s.whiteSpace]; }})())"))
                self.assertEqual(got, [True, "clip", "normal"], (width, got))

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
            got = json.loads(p.js("JSON.stringify((() => { const c = (v) => { const e = document.createElement('i'); e.style.color = v; document.body.append(e); const r = getComputedStyle(e).color; e.remove(); return r; };"
                "const s = getComputedStyle(document.querySelector('" + sec + " .wil-table tr.wil-off .ico')); return [s.color, c('var(--tone-grey-text)')]; })())"))
            self.assertEqual(got[0], got[1])

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
                self.assertEqual(got["tiles"].get("action"), w["a"], got)
                self.assertEqual(got["tiles"].get("risk"), w["r"], got)
                if "issue" in got["tiles"]:
                    self.assertEqual(got["tiles"]["issue"], w["i"], got)
                self.assertTrue(got["med"], "a Medium pill is listed")
                for bg, fg, weight, edge in got["med"]:
                    self.assertEqual((bg, fg, edge), (w["surface"], w["text"], w["edge"]), got)
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
        return {k: hashlib.md5(v.replace(ref, "REF").encode("utf-8")).hexdigest() for k, v in out.items()}, out

    def test_the_rendered_work_items_dom_is_the_dom_main_renders_at_1400_and_900(self):
        for width in (1400, 900):
            got, html = self.capture(width)
            self.assertNotIn("wil-k-", "".join(html.values()), "a Cards row carries no kind class")
            self.assertEqual(got, CARDS_DOM_MD5[width], width)

    def test_a_cards_page_has_no_theme_block_and_so_no_kind_class(self):
        self.assertNotIn('id="theme"', testpage.html())
