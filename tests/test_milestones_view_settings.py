"""Row 1230: the Milestones section's view settings {n, scroll, tracker} live in report_sections.body as JSON (head's ruling).
An old built-in row (empty body) and an old published file open exactly as today; a missing key means today's behaviour
(n 5, scroll false, tracker top). Written first, red until the "milestones" checker in section_bodies.py exists.

Run: python3 dev/run_tests.py test_milestones_view_settings
"""
import json
import unittest

from _paths import SRC  # noqa: F401  (puts src/ on sys.path)
from clark import section_bodies as sb, store as store_module
from clark.store import BODY_RULES
from test_publish_section_bodies import Published

DEFAULTS = {"n": 5, "scroll": False, "tracker": "top"}


def check(body):
    return sb.check("milestones", body, BODY_RULES)


class Checker(unittest.TestCase):
    def test_milestones_has_a_checker(self):
        self.assertIn("milestones", sb.CHECKERS)

    def test_a_full_body_is_stored_as_its_canonical_json(self):
        got = json.loads(check(json.dumps({"n": 8, "scroll": True, "tracker": "bottom"})))
        self.assertEqual({k: got[k] for k in DEFAULTS}, {"n": 8, "scroll": True, "tracker": "bottom"})

    def test_missing_keys_default_to_todays_behaviour(self):
        for given in ({}, {"n": 3}, {"scroll": True}, {"tracker": "off"}):
            got = json.loads(check(json.dumps(given)))
            want = {**DEFAULTS, **given}
            self.assertEqual({k: got[k] for k in DEFAULTS}, want, given)

    def test_an_empty_body_is_no_content(self):
        self.assertEqual(check(""), "")
        self.assertEqual(check(None), "")

    def test_tracker_takes_top_bottom_off_only(self):
        for ok in ("top", "bottom", "off"):
            check(json.dumps({"tracker": ok}))
        for bad in ("left", "", "TOP", 1, None, True):
            with self.assertRaises(sb.Bad, msg=repr(bad)):
                check(json.dumps({"tracker": bad}))

    def test_n_is_a_whole_number_of_at_least_one(self):
        for bad in (0, -1, "5", None, True, 1.5):
            with self.assertRaises(sb.Bad, msg=repr(bad)):
                check(json.dumps({"n": bad}))

    def test_n_has_an_upper_limit(self):
        with self.assertRaises(sb.Bad):
            check(json.dumps({"n": 10 ** 6}))

    def test_n_may_be_all(self):
        self.assertEqual(json.loads(check(json.dumps({"n": "all"})))["n"], "all")
        for bad in ("All", "ALL", "everything"):
            with self.assertRaises(sb.Bad, msg=repr(bad)):
                check(json.dumps({"n": bad}))

    def test_scroll_is_a_true_boolean(self):
        for bad in (1, 0, "true", None):
            with self.assertRaises(sb.Bad, msg=repr(bad)):
                check(json.dumps({"scroll": bad}))

    def test_a_body_that_is_not_an_object_is_refused(self):
        for bad in ("[]", "[1]", "3", '"x"', "true", "null"):
            with self.assertRaises(sb.Bad, msg=bad):
                check(bad)

    def test_an_unknown_key_is_refused(self):
        with self.assertRaises(sb.Bad):
            check(json.dumps({"n": 5, "colour": "red"}))

    def test_the_store_door_agrees(self):
        store_module.check_section_body("milestones", json.dumps({"n": 4}))
        with self.assertRaises(store_module.Invalid):
            store_module.check_section_body("milestones", json.dumps({"n": 0}))

    def test_n_limit_is_exactly_one_thousand(self):
        self.assertEqual(json.loads(check(json.dumps({"n": 1000})))["n"], 1000)
        self.assertEqual(json.loads(check(json.dumps({"n": 1})))["n"], 1)
        with self.assertRaises(sb.Bad):
            check(json.dumps({"n": 1001}))


