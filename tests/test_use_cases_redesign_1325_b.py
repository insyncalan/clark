"""Row 1325 slice B (Classic only): what the running page still missed against the ticket's design spec (comment 7006623019), measured at 1400 and 900.

Run: python3 dev/run_tests.py test_use_cases_redesign_1325_b
Chrome required (fails, never skips). Light mode. Design and format only; the prototype's words and example data are test content.
  Milestone label: 13px, --muted #475577, one line, ellipsis (base.css .mslab).
  Columns menu: 280px wide at 1400, 260px at 900, right-aligned under its button (extra.css .cols-menu).
  900 wide: Where 25%, Status 96px, Owner 88px (avatar only), Next steps 124px, Milestone / Commitment / Release / On the dashboard not drawn (extra.css media query).
Cards (no Theme) is pinned unchanged by test_use_cases_redesign_1325.CardsAsOnMain.
"""
import unittest

from test_server import chrome
from test_use_cases_redesign_1325 import Redesign, Base, theme

READ = """(() => {
  const q = (s) => document.querySelector(s), cs = (e) => getComputedStyle(e);
  const ms = q('#usecases tbody tr[data-uc]:not(.off) .mslab');
  const col = (v) => { const i = document.createElement('i'); i.style.color = v; document.body.appendChild(i); const c = cs(i).color; i.remove(); return c; };
  const w = (k) => Math.round(q('#usecases thead th.c-' + k).getBoundingClientRect().width);
  const t = q('#usecases table.items').getBoundingClientRect().width;
  return { ms: ms && [cs(ms).fontSize, cs(ms).color, cs(ms).whiteSpace, cs(ms).textOverflow, cs(ms).overflow], muted: col('#475577'),
    w: { where: w('where'), status: w('status'), owner: w('owner'), steps: w('steps') }, whereShare: w('where') / t,
    gone: ['ms', 'cm', 'rel', 'dash'].map((k) => { const h = q('#usecases thead th.c-' + k); return !h || h.getBoundingClientRect().width < 1; }) }; })()"""
MENU = """(() => { const m = document.querySelector('.cols-menu'), b = document.querySelector('#usecases button[aria-label=Columns]');
  if (!m) return null; const r = m.getBoundingClientRect(), br = b.getBoundingClientRect(); return [Math.round(r.width), Math.round(r.right) >= Math.round(br.right) - 1 && Math.round(r.right) <= innerWidth, r.left >= 0]; })()"""


class Slice:
    def test_milestone_label_is_13px_muted_one_line_with_ellipsis(self):
        for w in (1400, 900):
            if w == 900:
                continue   # the Milestone column is not drawn at 900
            with self.subTest(width=w), chrome() as cdp:
                p = self.open_page(cdp, w)
                g = p.js(READ)
                self.assertEqual(g["ms"], ["13px", g["muted"], "nowrap", "ellipsis", "hidden"])

    def test_900_wide_column_widths(self):
        with chrome() as cdp:
            p = self.open_page(cdp, 900)
            g = p.js(READ)
            self.assertEqual(g["gone"], [True, True, True, True], "Milestone, Commitment, Release, On the dashboard are not drawn")
            self.assertEqual((g["w"]["status"], g["w"]["owner"], g["w"]["steps"]), (96, 88, 124))
            self.assertAlmostEqual(g["whereShare"], 0.25, delta=0.01)

    def test_columns_menu_width(self):
        for w, want in ((1400, 280), (900, 260)):
            with self.subTest(width=w), chrome() as cdp:
                p = self.open_page(cdp, w)
                p.js("document.querySelector('#usecases button[aria-label=Columns]').click()")
                p.until("document.querySelector('.cols-menu')", "the chooser opened")
                m = p.js(MENU)
                self.assertEqual(m[0], want)
                self.assertEqual(m[1:], [True, True], "right-aligned under its button, on screen")


class Classic(Slice, Redesign, Base):
    css = theme.css("prototype-2.0")


if __name__ == "__main__":
    unittest.main()
