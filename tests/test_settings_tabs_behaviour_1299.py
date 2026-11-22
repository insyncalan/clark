"""Row 1299 AP11: what a project tab click does, in a real browser at 1400 px. Run: python3 dev/run_tests.py test_settings_tabs_behaviour_1299

What is asserted (Classic): a click makes no page load; the address keeps the tab's project as p (the rest of the address as it was) and the history entry is replaced, so
the entry count is the same and Back leaves Settings for the page before it, not for the previous tab; the project the top bar names does not change; the ask clark page has one bar whose first tab is All projects, then the project tabs; its click marks it and the Affects line says All projects, and a
project tab brings the project back. Chrome is required: these tests fail, never skip, without it.
"""
import unittest

from test_server import chrome
from test_settings_tabs_1299 import Rigged, LIVE, TABS


class TabBehaviour(Rigged):
    def test_tab_click_hash_history_and_independence(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p, 1400, slug="people")
            p.until(f"{TABS}.length === {len(LIVE)}", "the tabs drew")
            before = p.js("[location.hash, history.length, document.querySelector('#project-name').textContent, performance.getEntriesByType('navigation').length, window.__marker = 1]")
            p.js(f"{TABS}[2].click()")
            p.until(f"{TABS}[2].getAttribute('aria-current') === 'page'", "the third tab is marked")
            after = p.js("[location.hash, history.length, document.querySelector('#project-name').textContent, performance.getEntriesByType('navigation').length, window.__marker]")
            self.assertEqual(after[0], before[0].replace("p=PUB", "p=ZED"), "p is the tab's project, the page part is kept")
            self.assertEqual(after[1], before[1], "no entry was added")
            self.assertEqual(after[2], before[2], "the top bar still names the open project")
            self.assertEqual((after[3], after[4]), (before[3], 1), "the page was not loaded again")
            p.js(f"{TABS}[1].click()")
            p.until(f"{TABS}[1].getAttribute('aria-current') === 'page'", "the second tab is marked")
            self.assertEqual(p.js("[location.hash, history.length]"), [before[0].replace("p=PUB", "p=ABC"), before[1]], "a second click replaces the same entry")
            self.assertEqual(p.js("document.querySelector('#project-name').textContent"), before[2])

    def test_back_steps_through_pages_not_tabs(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p, 1400, slug="people")
            p.until(f"{TABS}.length === {len(LIVE)}", "the tabs drew")
            p.js("location.hash = '#settings&p=PUB&s=reports'")
            p.until("document.querySelector('.set-cards').getAttribute('data-page') === 'reports'", "Reports and pages drew")
            p.until(f"{TABS}.length === {len(LIVE)}", "the tabs drew")
            p.js(f"{TABS}[1].click(); {TABS}[2].click()")
            p.until(f"{TABS}[2].getAttribute('aria-current') === 'page'", "the third tab is marked")
            p.js("history.back()")
            p.until("document.querySelector('.set-cards').getAttribute('data-page') === 'people'", "Back went to the page before, not the tab before")

    def test_ask_clark_has_one_bar_with_a_leading_all_projects_tab(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p, 1400, slug="claude")
            all_tabs = "[...document.querySelectorAll('.set-tabs .set-tab')]"
            p.until(f"{all_tabs}.length === {len(LIVE) + 1}", "the tabs drew")
            self.assertEqual(p.js("document.querySelectorAll('.set-tabs').length"), 1, "one bar")
            self.assertEqual(p.js(f"{all_tabs}.map(b => b.textContent)"), ["All projects"] + [x["name"] for x in LIVE])
            self.assertEqual(p.js(f"{all_tabs}.map(b => b.getAttribute('aria-current'))"), [None, "page", None, None], "the open project is the chosen one to start with")
            before = p.js("location.hash")
            p.js(f"{all_tabs}[0].click()")
            p.until(f"{all_tabs}[0].getAttribute('aria-current') === 'page'", "All projects is marked")
            self.assertEqual(p.js(f"{all_tabs}.filter(b => b.getAttribute('aria-current')).length"), 1, "only one tab is marked")
            self.assertEqual(p.js("document.querySelector('.set-affects').textContent.trim()"), "Affects: All projects")
            self.assertEqual(p.js("location.hash"), before, "the address is not touched")
            p.js(f"{all_tabs}[2].click()")
            p.until("document.querySelector('.set-affects').textContent.trim() === 'Affects: ABC'", "the project tab brings the project back")
            p.js("location.hash = '#settings&p=PUB&s=people'")
            p.until("document.querySelector('.set-cards').getAttribute('data-page') === 'people'", "People drew")
            self.assertEqual(p.js("document.querySelectorAll('.set-tabs .set-tab[data-all]').length"), 0, "no other page has the All projects tab")


if __name__ == "__main__":
    unittest.main()
