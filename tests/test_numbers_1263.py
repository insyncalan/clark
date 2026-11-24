"""Row 1263: one Numbers card for three or four numbers (mock-up mockups/1263-numbers-template, approved 18-11-2026).

Stored data first: a section of the old type figures3 or figures4 (body {"v":1,"figures":[...]}, no count) is read by the one
card as before: checked, published, drawn and exported the same; a new body may carry "count": 3 or 4. Then the page: the pure
reader (figures.js), the card in the library, and the Classic Edit (count control "Numbers 3 | 4", a Typed | Live switch per
number) at 1400 and 900 px, light and dark. Cards keeps its Edit as it was. Fictional data only.

Run: python3 dev/run_tests.py test_numbers_1263
"""
import contextlib
import json
import unittest

from _demo import USER
from _tpl_figures import bare_page, live, typed
from clark import changes, docx_build, excel_client, page, publish, section_bodies, section_kinds, store as store_module, theme
from clark.section_kinds import base, figures3, figures4
import _testpage as testpage
from _real_server import real_server
from test_changes import Api
from test_report_editor import Base, tearDownModule  # noqa: F401
from test_server import Running, chrome, wait
import test_reportheadline_export_1261 as ex


class Rules:
    plain = visible = staticmethod(lambda t: t)


def body(*slots, **more):
    return {"v": 1, **more, "figures": list(slots)}


FOUR = [typed(label=f"L{i}", value=str(i)) for i in range(4)]


class Stored(unittest.TestCase):
    """Ticket line 3 (no migration): the one card reads figures3 and figures4 bodies as they were stored."""

    def test_an_old_body_without_a_count_is_checked_and_stored_exactly_as_before(self):
        for mod, n in ((figures4, 4), (figures3, 3)):
            got = mod.check(body(*FOUR[:n]), Rules)
            self.assertEqual(got, {"v": 1, "figures": FOUR[:n]})
            self.assertNotIn("count", got)

    def test_an_old_body_keeps_its_old_limit_by_type(self):
        with self.assertRaises(base.Bad):
            figures3.check(body(*FOUR), Rules)
        with self.assertRaises(base.Bad):
            figures4.check(body(*FOUR, typed()), Rules)

    def test_a_count_of_three_or_four_is_stored_and_sets_the_limit(self):
        for mod in (figures4, figures3):
            self.assertEqual(mod.check(body(*FOUR, count=4), Rules)["count"], 4)
            self.assertEqual(mod.check(body(*FOUR[:3], count=3), Rules), {"v": 1, "count": 3, "figures": FOUR[:3]})
            self.assertEqual(mod.check(body(count=3), Rules), {"v": 1, "count": 3, "figures": []})
            with self.assertRaises(base.Bad):
                mod.check(body(*FOUR, count=3), Rules)

    def test_a_count_that_is_not_three_or_four_is_refused_without_quoting_it(self):
        for bad in (2, 5, 0, -3, "3", 3.0, True, None, [3], {"n": 3}):
            with self.subTest(bad=bad), self.assertRaises(base.Bad) as got:
                figures4.check(body(typed(), count=bad), Rules)
            self.assertEqual(str(got.exception), figures4.BAD_SHAPE)

    def test_an_unknown_key_is_still_refused(self):
        with self.assertRaises(base.Bad):
            figures4.check(body(typed(), colour="red"), Rules)

    def test_the_registry_reads_both_old_types_and_the_page_catalogue_keeps_both_parts(self):
        self.assertIs(section_kinds.REGISTRY["figures3"], figures3)
        self.assertIs(section_kinds.REGISTRY["figures4"], figures4)
        self.assertEqual((figures3.PLACES, figures4.PLACES), (3, 4))


