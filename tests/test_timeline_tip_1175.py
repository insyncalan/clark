"""Row 1175: the name a hidden-name mark shows on hover or focus is drawn fully, not under a neighbouring shown label.

Run: python3 dev/run_tests.py test_timeline_tip_1175
Chrome launches at 1400 and 900 px, light and dark, Quarter scale.
"""
import unittest

from test_milestones_page import BrowserBase
from test_server import chrome, wait

HASH = "#milestones&p=TUL"

# For the open tip of the mark at index `i` among the hidden-name marks (sorted left to right):
# its box, the shown labels it overlaps, and whether each of those is painted below the mark.
PROBE = """((i) => {
  const marks = [...document.querySelectorAll('.mv-mk[data-hid]')].sort((a, b) => a.getBoundingClientRect().left - b.getBoundingClientRect().left);
  const m = marks[i < 0 ? marks.length + i : i], r = m.getBoundingClientRect(), c = getComputedStyle(m, '::after');
  const w = parseFloat(c.width), h = parseFloat(c.height);
  const tx = new DOMMatrix(c.transform).m41, k = r.width / 24;   // the tip's own shift (the mark is scaled while open)
  const box = {left: r.left + r.width / 2 + tx * k, top: r.bottom, right: r.left + r.width / 2 + (tx + w) * k, bottom: r.bottom + h * k};
  const wrap = m.closest('.mv-wrap').getBoundingClientRect();
  const over = [...document.querySelectorAll('.mv-lab')].filter(l => { const b = l.getBoundingClientRect();
    return b.left < box.right && b.right > box.left && b.top < box.bottom && b.bottom > box.top; });
  const z = e => { const v = parseInt(getComputedStyle(e).zIndex, 10); return isNaN(v) ? 0 : v; };
  const hits = [];
  if (c.pointerEvents !== 'none') for (let k = 1; k < 10; k++) { const e = document.elementFromPoint(box.left + (box.right - box.left) * k / 10, (box.top + box.bottom) / 2);
    hits.push(!!e && (e === m || m.contains(e))); }
  return {focus: document.activeElement === m, content: c.content, name: m.dataset.hid, w, h, box, wrap: {left: wrap.left, right: wrap.right, bottom: wrap.bottom},
    overlaps: over.length, markZ: z(m), labZ: over.map(z), hits, pe: c.pointerEvents}; })"""
LABZ = "Math.min(...[...document.querySelectorAll('.mv-lab')].map(e => parseInt(getComputedStyle(e).zIndex, 10)))"
MARKZ = "Math.max(...[...document.querySelectorAll('.mv-mk[data-hid]')].map(e => parseInt(getComputedStyle(e).zIndex, 10) || 0))"


