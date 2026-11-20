"""Row 1268, acceptance 1 and 2: three Work items lists show the same rows as the built-in sections, everywhere.

A page with three lists (Risks and issues, Open actions, Decisions) is compared with the built-in sections of the same project:
- in the published data, the Word report and the client workbook (the built-in sections hidden, the lists alone);
- in View, in Edit and in the published HTML, at 1400 and 900, light and dark (the built-in sections beside the lists);
- the client's At a glance counts, with the lists and with the built-in sections.
A check that fails today names the behaviour that is missing; none of them is skipped.

Run: python3 dev/run_tests.py test_workitems_acceptance_1268
Needs Chrome (the #33 harness). Fictional data only.
"""
import io
import json
import re
import shutil
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from _demo import USER
from _paths import ROOT   # noqa: F401
from openpyxl import load_workbook
from clark import changes, docx_build, excel, excel_client, publish
from test_changes import Api
from test_report_editor import EMPTY_BRANDING, Base as PageBase, Pg, tearDownModule  # noqa: F401
from test_server import chrome

TODAY = "2030-01-15"
ROW = re.compile(r"^ABC-(?:[A-Z]-)?\d{3}$")
LISTS = {                       # the three lists: the title, the kinds and the built-in section (type) each stands for
    "Risks and issues": (["risk", "issue"], "raid"),
    "Open actions": (["action"], "actions"),
    "Decisions": (["decision"], "decisions"),
}


def plant(test):
    """Work items of the three kinds, open and closed, and the four a client never sees (each carries a ZQ- marker)."""
    d, s = test.demo, test.demo.store
    test.a_open = d.action(description="Chase the supplier file", owner="Pat Demo", due_date="2030-01-10", priority="High")
    test.a_later = d.action(description="Plan the second wave", owner="Lee Demo", due_date="2030-03-01")
    test.a_done = d.action(description="Close the old ticket", owner="Lee Demo", due_date="2030-01-02", status="Closed")
    test.a_secret = d.action(description="ZQ-sensitive step", owner="Sam Demo", due_date="2030-01-11")
    test.a_off = d.action(description="ZQ-client-off step", owner="Sam Demo", due_date="2030-01-12", client_visible=0)
    test.a_arch = d.action(description="ZQ-archived step", owner="Sam Demo", due_date="2030-01-12")
    test.a_eye = d.action(description="ZQ-eye-hidden step", owner="Kim Demo", due_date="2030-01-13")
    with s.step("dashboard", USER) as st:
        test.risk = st.create("raid", {"project": "ABC", "type": "Risk", "description": "Key person leaves", "raised": "2026-10-01",
                                       "source": "demo", "impact": "High", "likelihood": "High", "owner": "Pat Demo"})
        test.issue = st.create("raid", {"project": "ABC", "type": "Issue", "description": "The test rig is down", "raised": "2026-10-02",
                                        "source": "demo", "impact": "High", "likelihood": "High", "owner": "Lee Demo"})
        test.pending = st.create("decisions", {"project": "ABC", "decision": "Pick the vendor", "status": "Pending", "needed_by": "2030-01-20", "source": "demo"})
        test.made_new = st.create("decisions", {"project": "ABC", "decision": "Go with plan B", "status": "Made", "date": "2030-01-10", "source": "demo"})
        test.made_old = st.create("decisions", {"project": "ABC", "decision": "Use the old tool", "status": "Made", "date": "2029-11-01", "source": "demo"})
    with s.step("dashboard", USER) as st:
        st.archive("actions", test.a_arch)
    s.con.execute("INSERT OR IGNORE INTO item_labels (item_id, label) VALUES (?, 'Sensitive')", (test.a_secret,))
    s.con.execute("INSERT INTO report_hidden (project, item_id) VALUES ('ABC', ?)", (test.a_eye,))
    s.con.commit()
    test.planted = ("ZQ-sensitive step", "ZQ-client-off step", "ZQ-archived step", "ZQ-eye-hidden step")


CLOSED = ("Closed", "Cancelled", "Made", "Withdrawn")


def built_in_rows(p, section):
    """The ids the built-in section holds: open rows; Decisions are Pending plus Made in the last 14 days (ruling of 16-11)."""
    rows = p["data"][section]
    if section != "decisions":
        return sorted(r["id"] for r in rows if r.get("status") not in CLOSED)
    cut = (date.fromisoformat(TODAY) - timedelta(days=14)).isoformat()
    return sorted(r["id"] for r in rows if r.get("status") == "Pending" or (r.get("status") == "Made" and (r.get("date") or "") >= cut))


