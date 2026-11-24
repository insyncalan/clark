"""Row 1575 (part of row 1262, AP15): the cards that keep their name keep it. Text, Quote, Table and Gantt are pinned here by name, in the page
code and in the catalogue the Add a section box lists. Report headline, Project at a glance and Milestones are pinned by their own tests (named
in KEPT_ELSEWHERE) and this file checks those tests still hold the name. Source only, plus the catalogue read in node: no browser, no layout.

Run: python3 dev/run_tests.py test_template_kept_names_1575
"""
import json
import re
import shutil
import subprocess
import unittest

from _paths import SRC, ROOT

PAGE = SRC / "clark" / "page" / "src"
TEMPLATES_JS = PAGE / "logic" / "templates.js"
TEMPLATES = TEMPLATES_JS.read_text(encoding="utf-8")

KEPT = {"text": "Text", "quote": "Quote", "table": "Table", "gantt": "Gantt"}      # id -> the name on the card, unchanged by row 1262

KEPT_ELSEWHERE = {      # file -> the text that pins the name there
    "test_reportheadline_eye_1261.py": 'name: "Report headline"',
    "test_glance_template.py": '"Project at a glance"',
    "test_milestones_template.py": '"Milestones"',
}


def catalogue_names():
    """[id, name] of every card the box lists, read by node from the real templates.js."""
    node = shutil.which("node")
    if not node:
        raise AssertionError("node is needed to read the catalogue (this test fails, never skips)")
    script = f"import * as T from {json.dumps(TEMPLATES_JS.as_uri())}; console.log(JSON.stringify(T.list().map((x) => [x.id, x.name])));"
    out = subprocess.run([node, "--input-type=module", "-e", script], capture_output=True, text=True, timeout=60, cwd=str(ROOT))
    if out.returncode != 0:
        raise AssertionError(f"node could not read the catalogue: {out.stderr[-500:]}")
    return json.loads(out.stdout)


class KeptNames(unittest.TestCase):
    def test_text_quote_table_and_gantt_keep_their_names(self):
        for id_, name in KEPT.items():
            self.assertRegex(TEMPLATES, r'\{ id: "%s", name: "%s", kind:' % (re.escape(id_), re.escape(name)), f"{id_} is still called {name}")

    def test_the_box_lists_each_kept_name_once(self):
        cat = catalogue_names()
        for id_, name in KEPT.items():
            self.assertEqual([c for c in cat if c[0] == id_], [[id_, name]], f"the box lists {id_} once, as {name}")
            self.assertEqual([c[0] for c in cat if c[1] == name], [id_], f"only {id_} is called {name}")

    def test_the_other_three_kept_names_stay_pinned_by_their_own_tests(self):
        cat = dict(catalogue_names())
        self.assertEqual(cat["report-headline"], "Report headline")
        self.assertEqual(cat["glance-template"], "Project at a glance")
        for fname, text in KEPT_ELSEWHERE.items():
            src = (ROOT / "tests" / fname).read_text(encoding="utf-8")
            self.assertIn(text, src, f"{fname} still pins the name")


if __name__ == "__main__":
    unittest.main()
