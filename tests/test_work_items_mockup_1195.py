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
