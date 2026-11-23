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

from _paths import SRC  # noqa: F401

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


class Followups(Base):
    """Row 1537 (the rest of row 1366): AP1, AP2, AP4, AP5, AP8."""

    def test_excel_over_row_cell_cap_counted_too_long_not_indexed(self):
        from test_ask_index_types_1366 import xlsx
        from clark import ask_index
        rows = [["item", "owner"]] + [[f"t{i}", f"zqcap{i}"] for i in range(10)]
        for cap, value in (("MAX_EXCEL_ROWS", 3), ("MAX_EXCEL_CELLS", 6)):
            with self.subTest(cap=cap):
                shutil.rmtree(self.box)
                self.box.mkdir()
                self.put("big.xlsx", xlsx({"S": rows}), binary=True)
                self.put("ok.txt", "zqcapfine")
                with mock.patch.object(ask_index, cap, value):
                    self.build()
                s = ix.status(self.data, "P1", [self.box])
                self.assertEqual((s["indexed"], s["too_long"]), (1, 1))
                for n in (0, 1, 9):
                    self.assertFalse(self.found(f"zqcap{n}"), "a workbook over the cap is not cut: none of it is indexed")
                self.assertTrue(self.found("zqcapfine"))
                self.assertEqual(dict(ask_index.files_left_out(self.data, "P1", 10)["files"]), {"saved/big.xlsx": ask_index.REASON_TOO_LONG})
        with mock.patch.object(ask_index, "MAX_EXCEL_ROWS", 11):             # exactly at the cap is read whole
            shutil.rmtree(self.box)
            self.box.mkdir()
            self.put("big.xlsx", xlsx({"S": rows}), binary=True)
            self.build()
        self.assertTrue(self.found("zqcap9"))

    def test_followup_terms_find_item_file_passage(self):
        from clark import ask_index
        self.put("risks.txt", "RISK-12 the supplier may slip zqidpassage\nRISK-99 unrelated zqother")
        self.put("noise.txt", "the 12 chairs and the RISK register zqnoise")
        self.build()
        got = ask_index.search(self.data, "P1", "and who owns it", extra=["RISK-12"])
        self.assertTrue(any("zqidpassage" in p.text for p in got))
        seen = []
        real = ask_index.sqlite3.connect
        class Spy:
            def __init__(self, c):
                self.c = c

            def execute(self, sql, args=()):
                if "MATCH" in sql:
                    seen.append(args[0])
                return self.c.execute(sql, args)

            def __getattr__(self, n):
                return getattr(self.c, n)
        with mock.patch.object(ask_index, "_open_read", lambda d, c: Spy(real(str(ask_index.path_for(d, c))))):
            ask_index.search(self.data, "P1", "who owns it", extra=["RISK-12"])
        self.assertIn('"RISK-12"', seen[0])
        self.assertNotIn(' RISK-12 ', " " + seen[0].replace('"RISK-12"', "") + " ")
        long_q = " ".join(f"w{i}" for i in range(45))
        got = ask_index.search(self.data, "P1", long_q, extra=["RISK-12"])
        self.assertTrue(any("zqidpassage" in p.text for p in got), "ids sit outside the first 40 words")
        self.assertEqual(ask_index.search(self.data, "P1", long_q), [])
        data = ask_index.folder_data(self.data, "P1", long_q, extra=["RISK-12"])
        self.assertTrue(any("zqidpassage" in p.text for p in data.passages))

    def test_online_only_not_opened_and_line_says_not_searched(self):
        from clark import ask_index
        self.put("here.txt", "zqhere text")
        self.put("cloud.txt", "x" * 37)
        opened = []
        real, real_online = reach.read_bytes, reach.online_only_stat
        def spy(p, *a, **k):
            opened.append(os.path.basename(str(p)))
            return real(p, *a, **k)
        with mock.patch.object(reach, "online_only_stat", side_effect=lambda st: st.st_size == 37 or real_online(st)), \
                mock.patch.object(reach, "read_bytes", side_effect=spy):
            self.build()
        self.assertEqual(opened, ["here.txt"], "an online-only file is never opened")
        c = ix.status(self.data, "P1", [self.box])
        self.assertEqual(c["online_only"], 1)
        self.assertEqual(ask_index.line_for(c), "Indexed 1 of 2 files. Online-only files not searched.")
        self.assertEqual(ask_index.line_for({"indexed": 1, "online_only": 5}), "Indexed 1 of 6 files. Online-only files not searched.")
        folder = ask_index.folder_status(self.data, "P1", [self.box])[str(self.box)]
        self.assertEqual(folder["left"]["files"][0][0], "Online-only files not searched")

    def test_oserror_on_file_3_does_not_reread_files_1_2(self):
        for n in "abc":
            self.put(f"{n}.txt", f"zq{n}file text")
        self.build()
        for n in "abc":
            (self.box / f"{n}.txt").write_bytes(f"zq{n}file changed".encode())
        real, reads = reach.read_bytes, []
        def spy(p, *a, **k):
            name = os.path.basename(str(p))
            reads.append(name)
            if name == "c.txt":
                raise OSError("disk went away")
            return real(p, *a, **k)
        with mock.patch.object(reach, "read_bytes", side_effect=spy):
            ix.refresh(self.data, "P1", [self.box])
        self.assertEqual(reads.count("a.txt"), 1)
        self.assertEqual(reads.count("b.txt"), 1)
        self.assertEqual(reads.count("c.txt"), 1)
        c = ix.status(self.data, "P1", [self.box])
        self.assertEqual((c["indexed"], c["type"], c["safety"]), (2, 1, 0), "the unreadable file is counted as one clark could not read")
        from clark import ask_index
        self.assertEqual(dict(ask_index.files_left_out(self.data, "P1", 10)["files"]), {"saved/c.txt": ask_index.REASON_TYPE})
        self.assertIn("1 file could not be read", ask_index.done_line(c))

    def test_fixture_library_has_no_client_names(self):
        import sys
        from _paths import TOOLS
        sys.path.insert(0, str(TOOLS))
        import publish_public
        from test_ask_index_types_1366 import xlsx, pptx
        from test_ask_pdf_passages import pdf
        files = {
            "text.pdf": pdf(["zqpdf one", "zqpdf two"]), "long.pdf": pdf([f"zqlong page {i}" for i in range(30)]), "scan.pdf": pdf([None, None]),
            "letter.docx": tdx.docx(tdx.P("zqdocx text")), "table.xlsx": xlsx({"Plan": [["item", "owner"], ["t1", "zqowner"]]}),
            "deck.pptx": pptx({1: ["zqslide text"]}, {1: ["zqnote text"]}), "page.html": b"<html><body><p>zqhtml text</p></body></html>",
            "picture.png": b"\x89PNG\r\n\x1a\nzqpicture", "cloud.txt": b"x" * 37, "keys.txt": FAKE_KEY.encode(),
        }
        self.assertEqual(len(files), 10)
        for name, raw in files.items():
            self.assertEqual(publish_public.guard_kinds("tests/" + name, raw), set(), name)

    def test_first_run_card_and_help_state_passages_go_to_claude(self):
        import json
        from _paths import ROOT
        page = ROOT / "src" / "clark" / "page" / "src"
        six = "Passages from the folders you list go to Claude, which Anthropic runs, only when they contain words from your question."
        ten = "On a Mac, text in PNG and JPG pictures is read on this Mac and never sent out."
        words = (page / "edit" / "askWords.js").read_text(encoding="utf-8")
        self.assertIn(f'export const FOLDERS_GO = "{six}";', words)
        self.assertIn(f'export const PICTURES_LOCAL = "{ten}";', words)
        panel = (page / "edit" / "AskPanel.jsx").read_text(encoding="utf-8")
        self.assertEqual(panel.count("W.FOLDERS_GO"), 2, "the Classic card and the Cards card")
        self.assertEqual(panel.count("W.PICTURES_LOCAL"), 2)
        text = json.dumps(json.loads((page / "help" / "helpContent.json").read_text(encoding="utf-8")), ensure_ascii=False)
        self.assertIn(six, text)
        self.assertIn(ten, text)


