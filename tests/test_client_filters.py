"""#69 (logic): the client page's Work items filters (src/clark/client_filters.py).

Run: python3 dev/run_tests.py test_client_filters
Every test fixes "today" as ON (a Wednesday). All rows are fictional. The first group runs the publish plant (tests/_publish_fixture.py)
through publish.select, so what the filters can see is exactly what a published file carries.
"""
import copy
import json
import re
import unittest

from _paths import ROOT  # noqa: F401  (puts src/ on the path)
import _publish_fixture as fx

from clark import client_filters as cf
from clark import publish

ON = "2026-10-28"      # a Wednesday
PICKED = {"type": "all", "show": "all", "f": {}, "not": {}, "q": "", "group": "none"}


def act(n, due=None, status="Open", **v):
    return {"id": f"ABC-A-{n:03d}", "description": f"Action {n}", "owner": "Ana", "workstream": "Delivery", "priority": "Medium",
            "due_date": due, "status": status, "latest_update": "", "client_message": "", "milestone": None, "use_case": None, **v}


def risk(n, type_="Risk", **v):
    return {"id": f"ABC-{n:03d}", "type": type_, "description": f"Risk {n}", "owner": "Bo", "workstream": "Build", "priority": "High",
            "due_date": None, "status": "Open", "client_message": "", "milestone": None, "use_case": None, **v}


def dec(n, status="Pending", **v):
    return {"id": f"ABC-D-{n:03d}", "decision": f"Decision {n}", "made_by": "Cy", "status": status, "needed_by": None, "date": None,
            "client_message": "", "use_case": None, **v}


def pub(actions=(), raid=(), decisions=()):
    return {"actions": list(actions), "raid": list(raid), "decisions": list(decisions)}


def sample():
    return cf.rows_of(pub(
        [act(1, "2026-10-20"), act(2, "2026-10-30", owner="Bo", priority="Urgent", workstream="Build", milestone="ABC-M-001"),
         act(3, "2026-11-20", status="Closed", use_case="ABC-U-001"), act(4, None, status="Delayed", owner=None, workstream=None)],
        [risk(1), risk(2, "Issue", priority="Low", status="Closed", due_date="2026-10-01")],
        [dec(1, needed_by="2026-11-03"), dec(2, "Made", date="2026-10-01")]), ON)


def st(**kw):
    return dict(PICKED, **kw)


def ids(r):
    return [x["id"] for x in r["items"]]


class Published(unittest.TestCase):
    """Nothing hidden or internal is in any count, option, chip or group."""

    def setUp(self):
        self.plant = fx.load()
        self.rows = self.built()

    def built(self):
        p = self.plant
        data = copy.deepcopy(p["data"])
        data["report_hidden"] = [{"item_id": i} for i in p["hidden"]]
        return cf.client_rows(data, p["as_at"], p["sections"], p["label_rules"])

    def everything(self, state=None):
        r = cf.apply_state(self.rows, state or st(), ON)
        return json.dumps(r, sort_keys=True), r

    def test_only_the_kept_work_items_are_rows(self):
        kept = [i for i in self.plant["kept"] if "-M-" not in i and "-U-" not in i and "-W-" not in i]
        self.assertEqual(sorted(r["id"] for r in self.rows), sorted(kept))

    def test_no_dropped_id_or_marker_is_in_any_part_of_the_answer(self):
        text, _ = self.everything()
        every = [self.everything(st(group=g))[0] for g in cf.GROUPS] + [text]
        for dropped in self.plant["dropped"]:
            for t in every:
                self.assertNotIn(dropped, t)
        for marker in self.plant["markers"].values():
            for t in every:
                self.assertNotIn(marker, t)
        self.assertNotIn("ZQ-GHOST-WORKSTREAM", text)

    def test_counts_and_options_hold_only_kept_rows(self):
        _, r = self.everything()
        self.assertEqual(r["counts"]["show"]["all"], len(self.rows))
        for d in r["dimensions"]:
            if d["dim"] not in ("due",):
                self.assertLessEqual(sum(o["count"] for o in d["options"]), len(self.rows))
        self.assertNotIn("ZQ-GHOST-WORKSTREAM", [o["value"] for o in r["dimensions"][0]["options"]])

    def test_a_row_still_marked_not_the_clients_is_refused(self):
        with self.assertRaises(cf.Refused):
            cf.rows_of(pub([act(1, client_visible=0)]), ON)
        with self.assertRaises(cf.Refused):
            cf.rows_of(pub([act(1, archived=1)]), ON)

    def test_a_row_has_the_whitelisted_fields_only(self):
        _, r = self.everything()
        for item in r["items"]:
            self.assertEqual(set(item), set(cf.ROW_FIELDS))

    def test_hidden_section_gives_no_rows(self):
        p = self.plant
        secs = [dict(s, hidden=1) if s["type"] == "actions" else s for s in p["sections"]]
        data = copy.deepcopy(p["data"])
        rows = cf.client_rows(data, p["as_at"], secs, p["label_rules"])
        self.assertFalse([r for r in rows if r["type"] == "A"])


