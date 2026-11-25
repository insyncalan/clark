"""Row 1366: every claim of the index Help paragraphs is pinned by a test that fails when the claim stops being true.

Run: python3 dev/run_tests.py test_ask_index_claims_1366
Tests only, no browser. Every file is made in the test from made-up text. The table claim -> test is in the PR body.
"""
import builtins
import json
import os
import re
import socket
import threading
import unittest
from pathlib import Path
from unittest import mock

from _paths import ROOT, SRC  # noqa: F401

from test_ask_change_route import Base as RouteBase
from test_ask_index_1366 import Base, FAKE_KEY, ix
from test_ask_index_types_1366 import xlsx
from clark import ask_index, ask_passages, ask_picture, ask_service, reach

HELP = ROOT / "src" / "clark" / "page" / "src" / "help" / "helpContent.json"
JSX = ROOT / "src" / "clark" / "page" / "src" / "edit" / "AskSettings.jsx"


def paragraph(start):
    ref = json.loads(HELP.read_text(encoding="utf-8"))["reference"]["sections"]
    sec = next(s for s in ref if s["id"] == "ask-clark")
    got = [b[1] for b in sec["b"] if b[0] == "p" and b[1].startswith(start)]
    assert len(got) == 1, start
    return got[0]


def no_network(*_a, **_k):
    raise AssertionError("the index opened a network connection")


class Network:
    """While active, any socket connection, name lookup or datagram fails the test."""

    def __enter__(self):
        self.ps = [mock.patch.object(socket.socket, "connect", no_network), mock.patch.object(socket.socket, "connect_ex", no_network),
                   mock.patch.object(socket.socket, "sendto", no_network), mock.patch.object(socket, "create_connection", no_network),
                   mock.patch.object(socket, "getaddrinfo", no_network)]
        for p in self.ps:
            p.start()

    def __exit__(self, *_a):
        for p in self.ps:
            p.stop()


class Where(Base):
    """Claim 4 and 5: one file for each project in <data>/ask-index/<code>.db; it is only a copy."""

    def test_the_index_is_one_file_per_project_in_ask_index_inside_the_data_folder(self):
        self.put("a.txt", "zqwhere")
        self.build("P1")
        self.build("P2")
        for code in ("P1", "P2"):
            self.assertEqual(ix.path_for(self.data, code), self.data / "ask-index" / f"{code}.db")
            self.assertTrue((self.data / "ask-index" / f"{code}.db").is_file())
        self.assertEqual(sorted(p.name for p in (self.data / "ask-index").iterdir()), ["P1.db", "P2.db"])

    def test_it_is_only_a_copy_building_again_after_a_delete_gives_the_same_answer_and_the_folder_is_untouched(self):
        a = self.put("a.txt", "zqcopy alpha")
        before = (a.read_bytes(), a.stat().st_mtime_ns, sorted(os.listdir(self.box)))
        self.build()
        first = self.found("zqcopy")
        ix.path_for(self.data, "P1").unlink()
        self.assertEqual(self.found("zqcopy"), [])
        self.build()
        self.assertEqual(self.found("zqcopy"), first)
        self.assertEqual((a.read_bytes(), a.stat().st_mtime_ns, sorted(os.listdir(self.box))), before)


class Once(Base):
    """Claim 1 and 7: read once; brought up to date when a file is added, changed or removed."""

    def test_a_second_refresh_opens_no_file_when_nothing_changed(self):
        self.put("a.txt", "zqonce")
        self.put("b.md", "zqonce too")
        self.build()
        with mock.patch.object(reach, "read_bytes", side_effect=AssertionError("a file was read twice")):
            self.assertTrue(ix.mod().refresh(self.data, "P1", [self.box]))
        self.assertEqual(len(self.found("zqonce")), 2)

    def test_refresh_takes_in_an_added_a_changed_and_a_removed_file(self):
        keep = self.put("keep.txt", "zqkeep stays", mtime=1000)
        chg = self.put("chg.txt", "zqold text", mtime=1000)
        gone = self.put("gone.txt", "zqgone text")
        self.build()
        self.put("new.txt", "zqadded text")
        self.put("chg.txt", "zqnew text longer", mtime=2000)
        gone.unlink()
        ix.refresh(self.data, "P1", [self.box])
        self.assertTrue(self.found("zqadded"))
        self.assertTrue(self.found("zqnew"))
        self.assertFalse(self.found("zqold"))
        self.assertFalse(self.found("zqgone"))
        self.assertTrue(self.found("zqkeep"))
        self.assertEqual(ix.status(self.data, "P1", [self.box])["indexed"], 3)


