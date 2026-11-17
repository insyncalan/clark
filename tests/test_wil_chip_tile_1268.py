"""Row 1268, mutation killers: the Priority chip of a Work items row is coloured by its word (Urgent red, High amber, others grey), and the
letter tile of a row is a picture for the eye only (hidden from the reader, not a keyboard stop), in View and in Edit.
Run: CLARK_CHROME=/usr/local/bin/creaite-chrome python3 dev/run_tests.py test_wil_chip_tile_1268.py"""
import json
import unittest

import test_tpl_workitems as base
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome

PROBE = """(ref => { const sec = document.querySelector('[data-id="' + ref + '"]'), chips = {}, tiles = [];
  for (const e of sec.querySelectorAll('.wil-table td .wil-pr')) chips[e.textContent] = [e.className.replace('wil-pr', '').trim(), getComputedStyle(e).backgroundColor];
  for (const e of sec.querySelectorAll('.wil-table td.wil-c-tile .ico, .wil-lines .wil-tile .ico')) tiles.push([e.getAttribute('aria-hidden'), e.getAttribute('role'), e.getAttribute('tabindex'), e.hasAttribute('data-tip')]);
  return JSON.stringify({chips: chips, tiles: tiles, lines: sec.querySelectorAll('.wil-lines li').length, lineTiles: sec.querySelectorAll('.wil-lines li > .wil-tile > .ico').length, rows: sec.querySelectorAll('.wil-table tbody tr').length, rowTiles: sec.querySelectorAll('.wil-table tbody tr > td.wil-c-tile > .ico').length}); })"""


class ChipTile(base.PageBase):
    add, show = base.InThePage.add, base.InThePage.show

    def setUp(self):
        super().setUp()
        base.plant(self)
        self.demo.action(description="Fix the urgent thing", owner="Pat Demo", due_date="2030-02-01", priority="Urgent")
        self.demo.action(description="Fix the low thing", owner="Pat Demo", due_date="2030-02-02", priority="Low")
        with self.store.step("dashboard", base.USER) as st:
            text = st.create("report_sections", {"project": "ABC", "type": "text", "title": "Fictional notes", "sort_order": 1})
        self.ref = self.add({"mode": "all", "columns": ["id", "owner", "due", "status", "priority"], "max": 20}, after=text, beside=1)

    def test_priority_chip_colour_follows_its_word_and_the_tile_is_not_a_keyboard_stop(self):
        with chrome() as cdp:
            p = self.show(cdp, 1400)
            for mode in ("view", "edit"):
                if mode == "edit":
                    p.edit()
                p.until(f"document.querySelectorAll('[data-id=\"{self.ref}\"] .wil-table td .wil-pr').length > 2", "the chips drew")
                got = json.loads(p.js(f"({PROBE})({json.dumps(self.ref)})"))
                chips = got["chips"]
                self.assertEqual(chips["Urgent"][0], "u", f"{mode}: {chips}")
                self.assertEqual(chips["High"][0], "h", f"{mode}: {chips}")
                self.assertEqual(chips["Low"][0], "", f"{mode}: {chips}")
                self.assertEqual(len({chips["Urgent"][1], chips["High"][1], chips["Low"][1]}), 3, f"{mode}: {chips}")
                self.assertGreater(got["lines"], 2, f"{mode}: the half width lines drew")
                self.assertEqual(got["lineTiles"], got["lines"], f"{mode}: every half width line has its tile")
                self.assertEqual(got["rowTiles"], got["rows"], f"{mode}: every table row has its tile")
                self.assertTrue(got["tiles"], f"{mode}: tiles drew")
                for tile in got["tiles"]:
                    self.assertEqual(tile, ["true", None, None, False], f"{mode}: {got['tiles']}")


if __name__ == "__main__":
    unittest.main()
