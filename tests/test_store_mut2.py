"""Mutation-check tests for the guarded src/clark/store.py (second pass, after schema step 21): each test kills a hand-made mutant
that the existing tests let survive (a dropped gap check in migration_plan, the restore of a project's `active` flag and its
children guard, the publication number and Word-sharing guards, the SHA-256 shape, the order of what an undo skips). Fictional data only.

Run: python3 dev/run_tests.py test_store_mut2
"""
import unittest
from pathlib import Path
from unittest import mock

from _demo import USER, DemoStore
from clark import store as store_module
from clark.store import Invalid, NumberTaken

SHA = "a" * 64
LOCAL = Path("/tmp/clark-fictional/local/ABC-report-2026-10-23.html")
WORD = Path("/tmp/clark-fictional/local/ABC-report-2026-10-23.docx")


class MigrationPlan(unittest.TestCase):
    def test_a_table_with_a_gap_that_still_ends_at_the_latest_version_is_refused(self):
        def noop(con):
            pass
        gap = ((2, noop), (store_module.SCHEMA_VERSION, noop))
        with self.assertRaises(Invalid) as e:
            store_module.migration_plan(1, gap)
        self.assertIn("missing a step", str(e.exception))

    def test_a_table_that_does_not_start_at_2_is_refused(self):
        def noop(con):
            pass
        table = tuple((n, noop) for n in range(3, store_module.SCHEMA_VERSION + 1))
        with self.assertRaises(Invalid):
            store_module.migration_plan(1, table)


