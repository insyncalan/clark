"""Row 1339, Work items Edit: the Configure box's Sort by offers Due date, Priority, Type, Owner (the approved mock-up) in the Classic theme;
Cards keeps Due date, Priority, ID. Type and Owner are real sorts, the same in the page's rules and in publish. The column order of the box was
built in row 1195 and stays pinned by test_work_items_mockup_1195.
Run: python3 dev/run_tests.py test_wil_sort_options_1339.py"""
import json
import unittest

import test_tpl_workitems as T
import test_work_items_mockup_1195 as M
from clark.section_kinds import base, workitems as wi
from test_report_editor import tearDownModule  # noqa: F401
import test_server  # noqa: F401  this file drives Chrome through the template harness (the browser tier reads this line)

SORTS = [{"sort": "type", "mode": "all"}, {"sort": "owner", "mode": "all"}, {"sort": "type"}, {"sort": "owner", "max": 3},
         {"sort": "owner", "mode": "all", "kinds": ["risk", "issue", "decision"]}]


class Rules(unittest.TestCase):
    def test_type_sorts_by_the_kind_then_the_due_day_then_the_id_and_owner_by_name_with_no_owner_last(self):
        ids = lambda v: wi.matching(T.check(v), wi.rows_of(T.ROWS), T.TODAY)
        rows = wi.rows_of(T.ROWS)
        kinds = {r["id"]: r["kind"] for r in rows}
        got = ids({"sort": "type", "mode": "all", "max": 50})
        order = [wi.KINDS.index(kinds[i]) for i in got if wi._open(next(r for r in rows if r["id"] == i))]
        self.assertEqual(order, sorted(order), "open rows in the order of the kinds")
        got = ids({"sort": "owner", "mode": "all", "max": 50})
        owners = {r["id"]: str(r.get("owner") or "").strip().lower() for r in rows}
        open_ids = [i for i in got if wi._open(next(r for r in rows if r["id"] == i))]
        named = [owners[i] for i in open_ids if owners[i]]
        self.assertEqual(named, sorted(named), "open rows by owner name")
        blank_at = [n for n, i in enumerate(open_ids) if not owners[i]]
        self.assertTrue(all(n >= len(named) for n in blank_at), "an item with no owner comes after the named ones")
        self.assertNotEqual(got, ids({"sort": "due", "mode": "all", "max": 50}), "a different order from Due date")

    def test_the_checker_keeps_type_and_owner_and_still_refuses_another_word(self):
        self.assertEqual(T.check({"sort": "type"})["sort"], "type")
        self.assertEqual(T.check({"sort": "owner"})["sort"], "owner")
        self.assertEqual(T.check({"sort": "id"})["sort"], "id")
        self.assertEqual(wi.SORTS, ("due", "priority", "id", "type", "owner"))
        with self.assertRaises(base.Bad):
            T.check({"sort": "ZQ-sort"})


ODD = [  # fictional rows: owners in mixed case with spaces, an unknown kind, one with no owner
    {"id": "Z-1", "kind": "action", "owner": "bo Demo", "status": "Open", "due": None},
    {"id": "Z-2", "kind": "action", "owner": "  Al Demo ", "status": "Open", "due": None},
    {"id": "Z-3", "kind": "zzkind", "owner": "Cy Demo", "status": "Open", "due": None},
    {"id": "Z-4", "kind": "risk", "owner": "", "status": "Open", "due": None},
    {"id": "Z-5", "kind": "decision", "owner": "AL Demo", "status": "Pending", "due": None}]


class Odd(unittest.TestCase):
    def test_owner_ignores_case_and_edge_spaces_and_an_unknown_kind_sorts_after_every_known_one(self):
        f = T.check({"sort": "owner", "mode": "all", "max": 50})
        self.assertEqual(wi.matching(f, ODD, T.TODAY), ["Z-2", "Z-5", "Z-1", "Z-3", "Z-4"])
        f = T.check({"sort": "type", "mode": "all", "max": 50})
        self.assertEqual(wi.matching(f, ODD, T.TODAY), ["Z-1", "Z-2", "Z-4", "Z-5", "Z-3"])