class Counts(unittest.TestCase):
    def test_type_counts_add_up(self):
        r = cf.apply_state(sample(), st(), ON)
        t = r["counts"]["type"]
        self.assertEqual(t["all"], t["A"] + t["R"] + t["D"])
        self.assertEqual(t["all"], 8)

    def test_show_counts_add_up_and_open_is_not_closed(self):
        r = cf.apply_state(sample(), st(show="open"), ON)
        s = r["counts"]["show"]
        self.assertEqual(s["all"], s["open"] + s["closed"])
        self.assertEqual((s["open"], s["closed"]), (5, 3))
        self.assertEqual(r["count"], 5)

    def test_a_count_is_what_a_click_would_show(self):
        rows = sample()
        base = st(show="open", f={"owner": ["Bo"]})
        counts = cf.apply_state(rows, base, ON)["counts"]
        for t in cf.TYPES:
            self.assertEqual(counts["type"][t], cf.apply_state(rows, dict(base, type=t), ON)["count"])
        for k in cf.SHOWS:
            self.assertEqual(counts["show"][k], cf.apply_state(rows, dict(base, show=k), ON)["count"])

    def test_option_counts_leave_out_their_own_dimension(self):
        r = cf.apply_state(sample(), st(f={"owner": ["Bo"]}), ON)
        owner = [d for d in r["dimensions"] if d["dim"] == "owner"][0]
        self.assertEqual({o["value"]: o["count"] for o in owner["options"]}, {"Ana": 2, "Bo": 3, "Cy": 2, "(none)": 1})
        self.assertEqual(sum(o["count"] for o in owner["options"]), 8)
        self.assertEqual(cf.apply_state(sample(), st(f={"owner": ["Bo"]}), ON)["count"], 3)


