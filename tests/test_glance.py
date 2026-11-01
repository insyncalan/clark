"""#45 (pure part): the At a glance tiles, the health pick and the use case strip (src/clark/glance.py).

Run: python3 dev/run_tests.py test_glance
Every test fixes "today" as ON, so nothing depends on the real date. All rows are fictional. The Work items list's own
fixture cases (tests/fixtures/work-items-list-cases.json, #36) are run through the same rules when that file is in the repo.
"""
import importlib.util
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from _demo import DemoStore, USER
from _paths import ROOT

from clark import glance as g
from clark import publish
from clark.store import Invalid, open_store

ON = "2026-10-28"
PLANTED_MARKER = "INTERNAL-ONLY-NOTE-7731"
FIXTURE = ROOT / "tests" / "fixtures" / "work-items-list-cases.json"


def action(n, due=None, status="Open", **values):
    return {"id": f"ABC-A-{n:03d}", "project": "ABC", "status": status, "due_date": due, "priority": "Medium",
            "client_visible": 1, "archived": 0, "use_case": None, **values}


def raid(n, type_="Risk", priority="Medium", status="Open", due=None, **values):
    return {"id": f"ABC-{n:03d}", "project": "ABC", "type": type_, "status": status, "priority": priority,
            "due_date": due, "client_visible": 1, "archived": 0, "use_case": None, **values}


def decision(n, status="Pending", needed_by=None, **values):
    return {"id": f"ABC-D-{n:03d}", "project": "ABC", "status": status, "needed_by": needed_by, "date": None,
            "client_visible": 1, "archived": 0, "use_case": None, **values}


def use_case(n, status="On track", **values):
    return {"id": f"ABC-U-{n:03d}", "project": "ABC", "ref": f"1.{n}", "title": f"Use case title {n}", "status": status,
            "headline": f"Headline {n}", "standing": "<p>Where it stands</p>", "sort_order": n, "client_visible": 1,
            "source": "demo", "archived": 0, **values}


def data(actions=(), raid_=(), decisions=(), **extra):
    return {"project": {"code": "ABC", "health": "At risk", "health_reason": "Supplier is a fortnight late"},
            "actions": list(actions), "raid": list(raid_), "decisions": list(decisions), **extra}


def by_name(result):
    return {t["tile"]: t for t in result}


class Dates(unittest.TestCase):
    def test_day_numbers(self):
        self.assertEqual(g.day_number("2026-10-29") - g.day_number("2026-10-28"), 1)
        for bad in (None, "", "2026-02-30", "28-10-2026", "2026-10-28T09:00", 20261028, "٢٠٢٦-١٠-٢٨"):
            self.assertIsNone(g.day_number(bad), bad)

    def test_shown_as_day_month_year(self):
        self.assertEqual(g.show_date("2026-11-04"), "04-11-2026")
        self.assertEqual(g.show_date(None), "—")
        self.assertEqual(g.show_date("soon"), "soon")

    def test_today_must_be_a_real_day(self):
        with self.assertRaises(ValueError):
            g.tiles(data(), "28-10-2026")
        with self.assertRaises(ValueError):
            g.use_case_strip([], [], "2026-02-30")


class HealthPill(unittest.TestCase):
    def test_each_health_has_words_and_a_colour(self):
        got = {h: g.health_pill(h) for h in g.HEALTHS}
        self.assertEqual([(p["words"], p["colour"], p["class"]) for p in got.values()],
                         [("On track", "green", "g"), ("At risk", "amber", "a"), ("Off track", "red", "r")])
        for p in got.values():
            self.assertIn(p["colour"], p["label"], "the colour is named in words, not colour alone")
            self.assertIn(p["words"], p["label"])

    def test_no_health_yet(self):
        p = g.health_pill(None)
        self.assertEqual((p["words"], p["colour"], p["class"]), ("Not set", None, "n"))
        self.assertEqual(g.health_pill("Purple")["words"], "Not set")

    def test_the_values_are_the_stores(self):
        from clark.store import ALLOWED
        self.assertEqual(g.HEALTHS, ALLOWED[("projects", "health")])
        self.assertEqual(g.USE_CASE_STATUSES, ALLOWED[("use_cases", "status")])


