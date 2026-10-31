"""#44a Plan: the Milestones page (timeline, rail list, Calendar, Legend) and its published form.

Run: python3 dev/run_tests.py test_milestones_page
Part 1 runs the page's pure rules (src/clark/page/src/logic/milestones.js, bundled by the pinned esbuild) in headless Chrome and
checks every value against clark.milestones and clark.milestone_rows, so the page and the Python agree on state, slip, marks, axis,
buckets, chips and the Legend. Part 2 loads the committed page from the real server on the demo database (fixed CLARK_NOW) at
1400 and 900 px. Part 3 publishes a project with an internal note, a state reason and a hidden milestone and searches the file.
The browser parts are required: they fail, never skip, without Chrome.
"""
import json
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from _demo import USER, DemoStore
from _paths import SRC

from clark import milestone_rows as mr, milestones as ms, page, publish
from test_server import chrome, wait
from test_work_items import FIXED_DATE, bundled, load_demo, page_target
from test_server import Running

TODAY = "2026-10-28"
MODULE = SRC / "clark" / "page" / "src" / "logic" / "milestones.js"
EMPTY_BRANDING = tempfile.mkdtemp(prefix="clark-no-brand-")        # so a brand on this laptop never changes a test
PLANT = "PLANTED-INTERNAL-NOTE-7731"


def row(**kw):
    base = {"id": "X-M-001", "name": "A milestone", "status": "Planned", "baseline_date": None, "forecast_date": None,
            "actual_date": None, "state": None, "state_set": 0, "archived": 0, "sort_order": 0, "client_visible": 1}
    base.update(kw)
    return base


# Every shape the rules care about, against the fixed TODAY above.
CASES = [
    row(id="X-M-001", name="On time", baseline_date="2026-12-01"),
    row(id="X-M-002", name="Forecast later", baseline_date="2026-11-10", forecast_date="2026-12-20"),
    row(id="X-M-003", name="Overdue, no forecast", baseline_date="2026-10-20"),
    row(id="X-M-004", name="Overdue, forecast later", baseline_date="2026-10-20", forecast_date="2026-11-30"),
    row(id="X-M-005", name="Done late", baseline_date="2026-10-01", status="Done", actual_date="2026-10-05"),
    row(id="X-M-006", name="Done early", baseline_date="2026-10-10", status="Done", actual_date="2026-10-08"),
    row(id="X-M-007", name="Done on the day", baseline_date="2026-10-10", status="Done", actual_date="2026-10-10"),
    row(id="X-M-008", name="Done, no actual", baseline_date="2026-10-10", status="Done"),
    row(id="X-M-009", name="At risk", baseline_date="2026-11-20", state="At risk", state_set=1),
    row(id="X-M-010", name="A forecast state, dates differ", baseline_date="2026-11-01", forecast_date="2026-12-01", state="Forecast", state_set=1),
    row(id="X-M-011", name="Forecast only", forecast_date="2027-03-01", state="Forecast", state_set=1),
    row(id="X-M-012", name="Cancelled", baseline_date="2026-11-15", status="Cancelled"),
    row(id="X-M-013", name="Archived", baseline_date="2026-11-15", archived=1),
    row(id="X-M-014", name="No dates at all"),
    row(id="X-M-015", name="Same date, sort order 2", baseline_date="2026-12-01", sort_order=2),
    row(id="X-M-016", name="Not client visible", baseline_date="2026-12-31", client_visible=0),
]


