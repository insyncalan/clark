"""#344: the week picker beside "Week ending" on the Dashboard's report bar (follow-on 3 of the #125 design note), in a real browser.

Run: python3 dev/run_tests.py test_week_picker
The page is the test build of the served page, over a real server whose routes are the real handlers over a real store in a
temporary folder (tests/_real_server.py, fictional data), with the real Published reports reader (past_reports.py) put in. Three
publications are recorded: 1 for week ending 23-10-2026 (a Word copy, so not kept), 2 and 3 both for week ending 30-10-2026, and only
3's page kept. The picker lists 3, 2, 1 then "Dashboard as at a day…"; a kept page opens in a new tab (window.open is stood in for),
one that was not kept opens as the Dashboard as at the day it was published, behind its banner. Nothing is written. Laptop widths
only: 1400 and 900 px, light and dark. Chrome is required; these tests fail, never skip, without it.
"""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from _demo import USER
from _paths import SRC
from clark import past_reports, published_copies
from test_report_editor import Base, Pg, tearDownModule  # noqa: F401
from test_server import chrome

PAGE = SRC / "clark" / "page"
STAND_IN = ("window.__opened = []; window.open = () => { const t = { location: null, opener: 1, closed: false, "
            "close() { this.closed = true; } }; window.__opened.push(t); return t; }")


class Static(unittest.TestCase):
    def test_a_published_file_never_has_the_picker(self):
        view = (PAGE / "page-view.html").read_text(encoding="utf-8")
        for name in ("week-past", "rbar-past", "Open a published week", "Published weeks"):
            self.assertNotIn(name, view)
        self.assertIn("week-past", (PAGE / "page.html").read_text(encoding="utf-8"))

    def test_the_options_follow_the_prototype(self):
        proto = (SRC.parent / "system" / "prototype" / "past.js").read_text(encoding="utf-8")
        for words in ('<option value="">Published weeks</option>', "· Publication ${x.n}</option>", "Dashboard as at a date…"):
            self.assertIn(words, proto)
        logic = (PAGE / "src" / "logic" / "weekPicker.js").read_text(encoding="utf-8")
        for words in ('FIRST = "Published weeks"', "· Publication ${p.number}", 'AS_AT = "Dashboard as at a day…"'):
            self.assertIn(words, logic)


