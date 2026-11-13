"""A long unbroken string in a project, milestone, use case or action name never gives the published file a sideways scroll.

Run: python3 dev/run_tests.py test_view_long_word
A real project is published with a 300 character word (no spaces) in the project name (crumbs), a milestone (the Milestones sentence),
a use case title (its bar), a use case's standing (its opened detail) and an action; every use case row is opened;
the finished file is opened from file:// at 1400 and 900 and every tab is drawn. All rows are fictional.
"""
import unittest

from _demo import USER
from _publish import PublishedFile
from test_glance_page import Setup, tearDownModule  # noqa: F401
from test_server import chrome

WORD = "Q" * 300
TABS = ("#dashboard", "#work", "#usecases", "#milestones")


class LongWord(PublishedFile, Setup):
    def plant_long(self):
        with self.store.step("dashboard", USER) as st:
            st.update("projects", "ABC", {"name": WORD})
            st.update("use_cases", self.uc2, {"title": WORD, "standing": WORD})
            st.update("actions", self.a_open, {"description": WORD})
            st.create("milestones", {"project": "ABC", "name": WORD, "baseline_date": "2030-03-01", "source": "demo"})

    def test_no_tab_of_the_file_scrolls_sideways(self):
        self.plant_long()
        path = self.publish()
        for width in (1400, 900):
            for tab in TABS:
                with self.subTest(width=width, tab=tab), chrome() as cdp:
                    p = self.draw(cdp, path, width)
                    p.js("location.hash = %r" % tab)
                    p.until("location.hash.startsWith(%r)" % tab, "the tab opened")
                    p.js("new Promise(r => setTimeout(r, 300))")
                    p.js("document.querySelectorAll('.ucbar').forEach(b => b.click())")      # open every use case row so its detail is drawn
                    p.js("new Promise(r => setTimeout(r, 300))")
                    self.assertEqual(p.js("document.documentElement.scrollWidth <= document.documentElement.clientWidth"), True,
                                     "%s at %d scrolls sideways: %s" % (tab, width, p.js("document.documentElement.scrollWidth")))


if __name__ == "__main__":
    unittest.main()
