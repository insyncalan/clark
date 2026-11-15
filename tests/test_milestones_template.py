"""Item 1192: Milestones as a library template. The Add a section box offers it with the built-in's own behaviour: it makes the
same section type (milestones), so the timeline or calendar, the list, the edit in place, View, Word, Excel and the published file
are the built-in's own; the card has its words, parts, width and sketch, and Help's table of section templates says the same words.

Run: python3 dev/run_tests.py test_milestones_template
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


class MilestonesTemplate(unittest.TestCase):
    def card(self):
        return run('T.list({sections: []}).find(x => x.type === "milestones") || null')

    def test_node_is_there(self):
        self.assertTrue(NODE, "node is needed to run the page's catalogue")

    def test_the_card_has_its_words_parts_and_fit(self):
        card = self.card()
        self.assertIsNotNone(card, "the box offers Milestones when the report has none")
        self.assertEqual((card["name"], card["title"], card["type"], card["kind"]), ("Milestones", "Milestones", "milestones", "dates"))
        self.assertEqual(card["description"], "The milestones on a timeline or a calendar, with the list beneath.")
        self.assertEqual(card["holds"], ["Heading", "Timeline or Calendar · live", "Milestone list · live"])
        self.assertEqual(card["fit"], ["full"])
        self.assertIs(card["ready"], True)

    def test_the_card_has_a_sketch_for_the_box(self):
        self.assertTrue(run('!!T.SKETCHES["built-in-milestones"]'))

    def test_help_says_the_same_words_as_the_card_and_full_width(self):
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
        has = [sec("a", "text"), sec("b", "milestones")]
        self.assertIsNone(run(f'T.list({{sections: {json.dumps(has)}}}).find(x => x.type === "milestones") || null'))
        self.assertFalse(run(f'T.plan({json.dumps(has)}, "built-in-milestones", "a")')["ok"])

    def test_placing_it_sends_the_one_request_the_store_takes(self):
        got = run('T.plan([{id: "a", type: "text", title: "Summary", beside: 0}], "built-in-milestones", "a")')
        self.assertTrue(got["ok"], got)
        self.assertEqual(got["requests"], [{"op": "new", "values": {"type": "milestones", "title": "Milestones"}, "after": "a", "place": "report"}])
        self.assertIn("milestones", changes.NEW_SECTION_TYPES)
        self.assertIn("milestones", store_module.SECTION_TYPES)
        self.assertIn("milestones", publish.BUILT_IN_SECTIONS)

    def test_beside_is_refused_full_width_only(self):
        got = run('T.plan([{id: "a", type: "text", title: "Summary", beside: 0}], "built-in-milestones", "a", true)')
        self.assertFalse(got["ok"], got)
        self.assertEqual(got["message"], "This template needs the full width. Place it on its own row.")


if __name__ == "__main__":
    unittest.main()