class HealthPick(unittest.TestCase):
    P = {"code": "ABC", "health": "On track", "health_reason": "Going well"}

    def test_a_change_with_the_reason_as_it_stands(self):
        r = g.health_pick(self.P, "At risk")
        self.assertEqual(r["errors"], [])
        self.assertEqual(r["change"], {"table": "projects", "ref": "ABC",
                                       "changes": {"health": "At risk", "health_reason": "Going well"}})
        self.assertEqual(r["message"], "Health changed from On track to At risk.")

    def test_the_reason_as_it_stands_is_flagged_as_reused(self):
        """The same reason sent with a different health: the page is told, so it can ask for a one-line confirmation."""
        self.assertIs(g.health_pick(self.P, "At risk")["reused_reason"], True)
        self.assertIs(g.health_pick(self.P, "At risk", "Going well")["reused_reason"], True, "typed again, unchanged")
        self.assertIs(g.health_pick(self.P, "At risk", "  Going well \n")["reused_reason"], True, "only spaces differ")

    def test_a_new_or_refused_or_unchanged_pick_is_not_flagged(self):
        self.assertIs(g.health_pick(self.P, "At risk", "Supplier has slipped")["reused_reason"], False)
        self.assertIs(g.health_pick(self.P, "At risk", "")["reused_reason"], False, "refused: nothing to confirm")
        self.assertIs(g.health_pick(self.P, "On track")["reused_reason"], False, "the same health is not a change")
        self.assertIs(g.health_pick(self.P, "Purple")["reused_reason"], False)
        self.assertIs(g.reason_change(self.P, "New words")["reused_reason"], False)
        first = g.health_pick({"code": "ABC", "health": None, "health_reason": "Kick-off"}, "On track")
        self.assertIs(first["reused_reason"], False, "the first health ever set has nothing to be reused from")

    def test_a_change_with_a_new_reason_keeps_its_lines(self):
        r = g.health_pick(self.P, "Off track", "Supplier has gone.\nNo date yet.")
        self.assertEqual(r["change"]["changes"], {"health": "Off track", "health_reason": "Supplier has gone.\nNo date yet."})

    def test_an_empty_reason_is_refused_in_plain_words(self):
        for reason in ("", "   ", "\n"):
            r = g.health_pick(self.P, "At risk", reason)
            self.assertIsNone(r["change"])
            self.assertEqual(r["errors"], ["Say why in a line or two before the health becomes At risk. "
                                           "clark keeps the reason with the health."])
        r = g.health_pick({**self.P, "health_reason": None}, "At risk")
        self.assertIsNone(r["change"], "no reason as it stands, none typed")
        self.assertEqual(len(r["errors"]), 1)

    def test_the_same_health_is_not_a_change(self):
        r = g.health_pick(self.P, "On track", "")
        self.assertEqual((r["change"], r["errors"]), (None, []))
        self.assertEqual(r["message"], "The health is already On track. Nothing to change.")

    def test_a_health_that_is_not_one(self):
        for wanted in ("Purple", "on track", "Red", "", None, 3):
            r = g.health_pick(self.P, wanted, "Because")
            self.assertIsNone(r["change"], wanted)
            self.assertEqual(len(r["errors"]), 1, wanted)
        self.assertEqual(g.health_pick(self.P, "Purple", "x")["errors"],
                         ["\"Purple\" is not a health. Choose On track, At risk or Off track."])
        self.assertEqual(g.health_pick(self.P, "", "x")["errors"], ["Choose a health: On track, At risk or Off track."])

    def test_a_project_with_no_health_yet(self):
        r = g.health_pick({"code": "ABC", "health": None, "health_reason": None}, "On track", "Starting out")
        self.assertEqual(r["message"], "Health set to On track.")
        self.assertEqual(r["change"]["changes"]["health"], "On track")

    def test_no_project(self):
        self.assertEqual(g.health_pick({"health": "On track"}, "At risk", "x")["errors"], ["Say which project the health is for."])

    def test_the_reason_alone(self):
        r = g.reason_change(self.P, "Going very well")
        self.assertEqual(r["change"], {"table": "projects", "ref": "ABC", "changes": {"health_reason": "Going very well"}})
        self.assertEqual(r["message"], "Reason saved.")
        self.assertEqual(g.reason_change(self.P, "Going well")["change"], None)
        self.assertEqual(g.reason_change(self.P, "")["message"], "Reason cleared.")

    def test_the_writer_agrees(self):
        """The requests are what Store.step(...).update takes, and the refusals are the writer's."""
        with DemoStore() as store:
            project = store.read("projects", ref="ABC")
            ok = g.health_pick(project, "At risk", "Supplier is late")["change"]
            with store.step("dashboard", USER) as st:
                st.update(ok["table"], ok["ref"], ok["changes"])
            project = store.read("projects", ref="ABC")
            self.assertEqual((project["health"], project["health_reason"]), ("At risk", "Supplier is late"))
            # the reason as it stands is enough for the writer, and the same words are what the pick sends
            back = g.health_pick(project, "On track")["change"]
            with store.step("dashboard", USER) as st:
                st.update(back["table"], back["ref"], back["changes"])
            # what the pick refuses, the writer refuses too
            blank = {**store.read("projects", ref="ABC"), "health_reason": ""}
            self.assertIsNone(g.health_pick(blank, "Off track")["change"])
            with self.assertRaises(Invalid):
                with store.step("dashboard", USER) as st:
                    st.update("projects", "ABC", {"health": "Off track", "health_reason": ""})
            # and the reason alone is accepted by the writer
            only = g.reason_change(store.read("projects", ref="ABC"), "Now clearer")["change"]
            with store.step("dashboard", USER) as st:
                st.update(only["table"], only["ref"], only["changes"])


class OverdueRules(unittest.TestCase):
    def test_due_today_is_not_overdue_and_yesterday_is(self):
        rows = g.work_rows(data(actions=[action(1, "2026-10-28"), action(2, "2026-10-27"), action(3, "2026-10-29")]))
        self.assertEqual([g.is_overdue(r, ON) for r in rows], [False, True, False])

    def test_closed_and_cancelled_are_never_overdue(self):
        rows = g.work_rows(data(actions=[action(1, "2026-10-01", "Closed"), action(2, "2026-10-01", "Cancelled"),
                                         action(3, "2026-10-01", "Delayed")]))
        self.assertEqual([g.is_overdue(r, ON) for r in rows], [False, False, True])

    def test_a_date_that_is_not_a_real_day_or_missing_is_never_overdue(self):
        rows = g.work_rows(data(actions=[action(1, "2026-02-30"), action(2, None), action(3, "soon")]))
        self.assertEqual([g.is_overdue(r, ON) for r in rows], [False, False, False])

    def test_a_pending_decision_is_due_on_its_needed_by_date(self):
        rows = g.work_rows(data(decisions=[decision(1, needed_by="2026-10-26"), decision(2, needed_by=ON), decision(3),
                                           decision(4, "Made", needed_by="2026-10-01")]))
        self.assertEqual([g.is_overdue(r, ON) for r in rows], [True, False, False, False])

    def test_month_year_and_leap_day_edges(self):
        self.assertTrue(g.is_overdue({"kind": "action", "status": "Open", "due_date": "2026-12-31"}, "2027-01-01"))
        self.assertFalse(g.is_overdue({"kind": "action", "status": "Open", "due_date": "2027-01-01"}, "2027-01-01"))
        self.assertTrue(g.is_overdue({"kind": "action", "status": "Open", "due_date": "2028-02-29"}, "2028-03-01"))

    def test_the_work_items_lists_own_cases(self):
        """The same rules as the list's: every case in its fixture file, due words ("late") and pill included."""
        if not FIXTURE.is_file():
            self.skipTest("tests/fixtures/work-items-list-cases.json arrives with #36")
        cases = json.loads(FIXTURE.read_text(encoding="utf-8"))
        n = 0
        for c in cases["due_and_pill"]:
            today = c.get("today") or cases["today"]
            row = c["row"]
            self.assertEqual(g.is_overdue(row, today), c["expect"]["due"]["tone"] == "late", c["name"])
            pill = g.pill_of(row, today)
            self.assertEqual((pill["text"], pill["class"]), (c["expect"]["pill"]["text"], c["expect"]["pill"]["class"]), c["name"])
            n += 1
        self.assertGreater(n, 30)


