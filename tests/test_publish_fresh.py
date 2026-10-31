"""#159: the Publish dialog lists open items with no owner or no date, and open items not reviewed in a while, each with Show them.

Run: python3 dev/run_tests.py test_publish_fresh
Part 1 runs the page's own pure modules (filters.js, publishCheck.js) in headless Chrome over small rows. Part 2 opens the real dialog
against the real routes (the publish rig) at 1400 and 900 px, light and dark. Part 3 checks the published file holds none of it.
Chrome is required: these tests fail, never skip, without it.
"""
import json
import threading
import unittest
from unittest import mock

import _publish_fixture as fx
from _paths import SRC
from test_page import navigate
from test_publish_route import Rig
from test_publish_dialog import Base, Pg, WIDTHS
from test_server import chrome, wait
from test_work_items import bundled, page_target

from clark import page

PAGE_SRC = SRC / "clark" / "page" / "src"
TODAY = "2026-10-28"
OPEN = {"status": "Open", "kind": "action", "owner": "Delivery lead", "due_date": "2026-11-06"}


def row(id_, **kw):
    return {**OPEN, "id": id_, **kw}


class Logic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = bundled(PAGE_SRC / "edit" / "publishCheck.js", "PC") + ";\n" + bundled(PAGE_SRC / "filters.js", "F")

    def run_js(self, expr):
        with chrome() as cdp:
            sid = page_target(cdp)
            return cdp.js(self.src + ";\n(" + expr + ")", sid)

    def groups(self, rows):
        return self.run_js(f"PC.groups({json.dumps(rows)}, {json.dumps(TODAY)})")

    def test_each_group_has_a_count_and_plain_words(self):
        rows = [row("A", owner=""), row("B", owner="TBC"), row("C", due_date=None), row("D", not_reviewed=True), row("E", not_reviewed=True),
                row("F", not_reviewed=True)]
        g = self.groups(rows)
        self.assertEqual([(x["value"], x["count"], x["text"]) for x in g],
                         [("incomplete", 3, "3 open items have no owner or no date."),
                          ("stale", 3, "3 open items have not been reviewed in 14 days.")])

    def test_one_item_reads_in_the_singular(self):
        g = self.groups([row("A", owner=""), row("B", not_reviewed=True)])
        self.assertEqual([x["text"] for x in g], ["1 open item has no owner or no date.", "1 open item has not been reviewed in 14 days."])

    def test_a_decision_needs_a_date_only_while_pending(self):
        g = self.groups([{"id": "D1", "kind": "decision", "status": "Pending", "owner": "Group", "needed_by": None},
                         {"id": "D2", "kind": "decision", "status": "Made", "owner": "Group", "date": None}])
        self.assertEqual([x["count"] for x in g], [1])

    def test_a_missing_date_counts_only_for_actions_and_decisions(self):
        for kind, counts in (("action", 1), ("risk", 0), ("issue", 0), ("assumption", 0), ("dependency", 0)):
            self.assertEqual(sum(x["count"] for x in self.groups([row("A", kind=kind, due_date=None)])), counts, kind)
        pending = {"id": "D1", "kind": "decision", "status": "Pending", "owner": "Group", "needed_by": None}
        self.assertEqual(sum(x["count"] for x in self.groups([pending])), 1, "decision")

    def test_a_missing_owner_counts_for_every_open_type(self):
        for kind in ("action", "risk", "issue", "assumption", "dependency"):
            self.assertEqual(sum(x["count"] for x in self.groups([row("A", kind=kind, owner="", due_date="2026-11-06")])), 1, kind)
        self.assertEqual(sum(x["count"] for x in self.groups([{"id": "D1", "kind": "decision", "status": "Pending", "owner": "TBC", "needed_by": "2026-11-06"}])), 1)

    def test_show_them_names_are_distinct_and_number_right(self):
        g = self.groups([row("A", owner=""), row("B", owner=""), row("C", not_reviewed=True)])
        self.assertEqual([x["label"] for x in g], ["Show them: 2 items with no owner or no date", "Show them: 1 item not reviewed in 14 days"])

    def test_closed_items_are_never_listed(self):
        rows = [row(str(i), status=s, owner="", due_date=None, not_reviewed=True) for i, s in enumerate(["Closed", "Cancelled", "Made", "Withdrawn"])]
        self.assertEqual(self.groups(rows), [])

    def test_nothing_when_everything_is_fresh(self):
        self.assertEqual(self.groups([row("A"), row("B", not_reviewed=False)]), [])
        self.assertEqual(self.groups([]), [])

    def test_not_reviewed_follows_the_dates_a_row_carries(self):
        old = row("A", last_reviewed="2026-10-01")
        edge = row("B", last_reviewed="2026-10-14")             # exactly 14 days: not yet
        self.assertEqual([x["count"] for x in self.groups([old, edge])], [1])

    def test_show_them_is_exactly_those_items(self):
        rows = [row("A", owner=""), row("B", due_date=None, not_reviewed=True), row("C"), row("D", not_reviewed=True), row("E", status="Closed", owner="")]
        for value, want in (("incomplete", ["A", "B"]), ("stale", ["B", "D"])):
            got = self.run_js(f"F.applyFilters({json.dumps(rows)}, PC.showState({json.dumps(value)}), {json.dumps(TODAY)}).map((r) => r.id)")
            self.assertEqual(got, want, value)
        self.assertEqual(self.run_js("F.encode(PC.showState('incomplete'))"), "reviewed:incomplete")
        self.assertEqual(self.run_js("F.decode('reviewed:incomplete').filters.reviewed"), ["incomplete"])


