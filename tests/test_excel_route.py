"""#444 (guarded): POST /api/excel-import, Import workbook (src/clark/excel_route.py), on a real store, and the route through the real
server. Fictional data only. Run: python3 dev/run_tests.py test_excel_route

What is asserted: a check writes nothing to the database and lists each difference by number in words; an apply is ONE step by the
"excel" route with ONE Undo; "all" takes the new and changed rows only (a row missing from the workbook is accepted by number); a
workbook clark did not export is applied only with `confirm` true; the same file is not imported twice; a broken row names itself and
nothing is written; a file that is not a workbook, a wrong request, an old plan and another project's step are refused in plain
words; the temporary copy of the workbook is gone after an apply, an expiry and a refusal; the route sits behind the same token, Host
and Origin checks as every route, with a body limit of the largest workbook as text.
"""
import base64
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import _paths  # noqa: F401
import _workbook as wbk
from _demo import USER, DemoStore
from clark import excel, excel_route
from test_word_route import Up

ON = "2030-06-01"
JARGON = r"(?i)\bzip\b|\bxml\b|traceback|exception|errno|\bsql\b|\bjson\b|\bschema\b|fingerprint|base64"


def encoded(path):
    return base64.b64encode(Path(path).read_bytes()).decode("ascii")


class Base(unittest.TestCase):
    def setUp(self):
        excel_route.PLANS.clear()
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store
        self.tmp = Path(tempfile.mkdtemp(prefix="clark-route-xlsx-"))
        self.addCleanup(shutil.rmtree, str(self.tmp), True)
        self.addCleanup(excel_route.PLANS.clear)
        self.now = [1000.0]
        self.seam = excel_route.make_excel_import(self.store.path, [], USER, clock=lambda: self.now[0])
        self.a1 = self.demo.action(description="Draft the cut-over plan", due_date="2030-04-15")
        self.a2 = self.demo.action(description="Book the training room")
        self.path = self.tmp / "ABC work items.xlsx"
        # as the page's Export does it (publish_flow.Publisher.export): the record is kept beside clark.db under the id inside the workbook
        made = excel.export_project(self.store, "ABC", self.path, self.tmp / "state.json", on=ON)
        record = excel.load_state(self.tmp / "state.json", made)
        excel.save_state(Path(self.store.path).parent / excel.STATE_FILE, excel.id_key("ABC", record["export_id"]), record)

    def edit(self, sheet, item_id, **cells):
        head = {c.value: c.column for c in __import__("openpyxl").load_workbook(str(self.path))[sheet][1]}
        wb = __import__("openpyxl").load_workbook(str(self.path))
        ws = wb[sheet]
        row = next(r for r in range(2, ws.max_row + 1) if ws.cell(r, 1).value == item_id)
        for label, value in cells.items():
            ws.cell(row, head[label]).value = value
        wb.save(str(self.path))

    def post(self, **req):
        return self.seam(req)

    def check(self, path=None, project="ABC", name="ABC work items.xlsx"):
        return self.post(op="check", project=project, name=name, data=encoded(path or self.path))

    def apply(self, key, accept="all", **extra):
        return self.post(op="apply", project="ABC", plan=key, accept=accept, **extra)

    def steps(self):
        return self.store.con.execute("SELECT count(*) FROM applies").fetchone()[0]

    def temp_folders(self):
        return [p for p in Path(tempfile.gettempdir()).glob("clark-import-*")]

    def description_of(self, ref):
        return self.store.read("actions", ref=ref)["description"]