class Rules(unittest.TestCase):
    """The page's rules in Chrome, compared with the Python modules."""

    @classmethod
    def setUpClass(cls):
        script = (bundled(MODULE, "MS") + ";\n(" + """(c) => {
            const rows = MS.milestoneRows(c.cases, c.today, false);
            const client = MS.milestoneRows(c.cases, c.today, true);
            const span = MS.timelineSpan(rows, c.today);
            const chips0 = MS.calendarChips(rows);
            return {
              rows, client, span,
              months: MS.monthStarts(span.start, span.end),
              buckets: Object.fromEntries(["week", "month", "quarter"].map((k) => [k, MS.buckets(k, c.from, c.to)])),
              chips: MS.calendarChips(rows),
              legend: [MS.legend(false), MS.legend(true)],
              zoom: [0.1, 0.7, 1.5, 3, 9, "x", null].map(MS.clampZoom),
              rail: [MS.railRows(rows, false).length, MS.railRows(rows, true).length, MS.railRows(rows.slice(0, 5), false).length],
              words: [MS.railWord(9, false), MS.railWord(9, true)],
              lines: MS.labelLines([0, 10, 20, 300, 305], 136),
              near: [MS.neighbour("month", "2026-12-15", 1), MS.neighbour("week", "2026-10-28", -1), MS.neighbour("quarter", "2026-10-28", -1),
                     MS.neighbour("month", "2100-12-31", 1), MS.neighbour("month", "2000-01-01", -1), MS.neighbour("week", "2100-12-31", 1)],
              inPeriod: MS.periodChips(chips0, MS.buckets("month", "2026-12-01", "2026-12-01")[0]).map((c) => c.id),
            };
        }""" + ")(" + json.dumps({"cases": CASES, "today": TODAY, "from": "2026-10-28", "to": "2027-03-02"}) + ")")
        with chrome() as cdp:
            sid = page_target(cdp)
            res = cdp.call("Runtime.evaluate", {"expression": script, "returnByValue": True}, sid)
            assert "exceptionDetails" not in res, res
            cls.js = res["result"]["value"]
        cls.py = mr.milestone_rows(CASES, TODAY)

    def test_every_row_agrees_with_the_python_rows(self):
        self.assertEqual([r["id"] for r in self.js["rows"]], [r["id"] for r in self.py], "the same rows in the same order")
        for j, p in zip(self.js["rows"], self.py):
            with self.subTest(p["id"]):
                self.assertEqual((j["state"], j["colour"], j["mark"]), (p["state"], p["colour"], p["mark"]))
                self.assertEqual((j["word"], j["baseline"], j["forecast"], j["achieved"]), (p["state"], p["baseline"], p["forecast"], p["achieved"]))
                self.assertEqual((j["slip"], j["slipText"], j["expected"]), (p["slip"], p["slip_text"], p["expected"]))
                self.assertEqual(j["achievedNote"], p["achieved_note"])
                self.assertEqual(j["marks"], p["marks"])

    def test_the_slip_is_milestones_slip_days_and_a_forecast_or_achieved_one_shows_none(self):
        by = {r["id"]: r for r in self.js["rows"]}
        for case in CASES:
            if case["archived"] or case["status"] == "Cancelled":
                continue
            r = by[case["id"]]
            if r["state"] in ("Forecast", "Achieved"):
                self.assertIsNone(r["marks"]["ghost"], case["name"])
                self.assertIsNone(r["marks"]["line"], case["name"])
            if r["marks"]["ghost"]:
                self.assertEqual(r["slip"], ms.slip_days(case, TODAY), case["name"])
                self.assertEqual(r["marks"]["line"]["days"], r["slip"])
        self.assertEqual(by["X-M-003"]["slip"], 8, "an overdue milestone with no forecast is late by the days since its date")
        self.assertEqual(by["X-M-003"]["marks"]["ghost"]["date"], TODAY)
        self.assertIsNone(by["X-M-010"]["marks"]["ghost"], "a Forecast state has no ghost, though its dates differ")
        self.assertEqual(by["X-M-002"]["slipText"], "40 days later")

    def test_the_axis_the_buckets_the_chips_and_the_legend_agree_with_python(self):
        rows = [r for r in self.py]
        start, end = mr.timeline_span(rows, TODAY)
        self.assertEqual((self.js["span"]["start"], self.js["span"]["end"]), (start, end))
        self.assertEqual(self.js["months"][0], start)
        for kind, got in self.js["buckets"].items():
            want = mr.buckets(kind, "2026-10-28", "2027-03-02")
            self.assertEqual([{k: b[k] for k in want[0]} for b in got], want, kind)
        self.assertEqual({d: [{k: v for k, v in c.items() if k != "date"} for c in cs] for d, cs in self.js["chips"].items()},
                         {d: [{**c, "word": c["state"]} for c in cs] for d, cs in mr.calendar_chips(rows).items()})
        self.assertTrue(all(c["date"] == d for d, cs in self.js["chips"].items() for c in cs), "each chip carries the day it is on (its tooltip)")
        self.assertEqual([[{k: it[k] for k in ("state", "word", "colour", "mark", "means")} for it in lg] for lg in self.js["legend"]],
                         [mr.legend(False), mr.legend(True)])

    def test_a_published_row_says_the_clients_words_and_leaves_out_cancelled(self):
        words = {r["id"]: r["word"] for r in self.js["client"]}
        self.assertEqual(words["X-M-002"], "Expected later")
        self.assertEqual(words["X-M-003"], "Late")
        self.assertEqual(words["X-M-010"], "Forecast")
        self.assertNotIn("X-M-012", words)

    def test_zoom_the_rail_and_the_label_lines(self):
        self.assertEqual(self.js["zoom"], [0.7, 0.7, 1.5, 3, 3, 1, 0.7])
        self.assertEqual(self.js["rail"], [5, len(self.py), 5])
        self.assertEqual(self.js["words"], ["Show all 9 milestones", "Show the first 5"])
        self.assertEqual(self.js["lines"], [0, 1, 2, 0, 1])

    def test_the_next_and_earlier_period_stop_where_the_page_stops_drawing(self):
        near = self.js["near"]
        self.assertEqual([n and n["key"] for n in near], ["2027-01", "2026-10-19", "2026-Q3", None, None, None])

    def test_the_period_list_holds_the_chips_of_that_period_by_date(self):
        self.assertEqual(self.js["inPeriod"], ["X-M-001", "X-M-015", "X-M-002", "X-M-016"])

    def test_the_rules_never_read_the_clock_or_the_page(self):
        text = MODULE.read_text(encoding="utf-8")
        for bad in ("new Date()", "Date.now", "document.", "window.", "fetch("):
            self.assertNotIn(bad, text)


