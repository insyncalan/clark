"""Row 1195: the Work items section's Edit and View as the approved mock-up draws them (header order, tabs, the + and its menu, Configure, table cells).

Run: python3 dev/run_tests.py test_work_items_mockup_1195
The rules are pinned by their CSS text and the source; the order and the look are pinned in the served page.
"""
import json
import re
import sys
import unittest

from _paths import SRC
import test_tpl_workitems as T

PAGE = SRC / "clark" / "page"
EDIT_CSS = (PAGE / "src" / "edit" / "edit.css").read_text(encoding="utf-8")
SHELL_CSS = (PAGE / "shell.css").read_text(encoding="utf-8")
JSX = (PAGE / "src" / "edit" / "templates" / "WorkItemsList.jsx").read_text(encoding="utf-8")


GOLDEN_LINES = {
    "shell.css": [
        ".wil-table th { text-align: left; font-weight: var(--weight-regular); font-size: var(--size-caption); letter-spacing: var(--tracking-caps); text-transform: uppercase; color: var(--text-muted); padding: 6px var(--space-2); border-top: 1px solid var(--grey-200); }",
        ".wil-table td.wil-c-id, .wil-c-id { font-family: ui-monospace, Menlo, Consolas, monospace; font-weight: var(--weight-medium); font-variant-numeric: tabular-nums; color: var(--status-blue-text); }",
        ".wil-pr { padding: 0 var(--space-2); border: 1px solid var(--grey-200); border-radius: var(--radius-sm); background: var(--grey-100); color: var(--grey-700); font-weight: var(--weight-medium); }",
        ".wil-pr.h, .wil-pr.u { border-color: color-mix(in srgb, currentColor 30%, transparent); }",
        ".wil-table .wil-c-workstream, .wil-table .wil-c-milestone { width: 100px; }",
        ".wil-table td.wil-c-due { white-space: nowrap; overflow-wrap: normal; }",
        ".wil-table .wil-c-due { width: 116px; }",
    ],
    "edit.css": [
        ".wil-form { margin: 0; padding: 0; border: 0; background: none; }",
        ".wil-add .newb { box-sizing: border-box; width: 34px; height: 34px; min-width: 0; padding: 0; justify-content: center; border: 1px dashed var(--grey-500); border-radius: var(--radius); background: none; color: var(--status-blue-text); }",
        ".wil-add .newb:hover, .wil-add .newb:focus-visible, .wil-add .newb[aria-expanded=\"true\"] { background: var(--grey-50); border-color: var(--grey-500); color: var(--status-blue-text); }",
        ".wil-add .newb:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; }",
        ".wil-add .newb .w, .wil-add .newb:hover .w, .wil-add .newb:focus-visible .w, .wil-add .newb[aria-expanded=\"true\"] .w, .wil-add .newb .nch { display: none; }",
        ".wil-add .ddmenu { min-width: calc(var(--space-8) * 2); padding: var(--space-1); border: 1px solid var(--grey-200); border-radius: var(--radius-lg); background: var(--surface); box-shadow: var(--shadow); }",
        ".wil-add .ddmenu [role=\"menuitem\"] { display: flex; align-items: center; gap: var(--space-2); min-height: calc(var(--space-6) + var(--space-2)); padding: 0 var(--space-2); border-radius: var(--radius); font-weight: var(--weight-medium); color: var(--text); }",
        ".wil-add .ddmenu [role=\"menuitem\"]:hover, .wil-add .ddmenu [role=\"menuitem\"]:focus-visible { background: var(--grey-50); color: var(--text); }",
        ".wil-add .ddmenu [role=\"menuitem\"]:focus-visible { outline: 0; }",
        ".wil-add .ddmenu .mtile { width: var(--space-5); height: var(--space-5); }",
        ".wil-cw { position: absolute; top: var(--sec-pad-t); right: var(--sec-px); z-index: 6; display: flex; justify-content: flex-end; }",
        ".wil-gear { display: inline-flex; align-items: center; justify-content: center; min-width: calc(var(--space-6) + var(--space-1)); min-height: calc(var(--space-6) + var(--space-1)); border: 1.5px solid var(--grey-200); border-radius: 50%; background: var(--surface); color: var(--text); cursor: pointer; }",
        ".wil-cfg { position: absolute; right: 0; top: calc(100% + var(--space-1)); z-index: 20; width: min(calc(var(--space-4) * 19), calc(100vw - var(--space-6))); box-sizing: border-box; display: grid; gap: var(--space-3); padding: var(--space-3); border: 1px solid var(--grey-200); border-radius: var(--radius); background: var(--surface); box-shadow: var(--shadow); }",
        ".wil-cfg h4 { margin: 0; font-family: var(--font-head); font-size: var(--size-body); font-weight: var(--weight-semibold); color: var(--heading); }",
        ".wil-cfg .wil-sel > span, .wil-cfg .wil-f legend { font-weight: var(--weight-medium); color: var(--text-muted); }",
        ".wil-cfg .wil-opts input[type=\"checkbox\"] { width: var(--space-4); height: var(--space-4); margin: 0; accent-color: var(--brand-blue); }",
        ".wil-cfg .wil-sel select:focus-visible, .wil-cfg .wil-sel input:focus-visible { outline: 2px solid var(--brand-blue); outline-offset: 1px; }",
        ".wil-cacts button { min-height: calc(var(--space-6) + var(--space-1)); padding: 0 var(--space-4); border: 0; border-radius: var(--radius-pill); background-color: var(--pill-color); background-image: var(--pill-bg); color: var(--pill-fg); font: inherit; font-weight: var(--weight-semibold); cursor: pointer; }",
        ".wil-edit > .wil-views { margin-top: var(--space-3); }",
        ".wil-views .vtab { font-weight: var(--weight-medium); }",
        ".wil-views .vtab em { font-weight: var(--weight-regular); color: var(--text-muted); }",
        ".wil-views .vnew { color: var(--status-blue-text); font-weight: var(--weight-medium); }",
        ".wil-views .vnew:hover { color: var(--status-blue-text); }",
        ".wil-views .vtabs { flex-wrap: wrap; overflow: visible; }",
        ".wil-edit .wil-line { margin: 0 0 var(--space-3); }",
        ".wil-table .wil-c-eye .ib { color: var(--text); }",
        ".wil-off .wil-c-eye .ib { color: var(--grey-500); }",
    ],
}