class OverdueTile(unittest.TestCase):
    def test_counts_open_actions_past_due(self):
        d = data(actions=[action(1, "2026-10-27"), action(2, "2026-10-01", "Delayed"), action(3, ON), action(4, "2026-11-30"),
                          action(5, "2026-10-01", "Closed"), action(6, "2026-10-01", "Cancelled"), action(7, None),
                          action(8, "2026-10-01", archived=1)])
        t = by_name(g.tiles(d, ON))["overdue"]
        self.assertEqual((t["value"], t["open"], t["words"]), (2, 5, "2 overdue"))
        self.assertEqual((t["detail"], t["colour"], t["class"]), ("of 5 open actions", "red", "r"))
        self.assertEqual(t["label"], "Overdue actions: 2, of 5 open actions, red")

    def test_the_other_overdue_work_is_reported_beside_it(self):
        d = data(actions=[action(1, "2026-10-27")], raid_=[raid(1, due="2026-10-20"), raid(2, "Issue", due="2026-10-20", status="Closed"),
                                                         raid(3, "Assumption", due="2026-10-27")],
                 decisions=[decision(1, needed_by="2026-10-01"), decision(2, needed_by="2026-12-01")])
        t = by_name(g.tiles(d, ON))["overdue"]
        self.assertEqual(t["value"], 1)
        self.assertEqual(t["parts"], {"actions": 1, "raid": 2, "decisions": 1})
        self.assertEqual(t["all_overdue"], 4)

    def test_plurals(self):
        one = by_name(g.tiles(data(actions=[action(1, "2026-10-27")]), ON))["overdue"]
        self.assertEqual((one["words"], one["detail"]), ("1 overdue", "of 1 open action"))
        two = by_name(g.tiles(data(actions=[action(1, "2026-10-27"), action(2, "2026-10-26")]), ON))["overdue"]
        self.assertEqual((two["words"], two["detail"]), ("2 overdue", "of 2 open actions"))

    def test_none_is_green_and_says_so(self):
        t = by_name(g.tiles(data(actions=[action(1, "2026-12-01")]), ON))["overdue"]
        self.assertEqual((t["value"], t["words"], t["colour"]), (0, "0 overdue", "green"))
        t = by_name(g.tiles(data(), ON))["overdue"]
        self.assertEqual((t["detail"], t["colour"]), ("No open actions", "green"))


class RisksTile(unittest.TestCase):
    def test_counts_open_risks_and_issues_rated_urgent_or_high(self):
        d = data(raid_=[raid(1, priority="Urgent"), raid(2, "Issue", "High"), raid(3, priority="Medium"), raid(4, priority="Low"),
                        raid(5, priority="High", status="Closed"), raid(6, "Assumption", "High"),
                        raid(7, "Dependency", "Urgent"), raid(8, priority="High", archived=1), raid(9, priority=None)])
        t = by_name(g.tiles(d, ON))["risks"]
        self.assertEqual((t["value"], t["high"], t["open"]), (2, 2, 5))
        self.assertEqual((t["detail"], t["colour"], t["class"]), ("of 5 open risks and issues", "red", "r"))

    def test_the_colour_is_the_highest_priority_by_d12(self):
        for priorities, colour in ((["Urgent"], "red"), (["High"], "red"), (["Medium", "Low"], "amber"), (["Low"], "green"),
                                   ([], "green"), ([None], "green"), (["Low", "High", "Medium"], "red")):
            d = data(raid_=[raid(i + 1, priority=p) for i, p in enumerate(priorities)])
            self.assertEqual(by_name(g.tiles(d, ON))["risks"]["colour"], colour, priorities)

    def test_words(self):
        none = by_name(g.tiles(data(), ON))["risks"]
        self.assertEqual((none["value"], none["detail"]), (0, "None open"))
        one = by_name(g.tiles(data(raid_=[raid(1, priority="High")]), ON))["risks"]
        self.assertEqual((one["value"], one["detail"]), (1, "of 1 open risk or issue"))
        self.assertEqual(one["label"], "High risks and issues: 1, of 1 open risk or issue, red")


class DecisionsTile(unittest.TestCase):
    def test_pending_count_and_the_oldest_needed_by(self):
        d = data(decisions=[decision(1, needed_by="2026-11-20"), decision(2, needed_by="2026-11-03"), decision(3),
                            decision(4, "Made", needed_by="2026-01-01"), decision(5, "Withdrawn", needed_by="2026-01-02"),
                            decision(6, needed_by="2026-09-01", archived=1), decision(7, needed_by="2026-02-30")])
        t = by_name(g.tiles(d, ON, hidden=()))["decisions"]
        self.assertEqual((t["value"], t["oldest"], t["oldest_shown"]), (4, "2026-11-03", "03-11-2026"))
        self.assertEqual((t["detail"], t["colour"]), ("Oldest needed by 03-11-2026", "amber"))

    def test_none_waiting_and_none_dated(self):
        t = by_name(g.tiles(data(), ON, hidden=()))["decisions"]
        self.assertEqual((t["value"], t["detail"], t["oldest"], t["colour"]), (0, "None waiting", None, "green"))
        t = by_name(g.tiles(data(decisions=[decision(1)]), ON, hidden=()))["decisions"]
        self.assertEqual((t["value"], t["detail"], t["oldest_shown"]), (1, "No date needed by", ""))


class HealthTile(unittest.TestCase):
    def test_value_reason_and_colour(self):
        t = by_name(g.tiles(data(), ON))["health"]
        self.assertEqual((t["value"], t["health"], t["colour"], t["class"]), ("At risk", "At risk", "amber", "a"))
        self.assertEqual(t["reason"], "Supplier is a fortnight late")
        self.assertEqual(t["label"], "Project health: At risk, amber. Supplier is a fortnight late")

    def test_no_health_set(self):
        d = data()
        d["project"] = {"code": "ABC", "health": None, "health_reason": None}
        t = by_name(g.tiles(d, ON))["health"]
        self.assertEqual((t["value"], t["colour"], t["reason"], t["label"]), ("Not set", None, "", "Project health: Not set"))


