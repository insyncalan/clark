"""Row 1336 part 3: Project health and the status shapes of the At a glance template under the Classic Theme, measured at 1400 and 900 px
against the approved mock-up (item 1264, the same elements in the page and in the mock-up): the reason box is as wide and as high as the mock-up's
(the pill sits above it, not beside it), no word of the reason is broken in the middle, and the status shape in View is the 8x8 dot Edit
and the mock-up draw. Fictional data only; the values are pinned here as constants (tests C1 to C5, which CI runs); the mock-up compare (H1, H2, H4) is an extra that runs only when the checkout named by
the CLARK_MOCKUP_DIR variable holds the mock-up.

Run: TZ=UTC python3 dev/run_tests.py test_theme_glance_health_1336_p3
"""
import json
import os
import pathlib
import re
import unittest

from test_server import chrome, wait
from test_tpl_glance_editor_1264 import OWN  # noqa: E402
from test_theme_glance_edit_1336 import ClassicEdit, RULES, tearDownModule  # noqa: F401

PLAN = os.environ.get("CLARK_MOCKUP_DIR") or "/nonexistent"      # no default place: the mock-up compare runs only where CLARK_MOCKUP_DIR names a checkout that holds it
MOCK = pathlib.Path(PLAN) / "mockups" / "1264-at-a-glance-template" / "html" / "at-a-glance-builder.html"
REASON = "Rights data for the 1970s catalogue is late; pilot labels are unaffected."
TILE_LESS_BOX = 34   # the tile width less the reason box width: padding 16 and border 1 on both sides, measured in Chrome at 1400 and 900, Edit and View
DOT = [8, 8, "block"]   # the counting tile's status shape in View and Edit
LONG = "Supercalifragilisticexpialidocious catalogue reconciliation incomprehensibilities"

# One health reason box, and what is in it: its box, the line count of its text, and whether any word was broken (a word drawn on two lines).
BOX = """(function(box){ if (!box) return null; var r = box.getBoundingClientRect(), cs = getComputedStyle(box), words = [], lines = 0, broken = 0;
  var w = document.createTreeWalker(box, NodeFilter.SHOW_TEXT), n, tops = {};
  while ((n = w.nextNode())) { var re = /\\S+/g, m; while ((m = re.exec(n.nodeValue))) { var rg = document.createRange(); rg.setStart(n, m.index); rg.setEnd(n, m.index + m[0].length);
    var rs = rg.getClientRects(), t = {}; for (var i = 0; i < rs.length; i++) { if (rs[i].width > 0) t[Math.round(rs[i].top)] = 1; tops[Math.round(rs[i].top)] = 1; }
    if (Object.keys(t).length > 1) broken++; words.push(m[0]); } }
  return { w: Math.round(r.width * 10) / 10, h: Math.round(r.height * 10) / 10, lines: Object.keys(tops).length, broken: broken, words: words.length, wb: cs.wordBreak, ow: cs.overflowWrap,
    over: box.scrollWidth - box.clientWidth, lh: parseFloat(cs.lineHeight) }; })"""
PAGE_PROBE = """(function(sel, view){ var g = document.querySelector(sel + (view ? ' .tpl-gt' : ' [data-glance-template]')), out = {};
  var cell = g.querySelector('[data-tile=health]'), box = cell && cell.querySelector('.hreason');
  out.box = (""" + BOX + """)(box);
  out.cell = cell ? (function(r){ return { w: Math.round(r.width * 10) / 10, h: Math.round(r.height * 10) / 10 }; })(cell.getBoundingClientRect()) : null;
  var fig = cell && cell.querySelector('.fig, .tpl-gt-tile'); var pill = cell && cell.querySelector('.hpill'); var pr = pill && pill.getBoundingClientRect(), br = box && box.getBoundingClientRect();
  out.stacked = !!(pr && br && br.top >= pr.bottom - 1);
  var shapes = []; g.querySelectorAll('.ragdot, .tpl-gt-dot, .tpl-shp').forEach(function(d){ var r = d.getBoundingClientRect(); shapes.push([Math.round(r.width * 10) / 10, Math.round(r.height * 10) / 10, getComputedStyle(d).display]); });
  out.shapes = shapes; return out; })"""
MOCK_PROBE = """(function(){ var out = {}; var cell = document.querySelector('[data-tile=health]'), box = cell.querySelector('.hreason');
  out.box = (""" + BOX + """)(box); var r = cell.getBoundingClientRect(); out.cell = { w: Math.round(r.width * 10) / 10, h: Math.round(r.height * 10) / 10 };
  var shapes = []; document.querySelectorAll('.glance .ragdot').forEach(function(d){ var r = d.getBoundingClientRect(); shapes.push([Math.round(r.width * 10) / 10, Math.round(r.height * 10) / 10, getComputedStyle(d).display]); });
  out.shapes = shapes; return out; })()"""


