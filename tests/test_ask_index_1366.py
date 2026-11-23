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
    """AP27: the first-run card and Help say passages leave the Mac. Words approved in NEW-WORDS (item 6). The picture sentence
    (item 10) is held: the build has no picture reader, so it would not be true."""
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
        for held in ("PNG", "JPG"):
            self.assertNotIn(held, said.get("CARD_PASSAGES", ""))


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
        self.assertEqual(left, 1)

    def test_need_match_with_no_words_keeps_none(self):
        from clark import ask_data
        for q in ("", None, "?? ab"):
            got, left = ask_data.choose(self.passages(), q, need_match=True)
            self.assertEqual((got, left), ((), 3), q)

    def test_default_still_keeps_every_passage_that_fits(self):
        from clark import ask_data
        got, left = ask_data.choose(self.passages(), "milestones")
        self.assertEqual(([p.label for p in got], left), (["a", "b", "c"], 0))


if __name__ == "__main__":
    unittest.main()