class OrderAndHidden(unittest.TestCase):
    def test_default_order_with_decisions_hidden(self):
        got = g.tiles(data(), ON)
        self.assertEqual([t["tile"] for t in got], ["health", "overdue", "risks", "decisions"])
        self.assertEqual([t["hidden"] for t in got], [False, False, False, True])

    def test_glance_tiles_rows_set_order_hidden_and_outline(self):
        rows = [{"project": "ABC", "tile": "risks", "hidden": 0, "outline": "", "sort_order": 1},
                {"project": "ABC", "tile": "health", "hidden": 0, "outline": "N", "sort_order": 2},
                {"project": "ABC", "tile": "decisions", "hidden": 0, "outline": "G", "sort_order": 3},
                {"project": "ABC", "tile": "overdue", "hidden": 1, "outline": "", "sort_order": 4}]
        got = g.tiles(data(glance_tiles=rows, actions=[action(1, "2026-10-27")]), ON)
        self.assertEqual([t["tile"] for t in got], ["risks", "health", "decisions", "overdue"])
        self.assertEqual([t["hidden"] for t in got], [False, False, False, True])
        self.assertEqual([t["outline"] for t in got], ["", "N", "G", ""])
        health, decisions = got[1], got[2]
        self.assertEqual((health["colour"], health["auto_colour"], health["class"]), (None, "amber", "n"))
        self.assertEqual((decisions["colour"], decisions["auto_colour"]), ("green", "green"))

    def test_the_outline_override_wins_over_the_automatic_colour(self):
        d = data(actions=[action(1, "2026-10-27")])
        for code, colour in (("R", "red"), ("A", "amber"), ("G", "green"), ("N", None), ("", "red")):
            t = by_name(g.tiles(d, ON, outlines={"overdue": code}))["overdue"]
            self.assertEqual(t["colour"], colour, code)
            self.assertEqual(t["auto_colour"], "red")
        t = by_name(g.tiles(d, ON, outlines={"overdue": "G"}))["overdue"]
        self.assertEqual(t["label"], "Overdue actions: 1, of 1 open action, green")

    def test_a_tile_with_no_row_comes_last_and_the_milestone_tiles_are_ignored(self):
        rows = [{"project": "ABC", "tile": "next_milestone", "hidden": 0, "outline": "", "sort_order": 0},
                {"project": "ABC", "tile": "overdue", "hidden": 0, "outline": "", "sort_order": 1}]
        got = g.tiles(data(glance_tiles=rows), ON)
        self.assertEqual([t["tile"] for t in got], ["overdue", "health", "risks", "decisions"])
        self.assertEqual([t["hidden"] for t in got], [False, False, False, True])

    def test_order_and_hidden_given_directly(self):
        got = g.tiles(data(), ON, tile_order=["decisions", "health", "milestones_met", "health"], hidden={"health"})
        self.assertEqual([t["tile"] for t in got], ["decisions", "health", "overdue", "risks"])
        self.assertEqual([t["hidden"] for t in got], [False, True, False, False], "an explicit hidden set replaces the default")

    def test_ties_keep_the_default_order(self):
        rows = [{"tile": t, "hidden": 0, "outline": "", "sort_order": 0} for t in ("risks", "health")]
        self.assertEqual([t["tile"] for t in g.tiles(data(glance_tiles=rows), ON)][:2], ["health", "risks"])


class ClientVersion(unittest.TestCase):
    def rows(self):
        return data(
            actions=[action(1, "2026-10-27"), action(2, "2026-10-27", client_visible=0, description=PLANTED_MARKER),
                     action(3, "2026-10-27", client_message=PLANTED_MARKER)],
            raid_=[raid(1, priority="High"), raid(2, priority="Urgent", client_visible=0, response_action=PLANTED_MARKER),
                   raid(3, priority="High")],
            decisions=[decision(1, needed_by="2026-10-01", client_visible=0, reasoning=PLANTED_MARKER),
                       decision(2, needed_by="2026-11-15")],
            report_hidden=[{"project": "ABC", "item_id": "ABC-A-003"}, {"project": "ABC", "item_id": "ABC-003"}],
            glance_tiles=[{"project": "ABC", "tile": "decisions", "hidden": 0, "outline": "", "sort_order": 4}])

    def test_counts_leave_out_the_flag_off_and_the_hidden(self):
        got = by_name(g.tiles(self.rows(), ON, for_client=True))
        self.assertEqual(got["overdue"]["value"], 1)
        self.assertEqual(got["overdue"]["parts"], {"actions": 1, "raid": 0, "decisions": 0})
        self.assertEqual((got["risks"]["value"], got["risks"]["open"]), (1, 1))
        self.assertEqual((got["decisions"]["value"], got["decisions"]["oldest"]), (1, "2026-11-15"))
        editor = by_name(g.tiles(self.rows(), ON))
        self.assertEqual((editor["overdue"]["value"], editor["risks"]["value"], editor["decisions"]["value"]), (3, 3, 2))

    def test_hidden_tiles_are_absent_not_dimmed(self):
        rows = data(glance_tiles=[{"tile": "overdue", "hidden": 1, "outline": "", "sort_order": 1}])
        got = g.tiles(rows, ON, for_client=True)
        self.assertEqual([t["tile"] for t in got], ["health", "risks"], "overdue hidden by the row, decisions by default")
        for t in got:
            self.assertNotIn("hidden", t)

    def test_nothing_internal_reaches_the_client_output(self):
        d = self.rows()
        d["project"]["internal_note"] = PLANTED_MARKER
        d["project"]["publish_local"] = PLANTED_MARKER
        text = json.dumps(g.tiles(d, ON, for_client=True), sort_keys=True)
        self.assertNotIn(PLANTED_MARKER, text)
        for key in ("auto_colour", "outline", "hidden", "source", "client_visible"):
            self.assertNotIn(f'"{key}"', text)

    def test_the_health_reason_is_the_clients_to_read(self):
        t = by_name(g.tiles(self.rows(), ON, for_client=True))["health"]
        self.assertEqual(t["reason"], "Supplier is a fortnight late")


