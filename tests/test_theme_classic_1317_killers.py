"""Row 1317 (Projects card, Classic Theme) killers: Add project's text is the on-brand colour, and the header rule reaches only the Projects table.

Run: python3 dev/run_tests.py test_theme_classic_1317_killers
Mutants killed (rules.css): the colour line of the Add project rule removed, and the header selector widened from table.proj-table to any table
inside the card. 1400 and 900 px, light and dark. Fails, never skips, without Chrome.
"""
import unittest

from _paths import ROOT  # noqa: F401
from test_server import chrome
from test_theme_classic_1317 import SIZES, Projects
from test_theme_classic_css import rgb


class Killers(unittest.TestCase):
    load = Projects.load

    def test_add_project_text_is_the_on_brand_colour(self):
        with chrome() as cdp:
            for scheme in ("light", "dark"):
                for w in SIZES:
                    got, sid = self.load(cdp, w, scheme, "prototype-2.0")
                    want = cdp.js("getComputedStyle(document.documentElement).getPropertyValue('--text-on-brand').trim()", sid)
                    self.assertEqual(got["fg"], rgb(want), f"classic {scheme} {w}")

    def test_another_table_in_the_card_keeps_its_tracked_capitals(self):
        with chrome() as cdp:
            for theme in ("prototype-2.0", None):
                for scheme in ("light", "dark"):
                    for w in SIZES:
                        got, sid = self.load(cdp, w, scheme, theme)
                        cdp.js("""(() => { const t = document.createElement('table'); t.className = 'items';
                            t.innerHTML = '<thead><tr><th id="oth" scope="col">Other</th></tr></thead>'; document.querySelector('.projects').appendChild(t); })()""", sid)
                        r = cdp.js("(() => { const s = getComputedStyle(document.getElementById('oth')); return [s.textTransform, s.letterSpacing]; })()", sid)
                        self.assertEqual(r[0], "uppercase", f"{theme} {scheme} {w}")
                        self.assertNotEqual(r[1], "normal", f"{theme} {scheme} {w}")


if __name__ == "__main__":
    unittest.main()