class RealBrowser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store, cls.folder, _ = load_demo()
        cls.projects = cls.store.read("projects")

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        shutil.rmtree(str(cls.folder), ignore_errors=True)

    def serve(self):
        s = Running(data_for=self.store.data_for, projects=lambda: self.projects, page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(s.close)
        return s.port

    def visit(self, cdp, width, hash_, port=None, ready='.mv-wrap'):
        port = port or self.serve()
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Page.navigate", {"url": "about:blank"}, sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{port}/{hash_}"}, sid)
        self.assertTrue(wait(lambda: cdp.js(f"!!document.querySelector('{ready}')", sid)), "the block drew")
        return sid

    def expected(self, code):
        rows = mr.milestone_rows(self.store.data_for(code)["milestones"], TODAY)
        return rows

    def test_the_timeline_holds_every_milestone_with_a_ghost_and_its_days_for_a_slipped_one(self):
        for code in ("TUL", "MOSS"):
            for width in (1400, 900):
                with self.subTest(code=code, width=width), chrome() as cdp:
                    sid = self.visit(cdp, width, f"#milestones&p={code}")
                    want = [r for r in self.expected(code) if r["marks"]["solid"]]
                    got = cdp.js("[...document.querySelectorAll('.mv-mk')].map(b => [b.dataset.ms, b.dataset.markAt])", sid)
                    self.assertEqual(sorted(got), sorted([r["id"], r["marks"]["solid"]["date"]] for r in want),
                                     "a mark for every milestone with a date, on its agreed date")
                    slipped = [r for r in want if r["marks"]["ghost"]]
                    self.assertTrue(slipped, "the demo has a slipped milestone")
                    ghosts = cdp.js("[...document.querySelectorAll('.mv-ghost')].map(g => g.dataset.ghost)", sid)
                    self.assertEqual(sorted(ghosts), sorted(r["id"] for r in slipped))
                    self.assertEqual(cdp.js("document.querySelectorAll('.mv-conn').length", sid), len(slipped), "a dashed line each")
                    text = {i: cdp.js(f"document.querySelector('[data-slip=\"{i}\"]').textContent", sid) for i in (r["id"] for r in slipped)}
                    self.assertEqual(text, {r["id"]: r["slip_text"] for r in slipped}, "N days later, the Python's slip_days")
                    self.assertEqual(cdp.js("document.querySelectorAll('[data-today]').length", sid), 1)
                    self.assertEqual(cdp.js("document.documentElement.scrollWidth <= window.innerWidth", sid), True, "no page-wide scroll")
                    self.assertEqual(cdp.js("(() => { const w = document.querySelector('.mv-wrap'); return w.scrollWidth >= w.clientWidth"
                                            " && getComputedStyle(w).overflowX === 'auto' && w.getBoundingClientRect().right <= window.innerWidth; })()", sid),
                                     True, "the line scrolls inside its box, which stays on the screen")
                    self.assertNotRegex(cdp.js("document.querySelector('#milestones').innerText", sid), r"\d{4}-\d{2}-\d{2}")

    def test_zoom_by_dragging_the_edge_is_remembered_and_reset_puts_it_back(self):
        with chrome() as cdp:
            sid = self.visit(cdp, 1400, "#milestones&p=TUL")
            self.assertEqual(cdp.js("document.querySelector('.mv-wrap').dataset.zoomPct", sid), "100")
            self.assertIsNone(cdp.js("document.querySelector('[data-zreset]')", sid))
            h = cdp.js("document.querySelector('.mv-wrap').offsetHeight", sid)
            cdp.js(f"document.querySelector('.mv-wrap').style.height = '{h * 2}px'", sid)       # what dragging the edge does
            self.assertTrue(wait(lambda: cdp.js("document.querySelector('.mv-wrap').dataset.zoomPct", sid) != "100"), "the line zoomed")
            pct = int(cdp.js("document.querySelector('.mv-wrap').dataset.zoomPct", sid))
            self.assertTrue(70 <= pct <= 300 and pct > 100, pct)
            self.assertEqual(json.loads(cdp.js("localStorage.getItem('clark.tlZoom.page')", sid)), pct / 100, "remembered for this place")
            cdp.js("document.querySelector('[data-zreset]').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelector('.mv-wrap').dataset.zoomPct", sid) == "100"))
            self.assertIsNone(cdp.js("document.querySelector('[data-zreset]')", sid))

    def test_the_rail_list_shows_five_then_all_and_remembers(self):
        port = self.serve()
        with chrome() as cdp:
            sid = self.visit(cdp, 1400, "#milestones&p=MOSS", port)
            self.assertEqual(len(self.expected("MOSS")), 7)
            self.assertEqual(cdp.js("document.querySelectorAll('.msl-row').length", sid), 5)
            self.assertEqual(cdp.js("document.querySelector('.msl-all').textContent", sid), "Show all 7 milestones")
            cdp.js("document.querySelector('.msl-all').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('.msl-row').length", sid) == 7))
            self.assertEqual(cdp.js("document.querySelector('.msl-all').textContent", sid), "Show the first 5")
            sid = self.visit(cdp, 1400, "#milestones&p=MOSS", port)
            self.assertEqual(cdp.js("document.querySelectorAll('.msl-row').length", sid), 7, "remembered")
            cdp.js("document.querySelector('.msl-all').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('.msl-row').length", sid) == 5), "Show the first 5 goes back")

    def test_the_legend_lists_the_six_states_expected_and_today_and_stays_on_screen(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.visit(cdp, width, "#milestones&p=TUL")
                self.assertEqual(cdp.js("[...document.querySelectorAll('[data-legend]')].map(e => e.dataset.legend)", sid),
                                 ["Achieved", "On track", "At risk", "Slipped", "Overdue", "Forecast", "Expected", "Today"])
                self.assertEqual(cdp.js("getComputedStyle(document.querySelector('.mlg-p')).visibility", sid), "hidden", "closed until hover or focus")
                cdp.js("document.querySelector('.mlg-b').focus()", sid)
                self.assertTrue(wait(lambda: cdp.js("getComputedStyle(document.querySelector('.mlg-p')).visibility", sid) == "visible"), "opens on focus")
                self.assertTrue(cdp.js("(() => { const r = document.querySelector('.mlg-p').getBoundingClientRect();"
                                       " return r.left >= 0 && r.right <= window.innerWidth && r.top >= 0; })()", sid), "the card stays on screen")
                self.assertIn("Slipped", cdp.js("document.querySelector('.mlg-p').textContent", sid), "the editor says Slipped")

    def test_the_switcher_opens_the_calendar_on_month_with_week_and_quarter_and_remembers(self):
        port = self.serve()
        rows = self.expected("MOSS")
        with chrome() as cdp:
            sid = self.visit(cdp, 1400, "#milestones&p=MOSS", port)
            self.assertEqual(cdp.js("document.querySelectorAll('.cal').length", sid), 0)
            cdp.js("document.querySelector('[data-msvb=cal]').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.cal')", sid)))
            self.assertEqual(cdp.js("document.querySelector('.cal').dataset.scale", sid), "month", "opens on Month")
            self.assertEqual(cdp.js("document.querySelector('.cal-t').textContent", sid), "October 2026")
            self.assertEqual(cdp.js("document.querySelector('.cal-d.today').dataset.d", sid), TODAY)
            self.assertEqual(cdp.js("document.documentElement.scrollWidth <= window.innerWidth", sid), True)
            self.assertEqual(cdp.js("document.querySelectorAll('.mv-wrap').length", sid), 0, "the timeline is out of the way")
            solid_oct = sorted(r["id"] for r in rows if r["marks"]["solid"] and r["marks"]["solid"]["date"][:7] == "2026-10")
            got = cdp.js("[...document.querySelectorAll('.cal-ms')].filter(c => c.dataset.ghost === '0').map(c => c.dataset.ms)", sid)
            self.assertEqual(sorted(got), solid_oct, "the chips of October")
            for scale, label in (("quarter", "Q4 2026"), ("week", "Week of 26-10-2026"), ("month", "October 2026")):
                cdp.js(f"document.querySelector('[data-scale-b={scale}]').click()", sid)
                self.assertTrue(wait(lambda: cdp.js("document.querySelector('.cal').dataset.scale", sid) == scale))
                self.assertEqual(cdp.js("document.querySelector('.cal-t').textContent", sid), label)
            cdp.js("document.querySelector('[data-cal=\"1\"]').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelector('.cal-t').textContent", sid) == "November 2026"))
            cdp.js("document.querySelector('[data-cal=\"0\"]').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelector('.cal-t').textContent", sid) == "October 2026"))
            sid = self.visit(cdp, 1400, "#milestones&p=MOSS", port, ready=".cal")
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.cal')", sid)), "the editor remembers Calendar")
            cdp.js("document.querySelector('[data-msvb=line]').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.mv-wrap')", sid)))

    def open_calendar(self, cdp, port, hash_="#milestones&p=MOSS"):
        sid = self.visit(cdp, 1400, hash_, port)
        cdp.js("document.querySelector('[data-msvb=cal]').click()", sid)
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.cal')", sid)))
        return sid

    def key(self, cdp, sid, name):
        cdp.js(f"document.querySelector('.cal').dispatchEvent(new KeyboardEvent('keydown', {{key: '{name}', bubbles: true, cancelable: true}}))", sid)
        time.sleep(0.02)                                  # a person's key presses are never in the same instant

    def title(self, cdp, sid):
        return cdp.js("document.querySelector('.cal-t').textContent", sid)

    def test_the_scale_is_remembered_for_the_place_and_not_for_another(self):
        port = self.serve()
        with chrome() as cdp:
            sid = self.open_calendar(cdp, port)
            cdp.js("document.querySelector('[data-scale-b=quarter]').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelector('.cal').dataset.scale", sid) == "quarter"))
            sid = self.visit(cdp, 1400, "#milestones&p=MOSS", port, ready=".cal")
            self.assertEqual(cdp.js("document.querySelector('.cal').dataset.scale", sid), "quarter", "restored on the next visit")
            self.assertEqual(cdp.js("Object.keys(window.localStorage).filter(k => k.startsWith('clark.msv.calv.'))", sid), ["clark.msv.calv.page"], "kept under this place only")
            cdp.js("window.localStorage.setItem('clark.msv.calv.page', JSON.stringify('decade'))", sid)
            sid = self.visit(cdp, 1400, "#milestones&p=MOSS", port, ready=".cal")
            self.assertEqual(cdp.js("document.querySelector('.cal').dataset.scale", sid), "month", "an unknown value opens on Month")

    def test_the_focusable_calendar_has_a_role_a_short_name_a_hidden_hint_and_announces_a_move(self):
        port = self.serve()
        with chrome() as cdp:
            sid = self.open_calendar(cdp, port)
            self.assertEqual(cdp.js("document.querySelector('.cal').getAttribute('role')", sid), "group", "a name needs a role")
            self.assertEqual(cdp.js("document.querySelector('.cal').getAttribute('aria-label')", sid), "Milestone calendar", "short name")
            self.assertIsNone(cdp.js("document.querySelector('.cal').getAttribute('title')", sid), "the hint is not repeated in a tooltip")
            hint = cdp.js("(() => { const c = document.querySelector('.cal'); const h = document.getElementById(c.getAttribute('aria-describedby')); "
                          "return h ? [h.textContent, h.className] : null; })()", sid)
            self.assertIsNotNone(hint, "the hint is described by an element")
            self.assertIn("Page Down", hint[0])
            self.assertIn("sr-only", hint[1])
            self.assertEqual(cdp.js("document.querySelector('[data-cal-say]').textContent", sid), "", "nothing announced on load")
            self.assertEqual(cdp.js("document.querySelector('[data-cal-say]').getAttribute('aria-live')", sid), "polite")
            cdp.js("document.querySelector('[data-cal=\"1\"]').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelector('[data-cal-say]').textContent", sid) == "Showing November 2026"))

    def test_the_calendar_has_no_hard_coded_fallback_year(self):
        src = (Path(__file__).resolve().parent.parent / "src" / "clark" / "page" / "src" / "components" / "MsCalendar.jsx").read_text(encoding="utf-8")
        self.assertNotIn("2026-01-01", src, "the fallback comes from the data or today")

    def test_each_chip_shows_its_status_word_and_the_period_lists_its_milestones(self):
        port = self.serve()
        rows = {r["id"]: r for r in self.expected("MOSS")}
        with chrome() as cdp:
            sid = self.open_calendar(cdp, port)
            words = cdp.js("[...document.querySelectorAll('.cal-ms')].filter(c => c.dataset.ghost === '0').map(c => [c.dataset.ms, c.querySelector('.cal-w').textContent, getComputedStyle(c.querySelector('.cal-w')).display])", sid)
            self.assertTrue(words)
            for mid, word, display in words:
                self.assertEqual(word, rows[mid]["state"], "the status word is on screen")
                self.assertNotEqual(display, "none")
            self.assertEqual(cdp.js("document.querySelector('.cal-list h4').textContent", sid), "Milestones in this period")
            listed = cdp.js("[...document.querySelectorAll('.cal-list li')].map(l => [l.dataset.cl, l.dataset.ghost])", sid)
            chips = cdp.js("[...document.querySelectorAll('.cal-d:not(.out) .cal-ms')].map(c => [c.dataset.ms, c.dataset.ghost])", sid)
            self.assertEqual(sorted(listed), sorted(chips), "the list is the period's chips")
            self.assertGreater(len(listed), 0)

    def test_an_empty_period_says_so_with_a_next_step_and_today_brings_it_back(self):
        port = self.serve()
        with chrome() as cdp:
            sid = self.open_calendar(cdp, port)
            for _ in range(40):
                self.key(cdp, sid, "PageDown")
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-cal-empty]')", sid)), "an empty period")
            text = cdp.js("document.querySelector('[data-cal-empty]').textContent", sid)
            self.assertTrue(text.startswith("No milestones in this period."))
            self.assertIn("go to today", text)
            self.assertEqual(cdp.js("document.querySelectorAll('.cal-list li').length", sid), 0)
            cdp.js("document.querySelector('[data-cal-empty] button').click()", sid)
            self.assertTrue(wait(lambda: self.title(cdp, sid) == "October 2026"))

    def test_the_keys_move_the_period_and_the_range_message_offers_go_to_today(self):
        port = self.serve()
        with chrome() as cdp:
            sid = self.open_calendar(cdp, port)
            for name, want in (("ArrowRight", "November 2026"), ("PageDown", "December 2026"), ("ArrowLeft", "November 2026"), ("PageUp", "October 2026")):
                self.key(cdp, sid, name)
                self.assertTrue(wait(lambda: self.title(cdp, sid) == want), f"{name} gives {want}")
            cdp.js("document.querySelector('[data-scale-b=week]').click()", sid)
            self.assertTrue(wait(lambda: self.title(cdp, sid) == "Week of 26-10-2026"))
            self.key(cdp, sid, "PageDown")
            self.assertTrue(wait(lambda: self.title(cdp, sid) == "Week of 02-11-2026"))
            self.assertEqual(cdp.js("document.querySelectorAll('[data-cal-far]').length", sid), 0)
            cdp.js("document.querySelector('[data-scale-b=quarter]').click()", sid)
            self.assertTrue(wait(lambda: self.title(cdp, sid) == "Q4 2026"))
            for _ in range(300):
                self.key(cdp, sid, "PageDown")
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-cal-far]')", sid)), "the range message")
            self.assertIn("Go back to today", cdp.js("document.querySelector('[data-cal-far]').textContent", sid))
            far_title = self.title(cdp, sid)
            self.assertTrue(far_title.endswith("2100"), far_title)
            cdp.js("document.querySelector('[data-cal-home]').click()", sid)
            self.assertTrue(wait(lambda: self.title(cdp, sid) == "Q4 2026"))
            self.assertEqual(cdp.js("document.querySelectorAll('[data-cal-far]').length", sid), 0)

    def test_a_slipped_milestone_also_shows_on_its_expected_day_in_the_calendar(self):
        slipped = [r for r in self.expected("MOSS") if r["marks"]["ghost"]]
        self.assertTrue(slipped)
        with chrome() as cdp:
            sid = self.visit(cdp, 1400, "#milestones&p=MOSS")
            cdp.js("document.querySelector('[data-msvb=cal]').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.cal')", sid)))
            for r in slipped:
                day = r["marks"]["ghost"]["date"]
                cdp.js("document.querySelector('[data-cal=\"0\"]').click()", sid)
                for _ in range(10):
                    if cdp.js(f"!!document.querySelector('[data-d=\"{day}\"]')", sid):
                        break
                    cdp.js("document.querySelector('[data-cal=\"1\"]').click()", sid)
                    time.sleep(0.2)
                got = cdp.js(f"[...document.querySelectorAll('[data-d=\"{day}\"] .cal-ms.ghost')].map(c => c.dataset.ms)", sid)
                self.assertIn(r["id"], got, f"{r['id']} on its expected day")


