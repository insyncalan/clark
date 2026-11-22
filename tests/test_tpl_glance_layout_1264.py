"""Row 1264 slice 9: the glance template's layout. Project health on its own row (a switch in Edit, off by default), half width shows 2 tiles
on a line in View and in Edit (493 px at 1400; at 900 half is the full width), "Tiles on a line" 3 or 4 (set in Edit, drawn in View too),
the eye on Project health ("hidden completely") and the button that brings it back, the two hint sentences. Real browser, widths 1400 and
900 only, light and dark, fictional data. Words are the ruled ones (words file groups 2, 3, 10, 12, 13 and v2 A); no keyboard-only walk-through.

Run: python3 dev/run_tests.py test_tpl_glance_layout_1264
"""
import json
import re
import unittest

from _demo import USER
from _paths import SRC
from test_glance_page import plant
from test_report_editor import Base, tearDownModule  # noqa: F401
from test_server import chrome, wait
from test_changes import KIND
from clark.section_kinds import glancetemplate as gt

W_OWN, W_BESIDE = "Project health on its own row", "Tiles on a line"
SHOW_HEALTH = "Show project health here"
HALF_NOTE = "Half width always shows 2 on a line."
HINT_EYE = "The eye on Project health hides it completely."
HINT_ADD = "Use Add a tile to make your own. Click the pencil on your own tile to edit it."


class Rules(unittest.TestCase):
    """The stored field: per_row, 3 or 4, 4 is the default and is not stored."""

    class R:
        plain = staticmethod(lambda t: True)
        visible = staticmethod(lambda t: any(c.isalnum() for c in t))

    def test_per_row_is_3_or_4_and_4_is_not_stored(self):
        self.assertEqual(gt.check({"v": 1, "per_row": 3}, self.R), {"v": 1, "per_row": 3})
        self.assertEqual(gt.check({"v": 1, "per_row": 4}, self.R), {"v": 1})
        self.assertEqual(gt.check({"v": 1}, self.R), {"v": 1})
        self.assertEqual(gt.upgrade({"v": 1})["per_row"], 4)
        self.assertEqual(gt.upgrade({"v": 1, "per_row": 3})["per_row"], 3)
        self.assertEqual(gt.upgrade({"v": 1, "per_row": 9})["per_row"], 4, "a wrong value reads as the default")

    def test_upgrade_reads_a_whole_float_per_row_as_the_page_does(self):
        self.assertEqual(gt.upgrade({"v": 1, "per_row": 3.0})["per_row"], 3)
        self.assertEqual(gt.upgrade({"v": 1, "per_row": 4.0})["per_row"], 4)
        self.assertIs(type(gt.upgrade({"v": 1, "per_row": 3.0})["per_row"]), int, "a number, not the float it was read as")
        self.assertEqual(gt.upgrade({"v": 1, "per_row": 3.5})["per_row"], 4)
        self.assertIs(type(gt.upgrade({"v": 1, "per_row": 3})["per_row"]), int)

    def test_per_row_wrong_values_are_refused_with_the_ruled_words_and_never_quote_the_value(self):
        for wrong in (2, 5, 0, -3, "3", 3.0, True, False, [], {}):
            with self.subTest(wrong=wrong):
                with self.assertRaises(gt.Bad) as got:
                    gt.check({"v": 1, "per_row": wrong}, self.R)
                self.assertEqual(str(got.exception), "Tiles on a line is 3 or 4. Choose one of those.")

    def test_the_file_carries_per_row_and_own_row(self):
        class Ctx:
            rows = {"actions": [], "raid": [], "decisions": []}
            as_at = "2030-01-15"
        got = gt.published({"v": 1, "per_row": 3, "health": {"own_row": True}, "bespoke": [{"id": "b1", "label": "Fictional"}]}, Ctx)
        self.assertEqual(got["content"]["per_row"], 3)
        self.assertEqual(got["content"]["health"], {"shown": True, "own_row": True})
        got = gt.published({"v": 1, "bespoke": [{"id": "b1", "label": "Fictional"}]}, Ctx)
        self.assertEqual(got["content"]["per_row"], 4)