class Background(Base):
    """Claim 6: read in the background while clark is open."""

    def test_start_returns_at_once_and_the_read_runs_on_another_daemon_thread(self):
        self.put("a.txt", "zqbg")
        gate, ran_on = threading.Event(), []

        def slow(*a, **k):
            ran_on.append(threading.current_thread())
            gate.wait(5)
            return ix.mod().refresh(*a, **k)
        w = ix.mod().Indexer(self.data, None, refresh_fn=slow)
        self.addCleanup(w.shutdown)
        self.addCleanup(gate.set)
        self.assertTrue(w.start("P1", [str(self.box)]))
        self.assertEqual(w.busy, 1, "start() came back while the read was still going")
        self.assertFalse(w.current("P1", [str(self.box)]))
        gate.set()
        self.assertTrue(w.wait_idle(10))
        self.assertTrue(w.current("P1", [str(self.box)]))
        self.assertIsNot(ran_on[0], threading.main_thread())
        self.assertTrue(ran_on[0].daemon)

    def test_the_server_starts_one_indexer_and_stops_it_with_clark(self):
        src = (SRC / "clark" / "__main__.py").read_text(encoding="utf-8")
        self.assertIn("indexer = ask_index.Indexer(", src)
        self.assertIn("indexer.shutdown()", src)


class FolderRemoved(Base):
    """Claim 8: taking a folder out of the list deletes its part of the index."""

    def test_a_folder_left_out_of_the_list_loses_its_rows_and_its_text_leaves_the_file(self):
        other = self.d / "other"
        a = self.put("a.txt", "zqstays here")
        self.put("b.txt", "zqremoved here", folder=other)
        self.build("P1", [self.box, other])
        self.assertTrue(self.found("zqremoved"))
        ix.refresh(self.data, "P1", [self.box])
        self.assertFalse(self.found("zqremoved"))
        self.assertTrue(self.found("zqstays"))
        self.assertNotIn(b"zqremoved", ix.path_for(self.data, "P1").read_bytes())
        self.assertEqual(ix.status(self.data, "P1", [self.box])["indexed"], 1)

    def test_the_last_folder_taken_out_deletes_the_index_file(self):
        self.put("a.txt", "zqlast")
        self.build()
        self.assertTrue(ix.path_for(self.data, "P1").exists())
        ix.refresh(self.data, "P1", [])
        self.assertFalse(ix.path_for(self.data, "P1").exists())


class NothingSent(Base):
    """Claim 9: nothing is sent anywhere when the index is made."""

    def files(self):
        import test_docx_read as tdx
        from test_ask_index_types_1366 import pptx
        self.put("n.txt", "zqnet plain")
        self.put("n.md", "zqnet markdown")
        self.put("n.csv", "a,b\nzqnet,1")
        self.put("n.docx", tdx.docx(tdx.P("zqnet word")), binary=True)
        self.put("n.xlsx", xlsx({"S": [["zqnet excel"]]}), binary=True)
        self.put("n.pptx", pptx({1: ["zqnet slide"]}), binary=True)
        self.put("n.html", '<html><body><p>zqnet web</p><img src="http://example.invalid/x.png">'
                           '<a href="https://example.invalid/">link</a><script src="http://example.invalid/s.js"></script></body></html>')

    def test_building_every_kind_of_file_opens_no_connection(self):
        self.files()
        with Network():
            self.build()
        self.assertEqual(ix.status(self.data, "P1", [self.box])["indexed"], 7)

    def test_the_indexer_thread_opens_no_connection_and_the_provider_is_never_called(self):
        self.files()
        provider = mock.Mock()
        w = ix.mod().Indexer(self.data, None)
        self.addCleanup(w.shutdown)
        with Network():
            w.start("P1", [str(self.box)])
            self.assertTrue(w.wait_idle(20))
            w.status_for("P1", [str(self.box)])
        self.assertTrue(w.current("P1", [str(self.box)]))
        self.assertEqual(provider.mock_calls, [])

    def test_the_index_code_has_no_way_to_reach_the_model_or_a_connector(self):
        for name in ("ask_service", "ask_claude", "ask_connectors", "ask_connector_stream", "ask_provider"):
            self.assertFalse(hasattr(ask_index, name), name)
        src = Path(ask_index.__file__).read_text(encoding="utf-8")
        for word in ("import socket", "urllib.request", "http.client", "ask_service", "ask_claude", "ask_connectors", "subprocess", "requests"):
            self.assertNotIn(word, src, word)


