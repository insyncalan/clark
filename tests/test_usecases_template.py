"""Item 1191: Use case summary as a library template. The Add a section box offers it with the built-in's own behaviour: it makes the
same section type (usecases), so the strip, the rows, the edit in place, View, Word, Excel and the published file are the built-in's own;
the card has its words, parts and sketch, and Help's table of section templates says the same words.

Run: python3 dev/run_tests.py test_usecases_template
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


class UseCasesTemplate(unittest.TestCase):
    def card(self):
        return run('T.list({sections: []}).find(x => x.type === "usecases") || null')

    def test_node_is_there(self):
        self.assertTrue(NODE, "node is needed to run the page's catalogue")

    def test_the_card_has_its_words_parts_and_fit(self):
        card = self.card()
        self.assertIsNotNone(card, "the box offers Use case summary when the report has none")
        self.assertEqual((card["name"], card["title"], card["type"], card["kind"]), ("Use cases", "Use cases", "usecases", "work"))
        self.assertTrue(card["description"].endswith("."))
        self.assertEqual(card["holds"], ["Heading", "Count for each status", "A row for each use case", "Where it stands", "Next steps"])
        self.assertEqual(card["fit"], ["full"])
        self.assertIs(card["ready"], True)

    def test_the_card_has_a_sketch_for_the_box(self):
        self.assertTrue(run('!!T.SKETCHES["built-in-usecases"]'))

    def test_help_says_the_same_words_as_the_card(self):
        card = self.card()
        rows = []

        def walk(o):
            if isinstance(o, dict):
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                if len(o) == 3 and all(isinstance(x, str) for x in o):
                    rows.append(tuple(o))
                for v in o:
                    walk(v)
        walk(json.loads(HELP.read_text(encoding="utf-8")))
        self.assertIn((card["name"], card["description"], "Full"), rows)

    def test_it_is_offered_once_like_the_built_in_and_not_while_it_is_there(self):
        has = [sec("a", "text"), sec("b", "usecases")]
        self.assertIsNone(run(f'T.list({{sections: {json.dumps(has)}}}).find(x => x.type === "usecases") || null'))
        gone = run(f'T.plan({json.dumps(has)}, "built-in-usecases", "a")')
        self.assertFalse(gone["ok"])

    def test_placing_it_sends_the_one_request_the_store_takes(self):
        got = run('T.plan([{id: "a", type: "text", title: "Summary", beside: 0}], "built-in-usecases", "a")')
        self.assertTrue(got["ok"], got)
        self.assertEqual(got["requests"], [{"op": "new", "values": {"type": "usecases", "title": "Use cases"}, "after": "a", "place": "report"}])
        self.assertEqual(got["words"], "Use cases added.")
        self.assertIn("usecases", changes.NEW_SECTION_TYPES)
        self.assertIn("usecases", store_module.SECTION_TYPES)
        self.assertIn("usecases", publish.BUILT_IN_SECTIONS, "the published file draws the section by its type, as for the built-in")

    def test_beside_is_refused_since_a_row_is_a_grid_of_fixed_columns(self):
        got = run('T.plan([{id: "a", type: "text", title: "Summary", beside: 0}], "built-in-usecases", "a", true)')
        self.assertFalse(got["ok"], got)
        self.assertEqual(got["message"], "This template needs the full width. Place it on its own row.")


if __name__ == "__main__":
    unittest.main()
