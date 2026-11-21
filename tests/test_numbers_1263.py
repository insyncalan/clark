"""Row 1263: one Numbers card for three or four numbers (mock-up mockups/1263-numbers-template, approved 18-11-2026).

Stored data first: a section of the old type figures3 or figures4 (body {"v":1,"figures":[...]}, no count) is read by the one
card as before: checked, published, drawn and exported the same; a new body may carry "count": 3 or 4. Then the page: the pure
reader (figures.js) and the one card in the library (the Classic Edit is the next slice). Fictional data only.

Run: python3 dev/run_tests.py test_numbers_1263
"""
import contextlib
import json
import unittest

from _tpl_figures import bare_page, live, typed
from clark import changes, docx_build, publish, section_bodies, section_kinds, store as store_module
from clark.section_kinds import base, figures3, figures4
from test_changes import Api
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
