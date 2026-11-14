"""Row 1192 (Milestones template): the library card named Milestones, and what stays as it is.

Run: python3 dev/run_tests.py test_tpl_milestones
Quick tier: reads files and runs the page logic in node, starts no browser.

Ruling: the library offers Milestones only as the existing built-in card. No extra wording, no second card.
The store type stays "milestones"; Word, Excel and the published file are not touched by this row.
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
    def test_one_built_in_card_and_no_extra_wording(self):
        cards = node('[...T.TEMPLATES, ...T.BUILT_INS].filter((x) => x.type === "milestones")')
        self.assertEqual(len(cards), 1, "one card, not two")
        c = cards[0]
        self.assertEqual((c["name"], c["title"], c["builtIn"], c["description"], c["holds"]), ("Milestones", "Milestones", True, "", []))
        self.assertFalse((LOGIC / "templatesStrings.js").exists())

    def test_it_is_still_offered_only_when_the_report_has_none_and_plans_the_same_request(self):
        none = node('T.list({sections: [{id: "a", type: "text", title: "A", beside: 0, hidden: 0}]}).some((x) => x.id === "built-in-milestones")')
        self.assertTrue(none)
        have = node('T.list({sections: [{id: "a", type: "milestones", title: "M", beside: 0, hidden: 0}]}).some((x) => x.id === "built-in-milestones")')
        self.assertFalse(have)
        p = node('T.plan([{id: "a", type: "text", title: "A", beside: 0, hidden: 0}], "built-in-milestones", "a", false).requests')
        self.assertEqual(p[0]["values"], {"type": "milestones", "title": "Milestones"})

    def test_help_has_no_new_milestones_card_row(self):
        text = (SRC / "page" / "src" / "help" / "helpContent.json").read_text(encoding="utf-8")
        self.assertNotIn("The project\u2019s milestones on a timeline", text)
        self.assertNotIn("The project’s milestones on a timeline", text)

    def test_the_store_and_first_run_are_unchanged(self):
        import sys
        sys.path.insert(0, str(SRC.parent))
        from clark import changes, default_sections
        self.assertIn("milestones", changes.BUILT_IN_TYPES)
        self.assertIn("milestones", [s["type"] for s in default_sections.DEFAULT_SECTIONS])
        self.assertIn("milestones", changes.NEW_SECTION_TYPES)


if __name__ == "__main__":
    unittest.main()
