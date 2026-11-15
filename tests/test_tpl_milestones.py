"""Row 1192 (Milestones library template): a standalone library template that works as the Dashboard's built-in Milestones section.

Run: python3 dev/run_tests.py test_tpl_milestones

Ruling (relayed from the issue text): build Milestones as a library template (an entry in TEMPLATES, with a view part and an edit
part, store type "milestoneslib") AND keep the built-in card unchanged. The heading is "Milestones". Every other word of the entry
is an UNRULED constant in logic/templatesStrings.js. Word, Excel and the existing sections are not touched. The layout step is store.MILESTONES_LIB_STEP.
"""
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT

SRC = ROOT / "src" / "clark"
PAGE = SRC / "page" / "src"
LOGIC = PAGE / "logic"
KIND = "milestoneslib"
sys.path.insert(0, str(SRC.parent))


def node(expr, module="./templates.js", cwd=LOGIC):
    code = f'import("{module}").then((T) => console.log(JSON.stringify({expr})))'
    out = subprocess.run(["node", "--input-type=module", "-e", code], cwd=str(cwd), capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def help_rows():
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
    walk(json.loads((PAGE / "help" / "helpContent.json").read_text(encoding="utf-8")))
    return rows


class TheLibraryEntry(unittest.TestCase):
    def test_the_words_are_in_one_strings_file_as_unruled_constants(self):
        text = (LOGIC / "templatesStrings.js").read_text(encoding="utf-8")
        for name in ("MILESTONES_TITLE", "MILESTONES_UNRULED_DESCRIPTION", "MILESTONES_UNRULED_HOLDS", "MILESTONES_UNRULED_FIT"):
            self.assertIn(f"export const {name}", text)

    def test_templates_has_one_milestones_entry_with_its_own_type(self):
        cards = node('T.TEMPLATES.filter((x) => x.type === "%s")' % KIND)
        self.assertEqual(len(cards), 1)
        c = cards[0]
        self.assertEqual((c["id"], c["name"], c["title"], c["ready"]), ("milestones", "Milestones", "Milestones", True))
        self.assertTrue(c["description"].endswith("."))
        self.assertTrue(c["holds"])
        self.assertIn("full", c["fit"])
        self.assertNotIn("builtIn", c)

    def test_the_store_takes_the_type_so_the_box_offers_it(self):
        self.assertTrue(node('T.available(T.find("milestones"))'))
        self.assertIn(KIND, node("T.ACCEPTS.types"))

    def test_the_built_in_card_is_unchanged(self):
        c = node('T.BUILT_INS.filter((x) => x.type === "milestones")')
        self.assertEqual(len(c), 1)
        c = c[0]
        self.assertEqual((c["id"], c["name"], c["title"], c["builtIn"], c["description"], c["holds"], c["fit"]),
                         ("built-in-milestones", "Milestones", "Milestones", True, "", [], ["full"]))
        none = node('T.list({sections: [{id: "a", type: "text", title: "A", beside: 0, hidden: 0}]}).some((x) => x.id === "built-in-milestones")')
        self.assertTrue(none)
        have = node('T.list({sections: [{id: "a", type: "milestones", title: "M", beside: 0, hidden: 0}]}).some((x) => x.id === "built-in-milestones")')
        self.assertFalse(have)
        p = node('T.plan([{id: "a", type: "text", title: "A", beside: 0, hidden: 0}], "built-in-milestones", "a", false).requests')
        self.assertEqual(p[0]["values"], {"type": "milestones", "title": "Milestones"})

    def test_the_library_entry_plans_its_own_type_and_is_offered_even_when_the_built_in_is_there(self):
        sections = '[{id: "a", type: "milestones", title: "M", beside: 0, hidden: 0}]'
        self.assertTrue(node('T.list({sections: %s}).some((x) => x.id === "milestones")' % sections))
        p = node('T.plan(%s, "milestones", "a", false).requests' % sections)
        self.assertEqual(p[0]["values"], {"type": KIND, "title": "Milestones"})

    def test_it_has_a_sketch_and_a_help_row_in_the_entrys_words(self):
        self.assertIn("milestones", node("Object.keys(T.SKETCHES)"))
        c = node('T.find("milestones")')
        self.assertIn(("Milestones", c["description"], "Full"), help_rows())

    def test_the_entry_reads_its_words_from_the_strings_file(self):
        c = node('T.find("milestones")')
        s = node("[T.MILESTONES_TITLE, T.MILESTONES_UNRULED_DESCRIPTION, T.MILESTONES_UNRULED_HOLDS, T.MILESTONES_UNRULED_FIT]", "./templatesStrings.js")
        self.assertEqual([c["title"], c["description"], c["holds"], c["fit"]], s)


class ThePageParts(unittest.TestCase):
    def test_the_type_is_pending_and_has_a_view_and_an_edit_part(self):
        self.assertIn(KIND, node("T.PENDING_TYPES", "./types.js", PAGE / "templates"))
        self.assertNotIn(KIND, node("T.TEMPLATE_TYPES", "./types.js", PAGE / "templates"))
        view = (PAGE / "components" / "MilestonesLibSection.jsx").read_text(encoding="utf-8")
        edit = (PAGE / "edit" / "templates" / "MilestonesLibSection.jsx").read_text(encoding="utf-8")
        for text in (view, edit):
            self.assertIn("MsBlock", text)
        self.assertIn("export function View", view)
        self.assertIn("export const isEmpty", view)
        self.assertIn("export function Edit", edit)
        self.assertIn("MilestonesLibSection", (PAGE / "templates" / "index.js").read_text(encoding="utf-8"))
        self.assertIn("MilestonesLibSection", (PAGE / "edit" / "templates" / "index.js").read_text(encoding="utf-8"))


class TheStore(unittest.TestCase):
    def test_the_type_is_in_the_store_the_change_route_and_the_publisher(self):
        from clark import changes, publish, store
        self.assertIn(KIND, store.SECTION_TYPES)
        self.assertIn(KIND, changes.NEW_SECTION_TYPES)
        self.assertIn(KIND, publish.SECTION_TYPES)
        self.assertNotIn(KIND, changes.BUILT_IN_TYPES)
        self.assertIn("milestones", changes.BUILT_IN_TYPES)
        self.assertIn("'%s'" % KIND, (SRC / "schema.sql").read_text(encoding="utf-8"))

    def test_the_migration_is_step_25_and_the_latest(self):
        from clark import store
        self.assertEqual(store.SCHEMA_VERSION, store.MILESTONES_LIB_STEP)
        self.assertEqual(dict(store.MIGRATIONS)[store.MILESTONES_LIB_STEP], store.migrate_milestones_library_section_type)

    def test_a_layout_24_file_opens_with_the_new_check_and_keeps_its_rows(self):
        from clark import store
        from clark.store import open_store
        from test_store_use_case_done_migration import make_at
        d = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, d, True)
        path = make_at(d, store.MILESTONES_LIB_STEP - 1)
        con = sqlite3.connect(str(path), isolation_level=None)
        con.execute("INSERT INTO report_sections (project, id, type, title, body, beside, hidden, sort_order) VALUES ('ABC', 'ABC-S-001', 'milestones', 'Milestones', '', 0, 0, 1)")
        self.assertNotIn("'%s'" % KIND, con.execute("SELECT sql FROM sqlite_master WHERE name = 'report_sections'").fetchone()[0])
        con.close()
        s = open_store(path, onedrive_roots=[])
        try:
            pass
        finally:
            s.close()
        con = sqlite3.connect(str(path))
        try:
            self.assertIn("'%s'" % KIND, con.execute("SELECT sql FROM sqlite_master WHERE name = 'report_sections'").fetchone()[0])
            self.assertEqual(con.execute("SELECT id, type FROM report_sections").fetchall(), [("ABC-S-001", "milestones")])
            con.execute("INSERT INTO report_sections (project, id, type, title, body, beside, hidden, sort_order) VALUES ('ABC', 'ABC-S-002', ?, 'Milestones', '', 0, 0, 2)", (KIND,))
        finally:
            con.close()
        self.assertEqual(len(list((d / "backups").glob("*-migrate.db"))), 1)


class ThePublishedFile(unittest.TestCase):
    def test_the_section_is_carried_and_the_milestones_are_carried_when_only_this_section_shows_them(self):
        from clark import publish
        self.assertEqual(publish.hidden_types([{"type": "text"}, {"type": KIND}]) & {"milestones"}, {"milestones"})
        self.assertEqual(publish.row_hidden_types([{"type": "text"}, {"type": KIND}]) & {"milestones"}, set())
        self.assertEqual(publish.row_hidden_types([{"type": "text"}, {"type": KIND, "hidden": 1}]) & {"milestones"}, {"milestones"})
        self.assertEqual(publish.row_hidden_types([{"type": "text"}, {"type": "milestones"}]) & {"milestones"}, set())


if __name__ == "__main__":
    unittest.main()
