"""Row 1366: the index of a project's documents (src/clark/ask_index.py, planned). Tests written FIRST from ~/ag/v13/tests-plan-1366.md
(numbers in the test names are the plan's). Only plan rows that do not wait on an open question are here: plan 1, 2, 3, 5, 8, 9,
10, 11, 12, 13, 15. Seam names are the plan's guesses; every call goes through the small adapter `ix` below, so a rename is one edit.

Run: python3 dev/run_tests.py test_ask_index_1366
Every file is made in the test from made-up text.
"""
import os
import shutil
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC

import test_docx_read as tdx
from clark import reach

FAKE_KEY = "password = " + "hunter2" * 3


class ix:
    """The seams (plan names, not final): build(data_dir, code, folders), refresh(same), search(data_dir, code, question) -> list of
    (label, text), status(data_dir, code, folders) -> dict of counts, path_for(data_dir, code)."""

    @staticmethod
    def mod():
        from clark import ask_index
        return ask_index

    @classmethod
    def build(cls, data, code, folders):
        return cls.mod().build(data, code, folders)

    @classmethod
    def refresh(cls, data, code, folders):
        return cls.mod().refresh(data, code, folders)

    @classmethod
    def search(cls, data, code, question):
        return [(p.label, p.text) if hasattr(p, "label") else tuple(p[:2]) for p in cls.mod().search(data, code, question)]

    @classmethod
    def status(cls, data, code, folders):
        return cls.mod().status(data, code, folders)

    @classmethod
    def path_for(cls, data, code):
        return Path(cls.mod().path_for(data, code))


class Base(unittest.TestCase):
    def setUp(self):
        patch = mock.patch.object(reach.platform, "system", return_value=reach.platform.MAC)
        patch.start()
        self.addCleanup(patch.stop)
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.data, self.box = self.d / "data", self.d / "saved"
        self.data.mkdir()
        self.box.mkdir()

    def put(self, name, text, binary=False, folder=None, mtime=None):
        p = Path(folder or self.box) / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(text if binary else text.encode())
        if mtime:
            os.utime(p, (mtime, mtime))
        return p

    def build(self, code="P1", folders=None):
        folders = folders or [self.box]
        ix.build(self.data, code, folders)
        return folders

    def found(self, word, code="P1"):
        return ix.search(self.data, code, word)


class Fixture(Base):
    def test_1_each_readable_type_is_found(self):
        self.put("notes.txt", "zqtxtalpha only here")
        self.put("readme.md", "zqmdbeta only here")
        self.put("table.csv", "owner,due\nzqcsvgamma,24-11")
        self.put("letter.docx", tdx.docx(tdx.P("zqdocxdelta only here")), binary=True)
        self.build()
        for word in ("zqtxtalpha", "zqmdbeta", "zqcsvgamma", "zqdocxdelta"):
            self.assertTrue(self.found(word), word)

    def test_2_counts_add_up_and_each_file_has_one_reason(self):
        self.put("a.txt", "zqone")
        self.put("b.md", "zqtwo")
        self.put("c.bin", b"\x89BIN", binary=True)
        self.put("d.js", "var x")
        self.put("prod.env", "K=1")
        self.put("keys.txt", FAKE_KEY)
        self.build()
        s = ix.status(self.data, "P1", [self.box])
        names = ("indexed", "type", "online_only", "too_long", "safety", "not_yet")
        self.assertEqual(sum(s[n] for n in names if n in s), 6, s)
        self.assertEqual(s["indexed"], 2)
        self.assertGreaterEqual(s["safety"], 2)

    def test_3_301_files_all_searchable(self):
        for i in range(301):
            self.put(f"f{i:03d}.txt", f"zqfile{i:03d}word")
        self.build()
        self.assertTrue(self.found("zqfile300word"), "the file past MAX_FILES_READ (300) is found")
        self.assertTrue(self.found("zqfile000word"))

    def test_5_question_time_reads_no_file(self):
        self.put("a.txt", "zqquiet only here")
        self.build()
        with mock.patch.object(reach, "read_bytes", side_effect=AssertionError("a question read a file")):
            self.assertTrue(self.found("zqquiet"))

    def test_15_newer_version_ranks_first_and_label_has_date(self):
        old, new = 1794268800, 1794700800        # 10-11-2026 and 15-11-2026 00:00 UTC
        self.put("SoW v1.5.txt", "zqscope the supplier delivers the report", mtime=old)
        self.put("SoW v1.6.txt", "zqscope the supplier delivers the report", mtime=new)
        self.build()
        got = self.found("zqscope")
        self.assertEqual(len(got), 2)
        self.assertIn("v1.6", got[0][0])
        self.assertIn("2026-11-15" if "2026-11-15" in got[0][0] else "15-11-2026", got[0][0])