def sections(*hide):
    """The default report sections, with the named types hidden."""
    return [{**sec, "hidden": 1 if sec["type"] in hide else 0} for sec in publish.DEFAULT_SECTIONS]


RULES = [{"name": "Sensitive", "behaviour": "exclude", "default_choice": "exclude"},
         {"name": "Commercial", "behaviour": "exclude", "default_choice": "include"},
         {"name": "Customer", "behaviour": "show", "default_choice": "include"}]


class ClientNumbersAreThePublishedList(unittest.TestCase):
    """"""

    def plant(self, *hide):
        acts = [action(1, "2026-10-20", use_case="ABC-U-001"),                      # kept
                action(2, "2026-10-20", use_case="ABC-U-001"),                      # Sensitive
                action(3, "2026-10-20", use_case="ABC-U-001", client_visible=0),    # flag off
                action(4, "2026-10-20", use_case="ABC-U-001"),                      # left off the page by the eye
                action(5, "2026-10-20", use_case="ABC-U-001"),                      # "sensitive"
                action(6, "2026-10-20", use_case="ABC-U-001"),                      # "SENSITIVE"
                action(7, "2026-10-20", use_case="ABC-U-002"),                      # the only item of use case 2, Sensitive
                action(8, "2026-12-20", use_case="ABC-U-001"),                      # kept, not yet due
                action(9, "2026-10-20", use_case="ABC-U-001")]                      # a label whose rule says exclude
        risks = [raid(1, priority="High", use_case="ABC-U-001"), raid(2, priority="Urgent"), raid(3, "Issue", "High"),
                 raid(4, priority="High")]
        decs = [decision(1, needed_by="2026-10-01", use_case="ABC-U-001"), decision(2, needed_by="2026-10-02"),
                decision(3, needed_by="2026-11-30")]
        ucs = [use_case(1), use_case(2, "Flag"), use_case(3, "High risk")]
        return data(
            actions=acts, raid_=risks, decisions=decs, use_cases=ucs,
            labels={"ABC-A-002": ["Sensitive"], "ABC-A-005": ["sensitive"], "ABC-A-006": ["SENSITIVE"],
                    "ABC-A-007": ["Customer", "Sensitive"], "ABC-A-009": ["Commercial"], "ABC-A-001": ["Customer"],
                    "ABC-002": ["Sensitive"], "ABC-D-002": ["Sensitive"], "ABC-U-003": ["Sensitive"]},
            report_hidden=[{"project": "ABC", "item_id": "ABC-A-004"}, {"project": "ABC", "item_id": "ABC-003"}],
            report_sections=sections(*hide), label_rules=RULES,
            glance_tiles=[{"project": "ABC", "tile": "decisions", "hidden": 0, "outline": "", "sort_order": 4}])

    def published(self, d):
        """The published lists, straight from select with the same inputs (the test does not use glance's own helper)."""
        return publish.select({"data": d, "hidden": [h["item_id"] for h in d["report_hidden"]], "sections": d["report_sections"],
                               "label_rules": d["label_rules"], "as_at": ON})["data"]

    @staticmethod
    def late(rows, key):
        return [r for r in rows if r["status"] not in g.CLOSED and r[key] and r[key] < ON]

    def test_each_client_number_is_the_count_of_the_published_list(self):
        d = self.plant()
        pub = self.published(d)
        self.assertEqual([a["id"] for a in pub["actions"]], ["ABC-A-001", "ABC-A-008"], "the plant: only two actions survive")
        got = by_name(g.tiles(d, ON, for_client=True))
        late = self.late(pub["actions"], "due_date")
        self.assertEqual(len(late), 1)
        self.assertEqual((got["overdue"]["value"], got["overdue"]["open"], got["overdue"]["parts"]["actions"]),
                         (len(late), len(pub["actions"]), len(late)))
        self.assertEqual(got["overdue"]["detail"], "of 2 open actions")
        high = [r for r in pub["raid"] if r["priority"] in ("Urgent", "High")]
        self.assertEqual((got["risks"]["value"], got["risks"]["open"]), (len(high), len(pub["raid"])))
        self.assertEqual(got["decisions"]["value"], len([r for r in pub["decisions"] if r["status"] == "Pending"]))
        self.assertEqual(got["overdue"]["parts"]["decisions"], len(self.late([dict(r, due=r["needed_by"]) for r in pub["decisions"]], "due")))
        self.assertEqual(got["decisions"]["oldest"], min(r["needed_by"] for r in pub["decisions"]))

    def test_the_editor_still_counts_everything(self):
        d = self.plant()
        ed = by_name(g.tiles(d, ON))
        self.assertEqual((ed["overdue"]["value"], ed["overdue"]["open"]), (8, 9), "all nine open, eight past due")
        self.assertEqual((ed["risks"]["value"], ed["risks"]["open"]), (4, 4))
        self.assertEqual(ed["decisions"]["value"], 3)

    def test_the_overdue_probe(self):
        """Four overdue actions: one Sensitive, one flag off, one left off the page. The list has one; the tile says one."""
        d = data(actions=[action(1, "2026-10-01"), action(2, "2026-10-01"), action(3, "2026-10-01", client_visible=0),
                          action(4, "2026-10-01")],
                 labels={"ABC-A-002": ["Sensitive"]}, report_hidden=[{"item_id": "ABC-A-004"}])
        client = by_name(g.tiles(d, ON, for_client=True))["overdue"]
        self.assertEqual((client["value"], client["detail"]), (1, "of 1 open action"))
        self.assertEqual(by_name(g.tiles(d, ON))["overdue"]["value"], 4)

    def test_an_item_in_a_hidden_section_is_in_no_client_number(self):
        d = self.plant("decisions")
        pub = self.published(d)
        self.assertEqual(pub["decisions"], [])
        kept = g.kept_rows(d, ON)
        self.assertEqual(kept["hidden_types"], {"decisions"})
        got = g.tiles(d, ON, for_client=True, kept=kept)
        self.assertNotIn("decisions", [t["tile"] for t in got], "the tile for a hidden section is left out")
        strip = g.use_case_strip(None, None, ON, for_client=True, kept=kept)
        uc1 = strip["rows"][0]
        self.assertEqual((uc1["linked"], uc1["open"], uc1["overdue"]), (3, 3, 1), "the overdue decision is not counted")
        self.assertEqual(by_name(g.tiles(d, ON))["decisions"]["value"], 3, "the editor still sees it")

    def test_a_tile_is_left_out_when_its_section_is_hidden(self):
        for hidden, tile in (("actions", "overdue"), ("raid", "risks"), ("decisions", "decisions")):
            d = self.plant(hidden)
            client = [t["tile"] for t in g.tiles(d, ON, for_client=True)]
            self.assertNotIn(tile, client, hidden)
            self.assertIn("health", client)
            self.assertIn(tile, [t["tile"] for t in g.tiles(d, ON)], "the editor keeps it")
        other = [t["tile"] for t in g.tiles(self.plant("actions"), ON, for_client=True)]
        self.assertEqual(sorted(other), ["decisions", "health", "risks"], "the other tiles stay")
        self.assertEqual(sorted(t["tile"] for t in g.tiles(self.plant("milestones", "usecases"), ON, for_client=True)),
                         ["decisions", "health", "overdue", "risks"], "a section no tile summarises changes nothing")

    def test_hidden_types_agree_with_select(self):
        for hide in ((), ("actions",), ("raid", "decisions"), ("usecases",), ("milestones", "current")):
            d = self.plant(*hide)
            kept = g.kept_rows(d, ON)
            pub = publish.select({"data": d, "hidden": [], "sections": d["report_sections"], "label_rules": RULES, "as_at": ON})
            self.assertEqual(kept["hidden_types"], set(hide))
            for kind, section in publish.SECTION_OF_KIND.items():
                if section in hide:
                    self.assertEqual(pub["data"][kind], [], f"{kind} hidden")
        none = data(actions=[action(1)])
        self.assertEqual(g.kept_rows(none, ON)["hidden_types"], set(), "no sections: select's defaults, none hidden")
        self.assertEqual(g.kept_rows(none, ON)["data"]["actions"][0]["id"], "ABC-A-001")

    def test_the_strip_counts_the_published_rows_only(self):
        d = self.plant()
        pub = self.published(d)
        kept = g.kept_rows(d, ON)
        strip = g.use_case_strip(d["use_cases"], g.work_rows(d), ON, for_client=True, kept=kept)
        self.assertEqual([r["id"] for r in strip["rows"]], [u["id"] for u in pub["use_cases"]], "use case 3 is Sensitive")
        for row in strip["rows"]:
            mine = [r for k in ("actions", "raid", "decisions") for r in pub[k] if r.get("use_case") == row["id"]]
            late = [r for r in self.late(pub["actions"], "due_date") + self.late(pub["raid"], "due_date") if r in mine]
            late += [r for r in pub["decisions"] if r in mine and r["status"] == "Pending" and r["needed_by"] < ON]
            self.assertEqual((row["linked"], row["open"], row["overdue"]), (len(mine), len(mine), len(late)), row["id"])
        one, two = strip["rows"]
        self.assertEqual((one["linked"], one["overdue"], one["words"]), (4, 2, "4 open, 2 overdue"))
        self.assertEqual((two["linked"], two["words"]), (0, "No linked work items"),
                         "a use case linked only to a Sensitive item shows no linked items, not a hint")
        editor = g.use_case_strip(d["use_cases"], g.work_rows(d), ON)
        self.assertEqual([r["linked"] for r in editor["rows"]], [10, 1, 0])
        self.assertEqual(g.use_case_strip(None, None, ON, for_client=True, kept=g.kept_rows(self.plant("usecases"), ON))["rows"], [])

    def test_the_use_case_detail_uses_the_same_rows(self):
        d = self.plant()
        kept = g.kept_rows(d, ON)
        self.assertEqual([r["id"] for r in g.use_case_items(kept, "ABC-U-001")],
                         ["ABC-A-001", "ABC-A-008", "ABC-001", "ABC-D-001"])
        self.assertEqual(g.use_case_items(kept, "ABC-U-002"), [])

    def test_the_label_in_any_case_and_a_rule_added_later(self):
        for label in ("Sensitive", "sensitive", "SENSITIVE", "sEnSiTiVe"):
            d = data(actions=[action(1, "2026-10-01"), action(2, "2026-10-01")], labels={"ABC-A-002": [label]})
            self.assertEqual(by_name(g.tiles(d, ON, for_client=True))["overdue"]["value"], 1, label)
        d = data(actions=[action(1, "2026-10-01"), action(2, "2026-10-01")], labels={"ABC-A-002": ["Draft"]})
        self.assertEqual(by_name(g.tiles(d, ON, for_client=True))["overdue"]["value"], 2, "no rule: nothing dropped")
        d["label_rules"] = [{"name": "draft", "behaviour": "exclude", "default_choice": "include"}]
        self.assertEqual(by_name(g.tiles(d, ON, for_client=True))["overdue"]["value"], 1, "a rule dropped it, whatever its case")

    def test_there_is_one_filter(self):
        self.assertFalse(hasattr(g, "_shown_to_client"))
        import inspect
        self.assertNotIn("client_visible\"]", inspect.getsource(g.tiles), "tiles does not filter by itself")


