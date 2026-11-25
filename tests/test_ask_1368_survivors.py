"""Row 1368: one test per survivor of the hand mutation sweep (each fails when its mutant is applied).
Run: python3 dev/run_tests.py test_ask_1368_survivors
Real index, real folder service and real server; made-up files only. The folder line wording is not asserted: counts and state only."""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from _paths import SRC  # noqa: F401

from test_ask_index_1366 import Base, ix
from test_ask_index_types_1366 import xlsx
from test_ask_pdf_passages import FAKE_PYPDF, pdf
from test_ask_folders import Base as FoldersBase
from clark import ask_folders, ask_index, ask_passages, ask_service, pdf_reader, reach


def state_of(case, name):
    return ask_index._open_read(case.data, "P1").execute("SELECT state FROM files WHERE label LIKE ?", (f"%{name}",)).fetchone()[0]


class Screens(Base):
    def test_m13_a_file_named_like_a_secret_is_left_out_though_its_text_is_harmless(self):
        self.put("password_hunter2x9.txt", "zqharmless words about the picnic")
        self.put("plain.txt", "zqother words about the picnic")
        self.build()
        self.assertEqual(state_of(self, "password_hunter2x9.txt"), "safety")
        self.assertFalse(self.found("zqharmless"))
        self.assertTrue(self.found("zqother"))
        c = ix.status(self.data, "P1", None)
        self.assertEqual((c["indexed"], c["safety"]), (1, 1))

    def test_m14_a_file_clark_may_never_open_while_reading_is_left_out_as_safety(self):
        self.put("fine.txt", "zqfinetext here")
        self.put("odd.txt", "zqoddtext here")
        real = reach.read_bytes

        def read(path, *a, **k):
            if str(path).endswith("odd.txt"):
                raise reach.Never("changed while opening")
            return real(path, *a, **k)

        with mock.patch.object(reach, "read_bytes", side_effect=read):
            self.build()
        c = ix.status(self.data, "P1", None)
        self.assertEqual((c["indexed"], c["safety"], c["type"]), (1, 1, 0))
        self.assertEqual(state_of(self, "odd.txt"), "safety")
        left = dict(ask_index.files_left_out(self.data, "P1", 200)["files"])
        self.assertEqual(left, {"saved/odd.txt": ask_index.REASON_SAFETY})
        self.assertFalse(self.found("zqoddtext"))


class Caps(Base):
    def test_m16_an_excel_sheet_over_the_row_cap_is_left_out_whole_as_too_long(self):
        rows = [["item", "owner"]] + [[f"t{i}", f"zqrow{i}"] for i in range(10)]
        self.put("s.xlsx", xlsx({"Plan": rows}), binary=True)
        with mock.patch.object(ask_index, "MAX_EXCEL_ROWS", 3):
            self.build()
        self.assertFalse(self.found("zqrow0"))
        self.assertFalse(self.found("zqrow9"))
        self.assertEqual(state_of(self, "s.xlsx"), "too_long")

    def test_m16_an_excel_file_over_the_cell_cap_across_its_sheets_is_left_out_whole_as_too_long(self):
        rows = [[f"zqa{i}", f"b{i}", f"c{i}"] for i in range(10)]
        self.put("c.xlsx", xlsx({"One": rows, "Two": [["zqsecondsheet", "x", "y"]]}), binary=True)
        with mock.patch.object(ask_index, "MAX_EXCEL_CELLS", 5):
            self.build()
        for word in ("zqa0", "zqa9", "zqsecondsheet"):
            self.assertFalse(self.found(word), word)
        self.assertEqual(state_of(self, "c.xlsx"), "too_long")

    def test_m19_a_file_keeps_at_most_the_part_cap_of_passages(self):
        long_line = "zqword " * 100                     # one line is about one passage
        self.put("big.txt", "\n".join(f"{long_line}zqline{i}" for i in range(8)))
        with mock.patch.object(ask_index, "MAX_PARTS_PER_FILE", 2):
            self.build()
        self.assertEqual(ix.status(self.data, "P1", None)["indexed"], 1)
        self.assertTrue(self.found("zqline0"))
        self.assertFalse(self.found("zqline7"))
        n = ask_index._open_read(self.data, "P1").execute("SELECT count(*) FROM p").fetchone()[0]
        self.assertEqual(n, 2)

    def test_m19_the_part_cap_is_one_budget_shared_by_the_pages_of_a_file(self):
        v = self.d / "vendor"
        (v / "pypdf").mkdir(parents=True)
        (v / "pypdf" / "__init__.py").write_text(FAKE_PYPDF, encoding="utf-8")
        with mock.patch.object(pdf_reader, "VENDOR", v), mock.patch.object(ask_index, "MAX_PARTS_PER_FILE", 2):
            self.put("pages.pdf", pdf(["zqpg1", "zqpg2", "zqpg3", "zqpg4"]), binary=True)
            self.build()
        self.assertTrue(self.found("zqpg1"))
        self.assertTrue(self.found("zqpg2"))
        self.assertFalse(self.found("zqpg3"))
        self.assertFalse(self.found("zqpg4"))

    def test_m19_the_cap_is_not_small(self):
        self.assertGreaterEqual(ask_index.MAX_PARTS_PER_FILE, 5000)


