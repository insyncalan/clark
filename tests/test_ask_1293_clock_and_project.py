"""Row 1293 tests 2 and 6 (test-only; no code is changed).

Run: python3 dev/run_tests.py test_ask_1293_clock_and_project
Test 2: on a fixed clock the request that reaches the model holds "Today is 17-11-2026." and the same question asked twice puts
the same request on the wire (a stub provider; nothing here calls a model). A different day gives a different line, so the line
is read from the clock and not written into the test.
Test 6: the chat survives a change of project, in a real browser against the real page. Fictional data only.
"""
import unittest
from unittest import mock

import test_ask_route as route
import test_ask_panel as panel
from test_report_editor import Base
from test_server import chrome
from clark import milestones

DAY = "2026-11-17"


class TodayInTheRequest(route.Base):
    def sent_on(self, day):
        before = len(self.provider.sent)
        with mock.patch.object(milestones, "today", return_value=day):
            status, got = self.question("What is overdue?")
        self.assertEqual(status, 200, got)
        self.assertEqual(len(self.provider.sent), before + 1)
        return self.provider.sent[-1]

    def test_the_request_holds_the_clocks_day_in_dd_mm_yyyy(self):
        self.assertIn("Today is 17-11-2026.", self.sent_on(DAY))

    def test_the_same_question_twice_on_a_fixed_clock_sends_the_same_request(self):
        first, second = self.sent_on(DAY), self.sent_on(DAY)
        self.assertEqual(first, second)

    def test_another_day_changes_the_line_and_nothing_stays_from_the_first(self):
        self.sent_on(DAY)
        later = self.sent_on("2026-11-18")
        self.assertIn("Today is 18-11-2026.", later)
        self.assertNotIn("17-11-2026", later)


TWO = [{"code": "ABC", "name": "Example Programme", "open": 3}, {"code": "XYZ", "name": "Second Programme", "open": 1}]
TURNS = "[...document.querySelectorAll('.ask-turn')].map(t => t.textContent)"
NAME = "document.querySelector('.top .hdr-project')"


class ChatAcrossProjects(Base):
    opened, ask = panel.Panel.opened, panel.Panel.ask       # the panel's own helpers; its tests are not run again here

    def setUp(self):
        super().setUp()
        self.stub = panel.Stub()
        self.s.httpd.ask = self.stub
        self.s.httpd.projects = lambda archived=False: TWO
        with self.store.step("dashboard", "tester", place="menu") as s:
            s.create("projects", {"code": "XYZ", "name": "Second Programme", "health": "On track"})

    def chat(self, cdp):
        p = self.opened(cdp)
        self.ask(p, "When is go-live?")
        p.until("document.querySelectorAll('.ask-turn').length === 2", "answered")
        return p, p.js(TURNS)

    def test_the_chat_survives_a_change_of_page_in_the_same_project(self):
        with chrome() as cdp:
            p, before = self.chat(cdp)
            p.js("window.marker = 'same page'")
            p.js("location.hash = location.hash.replace(/^#[a-z]+/, '#milestones')")
            p.until("location.hash.split('&')[0] === '#milestones'", "the Milestones page is open")
            self.assertEqual(p.js("window.marker"), "same page", "a change of page is no reload")
            self.assertTrue(p.js("!!document.querySelector('#ask-panel')"), "the panel stays open")
            self.assertEqual(p.js(TURNS), before, "the same two turns")
            self.assertEqual(self.stub.count("ask"), 1)

    @unittest.expectedFailure
    def test_the_chat_survives_a_change_of_project(self):
        """NOT MET on main (found while building this test): choosing another project in the header list is a fresh page load
        (stores/report.js loadProject: location.assign), the panel's signals are not carried (beforeReload holds only changes.js),
        so the panel is shut and the chat is empty. Row 1293 line 6 and row 1292 rule 4 say the chat survives. Marked expectedFailure
        until a ruling says whether the chat is to be carried (build) or the line is dropped; when it is built this test turns into an
        'unexpected success' and the marker is removed."""
        with chrome() as cdp:
            p, before = self.chat(cdp)
            p.js(f"{NAME}.click()")
            p.until("document.querySelectorAll('#project-menu [role=menuitemradio]').length === 2", "the project list has read both projects")
            p.js("[].filter.call(document.querySelectorAll('#project-menu [role=menuitemradio]'), e => e.textContent.indexOf('Second Programme') === 0)[0].click()")
            p.until("location.href.indexOf('XYZ') >= 0", "the address names the other project")
            p.until("document.readyState === 'complete' && !!document.querySelector('.top .hdr-project')", "the other project's page is up")
            self.assertTrue(p.js("!!document.querySelector('#ask-panel')"), "the panel stays open")
            self.assertEqual(p.js(TURNS), before, "the same two turns")
            self.ask(p, "And here?")
            p.until("document.querySelectorAll('.ask-turn').length === 4", "a follow-up in the new project")
            self.assertEqual(self.stub.calls[-1][1]["project"], "XYZ")
            self.assertEqual(len(self.stub.calls[-1][1]["earlier"]), 2, "and carries the chat so far")


if __name__ == "__main__":
    unittest.main()
