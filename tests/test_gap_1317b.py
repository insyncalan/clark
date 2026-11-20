"""Row 1317 follow-up: the Classic Projects table, header weight 600 muted with a 1px --grey-200 rule under it (prototype settings.css:141, --line),
body cells a 1px --grey-100 rule under each (settings.css:142, --line2) and none above; Cards keeps its own look. Chrome is required.

Run: python3 dev/run_tests.py test_gap_1317b
"""
import unittest

from test_server import chrome  # noqa: F401  (names the file as a browser test; the page comes from the base class)
from test_theme_classic_1317 import RealSettings as Base

PROBE_TOKENS = """(() => { const q = (s) => document.querySelector(s), g = (e, p) => getComputedStyle(e)[p];
  const tok = (v) => { const i = document.createElement('i'); i.style.borderBottomColor = v; document.body.appendChild(i); const r = getComputedStyle(i).borderBottomColor; i.remove(); return r; };
  const th = q('#projects-table th'), td = q('#projects-table tbody td:not(.acts)');
  return { thColor: g(th, 'color'), muted: tok('var(--text-muted)'), thBw: g(th, 'borderBottomWidth'), thBc: g(th, 'borderBottomColor'), line: tok('var(--grey-200)'),
    tdBw: g(td, 'borderBottomWidth'), tdBc: g(td, 'borderBottomColor'), line2: tok('var(--grey-100)'), tdTop: g(td, 'borderTopWidth'), tdPad: g(td, 'padding'), thWeight: g(th, 'fontWeight') }; })()"""


class Gap1317b(__import__("test_theme_classic_1317").RealSettings):
    def test_classic_projects_header_and_cell_rules(self):
        from test_theme_classic_1317 import NAME
        import test_theme_classic_1317 as m
        orig = m.PROBE
        m.PROBE = "(() => Object.assign(" + orig + ", " + PROBE_TOKENS + "))()"
        try:
            for tag, c in self.each(NAME):
                self.assertEqual((c["thWeight"], c["thColor"]), ("600", c["muted"]), tag + ": weight 600, muted")
                self.assertEqual(c["thBw"], "1px", tag + ": rule under the header")
                self.assertEqual(c["thBc"], c["line"], tag + ": header rule is --line (grey-200)")
                self.assertEqual(c["tdBw"], "1px", tag + ": rule under each body cell")
                self.assertEqual(c["tdBc"], c["line2"], tag + ": cell rule is --line2 (grey-100)")
                self.assertEqual(c["tdTop"], "0px", tag + ": no rule above a body cell")
                self.assertEqual(c["tdPad"], "8px 10px 8px 0px", tag)
        finally:
            m.PROBE = orig


del Base
if __name__ == "__main__":
    unittest.main()
