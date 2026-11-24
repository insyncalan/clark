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

from test_ask_change_route import Base as RouteBase

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


class FirstRunAndHelpWords(unittest.TestCase):
    """AP27: the first-run card and Help say passages leave the Mac. Words approved in NEW-WORDS (item 6; item 10 is held)."""
    PICTURES = "On a Mac, text in PNG and JPG pictures is read on this Mac and never sent out."
    SENTENCE = "Passages from the folders you list go to Claude, which Anthropic runs, only when they contain words from your question."

    def test_first_run_card_and_help_state_passages_go_to_claude(self):
        import json
        import re
        page = Path(__file__).resolve().parent.parent / "src" / "clark" / "page" / "src"
        words = (page / "edit" / "askWords.js").read_text(encoding="utf-8")
        said = dict(re.findall(r'export const (CARD_[A-Z_]+) = "((?:[^"\\]|\\.)*)"', words))
        self.assertEqual(said.get("CARD_PASSAGES"), self.SENTENCE)
        panel = (page / "edit" / "AskPanel.jsx").read_text(encoding="utf-8")
        self.assertIn("W.CARD_PASSAGES", panel)
        entries = json.loads((page / "help" / "helpContent.json").read_text(encoding="utf-8"))
        self.assertIn(self.SENTENCE, json.dumps(entries, ensure_ascii=False))
        # item 10 (pictures read on this Mac) is held until the picture reader exists: it is in neither the card nor Help.
        self.assertNotIn("CARD_PICTURES", said)
        self.assertNotIn("CARD_PICTURES", panel)
        self.assertNotIn(self.PICTURES, json.dumps(entries, ensure_ascii=False))


class QuestionNeedsNoPassages(RouteBase):
    """AP27 'only when they contain words from your question': a question that matches nothing in the listed folders sends no folder passage."""

    def setUp(self):
        super().setUp()
        patch = mock.patch.object(reach.platform, "system", return_value=reach.platform.MAC)
        patch.start()
        self.addCleanup(patch.stop)
        self.box = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.box, True)
        (self.box / "tank.txt").write_text("The zebrafish tank is cleaned on Tuesdays.", encoding="utf-8")
        self.service.folders_for = lambda store, code: [str(self.box)]
        from clark import ask_index
        self.ix = ask_index.Indexer(self.service.data_dir)
        self.addCleanup(self.ix.shutdown)
        self.service.indexer = self.ix
        self.ix.start("ABC", [str(self.box)])
        self.assertTrue(self.ix.wait_idle(20))

    def ask(self, question):
        self.provider.reply = "ok"
        before = len(self.provider.sent)
        status, got = self.s.api("POST", "/api/ask", {"project": "ABC", "question": question})
        self.assertEqual((status, got.get("ok")), (200, True), got)
        self.assertEqual(len(self.provider.sent), before + 1)
        return self.provider.sent[-1]

    def test_a_question_that_needs_no_passages_sends_none(self):
        needed = self.ask("when is the zebrafish tank cleaned")
        self.assertIn("zebrafish tank is cleaned on Tuesdays", needed, "control: a question that needs the passage sends it")
        unneeded = self.ask("milestones")
        self.assertNotIn("zebrafish", unneeded)
        self.assertNotIn("tank.txt", unneeded)

    def test_the_fallback_also_sends_no_passage_when_no_word_matches(self):
        self.service.indexer = None                       # no current index: the folders are read at question time
        needed = self.ask("when is the zebrafish tank cleaned")
        self.assertIn("zebrafish tank is cleaned on Tuesdays", needed, "control: a question that needs the passage sends it")
        for question in ("milestones", "?? !!"):          # no shared word; no words at all
            unneeded = self.ask(question)
            self.assertNotIn("zebrafish", unneeded, question)
            self.assertNotIn("tank.txt", unneeded, question)

    def test_the_fallback_runs_when_the_index_is_not_current(self):
        self.ix.current = lambda *a, **k: False
        needed = self.ask("when is the zebrafish tank cleaned")
        self.assertIn("zebrafish tank is cleaned on Tuesdays", needed)
        self.assertNotIn("zebrafish", self.ask("milestones"))


