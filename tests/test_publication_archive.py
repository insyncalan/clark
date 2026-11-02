"""#342: an old published report can be archived, never deleted (guarded: store.py, changes.py, schema.sql, past_reports.py).
Fictional data only; no browser.

Archive is a flag on the publication's row and nothing else: the kept file and the row's SHA-256 are never touched. It goes through
the store's one writer (one step, one Undo), hides the report from the Published reports list, and is counted, not named. A
published report cannot be added, edited, cancelled or deleted through the writer, and a kept copy cannot be written to.

Run: python3 dev/run_tests.py test_publication_archive
"""
import hashlib
import json
import sqlite3
import unittest
from pathlib import Path

import _paths  # noqa: F401
from _demo import USER
from clark import changes, past_reports, published_copies
from clark.store import Invalid, SCHEMA_VERSION, connect, migration_plan
from test_past_reports import Base, SHA

OTHER = "b" * 64


def sha(data):
    return hashlib.sha256(data).hexdigest()


class ArchiveHides(Base):
    def setUp(self):
        super().setUp()
        self.past = past_reports.PastReports(self.db)
        self.change = changes.make_change(self.store.path, [], USER)
        self.undo = changes.make_undo(self.store.path, [], USER)

    def archive(self, number, op="archive"):
        return self.change({"project": "PUB", "kind": "publications", "op": op, "id": f"PUB|{number}"})

    def listed(self):
        return [p["number"] for p in self.past.listing("PUB")[1]["publications"]]

    def snapshot(self, number):
        row = self.store.con.execute("SELECT * FROM publications WHERE project = 'PUB' AND number = ?", (number,)).fetchone()
        kept = self.copies / f"PUB-{number}.html"
        return {k: row[k] for k in row.keys() if k != "archived"}, sha(kept.read_bytes()), kept.stat().st_mtime_ns

    def test_archive_hides_one_from_the_list_and_deletes_nothing(self):
        first, body1 = self.publish()
        second, body2 = self.publish(now="2026-11-02")
        before = self.snapshot(1)
        status, reply = self.archive(1)
        self.assertEqual((status, reply["ok"], reply["archived"]), (200, True, 1), reply)
        self.assertEqual(self.listed(), [2], "the archived one is not in the list")
        listing = self.past.listing("PUB")[1]
        self.assertEqual((listing["total"], listing["archived"]), (1, 1))
        self.assertEqual(self.snapshot(1), before, "the row, the kept file's SHA-256 and the file itself are unchanged")
        self.assertEqual(before[1], first["sha256"])
        self.assertEqual((self.copies / "PUB-1.html").read_bytes(), body1)
        self.assertEqual(self.store.con.execute("SELECT count(*) FROM publications").fetchone()[0], 2, "no row is deleted")
        self.assertEqual(sorted(p.name for p in self.copies.iterdir()), ["PUB-1.html", "PUB-2.html"], "no file is deleted")
        self.assertEqual(self.past.visit("PUB", 1)[0], 200, "it is still kept and still opens")

    def test_the_second_publish_leaves_an_archived_first_unchanged(self):
        first, _ = self.publish()
        self.archive(1)
        before = self.snapshot(1)
        self.publish(now="2026-11-03")
        self.assertEqual(self.snapshot(1), before)
        self.assertEqual(self.listed(), [2])

    def test_one_step_with_one_undo_and_restore_shows_it_again(self):
        self.publish()
        self.publish(now="2026-11-02")
        steps = self.store.con.execute("SELECT count(*) FROM applies").fetchone()[0]
        status, reply = self.archive(2)
        self.assertEqual(self.store.con.execute("SELECT count(*) FROM applies").fetchone()[0], steps + 1, "one step")
        self.assertEqual(self.listed(), [1])
        status, back = self.undo({"project": "PUB", "apply_id": reply["apply_id"]})
        self.assertEqual(status, 200, back)
        self.assertEqual(self.listed(), [2, 1], "Undo shows it again")
        status, reply = self.archive(1)
        self.assertEqual(self.listed(), [2])
        self.assertEqual(self.archive(1)[0], 400, "already archived")
        self.assertEqual(self.archive(1, "restore")[0], 200)
        self.assertEqual(self.listed(), [2, 1])

    def test_the_reply_and_the_list_carry_no_path_or_hash(self):
        done, _ = self.publish()
        status, reply = self.archive(1)
        self.assertEqual(set(reply), {"ok", "apply_id", "ref", "archived"})
        text = json.dumps(reply) + json.dumps(self.past.listing("PUB")[1])
        for hidden in (str(self.root), str(self.data_dir), done["sha256"], ".html", "sha", "path"):
            self.assertNotIn(hidden, text)

    def test_a_request_may_not_archive_another_projects_report_or_a_missing_one(self):
        self.publish()
        before = self.store.con.execute("SELECT count(*) FROM applies").fetchone()[0]
        for ref in ("PUBX|1", "OTH|1", "PUB|9", "PUB|1;x", "1"):
            status, reply = self.change({"project": "PUB", "kind": "publications", "op": "archive", "id": ref})
            self.assertEqual((status, reply["ok"]), (400, False), ref)
        self.assertEqual(self.store.con.execute("SELECT count(*) FROM applies").fetchone()[0], before)
        self.assertEqual(self.listed(), [1])

    def test_no_field_is_taken_with_the_archive(self):
        self.publish()
        for extra in ({"changes": {"archived": 1}}, {"values": {"archived": 1}}, {"file_sha256": OTHER}, {"local_path": "/x"}):
            status, reply = self.change({"project": "PUB", "kind": "publications", "op": "archive", "id": "PUB|1", **extra})
            self.assertEqual((status, reply["ok"]), (400, False), extra)
        self.assertEqual(self.listed(), [1])