class WeekPicker(Base):
    def setUp(self):
        super().setUp()
        s = self.store
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        page = Path(tmp.name) / "page.html"
        page.write_bytes(b"<!doctype html><title>Publication 3</title><body><p>ZQ the kept page</p></body>")
        sha = hashlib.sha256(page.read_bytes()).hexdigest()
        s.log_publication("ABC", str(Path(tmp.name) / "one.docx"), "2026-10-23", "a" * 64, USER, word=1)
        s.log_publication("ABC", str(Path(tmp.name) / "two.html"), "2026-10-30", "b" * 64, USER)
        s.log_publication("ABC", str(page), "2026-10-30", sha, USER)
        kept = [published_copies.is_kept(Path(s.path).parent, "ABC", n) for n in (1, 2, 3)]
        self.assertEqual(kept, [False, False, True], "the store keeps the page of a real file only (#443)")
        self.s.httpd.past = past_reports.PastReports(s.path)
        self.before = self.counts()

    def counts(self):
        return [self.store.con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ("change_log", "publications")]

    def show(self, cdp, width=1400, dark=False):
        p = Pg.at(self, cdp, self.s.port, "#dashboard&p=ABC")
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        if dark:
            p.js("document.documentElement.dataset.theme = 'dark'")
        p.ready()
        p.until("!!document.querySelector('#week-past') && document.querySelector('#week-past').options.length === 5", "the picker drew")
        p.js(STAND_IN)
        return p

    def pick(self, p, value):
        p.js(f"(() => {{ const s = document.querySelector('#week-past'); s.value = {json.dumps(value)}; "
             "s.dispatchEvent(new Event('change', { bubbles: true })); })()")

    def test_it_lists_each_published_week_newest_first_both_publications_of_one_week_and_the_as_at_line(self):
        with chrome() as cdp:
            p = self.show(cdp)
            opts = p.js("JSON.stringify([...document.querySelector('#week-past').options].map(o => [o.value, o.textContent]))")
            self.assertEqual(json.loads(opts), [["", "Published weeks"],
                                                ["3", "30-10-2026 · Publication 3"],
                                                ["2", "30-10-2026 · Publication 2 · rebuilt"],
                                                ["1", "23-10-2026 · Publication 1 · rebuilt"],
                                                ["asat", "Dashboard as at a day…"]])
            self.assertEqual(p.js("document.querySelector('#week-past').getAttribute('aria-label')"), "Open a published week")
            self.assertEqual(p.js("document.querySelector('#week-past').closest('#report-bar') && "
                                  "document.querySelector('#week-past').previousElementSibling.querySelector('#week-ending') ? 'ok' : ''"), "ok", "beside the Week ending box, in View")
            p.edit()
            self.assertEqual(p.js("document.querySelector('#week-past').previousElementSibling.querySelector('#week-ending') ? 'ok' : ''"),
                             "ok", "beside the Week ending box, in Edit")
        self.assertEqual(self.counts(), self.before, "nothing was written")

    def test_a_kept_page_opens_in_a_new_tab_as_published(self):
        with chrome() as cdp:
            p = self.show(cdp)
            self.pick(p, "3")
            p.until("window.__opened.length === 1 && typeof window.__opened[0].location === 'string'", "the new tab was pointed at the page")
            self.assertTrue(p.js("window.__opened[0].location.startsWith('/past?id=')"), p.js("window.__opened[0].location"))
            self.assertEqual(p.js("document.querySelector('#week-past').value"), "", "the picker reads Published weeks again")
            self.assertFalse(p.js("!!document.querySelector('#as-at-banner')"), "this tab stays on now")
        self.assertEqual(self.counts(), self.before)

    def test_a_page_not_kept_opens_as_the_dashboard_as_at_its_day_read_only_and_back_to_now(self):
        with chrome() as cdp:
            p = self.show(cdp)
            self.pick(p, "2")
            p.until("!!document.querySelector('#as-at-banner') && document.querySelectorAll('.sec').length > 0", "the rebuilt Dashboard")
            self.assertEqual(p.js("window.__opened.length"), 0)
            self.assertIn("rebuilt from the change history", p.js("document.querySelector('#as-at-banner').textContent"))
            self.assertTrue(p.js("document.querySelector('#report').hasAttribute('inert')"))
            self.assertFalse(p.js("!!document.querySelector('#week-past')"), "no report bar while looking at the past")
            p.js("document.querySelector('#as-at-back').click()")
            p.until("!document.querySelector('#as-at-banner') && !!document.querySelector('#week-past')", "Back to now")
        self.assertEqual(self.counts(), self.before)

    def test_the_last_line_goes_to_the_as_at_box(self):
        with chrome() as cdp:
            p = self.show(cdp)
            self.pick(p, "asat")
            p.until("location.hash.startsWith('#published') && document.activeElement && document.activeElement.id === 'as-at-day'",
                    "the Published reports page, the day box")

    def test_nothing_published_has_no_picker(self):
        self.s.httpd.past.listing = lambda code: (200, {"ok": True, "project": code, "total": 0, "shown": 0, "limit": 10, "publications": []})
        with chrome() as cdp:
            p = Pg.at(self, cdp, self.s.port, "#dashboard&p=ABC")
            p.ready()
            p.until("!!document.querySelector('#report-bar')", "the report bar")
            self.assertFalse(p.js("!!document.querySelector('#week-past')"))

    def test_laptop_widths_light_and_dark(self):
        with chrome() as cdp:
            for width in (1400, 900):
                for dark in (False, True):
                    with self.subTest(width=width, dark=dark):
                        p = self.show(cdp, width, dark)
                        self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"), "no sideways scroll")
                        box = json.loads(p.js("JSON.stringify(document.querySelector('#week-past').getBoundingClientRect())"))
                        week = json.loads(p.js("JSON.stringify(document.querySelector('#report-bar .rbar-week').getBoundingClientRect())"))
                        self.assertGreaterEqual(box["height"], 24, "at least 24 px to point at")
                        self.assertLessEqual(box["right"], width)
                        self.assertLess(abs(box["top"] + box["height"] / 2 - (week["top"] + week["height"] / 2)), 12, "on the line of Week ending")
                        colours = p.js("(() => { const s = getComputedStyle(document.querySelector('#week-past')); return [s.color, s.backgroundColor]; })()")
                        self.assertNotEqual(colours[0], colours[1])
                        p.edit()
                        self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"), "no sideways scroll in Edit")
                        self.assertTrue(p.js("!!document.querySelector('#week-past')"))


if __name__ == "__main__":
    unittest.main()