def rule(css, selector):
    """The body of the first rule whose selector list is exactly `selector`."""
    m = re.search(r"(?:^|\n)" + re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert m, selector
    return m.group(1)


class SourceRules(unittest.TestCase):
    def test_the_header_order_is_gear_then_tabs_then_filter_then_table(self):
        gear, tabs, line, rows = (JSX.index(x) for x in ('<div class="wil-form">', "<Tabs add=", '<div class="wil-line"', "<Scroller"))
        self.assertLess(gear, tabs)
        self.assertLess(tabs, line)
        self.assertLess(line, rows)

    def test_the_gear_is_in_the_title_row_and_the_form_bar_is_gone(self):
        cw = rule(EDIT_CSS, ".wil-cw")
        self.assertIn("position: absolute", cw)
        self.assertIn("right: var(--sec-px)", cw)
        form = rule(EDIT_CSS, ".wil-form")
        for gone in ("background: var(--grey-50)", "border: 1px solid", "padding: var(--space-3)"):
            self.assertNotIn(gone, form)
        self.assertIn("border: 1.5px solid var(--grey-200)", rule(EDIT_CSS, ".wil-gear"))

    def test_tabs_are_semibold_with_grey_count_pills_and_a_violet_new_view(self):
        self.assertIn("font-weight: var(--weight-medium)", rule(EDIT_CSS, ".wil-views .vtab"))
        self.assertIn("color: var(--text-muted)", rule(EDIT_CSS, ".wil-views .vtab em"))
        new = rule(EDIT_CSS, ".wil-views .vnew")
        self.assertIn("color: var(--status-blue-text)", new)
        self.assertIn("font-weight: var(--weight-medium)", new)
        self.assertIn("border-bottom-color: var(--brand-blue)", rule(SHELL_CSS, '.vtab[aria-pressed="true"]'))

    def test_the_plus_is_a_dashed_square_in_every_state_and_never_a_filled_pill(self):
        base = rule(EDIT_CSS, ".wil-add .newb")
        self.assertIn("border: 1px dashed", base)
        self.assertIn("width: 34px; height: 34px", base)
        open_ = rule(EDIT_CSS, '.wil-add .newb:hover, .wil-add .newb:focus-visible, .wil-add .newb[aria-expanded="true"]')
        self.assertIn("var(--grey-50)", open_)
        self.assertNotIn("brand-blue", open_)
        self.assertIn("display: none", rule(EDIT_CSS, '.wil-add .newb .w, .wil-add .newb:hover .w, .wil-add .newb:focus-visible .w, .wil-add .newb[aria-expanded="true"] .w, .wil-add .newb .nch'))

    def test_the_add_menu_is_white_with_a_shadow_bold_labels_and_a_soft_grey_hover(self):
        box = rule(EDIT_CSS, ".wil-add .ddmenu")
        self.assertIn("background: var(--surface)", box)
        self.assertIn("box-shadow: var(--shadow)", box)
        self.assertIn("font-weight: var(--weight-medium)", rule(EDIT_CSS, '.wil-add .ddmenu [role="menuitem"]'))
        hov = rule(EDIT_CSS, '.wil-add .ddmenu [role="menuitem"]:hover, .wil-add .ddmenu [role="menuitem"]:focus-visible')
        self.assertIn("background: var(--grey-50)", hov)
        self.assertIn("outline: 0", rule(EDIT_CSS, '.wil-add .ddmenu [role="menuitem"]:focus-visible'))

    def test_configure_lists_the_columns_in_the_mockup_order_and_keeps_type_last(self):
        self.assertIn("SHOWN_COLUMNS = DESIGN_COLUMNS.concat(", JSX)
        self.assertIn("values={SHOWN_COLUMNS}", JSX)
        self.assertNotIn("values={COLUMNS}", JSX)

    def test_configure_done_is_the_aqua_pill_and_the_checkboxes_are_18_wide_violet(self):
        done = rule(EDIT_CSS, ".wil-cacts button")
        self.assertIn("background-image: var(--pill-bg)", done)
        self.assertIn("color: var(--pill-fg)", done)
        box = rule(EDIT_CSS, '.wil-cfg .wil-opts input[type="checkbox"]')
        self.assertIn("accent-color: var(--brand-blue)", box)

    def test_the_id_is_bold_mono_violet_and_the_priority_pill_has_a_border(self):
        idr = rule(SHELL_CSS, ".wil-table td.wil-c-id, .wil-c-id")
        self.assertIn("monospace", idr)
        self.assertIn("font-weight: var(--weight-medium)", idr)
        self.assertIn("color: var(--status-blue-text)", idr)
        self.assertIn("border: 1px solid var(--grey-200)", rule(SHELL_CSS, ".wil-pr"))
        self.assertIn("border-color:", rule(SHELL_CSS, ".wil-pr.h, .wil-pr.u"))

    def test_the_heading_row_is_caption_size_caps(self):
        self.assertIn("font-size: var(--size-caption)", rule(SHELL_CSS, ".wil-table th"))

    def test_at_1100_and_below_the_owner_keeps_its_width_and_at_1000_the_date_stays_on_one_line(self):
        small = [ln for ln in SHELL_CSS.splitlines() if "width: 100px" in ln and ".wil-c-workstream" in ln][0]
        self.assertNotIn("wil-c-owner", small)
        m = re.search(r"@media \(max-width: 1000px\) \{(.*?)\n\}", SHELL_CSS[SHELL_CSS.index(".wil-c-due"):], re.S)
        self.assertIn("td.wil-c-due { white-space: nowrap", m.group(1))

    def test_no_bare_px_font_size_and_no_looping_animation_in_what_this_row_added(self):
        for css in (EDIT_CSS, SHELL_CSS):
            for ln in css.splitlines():
                if ".wil-add" in ln or ".wil-cfg .wil-" in ln or ".wil-views" in ln:
                    self.assertNotRegex(ln, r"font-size:\s*\d+px")
                    self.assertNotIn("infinite", ln)


class EveryAddedRuleIsPinned(unittest.TestCase):
    """Row 1195: each rule line this row added must stay exactly as drawn (a colour token, a selector, a size, a breakpoint): a changed or dropped declaration fails here."""

    def test_every_added_rule_line_is_present_as_written(self):
        def norm(s):
            return re.sub(r"\s+", " ", re.sub(r"/\*.*?\*/", "", s)).strip()
        for name, css in (("edit.css", EDIT_CSS), ("shell.css", SHELL_CSS)):
            have = {norm(ln) for ln in css.splitlines()}
            for want in GOLDEN_LINES[name]:
                self.assertIn(want, have, name)


class InThePage(T.InThePage):
    def test_edit_draws_tabs_then_filter_then_table_with_the_gear_in_the_title_row_and_the_plus_square(self):
        ref = self.add({"mode": "all", "columns": ["id", "owner", "due", "priority"], "owner": ["Pat Demo", "Lee Demo"]})
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
                tiles = p.js(f"[...document.querySelectorAll('{sec} .wil-add .ddmenu .mtile')].map(e => e.textContent).join('')")
                self.assertEqual(tiles, "ARID")
                self.assertEqual(p.js(f"Math.round(document.querySelector('{sec} .wil-add .newb').getBoundingClientRect().width)"), 34, "open: still the square")

    def test_the_table_cells_the_id_priority_owner_and_due_at_900(self):
        ref = self.add({"mode": "all", "columns": ["id", "owner", "due", "priority"], "owner": ["Pat Demo", "Lee Demo"]})
        with T.chrome() as cdp:
            p = self.show(cdp, 900)
            sec = f'[data-id="{ref}"]'
            p.edit()
            p.until(f"!!document.querySelector('{sec} .wil-table td.wil-c-id')", "drew")
            idc = json.loads(p.js(f"JSON.stringify((() => {{ const s = getComputedStyle(document.querySelector('{sec} .wil-table td.wil-c-id')); return [s.fontFamily, s.fontWeight, s.color]; }})())"))
            self.assertIn("monospace", idc[0])
            self.assertEqual(idc[1], "600")
            vio = p.js("(() => { const e = document.createElement('i'); e.style.color = getComputedStyle(document.documentElement).getPropertyValue('--status-blue-text'); document.body.append(e); const c = getComputedStyle(e).color; e.remove(); return c; })()")
            self.assertEqual(idc[2], vio)
            self.assertNotEqual(p.js(f"getComputedStyle(document.querySelector('{sec} .wil-pr')).borderTopWidth"), "0px")
            own = json.loads(p.js(f"JSON.stringify([...document.querySelectorAll('{sec} .wil-table td.wil-c-owner .nm')].map(e => [e.scrollWidth, e.clientWidth]))"))
            for sw, cw in own:
                self.assertLessEqual(sw, cw, "an owner name is not cut")
            due = json.loads(p.js(f"JSON.stringify([...document.querySelectorAll('{sec} .wil-table td.wil-c-due .num')].map(e => e.getClientRects().length))"))
            for n in due:
                self.assertEqual(n, 1, "a date is on one line")


if __name__ == "__main__":
    unittest.main()