class PublishedPerField(unittest.TestCase):
    """section_bodies.published reads what is stored field by field: a field that is missing or not valid publishes as today's value."""

    def pub(self, value):
        return sb.published("milestones", value)

    def test_a_missing_field_publishes_its_default(self):
        self.assertEqual(self.pub({}), DEFAULTS)
        self.assertEqual(self.pub({"n": 9}), {**DEFAULTS, "n": 9})
        self.assertEqual(self.pub({"scroll": True}), {**DEFAULTS, "scroll": True})
        self.assertEqual(self.pub({"tracker": "off"}), {**DEFAULTS, "tracker": "off"})

    def test_a_field_that_is_not_valid_publishes_its_default_never_the_bad_value(self):
        for bad in (0, -1, 1001, "5", "All", True, None, 1.5):
            self.assertEqual(self.pub({"n": bad})["n"], 5, repr(bad))
        for bad in (1, 0, "true", None):
            self.assertIs(self.pub({"scroll": bad})["scroll"], False, repr(bad))
        for bad in ("left", "", 1, None):
            self.assertEqual(self.pub({"tracker": bad})["tracker"], "top", repr(bad))

    def test_a_value_that_is_not_a_dict_publishes_the_defaults(self):
        for bad in (None, [], "x", 3):
            self.assertEqual(self.pub(bad), DEFAULTS, repr(bad))

    def test_a_valid_value_is_published_as_it_is(self):
        full = {"n": "all", "scroll": True, "tracker": "bottom"}
        self.assertEqual(self.pub(full), full)
        self.assertEqual(self.pub({**full, "n": 1000})["n"], 1000)


class OldRowsAndFiles(Published):
    def ms(self):
        """The built-in Milestones row every demo project is seeded with (empty body, as an old file has it)."""
        return next(i for i, s in self.sections().items() if s["type"] == "milestones")

    def test_an_old_built_in_row_with_empty_body_publishes_as_today(self):
        ref = self.ms()
        before = self.sections()[ref]
        self.assertNotIn("n", before)
        self.assertNotIn("scroll", before)
        self.assertNotIn("tracker", before)

    def test_the_writer_stores_a_milestones_body_in_its_canonical_form(self):
        ref = self.ms()
        self.write(ref, json.dumps({"tracker": "bottom"}))
        self.assertEqual(self.sections()[ref]["tracker"], "bottom")
        status, _ = self.change(self.req("update", id=ref, changes={"body": json.dumps({"n": 0})}))
        self.assertNotEqual(status, 200)

    def test_an_empty_body_row_still_checks_as_no_content(self):
        self.assertEqual(sb.check("milestones", "", BODY_RULES), "")

    def test_a_row_with_settings_publishes_n_scroll_tracker(self):
        ref = self.ms()
        self.raw(ref, json.dumps({"n": 7, "scroll": True, "tracker": "off"}))
        got = self.sections()[ref]
        self.assertEqual((got["n"], got["scroll"], got["tracker"]), (7, True, "off"))

    def test_a_row_with_a_partial_body_publishes_the_defaults(self):
        ref = self.ms()
        self.raw(ref, json.dumps({"n": 9}))
        got = self.sections()[ref]
        self.assertEqual((got["n"], got["scroll"], got["tracker"]), (9, False, "top"))

    def test_n_all_publishes_as_all(self):
        ref = self.ms()
        self.raw(ref, json.dumps({"n": "all"}))
        self.assertEqual(self.sections()[ref]["n"], "all")

    def test_the_milestones_section_stays_in_the_file_whatever_its_body(self):
        ref = self.ms()
        for body in ("", "not json", json.dumps({"n": -3}), json.dumps({"zzz": 1})):
            self.raw(ref, body)
            self.assertIn(ref, self.sections(), body)

    def test_a_bad_stored_body_publishes_as_an_old_row(self):
        ref = self.ms()
        self.raw(ref, json.dumps({"n": -3}))
        self.assertNotIn("n", self.sections()[ref])


if __name__ == "__main__":
    unittest.main()
