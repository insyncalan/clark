"""#926 part 3, the Gantt as a full-width section template on the Dashboard (store type "gantt"): the data it reads, the view part (only the lines
put on the dashboard, only the columns not hidden from the client, read only), the Edit part (the same chart and a note), and the catalogue entry.
Page side only: the store does not take the type yet (that step is guarded), so the box lists the template but does not place it. Fictional data.

Run: python3 dev/run_tests.py test_gantt_section
Needs Chrome: these tests fail, never skip, without it.
"""
import contextlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT, SRC, TOOLS

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402

from test_gantt_logic import LINES, TODAY  # noqa: E402
from test_server import Running, chrome, wait  # noqa: E402

PAGE_SRC = SRC / "clark" / "page" / "src"
DEMO = ROOT / "tests" / "fixtures" / "gantt_section_demo.jsx"
_PAGE = {}


def page_html():
    if "html" not in _PAGE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "t.js"
            done = esbuild.run(["--bundle", "--format=iife", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(DEMO), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            script = out.read_text(encoding="utf-8").replace("</script", "<\\/script")
        _PAGE["html"] = ('<!doctype html>\n<html lang="en-GB"><head><meta charset="utf-8"><title>t</title></head>'
                         f'<body><div id="root"></div>\n<script>{script}</script>\n</body></html>\n')
    return _PAGE["html"]


def lit(x):
    return json.dumps(x)


def report(lines=LINES, hidden=("on_dashboard", "notes", "budget", "effort_days", "baseline_start", "baseline_end"), **project):
    return {"project": {"gantt_hidden_columns": list(hidden), **project}, "gantt_lines": [{**l, "show": 1 if l["show"] else 0, "sort_order": i} for i, l in enumerate(lines)]}


class Static(unittest.TestCase):
    def test_the_section_page_parts_are_there_and_use_no_hex_colour(self):
        for f in (PAGE_SRC / "components" / "GanttSection.jsx", PAGE_SRC / "edit" / "templates" / "GanttSection.jsx", PAGE_SRC / "gantt" / "logic" / "section.js"):
            text = f.read_text(encoding="utf-8")
            self.assertIn('store type "gantt"' if f.suffix == ".jsx" else "Dashboard section", text, f.name)
            self.assertNotIn("dangerouslySetInnerHTML", text, f.name)
            self.assertNotRegex(text, r"#[0-9a-fA-F]{6}\b", f.name)

    def test_the_catalogue_entry_is_full_width_only_and_before_one_document(self):
        text = (PAGE_SRC / "logic" / "templates.js").read_text(encoding="utf-8")
        entry = text[text.index('{ id: "gantt"'):text.index('{ id: "gantt-table"')]      # row 1068: the Gantt table card follows the Gantt card, both before One document
        self.assertIn('fit: ["full"]', entry)
        self.assertIn("The plan as bars on a timeline, from your Gantt lines. Only lines put in the client view show.", entry)
        self.assertIn('holds: ["Heading", "The Gantt chart"]', entry)
        self.assertLess(text.index('{ id: "gantt-table"'), text.index('{ id: "one-doc"'))

    def test_the_table_section_page_parts_are_there_and_its_card_is_a_full_or_half_template(self):
        """Row 1068: the Gantt table section (store type gantttable) reuses the Gantt page's table; its card is a template section's,
        full or half (the owner's ruling), named by the one constant GANTT_TABLE_NAME."""
        for f in (PAGE_SRC / "components" / "GanttTableSection.jsx", PAGE_SRC / "edit" / "templates" / "GanttTableSection.jsx"):
            text = f.read_text(encoding="utf-8")
            self.assertIn('store type "gantttable"', text, f.name)
            self.assertNotIn("dangerouslySetInnerHTML", text, f.name)
            self.assertNotRegex(text, r"#[0-9a-fA-F]{6}\b", f.name)
        self.assertIn("gantt/components/GanttTable.jsx", (PAGE_SRC / "components" / "GanttTableSection.jsx").read_text(encoding="utf-8"), "the one table")
        text = (PAGE_SRC / "logic" / "templates.js").read_text(encoding="utf-8")
        entry = text[text.index('{ id: "gantt-table"'):text.index('{ id: "one-doc"')]
        self.assertIn('fit: ["full", "half"]', entry)
        self.assertIn('type: "gantttable"', entry)
        self.assertIn("name: GANTT_TABLE_NAME", entry)
        self.assertIn("title: GANTT_TABLE_NAME", entry)
        self.assertIn("The plan as a table, from your Gantt lines. Only lines put in the client view show.", entry)
        self.assertIn('holds: ["Heading", "The plan table"]', entry)
        self.assertIn('export const GANTT_TABLE_NAME = "Table";', text)


class Section(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack = contextlib.ExitStack()
        cls.server = Running(page_html=page_html)
        cls.stack.callback(cls.server.close)
        cls.cdp = cls.stack.enter_context(chrome())
        tid = next(t["targetId"] for t in cls.cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        cls.sid = cls.cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cls.cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{cls.server.port}/"}, cls.sid)
        assert wait(lambda: cls.cdp.js("!!(window.mountSection && window.K)", cls.sid)), "the test bundle ran"

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    def js(self, expr):
        return self.cdp.js(expr, self.sid)

    def val(self, expr):
        got = self.js(f"(function(){{ try {{ return JSON.stringify({expr}); }} catch (e) {{ return 'ERROR ' + e.message; }} }})()")
        self.assertIsNotNone(got, expr)
        self.assertFalse(got.startswith("ERROR"), f"{expr}: {got}")
        return json.loads(got)

    def look(self, width):
        self.cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
        self.js("document.body.style.margin = '0'; document.body.style.padding = '0 20px'")

    def mount(self, data, width, **opts):
        self.js(f"mountSection({lit(data)}, {lit({'width': width - 40, **opts})})")
        self.assertTrue(wait(lambda: self.js("!!document.querySelector('[data-gantt]')"), 8), "the chart is on the page")

    def count(self, sel):
        return self.val(f"document.querySelectorAll({lit(sel)}).length")

    # ── what the section reads ───────────────────────────────────────────────

    def test_the_lines_the_columns_and_the_height_are_read_from_the_report(self):
        d = report(gantt_default_rows=3)
        self.assertEqual(self.val(f"K.section.linesOf({lit(d)}).length"), len(LINES))
        self.assertEqual(self.val(f"K.section.hiddenOf({lit(d)})"), [], "the hidden columns that are not start, end or done do not touch the chart")
        d["project"]["gantt_hidden_columns"] = "start_date,percent_complete,notes"
        self.assertEqual(self.val(f"K.section.hiddenOf({lit(d)})"), ["start", "pct"], "a comma list and the store's column names are read too")
        self.assertEqual(self.val(f"K.section.savedRows({lit(d)})"), 3)
        self.assertIsNone(self.val(f"K.section.savedRows({lit(report())})"), "no saved height: every row")
        self.assertEqual(self.val("K.section.linesOf({})"), [])
        self.assertEqual(self.val(f"K.section.linesOf({{gantt_lines: [null, 4, {{id: 'GNT-9', name: 'A', type: 'task', start: '2026-11-02', end: '2026-11-03', depends: 'GNT-1, GNT-2', show: 1}}]}})[0].depends"), ["GNT-1", "GNT-2"])

    def test_a_published_file_has_only_data_gantt_and_the_section_reads_its_lines(self):
        file_data = {"gantt": {"columns": ["id", "name", "type", "start", "end", "pct"], "lines": [
            {"id": "GNT-1", "name": "Plan", "type": "phase", "start": "2026-11-02", "end": "2026-11-20", "pct": 10},
            {"id": "GNT-2", "name": "Build", "type": "task", "parent": "GNT-1", "start": "2026-11-02", "end": "2026-11-10", "pct": 50}]}}
        self.assertEqual(self.val(f"K.section.linesOf({lit(file_data)}).map((l) => l.id)"), ["GNT-1", "GNT-2"])
        self.assertEqual(self.val(f"K.section.linesOf({lit({**file_data, 'gantt_lines': []})}).length"), 0, "the editor's own list wins when it is there")

    def test_a_line_with_no_usable_date_is_counted_and_keeps_the_section(self):
        bad = {"id": "GNT-90", "name": "No date", "type": "task", "start": "garbage", "end": "", "show": 1}
        off = {**bad, "id": "GNT-91", "show": 0}
        d = report([bad, off])
        self.assertEqual(self.val(f"K.section.leftOutOf({lit(d)})"), 1, "only the eye-on one is the viewer's")
        self.assertEqual(self.val(f"K.section.linesOf({lit(d)}).length"), 0)
        self.assertFalse(self.val(f"K.templateEmpty({{type: 'gantt'}}, {lit(d)})"), "the section is not dropped without a word")

    def test_a_published_file_line_has_no_show_field_and_a_line_without_a_date_in_it_is_still_counted(self):
        # Tripwire (row 989b). publish.gantt_for_client drops a line whose date is not a real day, so a file made by Clark never holds one
        # (tests/test_gantt_publish.py pins that); a hand-edited or older file may, and its lines carry no `show` at all (the eye only decides).
        file_data = {"gantt": {"columns": ["id", "name", "type", "start", "end", "pct"], "lines": [
            {"id": "GNT-1", "name": "Plan", "type": "phase", "start": "2026-11-02", "end": "2026-11-20", "pct": 10},
            {"id": "GNT-2", "name": "No date", "type": "task", "start": "garbage", "end": "", "pct": 0}]}}
        self.assertEqual(self.val(f"K.section.leftOutOf({lit(file_data)})"), 1, "a file line has no show field and still counts")
        self.assertEqual(self.val(f"K.section.linesOf({lit(file_data)}).length"), 1)

    def test_nothing_on_the_dashboard_means_an_empty_section(self):
        none = [{**l, "show": False} for l in LINES]
        self.assertTrue(self.val(f"K.templateEmpty({{type: 'gantt'}}, {lit(report(none))})"))
        self.assertTrue(self.val("K.templateEmpty({type: 'gantt'}, {})"))
        self.assertFalse(self.val(f"K.templateEmpty({{type: 'gantt'}}, {lit(report())})"))

    # ── View and Edit ────────────────────────────────────────────────────────

    def test_view_draws_only_the_lines_on_the_dashboard_and_cannot_be_changed(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                self.look(width)
                self.mount(report(), width)
                want = [l["id"] for l in LINES if l["show"]]
                self.assertEqual(self.val("[...document.querySelectorAll('[data-g-row]')].map(e => e.dataset.gRow)"), want)
                self.assertEqual(self.count("input, [data-g-eye], [data-g-add], [data-g-coleye], [data-rz]"), 0, "nothing to change")
                self.assertEqual(self.count("[data-tpl-gantt-note]"), 0, "the note is for Edit")
                self.assertGreaterEqual(self.val("document.getElementById('host').getBoundingClientRect().width"), width - 41)

    def test_a_column_hidden_from_the_client_is_gone(self):
        self.look(1400)
        self.mount(report(hidden=("end_date",)), 1400)
        self.assertEqual(self.count(".gt-h-end"), 0)
        self.mount(report(), 1400)
        self.assertEqual(self.count(".gt-h-end"), 1)

    def test_the_saved_plan_height_is_kept(self):
        self.look(1400)
        self.mount(report(), 1400)
        self.assertEqual(self.val("document.querySelector('[data-g-gx]').style.height"), "", "every row")
        self.mount(report(gantt_default_rows=2), 1400)
        self.assertEqual(self.val("document.querySelector('[data-g-gx]').style.height"), "134px", "the header and two rows")

    def test_edit_draws_the_same_chart_read_only_and_a_note(self):
        self.look(1400)
        self.mount(report(), 1400, edit=True)
        want = [l["id"] for l in LINES if l["show"]]
        self.assertEqual(self.val("[...document.querySelectorAll('[data-g-row]')].map(e => e.dataset.gRow)"), want, "Edit shows what the reader sees")
        self.assertEqual(self.count("input, [data-g-eye], [data-g-add], [data-rz]"), 0, "the lines are chosen on the Gantt page")
        self.assertEqual(self.val("document.querySelector('[data-tpl-gantt-note]').textContent"), "Lines are chosen on the Gantt page.")

    def test_no_lines_says_so_in_the_charts_words(self):
        self.look(1400)
        self.mount({"project": {}, "gantt_lines": []}, 1400, edit=True)
        self.assertEqual(self.val("document.querySelector('[data-g-none]').textContent"), "No lines to show.")

    # ── the Gantt table section (row 1068) ───────────────────────────────────

    TABLE = "[data-tpl=gantttable] [data-gt]"
    FILE_DATA = {"project": {}, "gantt": {"columns": ["id", "name", "type", "start", "end", "pct"], "lines": [
        {"id": "GNT-1", "name": "Plan", "type": "phase", "start": "2026-11-02", "end": "2026-11-20", "pct": 10},
        {"id": "GNT-2", "name": "Build", "type": "task", "parent": "GNT-1", "start": "2026-11-02", "end": "2026-11-10", "pct": 50}]}}

    def mount_table(self, data, width, **opts):
        self.js(f"mountSection({lit(data)}, {lit({'width': width - 40, 'type': 'gantttable', **opts})})")
        self.assertTrue(wait(lambda: self.js(f"!!document.querySelector({lit(self.TABLE)})"), 8), "the table is on the page")

    def table_rows(self):
        return self.val(f"[...document.querySelectorAll('{self.TABLE} tbody tr')].map(e => e.dataset.id)")

    def test_the_table_section_draws_the_table_alone_read_only_with_only_the_eye_on_lines(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                self.look(width)
                self.mount_table(report(), width)
                self.assertEqual(self.table_rows(), [l["id"] for l in LINES if l["show"]])
                self.assertEqual(self.count("[data-gantt]"), 0, "no chart, no bars")
                self.assertEqual(self.val(f"document.querySelector('{self.TABLE}').dataset.mode"), "view")
                self.assertEqual(self.count("input, select, .gt-eye, .gt-rb, .gt-rh, [data-gt-undo]"), 0, "nothing to change: no row heads, no eyes, no fields")
                self.assertEqual(self.count("[data-tpl-gantt-note]"), 0, "the note is for Edit")
                self.assertLessEqual(self.val("document.querySelector('.gt-scroll').getBoundingClientRect().right"), width - 19, "the table keeps to its width and scrolls sideways")

    def test_the_table_section_leaves_out_a_column_hidden_from_the_client(self):
        self.look(1400)
        self.mount_table(report(hidden=("owner",)), 1400)
        self.assertEqual(self.count(f"{self.TABLE} th[data-k=o]"), 0, "Owner is hidden from the client")
        self.assertEqual(self.count(f"{self.TABLE} th[data-k=n]"), 1, "the name is always there")
        self.mount_table(report(), 1400)
        self.assertEqual(self.count(f"{self.TABLE} th[data-k=o]"), 1)

    # mutation hunt (item 1230): the as-at day, the never-hidden columns and the section's ready flag were not pinned
    def status_of(self, ref):
        return self.val(f"document.querySelector('{self.TABLE} tr[data-id={ref}] td[data-k=st]').textContent")

    def test_the_table_reads_status_as_at_the_publish_day_in_a_file_and_as_today_otherwise(self):
        self.look(1400)
        self.mount_table(self.FILE_DATA, 1400, file=True, asAt="2026-11-05")
        self.assertEqual(self.status_of("GNT-2"), "In progress", "a file is read as at the day it was published")
        self.mount_table(self.FILE_DATA, 1400, file=True)
        self.assertEqual(self.status_of("GNT-2"), "Late", "a file with no day is read as at today")

    def test_the_columns_that_are_never_hidden_stay_when_the_settings_name_them(self):
        self.look(1400)
        self.mount_table(report(hidden=("type", "start", "end", "pct", "owner")), 1400)
        for key in ("t", "s", "e", "pct"):
            self.assertEqual(self.count(f"{self.TABLE} th[data-k={key}]"), 1, key)
        self.assertEqual(self.count(f"{self.TABLE} th[data-k=o]"), 0, "Owner, which may be hidden, is")

    def test_the_table_section_is_a_ready_template(self):
        self.assertEqual(self.val("K.templateFor('gantttable').ready"), True)

    def test_the_table_section_reads_a_published_file_as_the_gantt_tab_does(self):
        """A file carries data.gantt only (every line in it has its eye on; a column it does not carry is hidden)."""
        self.look(1400)
        self.mount_table(self.FILE_DATA, 1400, file=True)
        self.assertEqual(self.table_rows(), ["GNT-1", "GNT-2"])
        self.assertEqual(self.count(f"{self.TABLE} th[data-k=o], {self.TABLE} th[data-k=rag], {self.TABLE} th[data-k=note]"), 0, "columns the file does not carry are not drawn")
        self.assertEqual(self.count(f"{self.TABLE} th[data-k=s]"), 1)
        self.assertEqual(self.val("[...document.querySelectorAll('[data-tpl=gantttable] td[data-k=n]')].map(e => e.textContent)"), ["Plan", "Build"])

    def test_the_table_section_is_empty_exactly_when_the_gantt_section_is(self):
        none = [{**l, "show": False} for l in LINES]
        for d in (report(), report(none), {}, self.FILE_DATA):
            self.assertEqual(self.val(f"K.templateEmpty({{type: 'gantttable'}}, {lit(d)})"), self.val(f"K.templateEmpty({{type: 'gantt'}}, {lit(d)})"))
        self.assertTrue(self.val(f"K.templateEmpty({{type: 'gantttable'}}, {lit(report(none))})"))
        self.assertFalse(self.val(f"K.templateEmpty({{type: 'gantttable'}}, {lit(report())})"))

    def test_the_table_section_in_edit_is_the_same_read_only_table_and_the_note(self):
        self.look(1400)
        self.mount_table(report(), 1400, edit=True)
        self.assertEqual(self.table_rows(), [l["id"] for l in LINES if l["show"]], "Edit shows what the reader sees")
        self.assertEqual(self.val(f"document.querySelector('{self.TABLE}').dataset.mode"), "view")
        self.assertEqual(self.count("input, select, .gt-eye, .gt-rb, .gt-rh"), 0, "the lines are chosen on the Gantt page")
        self.assertEqual(self.val("document.querySelector('[data-tpl-gantt-note]').textContent"), "Lines are chosen on the Gantt page.")

    def test_the_table_section_in_edit_with_no_eye_on_line_says_so_in_the_charts_words(self):
        """No eye-on line: the Edit part says what the Gantt section's Edit says (the chart's own sentence), with the note, and draws no
        header-only grid. (The View leaves an empty section out, as the server does.)"""
        for width in (1400, 900):
            with self.subTest(width=width):
                self.look(width)
                self.js(f"mountSection({lit(report([{**l, 'show': False} for l in LINES]))}, {lit({'width': width - 40, 'type': 'gantttable', 'edit': True})})")
                self.assertTrue(wait(lambda: self.js("!!document.querySelector('[data-tpl=gantttable] [data-g-none]')"), 8), "the sentence is on the page")
                self.assertEqual(self.val("document.querySelector('[data-tpl=gantttable] [data-g-none]').textContent"), "No lines to show.")
                self.assertEqual(self.count(self.TABLE), 0, "no header-only grid")
                self.assertEqual(self.count("[data-gantt]"), 0, "no chart either")
                self.assertEqual(self.val("document.querySelector('[data-tpl-gantt-note]').textContent"), "Lines are chosen on the Gantt page.")
                self.assertEqual(self.val("document.querySelector('[data-tpl-gantt-left-out]').textContent"),
                                 "No Gantt line has its eye turned on, so this section is left out of the published page. Turn an eye on in the Gantt page to include it.")
        self.look(1400)
        self.mount_table(report(), 1400, edit=True)
        self.assertEqual(self.count("[data-tpl-gantt-left-out]"), 0, "with a line the section is published, so no such note")
        self.assertEqual(self.count("[data-tpl=gantttable] [data-g-none]"), 0, "with a line the table is drawn and the sentence is not")
