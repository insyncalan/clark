"""Issue 1016: the work item peek's top section is tighter vertically, without being cluttered.

Run: python3 dev/run_tests.py test_peek_spacing_1016

Measured in a real browser in Edit at 1400 and 900 px, light and dark. The four cells are shorter (a padding step less above and below),
the gap between the last field and the "Needed from the client" switch is one step smaller, the switch and Latest update sit closer, and
the empty "Add the latest update" area is shorter. Ranges, not exact numbers: every box keeps a floor (a touch target is 44 px or more, gaps
never close up) and a ceiling that the old, looser spacing exceeded. Edit only: the published page's own rules are not read here.
"""
import json
import unittest

from _paths import ROOT

import test_peek as tp  # noqa: E402
from test_peek_card import CardBrowser  # noqa: E402
from test_server import chrome  # noqa: E402

READ = """(() => { const p = document.querySelector('#peek');
  const b = (e) => { if (!e) return null; const r = e.getBoundingClientRect(); return { t: r.top, b: r.bottom, h: r.height }; };
  const cells = {}; for (const k of ['status', 'priority', 'owner', 'due']) { const e = p.querySelector('.pk-fields > [data-row=' + k + ']'); if (e) cells[k] = b(e); }
  const rows = [...p.querySelectorAll('.pk-fields > .pk-row:not([data-row])')].map(b);
  return { cells, lastRow: rows[rows.length - 1], act: b(p.querySelector('.pk-act')), latest: b(p.querySelector('.pk-latest')), lab: b(p.querySelector('.pk-lab')),
    text: b(p.querySelector('.pk-latest-text')), stamp: b(p.querySelector('.pk-last')), body: b(p.querySelector('.pk-body')) }; })()"""


class Spacing(unittest.TestCase):
    setUpClass = tp.Browser.__dict__["setUpClass"]
    tearDownClass = tp.Browser.__dict__["tearDownClass"]
    load_page = tp.Browser.load_page
    edit_mode = tp.Browser.edit_mode
    ids_on_page = tp.Browser.ids_on_page
    show_item = CardBrowser.show_item

    def test_the_top_section_is_tighter_and_not_cramped(self):
        for width in (1400, 900):
            with chrome() as cdp:
                s, sid = self.load_page(cdp, width)
                item = self.ids_on_page(cdp, sid)[0]
                self.edit_mode(cdp, sid)
                for theme in ("light", "dark"):
                    cdp.js(f"document.documentElement.dataset.theme = {json.dumps(theme)}", sid)
                    self.show_item(cdp, sid, item)
                    g = cdp.js(READ, sid)
                    where = f"{width} {theme}"
                    with self.subTest(where):
                        for k, c in g["cells"].items():
                            lo, hi = (48, 68) if width == 1400 and k in ("status", "priority") else (48, 88)
                            self.assertGreaterEqual(c["h"], lo, f"{where} {k}: not cramped")
                            self.assertLessEqual(c["h"], hi, f"{where} {k}: tighter than the old 74.5 / 93")
                        self.assertTrue(4 <= g["act"]["t"] - g["lastRow"]["b"] <= 10, f"{where}: last field to the switch")
                        self.assertGreaterEqual(g["act"]["h"], 40, f"{where}: the switch keeps its touch height")
                        self.assertTrue(4 <= g["latest"]["t"] - g["act"]["b"] <= 10, f"{where}: switch to Latest update")
                        self.assertTrue(4 <= g["lab"]["t"] - g["latest"]["t"] <= 14, f"{where}: rule to the label")
                        self.assertTrue(44 <= g["text"]["h"] <= 56, f"{where}: the empty Latest update area, {g['text']['h']}")
                        self.assertTrue(2 <= g["stamp"]["t"] - g["text"]["b"] <= 5, f"{where}: area to Last updated")
                        self.assertLessEqual(g["body"]["h"], 690 if width == 1400 else 625, f"{where}: the whole section, {g['body']['h']}")
                cdp.js("document.documentElement.dataset.theme = 'light'", sid)


if __name__ == "__main__":
    unittest.main()