def publish_with_plants():
    """A project with an internal note, a flagged-out milestone, one the editor hid and a slipped one, published; (demo, folder, path, ids)."""
    demo = DemoStore()
    st = demo.store
    with st.step("dashboard", USER) as step:
        a = step.create("milestones", {"project": "ABC", "name": "Visible slipped", "baseline_date": "2026-10-10", "forecast_date": "2026-12-01",
                                       "client_visible": 1, "internal_note": PLANT + " one", "source": "demo"})
        b = step.create("milestones", {"project": "ABC", "name": "Hidden from clients", "baseline_date": "2026-11-10",
                                       "client_visible": 0, "internal_note": PLANT + " two", "source": "demo"})
        c = step.create("milestones", {"project": "ABC", "name": "Forecast one", "forecast_date": "2027-02-01", "state": "Forecast",
                                       "state_set": 1, "client_visible": 1, "movement": "hold", "source": "demo"})
    with st.step("dashboard", USER) as step:
        step.update("milestones", demo.milestone, {"client_visible": 1})
    with st.step("dashboard", USER) as step:
        d = step.create("milestones", {"project": "ABC", "name": "Left out by the editor", "baseline_date": "2026-11-20",
                                       "client_visible": 1, "source": "demo"})
        step.create("report_hidden", {"project": "ABC", "item_id": d})
    folder = tempfile.mkdtemp(prefix="clark-pub-")
    done = publish.publish(st, "ABC", folder, by_user=USER, now=TODAY, branding=EMPTY_BRANDING)
    return demo, folder, Path(done["path"]), (a, b, c, d)