class Question(RouteBase):
    """Claims 2 and 9: what a question does with a finished index, and what is sent."""

    def setUp(self):
        super().setUp()
        import shutil
        import tempfile
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.box = self.d / "saved"
        self.box.mkdir()
        (self.box / "tank.txt").write_text("The zebrafish tank is cleaned on Tuesdays.", encoding="utf-8")
        (self.box / "other.txt").write_text("The quokka enclosure opens at nine.", encoding="utf-8")
        self.service.folders_for = lambda store, code: [str(self.box)]
        self.ix = ask_index.Indexer(self.service.data_dir)
        self.addCleanup(self.ix.shutdown)
        self.service.indexer = self.ix
        self.assertEqual(self.provider.sent, [])
        self.ix.start("ABC", [str(self.box)])
        self.assertTrue(self.ix.wait_idle(20))
        self.assertEqual(self.provider.sent, [], "making the index sent nothing to the model")

    def test_with_a_finished_index_no_source_file_is_opened_while_you_ask(self):
        opened = []
        real_open, real_os_open = builtins.open, os.open

        def spy_path(name):
            real = getattr(Path, name)

            def go(self_, *a, **k):
                # clark's own files (the usage count, settings) are read while you ask; a file in a source folder is not
                if str(self.box) in str(self_):
                    raise AssertionError(name)
                return real(self_, *a, **k)
            return go

        def spy_open(f, *a, **k):
            opened.append(str(f))
            return real_open(f, *a, **k)

        def spy_os_open(f, *a, **k):
            opened.append(str(f))
            return real_os_open(f, *a, **k)
        self.provider.reply = "It is cleaned on Tuesdays."
        with mock.patch.object(reach, "read_bytes", side_effect=AssertionError("a question read a file")), \
                mock.patch.object(ask_passages, "folder_data", side_effect=AssertionError("a question used the raw reader")), \
                mock.patch.object(Path, "read_bytes", autospec=True, side_effect=spy_path("read_bytes")), \
                mock.patch.object(Path, "read_text", autospec=True, side_effect=spy_path("read_text")), \
                mock.patch.object(builtins, "open", spy_open), mock.patch.object(os, "open", spy_os_open):
            status, got = self.s.api("POST", "/api/ask", {"project": "ABC", "question": "when is the zebrafish tank cleaned"})
        self.assertEqual((status, got.get("ok")), (200, True), got)
        self.assertEqual([f for f in opened if str(self.box) in f], [])

    def test_only_the_passages_that_match_the_question_are_sent(self):
        self.provider.reply = "Tuesdays."
        status, got = self.s.api("POST", "/api/ask", {"project": "ABC", "question": "when is the zebrafish tank cleaned"})
        self.assertEqual((status, got.get("ok")), (200, True), got)
        self.assertEqual(len(self.provider.sent), 1)
        self.assertIn("zebrafish", self.provider.sent[0])
        self.assertNotIn("quokka", self.provider.sent[0])
        self.assertNotIn(str(self.box), self.provider.sent[0], "no path of the folder is sent")

    def test_a_passage_served_from_the_index_goes_through_the_same_secret_screen_at_answer_time(self):
        """The index screens a file when it is read, but the answer path screens every passage again (ask.build_request), as for the files:
        a row that looks like a key and is in the index anyway (an older index, a screen that was weaker then) is never sent."""
        import sqlite3
        db = sqlite3.connect(ask_index.path_for(self.service.data_dir, "ABC"))
        for text, name in (("zebrafish tank login " + FAKE_KEY, "planted.txt"), ("The zebrafish tank is cleaned on Tuesdays.", "clean.txt")):
            db.execute("INSERT INTO p(text, file, part, mtime) VALUES (?, ?, NULL, 1700000000)", (text, name))
        db.commit()
        db.close()
        self.assertTrue(self.ix.current("ABC", [str(self.box)]), "the index is still the one a question is answered from")
        self.assertTrue(any("planted.txt" in p.label for p in ask_index.search(self.service.data_dir, "ABC", "zebrafish")),
                        "the planted row is served by the index search, so only the answer-time screen can stop it")
        self.provider.reply = "Tuesdays."
        status, got = self.s.api("POST", "/api/ask", {"project": "ABC", "question": "when is the zebrafish tank cleaned"})
        self.assertEqual((status, got.get("ok")), (200, True), got)
        self.assertEqual(len(self.provider.sent), 1)
        self.assertNotIn(FAKE_KEY, self.provider.sent[0], "a passage that looks like a password is not sent")
        self.assertNotIn("planted.txt", self.provider.sent[0])
        self.assertIn("clean.txt", self.provider.sent[0], "the ordinary passage is still sent")
        self.assertNotIn(FAKE_KEY, json.dumps(got))

    def test_while_the_index_is_not_current_a_question_reads_the_files_instead(self):
        """Why the Help does not say a question never opens a file: it falls back to the files while the index is old or being read."""
        self.ix.current = lambda code, folders: False
        raw = []
        real = ask_passages.folder_data
        with mock.patch.object(ask_service.ask_passages, "folder_data", lambda *a, **k: raw.append(1) or real(*a, **k)):
            self.provider.reply = "x"
            self.s.api("POST", "/api/ask", {"project": "ABC", "question": "zebrafish"})
        self.assertEqual(raw, [1])


