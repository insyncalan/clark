"""Row 1324 gap: the drag on the Work items grouped view. The one column-names row sits over every group, so dragging the right edge
of a column name (its width handle) must give that column the new width in the names row AND in every group's rows (no group keeps
the old width, none drifts off the names), and a drag on a group heading starts nothing. Classic only (the look is Classic only).
Design and format only: no word is new.

Run: python3 dev/run_tests.py test_drag_1324_grouped
"""
import unittest

from test_server import chrome, wait  # noqa: E402
import test_gap_1324_workitems as g  # noqa: E402
import test_motion_rows as tmr  # noqa: E402

WIDTHS = """(() => { const q = (s, r) => (r || document).querySelector(s), qa = (s, r) => [...(r || document).querySelectorAll(s)];
  const names = qa('#work .wcolh th[data-col]').map((h) => h.dataset.col);
  const one = (c) => { const h = q('#work .wcolh th[data-col=' + c + ']'); return h ? [Math.round(h.getBoundingClientRect().width), ...qa('#work table.grouped').map((t) => { const td = q('tbody tr[data-id] td.' + h.className.split(' ')[0], t); return td ? Math.round(td.getBoundingClientRect().width) : -1; })] : null; };
  return { names, one: Object.fromEntries(names.map((c) => [c, one(c)])) }; })()"""
GRIP = """(() => { const g = [...document.querySelectorAll('#work .wcolh th[data-col] .cgrip')]; if (!g.length) return null;
  const i = Math.min(1, g.length - 1), r = g[i].getBoundingClientRect(); g[i].scrollIntoView({block: 'center'});
  const s = g[i].getBoundingClientRect(); return [s.left + s.width / 2, s.top + s.height / 2, g[i].closest('th').dataset.col]; })()"""


class GroupedDrag(unittest.TestCase):
    setUpClass = classmethod(tmr.MotionRows.setUpClass.__func__)
    tearDownClass = classmethod(tmr.MotionRows.tearDownClass.__func__)
    load = g.WorkItemsOptionA.load

    def mouse(self, cdp, sid, kind, x, y, buttons=0):
        cdp.call("Input.dispatchMouseEvent", {"type": kind, "x": x, "y": y, "button": "left" if kind != "mouseMoved" or buttons else "none", "buttons": buttons, "clickCount": 1 if kind != "mouseMoved" else 0}, sid)

    def test_dragging_a_width_handle_resizes_the_column_in_the_names_row_and_in_every_group(self):
        with chrome() as cdp:
            sid = self.load(cdp, 1400, "light", "no-preference")
            before = cdp.js(WIDTHS, sid)
            grip = cdp.js(GRIP, sid)
            self.assertIsNotNone(grip, "the column names carry width handles")
            x, y, col = grip
            self.assertGreaterEqual(cdp.js("document.querySelectorAll('#work table.grouped').length", sid), 3, "grouped by workstream")
            self.mouse(cdp, sid, "mouseMoved", x, y)
            self.mouse(cdp, sid, "mousePressed", x, y, 1)
            for i in range(1, 9):
                self.mouse(cdp, sid, "mouseMoved", x + 8 * i, y, 1)
            self.mouse(cdp, sid, "mouseReleased", x + 64, y)
            got = {}
            def moved():
                got.update(cdp.js(WIDTHS, sid))
                return got["one"][col][0] != before["one"][col][0]
            self.assertTrue(wait(moved), "the dragged column changed width in the names row")
            row = got["one"][col]
            self.assertEqual(len(set(row)), 1, "the names row and every group's rows give the column one width: " + str(row))
            self.assertEqual(cdp.js("document.querySelectorAll('#work tr.colh').length", sid), 1, "still one names row")
            self.assertTrue(cdp.js("document.documentElement.scrollWidth <= window.innerWidth", sid), "no sideways scroll after the drag")

    def test_a_press_and_move_on_a_group_heading_starts_no_drag_and_keeps_the_group_open(self):
        with chrome() as cdp:
            sid = self.load(cdp, 1400, "light", "no-preference")
            rows = cdp.js("document.querySelectorAll('#work tbody tr[data-id]').length", sid)
            pos = cdp.js("(() => { const b = document.querySelector('#work .grp-b'); const r = b.getBoundingClientRect(); return [r.left + 40, r.top + r.height / 2, b.draggable, !!b.closest('[draggable=true]')]; })()", sid)
            x, y = pos[0], pos[1]
            self.assertEqual(pos[2:], [False, False], "a group heading is not draggable")
            self.mouse(cdp, sid, "mouseMoved", x, y)
            self.mouse(cdp, sid, "mousePressed", x, y, 1)
            for i in range(1, 6):
                self.mouse(cdp, sid, "mouseMoved", x + 10 * i, y + 30 * i, 1)
            self.mouse(cdp, sid, "mouseReleased", x + 50, y + 150)
            self.assertEqual(cdp.js("document.querySelectorAll('#work tbody tr[data-id]').length", sid), rows, "the same rows, in the same open groups")
            self.assertEqual(cdp.js("document.querySelectorAll('#work tr.colh').length", sid), 1)


if __name__ == "__main__":
    unittest.main()