class Files(Base):
    def test_8_one_private_file_per_project_outside_folders_and_clark_db(self):
        self.put("a.txt", "zqone")
        self.build()
        p = ix.path_for(self.data, "P1")
        self.assertTrue(p.is_file())
        self.assertEqual(p.parent, self.data / "ask-index")
        self.assertEqual(p.suffix, ".db")
        self.assertEqual(stat.S_IMODE(p.stat().st_mode), 0o600)
        self.assertNotEqual(p.name, "clark.db")
        self.assertFalse(str(p).startswith(str(self.box)))

    def test_9_two_projects_one_folder_two_files_two_builds(self):
        self.put("a.txt", "zqshared")
        self.build("P1")
        self.build("P2")
        a, b = ix.path_for(self.data, "P1"), ix.path_for(self.data, "P2")
        self.assertNotEqual(a, b)
        self.assertTrue(a.is_file() and b.is_file())

    def test_10_refresh_reads_only_what_changed(self):
        a = self.put("a.txt", "zqkeep one")
        b = self.put("b.txt", "zqchange one")
        c = self.put("c.txt", "zqgone one")
        self.build()
        real, opened = reach.read_bytes, []
        def spy(p, *x, **k):
            opened.append(os.path.basename(str(p)))
            return real(p, *x, **k)
        b.write_bytes(b"zqchanged two longer")
        c.unlink()
        with mock.patch.object(reach, "read_bytes", side_effect=spy):
            ix.refresh(self.data, "P1", [self.box])
        self.assertEqual(opened, ["b.txt"])
        self.assertTrue(self.found("zqchanged"))
        self.assertFalse(self.found("zqgone"))
        self.assertTrue(self.found("zqkeep"))

    def test_11_a_file_taken_away_leaves_no_text_in_the_db(self):
        a = self.put("a.txt", "zquniqueword here")
        self.put("b.txt", "zqother")
        self.build()
        a.unlink()                                  # OneDrive removed the local copy
        ix.refresh(self.data, "P1", [self.box])
        self.assertFalse(self.found("zquniqueword"))
        raw = ix.path_for(self.data, "P1").read_bytes()
        self.assertNotIn(b"zquniqueword", raw)

    def test_12_rebuild_gives_the_same_passages_and_removing_folders_drops_text(self):
        self.put("a.txt", "zqsame alpha\nzqsame beta")
        self.build()
        first = self.found("zqsame")
        ix.path_for(self.data, "P1").unlink()
        self.build()
        self.assertEqual(self.found("zqsame"), first)
        ix.refresh(self.data, "P1", [])             # the project has no folder left
        self.assertFalse(self.found("zqsame"))

    def test_13_a_secret_is_never_stored(self):
        self.put("keys.txt", "line one zqnote\n" + FAKE_KEY)
        self.put("prod.env", "ZQENVVALUE=1")
        self.put("ok.txt", "zqfine")
        self.build()
        raw = ix.path_for(self.data, "P1").read_bytes()
        for bad in (b"hunter2", b"ZQENVVALUE", b"zqnote"):
            self.assertNotIn(bad, raw)
        self.assertTrue(self.found("zqfine"))
        self.assertGreaterEqual(ix.status(self.data, "P1", [self.box])["safety"], 2)