def list_body(kinds):
    """Decisions use mode 'current' (Pending plus Made in the last 14 days); the other lists use 'open'."""
    mode = "current" if kinds == ["decision"] else "open"
    return json.dumps({"kinds": kinds, "mode": mode, "max": 50, "columns": ["id", "owner", "due", "status", "priority"]})


class Data(Api):
    """The store and the files: publish, Word, the client workbook and the client's At a glance counts."""

    def setUp(self):
        super().setUp()
        plant(self)

    def build(self, with_lists, built_in=True):
        """The published file's data. The lists are made once; the built-in sections are shown or hidden by their own rows."""
        if with_lists:
            for title, (kinds, _) in LISTS.items():
                ref = self.ok("new", values={"type": "workitems", "title": title}, after=None)["ref"]
                self.ok(changes.UPDATE, id=ref, changes={"body": list_body(kinds)}, place="report")
        if not built_in:
            with self.s.step("dashboard", USER) as st:
                for n, t in enumerate(("raid", "actions", "decisions")):
                    st.create("report_sections", {"project": "ABC", "type": t, "title": t, "sort_order": 50 + n, "hidden": 1})
        return publish.build(self.s, "ABC", now=TODAY)["published"]

    def test_the_lists_name_the_rows_the_built_in_sections_hold_in_the_published_file(self):
        p = self.build(True)
        for title, (_, section) in LISTS.items():
            with self.subTest(list=title):
                named = [s for s in p["sections"] if s["type"] == "workitems" and s["title"] == title][-1]["items"]   # the test's own list, made last; a new project already has a default list of the same title
                self.assertEqual(sorted(named), built_in_rows(p, section))
        for planted in self.planted:
            self.assertNotIn(planted, json.dumps(p))

    def test_with_the_built_in_sections_hidden_the_file_carries_the_same_rows_through_the_lists(self):
        shown = self.build(True)
        every = {t: built_in_rows(shown, t) for t in ("raid", "actions", "decisions")}
        self.tearDown(), self.setUp()
        hidden = self.build(True, built_in=False)
        for title, (_, section) in LISTS.items():
            with self.subTest(list=title):
                named = [s for s in hidden["sections"] if s["type"] == "workitems" and s["title"] == title][-1]["items"]   # the test's own list, made last; a new project already has a default list of the same title
                self.assertEqual(sorted(named), every[section])
                self.assertEqual(built_in_rows(hidden, section), every[section])

    def test_word_prints_each_list_with_the_rows_of_its_built_in_section(self):
        shown = self.build(True)
        every = {t: built_in_rows(shown, t) for t in ("raid", "actions", "decisions")}
        self.tearDown(), self.setUp()
        text = docx_text(docx_build.build(self.build(True, built_in=False)))
        for title, (_, section) in LISTS.items():
            with self.subTest(list=title):
                self.assertIn(title, text)
                for item in every[section]:
                    self.assertIn(item, text)
        for planted in self.planted:
            self.assertNotIn(planted, text)

    def test_the_client_workbook_holds_the_rows_of_each_built_in_sheet(self):
        shown = self.build(True)
        every = {t: built_in_rows(shown, t) for t in ("raid", "actions", "decisions")}
        # row 1307 point 3: the default Decisions list of a new project shows every decision (made ones are the record), so a file with lists only holds them all
        every["decisions"] = sorted(r["id"] for r in shown["data"]["decisions"])
        self.tearDown(), self.setUp()
        wb = load_workbook(io.BytesIO(excel_client.workbook_bytes(self.build(True, built_in=False))))
        for table in ("raid", "actions", "decisions"):
            with self.subTest(sheet=table):
                ws = wb[excel.SHEET_OF[table]]
                self.assertEqual(sorted(str(ws.cell(r, 1).value) for r in range(5, ws.max_row + 1) if ws.cell(r, 1).value), every[table])

    def test_at_a_glance_counts_are_the_same_with_the_lists_as_with_the_built_in_sections(self):
        """Ruling of 16-11: the tiles count what the client can open (Visible), and need no built-in section."""
        def tiles(p):
            return {t["tile"]: (t["value"], t["detail"]) for t in p["data"]["glance"]["tiles"]}
        def show_decisions():       # Decisions needed is hidden by default; show it so the client has it to count
            with self.s.step("dashboard", USER) as st:
                st.create("glance_tiles", {"project": "ABC", "tile": "decisions", "hidden": 0, "sort_order": 3})
        show_decisions()
        with_built_in = tiles(self.build(True))
        self.tearDown(), self.setUp()
        show_decisions()
        with_lists = tiles(self.build(True, built_in=False))
        for name in ("overdue", "risks", "decisions"):
            with self.subTest(tile=name):
                self.assertIn(name, with_lists, "the tile is left out when its built-in section is hidden (glance.py SECTION_OF_TILE)")
                self.assertEqual(with_lists.get(name), with_built_in.get(name))


