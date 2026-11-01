"""Shared by tests/test_tpl_figures4.py and tests/test_tpl_figures3.py (#96, G1): both Key figures templates keep one contract, so
one set of cases runs for each. Fictional data only."""
import contextlib
import json
import tempfile
import unittest
from pathlib import Path

from _demo import USER
from _paths import ROOT, SRC
from clark import changes, glance, publish, section_bodies, section_kinds, store as store_module
from clark.section_kinds import figures4 as _figures, base
from test_changes import Api
from test_report_editor import Base as PageBase
from test_server import Running, chrome, wait

PAGE_SRC = SRC / "clark" / "page" / "src"
DEMO = ROOT / "tests" / "fixtures" / "figures_demo.js"
MARK = "ZQ-FIGURE-MARK"
_PAGE = {}


def bare_page():
    if "html" not in _PAGE:
        import sys
        sys.path.insert(0, str(ROOT / "dev" / "tools"))
        import build_page
        import esbuild
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "t.js"
            done = esbuild.run(["--bundle", "--format=iife", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(DEMO), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            script = out.read_text(encoding="utf-8").replace("</script", "<\\/script")
        _PAGE["html"] = (f'<!doctype html>\n<html lang="en-GB"><head><meta charset="utf-8"><title>t</title></head>\n'
                         f'<body><div id="root"></div>\n<script>{script}</script>\n</body></html>\n')
    return _PAGE["html"]


def typed(label="Budget used", value="62%", detail="of the approved budget", asof="2030-01-10"):
    return {"mode": "typed", "label": label, "value": value, "detail": detail, "asof": asof}


def live(metric="overdue"):
    return {"mode": "live", "metric": metric}


def body(*slots):
    return json.dumps({"v": 1, "figures": list(slots)})


def make_cases(TYPE, PLACES):
    mod = section_kinds.REGISTRY[TYPE]

    class Contract(unittest.TestCase):
        def check(self, value, rules=None):
            return section_bodies.check(TYPE, value if isinstance(value, str) else json.dumps(value), rules or self.rules())

        def rules(self):
            return store_module.BODY_RULES

        def refused(self, value):
            with self.assertRaises(base.Bad) as got:
                self.check(value)
            self.assertNotIn(MARK, str(got.exception), "a refusal never quotes the value")
            return str(got.exception)

        def test_the_module_is_ready_with_the_right_places(self):
            self.assertIs(mod.READY, True)
            self.assertEqual(mod.PLACES, PLACES)
            self.assertEqual(section_bodies.EMPTY[TYPE], "")
            self.assertLessEqual(mod.LIMIT, 65536)

        def test_a_good_body_is_stored_canonical_and_saving_it_again_changes_nothing(self):
            once = self.check(body(typed(), live("risks")))
            self.assertEqual(self.check(once), once)
            self.assertEqual(json.loads(once), {"figures": [typed(), live("risks")], "v": 1})
            self.assertEqual(self.check(body()), json.dumps({"figures": [], "v": 1}, sort_keys=True, separators=(",", ":")))
            self.assertEqual(self.check(""), "")

        def test_a_number_may_arrive_as_a_number_and_is_kept_as_text(self):
            got = json.loads(self.check({"v": 1, "figures": [{"mode": "typed", "label": "Users", "value": 42}]}))
            self.assertEqual(got["figures"][0]["value"], "42")

        def test_hostile_bodies_are_refused_in_plain_words(self):
            cases = [
                {"v": 2, "figures": []}, {"figures": []}, {"v": 1, "figures": {}}, {"v": 1, "figures": [], "extra": 1}, [],
                {"v": 1, "figures": [typed()] * (PLACES + 1)},
                {"v": 1, "figures": ["x"]}, {"v": 1, "figures": [{"mode": "other"}]}, {"v": 1, "figures": [{}]},
                {"v": 1, "figures": [{"mode": "live", "metric": "budget"}]},
                {"v": 1, "figures": [{"mode": "live", "metric": "overdue", "label": MARK}]},
                {"v": 1, "figures": [typed(asof="2030-02-31")]}, {"v": 1, "figures": [typed(asof="15-01-2030")]},
                {"v": 1, "figures": [typed(label=MARK * 20)]}, {"v": 1, "figures": [typed(value=MARK * 10)]},
                {"v": 1, "figures": [typed(detail=MARK * 20)]},
                {"v": 1, "figures": [{"mode": "typed", "label": MARK, "value": ["x"]}]},
                {"v": 1, "figures": [{"mode": "typed", "label": MARK, "value": 1.5}]},
                {"v": 1, "figures": [{"mode": "typed", "label": MARK + "‮", "value": "1"}]},
                {"v": 1, "figures": [{"mode": "typed", "label": MARK + "\n", "value": "1"}]},
                {"v": 1, "figures": [{"mode": "typed", "label": MARK, "value": "1", "colour": "red"}]},
            ]
            for c in cases:
                with self.subTest(case=str(c)[:60]):
                    self.assertTrue(self.refused(c).endswith((".", "?")))
            for c in ("{", "null", "5", '"text"', "[1]", '{"v":1,"v":1,"figures":[]}', "x" * (mod.LIMIT + 1)):
                with self.subTest(raw=c[:20]):
                    self.refused(c)

        def test_markup_is_kept_as_text_never_as_markup(self):
            got = json.loads(self.check(body(typed(label="<b>Cost</b> <script>x</script>", value="1"))))
            self.assertEqual(got["figures"][0]["label"], "<b>Cost</b> <script>x</script>")

        def test_the_limit_fits_the_change_route(self):
            self.assertGreaterEqual(72 * 1024, mod.LIMIT + 8 * 1024)
            biggest = body(*[typed(label="é" * 60, value="é" * 30, detail="é" * 80)] * PLACES)
            self.assertLessEqual(len(self.check(biggest).encode("ascii")), mod.LIMIT)

    class Published(unittest.TestCase):
        AS_AT = "2030-01-15"

        def rows(self):
            return {"actions": [{"id": "ABC-A-001", "status": "Open", "due_date": "2030-01-01", "description": MARK},
                                {"id": "ABC-A-002", "status": "Open", "due_date": "2030-02-01", "description": MARK},
                                {"id": "ABC-A-003", "status": "Closed", "due_date": "2030-01-01", "description": MARK}],
                    "raid": [{"id": "ABC-R-001", "type": "Risk", "status": "Open", "priority": "High", "description": MARK},
                             {"id": "ABC-R-002", "type": "Issue", "status": "Open", "priority": "Medium", "description": MARK}],
                    "decisions": [{"id": "ABC-D-001", "status": "Pending", "needed_by": "2030-01-20", "decision": MARK}]}

        def pub(self, *slots, rows=None):
            return section_bodies.published(TYPE, json.loads(body(*slots)), base.Context(self.rows() if rows is None else rows, self.AS_AT))

        def test_live_figures_are_the_glance_figures_of_the_rows_kept(self):
            got = self.pub(live("overdue"), live("risks"), live("decisions"))["figures"][:PLACES]
            kept = {"rows": glance.work_rows(self.rows()), "hidden_types": set()}
            tiles = {t["tile"]: t for t in glance.tiles({"project": {}}, self.AS_AT, hidden=set(), for_client=True, kept=kept)}
            for f, name in zip(got, ("overdue", "risks", "decisions")):
                self.assertEqual((f["label"], f["value"], f["detail"], f["rag"]), (tiles[name]["title"], tiles[name]["value"], tiles[name]["detail"], tiles[name]["class"]))
            self.assertEqual((got[0]["value"], got[0]["detail"], got[0]["rag"]), (1, "of 2 open actions", "r"))
            self.assertEqual((got[1]["value"], got[1]["detail"], got[1]["rag"]), (1, "of 2 open risks and issues", "r"))

        def test_a_hidden_item_is_in_no_count_because_only_kept_rows_arrive(self):
            rows = self.rows()
            rows["actions"] = [r for r in rows["actions"] if r["id"] != "ABC-A-001"]      # publish.select dropped it
            self.assertEqual(self.pub(live("overdue"), rows=rows)["figures"][0]["value"], 0)

        def test_a_live_figure_with_no_row_of_its_kind_is_left_out_and_so_is_an_empty_template(self):
            self.assertIsNone(self.pub(live("overdue"), rows={"actions": [], "raid": [], "decisions": []}))
            self.assertIsNone(self.pub())
            self.assertIsNone(self.pub(typed(label="", value="", detail="", asof="")))
            self.assertIsNone(self.pub(typed(label="Only a label", value="")))
            self.assertIsNone(self.pub(typed(label="", value="5")))
            out = self.pub(live("overdue"), typed(), rows={"actions": [], "raid": [], "decisions": []})
            self.assertEqual([f["mode"] for f in out["figures"]], ["typed"])

        def test_a_typed_figure_carries_its_words_and_its_as_of_date_and_nothing_else(self):
            f = self.pub(typed(asof="2030-01-10"))["figures"][0]
            self.assertEqual(f, {"mode": "typed", "label": "Budget used", "value": "62%", "detail": "of the approved budget", "rag": "n", "asof": "2030-01-10"})

        def test_no_place_is_published_beyond_the_templates_places(self):
            raw = {"v": 1, "figures": [typed(label=f"L{i}", value=str(i)) for i in range(PLACES + 2)]}
            self.assertEqual(len(section_bodies.published(TYPE, raw, base.Context({}, self.AS_AT))["figures"]), PLACES)

        def test_nothing_of_an_items_words_is_ever_published(self):
            text = json.dumps(self.pub(live("overdue"), live("risks"), live("decisions")))
            self.assertNotIn(MARK, text)

        def test_a_bad_as_at_leaves_live_figures_out_instead_of_failing(self):
            self.assertIsNone(section_bodies.published(TYPE, json.loads(body(live())), base.Context(self.rows(), None)))

    class ThroughTheStore(Api):
        def section(self, *slots, title="Key figures", **more):
            ref = self.ok("new", values={"type": TYPE, "title": title}, **more)["ref"]
            if slots:
                status, got = self.change(self.req(changes.UPDATE, id=ref, changes={"body": body(*slots)}))
                self.assertEqual((status, got.get("message")), (200, None), got)
            return ref

        def plant(self):
            with self.s.step("dashboard", USER) as st:
                shown = st.create("actions", {"project": "ABC", "description": "Fictional shown action", "raised": "2030-01-01", "due_date": "2030-01-05", "source": "demo"})
                left = st.create("actions", {"project": "ABC", "description": f"{MARK} hidden", "raised": "2030-01-01", "due_date": "2030-01-05", "source": "demo"})
                st.create("report_hidden", {"project": "ABC", "item_id": left})
            return shown, left

        def figures(self, ref, now="2030-01-15"):
            built = publish.build(self.s, "ABC", now=now)
            text = built["body"].decode("utf-8")
            sec = next((s for s in built["published"]["sections"] if s["id"] == ref), None)
            return sec, text, built

        def test_one_save_is_one_step_and_one_undo(self):
            ref = self.section()
            before = self.snapshot()[0]
            status, got = self.change(self.req(changes.UPDATE, id=ref, changes={"body": body(typed())}))
            self.assertEqual(status, 200, got)
            self.assertEqual(self.snapshot()[0], before + 1)
            self.assertNotIn("body", got.get("sections", [{}])[0], "a reply never carries a body")
            self.assertEqual(self.undone(got["apply_id"])[0], 200)
            self.assertEqual(self.s.read("report_sections", ref=ref)["body"], "")

        def test_an_empty_template_and_one_with_a_half_filled_figure_stay_out_of_the_file(self):
            empty = self.section(title=f"Empty {MARK}")
            half = self.section(typed(label="Only a label", value=""), title=f"Half {MARK}")
            for ref in (empty, half):
                sec, text, _ = self.figures(ref)
                self.assertIsNone(sec)
            self.assertNotIn(MARK, self.figures(empty)[1])

        def test_the_file_carries_the_figures_and_never_a_hidden_item(self):
            self.plant()
            ref = self.section(live("overdue"), typed(), title="Key figures")
            sec, text, built = self.figures(ref)
            self.assertEqual([f["mode"] for f in sec["figures"]], ["live", "typed"])
            self.assertEqual(sec["figures"][0]["value"], 1, "the hidden action is not counted")
            self.assertNotIn(MARK, text)
            pub = built["published"]
            tiles = glance.tiles({"project": pub["data"]["project"]}, "2030-01-15", hidden=set(), for_client=True, kept=glance.kept_from(pub))
            self.assertEqual(sec["figures"][0]["value"], next(t for t in tiles if t["tile"] == "overdue")["value"])

        def test_a_live_figure_follows_the_rows_at_the_publish_day(self):
            self.plant()
            ref = self.section(live("overdue"))
            self.assertEqual(self.figures(ref, "2030-01-01")[0]["figures"][0]["value"], 0, "due 05-01-2030 is not yet overdue")
            self.assertEqual(self.figures(ref, "2030-02-01")[0]["figures"][0]["value"], 1)

        def test_a_hidden_section_is_not_in_the_file(self):
            ref = self.section(typed(label=f"Label {MARK}", value="5"))
            self.change(self.req(changes.UPDATE, id=ref, changes={"hidden": 1}))
            sec, text, _ = self.figures(ref)
            self.assertIsNone(sec)
            self.assertNotIn(MARK, text)

        def test_a_body_that_does_not_check_is_refused_and_leaves_the_record_alone(self):
            ref = self.section(typed())
            before = self.snapshot()
            for bad in ({"v": 1, "figures": [typed(asof="2030-13-01")]}, {"v": 1, "figures": [typed()] * (PLACES + 1)}, "{"):
                status, got = self.change(self.req(changes.UPDATE, id=ref, changes={"body": bad if isinstance(bad, str) else json.dumps(bad)}))
                self.assertEqual((status, got["ok"]), (400, False))
            self.assertEqual(self.snapshot(), before)

        def test_the_file_figures_are_text_and_whole_numbers_only(self):
            self.plant()
            ref = self.section(live("overdue"), typed(label="<img src=x onerror=alert(1)>", value="<b>1</b>"))
            sec, text, _ = self.figures(ref)
            self.assertNotIn("<img src=x", text)
            for f in sec["figures"]:
                self.assertTrue(all(isinstance(f[k], (str, int)) for k in f))

    class PageSide(unittest.TestCase):
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

        def data(self, **more):
            d = {"project": {"code": "ABC"}, "actions": [], "raid": [], "decisions": [], "milestones": [], "use_cases": [],
                 "labels": {}, "report_sections": []}
            d.update(more)
            return d

        def test_live_figures_in_the_page_match_those_publish_works_out(self):
            rows = Published.rows(None)
            full = {"actions": [dict(r, project="ABC", archived=0, client_visible=1) for r in rows["actions"]],
                    "raid": [dict(r, project="ABC", archived=0, client_visible=1) for r in rows["raid"]],
                    "decisions": [dict(r, project="ABC", archived=0, client_visible=1) for r in rows["decisions"]]}
            d = self.data(**full)
            page = self.val(f"F.figures.liveFigures({json.dumps(d)}, '2030-01-15')")
            kept = {"rows": glance.work_rows(rows), "hidden_types": set()}
            for t in glance.tiles({"project": {}}, "2030-01-15", hidden=set(), for_client=True, kept=kept):
                if t["tile"] in _figures.METRICS:
                    self.assertEqual({k: page[t["tile"]][k] for k in ("label", "value", "detail")},
                                     {"label": t["title"], "value": t["value"], "detail": t["detail"]}, t["tile"])
                    self.assertEqual(page[t["tile"]]["rag"], t["class"], t["tile"])

        def test_the_page_counts_only_rows_the_file_would_keep(self):
            base_row = {"project": "ABC", "archived": 0, "client_visible": 1, "status": "Open", "due_date": "2030-01-01", "description": "x"}
            actions = [dict(base_row, id="ABC-A-001"), dict(base_row, id="ABC-A-002", client_visible=0), dict(base_row, id="ABC-A-003", archived=1),
                       dict(base_row, id="ABC-A-004"), dict(base_row, id="ABC-A-005"), dict(base_row, id="ABC-A-006")]
            d = self.data(actions=actions, report_hidden=[{"item_id": "ABC-A-004"}], labels={"ABC-A-005": ["Sensitive"]},
                          label_rules=[], report_sections=[])
            got = self.val(f"F.figures.liveFigures({json.dumps(d)}, '2030-01-15')")
            self.assertEqual(got["overdue"]["value"], 2, "ABC-A-001 and ABC-A-006 only")
            self.assertNotIn("risks", got, "no rows of that kind: nothing to count")
            self.assertNotIn("decisions", got)

        def test_a_hidden_section_leaves_its_live_figure_out(self):
            d = self.data(actions=[{"id": "ABC-A-001", "project": "ABC", "archived": 0, "client_visible": 1, "status": "Open", "due_date": "2030-01-01"}],
                          report_sections=[{"id": "S", "type": "actions", "hidden": 1}])
            self.assertEqual(self.val(f"F.figures.liveFigures({json.dumps(d)}, '2030-01-15')"), {})

        def test_figures_of_a_served_section_and_of_a_file_section(self):
            sec = {"id": "S", "type": TYPE, "body": body(typed(), typed(label="", value="9"), {"mode": "typed", "label": "No number", "value": ""})}
            got = self.val(f"F.figures.figuresOf({json.dumps(sec)}, {json.dumps(self.data())}, '2030-01-15', {PLACES})")
            self.assertEqual([(f["label"], f["value"], f["asof"]) for f in got], [("Budget used", "62%", "10-01-2030")])
            filed = {"id": "S", "type": TYPE, "figures": [{"mode": "typed", "label": "A", "value": "1", "detail": "", "rag": "g", "asof": ""},
                                                          {"mode": "live", "label": "", "value": "", "rag": "r"}]}
            got = self.val(f"F.figures.figuresOf({json.dumps(filed)}, null, '2030-01-15', {PLACES})")
            self.assertEqual([(f["label"], f["rag"]) for f in got], [("A", "g")])

        def test_a_body_that_does_not_read_draws_nothing_and_is_empty(self):
            for b in ("", "{", "null", '{"v":1}', '{"figures":5}'):
                sec = {"id": "S", "type": TYPE, "body": b}
                self.assertEqual(self.val(f"F.figures.figuresOf({json.dumps(sec)}, {json.dumps(self.data())}, '2030-01-15', {PLACES})"), [], b)
                self.assertIs(self.val(f"F.empty({json.dumps(TYPE)}, {json.dumps(sec)}, {json.dumps(self.data())})"), True)

        def test_body_of_drops_trailing_empty_places_and_is_empty_for_none(self):
            self.assertEqual(self.val("F.figures.bodyOf([{mode:'typed',label:'',value:'',detail:'',asof:''}])"), "")
            got = json.loads(self.val("F.figures.bodyOf([{mode:'live',metric:'risks'},{mode:'typed',label:'',value:'',detail:'',asof:''}])"))
            self.assertEqual(got, {"v": 1, "figures": [live("risks")]})

        def test_the_page_part_is_ready(self):
            self.assertIs(self.val(f"F.parts.{TYPE}.ready"), True)

    class InThePage(PageBase):
        def add(self, *slots, title="Key figures"):
            with self.store.step("dashboard", USER) as st:
                ref = st.create("report_sections", {"project": "ABC", "type": TYPE, "title": title, "sort_order": 999})
                if slots:
                    st.update("report_sections", ref, {"body": store_module.check_section_body(TYPE, body(*slots))})
            return ref

        def test_view_draws_the_figures_and_leaves_an_empty_template_out(self):
            ref = self.add(typed())
            empty = self.add(title="Empty figures")
            with chrome() as cdp:
                p = self.visit(cdp)
                self.assertEqual(p.js(f"document.querySelectorAll('[data-id={json.dumps(ref)}] [data-fig=figure]').length"), 1)
                self.assertIn("Budget used", p.js(f"document.querySelector('[data-id={json.dumps(ref)}]').textContent"))
                self.assertIn("As of 10-01-2030", p.js(f"document.querySelector('[data-id={json.dumps(ref)}]').textContent"))
                self.assertFalse(p.js(f"!!document.querySelector('[data-id={json.dumps(empty)}]')"), "View: an empty template is not shown")
                self.assertIsNone(p.js(f"document.querySelector('[data-id={json.dumps(ref)}] [data-edit-only]')"))

        def test_edit_fills_a_figure_in_place_as_one_step_with_one_undo(self):
            ref = self.add()
            with chrome() as cdp:
                p = self.visit(cdp)
                p.edit()
                p.until(f"!!document.querySelector('[data-id={json.dumps(ref)}] [data-slot]')", "the places")
                self.assertEqual(p.js(f"document.querySelectorAll('[data-id={json.dumps(ref)}] [data-slot]').length"), PLACES)
                steps = self.store.con.execute("SELECT count(*) FROM applies").fetchone()[0]
                for name, text in (("label", "Users trained"), ("number", "120")):
                    p.js(f"(function(){{var el=document.querySelector('[data-id={json.dumps(ref)}] [aria-label=\"Figure 1 {name}\"]'); el.focus(); el.value={json.dumps(text)};"
                         "el.dispatchEvent(new Event('change', {bubbles: true}));})()")
                    p.saved()
                    p.clear_toast()
                self.assertEqual(self.store.con.execute("SELECT count(*) FROM applies").fetchone()[0], steps + 2, "one step for each field left")
                stored = json.loads(self.store.read("report_sections", ref=ref)["body"])
                self.assertEqual((stored["figures"][0]["label"], stored["figures"][0]["value"]), ("Users trained", "120"))
                p.until(f"document.querySelector('[data-id={json.dumps(ref)}] [data-fig=figure] .v')?.textContent === '120'", "the preview")
                p.view()
                self.assertIn("Users trained", p.js(f"document.querySelector('[data-id={json.dumps(ref)}]').textContent"))

        def test_a_half_filled_figure_says_it_stays_out(self):
            ref = self.add(typed(label="Only a label", value=""))
            with chrome() as cdp:
                p = self.visit(cdp)
                self.assertFalse(p.js(f"!!document.querySelector('[data-id={json.dumps(ref)}]')"), "View leaves it out")
                p.edit()
                p.until(f"!!document.querySelector('[data-id={json.dumps(ref)}] [data-slot]')", "Edit")
                self.assertIn("stays out of the published page", p.js(f"document.querySelector('[data-id={json.dumps(ref)}]').textContent"))

        def test_the_live_choice_is_saved_and_the_figure_is_the_tiles_number(self):
            self.demo.action(due_date="2030-01-01", description="Fictional late action")
            ref = self.add(live("overdue"))
            with chrome() as cdp:
                p = self.visit(cdp)
                self.assertIn("Overdue actions", p.js(f"document.querySelector('[data-id={json.dumps(ref)}]').textContent"))
                p.edit()
                p.until(f"!!document.querySelector('[data-id={json.dumps(ref)}] [data-slot]')", "Edit")
                self.assertEqual(p.js(f"document.querySelector('[data-id={json.dumps(ref)}] [aria-label=\"Figure 1 live figure\"]').value"), "overdue")

    return Contract, Published, ThroughTheStore, PageSide, InThePage
