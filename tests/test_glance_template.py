"""Item 1190 (card removed by row 1411): At a glance was a library template. The Add a section box offers it with the built-in's own behaviour: it makes the
same section type (glance), so the tiles, the edit in place, View, Word, Excel and the published file are the built-in's own;
the card has its words, parts and sketch, and Help's table of section templates says the same words.

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
    """Evaluate a JS expression against the page's templates.js and return it as JSON."""
    script = f'import * as T from {json.dumps(LOGIC.as_uri())}; console.log(JSON.stringify({expr}));'
    got = subprocess.run([NODE, "--input-type=module", "-e", script], capture_output=True, text=True, timeout=60)
    assert got.returncode == 0, got.stderr
    return json.loads(got.stdout)


def sec(i, type_):
    return {"id": i, "type": type_, "title": type_, "beside": 0}


class GlanceTemplate(unittest.TestCase):
    def card(self):
        return run('T.list({sections: []}).find(x => x.type === "glance") || null')

    def test_node_is_there(self):
        self.assertTrue(NODE, "node is needed to run the page's catalogue")

    def test_row_1411_the_card_is_gone_but_the_section_type_stays(self):
        """Row 1411: the box offers no At a glance card (with or without a glance section); the type stays in the store, so a report that
        holds one keeps it, and the published file still draws it by its type."""
        self.assertIsNone(self.card(), "no At a glance card")
        self.assertIsNone(run('T.find("built-in-glance")'))
        self.assertIsNone(run('T.SKETCHES["built-in-glance"] || null'))
        has = [sec("a", "text"), sec("b", "glance")]
        self.assertIsNone(run(f'T.list({{sections: {json.dumps(has)}}}).find(x => x.type === "glance") || null'))
        self.assertFalse(run(f'T.plan({json.dumps(has)}, "built-in-glance", "a")')["ok"])
        self.assertIn("glance", changes.NEW_SECTION_TYPES)
        self.assertIn("glance", store_module.SECTION_TYPES)
        self.assertIn("glance", publish.BUILT_IN_SECTIONS, "the published file draws the section by its type, as for the built-in")

    def test_help_has_no_row_for_the_card(self):
        text = HELP.read_text(encoding="utf-8")
        self.assertNotIn("The project’s health, and counts of overdue actions, high risks and issues, and decisions needed.", text)


if __name__ == "__main__":
    unittest.main()
