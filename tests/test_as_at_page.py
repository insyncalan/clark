"""#349 page side: Settings › Published reports › Dashboard as at a day, and the rebuilt Dashboard behind its banner, in a real browser.

Run: python3 dev/run_tests.py test_as_at_page
The page is the test build of the served page, over a real server whose routes are the real handlers over a real store in a
temporary folder (tests/_real_server.py, fictional data). The history is fixed: after the demo store is made, its log is moved
to 10-01-2020, and one later step (an action reworded, the health set to At risk, a risk added) is moved to 10-02-2020, so "as at
20-01-2020" is before it whatever the clock says. Laptop widths only: 1400 and 900 px, light and dark. Chrome is required; these
tests fail, never skip, without it.
"""
import json
import unittest

from _demo import USER
from test_report_editor import Base, Pg, tearDownModule  # noqa: F401
from test_server import chrome

OLD, NEW = "ZQ old words of the action", "ZQ new words of the action"
BANNER = "You are looking at the dashboard as at 20-01-2020, rebuilt from the change history. Back to now"
EDITING = ("input, textarea, select, [contenteditable=true], .grip, [data-mode=edit], #report-bar, .pubbtn, [data-undo]")


class AsAtPage(Base):
    def setUp(self):
        super().setUp()
        s = self.store
        self.a = self.demo.action(description=OLD, due_date="2020-01-25", owner="Pat Demo")
        self.move("2020-01-10 10:00:00")
        with s.step("dashboard", USER) as st:
            st.update("actions", self.a, {"description": NEW})
            st.update("projects", "ABC", {"health": "At risk", "health_reason": "ZQ a reason given later"})
            self.r = st.create("raid", {"project": "ABC", "type": "Risk", "description": "ZQ a risk raised later", "raised": "2020-02-10",
                                        "source": "demo", "impact": "High", "likelihood": "High", "owner": "Pat Demo"})
        self.move("2020-02-10 10:00:00", only_after="2020-01-11")

    def move(self, when, only_after=None):
        """Every log row (or only the ones not moved yet) to `when`, UTC as the log writes it."""
        con, where = self.store.con, ("WHERE at > ?", (only_after,)) if only_after else ("", ())
        for table in ("change_log", "item_events", "applies"):
            con.execute(f"UPDATE {table} SET at = ? {where[0]}", (when, *where[1]))

    def show(self, cdp, width=1400, dark=False):
        p = Pg.at(self, cdp, self.s.port, "#published&p=ABC")
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        if dark:
            p.js("document.documentElement.dataset.theme = 'dark'")
        p.until("!!document.querySelector('#as-at-pick')", "the picker drew on the Published reports page")
        return p

    def ask(self, p, typed):
        p.js(f"document.querySelector('#as-at-day').value = {json.dumps(typed)}; document.querySelector('#as-at-show').click()")

    def main_text(self, p):
        return p.js("document.querySelector('#main').textContent.replace(/\\s+/g, ' ')")

    def test_as_at_a_day_shows_then_read_only_and_back_to_now_shows_now(self):
        with chrome() as cdp:
            p = self.show(cdp)
            self.ask(p, "20-01-2020")
            p.until("!!document.querySelector('#as-at-banner') && document.querySelectorAll('.sec').length > 0", "the rebuilt Dashboard drew")
            self.assertEqual(p.js("location.hash.split('&')[0]"), "#dashboard")
            self.assertIn(BANNER, p.js("document.querySelector('#as-at-banner').textContent.replace(/\\s+/g, ' ')"))
            self.assertIn("Read only · this was not published in this form", p.js("document.querySelector('#as-at-banner').textContent"))
            self.assertTrue(p.js("document.querySelector('#report').hasAttribute('inert')"), "nothing in the frame can be focused or clicked")
            self.assertEqual(p.js("getComputedStyle(document.querySelector('#report')).borderTopStyle"), "dashed")
            self.assertEqual(p.js(f"document.querySelectorAll({json.dumps(EDITING)}).length"), 0, "no Edit part anywhere on the page")
            self.assertEqual(p.js("document.querySelector('#report').dataset.mode"), "view")
            text = self.main_text(p)
            self.assertNotIn(NEW, text)
            self.assertNotIn("ZQ a risk raised later", text)
            self.assertEqual(p.js("document.querySelector('[data-fig=overdue] .v').textContent"), "0", "due 25-01-2020: not overdue on 20-01-2020")
            self.assertEqual(p.js("document.querySelector('[data-fig=risks] .v').textContent"), "0")
            self.assertNotIn("At risk", p.js("document.querySelector('[data-fig=health]').textContent"))
            p.js("document.querySelector('#as-at-back').click()")
            p.until("!document.querySelector('#as-at-banner') && !!document.querySelector('[data-mode=edit]')", "Back to now")
            p.until("document.querySelector('[data-fig=overdue] .v') && document.querySelector('[data-fig=overdue] .v').textContent === '1'", "now: overdue")
            self.assertFalse(p.js("document.querySelector('#report').hasAttribute('inert')"))
            self.assertIn("At risk", p.js("document.querySelector('[data-fig=health]').textContent"))
        self.assertEqual([r["description"] for r in self.store.read("actions", "ABC") if r["id"] == self.a], [NEW], "nothing was written")

    def test_another_page_leaves_the_past(self):
        with chrome() as cdp:
            p = self.show(cdp)
            self.ask(p, "20-01-2020")
            p.until("!!document.querySelector('#as-at-banner')", "the banner")
            p.js("document.querySelector('[data-view=work]').click()")
            p.until("location.hash.startsWith('#work') && !document.querySelector('#as-at-banner')", "Work items is now")
            p.until(f"document.querySelector('#main').textContent.includes({json.dumps(NEW)})", "today's words on Work items")
            self.assertEqual(p.js("document.querySelectorAll('[data-mode]').length"), 0, "no View | Edit switch on Work items: it is the Dashboard's alone")

    def test_refusals_in_plain_words(self):
        with chrome() as cdp:
            p = self.show(cdp)
            self.ask(p, "31-02-2020")
            p.until("document.querySelector('#as-at-pick .pub-msg').textContent.includes('Type a day as DD-MM-YYYY')", "not a day")
            self.ask(p, "01-01-2099")
            p.until("document.querySelector('#as-at-pick .pub-msg').textContent.includes('That day has not happened yet')", "the future")
            self.ask(p, "01-01-2019")
            p.until("document.querySelector('#as-at-pick .pub-msg').textContent.includes('did not exist yet on 01-01-2019')", "before the project")
            self.assertFalse(p.js("!!document.querySelector('#as-at-banner')"))

    def test_laptop_widths_light_and_dark(self):
        with chrome() as cdp:
            for width in (1400, 900):
                for dark in (False, True):
                    with self.subTest(width=width, dark=dark):
                        p = self.show(cdp, width, dark)
                        self.assertEqual(p.js("document.documentElement.scrollWidth <= window.innerWidth"), True, "the card fits")
                        box = p.js("JSON.stringify(document.querySelector('#as-at-day').getBoundingClientRect())")
                        self.assertGreater(json.loads(box)["width"], 60)
                        self.ask(p, "20-01-2020")
                        p.until("!!document.querySelector('#as-at-banner') && document.querySelectorAll('.sec').length > 0", "the banner")
                        if dark:
                            p.js("document.documentElement.dataset.theme = 'dark'")
                        self.assertEqual(p.js("document.documentElement.scrollWidth <= window.innerWidth"), True, "no sideways scroll")
                        b = json.loads(p.js("JSON.stringify(document.querySelector('#as-at-banner').getBoundingClientRect())"))
                        self.assertGreater(b["height"], 20)
                        self.assertLessEqual(b["right"], width)
                        colours = p.js("(() => { const s = getComputedStyle(document.querySelector('#as-at-banner')); "
                                       "return [s.color, s.backgroundColor]; })()")
                        self.assertNotEqual(colours[0], colours[1])
                        back = p.js("JSON.stringify(document.querySelector('#as-at-back').getBoundingClientRect())")
                        self.assertGreaterEqual(json.loads(back)["height"], 24, "Back to now is at least 24 px to point at")
                        p.js("document.querySelector('#as-at-back').click()")
                        p.until("!document.querySelector('#as-at-banner')", "Back to now")


if __name__ == "__main__":
    unittest.main()