class Row1537(Base):
    """Row 1537: the parts of row 1366 that were missing. Every file is made in the test from made-up text."""

    def state(self, name):
        from clark import ask_index
        return ask_index._open_read(self.data, "P1").execute("SELECT state FROM files WHERE label LIKE ?", (f"%{name}",)).fetchone()[0]

    def test_excel_over_row_cell_cap_counted_too_long_not_indexed(self):
        from clark import ask_index
        from test_ask_index_types_1366 import xlsx
        rows = [["item", "owner"]] + [[f"t{i}", f"zqrow{i}"] for i in range(10)]
        cells = [[f"zqa{i}", f"b{i}", f"c{i}"] for i in range(10)]
        self.put("rows.xlsx", xlsx({"Plan": rows}), binary=True)
        self.put("cells.xlsx", xlsx({"One": cells, "Two": [["zqsecondsheet", "x", "y"]]}), binary=True)
        self.put("small.xlsx", xlsx({"S": [["zqsmall", "x"]]}), binary=True)
        with mock.patch.object(ask_index, "MAX_EXCEL_ROWS", 5), mock.patch.object(ask_index, "MAX_EXCEL_CELLS", 12):
            self.build()
        for word in ("zqrow0", "zqrow1", "zqa0", "zqa1", "zqsecondsheet"):
            self.assertFalse(self.found(word), word)           # nothing of a workbook over a cap is indexed, not even its first rows
        self.assertTrue(self.found("zqsmall"))
        s = ix.status(self.data, "P1", [self.box])
        self.assertEqual((s["indexed"], s["too_long"], s["type"]), (1, 2, 0))
        self.assertEqual(self.state("rows.xlsx"), "too_long")
        self.assertEqual(self.state("cells.xlsx"), "too_long")
        left = dict(ask_index.files_left_out(self.data, "P1", 200)["files"])
        self.assertEqual(left, {"saved/rows.xlsx": ask_index.REASON_TOO_LONG, "saved/cells.xlsx": ask_index.REASON_TOO_LONG})

    def test_excel_exactly_at_the_row_and_cell_cap_is_indexed(self):
        from clark import ask_index
        from test_ask_index_types_1366 import xlsx
        self.put("edge.xlsx", xlsx({"S": [[f"zqedge{i}", "v"] for i in range(4)]}), binary=True)
        with mock.patch.object(ask_index, "MAX_EXCEL_ROWS", 4), mock.patch.object(ask_index, "MAX_EXCEL_CELLS", 8):
            self.build()
        self.assertTrue(self.found("zqedge3"))
        self.assertEqual(ix.status(self.data, "P1", [self.box])["too_long"], 0)

    def test_followup_terms_find_item_file_passage(self):
        self.put("owners.txt", "ABC-12 is owned by zqdana from the supplier team")
        self.put("other.txt", "ABC-99 is owned by zqomar and the ticket count is 12")
        self.build()
        from clark import ask_index
        self.assertFalse(self.found("zzfollow zzup"), "the question alone names no item")
        got = ask_index.search(self.data, "P1", "zzfollow zzup", extra=["ABC-12"])
        self.assertEqual([p.text for p in got if "zqdana" in p.text and "zqomar" not in p.text], [p.text for p in got][:1])
        self.assertTrue(any("zqdana" in p.text for p in got))
        # the phrase "ABC 12" must be adjacent: ABC-99 with a 12 elsewhere in its text is not the item
        self.assertFalse(any("zqomar" in p.text for p in ask_index.search(self.data, "P1", "zzzz", extra=["ABC-12"])))
        # an id in the question itself is found the same way; the 40-word cap never cuts the extra terms
        filler = " ".join(f"zzf{i}" for i in range(45))
        self.assertTrue(any("zqdana" in p.text for p in ask_index.search(self.data, "P1", filler, extra=["ABC-12"])))
        self.assertTrue(any("zqdana" in p.text for p in ask_index.search(self.data, "P1", "who owns ABC-12")))

    def test_an_id_such_as_a_dash_12_is_found_by_the_fts5_query(self):
        self.put("a.txt", "the item A-12 is late")
        self.put("b.txt", "the item A-99 is late and has 12 users")
        self.build()
        from clark import ask_index
        got = ask_index.search(self.data, "P1", "zzzz", extra=["A-12"])
        self.assertEqual(len(got), 1, got)
        self.assertIn("A-12", got[0].text)

    def test_oserror_on_file_3_does_not_reread_files_1_2(self):
        from clark import ask_index
        for n in (1, 2, 3, 4):
            self.put(f"f{n}.txt", f"zqfile{n} text")
        reads, fail = {}, {"on": True}
        real = reach.read_bytes

        def counting(path, *a, **k):
            name = Path(path).name
            reads[name] = reads.get(name, 0) + 1
            if name == "f3.txt" and fail["on"]:
                raise OSError("read error")
            return real(path, *a, **k)
        with mock.patch.object(reach, "read_bytes", counting):
            with self.assertRaises(OSError):
                ask_index.refresh(self.data, "P1", [self.box])        # the Indexer's worker catches this and the run is left not current
            self.assertFalse(ask_index.current(self.data, "P1", [self.box]))
            fail["on"] = False
            self.assertTrue(ask_index.refresh(self.data, "P1", [self.box]))      # the next try (resume) carries on
        self.assertEqual((reads["f1.txt"], reads["f2.txt"]), (1, 1), reads)
        self.assertEqual(reads["f3.txt"], 2)
        self.assertEqual(reads["f4.txt"], 1)
        self.assertTrue(ask_index.current(self.data, "P1", [self.box]))
        for n in (1, 2, 3, 4):
            self.assertTrue(self.found(f"zqfile{n}"), n)

    def test_online_only_not_opened_and_line_says_not_searched(self):
        from clark import ask_index
        self.put("here.txt", "zqhere text")
        self.put("cloud.txt", "zqcloud " + "x" * 29)
        reads = []
        real, real_read = reach.online_only_stat, reach.read_bytes

        def counting(path, *a, **k):
            reads.append(Path(path).name)
            return real_read(path, *a, **k)
        with mock.patch.object(reach, "online_only_stat", side_effect=lambda st: st.st_size == 37 or real(st)), mock.patch.object(reach, "read_bytes", counting):
            self.build()
        self.assertIn("here.txt", reads)
        self.assertNotIn("cloud.txt", reads, "an online-only file is never opened")
        self.assertFalse(self.found("zqcloud"))
        self.assertEqual(ix.status(self.data, "P1", [self.box])["online_only"], 1)
        line = ask_index.line_for(ix.status(self.data, "P1", [self.box]))
        self.assertEqual(line, "Indexed 1 of 2 files. Online-only files not searched")
        self.assertEqual(ask_index.line_for({"indexed": 1, "online_only": 8}), "Indexed 1 of 9 files. Online-only files not searched", "no count in front")
        self.assertEqual(ask_index.left_out_line("online_only", 8), "Online-only files not searched")
        self.assertEqual(ask_index.left_out_line("online_only", 1), "Online-only files not searched")
        left = ask_index.folder_status(self.data, "P1", [str(self.box)])[str(self.box)]["left"]
        self.assertEqual(left["online_only"], "Online-only files not searched")
        none = {"indexed": 1}
        self.assertNotIn("Online-only", ask_index.line_for(none))

    def test_first_run_card_and_help_state_passages_go_to_claude(self):
        import json
        page = SRC / "clark" / "page" / "src"
        words = (page / "edit" / "askWords.js").read_text(encoding="utf-8")
        panel = (page / "edit" / "AskPanel.jsx").read_text(encoding="utf-8")
        six = "Passages from the folders you list go to Claude, which Anthropic runs, only when they contain words from your question."
        ten = "On a Mac, text in PNG and JPG pictures is read on this Mac and never sent out."
        self.assertIn(f'export const CARD_PASSAGES = "{six} {ten}";', words)
        classic = panel.split("{classic ? (<>")[1].split(") : (<>")[0]
        self.assertIn("W.named(W.CARD_PASSAGES, askProvider.value)", classic)       # Classic only: the Cards branch keeps its three lines
        self.assertNotIn("CARD_PASSAGES", panel.split(") : (<>")[1])
        help_text = json.dumps(json.loads((page / "help" / "helpContent.json").read_text(encoding="utf-8")), ensure_ascii=False)
        self.assertIn(six, help_text)
        self.assertIn(ten, help_text)

    def test_fixture_library_has_no_client_names(self):
        """The fixture library is made in the test files of row 1366 (the file names, the words in the files, the comments). None holds a name on the
        repo's banned list (tests/test_no_real_names.py, hashes only)."""
        import test_no_real_names as names
        here = Path(__file__).resolve().parent
        sources = sorted(here.glob("test_ask_index_*1366.py")) + sorted(here.glob("test_ask_vision_*1366.py")) + [here / "test_docx_read.py"]
        self.assertGreaterEqual(len(sources), 10)
        hits = []
        for f in sources:
            hits += names.text_hits(f.name, f.read_text(encoding="utf-8"), names.BANNED)
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