class Dimensions(unittest.TestCase):
    def one(self, dim, values, **kw):
        return ids(cf.apply_state(sample(), st(f={dim: values}, **kw), ON))

    def test_workstream(self):
        self.assertEqual(self.one("ws", ["Build"]), ["ABC-A-002", "ABC-001", "ABC-002"])
        self.assertEqual(self.one("ws", ["(none)"]), ["ABC-A-004", "ABC-D-001", "ABC-D-002"])

    def test_status(self):
        self.assertEqual(self.one("status", ["Delayed", "Made"]), ["ABC-A-004", "ABC-D-002"])

    def test_due_buckets(self):
        self.assertEqual(self.one("due", ["overdue"]), ["ABC-A-001"])
        self.assertEqual(self.one("due", ["soon"]), ["ABC-A-002", "ABC-D-001"])
        self.assertEqual(self.one("due", ["later"]), ["ABC-A-003"])
        self.assertEqual(self.one("due", ["past"]), ["ABC-002", "ABC-D-002"])
        self.assertEqual(self.one("due", ["none"]), ["ABC-A-004", "ABC-001"])

    def test_due_today_and_in_seven_days_are_soon_eight_is_later(self):
        rows = cf.rows_of(pub([act(1, ON), act(2, "2026-11-04"), act(3, "2026-11-05"), act(4, "2026-10-27")]), ON)
        self.assertEqual([r["bucket"] for r in rows], ["soon", "soon", "later", "overdue"])

    def test_owner_priority_use_case_milestone(self):
        self.assertEqual(self.one("owner", ["Bo"]), ["ABC-A-002", "ABC-001", "ABC-002"])
        self.assertEqual(self.one("owner", ["(none)"]), ["ABC-A-004"])
        self.assertEqual(self.one("priority", ["Urgent", "Low"]), ["ABC-A-002", "ABC-002"])
        self.assertEqual(self.one("uc", ["ABC-U-001"]), ["ABC-A-003"])
        self.assertEqual(self.one("ms", ["ABC-M-001"]), ["ABC-A-002"])

    def test_two_dimensions_are_all_of_and_values_in_one_are_any_of(self):
        r = cf.apply_state(sample(), st(f={"owner": ["Bo", "Cy"], "due": ["soon"]}), ON)
        self.assertEqual(ids(r), ["ABC-A-002", "ABC-D-001"])

    def test_not_keeps_the_others(self):
        r = cf.apply_state(sample(), st(f={"owner": ["Bo"]}, **{"not": {"owner": True}}), ON)
        self.assertEqual(ids(r), ["ABC-A-001", "ABC-A-003", "ABC-A-004", "ABC-D-001", "ABC-D-002"])
        self.assertTrue([d for d in r["dimensions"] if d["dim"] == "owner"][0]["negated"])

    def test_active_flag_only_on_a_dimension_with_values(self):
        r = cf.apply_state(sample(), st(f={"owner": ["Bo"], "status": []}), ON)
        self.assertEqual({d["dim"]: d["active"] for d in r["dimensions"]},
                         {"ws": False, "status": False, "due": False, "owner": True, "priority": False, "uc": False, "ms": False})

    def test_type_switch_and_the_issue_belongs_to_risks(self):
        self.assertEqual(ids(cf.apply_state(sample(), st(type="R"), ON)), ["ABC-001", "ABC-002"])
        self.assertEqual(ids(cf.apply_state(sample(), st(type="D"), ON)), ["ABC-D-001", "ABC-D-002"])
        self.assertEqual(len(cf.apply_state(sample(), st(type="A"), ON)["items"]), 4)

    def test_open_closed_all(self):
        self.assertEqual(ids(cf.apply_state(sample(), st(show="closed"), ON)), ["ABC-A-003", "ABC-002", "ABC-D-002"])
        self.assertEqual(len(cf.apply_state(sample(), st(show="open"), ON)["items"]), 5)

    def test_options_hold_only_present_values_in_a_fixed_order(self):
        r = cf.apply_state(sample(), st(), ON)
        d = {x["dim"]: [o["value"] for o in x["options"]] for x in r["dimensions"]}
        self.assertEqual(d["priority"], ["Urgent", "High", "Medium", "Low", "(none)"])
        self.assertEqual(d["status"], ["Open", "Delayed", "Pending", "Closed", "Made"])
        self.assertEqual(d["due"], ["overdue", "soon", "later", "none", "past"])
        self.assertEqual(d["ws"], ["Build", "Delivery", "(none)"])
        self.assertEqual(d["owner"], ["Ana", "Bo", "Cy", "(none)"])


class ClearAndChips(unittest.TestCase):
    def test_chips_name_each_active_filter_and_the_search(self):
        r = cf.apply_state(sample(), st(f={"owner": ["Bo"], "due": ["soon", "overdue"]}, q="risk"), ON)
        self.assertEqual([c["dim"] for c in r["chips"]], ["due", "owner", "q"])
        due = r["chips"][0]
        self.assertEqual([v["label"] for v in due["values"]], ["Overdue", "Due in 7 days"])

    def test_clear_all_empties_filters_and_search_and_keeps_the_rest(self):
        s = st(type="A", show="open", group="owner", f={"owner": ["Bo"]}, q="x", **{"not": {"owner": True}})
        c = cf.clear_all(s)
        self.assertEqual((c["f"], c["not"], c["q"]), ({}, {}, ""))
        self.assertEqual((c["type"], c["show"], c["group"]), ("A", "open", "owner"))
        self.assertEqual(cf.apply_state(sample(), c, ON)["chips"], [])
        self.assertEqual(s["f"], {"owner": ["Bo"]}, "the state given is not changed")


class Search(unittest.TestCase):
    def test_search_reads_id_title_owner_update_message_and_use_case(self):
        rows = cf.rows_of(pub([act(1, owner="Zed", latest_update="Pump arrived"), act(2, client_message="Awaiting crane", use_case="ABC-U-009")]), ON)
        q = lambda text: ids(cf.apply_state(rows, st(q=text), ON))
        self.assertEqual(q("a-001"), ["ABC-A-001"])
        self.assertEqual(q("ZED"), ["ABC-A-001"])
        self.assertEqual(q("pump"), ["ABC-A-001"])
        self.assertEqual(q("crane"), ["ABC-A-002"])
        self.assertEqual(q("u-009"), ["ABC-A-002"])
        self.assertEqual(q("action 2"), ["ABC-A-002"])
        self.assertEqual(q("  "), ["ABC-A-001", "ABC-A-002"])
        self.assertEqual(q("nothing like this"), [])

    def test_search_does_not_read_a_field_that_is_not_published(self):
        rows = cf.rows_of(pub([act(1, internal_note="ZQ-SECRET", source="ZQ-SRC")]), ON)
        self.assertEqual(ids(cf.apply_state(rows, st(q="ZQ-SECRET"), ON)), [])

    def test_search_combines_with_a_filter(self):
        r = cf.apply_state(sample(), st(q="action", f={"owner": ["Bo"]}), ON)
        self.assertEqual(ids(r), ["ABC-A-002"])


