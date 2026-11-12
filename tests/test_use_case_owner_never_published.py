"""Row 875: a use case's owner is internal. Planted markers (the owner's text, and the name of the linked person) are set through the
real change route on a client-visible use case, then the page, the client copy, the Word report, the client workbook, the PDF text
and the Ask passages are searched for them; the work items workbook does not export the owner, and an export then an import leaves
the owner as it was.

Run: python3 dev/run_tests.py test_use_case_owner_never_published
"""
import io
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

import _paths  # noqa: F401  (puts src/ and vendor/ on the path)
import _publish_fixture as fx
from openpyxl import load_workbook

from clark import ask_data, changes, docx_build, excel, excel_client, pdf, pdf_text, publish, publish_pdf
from clark import excel_import as xi
from clark import page
from test_publish_route import DAY, USER, WANTED, Rig

TEXT = "ZQ-OWNER-TEXT-6602 Placeholder Owner"
PERSON = "ZQ-OWNER-PERSON-6603 Pat Placeholder"
U1, U3 = "PUB-U-001", "PUB-U-003"          # both client-visible in the plant


def plant(rig):
    """U1 owned by a known person (text and link), U3 by free text with no link: through the change route."""
    with rig.store.step("dashboard", USER) as st:
        st.add_person(name=PERSON, source="People list")
    change = changes.make_change(rig.db, [], USER)
    for uc, name in ((U1, PERSON), (U3, TEXT)):
        status, got = change({"project": "PUB", "kind": "use_cases", "op": "update", "id": uc, "changes": {"owner": name}})
        assert status == 200, got
    row = rig.store.read("use_cases", ref=U1)
    assert (row["owner"], bool(row["owner_id"])) == (PERSON, True), row
    assert rig.store.read("use_cases", ref=U3)["owner"] == TEXT


def spelled(text):
    """Every spelling of every marker (and each piece of the person's name), as the file or the zip's parts hold it."""
    return [s for m in (TEXT, PERSON, "ZQ-OWNER") for s in fx.spellings(m)]


class Planted(unittest.TestCase):
    def setUp(self):
        self.rig = Rig(self)
        plant(self.rig)

    def assertClean(self, text, where):
        for s in spelled(text):
            self.assertNotIn(s, text, f"{s!r} is in {where}")
        self.assertNotIn("Pat Placeholder", text, where)

    def published(self):
        return publish.select(publish.read_inputs(self.rig.store, "PUB"))

    def test_the_page_its_data_block_and_the_client_copy(self):
        status, got = self.rig.publish(to_client=True)
        self.assertEqual((status, got["ok"], got["action"]), (200, True, "done"), got)
        local = (self.rig.local / "chosen.html").read_bytes().decode("utf-8")
        client = (self.rig.client / WANTED).read_bytes().decode("utf-8")
        self.assertIn("PUB-U-001", local, "the use case itself is published")
        self.assertClean(local, "the page")
        self.assertClean(client, "the client copy")

    def test_the_selected_data_has_no_owner_on_a_use_case(self):
        for row in self.published()["data"]["use_cases"]:
            self.assertNotIn("owner", row)
            self.assertNotIn("owner_id", row)

    def test_the_word_report(self):
        z = zipfile.ZipFile(io.BytesIO(docx_build.build(self.published())))
        self.assertTrue(z.namelist())
        for name in z.namelist():
            self.assertClean(z.read(name).decode("utf-8", "replace"), "the Word part " + name)

    def test_the_client_workbook(self):
        data = excel_client.workbook_bytes(self.published())
        z = zipfile.ZipFile(io.BytesIO(data))
        for name in z.namelist():
            self.assertClean(z.read(name).decode("utf-8", "replace"), "the client workbook part " + name)
        wb = load_workbook(io.BytesIO(data))
        for ws in wb.worksheets:
            for row in ws.iter_rows(values_only=True):
                for v in row:
                    self.assertClean(str(v), "client workbook sheet " + ws.title)

    def test_the_pdf_text(self):
        status, got = self.rig.publish(to_client=True)
        self.assertEqual((status, got["ok"]), (200, True), got)
        body = (self.rig.local / "chosen.html").read_bytes()
        try:
            data = publish_pdf.make(body, DAY)
        except pdf.PdfError as e:
            self.skipTest("no PDF printer here: %s" % e)
        text = pdf_text.text_of(data)
        self.assertClean(text, "the PDF text")
        self.assertClean(data.decode("latin-1"), "the PDF bytes")

    def test_the_ask_passages_and_facts(self):
        for question in ("", "who owns use case PUB-U-001", "owner Pat Placeholder ZQ-OWNER"):
            got = ask_data.project_data(self.rig.store, "PUB", question)
            self.assertTrue(got.passages)
            self.assertClean("\n".join(p.text for p in got.passages), "the Ask passages")
            self.assertClean(json.dumps(got.facts), "the Ask facts")


