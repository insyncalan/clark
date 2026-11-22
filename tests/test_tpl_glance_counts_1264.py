"""Row 1264 slice 2: the three built-in count tiles of the glance template, in published(). Counts come from ctx.rows (the rows publish
kept) through glance.tiles, the code of the At a glance section; a hidden section, a client-hidden, Sensitive, archived or eye-hidden row
is never counted and never named. Fictional data only. Words are the existing ones (glance.py); new words are the approved refusal texts (none here).

Run: python3 dev/run_tests.py test_tpl_glance_counts_1264
"""
import json
import unittest

from _demo import USER
from clark import glance, publish, section_bodies
from clark.section_kinds import base, glancetemplate as gt
from test_changes import Api

AS_AT = "2030-01-15"
MARK = "ZQ-GLANCE-MARK"


def rows():
    return {"actions": [{"id": "ABC-A-001", "status": "Open", "due_date": "2030-01-01", "description": MARK},
                        {"id": "ABC-A-002", "status": "Open", "due_date": "2030-02-01", "description": MARK},
                        {"id": "ABC-A-003", "status": "Closed", "due_date": "2030-01-01", "description": MARK}],
            "raid": [{"id": "ABC-R-001", "type": "Risk", "status": "Open", "priority": "High", "description": MARK},
                     {"id": "ABC-R-002", "type": "Issue", "status": "Open", "priority": "Medium", "description": MARK}],
            "decisions": [{"id": "ABC-D-001", "status": "Pending", "needed_by": "2030-01-20", "decision": MARK}]}


def pub(body=None, given=None, as_at=AS_AT):
    return gt.published(body if body is not None else {"v": 1}, base.Context(rows() if given is None else given, as_at))


def counts(out):
    return {c["tile"]: c for c in (out or {}).get("content", {}).get("counts", [])}


class Rules(unittest.TestCase):                                                       # T22-T29
    def test_t22_three_tiles_in_the_default_order_with_the_glance_words(self):
        out = pub()
        self.assertEqual([c["tile"] for c in out["content"]["counts"]], ["overdue", "risks", "decisions"])
        c = counts(out)
        self.assertEqual((c["overdue"]["title"], c["overdue"]["value"], c["overdue"]["detail"], c["overdue"]["rag"]), ("Overdue actions", 1, "of 2 open actions", "r"))
        self.assertEqual((c["risks"]["title"], c["risks"]["value"], c["risks"]["detail"], c["risks"]["rag"]), ("High risks and issues", 1, "of 2 open risks and issues", "r"))
        self.assertEqual((c["decisions"]["title"], c["decisions"]["value"], c["decisions"]["detail"], c["decisions"]["rag"]), ("Decisions needed", 1, "Oldest needed by 20-01-2030", "a"))

    def test_t23_the_counts_are_the_at_a_glance_tiles_of_the_same_rows(self):
        kept = {"rows": glance.work_rows(rows()), "hidden_types": set()}
        ref = {t["tile"]: t for t in glance.tiles({"project": {}}, AS_AT, hidden=set(), for_client=True, kept=kept)}
        for name, c in counts(pub()).items():
            self.assertEqual((c["value"], c["detail"], c["rag"], c["title"]), (ref[name]["value"], ref[name]["detail"], ref[name]["class"], ref[name]["title"]), name)

    def test_t24_overdue_is_open_and_before_the_day_only(self):
        given = {"actions": [{"id": "A1", "status": "Open", "due_date": AS_AT}, {"id": "A2", "status": "Closed", "due_date": "2030-01-01"},
                             {"id": "A3", "status": "Open", "due_date": "2030-01-14"}]}
        c = counts(pub(given=given))["overdue"]
        self.assertEqual((c["value"], c["detail"]), (1, "of 2 open actions"))

    def test_t25_high_counts_urgent_and_high_of_every_risk_kind_and_the_none_words(self):
        given = {"raid": [{"id": "R1", "type": "Assumption", "status": "Open", "priority": "Urgent"}, {"id": "R2", "type": "Risk", "status": "Open", "priority": "Low"}]}
        self.assertEqual(counts(pub(given=given))["risks"]["value"], 1)
        low = {"raid": [{"id": "R2", "type": "Risk", "status": "Open", "priority": "Low"}]}
        self.assertEqual((counts(pub(given=low))["risks"]["value"], counts(pub(given=low))["risks"]["detail"]), (0, "None high"))

    def test_t26_decisions_needed_is_pending_only_and_the_words_follow(self):
        given = {"decisions": [{"id": "D1", "status": "Delayed"}, {"id": "D2", "status": "Pending"}]}
        c = counts(pub(given=given))["decisions"]
        self.assertEqual((c["value"], c["detail"]), (1, "No date set"))
        none = {"decisions": [{"id": "D1", "status": "Delayed"}]}
        self.assertEqual(counts(pub(given=none))["decisions"]["detail"], "None waiting")

    def test_t27_only_existing_words_are_published(self):
        allowed = {"Overdue actions", "High risks and issues", "Decisions needed", "No open actions", "None open", "None high", "None waiting", "No date set"}
        for given in (rows(), {"actions": [{"id": "A", "status": "Closed"}], "raid": [{"id": "R", "type": "Risk", "status": "Closed"}],
                      "decisions": [{"id": "D", "status": "Made"}]}):
            for c in counts(pub(given=given)).values():
                self.assertIn(c["title"], allowed)
                self.assertTrue(c["detail"] in allowed or c["detail"].startswith(("of ", "Oldest needed by ")), c["detail"])
        self.assertFalse([k for k in gt.APPROVED if any(k in json.dumps(c) for c in counts(pub()).values())])

    def test_t28_the_outline_choice_sets_the_colour_class_and_the_order_is_followed(self):
        out = pub({"v": 1, "order": ["decisions", "overdue", "risks"], "builtin": {"overdue": {"outline": "G"}, "risks": {"outline": "N"}}})
        self.assertEqual([c["tile"] for c in out["content"]["counts"]], ["decisions", "overdue", "risks"])
        c = counts(out)
        self.assertEqual((c["overdue"]["rag"], c["risks"]["rag"]), ("g", "n"))

    def test_t29_a_count_carries_only_its_five_fields(self):
        for c in counts(pub()).values():
            self.assertEqual(set(c), {"tile", "title", "value", "detail", "rag"})
        self.assertNotIn(MARK, json.dumps(pub()))