class NothingElseChanges(Base):
    def test_a_published_report_is_not_added_edited_cancelled_or_deleted_by_the_writer(self):
        done, _ = self.publish()
        before = self.store.con.execute("SELECT * FROM publications").fetchall()
        for op, item in (("new", {"values": {"project": "PUB", "week_ending": "2026-11-01", "local_path": "/x", "file_sha256": OTHER,
                                              "checks": "passed", "by_user": "x", "number": 9}}),
                         ("update", {"id": "PUB|1", "changes": {"file_sha256": OTHER}}),
                         ("update", {"id": "PUB|1", "changes": {"archived": 1}}),
                         ("cancel", {"id": "PUB|1"})):
            with self.assertRaises(Invalid, msg=op):
                with self.store.step("dashboard", USER) as st:
                    from clark.store import write_item
                    write_item(st.con, {"table": "publications", "op": op, **item}, st)
        self.assertEqual([tuple(r) for r in self.store.con.execute("SELECT * FROM publications")], [tuple(r) for r in before])

    def test_the_database_refuses_a_change_to_any_column_but_the_flag_and_any_delete(self):
        self.publish()
        con = self.store.con
        for column, value in (("file_sha256", OTHER), ("number", 5), ("local_path", "/x"), ("by_user", "y"), ("project", "PUB")):
            with self.assertRaises(sqlite3.DatabaseError, msg=column):
                con.execute(f"UPDATE publications SET {column} = ? WHERE number = 1", (value,))
        with self.assertRaises(sqlite3.DatabaseError):
            con.execute("DELETE FROM publications WHERE number = 1")
        with self.assertRaises(sqlite3.DatabaseError):
            con.execute("UPDATE publications SET archived = 2 WHERE number = 1")

    def test_a_write_to_a_kept_copy_is_refused_and_it_cannot_be_kept_again(self):
        done, body = self.publish()
        kept = self.copies / "PUB-1.html"
        with self.assertRaises(PermissionError):
            kept.write_bytes(b"changed")
        other = self.root / "other.html"
        other.write_bytes(b"<html>other</html>")
        self.assertFalse(published_copies.keep(self.data_dir, "PUB", 1, other, sha(b"<html>other</html>")))
        self.assertEqual(kept.read_bytes(), body)
        self.assertEqual(sha(kept.read_bytes()), done["sha256"])

    def test_an_archive_leaves_a_kept_copy_just_as_hard_to_write_to(self):
        self.publish()
        changes.make_change(self.store.path, [], USER)({"project": "PUB", "kind": "publications", "op": "archive", "id": "PUB|1"})
        with self.assertRaises(PermissionError):
            (self.copies / "PUB-1.html").write_bytes(b"changed")


class TheMigration(Base):
    def test_a_file_at_version_ten_gains_the_flag_with_every_row_kept(self):
        self.assertEqual(SCHEMA_VERSION, 11)
        self.assertEqual([n for n, _ in migration_plan(10)], [11])
        self.publish()
        self.publish(now="2026-11-02")
        path = self.root / "old.db"
        con = sqlite3.connect(str(path))
        con.execute("CREATE TABLE publications (seq INTEGER PRIMARY KEY, project TEXT, number INTEGER, file_sha256 TEXT)")
        con.execute("INSERT INTO publications VALUES (1, 'PUB', 1, ?)", (SHA,))
        from clark.store import migrate_publication_archive
        migrate_publication_archive(con)
        migrate_publication_archive(con)                 # a second run changes nothing
        self.assertEqual(con.execute("SELECT seq, number, file_sha256, archived FROM publications").fetchall(), [(1, 1, SHA, 0)])
        con.close()


if __name__ == "__main__":
    unittest.main()
