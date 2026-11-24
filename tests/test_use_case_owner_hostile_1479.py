"""Row 1479: the owner of a use case now travels in the published file (as plain text, for the use case's own page). What the editor wrote is cleaned like the
other use case words: hidden characters out, cut at the limit, empty stays empty, and a script tag in it cannot end the data block of the page.

Run: python3 dev/run_tests.py test_use_case_owner_hostile_1479
Quick tier: no browser. Fictional words only.
"""
import json
import re
import unittest

from _paths import SRC  # noqa: F401
from test_publish_usecases import made, planted

from clark import publish


def with_owner(value):
    def plant(p):
        planted(p)
        p["data"]["use_cases"][0]["owner"] = value
    return plant


def owner_in_file(value):
    _, pub, text = made(with_owner(value))
    return pub["data"]["use_cases"][0].get("owner"), text


class OwnerInTheFile(unittest.TestCase):
    def test_the_owner_is_a_field_of_the_use_case_and_the_link_is_not(self):
        self.assertIn("owner", publish.PUBLISH_FIELDS["use_cases"])
        self.assertNotIn("owner_id", publish.PUBLISH_FIELDS["use_cases"])
        self.assertEqual(owner_in_file("Zed Placeholder")[0], "Zed Placeholder")

    def test_hidden_characters_are_dropped(self):
        got, _ = owner_in_file("Zed\u200b Place\u202eholder\x00\x07")
        self.assertEqual(got, "Zed Placeholder")

    def test_a_very_long_owner_is_cut_at_the_limit(self):
        got, _ = owner_in_file("Q" * (publish.REASON_LIMIT + 700))
        self.assertEqual(len(got), publish.REASON_LIMIT)

    def test_empty_and_none_stay_empty(self):
        self.assertIn(owner_in_file("")[0], ("", None))
        self.assertIsNone(owner_in_file(None)[0])

    def test_unicode_and_quotes_are_kept_as_text(self):
        word = "Zo\u00eb \"Placeholder\" O'Neil \u4e2d\u6587 \U0001f600"
        self.assertEqual(owner_in_file(word)[0], word)

    def test_a_script_tag_cannot_end_the_data_block(self):
        got, text = owner_in_file("</script><img src=x onerror=alert(1)>")
        self.assertEqual(got, "</script><img src=x onerror=alert(1)>", "kept as the words they are")
        self.assertNotIn("</script><img", text, "never raw in the page")


if __name__ == "__main__":
    unittest.main()