class ChooseNeedMatch(unittest.TestCase):
    def passages(self):
        from clark import ask
        return [ask.Passage("a", "alpha tank here"), ask.Passage("b", "beta nothing"), ask.Passage("c", "gamma ABC-R-12 row")]

    def test_need_match_keeps_only_passages_sharing_a_word_or_an_id(self):
        from clark import ask_data
        got, left = ask_data.choose(self.passages(), "the tank and ABC-R-12", need_match=True)
        self.assertEqual([p.label for p in got], ["a", "c"])
        self.assertEqual(left, 0, "b shares no word with the question: that is not a passage left out for size")

    def test_need_match_with_no_words_keeps_none(self):
        from clark import ask_data
        for q in ("", None, "?? ab"):
            got, left = ask_data.choose(self.passages(), q, need_match=True)
            self.assertEqual((got, left), ((), 0), q)

    def test_default_still_keeps_every_passage_that_fits(self):
        from clark import ask_data
        got, left = ask_data.choose(self.passages(), "milestones")
        self.assertEqual(([p.label for p in got], left), (["a", "b", "c"], 0))


ARABIC = "\u0645\u0631\u062d\u0628\u0627 \u0628\u0627\u0644\u0639\u0627\u0644\u0645 \u0627\u0644\u0645\u0634\u0631\u0648\u0639"      # made-up Arabic words, right to left