class Counts(Base):
    def test_m24_an_online_only_file_is_counted_and_the_files_add_up(self):
        self.put("here.txt", "zqhere text")
        self.put("cloud.txt", "x" * 37)
        real = reach.online_only_stat
        with mock.patch.object(reach, "online_only_stat", side_effect=lambda st: st.st_size == 37 or real(st)):
            self.build()
        c = ix.status(self.data, "P1", None)
        self.assertEqual((c["indexed"], c["online_only"], c["safety"]), (1, 1, 0))
        self.assertEqual(sum(c[k] for k in ask_index.NAMES), 2)
        self.assertIn("Online-only files not searched", ask_index.line_for(c))
        folder = ask_index._open_read(self.data, "P1").execute("SELECT v FROM meta WHERE k='folders'").fetchone()[0]
        self.assertEqual(json.loads(folder)[str(self.box)]["online_only"], 1)
        self.assertEqual(json.loads(folder)[str(self.box)]["safety"], 0)

    def test_m26_a_question_uses_its_first_forty_words_and_no_more(self):
        self.put("a.txt", "zqforty zqfortyone")
        self.build()
        filler = " ".join(f"zzf{i}" for i in range(39))
        self.assertTrue(self.found(f"{filler} zqforty"), "the 40th word is searched")
        self.assertFalse(self.found(f"{filler} zzf40 zqfortyone"), "the 41st word is not")
        self.assertTrue(self.found(f"zqforty {filler} zzf40 zzf41"), "words past 40 are dropped, the first still count")