class Layout(Base):
    def setUp(self):
        super().setUp()
        plant(self)
        with self.store.step("dashboard", USER) as st:
            self.ref = st.create("report_sections", {"project": "ABC", "type": "glancetemplate", "title": "Fictional glance", "sort_order": 998})
        self.store.con.execute("UPDATE report_sections SET body = ? WHERE id = ?", ('{"v":1}', self.ref))      # an existing page: no health field, health shown

    def set_body(self, body):
        status, got = self.real_change({"project": "ABC", "kind": KIND, "op": "update", "id": self.ref, "changes": {"body": json.dumps(body)}})
        assert status == 200, got

    def make_half(self):
        with self.store.step("dashboard", USER) as st:
            st.create("report_sections", {"project": "ABC", "type": "text", "title": "Fictional partner", "sort_order": 999})
        status, got = self.real_change({"project": "ABC", "kind": KIND, "op": "update", "id": self.ref, "changes": {"beside": 1}})
        assert status == 200, got

    def make_half_right(self):
        """The glance in the right slot: its partner comes first and sits beside it."""
        with self.store.step("dashboard", USER) as st:
            partner = st.create("report_sections", {"project": "ABC", "type": "text", "title": "Fictional partner", "sort_order": 997})
        status, got = self.real_change({"project": "ABC", "kind": KIND, "op": "update", "id": partner, "changes": {"beside": 1}})
        assert status == 200, got

    def sel(self, rest=""):
        return f'[data-id="{self.ref}"] {rest}'.strip()

    def per(self, n):
        return self.sel('[data-gt-per="%d"]' % n)

    def body(self):
        raw = self.store.read("report_sections", ref=self.ref)["body"]
        return json.loads(raw) if raw else {}

    def applies(self):
        return self.store.con.execute("SELECT count(*) FROM applies").fetchone()[0]

    def page(self, cdp, width=1400, dark=False, edit=False):
        p = self.visit(cdp)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        if dark:
            p.js("document.documentElement.dataset.theme = 'dark'")
        if edit:
            p.edit()
        p.until(f"!!document.querySelector('{self.sel('[data-tile=decisions]')}')", "the tiles drew")
        return p

    def cells(self, p, edit):
        """Every drawn tile with its box: health and the three (and any more)."""
        pick = ".glance > .tcell" if edit else ".tpl-gt > [data-tile]"
        return p.js(f"""(function(){{ var s = document.querySelector('{self.sel()}'), g = s.querySelector('{".glance" if edit else ".tpl-gt"}'), gr = g.getBoundingClientRect();
          return {{cells: [...s.querySelectorAll('{pick}')].map(function(e){{ var r = e.getBoundingClientRect(); return {{key: e.dataset.tile, left: r.left, right: r.right, top: Math.round(r.top), width: r.width}}; }}),
                  grid: [gr.left, gr.right, gr.width], sec: s.getBoundingClientRect().width, overflow: document.documentElement.scrollWidth > window.innerWidth}}; }})()""")

    @staticmethod
    def lines(got):
        tops = sorted({c["top"] for c in got["cells"]})
        return [[c["key"] for c in got["cells"] if c["top"] == t] for t in tops]


