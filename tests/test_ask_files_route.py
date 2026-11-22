"""#1292 S14: files added to a question, on the server (POST /api/ask with "files": [{name, data}], src/clark/ask_files.py).

Run: python3 dev/run_tests.py test_ask_files_route
A real server and store with a STUB provider (nothing here calls a model). Covers: a text, Markdown or CSV file is sent as a passage named by
its file name; a file with a key or a password line is refused before anything is sent; five files at most, 10 MB each; a name that is a path,
bytes that are not base64, a kind that cannot be read yet (PDF, Word, Excel, pictures: NEEDS RULING) and a wrong shape each say why and send
nothing; the files are not kept (no row written, no file on disk). Fictional text only.
"""
import base64
import os
import sqlite3
import unittest
from unittest import mock

from clark import ask_service
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
        self.assertEqual(len(self.sent()), 1, "only the plain question reached the AI")
        self.assertNotIn("ZQ-FILE-LINE", repr(self.sent()), "no file passage is in anything sent to the AI while the switch is off")

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


class Probe:
    """A connection that raises sqlite3.Error for any statement holding `needle` and passes every other one on."""

    def __init__(self, con, needle):
        self.con, self.needle = con, needle

    def execute(self, sql, *a):
        if self.needle in sql:
            raise sqlite3.OperationalError("probe")
        return self.con.execute(sql, *a)


def bare(*statements):
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    for sql in statements:
        con.execute(sql)
    return con


def store_of(con):
    """A Store around a bare connection (its constructor wants the whole schema; the flag reads only use `con`)."""
    from clark import store as st
    store = st.Store.__new__(st.Store)
    store.con = con
    return store


class TheFlagReads(unittest.TestCase):
    """Row 1294: store.ask_files_on / ask_files_off_here / ask_files_allowed on files that are odd, never failing open (columns with no type keep the value as written)."""

    def on(self, *statements, con=None):
        return store_of(con or bare(*statements)).ask_files_on()

    def off_here(self, project, *statements, con=None):
        return store_of(con or bare(*statements)).ask_files_off_here(project)

    def test_only_a_one_in_the_one_row_is_on(self):
        mk = "CREATE TABLE app_settings (id, ask_files)"
        for value, want in (("1", True), ("0", False), ("2", False), ("-1", False), ("NULL", False), ("'1'", False), ("1.5", False)):
            self.assertIs(self.on(mk, "INSERT INTO app_settings VALUES (1, %s)" % value), want, value)

    def test_a_missing_table_row_or_column_reads_as_off(self):
        self.assertIs(self.on("CREATE TABLE other (x)"), False)
        self.assertIs(self.on("CREATE TABLE app_settings (id, ask_files)"), False, "no row")
        self.assertIs(self.on("CREATE TABLE app_settings (id, ask_files)", "INSERT INTO app_settings VALUES (2, 1)"), False, "the row is not row 1")
        self.assertIs(self.on("CREATE TABLE app_settings (id, ask_enabled)", "INSERT INTO app_settings VALUES (1, 1)"), False, "no ask_files column")

    def test_a_database_error_reads_as_off(self):
        con = bare("CREATE TABLE app_settings (id, ask_files)", "INSERT INTO app_settings VALUES (1, 1)")
        self.assertIs(self.on(con=con), True)
        self.assertIs(self.on(con=Probe(con, "SELECT ask_files FROM")), False)
        self.assertIs(self.on(con=Probe(con, "PRAGMA")), False)
        self.assertIs(self.on(con=Probe(con, "sqlite_master")), False)

    def test_a_project_is_off_unless_its_own_flag_is_exactly_zero(self):
        mk = "CREATE TABLE projects (code, ask_files_off)"
        for value, want in (("0", False), ("1", True), ("2", True), ("NULL", True), ("'0'", True), ("0.5", True)):
            self.assertIs(self.off_here("P", mk, "INSERT INTO projects VALUES ('P', %s)" % value), want, value)

    def test_an_unknown_project_and_a_missing_column_read_as_off_here(self):
        mk = "CREATE TABLE projects (code, ask_files_off)"
        self.assertIs(self.off_here("NOPE", mk, "INSERT INTO projects VALUES ('P', 0)"), True)
        self.assertIs(self.off_here("P", "CREATE TABLE projects (code)", "INSERT INTO projects VALUES ('P')"), True)

    def test_a_database_error_reads_as_off_here(self):
        con = bare("CREATE TABLE projects (code, ask_files_off)", "INSERT INTO projects VALUES ('P', 0)")
        self.assertIs(self.off_here("P", con=con), False)
        self.assertIs(self.off_here("P", con=Probe(con, "SELECT ask_files_off")), True)
        self.assertIs(self.off_here("P", con=Probe(con, "PRAGMA")), True)

    def test_allowed_needs_the_switch_on_and_the_project_not_off(self):
        for on, off, want in ((1, 0, True), (1, 1, False), (0, 0, False), (0, 1, False)):
            con = bare("CREATE TABLE app_settings (id, ask_files)", "INSERT INTO app_settings VALUES (1, %d)" % on,
                       "CREATE TABLE projects (code, ask_files_off)", "INSERT INTO projects VALUES ('P', %d)" % off)
            store = store_of(con)
            self.assertIs(store.ask_files_allowed("P"), want, (on, off))
            self.assertIs(store.ask_files_allowed("NOPE"), False, "an unknown project")