class Strip(unittest.TestCase):
    def setUp(self):
        self.ucs = [use_case(2, "Flag"), use_case(1, "On track"), use_case(3, "High risk"), use_case(4, "On track")]
        self.d = data(actions=[
            action(1, "2026-10-27", use_case="ABC-U-001"), action(2, "2026-12-01", use_case="ABC-U-001"),
            action(3, "2026-10-01", "Closed", use_case="ABC-U-001"), action(4, None, use_case="ABC-U-002"),
            action(5, "2026-10-29", use_case="ABC-U-003")],
            raid_=[raid(1, "Issue", "Urgent", use_case="ABC-U-003"), raid(2, "Risk", "Low", use_case="ABC-U-002")],
            decisions=[decision(1, needed_by="2026-10-20", use_case="ABC-U-002")])
        self.rows = g.work_rows(self.d)

    def strip(self, **kw):
        return g.use_case_strip(self.ucs, self.rows, ON, **kw)

    def test_sorted_by_sort_order_then_id(self):
        self.assertEqual([r["id"] for r in self.strip()["rows"]], ["ABC-U-001", "ABC-U-002", "ABC-U-003", "ABC-U-004"])
        tied = [use_case(1, sort_order=5), use_case(2, sort_order=5), use_case(3, sort_order=1)]
        self.assertEqual([r["id"] for r in g.use_case_strip(tied, [], ON)["rows"]], ["ABC-U-003", "ABC-U-001", "ABC-U-002"])

    def test_counts_per_status_in_the_schemas_order(self):
        s = self.strip()
        self.assertEqual((s["total"], s["total_words"]), (4, "4 use cases"))
        self.assertEqual([(c["status"], c["colour"], c["count"]) for c in s["counts"]],
                         [("On track", "green", 2), ("Flag", "amber", 1), ("High risk", "red", 1)])

    def test_open_overdue_next_steps_and_worst_colour(self):
        r = {x["id"]: x for x in self.strip()["rows"]}
        one = r["ABC-U-001"]
        self.assertEqual((one["linked"], one["open"], one["overdue"], one["next_steps"], one["worst"]), (3, 2, 1, 2, "red"))
        self.assertEqual((one["words"], one["steps_words"]), ("2 open, 1 overdue", "2 next steps"))
        two = r["ABC-U-002"]    # an open action with no date, a Low risk, and a pending decision that is late
        self.assertEqual((two["linked"], two["open"], two["overdue"], two["next_steps"], two["worst"]), (3, 3, 1, 1, "green"))
        three = r["ABC-U-003"]
        self.assertEqual((three["open"], three["overdue"], three["worst"], three["steps_words"]), (2, 0, "red", "1 next step"))
        self.assertEqual(three["words"], "2 open")

    def test_a_use_case_with_nothing_linked_says_so(self):
        four = {x["id"]: x for x in self.strip()["rows"]}["ABC-U-004"]
        self.assertEqual((four["words"], four["steps_words"], four["linked"], four["worst"]),
                         ("No linked work items", "No open steps", 0, None))

    def test_a_use_case_with_only_closed_items(self):
        rows = g.work_rows(data(actions=[action(1, "2026-10-01", "Closed", use_case="ABC-U-001"),
                                         action(2, None, "Cancelled", use_case="ABC-U-001")]))
        r = g.use_case_strip([use_case(1)], rows, ON)["rows"][0]
        self.assertEqual((r["words"], r["linked"], r["open"], r["worst"]), ("No open work items", 2, 0, None))

    def test_boundary_dates(self):
        for due, late in (("2026-10-28", 0), ("2026-10-27", 1)):
            rows = g.work_rows(data(actions=[action(1, due, use_case="ABC-U-001")]))
            self.assertEqual(g.use_case_strip([use_case(1)], rows, ON)["rows"][0]["overdue"], late, due)

    def test_the_worst_colour_follows_the_list_pills(self):
        for item, worst in ((action(1, "2026-10-29", use_case="ABC-U-001"), "amber"),      # due soon
                            (action(1, "2026-12-30", use_case="ABC-U-001"), None),         # plain Open
                            (action(1, "2026-12-30", "Delayed", use_case="ABC-U-001"), "amber"),
                            (action(1, "2026-10-01", use_case="ABC-U-001"), "red")):
            rows = g.work_rows(data(actions=[item]))
            self.assertEqual(g.use_case_strip([use_case(1)], rows, ON)["rows"][0]["worst"], worst, item["due_date"])

    def test_one_use_case_has_singular_words(self):
        s = g.use_case_strip([use_case(1)], [], ON)
        self.assertEqual((s["total_words"], s["rows"][0]["steps_words"]), ("1 use case", "No open steps"))
        self.assertEqual(g.use_case_strip([], [], ON), {"total": 0, "total_words": "No use cases", "counts": [], "rows": []})

    def test_archived_use_cases_are_left_out(self):
        s = g.use_case_strip([use_case(1), use_case(2, archived=1)], [], ON)
        self.assertEqual([r["id"] for r in s["rows"]], ["ABC-U-001"])

    def test_a_status_the_schema_does_not_allow_is_shown_as_stored_with_no_colour(self):
        r = g.use_case_strip([use_case(1, "Finished")], [], ON)["rows"][0]
        self.assertEqual((r["status"], r["colour"], r["class"]), ("Finished", None, "n"))
        self.assertEqual(g.use_case_strip([use_case(1, "Finished")], [], ON)["counts"], [], "it has no place in the counts")

    def test_done_is_grey_with_its_own_word_and_its_own_count_after_the_others(self):
        """#412: Done is a status: its word, grey (never colour alone: the word is always there), and a count after High risk."""
        s = g.use_case_strip([use_case(1, "Done"), use_case(2, "Flag"), use_case(3, "Done")], [], ON)
        r = s["rows"][0]
        self.assertEqual((r["status"], r["colour"], r["class"]), ("Done", "grey", "n"))
        self.assertEqual([(c["status"], c["colour"], c["class"], c["count"]) for c in s["counts"]],
                         [("Flag", "amber", "a", 1), ("Done", "grey", "n", 2)])
        self.assertEqual(g.USE_CASE_STATUSES[-1], "Done")

    def test_the_client_version_whitelist(self):
        ucs = [use_case(1, source=PLANTED_MARKER, standing=f"<p>{PLANTED_MARKER}</p>", state_notes=PLANTED_MARKER, internal_note=PLANTED_MARKER),
               use_case(2, client_visible=0, title=PLANTED_MARKER, headline=PLANTED_MARKER, ref=PLANTED_MARKER),
               use_case(3, "Flag", headline="Visible")]
        d = data(actions=[action(1, "2026-10-27", use_case="ABC-U-001", description=PLANTED_MARKER, client_message=PLANTED_MARKER),
                          action(2, "2026-10-27", use_case="ABC-U-001", client_visible=0, description=PLANTED_MARKER),
                          action(3, "2026-10-27", use_case="ABC-U-001", description=PLANTED_MARKER),
                          action(4, "2026-10-27", use_case="ABC-U-002", description=PLANTED_MARKER)])
        rows = g.work_rows(d)
        kept = g.kept_rows({**d, "use_cases": ucs, "report_hidden": [{"project": "ABC", "item_id": "ABC-A-003"}]}, ON)
        s = g.use_case_strip(ucs, rows, ON, for_client=True, kept=kept)
        self.assertEqual([r["id"] for r in s["rows"]], ["ABC-U-001", "ABC-U-003"])
        self.assertEqual((s["total"], s["rows"][0]["linked"], s["rows"][0]["open"], s["rows"][0]["overdue"]), (2, 1, 1, 1))
        text = json.dumps(s, sort_keys=True)
        self.assertNotIn(PLANTED_MARKER, text)
        self.assertNotIn("ABC-U-002", text)
        self.assertEqual(sorted(s["rows"][0]), sorted(["id", "ref", "title", "headline", "status", "colour", "class", "linked",
                                                         "open", "overdue", "next_steps", "worst", "words", "steps_words"]))
        editor = g.use_case_strip(ucs, rows, ON)
        self.assertEqual([r["client_visible"] for r in editor["rows"]], [True, False, True])
        self.assertEqual(editor["rows"][0]["linked"], 3, "the editor counts every linked item")
        with self.assertRaises(ValueError):
            g.use_case_strip(ucs, rows, ON, for_client=True)

    def test_work_rows_carry_no_text(self):
        d = data(actions=[action(1, description=PLANTED_MARKER, client_message=PLANTED_MARKER, latest_update=PLANTED_MARKER)],
                 raid_=[raid(1, response_action=PLANTED_MARKER)], decisions=[decision(1, reasoning=PLANTED_MARKER)])
        self.assertNotIn(PLANTED_MARKER, json.dumps(g.work_rows(d)))