REAL_LOAD = fx.load


def planted():
    plant = REAL_LOAD()
    for r in plant["data"]["actions"]:
        if r["id"] == "PUB-A-001":
            r["owner"] = "TBC"
        elif r["id"] == "PUB-A-002":
            r["due_date"] = None
        elif r["id"] == "PUB-A-014":
            r.update(status="Closed", owner="TBC", due_date=None)
        elif r["id"] == "PUB-A-016":
            r.update(owner="TBC", due_date=None)                 # archived: never listed
    return plant


class Dialog(Base):
    def setUp(self):
        with mock.patch.object(fx, "load", planted):
            super().setUp()

    def test_the_dialog_lists_the_group_and_show_them_opens_those(self):
        with chrome() as cdp:
            p = self.page(cdp, "#dashboard&p=PUB")
            for w in WIDTHS:
                for scheme in ("light", "dark"):
                    cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, p.sid)
                    p.width(w)
                    p.open_publish()
                    self.assertEqual(p.js("document.querySelectorAll('#pub-fresh [data-fresh]').length"), 1, "one group: the data has no review dates")
                    self.assertIn("2 open items have no owner or no date.", p.dialog_text())
                    self.assertIn("Show them, or publish anyway.", p.dialog_text())
                    self.assertFalse(p.js("document.querySelector('[data-go]').disabled"), "never blocks")
                    self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"))
                    p.js("document.querySelector('#publish-dialog [data-show=incomplete]').click()")
                    p.until("!document.querySelector('#publish-dialog')", "the dialog closed")
                    p.until("location.hash.indexOf('reviewed:incomplete') > 0 && location.hash.indexOf('#work') === 0", "Work items, filtered")
                    p.until("document.querySelectorAll('[data-row], tr[data-id]').length === 2 || /2 open items/.test(document.body.innerText)", "two items")
                    self.assertIn("Freshness", p.js("document.body.innerText"))
                    p.js("location.hash = '#dashboard&p=PUB'")
                    p.until("!!document.querySelector('#profile-btn')", "back")

    def test_show_them_is_blocked_while_the_report_is_publishing(self):
        gate, inside = threading.Event(), threading.Event()
        save = self.rig.publisher.choose_save_file

        def slow(prompt, name, start=None):
            inside.set()
            gate.wait(20)
            return save(prompt, name, start)
        self.rig.publisher.choose_save_file = slow
        try:
            with chrome() as cdp:
                p = self.page(cdp, "#dashboard&p=PUB")
                p.open_publish()
                self.assertEqual(p.js("document.querySelector('#publish-dialog [data-show=incomplete]').disabled"), False)
                self.assertEqual(p.js("document.querySelector('#publish-dialog [data-show=incomplete]').getAttribute('aria-label')"),
                                 "Show them: 2 items with no owner or no date")
                p.go()
                self.assertTrue(inside.wait(10))
                p.until("document.querySelector('#publish-dialog [data-show=incomplete]').disabled", "Show them waits like Cancel")
                self.assertTrue(p.js("document.querySelector('[data-cancel]').disabled"))
                p.js("document.querySelector('#publish-dialog [data-show=incomplete]').click()")
                self.assertTrue(p.js("!!document.querySelector('#publish-dialog[open]')"), "the dialog stays")
                gate.set()
                p.until("/Published/.test(document.querySelector('#pub-msg').innerText)", "the result is seen")
        finally:
            gate.set()

    def test_nothing_is_listed_when_everything_is_fresh(self):
        rig = Rig(self)                                         # the plain plant: every open item has an owner and a date
        with chrome() as cdp:
            sid = navigate(cdp, rig.httpd.server_port, "#dashboard&p=PUB")
            p = Pg(self, cdp, sid)
            p.until("!!document.querySelector('#profile-btn')", "ready")
            p.open_publish()
            self.assertEqual(p.js("!!document.querySelector('#pub-fresh')"), False, "no empty box")
            self.assertNotIn("open item", p.dialog_text())


class Published(unittest.TestCase):
    def test_the_published_file_holds_none_of_the_dialog_words(self):
        view = page.VIEW_PAGE.read_text(encoding="utf-8")
        for never in ("data-fresh", "Show them", "Show them, or publish anyway", "have no owner or no date", "have not been reviewed in"):
            self.assertNotIn(never, view, never)
        self.assertIn("data-fresh", page.PAGE.read_text(encoding="utf-8"), "the served page has it")


if __name__ == "__main__":
    unittest.main()