def arabic_pdf(visual):
    """A real one-page PDF whose text is `visual` (a real PDF stores Arabic in visual order): an Identity-H font with a ToUnicode map, so the
    vendored pypdf reads it the way it reads a real file."""
    chars = sorted(set(visual))
    code = {c: i + 1 for i, c in enumerate(chars)}
    pairs = "".join("<%04X> <%04X>\n" % (code[c], ord(c)) for c in chars)
    cmap = ("/CIDInit /ProcSet findresource begin 12 dict begin begincmap /CMapName /X def /CMapType 2 def\n"
            "1 begincodespacerange <0000> <FFFF> endcodespacerange\n%d beginbfchar\n%sendbfchar\nendcmap end end" % (len(chars), pairs))
    stream = "BT /F1 12 Tf 50 700 Td <%s> Tj ET" % "".join("%04X" % code[c] for c in visual)
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            "<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
            "<< /Type /Font /Subtype /Type0 /BaseFont /Made /Encoding /Identity-H /DescendantFonts [6 0 R] /ToUnicode 7 0 R >>",
            "<< /Type /Font /Subtype /CIDFontType2 /BaseFont /Made /CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> /DW 500 >>",
            "<< /Length %d >>\nstream\n%s\nendstream" % (len(cmap), cmap)]
    out, offs = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += ("%d 0 obj\n%s\nendobj\n" % (i, o)).encode()
    tail = "xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1) + "".join("%010d 00000 n \n" % o for o in offs)
    return out + (tail + "trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, len(out))).encode()


class RowCaps(Base):
    def left_out(self):
        return dict(ix.mod().files_left_out(self.data, "P1", 200)["files"])

    def test_excel_over_row_cell_cap_counted_too_long_not_indexed(self):
        from test_ask_index_types_1366 import xlsx
        rows = [["item", "owner"]] + [[f"t{i}", f"zqrow{i}"] for i in range(9)]
        self.put("rows.xlsx", xlsx({"Plan": rows}), binary=True)
        self.put("cells.xlsx", xlsx({"One": [[f"zqcell{i}", "b", "c"] for i in range(6)]}), binary=True)
        self.put("fits.xlsx", xlsx({"Plan": [["item", "owner"], ["t", "zqfits"]]}), binary=True)
        with mock.patch.object(ix.mod(), "MAX_EXCEL_ROWS", 9), mock.patch.object(ix.mod(), "MAX_EXCEL_CELLS", 12):
            self.build()
        s = ix.status(self.data, "P1", None)
        self.assertEqual((s["indexed"], s["too_long"]), (1, 2), s)
        self.assertEqual(self.left_out(), {"saved/rows.xlsx": ix.mod().REASON_TOO_LONG, "saved/cells.xlsx": ix.mod().REASON_TOO_LONG})
        for word in ("zqrow0", "zqrow8", "zqcell0"):
            self.assertFalse(self.found(word), "no part of a workbook over the cap is stored: " + word)
        self.assertTrue(self.found("zqfits"))

    def test_a_workbook_exactly_at_the_row_and_cell_cap_is_indexed(self):
        from test_ask_index_types_1366 import xlsx
        self.put("edge.xlsx", xlsx({"S": [[f"zqedge{i}", "x"] for i in range(5)]}), binary=True)
        with mock.patch.object(ix.mod(), "MAX_EXCEL_ROWS", 5), mock.patch.object(ix.mod(), "MAX_EXCEL_CELLS", 10):
            self.build()
        self.assertEqual(ix.status(self.data, "P1", None)["indexed"], 1)
        self.assertTrue(self.found("zqedge4"))


class Arabic(Base):
    def setUp(self):
        super().setUp()
        self.word = ARABIC.split()[2]

    def test_arabic_rtl_docx_pdf_indexed(self):
        self.put("arabic.docx", tdx.docx(tdx.P("\u200f" + ARABIC + "\u200f") + tdx.P("zqenglish after")), binary=True)
        self.put("arabic.pdf", arabic_pdf(ARABIC[::-1]), binary=True)
        self.build()
        s = ix.status(self.data, "P1", None)
        self.assertEqual((s["indexed"], s["type"]), (2, 0), s)
        got = self.found(self.word)
        self.assertEqual(sorted({l.split(",")[0].split(" (")[0] for l, _t in got}), ["saved/arabic.docx", "saved/arabic.pdf"])
        self.assertTrue(all(ARABIC in t for _l, t in got), "each file's text comes back in reading order, whole")
        self.assertTrue(self.found("zqenglish"), "Latin text in the same file is still found")
        self.assertFalse(self.found("\u0627\u0644\u0645\u0634"), "a part of a word is not a match")


class StartupAndRecovery(Base):
    def test_launcher_starts_indexer_for_saved_folder_without_db(self):
        import io
        from clark import __main__ as launcher, ask_folders, ask_index, store as st
        made, calls = [], []
        real = ask_index.Indexer
        data = self.d / "launch"
        data.mkdir()
        store = st.open_store(data / "clark.db", onedrive_roots=[])
        with store.step("dashboard", "tester", place="menu") as step:
            step.create("projects", {"code": "ABC", "name": "Example Programme"})
            step.create("projects", {"code": "XYZ", "name": "Other Programme"})
        store.close()
        seed = ask_folders.AskFolders(data / "clark.db", [], data_dir=data, home=self.d, by_user=lambda: "tester")
        self.assertEqual(seed.change({"project": "ABC", "action": "add", "path": str(self.box)})[0], 200)
        self.assertFalse(ix.path_for(data, "ABC").exists())

        def spy(*a, **kw):
            made.append(real(*a, refresh_fn=lambda d, code, folders, *r, **k: calls.append((code, list(folders))) or True, **kw))
            return made[-1]

        def serve(**kw):
            print("Open http://127.0.0.1:%d/ to use the report editor." % kw["port"], file=kw["out"], flush=True)
            made[-1].wait_idle(10)
            return 0

        with mock.patch.object(launcher.ask_index, "Indexer", spy), mock.patch.object(launcher.platform, "container_on_host_network", lambda: False), \
                mock.patch.object(st.Store, "ask_enabled", lambda self: True):
            code = launcher.main(["--data", str(data), "--port", "8123"], out=io.StringIO(), err=io.StringIO(), serve=serve,
                                 home=self.d, onedrive_roots=[], environ={}, is_free=lambda port: True)
        self.assertEqual(code, 0)
        self.assertEqual(calls, [("ABC", [str(self.box)])], "the project with a saved folder and no index starts; the project with no folder does not")

    def _launch_with(self, refresh_fn, serve_body, start_wrap=None, name="launch", patches=()):
        """Real launcher.main with a stub serve; serve_body(made, state) runs when serve begins. Returns (exit code, state)."""
        import contextlib
        import io
        from clark import __main__ as launcher, ask_folders, ask_index, store as st
        made, state = [], {"starts": 0, "started_at_serve": None, "served": False}
        real = ask_index.Indexer
        data = self.d / name
        data.mkdir()
        store = st.open_store(data / "clark.db", onedrive_roots=[])
        with store.step("dashboard", "tester", place="menu") as step:
            step.create("projects", {"code": "ABC", "name": "Example Programme"})
        store.close()
        seed = ask_folders.AskFolders(data / "clark.db", [], data_dir=data, home=self.d, by_user=lambda: "tester")
        self.assertEqual(seed.change({"project": "ABC", "action": "add", "path": str(self.box)})[0], 200)

        def spy(*a, **kw):
            made.append(real(*a, refresh_fn=refresh_fn, **kw))
            real_start = made[-1].start

            def start(*sa, **skw):
                state["starts"] += 1
                if start_wrap:
                    start_wrap()
                return real_start(*sa, **skw)
            made[-1].start = start
            return made[-1]

        def serve(**kw):
            print("Open http://127.0.0.1:%d/ to use the report editor." % kw["port"], file=kw["out"], flush=True)
            state["started_at_serve"] = state["starts"]
            state["served"] = True
            serve_body(made, state)
            return 0

        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(launcher.ask_index, "Indexer", spy))
            stack.enter_context(mock.patch.object(launcher.platform, "container_on_host_network", lambda: False))
            stack.enter_context(mock.patch.object(st.Store, "ask_enabled", lambda self: True))
            for make in patches:
                stack.enter_context(make(ask_folders))
            code = launcher.main(["--data", str(data), "--port", "8123"], out=io.StringIO(), err=io.StringIO(), serve=serve,
                                 home=self.d, onedrive_roots=[], environ={}, is_free=lambda port: True)
        return code, state

    def test_launcher_starts_indexer_before_serve_begins(self):
        """Order pin: the start is already made when serve begins (a start moved after serve would count 0 here)."""
        code, state = self._launch_with(lambda d, c, f, *r, **k: True, lambda made, state: made[-1].wait_idle(10))
        self.assertEqual(code, 0)
        self.assertEqual(state["started_at_serve"], 1, "Indexer.start was already called for the saved folder when serve began")

    def test_launcher_survives_start_missing_raising(self):
        def boom():
            raise RuntimeError("zq start failed")
        code, state = self._launch_with(lambda d, c, f, *r, **k: True, lambda made, state: None, start_wrap=boom, name="boom_start")
        self.assertEqual(code, 0, "Indexer.start raising does not stop the launch")
        self.assertTrue(state["served"], "serve is still reached after Indexer.start raised")
        self.assertEqual(state["starts"], 1)

        def open_boom(af):
            return mock.patch.object(af.AskFolders, "store", side_effect=RuntimeError("zq store open failed"))
        code, state = self._launch_with(lambda d, c, f, *r, **k: True, lambda made, state: None, name="boom_store", patches=[open_boom])
        self.assertEqual(code, 0, "the store failing to open does not stop the launch")
        self.assertTrue(state["served"], "serve is still reached after the store open raised")

    def test_launcher_reaches_serve_while_refresh_is_blocked(self):
        import threading
        gate, entered = threading.Event(), threading.Event()

        def refresh(d, code, folders, *r, **k):
            entered.set()
            gate.wait(10)
            return True

        seen = {}

        def body(made, state):
            seen["entered"] = entered.wait(5)
            seen["blocked_at_serve"] = not gate.is_set()
            gate.set()
            made[-1].wait_idle(10)

        try:
            code, state = self._launch_with(refresh, body, name="slow")
        finally:
            gate.set()
        self.assertEqual(code, 0)
        self.assertTrue(state["served"], "serve is reached")
        self.assertTrue(seen["entered"], "the read had started")
        self.assertTrue(seen["blocked_at_serve"], "serve began while the read was still blocked")

    def test_oserror_on_file_3_does_not_reread_files_1_2(self):
        for i in (1, 2, 3):
            self.put(f"f{i}.txt", f"zqfile{i} words")
        opened = []
        real = reach.read_bytes

        def read(path, *a, **k):
            opened.append(Path(path).name)
            if str(path).endswith("f3.txt"):
                raise OSError("zq cannot read")
            return real(path, *a, **k)

        with mock.patch.object(reach, "read_bytes", side_effect=read):
            self.assertTrue(ix.mod().refresh(self.data, "P1", [str(self.box)]), "the pass runs to its end")
            self.assertTrue(ix.mod().refresh(self.data, "P1", [str(self.box)]))
        self.assertEqual(sorted(opened), ["f1.txt", "f2.txt", "f3.txt"], "files 1 and 2 are opened once, never again")
        self.assertTrue(ix.mod().current(self.data, "P1", [str(self.box)]))
        s = ix.status(self.data, "P1", None)
        self.assertEqual((s["indexed"], s["type"]), (2, 1), s)
        self.assertTrue(self.found("zqfile1") and self.found("zqfile2"))
        self.assertFalse(self.found("zqfile3"))

    def test_all_refused_folders_index_is_current(self):
        bad = self.box / ".ssh"
        bad.mkdir()
        (bad / "k.txt").write_text("zqrefused text", encoding="utf-8")
        folders = [str(bad)]
        self.assertTrue(ix.mod().refresh(self.data, "P1", folders))
        self.assertTrue(ix.mod().current(self.data, "P1", folders), "it carries the screen version, so it is not read again every 5 seconds")
        calls = []
        w = ix.mod().Indexer(self.data, None, refresh_fn=lambda *a, **k: calls.append(1))
        self.addCleanup(w.shutdown)
        later = ix.mod().time.monotonic() + ix.mod().STALE_POLL_SECONDS + 1
        with mock.patch.object(ix.mod().time, "monotonic", return_value=later):
            w.status_for("P1", folders)
            self.assertTrue(w.wait_idle(10))
        self.assertEqual(calls, [])
        self.assertFalse(self.found("zqrefused"))