class View(Layout):
    def setUp(self):
        super().setUp()
        self.set_body({"v": 1})          # a section with no body at all is left out whole; this one is drawn

    def test_V1_by_default_health_and_the_three_tiles_share_one_line_of_four_at_1400(self):
        with chrome() as cdp:
            got = self.cells(self.page(cdp), False)
        self.assertEqual(self.lines(got), [["health", "overdue", "risks", "decisions"]])
        widths = [c["width"] for c in got["cells"]]
        self.assertLessEqual(max(widths) - min(widths), 1.5, f"one size: {widths}")

    def test_V2_tiles_on_a_line_3_gives_lines_of_three(self):
        self.set_body({"v": 1, "per_row": 3})
        with chrome() as cdp:
            got = self.cells(self.page(cdp), False)
        self.assertEqual(self.lines(got), [["health", "overdue", "risks"], ["decisions"]])

    def test_V3_health_on_its_own_row_takes_the_whole_row_and_the_tiles_follow(self):
        self.set_body({"v": 1, "health": {"own_row": True}})
        with chrome() as cdp:
            got = self.cells(self.page(cdp), False)
        self.assertEqual(self.lines(got), [["health"], ["overdue", "risks", "decisions"]])
        health = got["cells"][0]
        self.assertAlmostEqual(health["width"], got["grid"][2], delta=1.5, msg="the whole row")

    def test_V4_health_off_leaves_no_health_tile(self):
        self.set_body({"v": 1, "health": {"shown": False}})
        with chrome() as cdp:
            got = self.cells(self.page(cdp), False)
        self.assertEqual(self.lines(got), [["overdue", "risks", "decisions"]])

    def test_V5_half_width_shows_2_on_a_line_whatever_the_setting_and_is_half_of_the_full_width_at_1400(self):
        with chrome() as cdp:
            full = self.cells(self.page(cdp), False)["sec"]
        self.make_half()
        for body in ({"v": 1}, {"v": 1, "per_row": 3}):
            self.set_body(body)
            with self.subTest(body=body), chrome() as cdp:
                got = self.cells(self.page(cdp), False)
                self.assertEqual(self.lines(got), [["health", "overdue"], ["risks", "decisions"]])
                self.assertLess(got["sec"], full * 0.55, f"the half column: {got['sec']} of {full}")
                self.assertGreater(got["sec"], full * 0.4)
                self.assertTrue(all(c["width"] > 150 for c in got["cells"]), "no tile is squeezed")
                self.assertFalse(got["overflow"])

    def test_V9_half_width_in_the_right_slot_shows_2_on_a_line_too(self):
        self.make_half_right()
        with chrome() as cdp:
            p = self.page(cdp)
            self.assertTrue(p.js(f"!!document.querySelector('{self.sel()}.slot-right')"), "the glance is in the right slot")
            got = self.cells(p, False)
        self.assertEqual(self.lines(got), [["health", "overdue"], ["risks", "decisions"]])

    def test_V10_the_gap_between_tiles_is_the_space_token_both_ways(self):
        with chrome() as cdp:
            p = self.page(cdp)
            got = self.cells(p, False)
            token = p.js("(function(){ var d = document.createElement('div'); d.style.width = 'var(--space-3)'; document.body.appendChild(d); var w = d.getBoundingClientRect().width; d.remove(); return w; })()")
        a, b = got["cells"][0], got["cells"][1]
        self.assertAlmostEqual(b["left"] - a["right"], token, delta=0.6)

    def test_V6_at_900_the_one_breakpoint_is_760_so_full_draws_4_a_line_half_draws_2_and_half_is_the_full_width(self):
        full = None
        for half in (False, True):
            if half:
                self.make_half()
            with chrome() as cdp:
                got = self.cells(self.page(cdp, 900), False)
            self.assertEqual(self.lines(got), [["health", "overdue"], ["risks", "decisions"]] if half else [["health", "overdue", "risks", "decisions"]])
            self.assertFalse(got["overflow"])
            if full is None:
                full = got["sec"]
            else:
                self.assertAlmostEqual(got["sec"], full, delta=1.5, msg="half equals full at 900")

    def test_V7_it_fits_in_light_and_dark_at_both_widths_and_shows_the_projects_health(self):
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark), chrome() as cdp:
                    p = self.page(cdp, width, dark)
                    self.assertFalse(self.cells(p, False)["overflow"])
                    self.assertEqual(p.js(f"document.querySelector('{self.sel('[data-tile=health] .hpill')}').textContent"), self.store.read("projects", ref="ABC")["health"] or "Not set")
                    self.assertNotIn("words pending", p.js(f"document.querySelector('{self.sel()}').textContent").lower())


    def test_V8_a_built_in_label_is_whole_on_one_line_at_four_on_a_line_and_at_half_width(self):
        for half in (False, True):
            if half:
                self.make_half()
            for dark in (False, True):
                with self.subTest(half=half, dark=dark), chrome() as cdp:
                    p = self.page(cdp, 1400, dark)
                    got = p.js(f"""[...document.querySelectorAll('{self.sel('.tpl-gt-tile')}')].map(function(t){{ var k = t.querySelector('.tpl-gt-k'), r = k.getBoundingClientRect(), lh = parseFloat(getComputedStyle(k).lineHeight) || r.height;
                      return [k.textContent, k.scrollWidth > k.clientWidth, r.height <= lh * 1.5]; }})""")
                    self.assertEqual(len(got), 3)
                    for label, clipped, one in got:
                        self.assertFalse(clipped, f"{label}: cut")
                        self.assertTrue(one, f"{label}: one line")