class Published(unittest.TestCase):
    AS_AT = "2030-01-15"

    def pub(self, type_, value):
        return section_bodies.published(type_, value, base.Context({}, self.AS_AT))

    def test_an_old_body_publishes_exactly_as_before_with_no_count_in_the_entry(self):
        for type_, n in (("figures4", 4), ("figures3", 3)):
            got = self.pub(type_, body(*FOUR[:n]))
            self.assertEqual(set(got), {"figures"})
            self.assertEqual([f["label"] for f in got["figures"]], [f"L{i}" for i in range(n)])

    def test_a_body_with_a_count_publishes_the_count_and_no_more_than_it(self):
        got = self.pub("figures4", body(*FOUR[:3], count=3))
        self.assertEqual((got["count"], len(got["figures"])), (3, 3))
        got = self.pub("figures3", body(*FOUR, count=4))
        self.assertEqual((got["count"], len(got["figures"])), (4, 4))

    def test_a_count_only_body_is_left_out_like_an_empty_template(self):
        self.assertIsNone(self.pub("figures4", body(count=3)))
        self.assertIsNone(self.pub("figures4", body()))

    def test_a_count_smaller_than_the_stored_figures_publishes_only_the_count(self):
        raw = {"v": 1, "count": 3, "figures": FOUR}      # not a checked body: published never trusts more than it must
        self.assertEqual(len(self.pub("figures4", raw)["figures"]), 3)

    def test_a_count_that_is_not_three_or_four_publishes_the_places_of_its_type(self):
        for type_, places in (("figures3", 3), ("figures4", 4)):
            for bad in (9, "4", True):
                with self.subTest(type=type_, count=bad):
                    got = self.pub(type_, {"v": 1, "count": bad, "figures": FOUR})      # not a checked body
                    self.assertEqual((len(got["figures"]), "count" in got), (min(places, 4), True))


class ThroughTheStore(Api):
    def setUp(self):
        super().setUp()
        self.demo.plant_builtin_sections()

    def section(self, type_, value):
        ref = self.ok("new", values={"type": type_, "title": "Numbers"})["ref"]
        if value is not None:
            status, got = self.change(self.req(changes.UPDATE, id=ref, changes={"body": json.dumps(value)}))
            self.assertEqual((status, got.get("message")), (200, None), got)
        return ref

    def entry(self, ref):
        built = publish.build(self.s, "ABC", now="2030-01-15")
        return next(s for s in built["published"]["sections"] if s["id"] == ref)

    def test_an_old_figures3_and_an_old_figures4_section_publish_the_same_entry_as_before(self):
        three, four = self.section("figures3", body(*FOUR[:3])), self.section("figures4", body(*FOUR))
        self.assertNotIn("count", self.entry(three))
        self.assertNotIn("count", self.entry(four))
        self.assertEqual(len(self.entry(three)["figures"]), 3)
        self.assertEqual(len(self.entry(four)["figures"]), 4)

    def test_a_new_numbers_section_with_a_count_of_three_is_saved_and_published_with_the_count(self):
        ref = self.section("figures4", body(*FOUR[:3], count=3))
        got = self.entry(ref)
        self.assertEqual((got["count"], len(got["figures"])), (3, 3))

    def test_an_old_figures3_section_can_be_switched_to_four_without_changing_its_type(self):
        ref = self.section("figures3", body(*FOUR[:3]))
        status, got = self.change(self.req(changes.UPDATE, id=ref, changes={"body": json.dumps(body(*FOUR, count=4))}))
        self.assertEqual(status, 200, got)
        self.assertEqual(self.s.read("report_sections", ref=ref)["type"], "figures3")
        self.assertEqual(len(self.entry(ref)["figures"]), 4)

    def test_a_body_over_its_count_is_refused_and_leaves_the_record_alone(self):
        ref = self.section("figures4", body(*FOUR[:3], count=3))
        before = self.s.read("report_sections", ref=ref)["body"]
        status, got = self.change(self.req(changes.UPDATE, id=ref, changes={"body": json.dumps(body(*FOUR, count=3))}))
        self.assertEqual((status, got["ok"]), (400, False))
        self.assertEqual(self.s.read("report_sections", ref=ref)["body"], before)

    def test_one_count_change_is_one_step_and_one_undo(self):
        ref = self.section("figures4", body(*FOUR))
        before = self.snapshot()[0]
        status, got = self.change(self.req(changes.UPDATE, id=ref, changes={"body": json.dumps(body(*FOUR[:3], count=3))}))
        self.assertEqual((status, self.snapshot()[0]), (200, before + 1))
        self.assertEqual(self.undone(got["apply_id"])[0], 200)
        self.assertEqual(json.loads(self.s.read("report_sections", ref=ref)["body"]), json.loads(section_bodies.check("figures4", json.dumps(body(*FOUR)), store_module.BODY_RULES)))

    def undone(self, apply_id):
        return self.undo({"project": "ABC", "apply_id": apply_id})

    def test_word_and_excel_do_not_draw_either_type_and_a_count_changes_nothing_there(self):
        """Fact (read, then pinned): docx_build.sections() draws only the types in TITLES and the workbook has no sheet for these two."""
        self.assertNotIn("figures4", docx_build.TITLES)
        self.assertNotIn("figures3", docx_build.TITLES)
        plain = ex.select()
        with_numbers = ex.select()
        for entry in ({"id": "n1", "type": "figures4", "title": "Numbers", "figures": [], "count": 3},
                      {"id": "n2", "type": "figures3", "title": "Numbers", "figures": []}):
            with_numbers["sections"] = list(with_numbers["sections"]) + [entry]
        self.assertEqual(ex.doc_xml(docx_build.build(plain)), ex.doc_xml(docx_build.build(with_numbers)))
        self.assertEqual(ex.sheet(plain).sheetnames, ex.sheet(with_numbers).sheetnames)