def docx_text(data):
    from test_docx_build import every_text
    return every_text(data)


class InThePage(PageBase):
    """View and Edit in a real browser: each list lists the ids the built-in section beside it lists."""

    def setUp(self):
        super().setUp()
        plant(self)
        self.refs, self.built_in = {}, {}
        with self.store.step("dashboard", USER) as st:          # the built-in sections the lists stand for, drawn beside them
            for n, (_, (_, section)) in enumerate(LISTS.items()):
                self.built_in[section] = st.create("report_sections", {"project": "ABC", "type": section, "title": section, "sort_order": 50 + n})
        for title, (kinds, _) in LISTS.items():
            status, got = self.real_change({"project": "ABC", "kind": "report_sections", "op": changes.NEW, "values": {"type": "workitems", "title": title}, "after": None})
            self.assertEqual(status, 200, got)
            self.refs[title] = got["ref"]
            status, got = self.real_change({"project": "ABC", "kind": "report_sections", "op": changes.UPDATE, "id": got["ref"], "changes": {"body": list_body(kinds)}})
            self.assertEqual(status, 200, got)

    def ids(self, p, root, off=False):
        """The ids drawn under root. `off` true: only the rows greyed (wil-off); false: the rows not greyed."""
        test = "e.classList.contains('wil-off')" if off else "!e.classList.contains('wil-off')"
        return sorted(set(p.js(f"[...document.querySelectorAll({json.dumps(root + ' [data-id]')})].filter(e => e.offsetParent && {test}).map(e => e.dataset.id)")))

    def compare(self, p, where):
        for title, (_, section) in LISTS.items():
            with self.subTest(where=where, list=title):
                listed = [i for i in self.ids(p, f"[data-id=\"{self.refs[title]}\"]") if ROW.match(i)]
                built_in = [i for i in self.ids(p, f"[data-id=\"{self.built_in[section]}\"]") if ROW.match(i)]
                self.assertTrue(built_in, f"the built-in {section} section drew no rows (section {self.built_in[section]})")
                self.assertEqual(listed, built_in)
                if where.startswith("Edit") and section == "actions":
                    # Edit lists, greyed, the rows the client eye or the client-off flag has taken off (editListOf: so the eye can be turned back on);
                    # the built-in section does not draw them (it offers them in its picker). They are not part of what the client sees.
                    off = [i for i in self.ids(p, f"[data-id=\"{self.refs[title]}\"]", off=True) if ROW.match(i)]
                    self.assertEqual(off, sorted([self.a_off, self.a_eye]))

    def test_view_and_edit_list_the_rows_of_the_built_in_sections_at_both_widths_in_light_and_dark(self):
        for width in (1400, 900):
            for dark in (False, True):
                with chrome() as cdp:
                    p = self.visit(cdp)
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                    if dark:
                        p.js("document.documentElement.dataset.theme = 'dark'")
                    p.until(f"!!document.querySelector('[data-id=\"{self.refs['Decisions']}\"]')", "the lists drew")
                    self.compare(p, f"View {width} {'dark' if dark else 'light'}")
                    p.edit()
                    p.until(f"!!document.querySelector('[data-id=\"{self.refs['Decisions']}\"]')", "the lists drew in Edit")
                    self.compare(p, f"Edit {width} {'dark' if dark else 'light'}")

    def test_the_published_file_lists_the_rows_of_the_built_in_sections_at_both_widths_in_light_and_dark(self):
        out = tempfile.mkdtemp(prefix="clark-1268-acc-")
        self.addCleanup(shutil.rmtree, out, ignore_errors=True)
        path = Path(publish.publish(self.store, "ABC", out, by_user=USER, now=TODAY, branding=EMPTY_BRANDING)["path"])
        for width, dark in ((1400, False), (1400, True), (900, False), (900, True)):
            with chrome() as cdp:
                tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
                sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, sid)
                cdp.call("Page.navigate", {"url": path.as_uri()}, sid)
                p = Pg(self, cdp, sid)
                p.until("document.documentElement.dataset.ready === '1' && !!document.querySelector('h1')", "the file drew")
                if dark:
                    p.js("document.documentElement.dataset.theme = 'dark'")
                self.compare(p, f"file {width} {'dark' if dark else 'light'}")


if __name__ == "__main__":
    unittest.main()