class Published(unittest.TestCase):
    def test_the_file_draws_the_plan_in_client_words_and_holds_nothing_internal(self):
        demo, folder, path, (a, b, c, d) = publish_with_plants()
        self.addCleanup(demo.close)
        self.addCleanup(shutil.rmtree, folder, True)
        text = path.read_text(encoding="utf-8")
        for never in (PLANT, "internal_note", "Hidden from clients", "Left out by the editor", "Movement", "/api/change"):
            self.assertNotIn(never, text, never)
        with chrome() as cdp:
            sid = page_target(cdp)
            cdp.call("Page.navigate", {"url": path.as_uri()}, sid)
            self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.ready === '1'", sid)))
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.tab')", sid)))
            cdp.js("[...document.querySelectorAll('.tab')].find(t => /Milestones/.test(t.textContent)).click()", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.mv-wrap')", sid)), "the Milestones tab drew a timeline")
            marks = cdp.js("[...document.querySelectorAll('.mv-mk')].map(b => b.dataset.ms)", sid)
            self.assertEqual(sorted(marks), sorted([a, c, demo.milestone]), "the client-flagged milestones only")
            self.assertEqual(cdp.js("document.querySelectorAll('.mv-ghost').length", sid), 1)
            self.assertEqual(cdp.js("document.querySelector('[data-slip]').textContent", sid), "52 days later")
            legend = cdp.js("document.querySelector('.mlg-p').textContent", sid)
            for word in ("Expected later", "Late", "Forecast"):
                self.assertIn(word, legend)
            self.assertNotIn("Slipped", legend)
            self.assertNotIn("Overdue", legend)
            self.assertEqual(cdp.js("document.querySelectorAll('.msl-row .tag').length", sid), 0, "no Internal only tag")
            self.assertEqual(cdp.js("document.querySelector('.msv').dataset.view", sid), "line", "starts on Timeline")
            self.assertIn("Milestone timeline;", cdp.js("document.querySelector('.mv-wrap').getAttribute('aria-label')", sid))
            self.assertEqual(cdp.js("document.querySelectorAll('input, textarea, select, [contenteditable]').length", sid), 0)
            self.assertGreater(cdp.js("document.querySelectorAll('.mv-mk, .mv-lab, .msl-row').length", sid), 0)
            self.assertEqual(cdp.js("[...document.querySelectorAll('.mv-mk, .mv-lab, .msl-row')].filter(e => e.tagName === 'BUTTON' || e.getAttribute('role') === 'button' || e.tabIndex >= 0 || getComputedStyle(e).cursor === 'pointer').length", sid), 0,
                             "marks, labels and rail rows are plain text in a file: no button, no pointer")
            before = cdp.js("location.href", sid)
            cdp.js("document.querySelector('.mv-mk').click()", sid)
            time.sleep(0.3)
            self.assertEqual(cdp.js("location.href", sid), before, "a click in a file opens nothing")
            cdp.js("document.querySelector('[data-msvb=cal]').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.cal')", sid)), "the Calendar switch works in the file")
            self.assertRegex(cdp.js("document.querySelector('.cal-d[aria-label]').getAttribute('aria-label')", sid), r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday) \d")
            self.assertGreater(cdp.js("document.querySelectorAll('.cal-ms').length", sid), 0)
            self.assertRegex(cdp.js("document.querySelector('.cal-ms').title", sid), r"\d{2}-\d{2}-\d{4}", "a chip's tooltip carries its date")
            self.assertEqual(cdp.js("[...document.querySelectorAll('.cal-ms')].filter(e => e.tagName === 'BUTTON' || getComputedStyle(e).cursor === 'pointer').length", sid), 0,
                             "calendar chips are plain text in a file")