class RestoreProject(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.s = self.demo.store
        self.a1 = self.demo.action()
        self.a2 = self.demo.action(description="Second")

    def tearDown(self):
        self.demo.close()

    def archive(self):
        with self.s.step("dashboard", USER) as st:
            st.archive("projects", "ABC")
        return self.demo.last_step()

    def restore(self):
        with self.s.step("dashboard", USER) as st:
            st.restore("projects", "ABC")
            self.result = st.result

    def project(self):
        return self.s.read("projects", ref="ABC")

    def test_the_logged_old_active_value_is_what_comes_back(self):
        step = self.archive()
        self.s.con.execute("UPDATE change_log SET old_value = '0' WHERE apply_id = ? AND tbl = 'projects' AND field = 'active'", (step,))
        self.restore()
        self.assertEqual((self.project()["archived"], self.project()["active"]), (0, 0))

    def test_an_old_active_value_that_is_not_0_or_1_is_ignored_not_fatal(self):
        step = self.archive()
        self.s.con.execute("UPDATE change_log SET old_value = 'x' WHERE apply_id = ? AND tbl = 'projects' AND field = 'active'", (step,))
        self.restore()
        self.assertEqual(self.project()["archived"], 0)

    def test_a_child_that_is_not_archived_any_more_is_not_restored_or_counted(self):
        self.archive()
        self.s.con.execute("UPDATE actions SET archived = 0 WHERE id = ?", (self.a1,))
        self.restore()
        self.assertEqual(self.result["counts"]["actions"], 1)
        self.assertEqual(sum(r["archived"] for r in self.s.read("actions", "ABC")), 0)


class PublicationGuards(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.s = self.demo.store

    def tearDown(self):
        self.demo.close()

    def count(self):
        return self.s.con.execute("SELECT count(*) FROM publications").fetchone()[0]

    def test_a_number_ahead_of_the_next_one_is_refused_and_nothing_is_written(self):
        with self.assertRaises(NumberTaken):
            self.s.log_publication("ABC", LOCAL, "2026-10-23", SHA, USER, number=2)
        self.assertEqual(self.count(), 0)
        self.s.log_publication("ABC", LOCAL, "2026-10-23", SHA, USER)
        with self.assertRaises(NumberTaken):
            self.s.log_publication("ABC", LOCAL, "2026-10-23", SHA, USER, number=3)
        with self.assertRaises(NumberTaken):
            self.s.log_publication("ABC", LOCAL, "2026-10-23", SHA, USER, number=1)
        self.assertEqual(self.count(), 1)

    def test_the_number_must_be_a_real_int(self):
        with self.assertRaises(NumberTaken):
            self.s.log_publication("ABC", LOCAL, "2026-10-23", SHA, USER, number=True)
        with self.assertRaises(NumberTaken):
            self.s.log_publication("ABC", LOCAL, "2026-10-23", SHA, USER, number="1")
        self.assertEqual(self.count(), 0)
        self.s.log_publication("ABC", LOCAL, "2026-10-23", SHA, USER, number=1)
        self.assertEqual(self.count(), 1)

    def test_the_next_number_is_one_then_one_more_than_the_highest(self):
        self.assertEqual(self.s.next_publication("ABC"), 1)
        seq = self.s.log_publication("ABC", LOCAL, "2026-10-23", SHA, USER)
        self.assertEqual(self.s.number_of(seq), 1)
        self.assertEqual(self.s.next_publication("ABC"), 2)
        seq2 = self.s.log_publication("ABC", LOCAL, "2026-10-23", SHA, USER)
        self.assertEqual(self.s.number_of(seq2), 2)

    def test_a_word_file_cannot_share_the_number_of_a_word_file(self):
        page = self.s.log_publication("ABC", LOCAL, "2026-10-23", SHA, USER)
        word = self.s.log_publication("ABC", WORD, "2026-10-23", "b" * 64, USER, word=1, same_as=page)
        self.assertEqual(self.s.number_of(word), 1)
        with self.assertRaises(Invalid):
            self.s.log_publication("ABC", WORD, "2026-10-23", "c" * 64, USER, word=1, same_as=word)
        self.assertEqual(self.count(), 2)

    def test_same_as_is_for_a_word_file_alone_and_never_with_a_number(self):
        page = self.s.log_publication("ABC", LOCAL, "2026-10-23", SHA, USER)
        with self.assertRaises(Invalid):
            self.s.log_publication("ABC", LOCAL, "2026-10-23", SHA, USER, word=0, same_as=page)
        with self.assertRaises(Invalid):
            self.s.log_publication("ABC", WORD, "2026-10-23", SHA, USER, word=1, same_as=page, number=1)
        with self.assertRaises(Invalid):
            self.s.log_publication("ABC", WORD, "2026-10-23", SHA, USER, word=1, same_as="1")
        self.assertEqual(self.count(), 1)

    def test_a_publication_needs_a_publisher_that_is_not_blank(self):
        for bad in ("", "   ", None):
            with self.subTest(bad=bad), self.assertRaises(Invalid):
                self.s.log_publication("ABC", LOCAL, "2026-10-23", SHA, bad)
        self.assertEqual(self.count(), 0)
        self.s.log_publication("ABC", LOCAL, "2026-10-23", SHA, "  " + USER + "  ")
        self.assertEqual(self.s.con.execute("SELECT by_user FROM publications").fetchone()[0], USER)

    def test_only_a_web_page_has_a_copy_kept(self):
        with mock.patch.object(type(self.s), "keep_copy", return_value=True) as kept:
            page = self.s.log_publication("ABC", LOCAL, "2026-10-23", SHA, USER)
            self.assertEqual(kept.call_count, 1)
            self.s.log_publication("ABC", WORD, "2026-10-23", "b" * 64, USER, word=1, same_as=page)
            self.assertEqual(kept.call_count, 1, "a Word file has no page to keep")

    def test_the_sha_256_must_be_exactly_64_lowercase_hex_digits(self):
        for bad in ("a" * 63, "a" * 65, "A" * 64, "g" * 64, "", None, "a" * 8):
            with self.subTest(bad=bad), self.assertRaises(Invalid):
                self.s.log_publication("ABC", LOCAL, "2026-10-23", bad, USER)
        self.assertEqual(self.count(), 0)


class RevertPlanOrder(unittest.TestCase):
    def test_rows_that_cannot_be_put_back_are_named_newest_first(self):
        demo = DemoStore()
        self.addCleanup(demo.close)
        rows = [{"rowid": n, "tbl": "not_a_table", "item_id": f"X-{n}", "field": "f", "op": "update", "via": None,
                 "apply_id": 1} for n in (1, 2, 3)]
        done, skipped = store_module.revert_plan(demo.store.con, rows, None, False)
        self.assertEqual(done, [])
        self.assertEqual([s["rowid"] for s in skipped], [3, 2, 1])
        self.assertTrue(all(s["why"] == "can't be undone" for s in skipped))


if __name__ == "__main__":
    unittest.main()
