"""#1292 S14: files added to a question, on the server (POST /api/ask with "files": [{name, data}], src/clark/ask_files.py).

Run: python3 dev/run_tests.py test_ask_files_route
A real server and store with a STUB provider (nothing here calls a model). Covers: a text, Markdown or CSV file is sent as a passage named by
its file name; a file with a key or a password line is refused before anything is sent; five files at most, 10 MB each; a name that is a path,
bytes that are not base64, a kind that cannot be read yet (PDF, Word, Excel, pictures: NEEDS RULING) and a wrong shape each say why and send
nothing; the files are not kept (no row written, no file on disk). Fictional text only.
"""
import base64
import os
import unittest

from test_ask_route import Base

MB = 1024 * 1024


def f(name, text=b"", raw=None):
    return {"name": name, "data": base64.b64encode(raw if raw is not None else text).decode()}


LEAKY_NAME = "pass" + "word=Hunter2xyz99.txt"     # built in two pieces: the CI scan reads a literal password line as a real one


class Files(Base):
    def sent(self):
        return self.provider.sent

    def test_a_text_file_is_sent_as_a_passage_named_by_its_file(self):
        status, got = self.question("What does my note say?", files=[f("notes.txt", b"ZQ-FILE-LINE the vendor moved to March")])
        self.assertEqual(status, 200, got)
        (text,) = self.sent()
        self.assertIn("ZQ-FILE-LINE the vendor moved to March", text)
        self.assertIn("notes.txt", text)

    def test_markdown_and_csv_are_read_too(self):
        status, got = self.question(files=[f("a.md", b"# ZQ-MD-HEAD"), f("b.csv", b"id,ZQ-CSV-CELL\n1,2")])
        self.assertEqual(status, 200, got)
        self.assertIn("ZQ-MD-HEAD", self.sent()[0])
        self.assertIn("ZQ-CSV-CELL", self.sent()[0])

    def test_a_file_with_a_password_line_is_refused_and_nothing_is_sent(self):
        status, got = self.question(files=[f("ok.txt", b"fine"), f("conf.txt", b"db pass" + b"word: Hunter2xyz99!")])
        self.assertEqual(status, 400, got)
        self.assertEqual(got["code"], "refused")
        self.assertEqual(self.sent(), [])
        self.assertNotIn("Hunter2", got["message"])
        self.assertIn("conf.txt", got["message"])

    def test_a_private_key_block_is_refused(self):
        status, got = self.question(files=[f("k.txt", b"-----BEGIN " + b"PRIVATE KEY-----\nMIIEvQIBADANBg\n-----END " + b"PRIVATE KEY-----")])
        self.assertEqual(status, 400, got)
        self.assertEqual(self.sent(), [])

    def test_five_files_are_taken_six_are_not(self):
        five = [f("f%d.txt" % i, b"line %d" % i) for i in range(5)]
        self.assertEqual(self.question(files=five)[0], 200)
        status, got = self.question(files=five + [f("g.txt", b"x")])
        self.assertEqual(status, 400, got)
        self.assertEqual(len(self.sent()), 1)

    def test_ten_mb_is_the_most_for_a_file(self):
        status, got = self.question(files=[f("big.txt", raw=b"a " * (5 * MB) + b"a")])
        self.assertEqual(status, 400, got)
        self.assertIn("big.txt", got["message"])
        self.assertEqual(self.sent(), [])

    def test_a_name_that_is_a_path_is_refused(self):
        for name in ("../x.txt", "/etc/x.txt", "a\\b.txt", "~/x.txt", ""):
            status, got = self.question(files=[f(name, b"x")])
            self.assertEqual(status, 400, name)
        self.assertEqual(self.sent(), [])

    def test_bytes_that_are_not_base64_are_refused(self):
        status, got = self.question(files=[{"name": "a.txt", "data": "!!not base64!!"}])
        self.assertEqual(status, 400, got)
        self.assertEqual(self.sent(), [])

    def test_a_wrong_shape_is_refused(self):
        for bad in ("a.txt", [1], [{"name": "a.txt"}], [{"name": "a.txt", "data": "eA==", "x": 1}], {"name": "a.txt"}):
            status, got = self.question(files=bad)
            self.assertEqual(status, 400, bad)
        self.assertEqual(self.sent(), [])

    def test_a_kind_that_cannot_be_read_yet_says_so(self):          # NEEDS RULING: PDF, Word, Excel and pictures need a reader or the command's picture support
        for name in ("a.pdf", "a.docx", "a.xlsx", "a.png", "a.jpg"):
            status, got = self.question(files=[f(name, b"x")])
            self.assertEqual(status, 400, name)
            self.assertIn("cannot be read yet", got["message"], name)
            self.assertIn("Nothing was sent", got["message"], name)
        self.assertEqual(self.sent(), [])

    def test_an_empty_list_is_the_same_as_none(self):
        self.assertEqual(self.question(files=[])[0], 200)

    def test_the_gate_still_comes_first(self):
        self.set_switch(False)
        status, got = self.question(files=[f("a.txt", b"x")])
        self.assertEqual(status, 409, got)
        self.assertEqual(self.sent(), [])

    def test_nothing_is_kept(self):
        before = self.counts()
        self.question(files=[f("keep.txt", b"ZQ-NOT-KEPT")])
        self.assertEqual(self.counts(), before)
        for root, _dirs, names in os.walk(self.d):
            for n in names:
                self.assertNotEqual(n, "keep.txt")

    # Killers (#1292 S14 mutation sweep)
    def test_a_name_with_a_slash_in_it_is_refused(self):
        status, got = self.question(files=[f("a/b.txt", b"x")])
        self.assertEqual(status, 400, got)
        self.assertEqual(self.sent(), [])

    def test_a_secret_in_the_file_name_alone_is_refused_naming_the_file(self):
        status, got = self.question(files=[f(LEAKY_NAME, b"harmless words")])
        self.assertEqual(status, 400, got)
        self.assertEqual(self.sent(), [])
        self.assertNotIn("Hunter2", got["message"].replace(LEAKY_NAME, ""))

    def test_a_kind_that_is_not_text_at_all_is_refused_in_the_same_words(self):
        for name in ("a.exe", "noextension", "a.txt.exe", "a.txtx", "a.md.pdf"):
            status, got = self.question(files=[f(name, b"x")])
            self.assertEqual(status, 400, name)
            self.assertIn("cannot be read yet", got["message"], name)
        self.assertEqual(self.sent(), [])

    def test_the_kind_is_judged_in_any_letter_case(self):
        status, got = self.question(files=[f("NOTES.TXT", b"ZQ-UPPER-OK"), f("Plan.Md", b"x"), f("T.CsV", b"y")])
        self.assertEqual(status, 200, got)
        self.assertIn("ZQ-UPPER-OK", self.sent()[0])

    def test_bytes_that_are_not_base64_are_refused_even_when_a_strict_reader_would_skip_the_stray_mark(self):
        status, got = self.question(files=[{"name": "a.txt", "data": "e!A=="}])
        self.assertEqual(status, 400, got)
        self.assertIn("could not be read", got["message"])
        self.assertEqual(self.sent(), [])

    def test_a_huge_body_is_refused_for_its_size_before_it_is_decoded(self):
        status, got = self.question(files=[{"name": "a.txt", "data": "!" * (14 * MB)}])
        self.assertEqual(status, 400, got)
        self.assertIn("over 10 MB", got["message"])

    def test_exactly_ten_mb_is_not_refused_for_its_size(self):          # the rule itself (a 10 MB body through the whole route is too slow for a test)
        from clark import ask, ask_files
        (one,) = ask_files.passages([f("ten.txt", raw=b"\n" * (10 * MB))])
        self.assertEqual(one.label, "ten.txt")
        with self.assertRaises(ask.AskRefused) as caught:
            ask_files.passages([f("ten.txt", raw=b"\n" * (10 * MB + 1))])
        self.assertIn("over 10 MB", str(caught.exception))

    def test_a_file_that_is_not_valid_utf8_is_still_read(self):
        status, got = self.question(files=[f("latin.txt", raw=b"ZQ-LATIN caf\xe9 ok")])
        self.assertEqual(status, 200, got)
        self.assertIn("ZQ-LATIN", self.sent()[0])

    def test_the_whole_text_of_a_file_is_sent_not_its_start(self):
        status, got = self.question(files=[f("long.txt", raw=b"ordinary words here. " * 40 + b"ZQ-LAST-LINE")])
        self.assertEqual(status, 200, got)
        self.assertIn("ZQ-LAST-LINE", self.sent()[0])

    def test_a_value_of_the_wrong_type_is_a_plain_refusal_not_a_crash(self):
        for bad in (7, True, 1.5, [{"name": "a.txt", "data": 5}], [{"name": "a.txt", "data": None}]):
            status, got = self.question(files=bad)
            self.assertEqual(status, 400, bad)
            self.assertEqual(got["code"], "refused", bad)
        self.assertEqual(self.sent(), [])

    def test_the_ask_route_takes_a_question_and_five_full_files(self):
        from clark import ask_files, server
        full = ask_files.FILE_MAX * (ask_files.FILE_BYTES * 4 // 3 + 8)          # five files of 10 MB, in base64
        limit = server.ROUTE_BODY_LIMITS["/api/ask"]
        self.assertGreaterEqual(limit, 128 * 1024 + full)
        self.assertLess(limit, 128 * 1024 + full + 6 * MB)          # and not much more


    def test_the_ask_body_limit_is_exact_and_the_other_ask_routes_stay_small(self):
        from clark import server
        # 128 KiB for the question + five files, each 10 MB in base64 (13,981,013 bytes) and 1024 bytes of envelope
        self.assertEqual(server.ASK_BODY_LIMIT, 131072 + 5 * (13981013 + 1024))
        self.assertEqual(server.ROUTE_BODY_LIMITS["/api/ask"], server.ASK_BODY_LIMIT)
        for route in ("/api/ask/stop", "/api/ask/change/dry", "/api/ask/change/apply", "/api/ask/open-source", "/api/ask-folders", "/api/ask-enabled"):
            self.assertLessEqual(server.ROUTE_BODY_LIMITS[route], 4096, route)


class TheFilesSwitch(Base):
    """Row 1294: the Files switch (all projects) and a project's own turn-off. It is read again for every question that carries files."""

    def setUp(self):
        super().setUp()
        from clark import app_settings
        self.s.httpd.app_settings = app_settings.AppSettings(self.db, [])

    def sent(self):
        return self.provider.sent

    def flags(self, on=None, off_here=None):
        from clark import store as st
        store = st.open_store(self.db, onedrive_roots=[])
        try:
            with store.step("dashboard", "tester", place="menu") as s:
                if on is not None:
                    s.update("app_settings", "1", {"ask_files": on})
                if off_here is not None:
                    s.update("projects", "PUB", {"ask_files_off": off_here})
        finally:
            store.close()

    def test_files_are_on_for_a_new_file_and_the_route_says_so(self):
        self.assertEqual(self.s.api("GET", "/api/ask-files?project=PUB")[1]["allowed"], True)
        status, got = self.s.api("GET", "/api/ask-files")
        self.assertEqual((status, got["on"], got["off_here"], got["allowed"]), (200, True, False, False), "no project: nothing is allowed there")

    def test_the_switch_off_refuses_every_file_and_sends_nothing(self):
        self.flags(on=0)
        status, got = self.question(files=[f("notes.txt", b"ZQ-FILE-LINE")])
        self.assertEqual((status, got["code"]), (400, "refused"), got)
        self.assertEqual(self.sent(), [])
        self.assertEqual(self.question("A plain question")[0], 200, "a question without files still goes")

    def test_a_project_turned_off_refuses_files_and_another_project_still_takes_them(self):
        self.flags(off_here=1)
        self.assertEqual(self.question(files=[f("notes.txt", b"ZQ-FILE-LINE")])[0], 400)
        self.assertEqual(self.sent(), [])
        self.assertEqual(self.question(project="OTH", files=[f("notes.txt", b"ZQ-FILE-LINE")])[0], 200)

    def test_the_post_sets_each_flag_with_one_undo_and_refuses_anything_else(self):
        api = self.s.api
        status, got = api("POST", "/api/ask-files", {"on": False})
        self.assertEqual((status, got["on"], got["allowed"]), (200, False, False))
        status, undone = api("POST", "/api/ask-files", {"undo": got["apply_id"]})
        self.assertEqual((status, undone["on"]), (200, True))
        status, got = api("POST", "/api/ask-files", {"project": "PUB", "off_here": True})
        self.assertEqual((status, got["off_here"], got["allowed"]), (200, True, False))
        self.assertEqual(api("POST", "/api/ask-files", {"undo": got["apply_id"]})[1]["off_here"], False)
        self.assertEqual(api("POST", "/api/ask-files", {"on": "yes"})[0], 400)
        self.assertEqual(api("POST", "/api/ask-files", {"on": True, "extra": 1})[0], 400)
        self.assertEqual(api("POST", "/api/ask-files", {"project": "NOPE", "off_here": True})[0], 404)
        self.assertEqual(api("POST", "/api/ask-files", {"undo": 999999})[0], 409)
        self.assertEqual(api("GET", "/api/ask-files?project=PUB&x=1")[0], 400)

    def test_a_file_that_cannot_say_reads_as_off(self):
        from clark import store as st
        con = st.connect(self.db)
        con.execute("UPDATE app_settings SET ask_files = 0")
        con.close()
        reader = st.Store(st.connect(self.db, readonly=True), self.db, [])
        self.assertEqual((reader.ask_files_on(), reader.ask_files_allowed("PUB"), reader.ask_files_off_here("NOPE")), (False, False, True))
        reader.close()


if __name__ == "__main__":
    unittest.main()