class Determinism(unittest.TestCase):
    def test_the_same_input_gives_the_same_output(self):
        d = data(actions=[action(1, "2026-10-27", use_case="ABC-U-001")], raid_=[raid(1, priority="High")],
                 decisions=[decision(1, needed_by="2026-11-03")])
        self.assertEqual(g.tiles(d, ON), g.tiles(d, ON))
        before = json.dumps(d, sort_keys=True)
        a = g.use_case_strip([use_case(1)], g.work_rows(d), ON)
        self.assertEqual(a, g.use_case_strip([use_case(1)], g.work_rows(d), ON))
        self.assertEqual(json.dumps(d, sort_keys=True), before, "the rows are not changed")

    def test_the_date_comes_only_from_the_argument(self):
        d = data(actions=[action(1, "2026-10-28")])
        self.assertEqual(by_name(g.tiles(d, "2026-10-28"))["overdue"]["value"], 0)
        self.assertEqual(by_name(g.tiles(d, "2026-10-29"))["overdue"]["value"], 1)


class Words(unittest.TestCase):
    def test_plain_words_british_english(self):
        shown = json.dumps([g.tiles(data(), ON), g.use_case_strip([use_case(1)], [], ON)])
        for word in ("UC ", "color", "Color", "Clark"):
            self.assertNotIn(word, shown)


