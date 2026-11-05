"""Item 713: what the publish flow writes for the published page's menu is exactly what the page's own checks accept.

Run: python3 dev/run_tests.py test_client_menu_contract
The page reads three optional keys at the top level of its data (src/clark/page/src/logic/clientMenu.js): client_workbook {name, base64},
client_workbook_too_large (a boolean true) and past_reports [{week_ending, file}]. The functions below are Python copies of that file's
checks (workbookOf, tooLarge, plainFile, pastReportsOf), written out the same way. The real flow publishes a fixture project twice into a
folder; its second file is read back and put through them. When the page's file is in this checkout, the real functions run on the same data
in node as well.
"""
import base64
import io
import json
import re
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import _publish_fixture as fx
from _paths import SRC
from clark import excel_client, publish, publish_flow
from clark.store import open_store
from openpyxl import load_workbook

EMPTY_BRANDING = tempfile.mkdtemp(prefix="clark-no-brand-")
DAY = "2026-10-28"
MENU_JS = SRC / "clark" / "page" / "src" / "logic" / "clientMenu.js"
THREE = {"client_workbook", "client_workbook_too_large", "past_reports"}


def tearDownModule():
    Path(EMPTY_BRANDING).rmdir()


# ----- Python copies of clientMenu.js -----
def workbook_of(d):
    w = d.get("client_workbook") if isinstance(d, dict) else None
    if not isinstance(w, dict) or not isinstance(w.get("base64"), str) or not w["base64"] or not re.fullmatch(r"[A-Za-z0-9+/=\s]+", w["base64"]):
        return None
    ok = isinstance(w.get("name"), str) and re.fullmatch(r'[^\\/:*?"<>|\x00-\x1f]{1,120}', w["name"])
    name = w["name"] if ok else "report.xlsx"
    return {"name": name if re.search(r"\.xlsx$", name, re.I) else name + ".xlsx", "base64": re.sub(r"\s+", "", w["base64"])}


def too_large(d):
    return isinstance(d, dict) and d.get("client_workbook_too_large") is True


def plain_file(f):
    return f if isinstance(f, str) and re.fullmatch(r"[^\\/:?#\x00-\x1f]+", f) and not f.startswith(".") and len(f) <= 200 else ""


def past_reports_of(d):
    out = []
    for r in d.get("past_reports") or [] if isinstance(d, dict) and isinstance(d.get("past_reports"), list) else []:
        if not isinstance(r, dict) or not isinstance(r.get("week_ending"), str) or not re.fullmatch(r"\d{4}-\d\d-\d\d", r["week_ending"]) \
                or not plain_file(r.get("file")):
            continue
        out.append({"iso": r["week_ending"], "file": r["file"]})
    return sorted(out, key=lambda r: r["iso"], reverse=True)