class GroupBy(unittest.TestCase):
    def groups(self, g, **kw):
        r = cf.apply_state(sample(), st(group=g, **kw), ON)
        self.assertEqual(sum(x["count"] for x in r["groups"]), r["count"])
        self.assertEqual(sorted(i["id"] for x in r["groups"] for i in x["items"]), sorted(ids(r)))
        return [(x["key"], x["label"], [i["id"] for i in x["items"]]) for x in r["groups"]]

    def test_workstream_none_goes_last(self):
        g = self.groups("ws")
        self.assertEqual([k for k, _, _ in g], ["Build", "Delivery", "(none)"])
        self.assertEqual(g[2][1], "No workstream")

    def test_priority_status_owner_type_and_nothing(self):
        self.assertEqual([k for k, _, _ in self.groups("priority")], ["Urgent", "High", "Medium", "Low", "(none)"])
        self.assertEqual([k for k, _, _ in self.groups("status")], ["Open", "Delayed", "Pending", "Closed", "Made"])
        self.assertEqual([k for k, _, _ in self.groups("owner")], ["Ana", "Bo", "Cy", "(none)"])
        self.assertEqual([l for _, l, _ in self.groups("type")], ["Actions", "Risks and issues", "Decisions"])
        self.assertEqual(self.groups("none"), [("", "All items", [i for i in ids(cf.apply_state(sample(), st(), ON))])])

    def test_due_groups_use_weeks(self):
        rows = cf.rows_of(pub([act(1, "2026-10-27"), act(2, "2026-11-01"), act(3, "2026-11-02"), act(4, "2026-11-08"),
                               act(5, "2026-11-09"), act(6)]), ON)
        g = cf.apply_state(rows, st(group="due"), ON)["groups"]
        self.assertEqual([(x["key"], [i["id"] for i in x["items"]]) for x in g],
                         [("overdue", ["ABC-A-001"]), ("week", ["ABC-A-002"]), ("next", ["ABC-A-003", "ABC-A-004"]),
                          ("later", ["ABC-A-005"]), ("none", ["ABC-A-006"])])

    def test_a_sunday_ends_its_own_week(self):
        self.assertEqual(cf.week_end("2026-11-01"), "2026-11-01")
        self.assertEqual(cf.week_end("2026-10-28"), "2026-11-01")
        self.assertEqual(cf.week_end("2026-10-28", 1), "2026-11-08")

    def test_groups_respect_filters_and_empty_groups_are_not_listed(self):
        g = self.groups("owner", f={"owner": ["Cy"]})
        self.assertEqual([k for k, _, _ in g], ["Cy"])

    def test_items_keep_the_file_order_inside_a_group(self):
        g = dict((k, v) for k, _, v in self.groups("owner"))
        self.assertEqual(g["Bo"], ["ABC-A-002", "ABC-001", "ABC-002"])


