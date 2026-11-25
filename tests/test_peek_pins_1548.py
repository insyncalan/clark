"""Row 1548 (v1.3), Tech Debt, follow-up to 1285: the Latest update block of the peeks, pinned at 1400 and 900 px (Classic, light):
the label "Latest update" (.pk-lab) is weight 700, the client value (.pk-latest-client) is the muted grey, and the empty-box text is ONE exported
constant (LATEST_PLACEHOLDER in PeekLatest.jsx) that the work item peek and the milestone peek both use.
Run: python3 dev/run_tests.py test_peek_pins_1548
"""
import re
import unittest
from unittest import mock

import _testpage
import test_peek_latest
import test_server  # noqa: F401  (a test that drives Chrome carries this import)
from _paths import SRC
from clark import page, theme as themes
import test_movement_page
from test_server import chrome

EDIT = SRC / "clark" / "page" / "src" / "edit"
PEEK_LATEST = (EDIT / "PeekLatest.jsx").read_text(encoding="utf-8")
MILESTONE_PEEK = (EDIT / "MilestonePeek.jsx").read_text(encoding="utf-8")
TEXT = "What changed? Add the latest update…"
CONSTANT = re.search(r'export const (\w+) = "([^"]*)";', PEEK_LATEST)
_B = test_peek_latest.Browser


class Pins(unittest.TestCase):
    load = _B.load
    _base_setup = _B.setUp

    def setUp(self):
        self._base_setup()
        real = _testpage.html          # Classic layered on, as the served page draws it (row 1576: the client value's colour is a Classic rule)
        p = mock.patch.object(_testpage, "html", lambda branding=None: page.layer_theme(real(), themes.css("prototype-2.0")))
        p.start()
        self.addCleanup(p.stop)
    fresh, refused, kinds, action = _B.fresh, _B.refused, _B.kinds, _B.action
    HOLD = _B.HOLD

    def test_the_latest_label_weight_is_700(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, "TUL-A-002", edit=True)
                self.assertEqual(cdp.js("getComputedStyle(document.querySelector('#peek .pk-lab')).fontWeight", sid), "700")

    def test_the_client_value_is_the_muted_grey(self):
        shown, _internal = self.kinds()
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, shown, edit=True)
                self.assertEqual(cdp.js("getComputedStyle(document.querySelector('#peek [data-pk-latest-client]')).color", sid), "rgb(85, 103, 122)")       # row 1576: #55677A

    def test_the_latest_placeholder_is_defined_once(self):
        self.assertIsNotNone(CONSTANT, "PeekLatest.jsx exports the placeholder constant")
        self.assertEqual(CONSTANT.group(2), TEXT)
        self.assertEqual(PEEK_LATEST.count(TEXT), 1, "the text is written once in PeekLatest.jsx")
        self.assertNotIn(TEXT, MILESTONE_PEEK, "MilestonePeek.jsx has no text of its own")
        self.assertNotRegex(MILESTONE_PEEK, r"placeholder=\"")


class MilestonePins(test_movement_page.Base):
    def test_the_milestone_peek_shows_the_shared_placeholder(self):
        for width in (1400, 900):
            with self.subTest(width=width, peek="milestone"), chrome() as cdp:
                from test_report_editor import Pg
                self.cur = test_movement_page.PILOT
                p = Pg.at(self, cdp, self.s.port, f"#milestones&p=ABC&ms={test_movement_page.PILOT}")
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                p.until("!!document.querySelector('#peek [data-pk-latest]')", "the milestone peek drew the box")
                self.assertEqual(p.js("document.querySelector('#peek [data-pk-latest] [data-rich] .quiet').textContent"), TEXT)


class WorkItemPins(unittest.TestCase):
    load, setUp, fresh, refused, HOLD = _B.load, _B.setUp, _B.fresh, _B.refused, _B.HOLD

    def test_both_peeks_use_the_shared_placeholder(self):
        name = CONSTANT.group(1)
        self.assertIn(f"placeholder = {name}", PEEK_LATEST, "the box defaults to the constant")
        self.assertNotRegex(MILESTONE_PEEK, r"placeholder=\"", "the milestone peek has no text of its own")
        seen = []
        for width in (1400, 900):
            for ref in ("TUL-A-002", "TUL-007", "TUL-010"):
                with self.subTest(width=width, ref=ref), chrome() as cdp:
                    sent, sid = self.load(cdp, width, ref, edit=True)
                    seen.append(cdp.js("(e => e ? e.textContent : '')(document.querySelector('#peek [data-pk-lbox] .rt-view .quiet'))", sid))
        self.assertIn(TEXT, seen, "an empty work item box shows the constant")
        self.assertLessEqual(set(seen) - {""}, {TEXT})


del _B      # a name left here would make the runner collect the whole Browser class again


if __name__ == "__main__":
    unittest.main()
