"""Row 1357 items 2, 6 and 9 (Use cases page, Classic only), values read from the prototype's usecases.css:
item 2 Group by / Sort by: 1px line in the prototype's --ui (this theme's --grey-500), 6px corners, 28px high (usecases.css:10);
item 6 the status pill: 13px, weight 600 (usecases.css:73); item 9 the left rule has border-radius 0.

Run: cd tests && PYTHONPATH=../src python3 -m unittest test_classic_uc_1357_items
Chrome at 1400 and 900 px (fictional data). Page words: none new.
"""
import unittest

from test_server import chrome

import test_use_cases_list as ucl

PROBE = """(() => { const g = id => { const e = document.getElementById(id); const c = getComputedStyle(e);
    return { fw: c.fontWeight, w: c.borderTopWidth, s: c.borderTopStyle, col: c.borderTopColor, r: c.borderTopLeftRadius, h: e.getBoundingClientRect().height }; };
  const pill = document.querySelector('#usecases .pill'); const pc = pill ? getComputedStyle(pill) : null;
  const rule = getComputedStyle(document.querySelector('.frame.ucl'));
  const ref = document.createElement('i'); ref.style.color = 'var(--grey-500)'; document.body.appendChild(ref); const grey = getComputedStyle(ref).color; ref.remove();
  return { group: g('ucl-group'), sort: g('ucl-sort'), grey, pill: pc && { size: pc.fontSize, weight: pc.fontWeight, h: pill.getBoundingClientRect().height, lh: pc.lineHeight, pl: pc.paddingLeft, pr: pc.paddingRight },
    add: (() => { const a = document.getElementById('ucAddPage'); return { h: a.getBoundingClientRect().height, r: getComputedStyle(a).borderTopLeftRadius }; })(),
    vnewR: getComputedStyle(document.getElementById('ucl-viewNew')).borderTopLeftRadius,
    rule: { r: rule.borderTopLeftRadius, rb: rule.borderBottomLeftRadius, left: rule.borderLeftWidth } }; })()"""


class App(ucl.Setup):
    THEME = "prototype-2.0"

    def got(self, width):
        with chrome() as cdp:
            p = self.show(cdp, width=width, dark=False)
            return p.js(PROBE)

    def test_item_2_group_and_sort_buttons_have_the_prototype_line(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                g = self.got(width)
                for k in ("group", "sort"):
                    self.assertEqual((g[k]["w"], g[k]["s"], g[k]["r"]), ("1px", "solid", "6px"), f"{width} {k}")
                    self.assertEqual(g[k]["col"], g["grey"], f"{width} {k} line colour is --grey-500")
                    self.assertEqual(g[k]["h"], 28, f"{width} {k} exactly 28 px high")
                self.assertEqual(g["add"]["h"], 28, f"{width} Add exactly 28 px high")
                self.assertEqual(g["add"]["r"], "6px", f"{width} Add 6px corners")

    def test_item_2_weight_500_and_new_view_radius_6(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                g = self.got(width)
                for k in ("group", "sort"):
                    self.assertEqual(g[k]["fw"], "500", f"{width} {k} weight 500 (usecases.css line 10)")
                self.assertEqual(g["vnewR"], "6px", f"{width} + New view 6px corners")

    def test_item_6_pill_is_20px_high(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                p = self.got(width)["pill"]
                self.assertEqual((p["h"], p["lh"], p["pl"], p["pr"], p["size"], p["weight"]), (20, "20px", "10px", "10px", "13px", "600"), "usecases.css line 73: box 20 high, line-height 20, padding 0 10, 13px/600")

    def test_item_9_left_rule_square_in_dark_at_900_and_1400(self):
        for width in (900, 1400):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width=width, dark=True)
                g = p.js(PROBE)
                self.assertEqual(g["rule"]["left"], "2px")
                self.assertEqual((g["rule"]["r"], g["rule"]["rb"]), ("0px", "0px"))

    def test_item_6_pill_is_13px_weight_600(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                g = self.got(width)
                self.assertIsNotNone(g["pill"], "the list shows a status pill")
                self.assertEqual((g["pill"]["size"], g["pill"]["weight"]), ("13px", "600"))

    def test_item_9_left_rule_has_square_corners(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                g = self.got(width)
                self.assertEqual(g["rule"]["left"], "2px", "the left rule is there")
                self.assertEqual((g["rule"]["r"], g["rule"]["rb"]), ("0px", "0px"))


if __name__ == "__main__":
    unittest.main()
