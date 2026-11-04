"""#454 (point 2): "Get the template" in the Import workbook box. The template is an export's workbook with no rows
(excel.template_bytes), served by GET /api/export?template=1 (server.py export_route, publish_flow.py template): the same
sheets and column labels as the export, so the import reads it unchanged; no project, person or item in it. The non-browser
tests run a real server over the #39 plant (tests/test_publish_route.py Rig); the browser tests are the box with its button.
Run: python3 dev/run_tests.py test_import_template
"""
import base64
import io
import json
import tempfile
import unittest
import zipfile
from xml.sax.saxutils import escape
from pathlib import Path

from _paths import SRC
from openpyxl import load_workbook
from clark import excel, excel_import, server as sv
import test_publish_route as base
from test_preview_export_route import get
from test_settings_data_page import Card, WIDTHS
from test_server import chrome

URL = "/api/export?template=1"
NAME = "clark import template.xlsx"


def sheets_of(raw):
    return load_workbook(io.BytesIO(raw))


def planted_strings(store):
    """Every text value of every table of the planted project, and the project's own words: what must not be in the template."""
    found = {"PUB", "Harbour Bridge", base.USER}
    for table in excel.TABLES + ("projects", "workstreams"):
        for row in store.read(table):
            found.update(v for v in row.values() if isinstance(v, str) and len(v) >= 4 and not v.isdigit())
    found.discard("")
    vocabulary = {v for _, table, cols, _ in excel.SHEETS for _, f in cols for v in (excel.choices(table, f) or [])} | {"Yes", "No"}
    return found - vocabulary          # the words clark itself offers in a drop-down (Open, High, At risk) are not the project's


