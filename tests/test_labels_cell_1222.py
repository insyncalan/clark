"""Item 1195 slice S6 (row 1222): the Labels column of the Work items table, drawn for real in Chrome (one browser at a time).

Run: python3 dev/run_tests.py test_labels_cell_1222
"""
import json
import unittest

from clark.store import open_store
from test_inline_edits import need_chrome, tearDownModule  # noqa: F401
from test_server import chrome, wait
from test_table_columns import Columns, TABLES


class LabelsCell(unittest.TestCase):
    setUp = Columns.setUp
    visit = Columns.visit
    open_table = Columns.open_table
    right_click = Columns.right_click
    menu = Columns.menu
    heads = Columns.heads
    pick = Columns.pick

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


if __name__ == "__main__":
    unittest.main()