class Remembered(unittest.TestCase):
    def test_round_trip(self):
        rows = sample()
        s = cf.normalise(st(type="R", show="open", group="owner", f={"owner": ["Bo"], "due": ["soon"]}, q="not kept",
                            **{"not": {"owner": True}}), rows)
        key, text = cf.remember(s, "ABC")
        self.assertEqual(key, "clark.work.ABC")
        back = cf.recall(text, rows)
        self.assertEqual(back, dict(s, q=""), "everything but the search text comes back")
        self.assertNotIn("not kept", text)

    def test_unknown_keys_values_and_bad_text_are_ignored(self):
        rows = sample()
        text = json.dumps({"v": 1, "type": "Z", "show": "closed", "group": "nope", "evil": "<script>", "f": {"owner": ["Nobody", "Bo"], "ghost": ["x"]},
                           "not": {"owner": True, "ghost": True}})
        got = cf.recall(text, rows)
        self.assertEqual((got["type"], got["show"], got["group"]), ("all", "closed", cf.DEFAULT_GROUP))
        self.assertEqual(got["f"], {"owner": ["Bo"]})
        self.assertEqual(got["not"], {"owner": True})
        self.assertNotIn("evil", got)
        for bad in (None, "", "{", "[]", "7", json.dumps({"v": 2, "type": "A"}), json.dumps({"type": "A"})):
            self.assertEqual(cf.recall(bad, rows), cf.new_state())

    def test_a_list_or_dict_value_never_raises_and_gives_the_default(self):
        rows = sample()
        for odd in ([], ["ws"], {}, {"a": 1}, None, 5, ("ws",)):
            got = cf.normalise({"group": odd, "type": odd, "show": odd, "q": odd}, rows)
            self.assertEqual(got, cf.new_state())
            self.assertEqual(cf.apply_state(rows, {"group": odd}, ON)["state"]["group"], cf.DEFAULT_GROUP)
            self.assertEqual(cf.recall(json.dumps({"v": 1, "group": odd}), rows), cf.new_state())

    def test_one_word_for_no_priority_and_earlier(self):
        self.assertEqual(cf.value_label("priority", cf.NONE), "No priority")
        self.assertEqual(cf.BUCKET_LABELS["past"], "Earlier")
        self.assertEqual(dict(cf.GROUP_DUE)["past"], "Earlier")
        for text in (cf.value_label("priority", cf.NONE), "Earlier"):
            self.assertNotIn("Not rated", text)

    def test_a_text_flag_that_is_not_one_is_refused_too(self):
        for odd in ("0", "no", None, 2):
            with self.subTest(odd=odd), self.assertRaises(cf.Refused):
                cf.rows_of(pub([act(1, client_visible=odd)]), ON)
        self.assertEqual(len(cf.rows_of(pub([act(1, client_visible=1), act(2, client_visible=True)]), ON)), 2)

    def test_the_refusal_says_what_to_do_next(self):
        with self.assertRaises(cf.Refused) as cm:
            cf.rows_of(pub([act(1, client_visible=0)]), ON)
        self.assertIn("Publish the report again", str(cm.exception))

    def test_stored_text_holds_only_the_remembered_keys(self):
        _, text = cf.remember(dict(cf.new_state(), extra="x", items=[1]), "ABC")
        self.assertEqual(sorted(json.loads(text)), ["f", "group", "not", "show", "type", "v"])

    def test_a_choice_no_row_has_any_more_is_dropped(self):
        got = cf.recall(json.dumps({"v": 1, "f": {"owner": ["Gone"]}}), sample())
        self.assertEqual(got["f"], {})
        self.assertEqual(cf.apply_state(sample(), got, ON)["chips"], [])

    def test_the_module_sends_nothing_anywhere(self):
        src = (ROOT / "src" / "clark" / "client_filters.py").read_text(encoding="utf-8")
        code = src.split('"""', 2)[2]
        for word in ("urllib", "http", "socket", "requests", "import os", "pathlib"):
            self.assertNotIn(word, code)
        self.assertIsNone(re.search(r"(?<![\w.])open\(", code))


class Cases(unittest.TestCase):
    """The shared cases the page's JavaScript must also pass (tests/fixtures/client-filter-cases.json)."""

    def test_the_cases_give_the_recorded_answers(self):
        f = json.loads((ROOT / "tests" / "fixtures" / "client-filter-cases.json").read_text(encoding="utf-8"))
        rows = cf.rows_of(f["published"], f["today"])
        self.assertGreaterEqual(len(f["cases"]), 6)
        for c in f["cases"]:
            self.assertEqual(cf.apply_state(rows, c["state"], f["today"]), c["expect"], c["state"])


class Order(unittest.TestCase):
    def test_same_input_same_answer(self):
        a = json.dumps(cf.apply_state(sample(), st(group="owner", f={"due": ["soon", "overdue"]}), ON), sort_keys=False)
        b = json.dumps(cf.apply_state(sample(), st(group="owner", f={"due": ["overdue", "soon"]}), ON), sort_keys=False)
        self.assertEqual(a, b)

    def test_rows_follow_the_published_order(self):
        self.assertEqual([r["id"] for r in sample()], ["ABC-A-001", "ABC-A-002", "ABC-A-003", "ABC-A-004", "ABC-001", "ABC-002",
                                                      "ABC-D-001", "ABC-D-002"])

    def test_decision_due_is_needed_by_while_pending_else_the_date(self):
        r = {x["id"]: x for x in sample()}
        self.assertEqual((r["ABC-D-001"]["due"], r["ABC-D-002"]["due"]), ("2026-11-03", "2026-10-01"))


if __name__ == "__main__":
    unittest.main()
