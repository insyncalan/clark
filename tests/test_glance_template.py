"""Row 1411: the built-in At a glance card is not in the Add a section box. "Project at a glance" stays. A report that already has an
At a glance section keeps it: the section type, its tiles and every reader are unchanged.

Run: python3 dev/run_tests.py test_glance_template
No Chrome: the page's catalogue (logic/templates.js) runs in node. Fictional data only.
"""
import json
import shutil
import subprocess
import unittest

from _paths import SRC
from clark import changes, publish, store as store_module

LOGIC = SRC / "clark" / "page" / "src" / "logic" / "templates.js"
HELP = SRC / "clark" / "page" / "src" / "help" / "helpContent.json"
NODE = shutil.which("node")


def run(expr):
    script = f'import * as T from {json.dumps(LOGIC.as_uri())}; console.log(JSON.stringify({expr}));'
    got = subprocess.run([NODE, "--input-type=module", "-e", script], capture_output=True, text=True, timeout=60)
    assert got.returncode == 0, got.stderr
    return json.loads(got.stdout)


class GlanceCardRemoved(unittest.TestCase):
    def test_node_is_there(self):
        self.assertTrue(NODE, "node is needed to run the page's catalogue")

    def test_the_box_has_no_at_a_glance_card_with_or_without_the_section(self):
        for secs in ([], [{"id": "a", "type": "text", "title": "t", "beside": 0}]):
            names = run(f'T.list({{sections: {json.dumps(secs)}}}).map(x => x.name)')
            self.assertNotIn("At a glance", names)
            self.assertEqual(run(f'T.list({{sections: {json.dumps(secs)}}}).filter(x => x.type === "glance").length'), 0)

    def test_it_has_no_catalogue_entry_or_plan(self):
        self.assertIsNone(run('T.find("built-in-glance")'))
        # the sketch entry stays: the Cards look is frozen and the entry is part of its pin; no card can reach it
        got = run('T.plan([{id: "a", type: "text", title: "Summary", beside: 0}], "built-in-glance", "a")')
        self.assertFalse(got["ok"], got)

    def test_project_at_a_glance_stays(self):
        card = run('T.list({sections: []}).find(x => x.id === "glance-template") || null')
        self.assertIsNotNone(card)
        self.assertEqual((card["name"], card["type"]), ("Project at a glance", "glancetemplate"))

    def test_help_table_has_no_at_a_glance_row_but_keeps_project_at_a_glance(self):
        names = []

        def walk(o):
            if isinstance(o, dict):
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                if len(o) == 3 and all(isinstance(x, str) for x in o):
                    names.append(o[0])
                for v in o:
                    walk(v)
        walk(json.loads(HELP.read_text(encoding="utf-8")))
        self.assertNotIn("At a glance", names)
        self.assertIn("Project at a glance", names)

    def test_existing_glance_sections_still_work(self):
        self.assertIn("glance", changes.NEW_SECTION_TYPES)
        self.assertIn("glance", store_module.SECTION_TYPES)
        self.assertIn("glance", publish.BUILT_IN_SECTIONS)
        self.assertTrue(run('T.ACCEPTS.types.includes("glance")'))


if __name__ == "__main__":
    unittest.main()
