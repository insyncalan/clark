"""Row S6: the words of a section the owner hid are markers for the finished file (publish_flow.markers_for, guarded), so a leak of a
hidden section's body into the file, the Word copy or the PDF is refused. Words a kept section also shows are no marker.
Fictional data only.

Run: python3 dev/run_tests.py test_publish_hidden_section_markers
"""
import json
import time
import unicodedata

from clark import publish, publish_flow, to_client
from test_gantt_markers import Base

HID_TEXT = "<p>Zqcorp Holdings secret plan</p><ul><li>Zq renewal price is low</li></ul>"
HID_NEEDS = json.dumps({"v": 1, "rows": [{"what": "Zqcorp must sign the waiver", "kind": "decision", "from": "Zqcorp must sign the waiver", "by": "", "hidden": 0}]})
HID_TRACKER = json.dumps({"v": 1, "groups": [{"name": "Plan", "lines": [{"text": "Zqcorp audit walkthrough line"}]}]})


class HiddenSections(Base):
    def section(self, ref, kind, body, hidden):
        self.sql("INSERT INTO report_sections (project, id, type, title, body, beside, hidden, sort_order) VALUES ('ABC',?,?,?,?,0,?,?)",
                 (ref, kind, "Title " + ref, body, hidden, 9000 + len(ref)))

    def refused(self, built, got, leak):
        body = built["body"].replace(b"</body>", b"<p>" + leak.encode("utf-8") + b"</p></body>")
        return bool(to_client.check_copy(body, markers=got, folder=None))

    def test_the_words_of_a_hidden_text_section_are_markers(self):
        self.section("s-hid", "text", HID_TEXT, 1)
        built, got = self.got()
        self.assertNotIn("Zqcorp", built["body"].decode("utf-8"))
        for m in ("Zqcorp Holdings secret plan", "Zq renewal price is low"):
            self.assertIn(m, got)
            self.assertTrue(self.refused(built, got, m))
            self.assertTrue(self.refused(built, got, unicodedata.normalize("NFD", m.upper())))

    def test_the_words_of_a_hidden_needs_or_tracker_section_are_markers(self):
        self.section("s-hn", "needs", HID_NEEDS, 1)
        self.section("s-ht", "tracker", HID_TRACKER, 1)
        built, got = self.got()
        for m in ("Zqcorp must sign the waiver", "Zqcorp audit walkthrough line"):
            self.assertIn(m, got)
            self.assertTrue(self.refused(built, got, m))

    def test_a_shown_section_is_no_marker_and_the_file_as_built_passes(self):
        self.section("s-vis", "text", "<p>Visible words here today</p>", 0)
        self.section("s-hid", "text", HID_TEXT, 1)
        built, got = self.got()
        self.assertIn("Visible words here today", built["body"].decode("utf-8"))
        self.assertNotIn("Visible words here today", got)
        self.assertEqual(to_client.check_copy(built["body"], markers=got, folder=None), [])

    def test_words_a_shown_section_also_has_are_no_marker(self):
        self.section("s-vis", "text", "<p>Zqcorp Holdings secret plan</p>", 0)
        self.section("s-hid", "text", HID_TEXT, 1)
        built, got = self.got()
        self.assertNotIn("Zqcorp Holdings secret plan", got)
        self.assertIn("Zq renewal price is low", got)
        self.assertEqual(to_client.check_copy(built["body"], markers=got, folder=None), [])

    def test_a_short_word_of_a_hidden_section_is_no_marker(self):
        self.section("s-hid", "text", "<p>Zq shor</p>", 1)
        built, got = self.got()
        self.assertNotIn("Zq shor", got)

    def test_a_shown_section_whose_body_the_file_does_not_carry_is_no_marker(self):
        # Only a section the owner hid has markers: a shown built-in section keeps a stored body that is never published, and
        # that body is not in the file, not in the kept text and not in the page, so only the hidden flag keeps it out of the markers.
        self.section("s-raid", "raid", "<p>Zq stored raid words nobody publishes</p>", 0)
        built, got = self.got()
        self.assertNotIn("Zq stored raid words nobody publishes", built["body"].decode("utf-8"))
        self.assertNotIn("Zq stored raid words nobody publishes", got)
        self.section("s-raid-hid", "raid", "<p>Zq stored raid words nobody publishes</p>", 1)
        self.assertIn("Zq stored raid words nobody publishes", self.got()[1], msg="the same words in a hidden section are a marker")

    def test_words_the_bare_page_has_are_no_marker_and_the_same_words_without_it_are(self):
        # markers_for(..., template) is the bare page every file holds; its words cannot tell a leak from the page itself.
        self.section("s-hid", "text", "<p>Zq bare page sentence here</p>", 1)
        built = publish.build(self.s, "ABC", now="2031-06-15")
        page = "<html><body><p>Zq BARE page sentence here</p></body></html>"
        self.assertNotIn("Zq bare page sentence here", publish_flow.markers_for(self.s, "ABC", built["published"], page))
        self.assertIn("Zq bare page sentence here", publish_flow.markers_for(self.s, "ABC", built["published"], ""))
        self.assertIn("Zq bare page sentence here", publish_flow.markers_for(self.s, "ABC", built["published"], "<p>Other words</p>"))

    def test_a_hidden_run_inside_a_longer_shown_text_is_still_a_marker(self):
        # Same whole-value rule as the left-out rows (#619): a kept value excuses a run only when it IS the run, not when the run
        # is a piece of it. A hidden section pasted into a longer shown section must be refused.
        self.section("s-vis", "text", "<p>Intro. Zqcorp Holdings secret plan, and more words after it.</p>", 0)
        self.section("s-hid", "text", HID_TEXT, 1)
        built, got = self.got()
        self.assertIn("Zqcorp Holdings secret plan", got)

    def test_a_shown_run_equal_to_the_hidden_run_is_still_no_marker(self):
        self.section("s-vis", "text", "<p>Zqcorp Holdings secret plan</p>", 0)
        self.section("s-hid", "text", HID_TEXT, 1)
        self.assertNotIn("Zqcorp Holdings secret plan", self.got()[1])

    def test_thousands_of_runs_are_capped_and_scan_fast(self):
        # A hostile hidden section of 8,000 distinct runs made 8,006 markers and a 145 s scan. The run markers are capped
        # (count and total characters); the whole-body marker stays, so a paste of the full body is still refused.
        runs = "".join("<p>Hostile run number %05d of filler</p>" % i for i in range(8000))
        self.section("s-big", "text", runs, 1)
        t0 = time.monotonic()
        built, got = self.got()
        self.assertEqual(len([m for m in got if m.startswith("Hostile run number")]), publish_flow.MAX_RUN_MARKERS)      # the cap is reached, not just kept under
        # the whole-body marker (markers_for, #619) is one long text, counted apart from the run markers the cap is about
        self.assertLessEqual(sum(len(m) for m in got if len(m) < 1000), publish_flow.MAX_RUN_CHARS + 20000)
        self.assertEqual(to_client.check_copy(built["body"], markers=got, folder=None), [])
        self.assertLess(time.monotonic() - t0, 30.0)          # was 145 s before the cap; a slow runner (macOS) stays well inside 30
        self.assertTrue(self.refused(built, got, " ".join("Hostile run number %05d of filler" % i for i in range(8000))))

    # mutation hunt (item 1151): the cases below each failed to catch a changed line of hidden_section_markers / _body_runs
    def markers(self):
        built = publish.build(self.s, "ABC", now="2031-06-15")
        return publish_flow.markers_for(self.s, "ABC", built["published"])

    def test_a_json_body_that_is_a_list_gives_its_strings_as_markers(self):
        self.section("s-list", "needs", json.dumps(["Zqcorp list item one", ["Zqcorp nested list item"]]), 1)
        got = self.got()[1]
        self.assertIn("Zqcorp list item one", got)
        self.assertIn("Zqcorp nested list item", got)

    def test_character_references_are_read_as_the_characters(self):
        self.section("s-ent", "text", "<p>Zqcorp &amp; Partners secret plan</p>", 1)
        got = self.got()[1]
        self.assertIn("Zqcorp & Partners secret plan", got)
        self.assertFalse([m for m in got if "&amp;" in m and not m.startswith("<")], "no run keeps the raw reference")

    def test_a_run_is_a_marker_from_exactly_the_minimum_length(self):
        n = publish_flow.MIN_MARKER
        self.section("s-edge", "text", "<p>%s</p><p>%s</p>" % ("Q" * (n - 1), "Z" * n), 1)
        got = self.got()[1]
        self.assertIn("Z" * n, got)
        self.assertNotIn("Q" * (n - 1), got)

    def test_a_run_has_its_spaces_and_line_breaks_folded_to_single_spaces(self):
        self.section("s-ws", "text", "<p>  Zqcorp   spread\n\n words   here </p>", 1)
        got = self.got()[1]
        self.assertIn("Zqcorp spread words here", got)
        self.assertNotIn("Zqcorp   spread\n\n words   here", got)

    def test_the_marker_of_a_run_says_which_section_it_came_from(self):
        self.section("s-where", "text", "<p>Zqcorp where-from run</p>", 1)
        self.assertEqual(self.markers().where["Zqcorp where-from run"], "s-where")

    def test_a_hidden_run_equal_to_a_kept_row_value_is_no_marker(self):
        shown = publish.build(self.s, "ABC", now="2031-06-15")["published"]["data"]["project"]
        value = next(v for v in shown.values() if isinstance(v, str) and len(v.strip()) >= publish_flow.MIN_MARKER and v == v.strip() and "  " not in v)
        self.section("s-kept", "text", "<p>%s</p><p>Zqcorp other hidden run</p>" % value, 1)
        got = self.got()[1]
        self.assertNotIn(value, got)
        self.assertIn("Zqcorp other hidden run", got)

    def test_the_character_cap_is_exact_and_stops_the_scan_for_good(self):
        cap = publish_flow.MAX_RUN_CHARS
        runs = "".join("<p>%s</p>" % ("Chars run %04d " % i).ljust(1000, "x") for i in range(120))
        self.section("s-chars", "text", runs, 1)
        got = [m for m in self.got()[1] if m.startswith("Chars run")]
        self.assertEqual(len(got), cap // 1000)                      # 100 runs of 1,000 reach the cap exactly: all 100 stay, the 101st goes
        self.assertEqual(sum(len(m) for m in got), cap)

    def test_a_run_that_does_not_fit_ends_the_scan_even_if_a_later_short_one_would(self):
        runs = "".join("<p>%s</p>" % ("Fit run %04d " % i).ljust(1000, "x") for i in range(99))
        runs += "<p>%s</p>" % "Over the line ".ljust(1500, "y") + "<p>Short tail run after the cap</p>"
        self.section("s-end", "text", runs, 1)
        got = self.got()[1]
        self.assertEqual(len([m for m in got if m.startswith("Fit run")]), 99)
        self.assertNotIn("Short tail run after the cap", got)

    def test_a_section_under_the_cap_keeps_every_run(self):
        runs = "".join("<p>Modest run number %02d of filler</p>" % i for i in range(20))
        self.section("s-mid", "text", runs, 1)
        got = self.got()[1]
        for i in range(20):
            self.assertIn("Modest run number %02d of filler" % i, got)