class FollowUp(Base):
    def test_followup_terms_find_item_file_passage(self):
        """"And who owns it?" has no word the file holds; the item ID named in the turns before it does."""
        import _publish_fixture as plant
        from types import SimpleNamespace
        from clark import ask_claude as ac, ask_index, ask_service
        from test_ask_connector_wiring import LIST_M365, PATH, final, stream
        self.put("launch.txt", "Item ABC-12 is owned by zqpriya for the launch.\nA different page about zqcatering.")
        ix.build(self.data, "PUB", [self.box])
        provider = ac.ClaudeCommand(places=(), env={}, limit=5)
        provider.connector_runner = lambda: LIST_M365
        out = stream(final("zqpriya.\nCITE: P1"))
        for p in (mock.patch.object(provider, "usable", return_value=(PATH, None)), mock.patch.object(ac, "run", side_effect=lambda *a, **k: ("ok", out, 0))):
            p.start()
            self.addCleanup(p.stop)
        service = ask_service.AskService(plant.build_db(self.d / "clark.db"), provider, [], data_dir=self.data,
                                         indexer=SimpleNamespace(current=lambda code, folders: True, not_yet=lambda code: 0))
        service.folders_for = lambda store, code: [str(self.box)]
        seen = []
        real = ask_index.folder_data
        with mock.patch.object(ask_index, "folder_data", side_effect=lambda *a, **k: seen.append((a[2], real(*a, **k))) or seen[-1][1]):
            earlier = [{"role": "user", "text": "What is ABC-12?"}, {"role": "assistant", "text": "ABC-12 is the launch."}]
            status, body = service.ask({"project": "PUB", "question": "And who owns it?", "earlier": earlier})
            self.assertEqual(status, 200, body)
            alone = real(self.data, "PUB", "And who owns it?")
        self.assertEqual(len(seen), 1, "the answer came from the index")
        asked, found = seen[0]
        self.assertTrue(asked.startswith("And who owns it?") and "ABC-12" in asked, asked)
        self.assertTrue(any("zqpriya" in p.text for p in found.passages), "the item's file passage is found")
        self.assertFalse(alone.passages, "the question alone finds nothing: the file holds none of its words")


