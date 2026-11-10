"""Row S6: hostile spellings and sizes for the Gantt markers (publish_flow.gantt_markers, guarded) and the scan (to_client.check_copy):
a hidden value written in another Unicode form or letter case, with markup characters or a line break, very long, or inside the
note of a left-out line, is still found when it is in the file. A value the project shows is still no marker. Fictional data only.

Run: python3 dev/run_tests.py test_gantt_markers_hostile
"""
import unicodedata
import unittest

from clark import publish_flow, to_client
from test_gantt_markers import Base


class Hostile(Base):
    def refused(self, built, got, leak):
        body = built["body"].replace(b"</body>", b"<p>" + leak.encode("utf-8") + b"</p></body>")
        return bool(to_client.check_copy(body, markers=got, folder=None))

    def test_a_hidden_note_is_found_in_another_unicode_form_or_case(self):
        note = "Zq café zürich nöte"
        self.bare("ZQ-SHOWN-LINE", note=note)
        built, got = self.got()
        self.assertIn(note, got)
        for spelled in (unicodedata.normalize("NFD", note), note.upper(), unicodedata.normalize("NFD", note.upper())):
            with self.subTest(spelled=ascii(spelled)):
                self.assertTrue(self.refused(built, got, spelled))

    def test_a_marker_stored_decomposed_is_found_when_the_file_has_it_composed(self):
        note = unicodedata.normalize("NFD", "Zq café zürich nöte")
        self.bare("ZQ-SHOWN-LINE", note=note)
        built, got = self.got()
        self.assertTrue(self.refused(built, got, unicodedata.normalize("NFC", note)))

    def test_a_note_with_markup_characters_is_found_escaped_or_not(self):
        note = "ZQ <b>client</b> & \"co\" 'x'"
        self.bare("ZQ-SHOWN-LINE", note=note)
        built, got = self.got()
        self.assertIn(note, got)
        import html
        for spelled in (note, html.escape(note), html.escape(note, quote=False)):
            with self.subTest(spelled=spelled):
                self.assertTrue(self.refused(built, got, spelled))

    def test_a_note_with_a_line_break_is_found_in_the_json_spelling(self):
        note = "ZQ-FIRST-LINE-OF\nZQ-SECOND-LINE-OF"
        self.bare("ZQ-SHOWN-LINE", note=note)
        built, got = self.got()
        self.assertIn(note, got)
        self.assertTrue(self.refused(built, got, "ZQ-FIRST-LINE-OF\\nZQ-SECOND-LINE-OF"))
        self.assertTrue(self.refused(built, got, note))

    def test_a_very_long_note_is_a_marker_and_is_found(self):
        note = "ZQ-LONG-" + "x" * 1992                                  # the store caps a note at 2000
        for n in range(150):
            self.bare(f"ZQ-LINE-{n:04d}", note=f"ZQ-NOTE-{n:04d}-" + "y" * 1980)
        self.bare("ZQ-SHOWN-LINE", note=note)
        built, got = self.got()
        self.assertIn(note, got)
        self.assertTrue(self.refused(built, got, note))
        self.assertTrue(self.refused(built, got, note.upper()))

    def test_a_client_name_in_the_note_of_an_eye_off_line_is_found(self):
        self.project(hidden="")
        self.bare("ZQ-SHOWN-LINE")
        self.bare("ZQ-EYE-OFF-LINE", show=0, note="Ask Zqcorp Holdings about the renewal", owner="Zqcorp Holdings")
        built, got = self.got()
        for m in ("Zqcorp Holdings", "Ask Zqcorp Holdings about the renewal"):
            self.assertIn(m, got)
            self.assertTrue(self.refused(built, got, m.upper()))

    def test_a_client_name_in_a_hidden_note_of_a_kept_line_is_found(self):
        self.bare("ZQ-SHOWN-LINE", note="Zqcorp Holdings will not like this")
        built, got = self.got()
        self.assertIn("Zqcorp Holdings will not like this", got)
        self.assertTrue(self.refused(built, got, "zqcorp holdings will not like this"))

    def test_a_value_with_outer_white_space_is_a_marker_without_it(self):
        self.bare("ZQ-SHOWN-LINE", note="  \tZQ-PADDED-NOTE  \n")
        built, got = self.got()
        self.assertIn("ZQ-PADDED-NOTE", got)

    def test_a_hidden_value_shorter_than_the_least_is_no_marker_and_the_least_is(self):
        short = "z" * (publish_flow.MIN_MARKER - 1)
        exact = "z" * publish_flow.MIN_MARKER
        self.bare("ZQ-SHOWN-LINE", note=short)
        self.bare("ZQ-SHOWN-TWO", note=exact)
        built, got = self.got()
        self.assertNotIn(short, got)
        self.assertIn(exact, got)

    def test_a_shown_value_in_another_form_is_still_no_marker(self):
        self.project(hidden="show,note,budget,effort,baseline_start,baseline_end")            # owner shown
        owner = "Zq Café Owner"
        self.bare("ZQ-SHOWN-LINE", owner=owner)
        built, got = self.got()
        self.assertNotIn(owner, got)
        self.assertEqual(to_client.check_copy(built["body"], markers=got, folder=None), [])

    def test_a_number_hidden_is_found_in_its_text_spellings(self):
        self.bare("ZQ-SHOWN-LINE", budget=1234567.25)
        built, got = self.got()
        self.assertIn("1234567.25", got)
        self.assertTrue(self.refused(built, got, "1234567.25"))


if __name__ == "__main__":
    unittest.main()
