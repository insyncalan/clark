"""Row 1192 (Milestones template): the library card named Milestones, and what stays as it is.

Run: python3 dev/run_tests.py test_tpl_milestones
Quick tier: reads files and runs the page logic in node, starts no browser.

The card is the built-in re-add card (one card, not two). Its words live in logic/templatesStrings.js as UNRULED constants,
until they are ruled. The store type stays "milestones"; Word, Excel and the published file are not touched by this row.
"""
import json
import subprocess
import unittest

from _paths import ROOT

SRC = ROOT / "src" / "clark"
LOGIC = SRC / "page" / "src" / "logic"


def node(expr):
    code = f'import("./templates.js").then((T) => console.log(JSON.stringify({expr})))'
    out = subprocess.run(["node", "--input-type=module", "-e", code], cwd=str(LOGIC), capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


class MilestonesTemplate(unittest.TestCase):
    def test_the_words_are_in_one_strings_file_as_unruled_constants(self):
        text = (LOGIC / "templatesStrings.js").read_text(encoding="utf-8")
        for name in ("MILESTONES_NAME", "MILESTONES_TITLE", "MILESTONES_UNRULED_DESCRIPTION", "MILESTONES_UNRULED_HOLDS", "MILESTONES_UNRULED_FIT"):
            self.assertIn(f"export const {name}", text)

    def test_one_card_named_milestones_with_description_holds_and_fit(self):
        cards = node('[...T.TEMPLATES, ...T.BUILT_INS].filter((x) => x.type === "milestones")')
        self.assertEqual(len(cards), 1, "one card, not two")
        c = cards[0]
        self.assertEqual((c["name"], c["title"], c["type"], c["ready"]), ("Milestones", "Milestones", "milestones", True))
        self.assertTrue(c["description"].endswith("."))
        self.assertTrue(c["holds"])
        self.assertEqual(c["fit"], ["full"])

    def test_it_is_still_offered_only_when_the_report_has_none_and_plans_the_same_request(self):
        none = node('T.list([{id: "a", type: "text", title: "A", beside: 0, hidden: 0}]).some((x) => x.id === "built-in-milestones")')
        self.assertTrue(none)
        have = node('T.list([{id: "a", type: "milestones", title: "M", beside: 0, hidden: 0}]).some((x) => x.id === "built-in-milestones")')
        self.assertFalse(have)
        p = node('T.plan([{id: "a", type: "text", title: "A", beside: 0, hidden: 0}], "built-in-milestones", "a", false).requests')
        self.assertEqual(p[0]["values"], {"type": "milestones", "title": "Milestones"})

    def test_help_has_a_row_in_the_cards_words(self):
        help_ = json.loads((SRC / "page" / "src" / "help" / "helpContent.json").read_text(encoding="utf-8"))
        rows = []

        def walk(o):
            if isinstance(o, list):
                if len(o) == 3 and all(isinstance(x, str) for x in o):
                    rows.append(tuple(o))
                for v in o:
                    walk(v)
            elif isinstance(o, dict):
                for v in o.values():
                    walk(v)
        walk(help_)
        c = node('T.BUILT_INS.find((x) => x.type === "milestones")')
        self.assertIn(("Milestones", c["description"], "Full"), rows)

    def test_the_store_and_first_run_are_unchanged(self):
        import sys
        sys.path.insert(0, str(SRC.parent))
        from clark import changes, default_sections
        self.assertIn("milestones", changes.BUILT_IN_TYPES)
        self.assertIn("milestones", [s["type"] for s in default_sections.DEFAULT_SECTIONS])
        self.assertIn("milestones", changes.NEW_SECTION_TYPES)


if __name__ == "__main__":
    unittest.main()