class AskNoFolders(unittest.TestCase):
    """The real service with a stub indexer that says it is current: a question with no folders must not use the index or add its note."""

    def setUp(self):
        import _publish_fixture as plant
        from clark import ask_claude as ac
        from test_ask_connector_wiring import LIST_M365, PATH, final, stream
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.db = plant.build_db(self.d / "clark.db")
        self.provider = ac.ClaudeCommand(places=(), env={}, limit=5)
        self.provider.connector_runner = lambda: LIST_M365
        out = stream(final("The plan is on track.\nCITE: P1"))
        for p in (mock.patch.object(self.provider, "usable", return_value=(PATH, None)),
                  mock.patch.object(ac, "run", side_effect=lambda *a, **k: ("ok", out, 0))):
            p.start()
            self.addCleanup(p.stop)
        self.indexer = SimpleNamespace(current=lambda code, folders: True, not_yet=lambda code: 7)
        self.service = ask_service.AskService(self.db, self.provider, [], data_dir=self.d, indexer=self.indexer)
        self.folders = []
        p = mock.patch.object(self.service, "folders_for", side_effect=lambda store, code: self.folders)
        p.start()
        self.addCleanup(p.stop)

    def ask(self):
        return self.service.ask({"project": "PUB", "question": "What is the state of the plan?"})

    def test_m29_no_folders_means_the_index_is_not_used_but_the_folder_reader_is(self):
        with mock.patch.object(ask_service.ask_index, "folder_data", side_effect=AssertionError("index used")) as idx, \
                mock.patch.object(ask_service.ask_passages, "folder_data", wraps=ask_passages.folder_data) as plain:
            status, body = self.ask()
        self.assertEqual((status, body.get("ok")), (200, True), body)
        self.assertEqual(idx.call_count, 0)
        self.assertEqual(plain.call_count, 1)

    def test_m29_with_a_folder_and_a_current_index_the_index_is_used(self):
        self.folders = [str(self.d)]
        with mock.patch.object(ask_service.ask_index, "folder_data", wraps=ask_index.folder_data) as idx:
            status, body = self.ask()
        self.assertEqual((status, body.get("ok")), (200, True), body)
        self.assertEqual(idx.call_count, 1)

    def test_m32_no_folders_means_no_still_reading_note(self):
        status, body = self.ask()
        self.assertEqual(status, 200, body)
        self.assertFalse(body.get("index_note"), "no folder, no note")      # the note is its own field (ask_service.py:370), not one of notes
        self.folders = [str(self.d)]
        self.assertTrue(str(self.ask()[1].get("index_note", "")).startswith("Still reading"), "with a folder the note is there")


class Routes(FoldersBase):
    def setUp(self):
        super().setUp()
        self.seen = []
        self.indexer = SimpleNamespace(status_for=lambda code, folders: self.seen.append(code) or {"line": "x"}, start=lambda *a, **k: None)
        self.service.indexer = self.indexer

    def test_m33_the_all_projects_read_passes_the_project_to_the_index_status(self):
        status, _, data = self.s.api("GET", "/api/ask-folders?scope=all&project=ABC")
        body = json.loads(data)
        self.assertEqual((status, body["ok"], body.get("index")), (200, True, {"line": "x"}))
        self.assertEqual(self.seen, ["ABC"])
        status, _, data = self.s.api("GET", "/api/ask-folders?scope=all")
        self.assertNotIn("index", json.loads(data))
        self.assertEqual(self.seen, ["ABC"])

    def test_m34_a_hostile_project_value_never_reaches_the_index(self):
        for bad in ("../x", "A/B", "ABC\n", "", "a b", "x" * 200, None, 7):
            status, body = self.service.read_all(bad)
            self.assertEqual((status, body["ok"]), (200, True), bad)
            self.assertNotIn("index", body, bad)
        self.assertEqual(self.seen, [])

    def test_m35_every_change_that_alters_the_folders_starts_a_reindex_and_a_refused_one_does_not(self):
        calls = []
        with mock.patch.object(self.service, "reindex", side_effect=calls.append):
            status, body = self.post({"project": "ABC", "action": "add", "path": str(self.docs)})
            self.assertEqual(status, 200, body)
            self.assertEqual(calls, [["ABC"]])
            status, body = self.post({"project": "ABC", "action": "remove", "path": str(self.docs)})
            self.assertEqual((status, body["ok"]), (200, True))
            self.assertEqual(len(calls), 2, "remove")
            status, body = self.post({"project": "ABC", "action": "undo", "apply_id": body["apply_id"]})
            self.assertEqual((status, body["ok"]), (200, True), body)
            self.assertEqual(len(calls), 3, "undo")
            self.post({"project": "ABC", "action": "add", "path": str(self.home / "missing")})
            self.assertEqual(len(calls), 3, "a refused add starts nothing")
            self.assertEqual(self.get("ABC")[0], 200)
            self.assertEqual(len(calls), 3, "a read starts nothing")


if __name__ == "__main__":
    unittest.main()