class ViewHealth(Layout):
    """Where Project health sits in the order and what its tile shows."""

    def setUp(self):
        super().setUp()
        self.set_body({"v": 1})

    def test_K1_health_is_drawn_where_the_order_puts_it(self):
        for order, want in ((["overdue", "health", "risks", "decisions"], ["overdue", "health", "risks", "decisions"]),
                            (["overdue", "risks", "decisions", "health"], ["overdue", "risks", "decisions", "health"])):
            with self.subTest(order=order):
                self.set_body({"v": 1, "order": order})
                with chrome() as cdp:
                    got = self.cells(self.page(cdp), False)
                self.assertEqual(self.lines(got), [want])

    def test_K2_the_health_tile_has_the_projects_colour_and_reason(self):
        for health in ("On track", "At risk", "Off track"):
            with self.subTest(health=health):
                with self.store.step("dashboard", USER) as st:
                    st.update("projects", "ABC", {"health": health, "health_reason": "<p>Fictional reason</p>"})
                with chrome() as cdp:
                    p = self.page(cdp)
                    got = p.js(f"""(function(){{ var t = document.querySelector('{self.sel('[data-tile=health]')}');
                      return [t.querySelector('.hpill').className, t.querySelector('[data-fig=health]').className, (t.querySelector('.hreason') || {{}}).textContent || '']; }})()""")
                self.assertEqual(got, EXPECT_K2[health])


    def test_K3_3_on_a_line_is_a_third_of_the_row_each(self):
        self.set_body({"v": 1, "per_row": 3})
        with chrome() as cdp:
            got = self.cells(self.page(cdp), False)
        c = got["cells"]
        gap = c[1]["left"] - c[0]["right"]
        for cell in c[:3]:
            self.assertAlmostEqual(cell["width"], (got["grid"][2] - 2 * gap) / 3, delta=1.5)

    def test_K4_half_width_in_the_right_slot_shows_2_on_a_line(self):
        with chrome() as cdp:
            full = self.cells(self.page(cdp), False)["sec"]
        with self.store.step("dashboard", USER) as st:
            partner = st.create("report_sections", {"project": "ABC", "type": "text", "title": "Fictional partner", "sort_order": 997})
        status, got = self.real_change({"project": "ABC", "kind": KIND, "op": "update", "id": partner, "changes": {"beside": 1}})
        assert status == 200, got
        with chrome() as cdp:
            got = self.cells(self.page(cdp), False)
            self.assertEqual(self.lines(got), [["health", "overdue"], ["risks", "decisions"]])
            self.assertLess(got["sec"], full * 0.55)


EXPECT_K2 = {
    "On track": ["pill hpill g", "fig health-fig rag-g", "Fictional reason"],
    "At risk": ["pill hpill a", "fig health-fig rag-a", "Fictional reason"],
    "Off track": ["pill hpill r", "fig health-fig rag-r", "Fictional reason"],
}