class Tip(BrowserBase, unittest.TestCase):
    def quarter(self, cdp, width, port):
        sid = self.visit(cdp, width, HASH, port)
        cdp.js("document.querySelector('.mv-bar [data-scale-b=quarter]').click()", sid)
        self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('.mv-mk[data-hid]').length", sid) > 1), "names are hidden at Quarter")
        return sid

    def check(self, cdp, sid, i, where):
        got = cdp.js(f"({PROBE})({i})", sid)
        self.assertTrue(got["focus"], f"{where}: the mark takes the focus")
        self.assertEqual(got["content"].strip('"'), got["name"], f"{where}: the tip shows the whole name")
        self.assertGreater(got["w"], 0, where)
        for z in got["labZ"]:
            self.assertGreater(got["markZ"], z, f"{where}: the open mark is above every label its tip overlaps")
        self.assertNotIn(False, got["hits"], f"{where}: the tip is the top thing along its whole width")
        self.assertGreaterEqual(got["box"]["left"], got["wrap"]["left"] - 0.5, f"{where}: the tip is not cut at the left edge of the timeline box")
        self.assertLessEqual(got["box"]["right"], got["wrap"]["right"] + 0.5, f"{where}: the tip is not cut at the right edge of the timeline box")
        self.assertLessEqual(got["box"]["bottom"], got["wrap"]["bottom"] + 0.5, f"{where}: the tip is not cut at the bottom of the timeline box")
        return got

    def test_the_leftmost_and_rightmost_tips_are_above_the_shown_labels_by_focus(self):
        port = self.serve()
        for width in (1400, 900):
            with chrome() as cdp:
                sid = self.quarter(cdp, width, port)
                for theme in ("light", "dark"):
                    cdp.js(f"document.documentElement.dataset.theme = '{theme}'", sid)
                    self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.theme", sid) == theme))
                    for i in (0, -1):
                        cdp.js(f"(() => {{ const m = [...document.querySelectorAll('.mv-mk[data-hid]')].sort((a, b) => a.getBoundingClientRect().left - b.getBoundingClientRect().left); m[{i} < 0 ? m.length + {i} : {i}].focus(); }})()", sid)
                        self.check(cdp, sid, i, f"{width} {theme} mark {i}")

    def test_every_hidden_name_tip_is_above_the_labels_by_focus(self):
        port = self.serve()
        for width in (1400, 900):
            with chrome() as cdp:
                sid = self.quarter(cdp, width, port)
                n = cdp.js("document.querySelectorAll('.mv-mk[data-hid]').length", sid)
                for i in range(n):
                    cdp.js(f"(() => {{ const m = [...document.querySelectorAll('.mv-mk[data-hid]')].sort((a, b) => a.getBoundingClientRect().left - b.getBoundingClientRect().left); m[{i}].focus(); }})()", sid)
                    self.check(cdp, sid, i, f"{width} mark {i} of {n}")

    def test_hover_lifts_the_mark_the_same_way(self):
        port = self.serve()
        for width in (1400, 900):
            with chrome() as cdp:
                sid = self.quarter(cdp, width, port)
                at = cdp.js("""(() => { const m = [...document.querySelectorAll('.mv-mk[data-hid]')].sort((a, b) => a.getBoundingClientRect().left - b.getBoundingClientRect().left)[0];
                  const r = m.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; })()""", sid)
                cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": at[0], "y": at[1]}, sid)
                self.assertTrue(wait(lambda: cdp.js("document.querySelector('.mv-mk[data-hid]:hover') !== null", sid)), "the mark is hovered")
                got = cdp.js(f"({PROBE})(0)", sid)
                for z in got["labZ"]:
                    self.assertGreater(got["markZ"], z, f"{width}: hovered mark is above the labels its tip overlaps")
                self.assertNotIn(False, got["hits"], f"{width}: the hovered tip is on top along its whole width")

    def test_the_ticket_case_really_has_the_tip_across_a_shown_label(self):
        # The ticket case: Quarter scale, the leftmost tip lies across a shown label. If this stops being so the test above proves nothing.
        port = self.serve()
        for width in (1400, 900):
            with chrome() as cdp:
                sid = self.quarter(cdp, width, port)
                cdp.js("[...document.querySelectorAll('.mv-mk[data-hid]')].sort((a, b) => a.getBoundingClientRect().left - b.getBoundingClientRect().left)[0].focus()", sid)
                self.assertGreater(cdp.js(f"({PROBE})(0)", sid)["overlaps"], 0, f"{width}: the leftmost tip lies across a shown label")

    def test_at_rest_the_labels_still_sit_above_every_mark_and_the_open_mark_is_lifted_only_while_open(self):
        port = self.serve()
        for width in (1400, 900):
            with chrome() as cdp:
                sid = self.quarter(cdp, width, port)
                cdp.js("document.activeElement && document.activeElement.blur()", sid)
                self.assertGreaterEqual(cdp.js(LABZ, sid), cdp.js(MARKZ, sid), f"{width}: at rest no mark is above a label")
                cdp.js("[...document.querySelectorAll('.mv-mk[data-hid]')][0].focus()", sid)
                self.assertGreater(cdp.js(MARKZ, sid), cdp.js(LABZ, sid), f"{width}: the open mark is above the labels")
                cdp.js("document.activeElement.blur()", sid)
                self.assertGreaterEqual(cdp.js(LABZ, sid), cdp.js(MARKZ, sid), f"{width}: back to rest when closed")


if __name__ == "__main__":
    unittest.main()