class IndexAnswerPage(unittest.TestCase):
    """AP7 (was AP28): the Used line (row 1292) of an answer that names items and cites files from the index, at 1400 and 900, in Chrome.
    The server's answer is the stub of test_ask_about_1292 with sources named like the index labels them. The people and contract warning
    of row 1365 is not drawn by the page on this main (sensitive_names.py has no caller), so it is not asserted here."""

    def test_people_contract_warning_and_used_line_with_index_passages(self):
        import test_ask_about_1292 as about
        from test_server import chrome

        class Run(about.Classic):
            def runTest(self):
                for width in (1400, 900):
                    with self.subTest(width=width), chrome() as cdp:
                        p = self.edit_ready(cdp, width)
                        ident = p.js("document.querySelector('.wil-table tr[data-id]').dataset.id")
                        self.stub.answer = f"{ident} is late. The contract file says why."
                        self.stub.items = [ident]
                        self.stub.read = {"work_items": 17, "milestones": 6, "use_cases": 8, "as_at": "17-11-2026"}
                        self.stub.sources = [{"id": "F1", "label": "saved/plan.xlsx"}, {"id": "F2", "label": "saved/notes.docx"}]
                        p.key("/", code="Slash", vk=191)
                        p.until("!document.querySelector('#ask-send') || !document.querySelector('#ask-send').disabled", "ready")
                        self.ask(p, "What is late?")
                        p.until("!!document.querySelector('[data-ask-used]') && !!document.querySelector('.ask-sources')", "answered")
                        self.assertEqual(p.js("document.querySelector('[data-ask-used]').textContent.replace(/\\s+/g, ' ').trim()"), f"Used: 1 {ident}")
                        self.assertEqual(p.js("[...document.querySelectorAll('.ask-sources li')].map((l) => l.textContent)"), ["saved/plan.xlsx", "saved/notes.docx"])
                        self.assertTrue(p.js("(() => { const u = document.querySelector('[data-ask-used]').getBoundingClientRect(), a = document.querySelector('#ask-panel').getBoundingClientRect(); return u.width > 0 && u.left >= a.left - 1 && u.right <= a.right + 1; })()"), "the Used line sits inside the panel")

        res = unittest.TextTestRunner(stream=open(os.devnull, "w")).run(Run())
        self.assertTrue(res.wasSuccessful(), [str(f[1]) for f in res.failures + res.errors])


if __name__ == "__main__":
    unittest.main()