class Absent(unittest.TestCase):                                                      # T30-T35 (rules level)
    def test_t30_a_tile_whose_kind_has_no_kept_row_is_left_out(self):
        given = rows()
        given["raid"] = []
        self.assertEqual(sorted(counts(pub(given=given))), ["decisions", "overdue"])

    def test_t31_no_rows_and_no_own_tile_is_no_section(self):
        off = {"v": 1, "health": {"shown": False}}      # the health eye on still prints its row (ruled 17-11), so the eye is off here
        self.assertIsNone(pub(off, given={}))
        self.assertIsNone(pub(off, given={"actions": [], "raid": [], "decisions": []}))
        self.assertNotIn("counts", pub(given={})["content"])      # health on, no rows: the health row only

    def test_t32_the_eye_off_on_a_built_in_tile_leaves_it_out_and_names_nothing_of_it(self):
        out = pub({"v": 1, "builtin": {"overdue": {"hidden": True}}})
        self.assertEqual(sorted(counts(out)), ["decisions", "risks"])
        self.assertNotIn("Overdue actions", json.dumps(out["content"]["counts"]))

    def test_t33_all_three_eyes_off_is_no_count_and_no_section_without_own_tiles(self):
        off = {n: {"hidden": True} for n in gt.SETTLED}
        self.assertIsNone(pub({"v": 1, "health": {"shown": False}, "builtin": off}))
        self.assertNotIn("counts", pub({"v": 1, "builtin": off})["content"])      # health on: the health row only
        out = pub({"v": 1, "builtin": off, "bespoke": [{"id": "t1", "label": "Own"}]})
        self.assertNotIn("counts", out["content"])

    def test_t34_a_bad_or_missing_day_counts_nothing_and_does_not_fail(self):
        off = {"v": 1, "health": {"shown": False}}
        self.assertIsNone(pub(off, as_at=None))
        self.assertIsNone(pub(off, as_at=""))
        self.assertIsNone(gt.published(off, None))
        self.assertNotIn("counts", pub(as_at=None)["content"])

    def test_t35_own_tiles_and_counts_come_together(self):
        out = pub({"v": 1, "bespoke": [{"id": "t1", "label": "Own"}]})
        self.assertEqual((len(out["content"]["counts"]), [t["id"] for t in out["content"]["bespoke"]]), (3, ["t1"]))


