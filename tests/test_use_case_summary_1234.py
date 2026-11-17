"""Row 1234: the dashboard's Use case summary redesign, the parts that need no new words (page test skeleton).

Run: ~/ag/slot.sh with, inside tests/: PYTHONPATH=../src:../vendor:. python3 -m unittest test_use_case_summary_1234
Data: tests/fixtures/uc_summary_demo.json (6 use cases: statuses, commitments, open steps, work items), fictional.
Laptop widths only: 1400 and 900 px.

These tests are written ahead of the build and nothing is skipped, so some fail until it exists. The hooks they assume are
named once below; when the build names them differently, change them here only.
  VIEW_KEY    the "n" field of the usecases section body (how many rows the summary shows).
  SCROLL_KEY  the "scroll" field of the same body (false = no scrolling).
  SCROLLER    the element that scrolls when scroll is on.
Today's page (row 1108) shows RAIL = 5 rows, "Show all N use cases" / "Show the first 5", kept in 'clark.ucAll'.
"""
import json
import unittest

from _demo import USER
from _paths import ROOT
from _uc_view import put_view
from test_glance_page import Setup, tearDownModule  # noqa: F401
from test_server import chrome

VIEW_KEY = "n"
SCROLL_KEY = "scroll"
SCROLLER = ".ucrows"
ROWS = "document.querySelectorAll('.ucrows > .ucrow').length"
BUTTON = "(document.querySelector('[data-ucall]') || {}).textContent"
DEMO = json.loads((ROOT / "tests" / "fixtures" / "uc_summary_demo.json").read_text(encoding="utf-8"))["use_cases"]


class Demo(Setup):
    """Setup plants two use cases (refs 1.1 and 1.2) in ABC; this adds the demo page's 6, so 8 in all, and their open steps and work items."""

    def setUp(self):
        super().setUp()
        self.ids = {}
        with self.store.step("dashboard", USER) as st:
            for u in DEMO:
                self.ids[u["ref"]] = st.create("use_cases", {"project": "ABC", "title": u["title"], "status": u["status"], "ref": u["ref"],
                                                             "headline": u["headline"], "commitment": u["commitment"], "source": "demo"})
        for u in DEMO:
            for n in range(u["open_steps"]):
                self.demo.action(description=f"{u['title']} step {n + 1}", owner="Pat Demo", due_date="2099-01-01", use_case=self.ids[u["ref"]])
        with self.store.step("dashboard", USER) as st:
            for u in DEMO:
                for n in range(u["work_items"]):
                    if n == 0:
                        st.create("raid", {"project": "ABC", "type": "Risk", "description": f"{u['title']} risk", "raised": "2026-10-01", "source": "demo",
                                           "impact": "Low", "likelihood": "Low", "owner": "Pat Demo", "use_case": self.ids[u["ref"]]})
                    else:
                        st.create("decisions", {"project": "ABC", "decision": f"{u['title']} decision", "source": "demo", "status": "Pending",
                                                "use_case": self.ids[u["ref"]]})
        self.total = 2 + len(DEMO)

    def set_local(self, p, **kv):
        put_view(self, kv)
        p.reload()
        p.until("!!document.querySelector('.uc')", "the summary drew again")

    def edit(self, p):
        p.js("document.querySelector('[data-mode=edit]').click()")
        p.until("!!document.querySelector('[data-uc-configure]')", "Edit")


class DemoData(Demo):
    def test_the_demo_page_plants_the_six_use_cases_with_their_statuses_commitments_steps_and_work_items(self):
        read = {r["ref"]: r for r in self.store.read("use_cases", "ABC")}
        for u in DEMO:
            with self.subTest(ref=u["ref"]):
                self.assertEqual(read[u["ref"]]["status"], u["status"])
                self.assertEqual(read[u["ref"]].get("commitment"), u["commitment"])
        d = self.store.data_for("ABC")
        for u in DEMO:
            with self.subTest(ref=u["ref"], what="links"):
                uid = self.ids[u["ref"]]
                self.assertEqual(sum(1 for a in d["actions"] if a.get("use_case") == uid), u["open_steps"])
                self.assertEqual(sum(1 for k in ("raid", "decisions") for r in d[k] if r.get("use_case") == uid), u["work_items"])


class RowCount(Demo):
    def test_the_row_count_honours_the_view_number(self):
        for width in (1400, 900):
            for n in (3, 6):
                with self.subTest(width=width, view=n), chrome() as cdp:
                    p = self.show(cdp, width)
                    self.set_local(p, **{VIEW_KEY: n})
                    self.assertEqual(p.js(ROWS), n)
                    self.assertEqual(p.js("document.querySelector('.uctotal').textContent"), f"{self.total} use cases", "the count still covers every use case")

    def test_show_all_shows_every_use_case_and_show_the_first_5_goes_back_while_no_number_is_set(self):
        """Ruling 16-11 01:00: the old link stays only until Configure sets a number."""
        with chrome() as cdp:
            p = self.show(cdp)
            self.set_local(p)
            self.assertEqual(p.js(ROWS), 5)
            self.assertEqual(p.js(BUTTON), f"Show all {self.total} use cases")
            p.js("document.querySelector('[data-ucall]').click()")
            p.until(f"{ROWS} === {self.total}", "all shown")
            self.assertEqual(p.js(BUTTON), "Show the first 5")
            p.js("document.querySelector('[data-ucall]').click()")
            p.until(f"{ROWS} === 5", "reduced")

    def test_a_set_number_has_no_show_all_link_and_an_old_show_all_does_not_open_the_rest(self):
        """Ruling 16-11 01:00: the old link goes once Configure sets the number; scroll off then means viewers see only the first n."""
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                p.js("localStorage.setItem('clark.ucAll', 'true')")
                self.set_local(p, **{VIEW_KEY: 2, SCROLL_KEY: False})
                self.assertEqual(p.js(ROWS), 2, "the number wins over an old Show all")
                self.assertIsNone(p.js(BUTTON), "no Show all link")
                self.edit(p)
                self.assertIsNone(p.js(BUTTON), "no Show all link in Edit either")

    def test_a_view_number_at_or_above_the_total_has_no_show_all(self):
        with chrome() as cdp:
            p = self.show(cdp)
            self.set_local(p, **{VIEW_KEY: self.total})
            self.assertEqual(p.js(ROWS), self.total)
            self.assertIsNone(p.js(BUTTON))


class Scroll(Demo):
    OFF = {VIEW_KEY: 4, SCROLL_KEY: False}

    def test_scroll_off_keeps_the_first_n_in_view_with_nothing_to_scroll(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                self.set_local(p, **self.OFF)
                self.assertEqual(p.js(ROWS), 4)
                self.assertTrue(p.js(f"(e => e.scrollHeight <= e.clientHeight + 1)(document.querySelector('{SCROLLER}'))"), "the list does not scroll")

    def test_edit_scrolls_even_when_scroll_is_off_in_view(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                self.set_local(p, **self.OFF)
                self.edit(p)
                self.assertEqual(p.js(f"getComputedStyle(document.querySelector('{SCROLLER}')).overflowY"), "auto", "Edit scrolls")
                self.assertGreater(p.js(f"document.querySelector('{SCROLLER}').scrollHeight"), p.js(f"document.querySelector('{SCROLLER}').clientHeight"), "and has more than fits")
                self.assertEqual(p.js(ROWS), self.total, "Edit reaches every use case by scrolling")


if __name__ == "__main__":
    unittest.main()