class Edit(Layout):
    def toast(self, p):
        return p.js("(document.querySelector('.toast-text') || {}).textContent || ''")

    def test_E1_edit_draws_the_same_grid_and_the_two_controls_with_their_words(self):
        with chrome() as cdp:
            p = self.page(cdp, edit=True)
            got = self.cells(p, True)
            self.assertEqual(self.lines(got), [["health", "overdue", "risks", "decisions"]])
            names = p.js(f"[...document.querySelectorAll('{self.sel('.tpl-gt-opts [data-gt-per]')}')].map(b => [b.textContent, b.getAttribute('aria-pressed')])")
            self.assertEqual(names, [["3", "false"], ["4", "true"]])
            self.assertEqual(p.js(f"document.querySelector('{self.sel('.tpl-gt-opts [role=group]')}').getAttribute('aria-label')"), W_BESIDE)
            sw = p.js(f"(function(){{ var b = document.querySelector('{self.sel('.tpl-gt-opts [role=switch]')}'); return [b.textContent.trim(), b.getAttribute('aria-checked')]; }})()")
            self.assertEqual(sw, [W_OWN, "false"], "off by default")

    def test_E2_3_on_a_line_is_one_step_and_the_grid_follows(self):
        with chrome() as cdp:
            p = self.page(cdp, edit=True)
            before = self.applies()
            p.js(f"document.querySelector('{self.per(3)}').click()")
            self.assertTrue(wait(lambda: self.body().get("per_row") == 3, 10), f"stored: {self.body()}")
            self.assertEqual(self.applies(), before + 1)
            p.until(f"document.querySelector('{self.per(3)}').getAttribute('aria-pressed') === 'true'", "pressed")
            self.assertEqual(self.lines(self.cells(p, True)), [["health", "overdue", "risks"], ["decisions"]])
            p.js(f"document.querySelector('{self.per(4)}').click()")
            self.assertTrue(wait(lambda: "per_row" not in self.body(), 10), f"4 is the default and is not stored: {self.body()}")
            self.assertEqual(self.applies(), before + 2)
            p.js(f"document.querySelector('{self.per(4)}').click()")      # already 4: no step
            import time
            time.sleep(0.6)
            self.assertEqual(self.applies(), before + 2)

    def test_E2b_tiles_on_a_line_shows_no_toast(self):
        with chrome() as cdp:
            p = self.page(cdp, edit=True)
            p.js(f"document.querySelector('{self.per(3)}').click()")
            self.assertTrue(wait(lambda: self.body().get("per_row") == 3, 10), f"stored: {self.body()}")
            import time
            time.sleep(0.5)
            self.assertEqual(self.toast(p), "", "a layout setting says nothing")

    def test_E3_the_own_row_switch_is_one_step_with_its_two_toasts_and_undo(self):
        with chrome() as cdp:
            p = self.page(cdp, edit=True)
            before = self.applies()
            p.js(f"document.querySelector('{self.sel('[role=switch]')}').click()")
            self.assertTrue(wait(lambda: self.body().get("health") == {"own_row": True}, 10), f"stored: {self.body()}")
            self.assertEqual(self.applies(), before + 1)
            p.until("!!document.querySelector('[data-undo]')", "the toast")
            self.assertEqual(self.toast(p), "Project health sits on its own row")
            self.assertEqual(p.js(f"document.querySelector('{self.sel('[role=switch]')}').getAttribute('aria-checked')"), "true")
            got = self.cells(p, True)
            self.assertEqual(self.lines(got), [["health"], ["overdue", "risks", "decisions"]])
            self.assertAlmostEqual(got["cells"][0]["width"], got["grid"][2], delta=1.5)
            p.js(f"document.querySelector('{self.sel('[role=switch]')}').click()")
            self.assertTrue(wait(lambda: "health" not in self.body(), 10), f"stored: {self.body()}")
            p.until("document.querySelector('.toast-text') && document.querySelector('.toast-text').textContent === 'Project health sits with the tiles'", "the second toast")
            p.js("document.querySelector('[data-undo]').click()")
            self.assertTrue(wait(lambda: self.body().get("health") == {"own_row": True}, 10), f"undone: {self.body()}")

    def test_E4_the_eye_on_health_hides_it_completely_and_a_button_brings_it_back(self):
        with chrome() as cdp:
            p = self.page(cdp, edit=True)
            before = self.applies()
            p.js(f"document.querySelector('{self.sel('[data-tile=health] [data-tile-eye]')}').click()")
            self.assertTrue(wait(lambda: self.body().get("health") == {"shown": False}, 10), f"stored: {self.body()}")
            self.assertEqual(self.applies(), before + 1)
            p.until("!!document.querySelector('[data-undo]')", "the toast")
            self.assertEqual(self.toast(p), "Project health is hidden completely")
            self.assertFalse(p.js(f"!!document.querySelector('{self.sel('[data-tile=health]')}')"), "no health tile, not even a dimmed one")
            self.assertEqual(p.js(f"(document.querySelector('{self.sel('[data-gt-showhealth]')}') || {{}}).textContent"), SHOW_HEALTH)
            self.assertEqual(self.lines(self.cells(p, True)), [["overdue", "risks", "decisions"]])
            p.js(f"document.querySelector('{self.sel('[data-gt-showhealth]')}').click()")
            self.assertTrue(wait(lambda: "health" not in self.body(), 10), f"stored: {self.body()}")
            p.until("document.querySelector('.toast-text') && document.querySelector('.toast-text').textContent === 'Project health is shown'", "the second toast")
            p.until(f"!!document.querySelector('{self.sel('[data-tile=health]')}')", "the tile is back")
            self.assertFalse(p.js(f"!!document.querySelector('{self.sel('[data-gt-showhealth]')}')"))

    def test_E5_half_width_shows_2_on_a_line_in_edit_and_says_so(self):
        self.make_half()
        with chrome() as cdp:
            p = self.page(cdp, edit=True)
            got = self.cells(p, True)
            self.assertEqual(self.lines(got), [["health", "overdue"], ["risks", "decisions"]])
            self.assertLess(got["sec"], 700, "the half column")
            self.assertFalse(got["overflow"])
            self.assertEqual(p.js(f"(function(){{ var n = document.querySelector('{self.sel('[data-gt-halfnote]')}'); return n && n.offsetParent !== null ? n.textContent : null; }})()"), HALF_NOTE)

    def test_E10_half_width_in_the_right_slot_shows_2_on_a_line_in_edit_and_says_so(self):
        self.make_half_right()
        with chrome() as cdp:
            p = self.page(cdp, edit=True)
            self.assertTrue(p.js(f"!!document.querySelector('{self.sel()}.slot-right')"), "the glance is in the right slot")
            self.assertEqual(self.lines(self.cells(p, True)), [["health", "overdue"], ["risks", "decisions"]])
            self.assertEqual(p.js(f"(function(){{ var n = document.querySelector('{self.sel('[data-gt-halfnote]')}'); return n && n.offsetParent !== null ? n.textContent : null; }})()"), HALF_NOTE)

    def test_E9_a_built_in_label_is_whole_in_edit_at_four_on_a_line_and_at_half_width(self):
        for half in (False, True):
            if half:
                self.make_half()
            with self.subTest(half=half), chrome() as cdp:
                p = self.page(cdp, 1400, False, edit=True)
                got = p.js(f"""[...document.querySelectorAll('{self.sel('.glance .fig .k')}')].map(function(k){{ var r = k.getBoundingClientRect(); return [k.textContent.trim(), k.scrollWidth > k.clientWidth + 1, r.height]; }})""")
                self.assertEqual([g[0] for g in got], ["Project health", "Overdue actions", "High risks and issues", "Decisions needed"])
                for label, clipped, height in got:
                    self.assertFalse(clipped, f"{label}: cut")

    def test_E6_the_half_width_note_is_not_shown_at_full_width(self):
        with chrome() as cdp:
            p = self.page(cdp, edit=True)
            self.assertIsNone(p.js(f"(function(){{ var n = document.querySelector('{self.sel('[data-gt-halfnote]')}'); return n && n.offsetParent !== null ? n.textContent : null; }})()"))

    def test_E7_the_hint_keeps_the_app_words_and_adds_the_approved_sentences(self):
        with chrome() as cdp:
            p = self.page(cdp, edit=True)
            text = p.js(f"[...document.querySelectorAll('{self.sel('[data-glance-hint], [data-gt-hint]')}')].map(e => e.textContent).join(' ')")
            self.assertIn("Drag a tile to move it, or hold Alt and press an arrow key.", text)
            self.assertIn(HINT_EYE, text)
            self.assertIn(HINT_ADD, text)

    def test_E8_it_fits_at_1400_and_900_in_light_and_dark_in_edit(self):
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark), chrome() as cdp:
                    p = self.page(cdp, width, dark, edit=True)
                    got = self.cells(p, True)
                    self.assertFalse(got["overflow"])
                    if width == 900:       # mock-up checked: ag-edit-900.png; the builder default is perRow:4, hrow:false (at-a-glance-builder.html:485) and the column count is --cols = perRow (:539) with no 900 override, so the default page keeps its tiles sharing one row at 900, as at 1400
                        self.assertEqual(self.lines(got), [["health", "overdue", "risks", "decisions"]])
                    self.assertNotIn("words pending", p.js(f"document.querySelector('{self.sel()}').textContent").lower())
                    self.assertTrue(p.js(f"[...document.querySelectorAll('{self.sel('.tpl-gt-opts button')}')].every(b => b.getBoundingClientRect().height >= 24)"), "the controls are big enough to hit")

    def test_E9_at_900_edit_keeps_the_three_tile_columns_with_health_on_its_own_row(self):
        # mock-up checked: ag-edit-900.png (images folder of the 1264 mock-up): health on its own row, then three tiles a row
        self.set_body({"v": 1, "per_row": 3, "health": {"shown": True, "own_row": True}})
        for dark in (False, True):
            with self.subTest(dark=dark), chrome() as cdp:
                got = self.cells(self.page(cdp, 900, dark, edit=True), True)
                self.assertEqual(self.lines(got), [["health"], ["overdue", "risks", "decisions"]])
                self.assertFalse(got["overflow"])

    def test_E11_at_900_in_edit_a_half_slot_glance_draws_one_tile_a_line_in_both_slots_and_full_width_shares_a_row(self):
        # mock-up checked: README.md of the 1264 mock-up: at 900 half does nothing, shell.css puts every slot in one column; edit tiles do not fit twice in a half column (ag-edit-half.png)
        one = [["health"], ["overdue"], ["risks"], ["decisions"]]
        with self.subTest(slot="full"), chrome() as cdp:
            self.assertEqual(self.lines(self.cells(self.page(cdp, 900, False, edit=True), True)), [["health", "overdue", "risks", "decisions"]])
        for slot in ("left", "right"):
            with self.subTest(slot=slot), chrome() as cdp:
                self.make_half() if slot == "left" else self.make_half_right()
                p = self.page(cdp, 900, False, edit=True)
                self.assertTrue(p.js(f"!!document.querySelector('{self.sel()}.slot-{slot}')"), f"the glance is in the {slot} slot")
                self.assertEqual(self.lines(self.cells(p, True)), one)

    def test_E10_a_half_glance_at_900_in_edit_stays_one_column(self):
        # mock-up checked: ag-edit-900.png; the README says 250 px tiles do not fit twice in a half column, so a half slot is one column
        self.make_half()
        with chrome() as cdp:
            got = self.cells(self.page(cdp, 900, False, edit=True), True)
        self.assertEqual(self.lines(got), [["health"], ["overdue"], ["risks"], ["decisions"]])