class Library(Base):
    """Row 1366 AP29 (Product Manager ruling 24-11): one made-up library of the ten types, and none of it names a client. The names list is the one
    test_no_real_names.py holds (banned_in, banned_across), read only."""

    WORDS = {"text.pdf": "zqlibpdf", "long.pdf": "zqlibpage201", "scan.pdf": None, "memo.docx": "zqlibdocx", "sheet.xlsx": "zqlibxlsx",
             "deck.pptx": "zqlibpptx", "page.html": "zqlibhtml", "photo.png": "zqlibpicture"}

    def library(self):
        """Make the ten files in the saved folder; the text of each (and each name) is returned for the names check."""
        import test_ask_index_types_1366 as types
        from test_ask_pdf_passages import FAKE_PYPDF, pdf
        from clark import ask_index, ask_picture, pdf_reader      # ask_index first: on a Mac it registers the real picture reader at import, which would replace the stand-in
        v = self.d / "vendor"
        (v / "pypdf").mkdir(parents=True)
        (v / "pypdf" / "__init__.py").write_text(FAKE_PYPDF, encoding="utf-8")
        for p in (mock.patch.object(pdf_reader, "VENDOR", v), mock.patch.object(ask_picture.platform, "system", return_value=ask_picture.platform.MAC),
                  mock.patch.object(ask_picture, "_READER", lambda raw: raw.decode("latin-1").split("|", 1)[-1])):
            p.start()
            self.addCleanup(p.stop)
        w = self.WORDS
        self.put("text.pdf", pdf([f"{w['text.pdf']} first page", "second page"]), binary=True)
        self.put("long.pdf", pdf([f"page {i}" if i < 201 else w["long.pdf"] for i in range(1, 202)]), binary=True)      # over the question's 200 pages
        self.put("scan.pdf", pdf([None, None]), binary=True)
        self.put("memo.docx", tdx.docx(tdx.P(f"{w['memo.docx']} words")), binary=True)
        self.put("sheet.xlsx", types.xlsx({"Plan": [["item", "owner"], [w["sheet.xlsx"], "Ana"]]}), binary=True)
        self.put("deck.pptx", types.pptx({1: [f"{w['deck.pptx']} slide"]}), binary=True)
        self.put("page.html", f"<html><body><p>{w['page.html']} text</p></body></html>")
        self.put("photo.png", f"IMG|{w['photo.png']} words".encode(), binary=True)
        self.put("key.txt", FAKE_KEY)
        return [*self.WORDS, "key.txt", "online-only stand-in"], [*(v for v in w.values() if v), "Plan item owner Ana"]

    def test_fixture_library_has_no_client_names(self):
        import test_no_real_names as names
        files, texts = self.library()
        real = reach.online_only_stat
        with mock.patch.object(reach, "online_only_stat", lambda st: st.st_size == 77 or real(st)):          # the online-only stand-in: a placeholder (Mac flag), counted and never opened
            self.put("stand-in.txt", "x" * 77)
            self.build()
        c = ix.status(self.data, "P1", None)
        self.assertEqual((c["indexed"], c["type"], c["safety"], c["online_only"]), (7, 1, 1, 1), c)      # 7 read, the scan, the fake key, the stand-in: ten types, each counted once
        for name, word in self.WORDS.items():
            if word:
                self.assertTrue(self.found(word), name)
        text = "\n".join([*files, *texts, *(f"{label}\n{t}" for w in texts for label, t in self.found(w))])
        self.assertEqual(names.banned_in(text), [], "a name from the banned list is in the library")
        self.assertFalse(names.banned_across(text))
        self.assertEqual(len(files), 10)
        self.assertTrue(names.banned_in(text, frozenset({names.digest("zqlibdocx")})), "the check does see a banned word in the library")


