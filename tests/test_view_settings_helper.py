"""Rows 1230 and 1234: the use case summary and Milestones share ONE view-settings checker (section_bodies._checked_view_settings).

Run: python3 dev/run_tests.py test_view_settings_helper
"""
import json
import unittest

from clark import section_bodies as sb

RULES = sb.Rules(plain=lambda t: True, visible=lambda t: True)


def check(kind, value):
    return sb.check(kind, json.dumps(value), RULES)


class Shared(unittest.TestCase):
    def test_both_kinds_store_and_refuse_the_same_values(self):
        good = [{}, {"n": 3}, {"n": "all", "scroll": True, "tracker": "off"}, {"n": 1000}]
        bad = [[], {"x": 1}, {"n": 0}, {"n": 1001}, {"n": True}, {"n": "7"}, {"scroll": 1}, {"tracker": "left"}, {"tracker": None}]
        for v in good:
            self.assertEqual(check("usecases", v), check("milestones", v), v)
        for v in bad:
            for kind in sb.VIEW_KINDS:
                with self.subTest(kind=kind, v=v), self.assertRaises(sb.Bad):
                    check(kind, v)

    def test_usecases_keeps_the_one_existing_sentence_and_milestones_its_own(self):
        with self.assertRaises(sb.Bad) as u:
            check("usecases", {"n": 0})
        self.assertEqual(str(u.exception), sb.BAD_VALUE)
        with self.assertRaises(sb.Bad) as m:
            check("milestones", {"n": 0})
        self.assertEqual(str(m.exception), sb.MS_N)

    def test_published_falls_back_per_field_for_both(self):
        for kind in sb.VIEW_KINDS:
            self.assertEqual(sb.published(kind, {"n": 0, "scroll": True, "tracker": "x"}), {"n": 5, "scroll": True, "tracker": "top"})
            self.assertEqual(sb.published(kind, "junk"), sb.VIEW_DEFAULTS)


if __name__ == "__main__":
    unittest.main()