class DemoData(unittest.TestCase):
    """The tiles against the demo database at the demo clock: the figures are counted again here straight from the tables."""
    NOW = datetime(2026, 10, 28, 9, 0)

    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("demo_data", str(ROOT / "dev" / "demo_data.py"))
        demo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(demo)
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = Path(cls.tmp.name) / "clark.db"
        demo.build(cls.path, cls.NOW)
        cls.store = open_store(cls.path, onedrive_roots=[])

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        cls.tmp.cleanup()

    def count(self, sql, *args):
        con = sqlite3.connect(str(self.path))
        try:
            return con.execute(sql, args).fetchone()[0]
        finally:
            con.close()

    def test_each_demo_project(self):
        for code in ("TUL", "MOSS"):
            d = self.store.data_for(code)
            got = by_name(g.tiles(d, ON, hidden=()))
            late = self.count("SELECT count(*) FROM actions WHERE project = ? AND status IN ('Open','Delayed') AND due_date < ? "
                              "AND archived = 0", code, ON)
            high = self.count("SELECT count(*) FROM raid WHERE project = ? AND status = 'Open' AND type IN ('Risk','Issue') "
                              "AND priority IN ('Urgent','High') AND archived = 0", code)
            pending = self.count("SELECT count(*) FROM decisions WHERE project = ? AND status = 'Pending' AND archived = 0", code)
            self.assertEqual((got["overdue"]["value"], got["risks"]["value"], got["decisions"]["value"]), (late, high, pending), code)
            self.assertEqual(got["health"]["health"], d["project"]["health"])
        tul = by_name(g.tiles(self.store.data_for("TUL"), ON))
        self.assertGreater(tul["overdue"]["value"], 0, "the demo data has late actions to count")

    def test_the_strip_on_the_demo_data(self):
        d = self.store.data_for("TUL")
        s = g.use_case_strip(d["use_cases"], g.work_rows(d), ON)
        self.assertEqual(s["total"], len(d["use_cases"]))
        self.assertEqual(sum(c["count"] for c in s["counts"]), s["total"])
        linked = self.count("SELECT count(*) FROM (SELECT use_case FROM actions WHERE project = 'TUL' AND use_case IS NOT NULL "
                            "AND archived = 0 UNION ALL SELECT use_case FROM raid WHERE project = 'TUL' AND use_case IS NOT NULL "
                            "AND archived = 0 UNION ALL SELECT use_case FROM decisions WHERE project = 'TUL' "
                            "AND use_case IS NOT NULL AND archived = 0)")
        self.assertEqual(sum(r["linked"] for r in s["rows"]), linked)


if __name__ == "__main__":
    unittest.main()