class UsedLine(unittest.TestCase):
    """Row 1366 AP28 (Product Manager ruling 24-11: the Used line only; the people and contract warning belongs to row 1365): an answer built from index
    passages carries the same Used line data (what was read, and each source's file) as one built from the raw reader."""

    def setUp(self):
        from test_ask_change_route import Base as Route
        self.route = Route("run")
        self.route.setUp()
        self.addCleanup(self.route.s.close)
        self.addCleanup(self.route.demo.close)
        patch = mock.patch.object(reach.platform, "system", return_value=reach.platform.MAC)
        patch.start()
        self.addCleanup(patch.stop)
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        (self.d / "saved").mkdir()
        (self.d / "saved" / "plan.txt").write_text("The zqusedline tank is cleaned on Tuesdays.", encoding="utf-8")
        self.route.service.data_dir = self.d / "data"
        (self.d / "data").mkdir()

    def ask(self, current):
        from clark import ask_service
        ask_index = ix.mod()
        ask_index.build(self.d / "data", "ABC", [str(self.d / "saved")])
        self.route.service.indexer = mock.Mock(current=mock.Mock(return_value=current), not_yet=mock.Mock(return_value=None))
        self.route.provider.reply = "Here.\n" + "\n".join(f"CITE: P{i}" for i in range(1, 15))
        with mock.patch.object(ask_service.AskService, "folders_for", lambda *_a: [str(self.d / "saved")]), \
                mock.patch.object(ask_service.ask_index, "folder_data", wraps=ask_index.folder_data) as idx:
            status, got = self.route.s.api("POST", "/api/ask", {"project": "ABC", "question": "when is the zqusedline tank cleaned"})
        self.assertEqual(idx.call_count, int(current), "the index answered exactly when it was current")
        self.assertEqual((status, got.get("ok")), (200, True), got)
        return got

    def test_used_line_with_index_passages(self):
        by_index, by_raw = self.ask(True), self.ask(False)
        files = [(s["label"], s["file"]) for s in by_index["sources"] if s["file"]]
        self.assertEqual([f for _l, f in files], ["saved/plan.txt"], by_index["sources"])
        self.assertIn("plan.txt", files[0][0])
        self.assertEqual(by_index["read"], by_raw["read"])
        self.assertEqual(by_index["read"]["milestones"] + by_index["read"]["work_items"] + by_index["read"]["use_cases"], 3, by_index["read"])
        self.assertEqual([s for s in by_index["sources"] if not s["file"]], [s for s in by_raw["sources"] if not s["file"]])
        self.assertEqual([f for _l, f in ((s["label"], s["file"]) for s in by_raw["sources"] if s["file"])], ["saved/plan.txt"])


if __name__ == "__main__":
    unittest.main()