FAR = ["0001-01-01", "0026-10-01", "0099-12-31", "1999-12-31", "2101-01-01", "2126-03-01", "9999-12-31", "10000-01-01", "2026-02-30", "soon"]


class FarDates(unittest.TestCase):
    """A mistyped or far-off year never stretches the axis: it is left off and named in a plain note (page and Python agree)."""

    @classmethod
    def setUpClass(cls):
        cls.cases = [row(id="X-M-%03d" % (i + 1), name=f"Far {i}", baseline_date=d) for i, d in enumerate(FAR)]
        cls.cases.append(row(id="X-M-099", name="Near", baseline_date="2026-12-01"))
        script = (bundled(MODULE, "MS") + ";\n(" + """(c) => {
            const rows = MS.milestoneRows(c.cases, c.today, false);
            const span = MS.timelineSpan(rows, c.today);
            const edge = ["2000-01-01", "2100-12-31", "1999-12-31", "2101-01-01"].map(MS.inRange);
            const wide = MS.monthStarts("2000-01-01", "2100-12-01");
            return {rows: rows.map((r) => r.id), far: MS.farRows(rows).map((r) => r.id), span, months: MS.monthStarts(span.start, span.end).length,
                    dates: MS.markDates(rows), edge, wide: wide.length, wideFirst: wide[0], note: MS.FAR_NOTE,
                    buckets: MS.buckets("month", c.today, "2027-01-01").length};
        }""" + ")(" + json.dumps({"cases": cls.cases, "today": TODAY}) + ")")
        with chrome() as cdp:
            sid = page_target(cdp)
            res = cdp.call("Runtime.evaluate", {"expression": script, "returnByValue": True}, sid)
            assert "exceptionDetails" not in res, res
            cls.js = res["result"]["value"]
        cls.py = mr.milestone_rows([c for c in cls.cases if c["baseline_date"] not in ("10000-01-01", "2026-02-30", "soon")], TODAY)   # the store only lets 4-digit years through

    def test_far_and_mistyped_dates_are_not_drawn_on_the_axis(self):
        near = "X-M-099"
        self.assertEqual(sorted(set(self.js["dates"])), [TODAY, "2026-12-01"], "only real dates in range are drawn (an overdue one is shown from today)")
        self.assertEqual(self.js["span"], {"start": "2026-10-01", "end": "2027-01-01"}, "the axis is today to the near mark, not thousands of months")
        self.assertEqual(self.js["months"], 3)
        self.assertNotIn(near, self.js["far"])
        self.assertEqual(len(self.js["far"]), len(FAR), "every far, mistyped or unreal date is named in the note, none is drawn")
        self.assertEqual(self.js["edge"], [True, True, False, False], "2000 to 2100 is the range")
        self.assertEqual(self.js["note"], "Left off the timeline because the date looks wrong")

    def test_the_axis_never_has_more_than_200_names(self):
        self.assertLessEqual(self.js["wide"], 200, "a hundred years is thinned to at most 200 names")
        self.assertGreater(self.js["wide"], 100)
        self.assertEqual(self.js["wideFirst"], "2000-01-01")

    def test_python_agrees(self):
        self.assertEqual(sorted(set(mr.mark_dates(self.py))), [TODAY, "2026-12-01"])
        self.assertEqual(mr.timeline_span(self.py, TODAY), ("2026-10-01", "2027-01-01"))
        self.assertEqual([r["id"] for r in mr.far_rows(self.py)], [i for i in self.js["far"] if i in {r["id"] for r in self.py}])
        self.assertEqual([mr.in_range(d) for d in ("2000-01-01", "2100-12-31", "1999-12-31", "2101-01-01", "0001-01-01", "10000-01-01", "x", None)],
                         [True, True, False, False, False, False, False, False])