class Real(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name).resolve()
        self.folder = root / "Reports"
        self.folder.mkdir()
        data = root / "clark-data"
        data.mkdir()
        db = self.db = data / "clark.db"
        fx.build_db(db, fx.load())
        self.answer = None
        self.publisher = publish_flow.Publisher(db, [], choose_save_file=lambda prompt, default, start=None: self.answer,
                                                choose_folder=lambda *a, **k: None, today=lambda: DAY, by_user=lambda: "Pat Writer",
                                                data_dir=data, branding=EMPTY_BRANDING)

    def go(self, name):
        self.answer = self.folder / name
        status, out = self.publisher.publish({"project": "PUB"})
        self.assertEqual((status, out["ok"]), (200, True), out)
        text = (self.folder / name).read_text(encoding="utf-8")
        return json.loads(re.search(r'id="clark-data">(.*?)</script>', text, re.S).group(1))

    def twice(self):
        self.go("PUB-report-2026-10-09.html")
        self.go("PUB-report-2026-10-16.html")
        return self.go("PUB-report-2026-10-23.html")

    def test_the_workbook_is_what_the_page_accepts(self):
        block = self.twice()
        data = block["data"]
        self.assertEqual(set(data["client_workbook"]), {"name", "base64"})
        got = workbook_of(data)
        self.assertIsNotNone(got, "the page would draw no download")
        self.assertEqual(got["name"], data["client_workbook"]["name"], "the page keeps the name as written")
        self.assertEqual(got["base64"], data["client_workbook"]["base64"])
        raw = base64.b64decode(got["base64"], validate=True)
        zipfile.ZipFile(io.BytesIO(raw)).testzip()
        load_workbook(io.BytesIO(raw))
        self.assertTrue(got["name"].endswith(".xlsx"))
        self.assertFalse(too_large(data))

    def test_the_bytes_are_the_stand_alone_builders(self):
        data = self.twice()["data"]
        store = open_store(self.db, onedrive_roots=[])
        self.addCleanup(store.close)
        inputs = publish.read_inputs(store, "PUB", DAY)
        alone = excel_client.workbook_bytes(publish.add_glance(publish.select(inputs), inputs))
        self.assertEqual(base64.b64decode(data["client_workbook"]["base64"], validate=True), alone)

    def test_every_past_report_row_passes_the_pages_checks(self):
        data = self.twice()["data"]
        rows = data["past_reports"]
        self.assertEqual([r["file"] for r in rows], ["PUB-report-2026-10-16.html", "PUB-report-2026-10-09.html"])
        shown = past_reports_of(data)
        self.assertEqual(len(shown), len(rows), "the page would leave a row out")
        for r in rows:
            self.assertEqual(set(r), {"week_ending", "file"})
            self.assertEqual(plain_file(r["file"]), r["file"])
        self.assertEqual([r["iso"] for r in shown], [r["week_ending"] for r in rows], "already newest first")

    def test_no_key_outside_the_three_and_none_of_the_old_ones(self):
        block = self.twice()
        data = block["data"]
        self.assertTrue(THREE - {"client_workbook_too_large"} <= set(data))
        for old in ("workbook", "workbook_note", "mime", "b64"):
            self.assertNotIn(old, block)
            self.assertNotIn(old, data)
        self.assertFalse(THREE & set(block), "they are in the data, not beside it")
        self.assertNotIn("mime", data["client_workbook"])

    def test_too_large_is_a_real_true_and_no_workbook(self):
        with mock.patch.object(excel_client, "MAX_WORKBOOK_BYTES", 100):
            data = self.go("PUB-report-2026-10-23.html")["data"]
        self.assertIs(data["client_workbook_too_large"], True)
        self.assertTrue(too_large(data))
        self.assertNotIn("client_workbook", data)
        self.assertIsNone(workbook_of(data))

    def test_the_first_report_has_none_of_the_three_but_the_workbook(self):
        data = self.go("PUB-report-2026-10-09.html")["data"]
        self.assertNotIn("past_reports", data)
        self.assertNotIn("client_workbook_too_large", data)
        self.assertIsNotNone(workbook_of(data))

    def test_the_page_would_refuse_what_it_should(self):
        self.assertIsNone(workbook_of({"client_workbook": {"name": "a.xlsx", "base64": "not base64!"}}))
        self.assertIsNone(workbook_of({"client_workbook": {"name": "a.xlsx", "base64": ""}}))
        self.assertEqual(workbook_of({"client_workbook": {"name": "a/b", "base64": "QQ=="}})["name"], "report.xlsx")
        self.assertFalse(too_large({"client_workbook_too_large": "true"}))
        self.assertFalse(too_large({"client_workbook_too_large": 1}))
        self.assertEqual(plain_file(".hidden.html"), "")
        self.assertEqual(plain_file("a/b.html"), "")
        self.assertEqual(plain_file("a?b.html"), "")


@unittest.skipUnless(MENU_JS.exists() and shutil.which("node"), "the page's clientMenu.js is not in this checkout (or no node)")
class Node(unittest.TestCase):
    """The page's real functions on the real output."""

    setUp = Real.setUp
    go = Real.go
    twice = Real.twice

    def run_node(self, data):
        import esbuild  # noqa: E402  (dev/tools)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "menu.js"
            done = esbuild.run(["--bundle", "--format=iife", "--global-name=CM", str(MENU_JS), f"--outfile={out}"], capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            probe = Path(tmp) / "probe.js"
            probe.write_text(out.read_text(encoding="utf-8") + ";\nconst d = " + json.dumps(data) + ";\nconsole.log(JSON.stringify({w: CM.workbookOf(d), t: CM.tooLarge(d), p: CM.pastReportsOf(d)}));",
                             encoding="utf-8")
            got = subprocess.run([shutil.which("node"), str(probe)], capture_output=True, text=True)
            self.assertEqual(got.returncode, 0, got.stderr)
            return json.loads(got.stdout)

    def test_the_real_functions_accept_the_real_output(self):
        data = self.twice()["data"]
        got = self.run_node(data)
        self.assertEqual(got["w"], workbook_of(data))
        self.assertEqual(len(got["p"]), len(data["past_reports"]))
        self.assertFalse(got["t"])
        self.assertEqual(base64.b64decode(got["w"]["base64"], validate=True)[:2], b"PK")

    def test_the_real_functions_on_too_large(self):
        with mock.patch.object(excel_client, "MAX_WORKBOOK_BYTES", 100):
            data = self.go("PUB-report-2026-10-23.html")["data"]
        got = self.run_node(data)
        self.assertEqual((got["w"], got["t"]), (None, True))


if __name__ == "__main__":
    unittest.main()
