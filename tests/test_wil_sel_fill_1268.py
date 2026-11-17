"""Row 1268, mutation killers: in Edit, at half width, each field box of the Work items list fills its label cell and ends inside it
(the Configure box and the form), at 1400 and 900 px.
Run: CLARK_CHROME=/usr/local/bin/creaite-chrome python3 dev/run_tests.py test_wil_sel_fill_1268.py"""
import json
import unittest

import test_tpl_workitems as base
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome

PROBE = """(ref => { const sec = document.querySelector('[data-id="' + ref + '"]'), out = [];
  for (const e of sec.querySelectorAll('.wil-sel select, .wil-sel input')) { const b = e.getBoundingClientRect(), l = e.closest('.wil-sel').getBoundingClientRect();
    if (b.width < 1) continue; out.push([e.tagName + ':' + (e.closest('.wil-sel').dataset.field || ''), Math.round(l.width - b.width), Math.round(b.right - l.right), Math.round(b.left - l.left)]); }
  return out; })"""


class SelFill(base.PageBase):
    add, show = base.InThePage.add, base.InThePage.show

    def setUp(self):
        super().setUp()
        base.plant(self)
        with self.store.step("dashboard", base.USER) as st:
            text = st.create("report_sections", {"project": "ABC", "type": "text", "title": "Fictional notes", "sort_order": 1})
        self.ref = self.add({"mode": "all", "columns": ["id", "owner", "due", "status", "priority"], "max": 2}, after=text, beside=1)

    def test_each_field_box_fills_its_cell_and_ends_inside_it_at_half_width(self):
        for width in (1400, 900, 600, 400, 320):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                p.edit()
                p.until(f"!!document.querySelector('[data-id=\"{self.ref}\"] [data-wil-gear]')", "the list drew")
                p.js(f"(() => {{ const g = document.querySelector('[data-id=\"{self.ref}\"] [data-wil-gear]'); if (g.getAttribute('aria-expanded') !== 'true') g.click(); }})()")
                p.until(f"!document.querySelector('[data-id=\"{self.ref}\"] .wil-cfg').hidden", "the Configure box opened")
                got = json.loads(p.js(f"JSON.stringify(({PROBE})({json.dumps(self.ref)}))"))
                self.assertTrue(got, "there are field boxes")
                for name, gap, over, left in got:
                    self.assertEqual((gap, over, left), (0, 0, 0), f"{name} at {width}: {got}")


if __name__ == "__main__":
    unittest.main()
