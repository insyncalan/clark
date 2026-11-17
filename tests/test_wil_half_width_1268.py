"""Row 1268: a Work items list at HALF width keeps its right edge. The list's scroll box, its rows and its foot end inside the section card
(nothing is cut at the card's right edge), in View and in Edit, at 1400 and 900 px, light and dark. Horizontal scroll inside the list is
not the fix: the scroll box itself must not scroll sideways, and the box that scrolls must be reachable by keyboard.
Run: CLARK_CHROME=/usr/local/bin/creaite-chrome python3 dev/run_tests.py test_wil_half_width_1268.py"""
import json
import unittest

import test_tpl_workitems as base
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome

MEASURE = """(ref => { const sec = document.querySelector('[data-id="' + ref + '"]'), card = sec.getBoundingClientRect(), box = sec.querySelector('[data-wil-scroll]'), out = {};
  out.slot = sec.className; out.cardScroll = sec.scrollWidth - sec.clientWidth; out.box = box.scrollWidth - box.clientWidth;
  out.boxRight = Math.round(box.getBoundingClientRect().right - card.right);
  out.cut = []; const clip = (e) => { for (let a = e.parentElement; a && a !== sec; a = a.parentElement) if (getComputedStyle(a).overflowX !== 'visible' && a.scrollWidth > a.clientWidth + 1) return a.className; return ''; };
  for (const e of sec.querySelectorAll('*')) { if (e.closest('.sec-ctl, [data-tip], .toast, .wil-cfg, .cols-menu, .vtabs')) continue; /* the saved-view tabs scroll in their own strip, by design: each tab is a keyboard stop */ const b = e.getBoundingClientRect();
    if (b.width > 1 && b.height > 1 && getComputedStyle(e).display !== 'none' && (b.right > card.right + 1 || b.left < card.left - 1)) out.cut.push(e.tagName + "." + e.className + (e.parentElement ? "<" + e.parentElement.tagName + "." + e.parentElement.className : "") + ' ' + Math.round(b.right - card.right)); }
  out.vis = [...sec.querySelectorAll('.wil-lines li')].filter(e => e.offsetParent).length; out.page = document.documentElement.scrollWidth - document.documentElement.clientWidth; return out; })"""


class HalfWidth(base.PageBase):
    add, show = base.InThePage.add, base.InThePage.show      # the helpers only: the neighbour's own tests are not run again here

    def setUp(self):
        super().setUp()
        base.plant(self)
        with self.store.step("dashboard", base.USER) as st:
            text = st.create("report_sections", {"project": "ABC", "type": "text", "title": "Fictional notes", "sort_order": 1})
        self.ref = self.add({"mode": "all", "columns": ["id", "owner", "due", "status", "priority"], "max": 2}, after=text, beside=1)

    def test_half_width_list_ends_inside_its_card_view_and_edit_1400_900_light_dark(self):
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark), chrome() as cdp:
                    p = self.show(cdp, width, dark)
                    for mode in ("view", "edit"):
                        if mode == "edit":
                            p.edit()
                        p.until(f"!!document.querySelector('[data-id=\"{self.ref}\"] [data-wil-scroll]') && document.querySelectorAll('[data-id=\"{self.ref}\"] .wil-lines li').length > 0", "the list drew")
                        got = p.js(f"({MEASURE})({json.dumps(self.ref)})")
                        where = f"{mode} {width} {'dark' if dark else 'light'}: {got}"
                        self.assertEqual(got["cut"], [], where)
                        self.assertLessEqual(got["box"], 0, "the list box scrolls sideways: " + where)
                        self.assertLessEqual(got["cardScroll"], 0, where)
                        self.assertLessEqual(got["boxRight"], 0, where)
                        self.assertLessEqual(got["page"], 0, where)

    def test_the_vertical_scroll_box_keeps_overscroll_contain_and_is_a_keyboard_stop(self):
        with chrome() as cdp:
            p = self.show(cdp, 1400)
            p.until(f"!!document.querySelector('[data-id=\"{self.ref}\"] [data-wil-scroll]')", "drew")
            got = p.js(f"(() => {{ const b = document.querySelector('[data-id=\"{self.ref}\"] [data-wil-scroll]'), c = getComputedStyle(b); return [c.overscrollBehaviorX, c.overscrollBehaviorY, b.tabIndex, b.scrollHeight > b.clientHeight]; }})()")
            self.assertEqual(got, ["auto", "contain", 0, True])


if __name__ == "__main__":
    unittest.main()
