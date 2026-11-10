"""Row 1078: the milestone peek is one flat list (no tiles), in the owner's order: Description, Agreed date, Forecast date, Achieved on (only
when the milestone is achieved), then the name, owner, state, progress, Workstream, Visible to client and Client wording. A client's
(read only) peek is the same list. Widths 1400 and 900 only.

Run: python3 dev/run_tests.py test_milestone_peek_1078
"""
import json
import unittest

from _demo import USER

from test_movement_page import GO_LIVE, PILOT, Base  # noqa: E402
import test_milestone_peek_828 as b828  # noqa: E402
from test_server import chrome  # noqa: E402

EDIT_ROWS = ["description", "baseline", "forecast", "name", "owner", "state", "progress", "workstream", "visible", "client_message"]
EDIT_ROWS_DONE = ["description", "baseline", "forecast", "actual", "name", "owner", "state", "progress", "workstream", "visible", "client_message"]
VIEW_ROWS = ["description", "baseline", "forecast", "state", "progress", "workstream", "client_message"]
VIEW_ROWS_DONE = ["description", "baseline", "forecast", "actual", "state", "progress", "workstream", "client_message"]

FLAT = """(() => {
  const rows = [...document.querySelectorAll('#peek .pk-fields > .pk-row')];
  const box = (r) => r.getBoundingClientRect();
  const cs = (r) => getComputedStyle(r);
  return {keys: rows.map((r) => r.dataset.row),
          lefts: [...new Set(rows.map((r) => Math.round(box(r).left)))],
          rights: [...new Set(rows.map((r) => Math.round(box(r).right)))],
          stacked: rows.every((r, i) => i === 0 || box(r).top >= box(rows[i - 1]).bottom - 1),
          tile: rows.filter((r) => ['Left', 'Right', 'Bottom'].some((s) => parseFloat(cs(r)['border' + s + 'Width']) > 0) || parseFloat(cs(r).borderTopLeftRadius) > 0).length,
          grid: getComputedStyle(document.querySelector('#peek .pk-fields')).gridTemplateColumns.split(' ').length};
})()"""


class Flat(Base):
    cur = GO_LIVE
    visit_peek = b828.Fields.visit_peek

    def done(self):
        with self.store.step("dashboard", USER) as st:
            st.update("milestones", PILOT, {"status": "Done", "state": "Achieved", "state_set": 1, "actual_date": "2020-01-05"})

    def seen(self, ms, width, view="milestones"):
        with chrome() as cdp:
            p = self.visit_peek(cdp, ms=ms, width=width, view=view)
            p.until("document.querySelectorAll('#peek .pk-fields > .pk-row').length > 3", "the rows drew")
            return json.loads(json.dumps(p.js(FLAT)))

    def check_flat(self, s):
        self.assertEqual(s["tile"], 0, "no row is a bordered tile")
        self.assertEqual(len(s["lefts"]), 1, "every row starts at the same left edge")
        self.assertEqual(len(s["rights"]), 1, "every row ends at the same right edge")
        self.assertTrue(s["stacked"], "one row under another, not side by side")
        self.assertEqual(s["grid"], 1, "one column")

    def test_the_editable_peek_is_one_flat_list_in_the_ruled_order(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                s = self.seen(PILOT, width)
                self.assertEqual(s["keys"], EDIT_ROWS)
                self.check_flat(s)

    def test_achieved_on_is_there_only_when_the_milestone_is_achieved(self):
        self.done()
        for width in (1400, 900):
            with self.subTest(width=width):
                s = self.seen(PILOT, width)
                self.assertEqual(s["keys"], EDIT_ROWS_DONE)
                self.check_flat(s)

    def test_the_read_only_peek_is_the_same_flat_list(self):
        with self.store.step("dashboard", USER) as st:
            st.update("milestones", PILOT, {"description": "<p>Training done</p>", "client_message": "On its way", "percent_complete": 50, "workstream": "Build"})
        for width in (1400, 900):
            with self.subTest(width=width):
                s = self.seen(PILOT, width, view="dashboard")
                self.assertEqual(s["keys"], VIEW_ROWS)
                self.check_flat(s)

    def test_the_read_only_peek_shows_achieved_on_only_when_achieved(self):
        self.done()
        for width in (1400, 900):
            with self.subTest(width=width):
                s = self.seen(PILOT, width, view="dashboard")
                self.assertEqual(s["keys"], VIEW_ROWS_DONE)
                self.check_flat(s)


if __name__ == "__main__":
    unittest.main()