class Health(ClassicEdit):
    def setUp(self):
        super().setUp()
        with self.store.step("dashboard", __import__("_demo").USER) as st:
            st.update("projects", "ABC", {"health": "At risk", "health_reason": REASON})
        self.seed_view_body()

    def seed_view_body(self):
        status, got = self.real_change({"project": "ABC", "kind": "report_sections", "op": "update", "id": self.ref, "changes": {"body": json.dumps({"v": 1})}})
        assert status == 200, got

    def page_numbers(self, cdp, width, view):
        p = self.page(cdp, width, False)
        if view:
            p.view()
            p.until(f"!!document.querySelector('{self.sel('.tpl-gt [data-tile=health] .hreason')}')", "View drew the health reason")
        else:
            p.until(f"!!document.querySelector('{self.sel('[data-glance-template] [data-tile=health] .hreason')}')", "Edit drew the health reason")
        return p.js(f"({PAGE_PROBE})({json.dumps(self.sel())}, {json.dumps(view)})")

    def mock_numbers(self, cdp, width, mode):
        tid = cdp.call("Target.createTarget", {"url": "about:blank"})["targetId"]
        sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Page.navigate", {"url": MOCK.as_uri()}, sid)
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-tile=health] .hreason') || !!document.querySelector('[data-tile=health]')", sid), 15), "the mock-up drew")
        cdp.js(f"document.querySelector('#segMode [data-v={mode}]').click()", sid)
        self.assertTrue(wait(lambda: cdp.js(f"document.querySelector('.rep').dataset.mode === '{mode}'", sid), 5))
        return cdp.js(MOCK_PROBE, sid)

    def measure(self):
        got = {}
        with chrome() as cdp:
            for width in (1400, 900):
                for mode in ("edit", "view"):
                    got[f"{mode}{width}"] = {"page": self.page_numbers(cdp, width, mode == "view"), "mock": self.mock_numbers(cdp, width, mode)}
        out = os.environ.get("MEASURE_OUT")
        if out:
            pathlib.Path(out).write_text(json.dumps(got, indent=1), encoding="utf-8")
        return got

    @unittest.skipUnless(MOCK.exists(), "the checkout with the mock-up is not here")
    def test_H1_the_reason_sits_under_the_pill_at_the_mock_up_width_and_height_in_edit_and_view(self):
        """The same element in the page and in the mock-up at 1400 and 900. The tile is narrower in the page than in the mock-up (the page has a side
        bar), so the width is compared as what the tile leaves it: the tile width less the box width (padding 16 and border 1 on both sides: 34).
        The height is compared as the box less its lines (padding and border), because the page's text leading is the page's own token."""
        got = self.measure()
        for key, v in got.items():
            with self.subTest(key=key):
                pg, mk = v["page"], v["mock"]
                self.assertTrue(pg["stacked"], f"the reason is under the pill: {pg}")
                self.assertAlmostEqual(pg["cell"]["w"] - pg["box"]["w"], mk["cell"]["w"] - mk["box"]["w"], delta=1, msg=f"width left by the tile {pg} {mk}")
                self.assertAlmostEqual(pg["box"]["h"] - pg["box"]["lines"] * pg["box"]["lh"], mk["box"]["h"] - mk["box"]["lines"] * mk["box"]["lh"], delta=1,
                                       msg=f"box height less its text lines {pg} {mk}")
                self.assertGreater(pg["box"]["w"], 140, f"no strip of a few words: {pg}")

    @unittest.skipUnless(MOCK.exists(), "the checkout with the mock-up is not here")
    def test_H2_no_word_of_the_reason_is_broken_and_the_wrap_is_normal(self):
        got = self.measure()
        for key, v in got.items():
            with self.subTest(key=key):
                b = v["page"]["box"]
                self.assertEqual(b["broken"], 0, f"a word was drawn on two lines: {b}")
                self.assertEqual((b["wb"], b["ow"]), ("normal", "break-word"), b)
                self.assertLessEqual(b["over"], 0, f"nothing runs out of the box: {b}")

    def test_H3_a_word_longer_than_the_line_breaks_only_as_the_last_resort_and_stays_inside(self):
        with self.store.step("dashboard", __import__("_demo").USER) as st:
            st.update("projects", "ABC", {"health": "At risk", "health_reason": LONG})
        for view in (False, True):
            with chrome() as cdp:
                for width in (1400, 900):
                    with self.subTest(view=view, width=width):
                        got = self.page_numbers(cdp, width, view)
                        self.assertLessEqual(got["box"]["over"], 0, got)
                        self.assertLessEqual(got["box"]["broken"], 1, "only the one long word may break: " + json.dumps(got["box"]))

    @unittest.skipUnless(MOCK.exists(), "the checkout with the mock-up is not here")
    def test_H4_the_view_status_shapes_are_the_8_by_8_dot_of_edit_and_the_mock_up(self):
        got = self.measure()
        for width in (1400, 900):
            with self.subTest(width=width):
                for key in (f"view{width}", f"edit{width}"):
                    self.assertEqual(got[key]["page"]["shapes"], [[8, 8, "block"]] * 4, got[key]["page"]["shapes"])
                self.assertEqual(got[f"view{width}"]["mock"]["shapes"], got[f"view{width}"]["page"]["shapes"])

    def test_C1_the_tile_leaves_the_reason_box_34px_in_edit_and_view_at_1400_and_900(self):
        with chrome() as cdp:
            for width in (1400, 900):
                for view in (False, True):
                    with self.subTest(width=width, view=view):
                        got = self.page_numbers(cdp, width, view)
                        self.assertAlmostEqual(got["cell"]["w"] - got["box"]["w"], TILE_LESS_BOX, delta=1, msg=json.dumps(got))
                        self.assertGreater(got["box"]["w"], 140, f"no strip of a few words: {got}")

    def test_C2_the_reason_sits_under_the_pill_and_its_lines_do_not_exceed_the_measured_count(self):
        # Pinned as structure (box top at or below the pill bottom), not as a number that depends on the side bar; 3 lines at 1400 and 4 at 900 are a ceiling.
        with chrome() as cdp:
            for width, most in ((1400, 3), (900, 4)):
                for view in (False, True):
                    with self.subTest(width=width, view=view):
                        got = self.page_numbers(cdp, width, view)
                        self.assertTrue(got["stacked"], f"the reason is under the pill: {got}")
                        self.assertLessEqual(got["box"]["lines"], most, got)

    def test_C3_no_word_is_broken_and_the_wrap_is_normal_with_break_word_only(self):
        with chrome() as cdp:
            for width in (1400, 900):
                for view in (False, True):
                    with self.subTest(width=width, view=view):
                        b = self.page_numbers(cdp, width, view)["box"]
                        self.assertEqual(b["broken"], 0, f"a word was drawn on two lines: {b}")
                        self.assertEqual((b["wb"], b["ow"]), ("normal", "break-word"), b)
                        self.assertLessEqual(b["over"], 0, b)

    def test_C4_the_counting_tiles_draw_the_8_by_8_dot_in_view_and_edit(self):
        with chrome() as cdp:
            for width in (1400, 900):
                for view in (False, True):
                    with self.subTest(width=width, view=view):
                        self.assertEqual(self.page_numbers(cdp, width, view)["shapes"], [DOT] * 4)

    def test_C5_a_typed_own_tile_in_view_keeps_its_12_by_12_shape(self):
        self.seed([dict(OWN)])
        with chrome() as cdp:
            for width in (1400, 900):
                with self.subTest(width=width):
                    p = self.page(cdp, width, False)
                    p.view()
                    q = self.sel('.tpl-gt [data-tile=t1] .tpl-gt-dot')
                    p.until(f"!!document.querySelector('{q}')", "View drew the typed tile")
                    self.assertEqual(p.js(f"(function(r){{ return [Math.round(r.width), Math.round(r.height)]; }})(document.querySelector('{q}').getBoundingClientRect())"), [12, 12])

    def test_H5_the_rules_sit_in_the_classic_block_before_row_1314_with_no_hash_and_digits(self):
        block = RULES.split("/* Row 1336 part 3")[1].split("/* Row 1342")[0]
        self.assertLess(RULES.index("/* Row 1336 part 3"), RULES.index("/* Row 1314"))
        for rule in (".tpl-edit-glancetemplate .glance .hrow, .tpl-gt-health .hrow { flex-wrap: wrap; }", ".tpl-gt .tpl-gt-tile.go .tpl-gt-dot { width: 8px; height: 8px; }"):
            self.assertIn(rule, block)
        self.assertNotRegex(block, r"break-all|anywhere|#\d")


if __name__ == "__main__":
    unittest.main()
