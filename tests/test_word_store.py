"""#48 (guarded store change, Head rulings Q2 and Q4): the `word` route and the Word row of `publications`. Fictional data."""
import re
import sqlite3
import unittest
from pathlib import Path

from _demo import DemoStore, USER
from _paths import SRC
from clark import store as store_module
from clark.store import Invalid


class WordRoute(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store

    def test_the_schema_check_and_the_store_list_name_the_same_routes(self):
        text = (SRC / "clark" / "schema.sql").read_text(encoding="utf-8")
        listed = re.search(r"route\s+TEXT NOT NULL CHECK \(route IN \(([^)]*)\)\)", text).group(1)
        self.assertEqual(tuple(re.findall(r"'([a-z]+)'", listed)), store_module.ROUTES)
        self.assertIn("word", store_module.ROUTES)

    def test_a_step_by_the_word_route_is_recorded_with_its_route_and_its_source(self):
        with self.store.step("word", USER, src_ref="Added from Word (plan.docx)") as st:
            ref = st.create("actions", {"project": "ABC", "description": "Book the room", "raised": "2026-10-01",
                                        "source": "Word import", "client_visible": 0})
        rows = self.store.con.execute("SELECT route, place, src_ref FROM item_events WHERE item_id = ?", (ref,)).fetchall()
        self.assertTrue(rows)
        self.assertEqual({(r["route"], r["place"], r["src_ref"]) for r in rows}, {("word", None, "Added from Word (plan.docx)")})

    def test_an_unknown_route_is_still_refused_by_the_store_and_by_the_schema(self):
        with self.assertRaises(Invalid):
            self.store.step("email", USER).__enter__()
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.con.execute("INSERT INTO item_events (at, item_id, kind, route, actor) VALUES ('x', 'ABC-A-001', 'change', 'wordy', 'you')")


class WordPublication(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store
        self.path = Path(self.demo.dir) / "ABC-report-2026-10-28.docx"

    def rows(self):
        return [dict(r) for r in self.store.con.execute("SELECT * FROM publications ORDER BY seq")]

    def test_a_word_row_has_word_1_and_its_own_sha256(self):
        seq = self.store.log_publication("ABC", self.path, "2026-10-23", "b" * 64, USER, word=1)
        row = self.rows()[0]
        self.assertEqual((row["seq"], row["word"], row["file_sha256"], row["client_path"], row["checks"], row["by_user"]),
                         (seq, 1, "b" * 64, None, "not needed", USER))

    def test_the_default_is_still_a_web_page_row_and_a_client_copy_is_recorded_when_given(self):
        self.store.log_publication("ABC", self.path.with_suffix(".html"), None, "a" * 64, USER)
        client = Path(self.demo.dir) / "client" / "x.docx"
        self.store.log_publication("ABC", self.path, None, "b" * 64, USER, word=1, client_path=client)
        first, second = self.rows()
        self.assertEqual((first["word"], first["client_path"]), (0, None))
        self.assertEqual((second["word"], second["client_path"]), (1, str(client)))

    def test_bad_word_or_client_path_is_refused_and_nothing_is_recorded(self):
        for kw, words in (({"word": 2}, "word must be 0 or 1"), ({"word": True}, "word must be 0 or 1"), ({"word": "1"}, "word must be 0 or 1"),
                          ({"word": 1, "client_path": "x.docx"}, "client copy")):
            with self.subTest(kw=kw), self.assertRaisesRegex(Invalid, words):
                self.store.log_publication("ABC", self.path, None, "b" * 64, USER, **kw)
        self.assertEqual(self.rows(), [])

    def test_a_word_row_makes_no_step_and_no_change_log_row(self):
        before = self.store.con.execute("SELECT count(*) FROM change_log").fetchone()[0]
        self.store.log_publication("ABC", self.path, None, "b" * 64, USER, word=1)
        self.assertEqual(self.store.con.execute("SELECT count(*) FROM change_log").fetchone()[0], before)


if __name__ == "__main__":
    unittest.main()
