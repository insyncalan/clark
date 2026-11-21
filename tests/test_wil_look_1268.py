"""Row 1268, items 9 and 14: the one-line row of a Work items list and the filter box without a focus ring, Classic only.

Run: python3 dev/run_tests.py test_wil_look_1268
Browser tier, 1400 and 900 only. Both hold on main already (shell.css .wil-c-title; no focus rule on .fline), so these are pins, measured in the served Classic page with getComputedStyle.
The mock-up row (.row min-height 48 with a 1px rule, .ttl nowrap with an ellipsis) is the measure: letter tile, title, owner, date, priority, ID, on one line.
"""
import json

import test_server  # noqa: F401  the browser harness (a Chrome file names it, so the tier reads this one as browser)
import test_tpl_workitems as T
from test_work_items_mockup_1195 import Look

LONG = "A very long title that runs past any column so that the row must cut it with an ellipsis instead of growing a second line " * 3


class OneLine(Look):
    def test_a_long_title_is_cut_with_an_ellipsis_and_the_row_keeps_the_one_line_height_at_1400_and_900(self):
        self.demo.action(description=LONG, owner="Pat Demo", due_date="2030-01-10", priority="High")
        ref = self.add({"mode": "all", "columns": ["id", "owner", "due", "priority"], "owner": ["Pat Demo", "Lee Demo"]})
        for width in (1400, 900):
            with T.chrome() as cdp:
                p = self.show(cdp, width)
                sec = f'[data-id="{ref}"]'
                p.until(f"document.querySelectorAll('{sec} .wil-table tbody tr').length > 1", "drew")
                got = json.loads(p.js("JSON.stringify((() => { const rows = [...document.querySelectorAll('" + sec + " .wil-table tbody tr')];"
                    "const long = rows.find(r => r.querySelector('.wil-c-title').textContent.startsWith('A very long')), t = long.querySelector('.wil-c-title'), s = getComputedStyle(t);"
                    "const h = rows.map(r => Math.round(r.getBoundingClientRect().height)), tile = long.querySelector('.wil-c-tile .ico').getBoundingClientRect();"
                    "return {ws: s.whiteSpace, to: s.textOverflow, ov: s.overflow, cut: t.scrollWidth > t.clientWidth, heights: h, tile: [Math.round(tile.width), Math.round(tile.height)],"
                    "cells: [...long.children].map(c => c.className.split(' ').find(x => x.startsWith('wil-c-'))).join()}; })())"))
                self.assertEqual((got["ws"], got["to"], got["ov"]), ("nowrap", "ellipsis", "hidden"), (width, got))
                self.assertTrue(got["cut"], (width, "the long title is cut, not wrapped", got))
                self.assertEqual(len(set(got["heights"])), 1, (width, "the long row is as high as the short rows", got))
                self.assertTrue(48 <= got["heights"][0] <= 50, (width, "the mock-up .row: min-height 48 plus its 1px rule", got))
                self.assertEqual(got["tile"], [28, 28], (width, got))
                self.assertEqual(got["cells"], "wil-c-tile,wil-c-title,wil-c-owner,wil-c-due,wil-c-priority,wil-c-id", (width, got))


class FilterNoRing(Look):
    def test_the_filter_box_shows_no_outline_and_no_shadow_ring_when_focused_at_1400_and_900(self):
        ref = self.add({"mode": "all", "columns": ["id", "owner", "due", "priority"], "owner": ["Pat Demo"]})
        for width in (1400, 900):
            with T.chrome() as cdp:
                p = self.show(cdp, width)
                sec = f'[data-id="{ref}"]'
                p.edit()
                p.until(f"!!document.querySelector('{sec} .fline input')", "drew")
                p.js(f"document.querySelector('{sec} .fline input').focus()")
                got = json.loads(p.js("JSON.stringify((() => { const i = document.activeElement, f = i.closest('.fline'), a = getComputedStyle(i), b = getComputedStyle(f);"
                    "return {on: i.matches('.fline input') && i.matches(':focus'), inOutline: a.outlineStyle, inShadow: a.boxShadow, boxOutline: b.outlineStyle, boxShadow: b.boxShadow, line: b.borderBottomStyle}; })())"))
                self.assertTrue(got["on"], got)
                self.assertEqual((got["inOutline"], got["inShadow"], got["boxOutline"], got["boxShadow"]), ("none", "none", "none", "none"), (width, got))
                self.assertEqual(got["line"], "solid", (width, "the underline stays", got))


class NewListOrder(Look):
    def test_a_new_classic_list_draws_owner_due_priority_id_and_no_type_at_1400_and_900(self):
        ref = self.add(json.loads(T.wi.START))
        for width in (1400, 900):
            with T.chrome() as cdp:
                p = self.show(cdp, width)
                p.until(f"!!document.querySelector('[data-id=\"{ref}\"] .wil-table th')", "drew")
                self.assertEqual(p.js(f"[...document.querySelectorAll('[data-id=\"{ref}\"] .wil-table th')].map(e => e.textContent)"), ["", "Item", "Owner", "Due", "Priority", "ID"], width)