class Sketch(unittest.TestCase):
    def test_the_library_card_sketch_has_three_low_tiles_edged_red_amber_green_in_that_order(self):
        text = (SRC / "clark" / "page" / "src" / "logic" / "templates.js").read_text(encoding="utf-8")
        line = next(l for l in text.splitlines() if l.strip().startswith('"glance-template":'))
        self.assertIn("grid-template-columns:repeat(3,1fr)", line)
        self.assertEqual(re.findall(r"var\(--status-(\w+)\)", line), ["red", "amber", "green"])
        self.assertEqual(line.count("border-top:3px solid"), 3, "each low tile has the same edge")

    def test_help_has_the_card_row_with_the_ruled_words_and_the_widths(self):
        rows = json.loads((SRC / "clark" / "page" / "src" / "help" / "helpContent.json").read_text(encoding="utf-8"))
        found = []
        def walk(x):
            if isinstance(x, list):
                if len(x) == 3 and x[0] == "Project at a glance":
                    found.append(x)
                for y in x:
                    walk(y)
            elif isinstance(x, dict):
                for y in x.values():
                    walk(y)
        walk(rows)
        self.assertEqual(found, [["Project at a glance", "Three counts, an optional project health and tiles of your own.", "Full or half"]])


if __name__ == "__main__":
    unittest.main()
