"""Row 1366: the ask index (<data>/ask-index/<code>.db and its -wal/-shm/-journal) is a private, rebuildable copy of folder text. It must never
travel with a backup, its copy folder or a publication, and it goes when its project goes. Each real pickup path of the data folder is tried.
Run: python3 dev/run_tests.py test_ask_index_pickup_1366"""
import os
import unittest
from pathlib import Path

from _paths import SRC  # noqa: F401
from test_backup_copy import Rig
from test_demo_seed import NO_ONEDRIVE, fresh_folder, opened
from clark import backup, demo_seed, platform as pl, published_copies

MARK = b"zqindexsecretmark"


def plant(data, code="ABC"):
    """An index file with its sidecars, holding a mark that must not be found anywhere else."""
    folder = Path(data) / "ask-index"
    folder.mkdir(mode=0o700, exist_ok=True)
    made = []
    for suffix in ("", "-wal", "-shm", "-journal"):
        p = Path(str(folder / f"{code}.db") + suffix)
        p.write_bytes(MARK + b" some passage text")
        made.append(p)
    return made


def holds_mark(folder):
    for dirpath, _d, files in os.walk(folder):
        for n in files:
            if MARK in (Path(dirpath) / n).read_bytes():
                return str(Path(dirpath) / n)
    return None


class Backups(Rig):
    def test_a_backup_holds_the_database_only_not_the_index(self):
        plant(self.data)
        made = backup.take(self.s, "undo")
        self.assertEqual(self.names(made.parent), [made.name])
        self.assertIsNone(holds_mark(made.parent))

    def test_the_copy_folder_gets_the_backup_and_kept_publications_only(self):
        self.on()
        plant(self.data)
        made = backup.take(self.s, "undo")
        self.assertEqual(self.names(self.copy), [made.name])
        self.assertIsNone(holds_mark(self.copy))

    def test_a_kept_publication_copy_never_takes_the_index_file_even_under_a_kept_name(self):
        self.on()
        plant(self.data)
        kept = published_copies.folder_of(self.data)
        kept.mkdir(exist_ok=True)
        (kept / "ABC-1.html").write_bytes(b"<html></html>")
        backup.take(self.s, "undo")
        self.assertEqual(self.names(self.copy / "published-copies"), ["ABC-1.html"])
        self.assertIsNone(holds_mark(self.copy))

    def test_the_data_folder_is_never_a_folder_that_may_be_synced(self):
        """A data folder inside OneDrive (or another synced place) is refused outright, so the index inside it is never uploaded."""
        with self.assertRaises(pl.PlatformError):
            pl.check_data_dir(self.data / "ask-index", [self.data])


class Project(unittest.TestCase):
    def test_removing_the_demo_projects_removes_their_index_files_and_leaves_another_projects(self):
        folder = fresh_folder(self)
        s = opened(folder)
        self.addCleanup(s.close)
        codes = [r["code"] for r in s.read("projects")]
        self.assertTrue(codes)
        for c in codes:
            plant(folder, c)
        plant(folder, "KEEP")
        self.assertEqual(demo_seed.remove(s), len(codes))
        left = sorted(p.name for p in (folder / "ask-index").iterdir())
        self.assertEqual(left, ["KEEP.db", "KEEP.db-journal", "KEEP.db-shm", "KEEP.db-wal"])

    def test_a_project_left_with_no_folder_loses_its_index_and_sidecars(self):
        from clark import ask_index
        folder = fresh_folder(self)
        plant(folder, "ABC")
        ask_index.refresh(folder, "ABC", [], None)
        self.assertEqual(list((folder / "ask-index").iterdir()), [])


class Publishing(unittest.TestCase):
    def test_nothing_that_writes_a_publication_or_export_lists_the_data_folder(self):
        """Publication, PDF and Word output are built from store rows and written to the client's folder; none walks clark's data folder.
        (publish_flow.py:465 and publish_pdf.py:305 also refuse a destination inside it.)"""
        import re
        src = Path(SRC) / "clark"
        for name in ("publish.py", "publish_flow.py", "publish_pdf.py", "to_client.py", "word_route.py", "excel_route.py", "published_copies.py"):
            text = (src / name).read_text(encoding="utf-8")
            self.assertNotRegex(text, r"ask-index|ask_index", name)
            for call in re.findall(r"(?:os\.walk|rglob|iterdir|scandir|listdir|glob)\(([^)]*)\)", text):
                self.assertNotRegex(call, r"data_dir|data\b", (name, call))


if __name__ == "__main__":
    unittest.main()
