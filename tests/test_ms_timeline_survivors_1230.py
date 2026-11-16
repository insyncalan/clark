"""Row 1230, part 2: browser assertions for the survivors of the mutant report on MsTimeline.jsx (the Dashboard section's timeline).

Run: python3 dev/run_tests.py -j 1 test_ms_timeline_survivors_1230
Each test measures the drawn page in headless Chrome at 1400 and 900 px (real server, fictional data) and pins one rule of the layout:
  line 58   the number of tiers below the line sets the box's height (the lowest label sits inside the box);
  line 65   the line's top is the highest tier's top (44 px) plus every tier and every gap above it, tiers 48 px apart (label 38 + gap 10);
  line 67   the box keeps 30 px under the lowest label, and the caption does not overlap that label;
  line 76   a label's real width, not the 136 px estimate, decides which tier it takes;
  line 177  each leader ends 12 px from the line, above and below.
No new word: nothing here changes a string.
"""
import unittest

import test_ms_header_1230 as H

WIDTHS = (1400, 900)
LH, TGAP, LEAD, SIDE, CAPROOM, TOP = 38, 10, 12, 24, 30, 44      # MsTimeline.jsx's own numbers (line 26 and the 44 at line 65)

PROBE = """(() => {
  const R = (e) => e.getBoundingClientRect(), box = document.querySelector('.msv[data-place^=sec-]');
  const wrap = box.querySelector('.mv-wrap'), strip = box.querySelector('.mv-strip'), line = box.querySelector('.mv-line'), cap = box.querySelector('.mv-cap');
  const cs = getComputedStyle(wrap), s = R(strip).top, lineTop = R(line).top - s;
  const labs = [...box.querySelectorAll('.mv-lab2')].map((e) => { const r = R(e); return {id: e.dataset.lab, t: r.top - s, b: r.bottom - s, l: r.left, r: r.right, w: r.width}; });
  return {lineTop, labs, inner: R(wrap).top + wrap.clientTop + wrap.clientHeight - s, capTop: R(cap).top - s, capBottom: R(cap).bottom - s, overlaps: []};
})()"""


def tiers(got):
    """The distinct label tops above and below the line, each side sorted from the line outwards."""
    above = sorted({round(x["t"]) for x in got["labs"] if x["b"] <= got["lineTop"]}, reverse=True)
    below = sorted({round(x["t"]) for x in got["labs"] if x["t"] >= got["lineTop"]})
    return above, below


class Look(H.Base):
    def look(self, width):
        with self.case(width, False) as (cdp, sid, got):
            return got, cdp.js(PROBE, sid)


class Tiers(Look):      # the hostile fixture: ten marks in two weeks, so several tiers a side
    def test_the_highest_tier_starts_44px_down_and_tiers_above_are_48px_apart(self):      # line 65: LY without (nA - 1) * TGAP
        for width in WIDTHS:
            with self.subTest(width=width):
                got, p = self.look(width)
                above, below = tiers(p)
                self.assertGreaterEqual(len(above), 2, "two tiers above the line, so the gap between them counts")
                self.assertEqual(above[-1], TOP, "the highest label starts 44 px under the top of the strip")
                self.assertEqual([a - b for a, b in zip(above, above[1:])], [LH + TGAP] * (len(above) - 1), "tiers above are 38 + 10 px apart")
                self.assertEqual(round(p["lineTop"]), TOP + len(above) * LH + (len(above) - 1) * TGAP + SIDE, "the line sits under every tier above it")
                self.assertEqual([b - a for a, b in zip(below, below[1:])], [LH + TGAP] * (len(below) - 1), "and below it")


class Spread(Look):
    ROWS = H.Spread.ROWS

    def test_the_box_is_tall_enough_for_the_lowest_label(self):      # line 58: nB without the + 1
        for width in WIDTHS:
            with self.subTest(width=width):
                got, p = self.look(width)
                above, below = tiers(p)
                self.assertGreaterEqual(len(below), 1, "there are tiers below the line")
                low = max(x["b"] for x in p["labs"])
                self.assertLessEqual(low, p["inner"] + 1, f"the lowest label ends at {low}, inside the box that ends at {p['inner']}")
                self.assertGreaterEqual(p["inner"], p["lineTop"] + SIDE + len(below) * LH + (len(below) - 1) * TGAP - 1, "the box holds every tier below the line")

    def test_the_caption_has_room_under_the_lowest_label(self):      # line 67: CAPROOM dropped
        for width in WIDTHS:
            with self.subTest(width=width):
                got, p = self.look(width)
                low = max(x["b"] for x in p["labs"])
                self.assertGreaterEqual(p["inner"] - low, CAPROOM - 4, f"{CAPROOM} px under the lowest label (box ends {p['inner']}, label {low})")
                self.assertGreaterEqual(p["capTop"], low - 1, "the caption starts under the lowest label")

    def test_each_leader_ends_12px_from_the_line_above_and_below(self):      # line 177: the upper leader without - LEAD
        for width in WIDTHS:
            with self.subTest(width=width):
                got, p = self.look(width)
                self.assertEqual(len(got["joins"]), got["labs"])
                for j in got["joins"]:
                    self.assertGreaterEqual(j["far"], LEAD - 3, f"{j['id']}: the leader stops {j['far']} px from the line, not on it")
                    self.assertLessEqual(j["far"], LEAD + 3, f"{j['id']}: and not further than {LEAD} px from it")


LONG = [(f"Regional programme steering board sign-off {k}", d, None)
        for k, d in enumerate(["2026-08-02", "2026-09-01", "2026-10-01", "2026-10-31", "2026-11-30", "2026-12-30", "2027-01-29", "2027-02-28", "2027-03-30", "2027-04-29"], 1)]


class Wide(H.Base):
    ROWS = LONG

    def test_a_long_name_takes_the_room_it_really_needs(self):      # line 76: the measure loses .mv-lab2, so every label counts 136 px
        for width in WIDTHS:
            with self.subTest(width=width), self.case(width, False) as (cdp, sid, got):
                p = cdp.js(PROBE, sid)
                self.assertEqual(len([x for x in p["labs"] if x["w"] > 180]), 10, [round(x["w"]) for x in p["labs"]])
                self.assertEqual(got["overlaps"], [], "labels about 150 px apart but 180+ px wide do not sit on each other")
                self.assertGreaterEqual(len(set(round(x["t"]) for x in p["labs"])), 2, "they take more than one tier")


if __name__ == "__main__":
    unittest.main()
