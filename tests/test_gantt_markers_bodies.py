"""Row 1027 (1.0.5 ultrareview, section 1): publish_flow.gantt_markers gives the same two exemptions markers_for gives its other
markers: a value that is in the words of a kept report section (its body), and one that is in the bare page (the template every
file holds). Before, a Gantt owner or baseline date that a section's own text also names made the whole publish refuse (a
regression from 1.0.4). A value found nowhere else is still a marker and still refused. Real publishes, through the web publish.

Fictional data only: the demo store's project ABC, one Gantt line, one kept section, a client folder and a Local folder.
Run: python3 dev/run_tests.py test_gantt_markers_bodies
"""
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _demo import DemoStore
from _paths import SRC  # noqa: F401  (puts src/ on the path)
from clark import page, publish, publish_flow
from test_gantt_markers import leaky_gantt_for_client

USER = "Sam Carter"
TODAY = "2026-10-29"
HIDE = "show,note,budget,effort,baseline_start,baseline_end,owner"


class Setup(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store
        self.tmp = Path(tempfile.mkdtemp(prefix="clark-gantt-bodies-")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.local, self.client = self.tmp / "Local", self.tmp / "Client"
        self.local.mkdir()
        self.client.mkdir()
        self.demo.update("projects", "ABC", {"publish_client": str(self.client), "show_gantt_client": 1, "gantt_hidden_columns": HIDE})

    def line(self, **cols):
        with self.store.step("dashboard", USER) as st:
            st.create("gantt_lines", {"project": "ABC", "type": "task", "name": "ZQ-SHOWN-LINE", "start": "2026-11-02",
                                      "end": "2026-11-13", "show": 1, "sort_order": 90, **cols})

    def section(self, body, hidden=0):
        with self.store.step("dashboard", USER) as st:
            st.create("report_sections", {"project": "ABC", "type": "text", "title": "Plain words", "body": body,
                                          "hidden": hidden, "sort_order": 50})

    def publish(self):
        publisher = publish_flow.Publisher(self.store.path, [], choose_save_file=lambda prompt, name, start=None: self.local / name,
                                           today=lambda: TODAY, by_user=lambda: USER, data_dir=Path(self.store.path).parent)
        return publisher.publish({"project": "ABC", "to_client": True})

    def markers(self):
        built = publish.build(self.store, "ABC", now=TODAY)
        return list(publish_flow.markers_for(self.store, "ABC", built["published"], page.page_html(None, view=True)))

    def assertPublishes(self):
        status, got = self.publish()
        self.assertEqual((status, got["ok"]), (200, True), got)

    def assertRefused(self):
        """The Gantt copy is made to leak the value (as test_gantt_markers does), so the file holds it and only the scan stands in the way."""
        with mock.patch.object(publish, "gantt_for_client", leaky_gantt_for_client):
            status, got = self.publish()
        self.assertEqual((status, got["code"]), (409, "refused"), got)


class OwnerAndDates(Setup):
    def test_an_owner_that_a_section_body_also_names_publishes(self):
        self.line(owner="ZQ-Dana Reyes")
        self.section("This quarter the work is led by ZQ-Dana Reyes and her team.")
        self.assertPublishes()

    def test_an_owner_found_nowhere_else_is_still_refused(self):
        self.line(owner="ZQ-Dana Reyes")
        self.section("This quarter the work is led by someone else.")
        self.assertIn("ZQ-Dana Reyes", self.markers())
        self.assertRefused()

    def test_a_baseline_date_that_a_section_body_also_names_publishes(self):
        self.line(baseline_start="2031-05-06")
        self.section("The first plan said the work would start on 2031-05-06 and it did not.")
        self.assertPublishes()

    def test_a_baseline_date_found_nowhere_else_is_still_refused(self):
        self.line(baseline_start="2031-05-06")
        self.assertIn("2031-05-06", self.markers())
        self.assertRefused()

    def test_an_owner_a_body_also_names_is_refused_when_the_gantt_copy_leaks_it(self):
        self.line(owner="ZQ-Dana Reyes")
        self.section("This quarter the work is led by ZQ-Dana Reyes and her team.")
        self.assertRefused()

    def test_a_baseline_date_a_body_also_names_is_refused_when_the_gantt_copy_leaks_it(self):
        self.line(baseline_start="2031-05-06")
        self.section("The first plan said the work would start on 2031-05-06 and it did not.")
        self.assertRefused()

    def test_an_owner_made_of_the_bare_pages_own_words_publishes(self):
        self.line(owner="Milestones")
        self.assertNotIn("Milestones", self.markers())
        self.assertPublishes()


class Hostile(Setup):
    """Hostile pass on row 1027."""

    def test_an_owner_named_only_in_a_hidden_section_is_still_refused(self):
        self.line(owner="ZQ-Dana Reyes")
        self.section("Led by ZQ-Dana Reyes and her team.", hidden=1)
        self.assertIn("ZQ-Dana Reyes", self.markers())
        self.assertRefused()

    def test_an_owner_named_only_in_a_section_title_is_still_a_marker(self):
        self.line(owner="ZQ-Dana Reyes")
        with self.store.step("dashboard", USER) as st:
            st.create("report_sections", {"project": "ABC", "type": "text", "title": "ZQ-Dana Reyes", "body": "plain",
                                          "hidden": 0, "sort_order": 51})
        self.assertIn("ZQ-Dana Reyes", self.markers())

    def test_unicode_and_hostile_owner_in_body_publishes_and_unnamed_one_refused(self):
        owner = "Zo\u00eb <b>&amp; \"O'Neil\"</b> \u4e2d\u6587"
        self.line(owner=owner)
        self.section("Led by " + owner + " today.")
        self.assertPublishes()

    def test_unicode_owner_found_nowhere_is_refused(self):
        owner = "Zo\u00eb ZQ\u4e2d\u6587 \U0001F600"
        self.line(owner=owner)
        self.section("Nobody named here.")
        self.assertIn(owner, self.markers())
        self.assertRefused()

    def test_a_long_owner_that_is_only_a_prefix_of_a_body_word_is_not_silently_exempt_when_body_is_short(self):
        owner = "ZQ-" + "x" * 80
        self.line(owner=owner)
        self.section("short body")
        self.assertIn(owner, self.markers())

    def test_an_eye_off_line_name_only_in_a_hidden_section_still_a_marker(self):
        with self.store.step("dashboard", USER) as st:
            st.create("gantt_lines", {"project": "ABC", "type": "task", "name": "ZQ-SECRET-LINE", "start": "2026-11-02",
                                      "end": "2026-11-13", "show": 0, "sort_order": 91})
        self.section("The ZQ-SECRET-LINE work.", hidden=1)
        self.assertIn("ZQ-SECRET-LINE", self.markers())


if __name__ == "__main__":
    unittest.main()
