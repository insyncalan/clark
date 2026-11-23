"""Row 1262: the template names. Each name is pinned in the page code (templates.js, fullImageWords.js) AND as the heading of its row in Help, so a
rename that touches one side or both is caught. Source only: no browser needed.

Run: python3 dev/run_tests.py test_template_names_1262
"""
import json
import re
import unittest

from _paths import SRC

PAGE = SRC / "clark" / "page" / "src"
TEMPLATES = (PAGE / "logic" / "templates.js").read_text(encoding="utf-8")
WORDS = (PAGE / "logic" / "fullImageWords.js").read_text(encoding="utf-8")
HELP = json.loads((PAGE / "help" / "helpContent.json").read_text(encoding="utf-8"))

NAMES = {                                      # id -> the name on the card (the renamed ones, row 1262)
    "text-image": "Text and Image Side by Side",      # main's word (its own rename), not the Row 1262 list's Text with image
    "figures-4": "Numbers",
    "figures-3": "Numbers",
    "gallery": "Picture grid",
    "raid-3": "Item cards, three",
    "raid-4": "Item cards, four",
    "work-items": "Work items",
    "docs-links": "Files and links",
    "callout": "Must-see note",
    "contacts": "Who to ask",
    "checklist": "Next steps",
    "key-dates": "Coming dates",
    "link-preview": "Web page card",
    "plan-summary": "Where we are, what’s next",
    "one-doc": "One file",
}


def help_rows():
    """Every [name, description, width] row of every table in Help, found wherever they sit."""
    rows = []

    def walk(x):
        if isinstance(x, list):
            if len(x) == 3 and all(isinstance(c, str) for c in x):
                rows.append(tuple(x))
            for c in x:
                walk(c)
        elif isinstance(x, dict):
            for c in x.values():
                walk(c)
    walk(HELP)
    return rows


class TemplateNames(unittest.TestCase):
    def test_each_card_has_its_name_in_the_page_code(self):
        for id_, name in NAMES.items():
            self.assertRegex(TEMPLATES, r'\{ id: "%s", name: "%s", kind:' % (re.escape(id_), re.escape(name)), f"{id_} is called {name}")

    def test_no_built_in_keeps_a_name_from_the_old_list(self):      # row 1262 table: Use case summary -> Use cases, Supporting documents -> Documents
        from clark import changes
        old = ("Use case summary", "Supporting documents")
        lines = TEMPLATES.splitlines()
        block = next(l for l in lines if l.lstrip().startswith('builtIn("current"')) + "\n" + next(l for l in lines if l.lstrip().startswith('builtIn("milestones"'))
        for name in old:
            self.assertNotIn(f'"{name}"', block, f"the built-in cards in templates.js no longer use {name}")
            self.assertNotIn(name, changes.BUILT_IN_TITLES.values(), f"Add a section no longer makes a section titled {name}")
        self.assertIn('builtIn("usecases", "Use cases"', block)
        self.assertIn('builtIn("docs", "Documents"', block)
        self.assertEqual((changes.BUILT_IN_TITLES["usecases"], changes.BUILT_IN_TITLES["docs"]), ("Use cases", "Documents"))

    def test_the_current_card_keeps_current_state_because_cards_is_frozen(self):      # Romanoff 23-11: Cards keeps Current state; the Dashboard default is not changed
        from clark import changes, default_sections
        self.assertIn('builtIn("current", "Current state", "text"', TEMPLATES)
        self.assertEqual(changes.BUILT_IN_TITLES["current"], "Current state")
        self.assertEqual(default_sections.DEFAULT_SECTIONS[0]["title"], "Current state")
        self.assertRegex(TEMPLATES, r'\{ id: "current-state", name: "Header and Text", kind: "text", fit: \[[^\]]*\], type: "text", title: "Current state"')

    def test_the_numbers_group_is_in_the_picker(self):      # Romanoff 23-11 ruling point 3: the picker group Figures is named Numbers
        self.assertRegex(TEMPLATES, r'\{ id: "figures", name: "Numbers" \}')

    def test_the_gantt_table_card_is_called_gantt_table(self):
        self.assertIn('export const GANTT_TABLE_NAME = "Gantt table";', TEMPLATES)
        self.assertRegex(TEMPLATES, r'\{ id: "gantt-table", name: GANTT_TABLE_NAME, ')

    def test_the_two_picture_cards_keep_their_names(self):      # row 1223 replaces them with one Image card
        self.assertRegex(WORDS, r'WORDS = \{\s+name: "Full width image",')
        self.assertRegex(TEMPLATES, r'\{ id: "image-caption", name: "Image with caption", kind:')

    def test_help_has_a_row_headed_with_each_name(self):
        heads = [r[0] for r in help_rows()]
        for name in set(NAMES.values()) | {"Image with caption", "Full width image"}:
            self.assertIn(name, heads, f"Help has a row headed {name}")
        self.assertEqual(heads.count("Numbers"), 2, "the two Numbers cards have a row each")

    def test_help_rows_for_the_old_names_are_gone(self):
        heads = [r[0] for r in help_rows()]
        for old in ("Key figures, four", "Key figures, three", "Image gallery", "RAID cards, three", "RAID cards, four", "Work items list", "Live work list",
                    "Documents and links", "Callout", "One picture", "Wide picture", "Contacts", "Checklist", "Key dates",
                    "Link preview", "One document", "Plan summary", "Text and image"):
            self.assertNotIn(old, heads, old)

    def test_the_card_a_help_row_describes_has_the_row_s_name(self):
        by_desc = {}
        for r in help_rows():
            by_desc.setdefault(r[1], set()).add(r[0])
        for id_, name in NAMES.items():
            m = re.search(r'\{ id: "%s", name: "[^"]+".*?description: "([^"]+)"' % re.escape(id_), TEMPLATES, re.S)
            self.assertTrue(m, id_)
            self.assertIn(name, by_desc.get(m.group(1), set()), f"{id_}: the Help row with its description is headed {name}")

    def test_the_help_how_to_names_two_cards_by_their_new_names(self):
        text = json.dumps(HELP)
        self.assertIn("such as **Numbers** or **Must-see note**", text)


if __name__ == "__main__":
    unittest.main()