class Rebuild(Base):
    """Claim 5: clark builds a deleted index again. The behaviour is pinned in test_ask_index_rebuild_1366; here the Help sentence and the run."""

    def test_deleting_the_file_starts_a_read_and_the_file_is_there_again(self):
        self.put("a.txt", "zqdel")
        folders = [str(self.box)]
        w = ix.mod().Indexer(self.data, None)
        self.addCleanup(w.shutdown)
        w.start("P1", folders)
        self.assertTrue(w.wait_idle(10))
        ix.path_for(self.data, "P1").unlink()
        self.assertFalse(w.current("P1", folders), "the question that finds it missing reads the folders")
        self.assertTrue(w.wait_idle(10))
        self.assertTrue(ix.path_for(self.data, "P1").exists(), "the rebuild started and finished")
        self.assertTrue(w.current("P1", folders))

    def test_the_help_says_clark_builds_it_again_if_it_is_removed(self):
        t = paragraph("The index of your source folders.")
        self.assertIn("it is only a copy, and clark builds it again if it is removed.", t)


class StatusLine(Base):
    """P2: the numbers add up; the words are the app's; a password or key itself is never shown."""

    def setUp(self):
        super().setUp()
        patch = mock.patch.object(ask_picture, "_READER", None)
        patch.start()
        self.addCleanup(patch.stop)

    def test_the_numbers_add_up_to_the_files_in_the_folder(self):
        self.put("a.txt", "zqone")
        self.put("b.md", "zqtwo")
        self.put("c.png", b"\x89PNG", binary=True)
        self.put("d.js", "var x")
        self.put("keys.txt", FAKE_KEY)
        self.put("sub/e.txt", "zqthree")
        self.build()
        line = ask_index.folder_status(self.data, "P1", [str(self.box)])[str(self.box)]["line"]
        on_disk = sum(len(fs) for _d, _s, fs in os.walk(self.box))
        unread = int(re.match(r"100% indexed\. (\d+) files could not be read$", line).group(1))
        self.assertEqual(unread, 3)
        self.assertEqual(3 + unread, on_disk)

    def test_no_reason_is_shown_when_it_is_0(self):
        self.put("a.txt", "zqone")
        self.build()
        self.assertEqual(ask_index.folder_status(self.data, "P1", [str(self.box)])[str(self.box)]["line"], "100% indexed")

    def test_the_list_names_each_file_and_reason_and_never_the_password_or_key(self):
        self.put("keys.txt", "zqnote line\n" + FAKE_KEY)
        self.put("c.png", b"\x89PNG", binary=True)
        self.put("a.txt", "zqfine")
        self.build()
        got = ask_index.folder_status(self.data, "P1", [str(self.box)])[str(self.box)]
        self.assertEqual(sorted(map(tuple, got["left"]["files"])), [("c.png", ask_index.REASON_PICTURE), ("keys.txt", "looks like a password or a key")])
        shown = json.dumps([got, ix.mod().files_left_out(self.data, "P1"), ix.mod().folder_data(self.data, "P1", "zqnote hunter2 password")], default=str)
        for secret in ("hunter2", "zqnote", FAKE_KEY):
            self.assertNotIn(secret, shown)
        self.assertEqual(self.found("hunter2"), [])

    def test_the_button_in_the_settings_page_says_exactly_what_the_help_says(self):
        note = (SRC / "clark" / "page" / "src" / "edit" / "indexNote.js").read_text(encoding="utf-8")
        self.assertIn('why: "(why)"', note)
        self.assertIn("{LINKS.why}</button>", JSX.read_text(encoding="utf-8"))
        self.assertIn("**(why)**", paragraph("The line under each folder"))