class TheFilesRules(Base):
    """Row 1294: files_allowed in ask_service, the route's refusals, each answer's shape, Undo and the limits."""

    def setUp(self):
        super().setUp()
        from clark import app_settings
        self.service_settings = app_settings.AppSettings(self.db, [])
        self.s.httpd.app_settings = self.service_settings

    def sent(self):
        return self.provider.sent

    def api(self, method, body=None, query=""):
        return self.s.api(method, "/api/ask-files" + query, body)

    def flags(self, on=None, off_here=None, project="PUB"):
        from clark import store as st
        store = st.open_store(self.db, onedrive_roots=[])
        try:
            with store.step("dashboard", "tester", place="menu") as s:
                if on is not None:
                    s.update("app_settings", "1", {"ask_files": on})
                if off_here is not None:
                    s.update("projects", project, {"ask_files_off": off_here})
        finally:
            store.close()

    def sql(self, *statements):
        from clark import store as st
        con = st.connect(self.db)
        for q in statements:
            con.execute(q)
        con.commit()
        con.close()

    # files_allowed: fails closed
    def test_files_allowed_is_false_when_the_store_cannot_be_opened(self):
        for err in (sqlite3.OperationalError("x"), OSError("x"), TypeError("x")):
            with mock.patch.object(ask_service.AskService, "reader", side_effect=err):
                self.assertIs(self.service.files_allowed("PUB"), False, err)

    def test_files_allowed_is_false_when_the_store_cannot_say(self):
        with mock.patch("clark.store.Store.ask_files_allowed", side_effect=RuntimeError("x")):
            self.assertIs(self.service.files_allowed("PUB"), False)
            status, got = self.question(files=[f("a.txt", b"x")])
        self.assertEqual((status, got["code"]), (400, "refused"))
        self.assertEqual(self.sent(), [])

    def test_files_allowed_is_true_only_for_true_itself(self):
        for answer, want in ((True, True), (1, False), ("yes", False), (None, False), (False, False)):
            with mock.patch("clark.store.Store.ask_files_allowed", return_value=answer):
                self.assertIs(self.service.files_allowed("PUB"), want, answer)

    def test_files_allowed_follows_the_stored_flags(self):
        self.assertIs(self.service.files_allowed("PUB"), True)
        self.flags(off_here=1)
        self.assertIs(self.service.files_allowed("PUB"), False)
        self.assertIs(self.service.files_allowed("OTH"), True)
        self.flags(on=0)
        self.assertIs(self.service.files_allowed("OTH"), False)
        self.assertIs(self.service.files_allowed("NOPE"), False)

    def test_the_store_is_closed_after_the_read(self):
        closed = []
        real = ask_service.AskService.reader

        def reader(this):
            store = real(this)
            store.close = lambda orig=store.close: (closed.append(1), orig())[1]
            return store
        with mock.patch.object(ask_service.AskService, "reader", reader):
            self.service.files_allowed("PUB")
        self.assertEqual(closed, [1])

    def test_a_question_with_an_empty_list_or_none_does_not_read_the_flags(self):
        self.flags(on=0)
        with mock.patch.object(ask_service.AskService, "files_allowed", side_effect=AssertionError("not read")):
            self.assertEqual(self.question(files=[])[0], 200)
            self.assertEqual(self.question()[0], 200)

    def test_the_two_flags_in_every_combination_decide_a_question_with_files(self):
        for on, off, want in ((1, 0, 200), (1, 1, 400), (0, 0, 400), (0, 1, 400)):
            self.flags(on=on, off_here=off)
            status, got = self.question(files=[f("a.txt", b"x")])
            self.assertEqual(status, want, (on, off))
            if want == 400:
                self.assertEqual(got["message"], ThePassagesGate.WORDS, (on, off))
                self.assertNotIn("Reload", got["message"], (on, off))
            status, got = self.api("GET", query="?project=PUB")
            self.assertEqual((got["on"], got["off_here"], got["allowed"]), (bool(on), bool(off), want == 200), (on, off))

    # The read route
    def test_the_read_refuses_what_it_cannot_read_and_what_it_does_not_know(self):
        status, got = self.api("GET", query="?project=NOPE")
        self.assertEqual((status, got["code"]), (404, "bad_project"))
        for q in ("?project=bad%20code", "?project=", "?project=PUB&project=OTH", "?other=1"):
            status, got = self.api("GET", query=q)
            self.assertEqual((status, got["code"]), (400, "bad_project_code"), q)
        self.assertEqual(self.api("GET")[0], 200)

    def test_without_the_settings_service_both_routes_are_not_found(self):
        self.s.httpd.app_settings = None
        self.assertEqual(self.api("GET")[0], 404)
        self.assertEqual(self.api("POST", {"on": False})[0], 404)

    def test_busy_when_the_store_cannot_be_opened(self):
        from clark.store import Invalid
        with mock.patch.object(type(self.service_settings), "store", side_effect=Invalid("x")):
            for status, got in (self.api("GET"), self.api("POST", {"on": False}), self.api("POST", {"project": "PUB", "off_here": True})):
                self.assertEqual((status, got["code"]), (409, "busy"))
            self.assertEqual(self.api("POST", {"undo": 1})[1]["code"], "busy")

    def test_a_file_that_cannot_keep_the_flag_says_not_ready_and_changes_nothing(self):
        self.sql("DELETE FROM app_settings")
        status, got = self.api("GET")
        self.assertEqual((status, got["on"], got["saved"]), (200, False, False))
        for body in ({"on": False}, {"project": "PUB", "off_here": True}, {"undo": 1}):
            status, got = self.api("POST", body)
            self.assertEqual((status, got["code"]), (409, "not_ready"), body)

    def test_a_file_without_the_column_says_not_ready(self):
        self.sql("ALTER TABLE app_settings RENAME COLUMN ask_files TO ask_files_x")
        status, got = self.api("GET")
        self.assertEqual((status, got["on"], got["saved"]), (200, False, False))
        self.assertEqual(self.api("POST", {"on": False})[1]["code"], "not_ready")
        self.assertEqual(self.api("POST", {"undo": 1})[1]["code"], "not_ready")

    def test_a_store_that_refuses_the_step_says_it_could_not_save(self):
        with mock.patch.object(type(self.service_settings), "save", return_value=False):
            self.assertEqual(self.api("POST", {"on": False})[1]["code"], "cant_save")
            self.assertEqual(self.api("POST", {"project": "PUB", "off_here": True})[1]["code"], "cant_save")
        self.assertEqual(self.api("GET", query="?project=PUB")[1]["allowed"], True, "nothing was changed")

    # The POST: each refusal and each answer
    def test_each_wrong_request_gets_its_own_refusal(self):
        for body, code in (({"on": 1}, "bad_value"), ({"on": None}, "bad_value"), ({"on": "true"}, "bad_value"),
                           ({"project": "PUB", "off_here": "no"}, "bad_value"), ({"project": "PUB", "off_here": 0}, "bad_value"),
                           ({"project": "bad code", "off_here": True}, "bad_project"), ({"project": 5, "off_here": True}, "bad_project"),
                           ({"project": None, "off_here": True}, "bad_project"), ({"project": "PUB"}, "bad_request"), ({"off_here": True}, "bad_request"),
                           ({"on": True, "undo": 1}, "bad_request"), ({}, "bad_request"), ({"undo": 0}, "no_undo"), ({"undo": "1"}, "no_undo"),
                           ({"undo": True}, "no_undo"), ({"undo": 2 ** 63}, "no_undo"), ({"undo": -1}, "no_undo"), ({"undo": 1.0}, "no_undo")):
            status, got = self.api("POST", body)
            self.assertEqual((status, got["code"]), (400, code), body)
        self.assertEqual(self.api("GET", query="?project=PUB")[1]["allowed"], True, "nothing was changed")

    def test_a_body_that_is_not_an_object_is_a_bad_request(self):
        for body in ([], "on", 1, None):
            status, got = self.service_settings.change_files(body)
            self.assertEqual((status, got["code"]), (400, "bad_request"), body)

    def test_an_unknown_project_is_not_found_and_a_known_one_is_changed(self):
        status, got = self.api("POST", {"project": "NOPE", "off_here": True})
        self.assertEqual((status, got["code"]), (404, "bad_project"))
        self.assertEqual(self.api("POST", {"project": "OTH", "off_here": True})[0], 200)
        self.assertEqual(self.api("GET", query="?project=OTH")[1]["off_here"], True)
        self.assertEqual(self.api("GET", query="?project=PUB")[1]["off_here"], False)

    def test_a_change_answers_with_its_step_and_no_message(self):
        status, got = self.api("POST", {"on": False})
        self.assertEqual(status, 200)
        self.assertEqual(sorted(got), ["allowed", "apply_id", "off_here", "ok", "on", "saved"])
        self.assertEqual((got["ok"], got["saved"], got["on"], got["off_here"], got["allowed"]), (True, True, False, False, False))
        self.assertIsInstance(got["apply_id"], int)
        status, got = self.api("POST", {"on": True})
        self.assertEqual((got["on"], got["saved"]), (True, True))
        status, got = self.api("POST", {"project": "PUB", "off_here": True})
        self.assertEqual(sorted(got), ["allowed", "apply_id", "off_here", "ok", "on", "saved"])
        self.assertEqual((got["on"], got["off_here"], got["allowed"]), (True, True, False))

    def test_the_same_setting_again_says_so_and_writes_no_step(self):
        same = "That is the setting already in use."
        before = self.counts()
        status, got = self.api("POST", {"on": True})
        self.assertEqual((status, got["message"], "apply_id" in got, got["on"]), (200, same, False, True))
        status, got = self.api("POST", {"project": "PUB", "off_here": False})
        self.assertEqual((status, got["message"], "apply_id" in got, got["allowed"]), (200, same, False, True))
        self.assertEqual(self.counts(), before)
        self.flags(on=0, off_here=1)
        before = self.counts()
        self.assertEqual(self.api("POST", {"on": False})[1]["message"], same)
        self.assertEqual(self.api("POST", {"project": "PUB", "off_here": True})[1]["message"], same)
        self.assertEqual(self.counts(), before)

    def test_undo_answers_undone_and_puts_the_flag_back(self):
        step = self.api("POST", {"project": "PUB", "off_here": True})[1]["apply_id"]
        status, got = self.api("POST", {"undo": step})
        self.assertEqual((status, got["message"], "apply_id" in got, got["off_here"], got["allowed"], got["saved"]), (200, "Undone.", False, False, True, True))
        status, got = self.api("POST", {"undo": step})
        self.assertEqual((status, got["code"]), (409, "no_undo"), "a step already undone")
        step = self.api("POST", {"on": False})[1]["apply_id"]
        status, got = self.api("POST", {"undo": step})
        self.assertEqual((status, got["message"], got["on"], got["off_here"], got["allowed"]), (200, "Undone.", True, False, False), "no project: nothing is allowed there")

    def test_undo_takes_only_this_switchs_own_steps(self):
        from clark import store as st
        store = st.open_store(self.db, onedrive_roots=[])
        try:
            def step(route, *changes):
                with store.step(route, "tester", place="menu") as s:
                    for table, key, fields in changes:
                        s.update(table, key, fields)
                    return s.peek_apply_id()
            other = step("dashboard", ("app_settings", "1", {"ask_enabled": 0}))
            mixed = step("dashboard", ("app_settings", "1", {"ask_files": 0}), ("projects", "PUB", {"ask_files_off": 1}), ("projects", "OTH", {"ask_files_off": 1}))
            elsewhere = step("dashboard", ("projects", "PUB", {"name": "Renamed"}))
            imported = step("excel", ("app_settings", "1", {"ask_files": 1}))
            both = step("dashboard", ("app_settings", "1", {"ask_files": 0}), ("projects", "PUB", {"ask_files_off": 0}))
        finally:
            store.close()
        for bad in (other, mixed, elsewhere, imported, 999999):
            status, got = self.api("POST", {"undo": bad})
            self.assertEqual((status, got["code"]), (409, "no_undo"), (bad, got))
        from clark import store as st2
        con = st2.connect(self.db, readonly=True)
        self.assertEqual(con.execute("SELECT ask_enabled FROM app_settings").fetchone()[0], 0, "the other setting was not touched")
        con.close()
        status, got = self.api("POST", {"undo": both})
        self.assertEqual((status, got["message"], got["on"], got["off_here"]), (200, "Undone.", True, True))

    def test_undo_refuses_a_step_from_another_route_that_really_changed_the_flag(self):
        # The step is the latest change of the flag and nothing else blocks the undo, so only the
        # "written from the dashboard" check can refuse it.
        from clark import store as st
        store = st.open_store(self.db, onedrive_roots=[])
        try:
            with store.step("excel", "tester", place="menu") as s:
                s.update("app_settings", "1", {"ask_files": 0})
                imported = s.peek_apply_id()
        finally:
            store.close()
        self.assertEqual(self.api("GET")[1]["on"], False, "the import really turned the flag off")
        status, got = self.api("POST", {"undo": imported})
        self.assertEqual((status, got["code"]), (409, "no_undo"), got)
        self.assertEqual(self.api("GET")[1]["on"], False, "the refused undo left the flag as it was")

    def test_a_refused_undo_does_not_change_the_flags(self):
        self.flags(on=0)
        self.assertEqual(self.api("POST", {"undo": 999999})[0], 409)
        self.assertEqual(self.api("GET")[1]["on"], False)

    # Killers (row 1294 mutation sweep)
    def test_a_code_with_a_tail_is_refused_by_the_read_and_the_post_and_the_route(self):
        for bad in ("PUB!", "PUB ", "PUB\n", "!PUB"):
            status, got = self.service_settings.read_files(bad)
            self.assertEqual((status, got["code"]), (400, "bad_project"), repr(bad))
            status, got = self.service_settings.change_files({"project": bad, "off_here": True})
            self.assertEqual((status, got["code"]), (400, "bad_project"), repr(bad))
        for bad in (5, ["PUB"], b"PUB"):
            self.assertEqual(self.service_settings.read_files(bad)[0], 400, repr(bad))
        for q in ("?project=PUB%21", "?project=PUB%0A", "?project=%21PUB"):
            status, got = self.api("GET", query=q)
            self.assertEqual((status, got["code"]), (400, "bad_project_code"), q)

    def test_an_undo_the_store_does_not_carry_out_is_refused_with_409(self):
        from clark.store import Invalid
        step = self.api("POST", {"on": False})[1]["apply_id"]
        for result in ({}, {"reversed": 0}, {"reversed": False}):
            with mock.patch("clark.store.Store.undo", return_value=result):
                status, got = self.api("POST", {"undo": step})
            self.assertEqual((status, got["code"]), (409, "no_undo"), result)
        with mock.patch("clark.store.Store.undo", side_effect=Invalid("x")):
            status, got = self.api("POST", {"undo": step})
        self.assertEqual((status, got["code"]), (409, "no_undo"))
        self.assertEqual(self.api("GET")[1]["on"], False, "nothing was undone")

    def test_a_save_the_store_refuses_is_409_for_both_flags(self):
        with mock.patch.object(type(self.service_settings), "save", return_value=False):
            self.assertEqual(self.api("POST", {"on": False})[0], 409)
            self.assertEqual(self.api("POST", {"project": "PUB", "off_here": True})[0], 409)

    def test_a_project_turned_off_is_turned_back_on_by_the_post(self):
        self.flags(off_here=1)
        status, got = self.api("POST", {"project": "PUB", "off_here": False})
        self.assertEqual((status, got["off_here"], got["allowed"]), (200, False, True))
        self.assertEqual(self.question(files=[f("a.txt", b"x")])[0], 200)
        self.flags(on=0)
        status, got = self.api("POST", {"on": True})
        self.assertEqual((status, got["on"]), (200, True))
        self.assertEqual(self.question(files=[f("a.txt", b"x")])[0], 200)

    # The limits and the save paths
    def test_the_route_takes_a_small_body_and_a_write_is_a_save_path(self):
        from clark import server
        self.assertEqual(server.ROUTE_BODY_LIMITS["/api/ask-files"], 1024)
        self.assertIn("/api/ask-files", server.SAVE_PATHS)
        self.assertNotIn("/api/ask-files", server.PUBLISH_PATHS)
        self.assertEqual(self.s.api("POST", "/api/ask-files", b'{"on": false}' + b" " * 1011)[0], 200, "1024 bytes are taken")
        self.assertNotEqual(self.s.api("POST", "/api/ask-files", b'{"on": true}' + b" " * 1013)[0], 200, "1025 are not")