class Template(unittest.TestCase):
    def setUp(self):
        self.rig = base.Rig(self)
        self.status, self.resp, self.raw = get(self.rig, URL)

    def test_it_downloads_a_workbook_named_clark_import_template(self):
        self.assertEqual(self.status, 200)
        self.assertEqual(self.resp.getheader("Content-Disposition"), f'attachment; filename="{NAME}"')
        self.assertEqual(self.resp.getheader("Content-Type"), sv.XLSX_TYPE)
        self.assertEqual(self.resp.getheader("Content-Length"), str(len(self.raw)))
        self.assertEqual(self.resp.getheader("Cache-Control"), "no-store")
        self.assertEqual(self.raw[:2], b"PK")

    def test_it_has_exactly_the_exports_sheets_and_labels_and_no_rows(self):
        wb = sheets_of(self.raw)
        self.assertEqual(wb.sheetnames, [name for name, _, _, _ in excel.SHEETS])
        for name, _, cols, _ in excel.SHEETS:
            ws = wb[name]
            self.assertEqual([c.value for c in ws[1]], [label for label, _ in cols], name)
            self.assertEqual([v for row in ws.iter_rows(min_row=2, values_only=True) for v in row if v is not None], [], name)
        with tempfile.TemporaryDirectory() as t:
            f = Path(t) / "t.xlsx"
            f.write_bytes(self.raw)
            self.assertEqual(excel.read_workbook(f), {table: [] for table in excel.TABLES})

    def test_its_headers_are_the_ones_an_export_of_a_project_writes(self):
        with tempfile.TemporaryDirectory() as t:
            made = excel.export_project(self.rig.store, "PUB", Path(t) / "e.xlsx", Path(t) / "s.json", on=base.DAY)
            exported = load_workbook(str(made))
        mine = sheets_of(self.raw)
        for name, _, _, _ in excel.SHEETS:
            self.assertEqual([c.value for c in mine[name][1]], [c.value for c in exported[name][1]], name)
            self.assertEqual([c.width for c in mine[name].column_dimensions.values()], [c.width for c in exported[name].column_dimensions.values()], name)

    def test_it_carries_no_project_person_or_item_data(self):
        wanted = planted_strings(self.rig.store)
        wanted |= {r["name"] for r in self.rig.store.read("projects")}
        wanted |= {escape(t) for t in wanted}                       # as the XML of a workbook would spell them
        self.assertGreater(len(wanted), 20, "the plant has plenty to look for")
        with zipfile.ZipFile(io.BytesIO(self.raw)) as z:
            members = {n: z.read(n).decode("utf-8", "replace") for n in z.namelist()}
        for text in sorted(wanted):
            for member, body in members.items():
                self.assertNotIn(text, body, f"{text!r} is in {member}")
        self.assertEqual(sorted(members.keys() & {"docProps/custom.xml"}), [], "no export id")
        self.assertNotIn("clark_export_id", "".join(members.values()))
        wb = sheets_of(self.raw)
        self.assertNotIn("Cover", wb.sheetnames)
        self.assertNotIn("History", wb.sheetnames)
        self.assertEqual((wb.properties.creator, wb.properties.lastModifiedBy), ("clark", "clark"))

    def test_nothing_in_the_request_changes_it_and_no_project_is_read(self):
        for query in ("?template=1&project=PUB", "?template=1&project=ZZZ", "?project=PUB&template=1", "?template=1&project=../../etc/passwd",
                      "?template=1&x=y"):
            s, _, raw = get(self.rig, "/api/export" + query)
            self.assertEqual((s, raw), (200, self.raw), query)

    def test_only_template_1_is_the_template(self):
        for query in ("?template=2", "?template=", "?template=true", "?template=1&template=2", "?template"):
            s, _, raw = get(self.rig, "/api/export" + query)
            self.assertEqual(s, 400, query)                        # an export that names no project
            self.assertEqual(json.loads(raw)["code"], "bad_project_code")

    def test_it_writes_nothing_and_records_no_export(self):
        before = self.rig.everything_written()
        rows = self.rig.rows()
        get(self.rig, URL)
        get(self.rig, URL)
        self.assertEqual(self.rig.everything_written(), before)
        self.assertEqual(self.rig.rows(), rows)
        self.assertFalse((self.rig.data_dir / excel.STATE_FILE).exists(), "an export's record is not made for it")

    def test_it_is_guarded_like_the_export(self):
        self.assertEqual(get(self.rig, URL, token=False)[0], 403)
        self.assertEqual(get(self.rig, URL, token="wrong")[0], 403)
        self.assertEqual(get(self.rig, URL, headers={"Origin": "http://evil.example"})[0], 403)
        self.assertEqual(get(self.rig, URL, headers={"Sec-Fetch-Site": "cross-site"})[0], 403)
        self.assertEqual(get(self.rig, URL, host="evil.example")[0], 403)
        self.assertNotEqual(self.rig.call("POST", URL, {})[0], 200, "GET only")
        self.assertIn("/api/export", sv.GET_ROUTES)
        self.assertNotIn("/api/template", sv.GET_ROUTES)           # no route of its own

    def test_the_same_bytes_each_time_on_one_day(self):
        self.assertEqual(get(self.rig, URL)[2], self.raw)


