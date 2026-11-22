"""Row 1399 (Use cases rows audit, Classic only): computed styles at 1400 and 900, light and dark.
Run: python3 dev/run_tests.py test_use_cases_rows_1399
Spec: cell padding 6px 12px, hover F3F5FB (dark keeps the Theme grey), title weight 500, reference as a chip (1px 8794B3, radius 4, padding 2px 8px, 13px 500),
no progress bar under the next steps, view tabs 15px with padding 6px 8px. In a grouped card the cells are 6px 4px (ticket 1399 row 1)."""
import unittest

from _new_page import reload_to_new_page
from clark import theme
from test_report_editor import Base, tearDownModule  # noqa: F401
from test_server import chrome
from test_use_cases_redesign_1325 import Redesign

PROBE = """(() => {
  const q = (s) => document.querySelector(s), cs = (e) => getComputedStyle(e);
  const row = q('#usecases tbody tr[data-uc]'), td = row.querySelector('td.c-where'), item = row.querySelector('td.c-item');
  const ref = row.querySelector('.ucl-ref'), t = row.querySelector('.ucl-go'), prg = row.querySelector('.prg'), tab = q('#usecases .ucl-views .vtab');
  const c = cs(ref), p = cs(td), v = cs(tab);
  return { pad: [p.paddingTop, p.paddingRight, p.paddingBottom, p.paddingLeft], minH: Math.round(row.getBoundingClientRect().height),
    title: cs(t).fontWeight, chip: [c.borderTopWidth, c.borderTopStyle, c.borderTopColor, c.borderTopLeftRadius, c.paddingTop, c.paddingRight, c.fontSize, c.fontWeight, c.display],
    prg: prg ? cs(prg).display : 'none-in-dom-absent', tab: [v.fontSize, v.paddingTop, v.paddingRight, v.paddingBottom, v.paddingLeft],
    itemPad: cs(item).paddingLeft, rowBox: row.getBoundingClientRect().top }; })()"""
HOVER = "(() => { const r = document.querySelectorAll('#usecases tbody tr[data-uc]')[1]; return getComputedStyle(r).backgroundColor; })()"


class Rows:
    css = theme.css("prototype-2.0")

    def test_rows_match_the_prototype(self):
        for w in (1400, 900):
            for mode in ("light", "dark"):
                with self.subTest(width=w, mode=mode), chrome() as cdp:
                    p = self.open_page(cdp, w)
                    p.js(f"document.documentElement.setAttribute('data-theme', '{mode}')")
                    g = p.js(PROBE)
                    self.assertEqual(g["pad"], ["6px", "12px", "6px", "12px"], "cell padding")
                    self.assertGreaterEqual(g["minH"], 40, "min-height 40 (the fixture rows hold two lines, so this one is natural height)")
                    self.assertEqual(g["title"], "500", "title weight")
                    ring = "rgb(135, 148, 179)" if mode == "light" else None
                    self.assertEqual(g["chip"][:2] + g["chip"][3:], ["1px", "solid", "4px", "2px", "8px", "13px", "500", "inline-block"], "reference chip")
                    if ring:
                        self.assertEqual(g["chip"][2], ring, "chip ring 8794B3")
                    self.assertEqual(g["prg"], "none", "no progress bar")
                    self.assertEqual(g["tab"], ["15px", "6px", "8px", "6px", "8px"], "view tabs")
                    r = p.js("(() => { const b = document.querySelectorAll('#usecases tbody tr[data-uc]')[1].getBoundingClientRect(); return [b.left + 20, b.top + b.height / 2]; })()")
                    cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": r[0], "y": r[1]}, p.sid)
                    want = "rgb(243, 245, 251)" if mode == "light" else "rgb(34, 46, 66)"
                    p.until("getComputedStyle(document.querySelectorAll('#usecases tbody tr[data-uc]')[1]).backgroundColor === '%s'" % want, "the hover tint")
                    bg = p.js(HOVER)
                    if mode == "light":
                        self.assertEqual(bg, "rgb(243, 245, 251)", "hover F3F5FB")
                    else:
                        self.assertEqual(bg, "rgb(34, 46, 66)", "dark hover keeps the Theme grey")


    def test_a_one_line_row_is_exactly_40_high(self):
        """Ticket 1399 row 1: min-height 40. The fixture rows hold two lines (title and reference) and are 60, so each cell is cut to one short word here (buttons too) and the row must measure exactly 40."""
        for w in (1400, 900):
            for mode in ("light", "dark"):
                with self.subTest(width=w, mode=mode), chrome() as cdp:
                    p = self.open_page(cdp, w)
                    p.js(f"document.documentElement.setAttribute('data-theme', '{mode}')")
                    h = p.js("""(() => { const rows = [...document.querySelectorAll('#usecases tbody tr[data-uc]')];
                      for (const r of rows) for (const td of r.querySelectorAll('td')) td.textContent = 'x';
                      return rows.map((r) => r.getBoundingClientRect().height); })()""")
                    self.assertEqual(h, [40.0] * len(h), "every one-line row is exactly 40 high")

    def test_grouped_card_cells_are_6px_4px(self):
        """Ticket 1399 row 1: 6px 12px inside the box, 6px 4px in a grouped card; the same two-line rows stay as high as before."""
        for w in (1400, 900):
            with self.subTest(width=w), chrome() as cdp:
                p = self.open_page(cdp, w, ready="true")
                p.js("localStorage.setItem('clark.ucPage', JSON.stringify({ABC: {line: '', tab: 'all', group: 'status', sort: 'status'}}))")
                reload_to_new_page(p.js, "document.querySelectorAll('#usecases .ucl-group tr[data-uc]').length > 0", "grouped by Status")
                g = p.js("""(() => { const out = [];
                  for (const row of document.querySelectorAll('#usecases .ucl-group tr[data-uc]')) for (const td of row.children) { const c = getComputedStyle(td); out.push([c.paddingTop, c.paddingRight, c.paddingBottom, c.paddingLeft].join(' ')); }
                  return { pads: [...new Set(out)] }; })()""")
                self.assertEqual(g["pads"], ["6px 4px 6px 4px"], "grouped card cell padding")


class Classic(Rows, Redesign, Base):
    pass


if __name__ == "__main__":
    unittest.main()
