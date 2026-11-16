"""Row 1234: survivors, group C. One-line changes to the summary's view rules (logic/useCaseView.js) that the first tests let through.

Run: ~/ag/slot.sh with, inside tests/: PYTHONPATH=../src:../vendor:. python3 -m unittest test_uc_view_survivors_c_1234
Equivalent changes (no test can tell them apart, so none is written): viewOf's own "is it an array" check (an array has no n, so normalizeView gives the
same default and set stays false), its "is the file entry an object" check (the next line drops any non-object), and its "body is not empty" check
(an empty body fails to parse and gives the default).
"""
import json
import unittest

from test_use_case_view_1234 import run

DEFAULT = {"n": 5, "scroll": False, "tracker": "top"}


class ShowAllControl(unittest.TestCase):
    def test_no_control_when_nothing_is_hidden(self):
        for total in (0, 1, 4, 5):
            with self.subTest(total=total):
                self.assertFalse(run(f"V.needsShowAll({total}, {{n: 5}})"))

    def test_the_control_comes_with_the_first_hidden_row(self):
        self.assertTrue(run("V.needsShowAll(6, {n: 5})"))
        self.assertTrue(run("V.needsShowAll(2, {n: 1})"))


class TrackerOn(unittest.TestCase):
    def test_on_is_false_only_for_off(self):
        for place, on in (("top", True), ("bottom", True), ("off", False)):
            with self.subTest(tracker=place):
                self.assertEqual(run(f"V.trackerPlace({{tracker: '{place}'}})")["on"], on)


class ViewOfSet(unittest.TestCase):
    def of(self, section, from_file=False):
        return run(f"V.viewOf({json.dumps(section)}, {json.dumps(from_file)})")

    def test_a_null_count_is_not_a_set_count(self):
        self.assertFalse(self.of({"body": json.dumps({"n": None})})["set"])
        self.assertFalse(self.of({"n": None, "tracker": "off"}, True)["set"])
        self.assertEqual(self.of({"body": json.dumps({"n": None})})["n"], 5)

    def test_a_written_count_is_a_set_count_even_when_it_is_the_default(self):
        self.assertTrue(self.of({"body": json.dumps({"n": 5})})["set"])
        self.assertTrue(self.of({"n": "all"}, True)["set"])
        self.assertFalse(self.of({"body": json.dumps({"scroll": True})})["set"])


class BodyOf(unittest.TestCase):
    def test_the_body_text_holds_the_three_settings_in_one_order_and_nothing_else(self):
        self.assertEqual(run("V.bodyOf({n: 3, scroll: true, tracker: 'off', extra: 1})"), '{"n":3,"scroll":true,"tracker":"off"}')

    def test_a_bad_setting_is_stored_as_the_default_for_that_field(self):
        self.assertEqual(run("V.bodyOf({n: 0, scroll: 'yes', tracker: 'left'})"), json.dumps(DEFAULT, separators=(",", ":")))
        # an absent key stays absent: a view with nothing given writes nothing (row 1234: a tracker-only click must not write n)
        self.assertEqual(run("V.bodyOf(undefined)"), "{}")
        self.assertEqual(run("V.bodyOf({tracker: 'left'})"), '{"tracker":"top"}')

    def test_the_body_reads_back_the_same(self):
        saved = {"n": "all", "scroll": True, "tracker": "bottom"}
        text = run(f"V.bodyOf({json.dumps(saved)})")
        self.assertEqual(run(f"V.normalizeView({json.dumps(text)})"), saved)


class NormalizeFields(unittest.TestCase):
    def test_scroll_is_a_true_or_false_and_nothing_else(self):
        for raw in ("1", "0", "'true'", "null", "[]"):
            with self.subTest(scroll=raw):
                self.assertFalse(run(f"V.normalizeView({{scroll: {raw}}})")["scroll"])
        self.assertTrue(run("V.normalizeView({scroll: true})")["scroll"])

    def test_a_stored_text_is_read_and_a_broken_one_is_the_default(self):
        self.assertEqual(run("V.normalizeView('{\"n\": 2, \"tracker\": \"off\"}')"), {"n": 2, "scroll": False, "tracker": "off"})
        self.assertEqual(run("V.normalizeView('{\"n\": 2')"), DEFAULT)

    def test_the_default_count_is_five(self):
        self.assertEqual(run("V.shownRows(9, {})"), {"shown": 5, "hidden": 4})
        self.assertEqual(run("V.visibleItems([1,2,3,4,5,6,7], {tracker: 'off'})"), [1, 2, 3, 4, 5])

    def test_all_does_not_fix_a_scroll_height(self):
        self.assertEqual(run("V.scrollRows({n: 'all', scroll: true})"), 0)
        self.assertEqual(run("V.scrollRows({n: 1, scroll: true})"), 1)


if __name__ == "__main__":
    unittest.main()