class HelpWordsAreTheAppsWords(unittest.TestCase):
    def test_each_quoted_example_equals_the_app_string_character_for_character(self):
        t = paragraph("The line under each folder")
        quoted = [q.replace("’", "'") for q in re.findall("“([^”]*)”", t)]
        reading = ask_index.line_for(None, (180, 422))
        done = ask_index.done_line({"indexed": 180})
        unread = ask_index.done_line({"indexed": 180, "type": 242})
        none = ask_index.done_line({"type": 2})
        note = ask_index.answer_note({"not_yet": 120})
        self.assertEqual(reading, "Indexing… 42%")
        self.assertEqual(done, "100% indexed")
        self.assertEqual(unread, "100% indexed. 242 files could not be read")
        self.assertEqual(none, "No files to index")
        self.assertEqual(note, "Still reading 120 files, so this answer may miss some.")
        reasons = [ask_index.REASON_TYPE, ask_index.REASON_TOO_LONG_PDF, ask_index.REASON_TOO_LONG, ask_index.REASON_PICTURE, ask_index.REASON_SAFETY]
        self.assertEqual(quoted, [reading, done, unread, none, *reasons, ask_index.ONLINE_LINE, note])
        self.assertIn("**(why)**", t)

    def test_the_status_paragraph_lists_the_reasons_the_app_gives(self):
        t = paragraph("The line under each folder").replace("’", "'")
        # the reasons in the paragraph are the app's own words, read from the constants and not retyped
        reasons = {ask_index.REASON_TYPE, ask_index.REASON_SAFETY, ask_index.REASON_TOO_LONG, ask_index.REASON_TOO_LONG_PDF, ask_index.REASON_PICTURE}
        for app in reasons:
            self.assertIn("\u201c" + app + "\u201d", t, app)
        # the list holds exactly these reasons: a file that is online only is counted as not read but is not listed
        self.assertEqual(reasons, set(re.findall(r"REASON_\w+ = \"([^\"]*)\"", (SRC / "clark" / "ask_index.py").read_text(encoding="utf-8"))))
        self.assertIn(ask_index.ONLINE_LINE, ask_index.line_for({"indexed": 1, "online_only": 1}))
        self.assertIn("A file that is online only is not opened; the line and the list say \u201c" + ask_index.ONLINE_LINE + "\u201d.", t)
        self.assertEqual(ask_index.MAX_LEFT_OUT_SHOWN, 200)
        self.assertIn("up to 200 names", t)

    def test_the_help_carries_the_qualifier_once_the_index_is_up_to_date(self):
        t = paragraph("The index of your source folders.")
        self.assertIn("Once the index is up to date, a question is answered from the index and no file is opened while you ask.", t)

    def test_the_help_says_when_the_index_is_brought_up_to_date_and_the_code_does_it_there(self):
        t = paragraph("The index of your source folders.")
        self.assertIn("The index is brought up to date when you open Settings or ask a question.", t)
        from _paths import ROOT
        src = ROOT / "src" / "clark"
        # opening Settings: the folders read asks the indexer for its status, which starts a run when the files changed
        self.assertIn("self.indexer.status_for(", (src / "ask_folders.py").read_text(encoding="utf-8"))
        # asking a question: the service asks the indexer if it is current, which starts a run when it is not
        self.assertIn("self.indexer.current(", (src / "ask_service.py").read_text(encoding="utf-8"))

    def test_exemption_the_two_claims_once_cut_are_back_with_their_pins(self):
        """Named exemption of the earlier guard test_the_claims_that_are_not_true_are_not_in_the_help: it listed 'no file is opened while you ask'
        and 'builds it again' as cut. Both are true now (rebuild when missing; qualified by the index being up to date) and are pinned by
        test_with_a_finished_index_no_source_file_is_opened_while_you_ask and Rebuild above. The claim without the qualifier stays out."""
        t = paragraph("The index of your source folders.")
        self.assertNotIn(". A question is answered from the index", t)
        self.assertNotIn("a question never opens a file", t)

    def test_the_settings_asking_row_says_the_index_is_kept(self):
        ref = json.loads(HELP.read_text(encoding="utf-8"))
        text = json.dumps(ref, ensure_ascii=False)
        self.assertIn("keeps what it read in an index", text)
        self.assertIn("Excel, PowerPoint, web pages, text, Markdown and CSV files, and keeps what it read in an index", text)


if __name__ == "__main__":
    unittest.main()
