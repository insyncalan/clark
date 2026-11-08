"""Row S6: the words of a section the owner hid are markers for the finished file (publish_flow.markers_for, guarded), so a leak of a
hidden section's body into the file, the Word copy or the PDF is refused. Words a kept section also shows are no marker.
Fictional data only.

Run: python3 dev/run_tests.py test_publish_hidden_section_markers
"""
import json
import unicodedata

from clark import to_client
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