class ThroughPublish(Api):                                                            # T36-T39 (editor vs published, the file)
    def section(self, body=None, **more):
        ref = self.ok("new", values={"type": "glancetemplate", "title": "Fictional glance"}, **more)["ref"]
        if body is not None:
            from clark import changes
            status, got = self.change(self.req(changes.UPDATE, id=ref, changes={"body": json.dumps(body)}))
            self.assertEqual((status, got.get("message")), (200, None), got)
        return ref

    def plant(self):
        # new projects start with Work items lists in place of the built-in Actions, RAID and Decisions sections (row 1193), and a list alone
        # reaches the rows it names; these tests pin the built-in sections' counts, so the report is given those three sections here
        have = {x["type"] for x in self.s.data_for("ABC")["report_sections"]}
        for kind, title in (("actions", "Fictional actions"), ("raid", "Fictional risks"), ("decisions", "Fictional decisions")):
            if kind not in have:
                self.ok("new", values={"type": kind, "title": title})
        with self.s.step("dashboard", USER) as st:
            ids = {}
            ids["shown"] = st.create("actions", {"project": "ABC", "description": "Fictional shown action", "raised": "2030-01-01", "due_date": "2030-01-05", "source": "demo"})
            ids["eye"] = st.create("actions", {"project": "ABC", "description": f"{MARK} eye", "raised": "2030-01-01", "due_date": "2030-01-05", "source": "demo"})
            ids["client"] = st.create("actions", {"project": "ABC", "description": f"{MARK} client", "raised": "2030-01-01", "due_date": "2030-01-05", "source": "demo", "client_visible": 0})
            ids["sens"] = st.create("actions", {"project": "ABC", "description": f"{MARK} sens", "raised": "2030-01-01", "due_date": "2030-01-05", "source": "demo"})
            st.create("report_hidden", {"project": "ABC", "item_id": ids["eye"]})
            st.create("item_labels", {"item_id": ids["sens"], "label": "Sensitive"})
            ids["dec"] = st.create("decisions", {"project": "ABC", "decision": f"{MARK} decision", "status": "Pending", "needed_by": "2030-01-03", "source": "demo", "client_visible": 0})
        return ids

    def built(self, ref, now=AS_AT):
        b = publish.build(self.s, "ABC", now=now)
        return next((s for s in b["published"]["sections"] if s["id"] == ref), None), b["body"].decode("utf-8"), b

    def test_t36_the_file_counts_only_kept_rows_and_names_none_of_the_others(self):
        self.plant()
        sec, text, _ = self.built(self.section({"v": 1}))
        c = counts(sec)
        self.assertEqual(c["overdue"]["value"], 1)
        self.assertEqual(c["overdue"]["detail"], "of 1 open action")
        self.assertNotIn("decisions", c, "the only decision is client-hidden: no count of it, no name of its date")
        self.assertNotIn(MARK, text)
        self.assertNotIn("03-01-2030", json.dumps(sec))

    def test_t37_a_hidden_section_of_a_kind_hides_its_tile_in_the_file(self):
        self.plant()
        with self.s.step("dashboard", USER) as st:
            st.create("raid", {"project": "ABC", "type": "Risk", "description": "Fictional risk", "raised": "2030-01-01", "priority": "High", "source": "demo"})
        ref = self.section({"v": 1})
        for sec in self.s.data_for("ABC")["report_sections"]:
            if sec["type"] == "actions":
                self.ok("update", id=sec["id"], changes={"hidden": 1})
        sec, text, _ = self.built(ref)
        self.assertEqual(sorted(counts(sec)), ["risks"], "Overdue actions is gone with its section; the tile of a shown section stays")
        self.assertNotIn("Overdue actions", json.dumps(sec))
        self.assertNotIn(MARK, text)

    def test_t38_a_hidden_glance_template_section_is_not_in_the_file(self):
        self.plant()
        ref = self.section({"v": 1})
        self.ok("update", id=ref, changes={"hidden": 1})
        sec, text, _ = self.built(ref)
        self.assertIsNone(sec)
        self.assertNotIn("Fictional glance", text)

    def test_t39_the_editor_counts_more_than_the_file(self):
        ids = self.plant()
        data = self.s.data_for("ABC")
        editor = {t["tile"]: t for t in glance.tiles(data, AS_AT, hidden=set())}
        sec, _, _ = self.built(self.section({"v": 1}))
        filed = counts(sec)
        self.assertGreater(editor["overdue"]["value"], filed["overdue"]["value"])
        self.assertEqual(editor["overdue"]["value"], 4)
        self.assertEqual(filed["overdue"]["value"], 1)
        self.assertEqual(len(ids), 5)


if __name__ == "__main__":
    unittest.main()