class ThePassagesGate(unittest.TestCase):
    """Row 1294: ask_files.passages(files, allowed) with the Files switch off."""
    WORDS = "Files are turned off for asking, so none were sent. Turn them on in Settings, or ask again without them."

    def test_with_the_switch_off_any_file_is_refused_in_one_set_of_words(self):
        from clark import ask, ask_files
        for files in ([f("a.txt", b"x")], [f("a.pdf", b"x")], ["junk"], "a.txt", 7, [f("a.txt", b"x")] * 9):
            with self.assertRaises(ask.AskRefused) as caught:
                ask_files.passages(files, False)
            self.assertEqual(str(caught.exception), self.WORDS, files)

    def test_with_the_switch_on_a_wrong_shape_keeps_the_reload_words_and_the_off_words_are_not_them(self):
        from clark import ask, ask_files
        with self.assertRaises(ask.AskRefused) as caught:
            ask_files.passages("a.txt", True)
        self.assertEqual(str(caught.exception), "The files could not be read. Nothing was sent. Reload the page and ask again.")
        self.assertNotEqual(self.WORDS, str(caught.exception))

    def test_with_the_switch_off_no_file_is_still_no_file(self):
        from clark import ask_files
        self.assertEqual(ask_files.passages(None, False), [])
        self.assertEqual(ask_files.passages([], False), [])

    def test_with_the_switch_on_the_files_are_read_and_the_default_is_on(self):
        from clark import ask_files
        self.assertEqual([p.label for p in ask_files.passages([f("a.txt", b"x")], True)], ["a.txt"])
        self.assertEqual([p.label for p in ask_files.passages([f("a.txt", b"x")])], ["a.txt"])