class PageRules(T.PageRules):
    def test_the_page_and_publish_choose_the_same_ids_in_the_same_order(self):
        for f in SORTS:
            with self.subTest(filter=f):
                want = wi.matching(T.check(f), wi.rows_of(T.ROWS), T.TODAY)
                page = self.val(f"W.matching(W.filterOf({{body: {json.dumps(T.stored(f))}}}), W.ruleRows({json.dumps(T.ROWS)}), {json.dumps(T.TODAY)})")
                self.assertEqual(page, want)

    def test_the_page_offers_the_layers_own_sorts_and_the_saved_one_if_missing(self):
        self.assertEqual(self.val("W.sortChoices(true, 'due')"), ["due", "priority", "type", "owner"])
        self.assertEqual(self.val("W.sortChoices(false, 'due')"), ["due", "priority", "id"])
        self.assertEqual(self.val("W.sortChoices(true, 'id')"), ["due", "priority", "type", "owner", "id"])
        self.assertEqual(self.val("W.sortChoices(false, 'owner')"), ["due", "priority", "id", "owner"])

    def test_the_page_orders_odd_owners_and_an_unknown_kind_as_publish_does(self):
        for sort in ("owner", "type"):
            f = T.check({"sort": sort, "mode": "all", "max": 50})
            want = wi.matching(f, ODD, T.TODAY)
            page = self.val(f"W.matching(W.filterOf({{body: {json.dumps(T.stored({'sort': sort, 'mode': 'all', 'max': 50}))}}}), {json.dumps(ODD)}, {json.dumps(T.TODAY)})")
            self.assertEqual(page, want, sort)
    test_current_lists_open_rows_and_a_decision_made_in_the_last_14_days = None
    test_a_decision_has_no_priority_in_the_rules_as_on_the_work_items_page = None


PROBE = ("JSON.stringify([...document.querySelectorAll('%s .wil-cfg [data-field=sort] option')].map(o => o.textContent))")


class ConfigureOptions:
    want = []

    def test_the_box_lists_the_sort_options_at_1400_and_900(self):
        ref = self.add({"mode": "all", "columns": ["id", "owner"], "owner": ["Pat Demo"]})
        sec = f'[data-id="{ref}"]'
        for width in (1400, 900):
            with self.subTest(width=width), T.chrome() as cdp:
                p = self.show(cdp, width)
                p.edit()
                p.until(f"!!document.querySelector('{sec} [data-wil-gear]')", "drew")
                p.js(f"document.querySelector('{sec} [data-wil-gear]').click()")
                p.until(f"!document.querySelector('{sec} .wil-cfg').hidden", "open")
                self.assertEqual(json.loads(p.js(PROBE % sec)), self.want)

    def test_a_saved_sort_the_layer_does_not_offer_is_still_shown_selected(self):
        ref = self.add({"mode": "all", "sort": self.odd, "owner": ["Pat Demo"]})
        sec = f'[data-id="{ref}"]'
        with T.chrome() as cdp:
            p = self.show(cdp, 1400)
            p.edit()
            p.until(f"!!document.querySelector('{sec} [data-wil-gear]')", "drew")
            self.assertEqual(p.js(f"document.querySelector('{sec} .wil-cfg [data-field=sort] select').value"), self.odd)


class ClassicOptions(ConfigureOptions, M.Look):
    want = ["Due date", "Priority", "Type", "Owner"]
    odd = "id"

    def test_choosing_owner_saves_it_and_orders_the_rows(self):
        ref = self.add({"mode": "all", "columns": ["id", "owner"], "owner": ["Pat Demo", "Lee Demo", "Sam Demo"]})
        sec = f'[data-id="{ref}"]'
        with T.chrome() as cdp:
            p = self.show(cdp, 1400)
            p.edit()
            p.until(f"!!document.querySelector('{sec} [data-wil-gear]')", "drew")
            p.js(f"document.querySelector('{sec} [data-wil-gear]').click()")
            p.js("(s => { const e = document.querySelector(s + ' .wil-cfg [data-field=sort] select'); e.value = 'owner'; e.dispatchEvent(new Event('change', {bubbles: true})); })(" + json.dumps(sec) + ")")
            p.until("(s => { const t = [...document.querySelectorAll(s + ' .wil-table td.wil-c-owner')].map(e => e.textContent.trim().toLowerCase()); return t.length > 1 && t.join('|') === [...t].sort().join('|'); })(" + json.dumps(sec) + ")", "rows by owner")


class CardsOptions(ConfigureOptions, M.Look):
    classic = False
    want = ["Due date", "Priority", "ID"]
    odd = "owner"


if __name__ == "__main__":
    unittest.main()