class Workbook(unittest.TestCase):
    """The work items workbook does not export the owner of a use case, and an export then an import leaves it alone."""

    def setUp(self):
        from _demo import DemoStore
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.dir = Path(tempfile.mkdtemp(prefix="clark-uc-owner-"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.path, self.state = self.dir / "ABC work items.xlsx", self.dir / "state.json"
        with self.s.step("dashboard", USER) as st:
            st.add_person(name=PERSON, source="People list")
        change = changes.make_change(self.s.path, [], USER)
        status, got = change({"project": "ABC", "kind": "use_cases", "op": "update", "id": self.demo.use_case, "changes": {"owner": PERSON}})
        self.assertEqual(status, 200, got)
        self.before = self.owner()

    def owner(self):
        r = self.s.read("use_cases", ref=self.demo.use_case)
        return (r["owner"], r["owner_id"])

    def export(self):
        return excel.export_project(self.s, "ABC", self.path, self.state, on="2030-06-01")

    def test_the_marker_is_in_no_part_of_the_exported_workbook(self):
        """Every data sheet. The History sheet (marked read-only and internal, as for every other owner edit) names the change, so it
        is the one place the name may be, and the only one."""
        self.export()
        wb = load_workbook(str(self.path))
        seen = []
        for ws in wb.worksheets:
            cells = [str(v) for row in ws.iter_rows(values_only=True) for v in row if v is not None]
            hit = any("ZQ-OWNER" in c or "Pat Placeholder" in c for c in cells)
            if hit:
                seen.append(ws.title)
                self.assertTrue(any("for internal use" in c for c in cells), ws.title + " is not the internal History sheet")
        self.assertEqual(seen, ["History"], "the owner is in no data sheet; the internal History sheet alone names the change")

    def test_export_then_import_leaves_the_owner_and_the_link_unchanged(self):
        self.export()
        plan = xi.read_workbook(self.s, self.path, "ABC", state_path=self.state)
        self.assertEqual([c for c in plan.changes if c.kind != "unchanged"], [])
        self.assertEqual(self.owner(), self.before)
        self.assertNotEqual(self.before, (None, None))

    def test_an_edit_of_another_cell_then_import_leaves_the_owner(self):
        self.export()
        wb = load_workbook(str(self.path))
        ws = wb["Use cases"]
        head = {c.value: c.column for c in ws[1]}
        self.assertNotIn("Owner", head)
        row = next(r for r in range(2, ws.max_row + 1) if ws.cell(r, 1).value == self.demo.use_case)
        ws.cell(row, head["Headline"]).value = "Edited in Excel"
        wb.save(str(self.path))
        plan = xi.read_workbook(self.s, self.path, "ABC", state_path=self.state)
        plan.accept_all()
        res = xi.apply_import(self.s, plan, USER, state_path=self.state)
        self.assertTrue(res.applied, res.message)
        self.assertEqual(self.s.read("use_cases", ref=self.demo.use_case)["headline"], "Edited in Excel")
        self.assertEqual(self.owner(), self.before)


if __name__ == "__main__":
    unittest.main()
