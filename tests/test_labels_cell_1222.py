"""Item 1195 slice S6 (row 1222): the Labels column of the Work items table, drawn for real in Chrome (one browser at a time).

Run: python3 dev/run_tests.py test_labels_cell_1222
"""
import json
import sys
import unittest

from clark.store import open_store
from test_inline_edits import need_chrome, tearDownModule  # noqa: F401
from test_server import chrome, wait
from test_table_columns import Columns as _Columns, TABLES


class LabelsCell(unittest.TestCase):
    setUp = _Columns.setUp
    visit = _Columns.visit
    open_table = _Columns.open_table
    right_click = _Columns.right_click
    menu = _Columns.menu
    heads = _Columns.heads
    pick = _Columns.pick

    def read(self, code, archived="hide"):
        st = open_store(self.path, onedrive_roots=[])
        try:
            d = st.data_for(code, archived=archived)
        finally:
            st.close()
        ids = sorted(r["id"] for k in ("actions", "raid", "decisions") for r in d[k])
        d["labels"] = {ids[0]: ["Sensitive", "Board"]}
        self.first = ids[0]
        return d

    def test_the_menu_lists_labels_and_ticking_it_draws_the_names_in_that_row_and_a_dash_in_the_others(self):
        with chrome() as cdp:
            sid, js = self.open_table(cdp, 1400, "light", "work")
            self.right_click(cdp, sid, TABLES["work"][2] % "owner")
            self.assertTrue(wait(lambda: self.menu(js), 5), "the menu opens")
            self.assertIn("Labels", [i["name"] for i in self.menu(js)["items"]], "the menu offers Labels")
            self.pick(js, "Labels")
            self.assertTrue(wait(lambda: "labels" in self.heads(js, "work"), 5), "the column appears")
            sel = f"#work tbody tr[data-id={json.dumps(self.first)}] td[data-col=labels]"
            self.assertEqual(js(f"(document.querySelector({json.dumps(sel)}) || {{}}).textContent"), "Sensitive, Board")
            others = js("[...document.querySelectorAll('#work tbody tr[data-id] td[data-col=labels]')].map((e) => e.textContent.trim())")
            self.assertEqual(sorted(set(others)), ["Sensitive, Board", "—"])


# The class is borrowed from, not run again here: left as a module name, unittest would collect all of its tests into this file as well.
del _Columns


class OwnTestsOnly(unittest.TestCase):
    def test_this_file_collects_only_its_own_test_classes(self):
        """Importing the Columns class by name made unittest run all of its tests here as well (30 more browser launches; the macOS shard timed out)."""
        found = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
        classes = set()
        todo = [found]
        while todo:
            for t in todo.pop():
                (todo.append(t) if isinstance(t, unittest.TestSuite) else classes.add(type(t).__name__))
        self.assertEqual(classes, {"LabelsCell", "OwnTestsOnly"})


if __name__ == "__main__":
    unittest.main()