class ImportingIt(unittest.TestCase):
    def setUp(self):
        self.rig = base.Rig(self)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / NAME
        self.path.write_bytes(get(self.rig, URL)[2])

    def everything(self):
        return {t: self.rig.store.read(t) for t in excel.TABLES + ("projects", "workstreams")}

    def test_the_import_accepts_the_untouched_template_and_changes_nothing(self):
        before = self.everything()
        plan = excel_import.read_workbook(self.rig.store, self.path, "PUB", state_path=Path(self.tmp.name) / "s.json")
        self.assertEqual(plan.problems, [], "no row is refused")
        self.assertFalse(plan.already_imported)
        self.assertEqual(plan.counts()["new"] + plan.counts()["changed"], 0, "nothing new and nothing changed")
        self.assertEqual({c.kind for c in plan.changes} - {"removed"}, set())
        self.assertNotIn("is the wrong shape", " ".join(plan.notes))
        plan.confirm_unrecorded()               # a workbook clark did not record: the person confirms it, as for any other
        plan.accept_all()                        # what "Import" takes by default: nothing, as a row only missing is never taken in bulk
        self.assertEqual(plan.accepted(), [])
        result = excel_import.apply_import(self.rig.store, plan, base.USER)
        self.assertFalse(result.applied if hasattr(result, "applied") else True)
        self.assertEqual(self.everything(), before)

    def test_the_route_checks_it_and_applies_nothing(self):
        from clark import excel_route
        self.rig.httpd.excel_import = excel_route.make_excel_import(self.rig.db, [], base.USER)
        before = self.everything()
        data = base64.b64encode(self.path.read_bytes()).decode()
        status, body = self.rig.call("POST", "/api/excel-import", {"op": "check", "project": "PUB", "name": NAME, "data": data})
        self.assertEqual(status, 200, body)
        self.assertEqual([i for i in body["items"] if i["kind"] != "removed"], [])
        self.assertEqual(body["problems"], [])
        status, body = self.rig.call("POST", "/api/excel-import", {"op": "apply", "project": "PUB", "plan": body["plan"], "accept": "all", "confirm": True})
        self.assertEqual(self.everything(), before)


class Page(Card):
    def open_box(self, p):
        self.open_settings(p)
        self.settle(p, "!!document.querySelector('#import-workbook')", "the Import workbook button")
        p.js("document.querySelector('#import-workbook').click()")
        p.until("!!document.querySelector('#import-box')", "the box opened")

    def test_the_button_is_in_the_first_box_with_the_prototypes_words(self):
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                p.width(w)
                self.open_box(p)
                self.assertEqual(p.js("[...document.querySelectorAll('#import-box .ad-foot button')].map(b => b.textContent)"),
                                 ["Get the template", "Cancel", "Choose a file"])
                self.assertEqual(p.js("document.querySelector('#import-template').textContent"), "Get the template")
                self.assertLessEqual(p.js("document.documentElement.scrollWidth"), w)
                self.assertTrue(p.js("(() => { const a = document.querySelector('#import-template').getBoundingClientRect(), b = document.querySelector('#import-box .ad-foot [data-close]').getBoundingClientRect(); return a.right <= b.left && a.left < b.left; })()"),
                                "the template button is the left-hand one")

    def test_pressing_it_asks_the_server_once_and_the_browser_saves_the_template(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_box(p)
            p.js("""window.__asked = []; window.__saved = []; const f = window.fetch; window.fetch = function (u, o) { window.__asked.push(String(u)); return f.apply(this, arguments); };
              HTMLAnchorElement.prototype.click = function () { window.__saved.push(this.download); };""")
            p.js("document.querySelector('#import-template').click()")
            p.until("!!document.querySelector('#import-template-saved')", "the note that it was saved")
            self.assertEqual(p.js("window.__asked.filter(u => u.includes('template'))"), [URL], "asked once")
            self.assertEqual(p.js("window.__saved"), [NAME])
            self.assertIn(NAME, p.js("document.querySelector('#import-template-saved').textContent"))
            self.assertTrue(p.js("!!document.querySelector('#import-choose') && !document.querySelector('#import-summary')"), "still the first box")

    def test_a_template_that_cannot_be_made_is_said_in_words_and_the_box_stays(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_box(p)
            p.js("window.fetch = function () { return Promise.resolve(new Response('{}', {status: 500})); };")
            p.js("document.querySelector('#import-template').click()")
            p.until("!!document.querySelector('#import-problem').textContent", "the problem")
            self.assertIn("could not be made", p.js("document.querySelector('#import-problem').textContent"))
            self.assertFalse(p.js("!!document.querySelector('#import-template-saved')"))

    def test_the_published_page_has_no_template_button(self):
        view = (SRC / "clark" / "page" / "page-view.html").read_text(encoding="utf-8")
        for needle in ("Get the template", "import-template", "template=1"):
            self.assertNotIn(needle, view, needle)


if __name__ == "__main__":
    unittest.main()
