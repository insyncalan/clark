"""Row 1261 slice 1: the Report headline template's data layer (section_kinds/reportheadline.py): defaults, bad values, what is
published, the registry and the step that lets the store keep the type. Fictional data only.

Run: python3 dev/run_tests.py test_tpl_reportheadline
"""
import sqlite3
import unittest

from clark import section_bodies, section_kinds, store as store_module
from clark.section_kinds import base, reportheadline as rh


class Rules:
    plain = visible = staticmethod(lambda t: t)


def check(v):
    return rh.check(v, Rules)


class Check(unittest.TestCase):
    def test_a_full_body_is_kept_as_it_is(self):
        body = {"v": 1, "health": "at_risk", "headline": "Go-live moves a week", "sentence": "The test cut-over found two gaps."}
        self.assertEqual(check(body), body)

    def test_missing_fields_take_their_defaults_and_are_not_stored(self):
        self.assertEqual(check({"v": 1}), {"v": 1})
        self.assertEqual(check({"v": 1, "health": None, "headline": "  ", "sentence": None}), {"v": 1})
        self.assertEqual(rh.upgrade({"v": 1}), {"v": 1, "health": "", "headline": "", "sentence": ""})
        self.assertEqual(rh.upgrade(None), {"v": 1, "health": "", "headline": "", "sentence": ""})
        self.assertEqual(rh.upgrade({"health": "nope", "headline": 4, "sentence": " a "}), {"v": 1, "health": "", "headline": "", "sentence": "a"})

    def test_words_are_trimmed_and_a_long_headline_is_kept(self):
        self.assertEqual(check({"v": 1, "headline": "  Plan holds  "}), {"v": 1, "headline": "Plan holds"})
        long = "x" * 5000
        self.assertEqual(check({"v": 1, "headline": long})["headline"], long)

    def test_bad_values_are_refused_in_plain_words_that_never_quote_them(self):
        for bad in (None, [], "text", {}, {"v": 2}, {"v": "1"}, {"v": 1, "health": "green"}, {"v": 1, "health": 3}, {"v": 1, "health": ["on_track"]},
                    {"v": 1, "headline": 5}, {"v": 1, "sentence": ["a"]}, {"v": 1, "extra": "secret-word"}, {"v": 1, "headline": "x" * rh.LIMIT}):
            with self.subTest(bad=bad), self.assertRaises(base.Bad) as got:
                check(bad)
            self.assertNotIn("secret-word", str(got.exception))
            self.assertNotIn("green", str(got.exception))

    def test_published_carries_every_field_and_leaves_an_empty_one_out(self):
        self.assertEqual(rh.published({"v": 1, "health": "on_track", "headline": "H"}, None),
                         {"content": {"health": "on_track", "headline": "H", "sentence": ""}})
        self.assertEqual(rh.published({"v": 1, "sentence": "S"}, None), {"content": {"health": "", "headline": "", "sentence": "S"}})
        self.assertIsNone(rh.published({"v": 1}, None))
        self.assertIsNone(rh.published("", None))


class Registered(unittest.TestCase):
    def test_it_is_in_the_registry_and_the_store(self):
        self.assertIs(section_kinds.REGISTRY["reportheadline"], rh)
        self.assertIn("reportheadline", store_module.SECTION_TYPES)
        self.assertIs(section_bodies.CHECKERS["reportheadline"], rh.check)
        self.assertEqual(section_bodies.EMPTY["reportheadline"], "")

    def test_step_27_lets_an_older_file_keep_the_type_and_a_second_run_changes_nothing(self):
        con = sqlite3.connect(":memory:")
        con.execute(store_module.REPORT_SECTIONS_WITH_GANTT_TABLE.replace("CREATE TABLE IF NOT EXISTS report_sections (", "CREATE TABLE report_sections (", 1)
                    .replace("  project TEXT NOT NULL REFERENCES projects(code) ON DELETE CASCADE,", "  project TEXT NOT NULL,"))
        con.execute("INSERT INTO report_sections VALUES ('ABC','s1','callout','T','b',0,0,1)")
        with self.assertRaises(sqlite3.IntegrityError):
            con.execute("INSERT INTO report_sections VALUES ('ABC','s2','reportheadline','T','',0,0,2)")
        store_module.migrate_report_headline_section_type(con)
        con.execute("INSERT INTO report_sections VALUES ('ABC','s2','reportheadline','T','',0,0,2)")
        self.assertEqual([r[0] for r in con.execute("SELECT id FROM report_sections ORDER BY sort_order")], ["s1", "s2"])
        store_module.migrate_report_headline_section_type(con)
        self.assertEqual(con.execute("SELECT count(*) FROM report_sections").fetchone()[0], 2)


if __name__ == "__main__":
    unittest.main()
