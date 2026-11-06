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
        entry = text[text.index('{ id: "gantt"'):text.index('{ id: "one-doc"')]
        self.assertIn('fit: ["full"]', entry)
        self.assertIn("The plan as bars on a timeline, from your Gantt lines. Only lines put on the dashboard show.", entry)
        self.assertIn('holds: ["Heading", "The Gantt chart"]', entry)


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
