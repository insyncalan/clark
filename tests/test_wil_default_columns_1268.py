"""Row 1268: a new Work items list starts without the Type column (the letter tile already shows the kind).

Run: python3 dev/run_tests.py test_wil_default_columns_1268
Quick tier: no browser. The page's default (templates/workItemsList.js) and the saved start body (section_kinds/workitems.py) are held together.
"""
import json
import sys
import unittest

from _paths import SRC
from test_workitems_views_node import run_node

sys.path.insert(0, str(SRC))
from clark.section_kinds import workitems as wi  # noqa: E402

WANT = ["id", "owner", "due", "priority"]


class DefaultColumns(unittest.TestCase):
    def test_the_page_default_has_no_type(self):
        self.assertEqual(run_node("W.DEFAULT_COLUMNS"), WANT)
        self.assertEqual(run_node("W.defaults().columns"), WANT)

    def test_the_saved_start_body_has_no_type(self):
        self.assertEqual(json.loads(wi.START)["columns"], WANT)

    def test_a_saved_list_keeps_the_columns_and_the_order_it_names(self):
        saved = ["type", "id", "owner", "due", "priority"]
        body = json.loads(wi.START)
        body["columns"] = saved
        self.assertEqual(wi.check(body, None)["columns"], saved)
        self.assertEqual(run_node("W.listOf({items: [], columns: " + json.dumps(saved) + "}, {}, '2030-01-01').columns"), saved)

    def test_a_list_or_file_that_names_no_column_shows_what_it_always_showed(self):
        old = ["type", "id", "owner", "due", "priority"]
        self.assertEqual(run_node("W.listOf({items: [], columns: []}, {}, '2030-01-01').columns"), old)
        self.assertEqual(run_node("W.listOf({items: []}, {}, '2030-01-01').columns"), old)
        self.assertNotEqual(old, WANT)

    def test_a_saved_filter_body_with_no_columns_key_keeps_type(self):
        old = ["type", "id", "owner", "due", "priority"]
        body = json.loads(wi.START)
        del body["columns"]
        self.assertEqual(wi.check(body, None)["columns"], old)
        js = json.dumps(json.dumps(body))
        self.assertEqual(run_node("W.filterOf({body: " + js + "}).columns"), old)
        self.assertEqual(run_node("W.filterOf({body: JSON.stringify(W.defaults())}).columns"), WANT)

    def test_type_is_still_a_choice(self):
        self.assertIn("type", wi.COLUMNS)
        self.assertIn("type", run_node("W.COLUMNS"))


if __name__ == "__main__":
    unittest.main()