class PageSide(unittest.TestCase):
    """figures.js: the one reader."""

    @classmethod
    def setUpClass(cls):
        cls.stack = contextlib.ExitStack()
        cls.server = Running(page_html=bare_page)
        cls.stack.callback(cls.server.close)
        cls.cdp = cls.stack.enter_context(chrome())
        tid = next(t["targetId"] for t in cls.cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        cls.sid = cls.cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    def setUp(self):
        self.cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.server.port}/"}, self.sid)
        self.assertTrue(wait(lambda: self.cdp.js("!!(window.F && window.F.figures)", self.sid)), "the test bundle ran")

    def val(self, expr):
        got = self.cdp.js(f"(function(){{ try {{ return JSON.stringify({expr}); }} catch (e) {{ return 'ERROR ' + e.message; }} }})()", self.sid)
        self.assertIsNotNone(got, expr)
        self.assertFalse(got.startswith("ERROR"), f"{expr}: {got}")
        return json.loads(got)

    def data(self):
        return {"project": {"code": "ABC"}, "actions": [], "raid": [], "decisions": [], "milestones": [], "use_cases": [], "labels": {}, "report_sections": []}

    def test_the_count_is_the_bodys_when_it_has_one_and_the_types_when_it_has_not(self):
        cases = [("figures4", json.dumps(body()), 4), ("figures3", json.dumps(body()), 3), ("figures4", "", 4), ("figures3", "", 3),
                 ("figures4", json.dumps(body(count=3)), 3), ("figures3", json.dumps(body(count=4)), 4),
                 ("figures4", json.dumps(body(count=5)), 4), ("figures3", json.dumps(body(count="4")), 3), ("figures4", "{", 4)]
        for type_, b, want in cases:
            with self.subTest(type=type_, body=b):
                self.assertEqual(self.val(f"F.figures.countOf({json.dumps({'body': b})}, {json.dumps(type_)})"), want)

    def test_a_published_entry_names_its_count_and_an_old_one_falls_back_to_its_type(self):
        self.assertEqual(self.val("F.figures.countOf({figures: [], count: 3}, 'figures4')"), 3)
        self.assertEqual(self.val("F.figures.countOf({figures: []}, 'figures3')"), 3)
        self.assertEqual(self.val("F.figures.countOf({figures: [], count: 9}, 'figures4')"), 4)

    def test_the_figures_drawn_follow_the_count(self):
        sec = {"id": "S", "type": "figures4", "body": json.dumps({"v": 1, "count": 3, "figures": FOUR})}        # not a checked body: the reader still keeps to its count
        got = self.val(f"F.figures.figuresOf({json.dumps(sec)}, {json.dumps(self.data())}, '2030-01-15', F.figures.countOf({json.dumps(sec)}, 'figures4'))")
        self.assertEqual([f["label"] for f in got], ["L0", "L1", "L2"])

    def test_body_of_writes_the_count_when_given_and_nothing_extra_when_not(self):
        self.assertEqual(json.loads(self.val("F.figures.bodyOf([{mode:'live',metric:'risks'}], 3)")), {"v": 1, "count": 3, "figures": [live("risks")]})
        self.assertEqual(json.loads(self.val("F.figures.bodyOf([{mode:'live',metric:'risks'}])")), {"v": 1, "figures": [live("risks")]})

    def test_an_empty_body_keeps_a_count_that_is_not_the_types_own_and_drops_the_one_that_is(self):
        empty = "{mode:'typed',label:'',value:'',detail:'',asof:''}"
        self.assertEqual(json.loads(self.val(f"F.figures.bodyOf([{empty}], 3, 'figures4')")), {"v": 1, "count": 3, "figures": []})
        self.assertEqual(self.val(f"F.figures.bodyOf([{empty}], 4, 'figures4')"), "")
        self.assertEqual(self.val(f"F.figures.bodyOf([{empty}], 3, 'figures3')"), "")