class TheMigration(unittest.TestCase):
    """Row 1294: schema step 33 adds the two columns once, keeps every value and skips a missing table."""

    def run_step(self, con):
        from clark import store as st
        st.migrate_ask_files(con)
        return con

    def test_the_two_columns_are_added_with_their_defaults_and_a_second_run_changes_nothing(self):
        from clark import store as st
        con = bare("CREATE TABLE app_settings (id INTEGER, ask_enabled INTEGER)", "INSERT INTO app_settings VALUES (1, 0)",
                   "CREATE TABLE projects (code TEXT)", "INSERT INTO projects VALUES ('P')")
        self.run_step(con)
        self.run_step(con)
        self.assertEqual(st.columns(con, "app_settings"), ["id", "ask_enabled", "ask_files", "ask_new_projects"])
        self.assertEqual(st.columns(con, "projects"), ["code", "ask_files_off", "ask_off"])
        self.assertEqual(tuple(con.execute("SELECT id, ask_enabled, ask_files FROM app_settings").fetchone()), (1, 0, 1))
        self.assertEqual(tuple(con.execute("SELECT code, ask_files_off FROM projects").fetchone()), ("P", 0))
        with self.assertRaises(sqlite3.IntegrityError):
            con.execute("UPDATE app_settings SET ask_files = 2")
        with self.assertRaises(sqlite3.IntegrityError):
            con.execute("UPDATE projects SET ask_files_off = 2")

    def test_a_column_already_there_keeps_its_value_and_a_missing_table_is_skipped(self):
        from clark import store as st
        con = bare("CREATE TABLE app_settings (id INTEGER, ask_files INTEGER NOT NULL DEFAULT 1 CHECK (ask_files IN (0,1)))", "INSERT INTO app_settings VALUES (1, 0)")
        self.run_step(con)
        self.assertEqual(con.execute("SELECT ask_files FROM app_settings").fetchone()[0], 0)
        self.assertEqual(st.columns(con, "app_settings"), ["id", "ask_files", "ask_new_projects"])
        self.assertEqual([r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")], ["app_settings"], "no projects table was made")

    def test_the_step_is_number_33_in_the_list(self):
        from clark import store as st
        self.assertEqual(st.ASK_FILES_STEP, 33)
        self.assertIn((33, st.migrate_ask_files), st.MIGRATIONS)


if __name__ == "__main__":
    unittest.main()