# #130 point 6: every label's box is measured; no two overlap and the Today label stays clear of every label, mark and month name.
CROWDED = [("Design sign-off for the whole regional programme", "2026-10-26", "2026-11-09"), ("Vendor contract signed", "2026-10-27", None),
           ("Data migration rehearsal one", "2026-10-28", "2026-11-20"), ("Go-live readiness review", "2026-10-29", None),
           ("Training for every team lead complete", "2026-10-30", "2026-12-04"), ("Security test passed", "2026-11-02", None),
           ("Pilot users onboarded", "2026-11-03", "2026-11-17"), ("Cutover plan approved by the board", "2026-11-04", None),
           ("Hypercare starts", "2026-11-05", None), ("Old system switched off", "2026-11-06", "2026-11-08")]
BOXES = """(() => {
  const EPS = 1;                                        // one pixel of tolerance for sub-pixel differences between fonts and systems
  const box = (e) => { const r = e.getBoundingClientRect(); return {l: r.left, r: r.right, t: r.top, b: r.bottom, n: e.dataset.lab || e.className}; };
  const hit = (a, b) => a.l < b.r - EPS && b.l < a.r - EPS && a.t < b.b - EPS && b.t < a.b - EPS;
  const labs = [...document.querySelectorAll('.mv-lab')].map(box);
  const today = box(document.querySelector('.mv-today b'));
  const text = (e) => { const g = document.createRange(); g.selectNodeContents(e); const r = g.getBoundingClientRect(); return {l: r.left, r: r.right, t: r.top, b: r.bottom, n: 'month ' + e.textContent}; };
  const others = [...document.querySelectorAll('.mv-mk')].map(box).concat([...document.querySelectorAll('.mv-month')].map(text));
  const pairs = [];
  for (let i = 0; i < labs.length; i++) for (let j = i + 1; j < labs.length; j++) if (hit(labs[i], labs[j])) pairs.push([labs[i].n, labs[j].n]);
  const lanes = {};
  for (const e of document.querySelectorAll('.mv-lab')) (lanes[e.style.top] = lanes[e.style.top] || []).push(box(e));
  const laneClash = Object.values(lanes).flatMap((l) => l.flatMap((a, i) => l.slice(i + 1).filter((b) => a.l < b.r - EPS && b.l < a.r - EPS).map((b) => [a.n, b.n])));
  const wrap = document.querySelector('.mv-wrap'), strip = document.querySelector('.mv-strip').getBoundingClientRect();
  const lowest = Math.max(...labs.map((l) => l.b));
  return {count: labs.length, pairs, laneClash, lowest: lowest - strip.top, stripHeight: strip.height, fits: wrap.scrollHeight <= wrap.clientHeight + EPS, bar: wrap.offsetHeight - wrap.clientHeight - 2,
           todayHits: labs.concat(others).filter((o) => hit(today, o)).map((o) => o.n),
          inside: labs.every((l) => l.l >= document.querySelector('.mv-strip').getBoundingClientRect().left - 1)};
})()"""


def add_crowded(store, project):
    with store.step("dashboard", USER) as step:
        for name, base, fc in CROWDED:
            step.create("milestones", {"project": project, "name": name, "baseline_date": base, "forecast_date": fc,
                                       "client_visible": 1, "source": "demo"})