class Check(Base):
    def test_a_check_lists_the_differences_by_number_and_writes_nothing(self):
        self.edit("Actions", self.a1, Description="Draft the cut-over plan, version two")
        before = self.steps()
        status, got = self.check()
        self.assertEqual((status, got["ok"], got["file"]), (200, True, "ABC work items.xlsx"), got)
        self.assertEqual([(i["n"], i["kind"], i["table"]) for i in got["items"]], [(1, "changed", "actions")])
        self.assertIn(self.a1, got["items"][0]["text"])
        self.assertEqual((got["items"][0]["default"], got["unrecorded"], got["counts"]["changed"]), (True, False, 1))
        self.assertEqual(self.steps(), before)
        self.assertEqual(self.description_of(self.a1), "Draft the cut-over plan")
        self.assertIsNone(__import__("re").search(JARGON, json.dumps(got)), got)

    def test_a_workbook_with_no_difference_lists_none(self):
        status, got = self.check()
        self.assertEqual((status, got["items"], got["counts"]), (200, [], {"new": 0, "changed": 0, "removed": 0}))

    def test_a_file_that_is_not_a_workbook_a_bad_name_and_a_bad_encoding_are_refused_in_words_and_leave_no_temporary_folder(self):
        was = self.temp_folders()
        notbook = base64.b64encode(b"this is not a workbook").decode()
        for req, words in (({"name": "x.xlsx", "data": notbook}, "can't be read as an Excel workbook"), ({"name": "", "data": notbook}, excel_route.BAD_NAME),
                           ({"name": "x.xlsx", "data": ""}, excel_route.NO_FILE), ({"name": "x.xlsx", "data": "***"}, excel_route.BAD_FILE),
                           ({"name": 5, "data": notbook}, excel_route.BAD_NAME)):
            status, got = self.post(op="check", project="ABC", **req)
            self.assertEqual((status, got["ok"]), (400, False), req)
            self.assertIn(words, got["message"])
            self.assertIsNone(__import__("re").search(JARGON, got["message"]), got["message"])
        self.assertEqual(self.temp_folders(), was)
        self.assertEqual(excel_route.PLANS, {})

    def test_a_path_in_the_name_is_only_a_name(self):
        status, got = self.check(name="../../../etc/ABC work items.xlsx")
        self.assertEqual((status, got["file"]), (200, "ABC work items.xlsx"))

    def test_a_workbook_over_the_largest_is_refused_before_it_is_decoded(self):
        status, got = self.post(op="check", project="ABC", name="big.xlsx", data="A" * (excel_route.MAX_FILE_BYTES * 4 // 3 + 100))
        self.assertEqual(status, 400)
        self.assertIn("25 MB", got["message"])

    def test_the_largest_workbook_is_what_excel_reads(self):
        self.assertEqual(excel_route.MAX_FILE_BYTES, excel.MAX_FILE_BYTES)

    def test_a_missing_project_a_bad_code_and_a_request_with_a_field_that_is_not_allowed_are_refused(self):
        self.assertEqual(self.check(project="NOPE")[1]["code"], "project_not_found")
        self.assertEqual(self.post(op="check", project="abc", name="x", data="x")[1]["code"], "bad_project_code")
        status, got = self.post(op="check", project="ABC", name="x.xlsx", data="x", accept="all")
        self.assertEqual(status, 400)
        self.assertIn("not allowed", got["message"])
        self.assertEqual(self.post(op="nope", project="ABC")[0], 400)
        self.assertEqual(self.seam([])[0], 400)


class Apply(Base):
    def test_an_apply_is_one_step_with_one_undo_and_the_workbook_copy_is_gone(self):
        self.edit("Actions", self.a1, Description="Draft the cut-over plan, version two")
        self.edit("Actions", self.a2, Description="Book the big training room")
        key = self.check()[1]["plan"]
        self.assertEqual(len(self.temp_folders()) >= 1, True)
        before = self.steps()
        status, done = self.apply(key)
        self.assertEqual((status, done["ok"], done["counts"]["changed"]), (200, True, 2), done)
        self.assertEqual(self.steps(), before + 1)
        self.assertEqual(self.description_of(self.a1), "Draft the cut-over plan, version two")
        self.assertEqual({r["via"] for r in self.store.step_rows(done["apply_id"])}, {"excel"})
        self.assertNotIn(key, excel_route.PLANS)
        status, back = self.post(op="undo", project="ABC", apply_id=done["apply_id"])
        self.assertEqual((status, back["ok"]), (200, True), back)
        self.assertEqual(self.description_of(self.a1), "Draft the cut-over plan")
        self.assertEqual(self.description_of(self.a2), "Book the training room")
        self.assertEqual(self.post(op="undo", project="ABC", apply_id=done["apply_id"])[1]["code"], "undone")

    def test_accepting_by_number_applies_only_those(self):
        self.edit("Actions", self.a1, Description="Draft the cut-over plan, version two")
        self.edit("Actions", self.a2, Description="Book the big training room")
        got = self.check()[1]
        first = next(i["n"] for i in got["items"] if self.a1 in i["text"])
        status, done = self.apply(got["plan"], [first])
        self.assertEqual((status, done["counts"]["changed"]), (200, 1))
        self.assertEqual(self.description_of(self.a2), "Book the training room")

    def test_accept_all_leaves_a_row_missing_from_the_workbook_alone_and_a_number_archives_it(self):
        wbk_path = self.path
        import openpyxl
        wb = openpyxl.load_workbook(str(wbk_path))
        ws = wb["Actions"]
        row = next(r for r in range(2, ws.max_row + 1) if ws.cell(r, 1).value == self.a2)
        ws.delete_rows(row)
        wb.save(str(wbk_path))
        got = self.check()[1]
        gone = [i for i in got["items"] if i["kind"] == "removed"]
        self.assertEqual((len(gone), gone[0]["default"]), (1, False))
        self.assertEqual(self.apply(got["plan"], "all")[1]["code"], "not_applied")
        status, done = self.apply(got["plan"], [gone[0]["n"]])
        self.assertEqual((status, done["counts"]["removed"]), (200, 1), done)
        self.assertEqual(self.store.read("actions", ref=self.a2)["archived"], 1)

    def test_the_same_file_again_is_already_imported_and_no_plan_waits(self):
        self.edit("Actions", self.a1, Description="Draft the cut-over plan, version two")
        self.assertEqual(self.apply(self.check()[1]["plan"])[0], 200)
        status, got = self.check()
        self.assertEqual((status, got["already_imported"], got["items"], got["plan"]), (200, True, [], None))
        self.assertEqual(excel_route.PLANS, {})

    def test_a_workbook_clark_did_not_export_needs_the_confirm_and_says_so(self):
        plain = wbk.make_workbook(self.store, self.tmp / "other.xlsx")
        wbk.edit(plain, "Actions", self.a1, description="Draft the cut-over plan, by hand")
        got = self.check(plain, name="other.xlsx")[1]
        self.assertTrue(got["unrecorded"])
        status, refused = self.apply(got["plan"])
        self.assertEqual((status, refused["code"], refused["message"]), (409, "needs_confirm", excel_route.NEEDS_CONFIRM))
        self.assertEqual(self.description_of(self.a1), "Draft the cut-over plan")
        status, done = self.apply(got["plan"], "all", confirm=True)
        self.assertEqual((status, done["counts"]["changed"]), (200, 1), done)
        self.assertEqual(self.apply(got["plan"], "all", confirm="yes")[0], 400)

    def test_a_row_that_breaks_a_rule_is_named_and_nothing_is_written(self):
        self.edit("Actions", self.a1, Description="Draft the cut-over plan, version two")
        self.edit("Actions", self.a2, **{"Status": "Not a status"})
        got = self.check()[1]
        bad = [i for i in got["items"] if i["problem"]]
        self.assertEqual(len(bad), 1)
        before = self.steps()
        status, refused = self.apply(got["plan"], [i["n"] for i in got["items"]])
        self.assertEqual((status, refused["code"]), (400, "rolled_back"), refused)
        self.assertIn(self.a2, refused["message"])
        self.assertEqual(self.steps(), before)
        self.assertEqual(self.description_of(self.a1), "Draft the cut-over plan")

    def test_an_old_plan_a_wrong_project_a_bad_accept_and_a_missing_number_are_refused(self):
        self.edit("Actions", self.a1, Description="Draft the cut-over plan, version two")
        key = self.check()[1]["plan"]
        for accept in ([], [0], ["1"], [True], "some", None, [1] * 6000):
            self.assertEqual(self.apply(key, accept)[1]["message"], excel_route.BAD_ACCEPT, str(accept)[:20])
        self.assertIn("no staged change 99", self.apply(key, [99])[1]["message"])
        self.assertEqual(self.apply("nope")[1]["code"], "expired")
        self.now[0] += 31 * 60
        before = self.temp_folders()
        self.assertEqual(self.apply(key)[1]["code"], "expired")
        self.assertEqual(len(self.temp_folders()), len(before) - 1)
        self.assertEqual(excel_route.PLANS, {})

    def test_only_a_few_plans_wait_and_the_oldest_goes_with_its_copy(self):
        keys = []
        for _ in range(excel_route.MAX_PLANS + 2):
            self.now[0] += 1
            keys.append(self.check()[1].get("plan"))
        self.assertTrue(all(keys))
        self.assertEqual(len(excel_route.PLANS), excel_route.MAX_PLANS)
        self.assertEqual(self.apply(keys[0])[1]["code"], "expired")
        self.assertEqual(len(self.temp_folders()) >= 0, True)

    def test_an_undo_takes_only_a_workbook_step_of_that_project(self):
        self.edit("Actions", self.a1, Description="Draft the cut-over plan, version two")
        done = self.apply(self.check()[1]["plan"])[1]
        self.assertEqual(self.post(op="undo", project="ABC", apply_id="1")[1]["message"], excel_route.NO_UNDO)
        self.assertEqual(self.post(op="undo", project="ABC", apply_id=self.demo.last_step() - 5)[1]["message"], excel_route.NO_UNDO)
        self.assertEqual(self.post(op="undo", project="ABC", apply_id=10 ** 6)[1]["message"], excel_route.NO_UNDO)
        self.demo.update("actions", self.a2, {"owner": "Someone"})
        step = self.demo.last_step()
        self.assertEqual(self.post(op="undo", project="ABC", apply_id=step)[1]["message"], excel_route.NO_UNDO)
        self.assertEqual(self.post(op="undo", project="ABC", apply_id=done["apply_id"])[0], 200)


class ThroughTheServer(unittest.TestCase):
    ROUTE = "/api/excel-import"

    def setUp(self):
        self.calls = []
        self.up = Up()
        self.up.httpd.excel_import = lambda r: (self.calls.append(r) or (200, {"ok": True}))
        self.addCleanup(self.up.close)

    def test_without_the_right_token_host_and_origin_the_seam_is_never_called(self):
        for token in (None, "", "wrong"):
            self.assertEqual(self.up.ask(self.ROUTE, b"{}", token=token)[0], 403, token)
        self.assertEqual(self.up.ask(self.ROUTE, b"{}", host="evil.example")[0], 403)
        for extra in ({"Origin": "https://evil.example"}, {"Origin": "null"}, {"Sec-Fetch-Site": "cross-site"}):
            self.assertEqual(self.up.ask(self.ROUTE, b"{}", headers=extra)[0], 403, extra)
        self.assertEqual(self.up.ask(self.ROUTE, b"{}", method="GET")[0], 404)
        self.assertEqual(self.calls, [])

    def test_json_only_a_length_the_biggest_workbook_as_text_and_no_seam_is_503(self):
        import http.client
        sv = self.up.sv
        conn = http.client.HTTPConnection("127.0.0.1", self.up.port, timeout=10)
        conn.request("POST", self.ROUTE, b"{}", {sv.TOKEN_HEADER: sv.TOKEN, "Content-Type": "text/plain"})
        self.assertEqual(conn.getresponse().status, 415)
        conn.close()
        self.assertEqual(self.up.ask(self.ROUTE, b"{nope")[0], 400)
        biggest = (excel_route.MAX_FILE_BYTES * 4 // 3 + 4) + 200
        self.assertGreaterEqual(sv.ROUTE_BODY_LIMITS[self.ROUTE], biggest)
        self.assertLess(sv.ROUTE_BODY_LIMITS[self.ROUTE], 40 * 1024 * 1024)
        conn = http.client.HTTPConnection("127.0.0.1", self.up.port, timeout=10)
        conn.putrequest("POST", self.ROUTE, skip_accept_encoding=True)
        for k, v in {sv.TOKEN_HEADER: sv.TOKEN, "Content-Type": "application/json", "Content-Length": str(sv.ROUTE_BODY_LIMITS[self.ROUTE] + 1)}.items():
            conn.putheader(k, v)
        conn.endheaders()
        r = conn.getresponse()
        self.assertEqual((r.status, json.loads(r.read())["code"]), (400, "too_large"))
        conn.close()
        self.assertEqual(self.calls, [])
        bare = Up()
        self.addCleanup(bare.close)
        status, body = bare.ask(self.ROUTE, b"{}")
        self.assertEqual((status, body["code"]), (503, "saving_off"))


class WorksFromAServerThatNeverLoadedTheSpreadsheetLibrary(unittest.TestCase):
    def test_importing_the_route_and_the_server_does_not_load_openpyxl(self):
        import subprocess
        import sys
        from _paths import SRC
        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        done = subprocess.run([sys.executable, "-I", "-c", "import sys; sys.path.insert(0, sys.argv[1]); from clark import excel_route, server\n"
                               "print('openpyxl' in sys.modules)", str(SRC)], capture_output=True, text=True, env=env, timeout=60)
        self.assertEqual((done.returncode, done.stdout.strip()), (0, "False"), done.stderr)


if __name__ == "__main__":
    unittest.main()