class Classic(Base):
    """The Edit and View of the one card, in the Classic theme (the look is Classic only; Cards keeps its Edit)."""

    def setUp(self):
        super().setUp()
        self.demo.plant_builtin_sections()      # a new project's lists are Work items lists; the live figures count the built-in sections' rows (row 1193)
        self.s.close()
        css = theme.css("prototype-2.0")
        self.s = real_server(self.store.path, self.store.data_for, page_html=lambda: page.layer_theme(testpage.html(), css), seam=self.seam)
        self.addCleanup(self.s.close)

    def add(self, type_, value, order=990):
        with self.store.step("dashboard", USER) as st:
            ref = st.create("report_sections", {"project": "ABC", "type": type_, "title": "Fictional numbers", "sort_order": order})
            if value is not None:
                st.update("report_sections", ref, {"body": store_module.check_section_body(type_, json.dumps(value))})
        return ref

    def stored(self, ref):
        raw = self.store.read("report_sections", ref=ref)["body"]
        return json.loads(raw) if raw else raw

    def sized(self, cdp, width, theme_):
        p = self.visit(cdp)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        p.js(f"document.documentElement.dataset.theme = {json.dumps(theme_)}")
        return p

    def sec(self, ref, rest=""):
        return f"[data-id={json.dumps(ref)}] {rest}".strip()

    def edit(self, p, ref):
        p.edit()
        p.until(f"!!document.querySelector('{self.sec(ref, '[data-slot]')}')", "the places")

    def pressed(self, p, ref, group):
        return p.js(f"Array.from(document.querySelectorAll('{self.sec(ref, group + ' button')}')).filter(b => b.getAttribute('aria-pressed') === 'true').map(b => b.textContent).join()")

    # --- View: old sections draw as before, at 1400 and 900 ---------------------------------------------------------------------
    def test_an_old_figures3_and_an_old_figures4_section_draw_three_and_four_across_and_are_not_rewritten(self):
        three, four = self.add("figures3", body(*FOUR[:3]), 990), self.add("figures4", body(*FOUR), 991)
        was = (self.stored(three), self.stored(four))
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.sized(cdp, width, "light")
                p.until(f"!!document.querySelector('{self.sec(four, '.tpl-figs')}')", "drawn")
                for ref, n in ((three, 3), (four, 4)):
                    self.assertEqual(p.js(f"document.querySelectorAll('{self.sec(ref, '[data-fig=figure]')}').length"), n)
                    self.assertEqual(p.js(f"document.querySelector('{self.sec(ref, '.tpl-figs')}').className"), f"tpl-figs n{n}")
                    cols = p.js(f"getComputedStyle(document.querySelector('{self.sec(ref, '.tpl-figs')}')).gridTemplateColumns.split(' ').length")
                    self.assertEqual(cols, n, f"{n} columns at {width}")
                p.edit()
                p.until(f"!!document.querySelector('{self.sec(four, '[data-slot]')}')", "Edit")
                self.assertEqual(self.pressed(p, three, ".num-count"), "3")
                self.assertEqual(self.pressed(p, four, ".num-count"), "4")
        self.assertEqual((self.stored(three), self.stored(four)), was, "opening, drawing and editing did not write")

    def test_a_new_numbers_section_with_a_count_of_three_draws_three_wider_columns(self):
        ref = self.add("figures4", body(*FOUR[:3], count=3))
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.sized(cdp, width, "light")
                p.until(f"!!document.querySelector('{self.sec(ref, '.tpl-figs')}')", "drawn")
                self.assertEqual(p.js(f"document.querySelector('{self.sec(ref, '.tpl-figs')}').className"), "tpl-figs n3")
                self.assertEqual(p.js(f"document.querySelectorAll('{self.sec(ref, '[data-fig=figure]')}').length"), 3)

    # --- Edit: the count control ------------------------------------------------------------------------------------------------
    def test_the_count_control_is_numbers_3_4_and_choosing_3_keeps_three_places_in_one_step(self):
        ref = self.add("figures4", body(*FOUR))
        with chrome() as cdp:
            p = self.sized(cdp, 1400, "light")
            self.edit(p, ref)
            self.assertEqual(p.js(f"Array.from(document.querySelectorAll('{self.sec(ref, '.num-bar .num-bar-l, .num-bar button')}')).map(e => e.textContent).join(' ')"), "Numbers 3 4")
            self.assertEqual(p.js(f"document.querySelector('{self.sec(ref, '.num-bar')}').getAttribute('aria-label')"), None)
            self.assertEqual(p.js(f"document.querySelectorAll('{self.sec(ref, '.num-bar [aria-label]')}').length"), 1)       # the one name is the count group's
            self.assertEqual(p.js(f"document.querySelector('{self.sec(ref, '.num-count')}').getAttribute('aria-label')"), "How many numbers")
            self.assertEqual(p.js(f"document.querySelectorAll('{self.sec(ref, '[data-slot]')}').length"), 4)
            self.assertEqual(self.pressed(p, ref, ".num-count"), "4")
            steps = self.store.con.execute("SELECT count(*) FROM applies").fetchone()[0]
            p.js(f"Array.from(document.querySelectorAll('{self.sec(ref, '.num-count button')}')).find(b => b.textContent === '3').click()")
            p.saved()
            self.assertEqual(self.store.con.execute("SELECT count(*) FROM applies").fetchone()[0], steps + 1, "one step")
            self.assertEqual(self.stored(ref), {"v": 1, "count": 3, "figures": FOUR[:3]})
            p.until(f"document.querySelectorAll('{self.sec(ref, '[data-slot]')}').length === 3", "three places")
            self.assertEqual(self.pressed(p, ref, ".num-count"), "3")
            p.clear_toast()
            p.js(f"Array.from(document.querySelectorAll('{self.sec(ref, '.num-count button')}')).find(b => b.textContent === '4').click()")
            p.saved()
            self.assertEqual(self.stored(ref)["count"], 4)
            p.until(f"document.querySelectorAll('{self.sec(ref, '[data-slot]')}').length === 4", "four places")

    def test_the_count_control_on_an_old_figures3_section_switches_it_to_four_and_it_stays_a_figures3_type(self):
        ref = self.add("figures3", body(*FOUR[:3]))
        with chrome() as cdp:
            p = self.sized(cdp, 1400, "light")
            self.edit(p, ref)
            p.js(f"Array.from(document.querySelectorAll('{self.sec(ref, '.num-count button')}')).find(b => b.textContent === '4').click()")
            p.saved()
            self.assertEqual(self.stored(ref), {"v": 1, "count": 4, "figures": FOUR[:3]})
            self.assertEqual(self.store.read("report_sections", ref=ref)["type"], "figures3")

    def test_the_count_choice_on_an_empty_section_is_kept(self):
        ref = self.add("figures4", None)
        with chrome() as cdp:
            p = self.sized(cdp, 1400, "light")
            self.edit(p, ref)
            p.js(f"Array.from(document.querySelectorAll('{self.sec(ref, '.num-count button')}')).find(b => b.textContent === '3').click()")
            p.saved()
            self.assertEqual(self.stored(ref), {"v": 1, "count": 3, "figures": []})

    # --- Edit: Typed | Live per number ---------------------------------------------------------------------------------------------
    def test_each_number_has_a_typed_live_switch_then_its_fields(self):
        self.demo.action(due_date="2030-01-01", description="Fictional late action")
        ref = self.add("figures4", body(live("overdue"), typed(), count=4))
        with chrome() as cdp:
            p = self.sized(cdp, 1400, "light")
            self.edit(p, ref)
            slot = lambda i: self.sec(ref, f'[data-slot="{i}"]')
            self.assertEqual(p.js(f"Array.from(document.querySelectorAll('{slot(0)} .num-source button')).map(b => b.textContent).join()"), "Typed,Live")
            self.assertEqual(self.pressed(p, ref, '[data-slot="0"] .num-source'), "Live")
            self.assertEqual(self.pressed(p, ref, '[data-slot="1"] .num-source'), "Typed")
            self.assertEqual(p.js(f"document.querySelector('{slot(0)} legend').textContent"), "Number 1")
            self.assertIn("Worked out from the project each time. Now:", p.js(f"document.querySelector('{slot(0)}').textContent"))
            self.assertFalse(p.js(f"!!document.querySelector('{slot(0)} [aria-label=\"Figure 1 label\"]')"), "a live number has no typed fields")
            self.assertEqual(p.js(f"document.querySelector('{slot(0)} select[aria-label=\"Figure 1 live figure\"]').value"), "overdue")
            self.assertTrue(p.js(f"!!document.querySelector('{slot(1)} [aria-label=\"Figure 2 label\"]')"))
            p.js(f"Array.from(document.querySelectorAll('{slot(1)} .num-source button')).find(b => b.textContent === 'Live').click()")
            p.saved()
            p.clear_toast()
            self.assertEqual(self.stored(ref)["figures"][1], {"mode": "live", "metric": "overdue"})
            self.assertEqual(self.stored(ref)["count"], 4, "the count is kept")
            p.until(f"!!document.querySelector('{slot(1)} select[aria-label=\"Figure 2 live figure\"]')", "live fields")
            p.js(f"Array.from(document.querySelectorAll('{slot(1)} .num-source button')).find(b => b.textContent === 'Typed').click()")
            p.saved()
            self.assertEqual(self.stored(ref)["figures"], [live("overdue")], "a blank typed place is not stored; the count is kept")
            self.assertEqual(self.stored(ref)["count"], 4)

    def test_pressing_the_button_already_pressed_does_nothing_and_an_edit_never_gives_an_old_body_a_count(self):
        ref = self.add("figures4", body(*FOUR[:2]))
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.sized(cdp, width, "light")
                self.edit(p, ref)
                click = lambda sel, name: p.js(f"Array.from(document.querySelectorAll('{self.sec(ref, sel)}')).find(b => b.textContent === '{name}').click()")
                steps = self.store.con.execute("SELECT count(*) FROM applies").fetchone()[0]
                click(".num-count button", "4")                       # already pressed: no step
                click('[data-slot="0"] .num-source button', "Typed")  # already pressed: no step
                self.assertEqual(self.stored(ref), body(*FOUR[:2]))
                self.assertEqual(self.store.con.execute("SELECT count(*) FROM applies").fetchone()[0], steps, "a re-press is no step")
                click('[data-slot="2"] .num-source button', "Live")   # a real edit of an old body: saved without a count
                p.saved()
                self.assertEqual(self.stored(ref), body(*FOUR[:2], live("overdue")), "no count written into an old body")
                self.assertEqual(self.store.con.execute("SELECT count(*) FROM applies").fetchone()[0], steps + 1)
                with self.store.step("dashboard", USER) as st:        # back to the old body for the next width
                    st.update("report_sections", ref, {"body": store_module.check_section_body("figures4", json.dumps(body(*FOUR[:2])))})

    # --- Edit: the look, measured against the mock-up at 1400 and 900, light and dark ---------------------------------------------
    def test_the_count_and_source_switches_are_the_mock_ups_size_in_light_and_dark_at_1400_and_900(self):
        ref = self.add("figures4", body(typed(), count=4))
        for width, theme_ in ((1400, "light"), (1400, "dark"), (900, "light"), (900, "dark")):
            with self.subTest(width=width, theme=theme_), chrome() as cdp:
                p = self.sized(cdp, width, theme_)
                self.edit(p, ref)
                got = p.js(f"""(function(){{ var out = {{}};
                  [['count', '{self.sec(ref, '.num-count')}'], ['source', '{self.sec(ref, '[data-slot="0"] .num-source')}']].forEach(function(x){{
                    var seg = document.querySelector(x[1]), bs = seg.querySelectorAll('button'), c = getComputedStyle(seg), b = getComputedStyle(bs[0]), on = getComputedStyle(seg.querySelector('[aria-pressed=true]'));
                    out[x[0]] = {{h: bs[0].getBoundingClientRect().height, w: bs[0].getBoundingClientRect().width, radius: c.borderTopLeftRadius, border: c.borderTopWidth + ' ' + c.borderTopColor,
                                  fs: b.fontSize, fw: on.fontWeight, bg: on.backgroundColor, bgoff: getComputedStyle(seg.querySelector('[aria-pressed=false]')).backgroundColor, n: bs.length}}; }});
                  var root = getComputedStyle(document.documentElement); out.edge = root.getPropertyValue('--control-edge').trim(); out.tint = root.getPropertyValue('--brand-blue-tint').trim();
                  return out; }})()""")
                for k in ("count", "source"):
                    self.assertEqual((got[k]["h"], got[k]["fs"], got[k]["fw"], got[k]["radius"]), (32, "14px", "600", "8px"), k)
                    self.assertGreaterEqual(got[k]["w"], 40, k)
                    self.assertTrue(got[k]["border"].startswith("1px"), got[k]["border"])
                    self.assertNotEqual(got[k]["bg"], got[k]["bgoff"], "the pressed half is tinted")
                self.assertEqual(got["count"]["n"], 2)
                self.assertEqual(got["source"]["n"], 2)

    def test_nothing_overflows_at_900_with_four_numbers_in_edit(self):
        ref = self.add("figures4", body(*FOUR, count=4))
        with chrome() as cdp:
            p = self.sized(cdp, 900, "light")
            self.edit(p, ref)
            self.assertFalse(p.js("document.documentElement.scrollWidth > document.documentElement.clientWidth"), "no sideways scroll")

    def test_live_is_disabled_when_no_live_figure_is_offered_at_1400_and_900(self):
        ref = self.add("figures4", body(typed(), count=4))
        with self.store.step("dashboard", USER) as st:
            for r in self.store.read("report_sections", "ABC"):
                if r["type"] in ("actions", "raid", "decisions"):
                    st.update("report_sections", r["id"], {"hidden": 1})
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.sized(cdp, width, "light")
                self.edit(p, ref)
                state = p.js(f"Array.from(document.querySelectorAll('{self.sec(ref, '[data-slot=\"0\"] .num-source button')}')).map(b => b.textContent + ':' + b.disabled).join()")
                self.assertEqual(state, "Typed:false,Live:true")

    def test_a_number_already_live_keeps_live_enabled_when_no_live_figure_is_offered(self):
        ref = self.add("figures4", body(live("overdue"), typed(), count=4))
        with self.store.step("dashboard", USER) as st:
            for r in self.store.read("report_sections", "ABC"):
                if r["type"] in ("actions", "raid", "decisions"):
                    st.update("report_sections", r["id"], {"hidden": 1})
        with chrome() as cdp:
            p = self.sized(cdp, 1400, "light")
            self.edit(p, ref)
            state = lambda i: p.js(f"Array.from(document.querySelectorAll('{self.sec(ref, f'[data-slot=\"{i}\"] .num-source button')}')).map(b => b.textContent + ':' + b.disabled).join()")
            self.assertEqual(state(0), "Typed:false,Live:false")
            self.assertEqual(state(1), "Typed:false,Live:true")

    # --- Cards keeps its Edit ---------------------------------------------------------------------------------------------------------
    def test_cards_keeps_its_edit_the_source_select_and_no_count_control(self):
        self.s.close()
        self.s = real_server(self.store.path, self.store.data_for, page_html=lambda: testpage.html(), seam=self.seam)
        ref = self.add("figures4", body(*FOUR))
        with chrome() as cdp:
            p = self.visit(cdp)
            self.edit(p, ref)
            self.assertFalse(p.js(f"!!document.querySelector('{self.sec(ref, '.num-bar')}')"))
            self.assertTrue(p.js(f"!!document.querySelector('{self.sec(ref, 'select[aria-label=\"Figure 1 source\"]')}')"))
            self.assertEqual(p.js(f"document.querySelector('{self.sec(ref, '[data-slot=\"0\"] legend')}').textContent"), "Figure 1")
            self.assertEqual(p.js(f"document.querySelectorAll('{self.sec(ref, '[data-slot]')}').length"), 4)


if __name__ == "__main__":
    unittest.main()