class Crowded(unittest.TestCase):
    """A project with ten milestones within two weeks of each other, in the app and in the published file."""

    @classmethod
    def setUpClass(cls):
        cls.store, cls.folder, _ = load_demo()
        add_crowded(cls.store, "TUL")
        cls.projects = cls.store.read("projects")

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        shutil.rmtree(str(cls.folder), ignore_errors=True)

    # Other fonts, so the layout is shown not to depend on one system's metrics: a wide one, a narrow one, and a classic
    # (space-taking) sideways scrollbar as Linux draws it. Each is a style put in before the page's own script runs.
    FONTS = {
        "default": "",
        "wide": ".mv-lab, .mv-month, .mv-today { font-family: 'Courier New', 'DejaVu Sans Mono', monospace !important; letter-spacing: 0.08em !important; }",
        "narrow": ".mv-lab, .mv-month, .mv-today { font-family: 'Arial Narrow', 'DejaVu Sans Condensed', sans-serif !important; letter-spacing: -0.06em !important; }",
        "scrollbar": ".mv-wrap::-webkit-scrollbar { height: 15px; background: #ddd; } .mv-wrap::-webkit-scrollbar-thumb { background: #999; }",
    }
    VARIANTS = [("default", 1400), ("default", 900), ("default", 390), ("wide", 1400), ("wide", 900), ("narrow", 1400), ("narrow", 390), ("scrollbar", 1400), ("scrollbar", 390)]

    def style_for(self, font):
        css = self.FONTS[font]       # a constructed style sheet: the page's content-security rule would drop an inline <style>
        return "" if not css else "(() => { const sheet = new CSSStyleSheet(); sheet.replaceSync(%s); document.adoptedStyleSheets = [...document.adoptedStyleSheets, sheet]; })();" % json.dumps(css)

    def check(self, cdp, sid, where):
        self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('.mv-lab').length", sid) >= len(CROWDED)), where)
        time.sleep(0.4)                       # the labels are measured, then laid out again
        got = cdp.js(BOXES, sid)
        self.assertGreaterEqual(got["count"], len(CROWDED) + 4, where)
        if "scrollbar font" in where:
            self.assertGreaterEqual(got["bar"], 10, f"{where}: this variant really draws a scrollbar that takes room inside the box")
        self.assertEqual(got["pairs"], [], f"{where}: no two labels overlap")
        self.assertEqual(got["laneClash"], [], f"{where}: no two labels in one lane overlap")
        self.assertTrue(got["fits"], f"{where}: the box is tall enough for the lanes actually used (lowest label {got['lowest']}, strip {got['stripHeight']})")
        self.assertEqual(got["todayHits"], [], f"{where}: the Today label is clear of every label, mark and month name")
        self.assertTrue(got["inside"], where)

    def test_in_the_app_at_1400_900_and_390_px(self):
        s = Running(data_for=self.store.data_for, projects=lambda: self.projects, page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(s.close)
        for font, width in self.VARIANTS:
            with self.subTest(font=font, width=width), chrome() as cdp:
                sid = page_target(cdp)
                cdp.call("Page.enable", {}, sid)
                cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE + ";" + self.style_for(font)}, sid)
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": width < 600}, sid)
                cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{s.port}/#milestones&p=TUL"}, sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.mv-wrap')", sid)))
                self.check(cdp, sid, f"app {font} font {width}px")

    def test_many_lanes_in_a_wider_font_still_fit_the_box(self):
        """A wider font than this machine's (forced here) needs more lanes than the 900 px box limit: the box grows to the measured lanes."""
        extra = [(f"Extra milestone number {n} with a long name", f"2026-11-{10 + n % 3:02d}", f"2026-11-{20 + n % 5:02d}") for n in range(12)]
        store, folder, _ = load_demo()               # its own store: the shared one keeps ten milestones for the other tests
        self.addCleanup(shutil.rmtree, str(folder), True)
        self.addCleanup(store.close)
        add_crowded(store, "TUL")
        with store.step("dashboard", USER) as step:
            for name, base, fc in extra:
                step.create("milestones", {"project": "TUL", "name": name, "baseline_date": base, "forecast_date": fc, "client_visible": 1, "source": "demo"})
        s = Running(data_for=store.data_for, projects=lambda: store.read("projects"), page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(s.close)
        self.FONTS["wider"] = ".mv-lab, .mv-month, .mv-today { font-family: 'Courier New', 'DejaVu Sans Mono', monospace !important; letter-spacing: 0.2em !important; }"
        self.addCleanup(self.FONTS.pop, "wider", None)
        with chrome() as cdp:
            sid = page_target(cdp)
            cdp.call("Page.enable", {}, sid)
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE + ";" + self.style_for("wider")}, sid)
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": 1400, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
            cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{s.port}/#milestones&p=TUL"}, sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('.mv-lab').length", sid) >= len(CROWDED) + len(extra)))
            time.sleep(0.4)
            got = cdp.js(BOXES, sid)
            self.assertGreater(got["lowest"], 880, "this check really needs more lanes than the old 900 px limit allowed")
            self.assertTrue(got["fits"], f"the box is tall enough for the lanes actually used (lowest label {got['lowest']}, strip {got['stripHeight']})")
            self.assertEqual(got["laneClash"], [])

    def test_in_the_published_file_at_1400_900_and_390_px(self):
        demo = DemoStore()
        add_crowded(demo.store, "ABC")
        folder = tempfile.mkdtemp(prefix="clark-pub-")
        self.addCleanup(demo.close)
        self.addCleanup(shutil.rmtree, folder, True)
        path = Path(publish.publish(demo.store, "ABC", folder, by_user=USER, now=TODAY, branding=EMPTY_BRANDING)["path"])
        for font, width in self.VARIANTS:
            with self.subTest(font=font, width=width), chrome() as cdp:
                sid = page_target(cdp)
                cdp.call("Page.enable", {}, sid)
                cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE + ";" + self.style_for(font)}, sid)
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": width < 600}, sid)
                cdp.call("Page.navigate", {"url": path.as_uri()}, sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.tab')", sid)))
                cdp.js("[...document.querySelectorAll('.tab')].find(t => /Milestones/.test(t.textContent)).click()", sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.mv-wrap')", sid)))
                self.check(cdp, sid, f"published {font} font {width}px")

    def test_label_lines_use_each_labels_own_width(self):
        text = MODULE.read_text(encoding="utf-8")
        self.assertIn("labelLines(xs, width, gap = 0)", text)


if __name__ == "__main__":
    unittest.main()
