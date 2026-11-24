"""Row 1534, AP5 test 6: the order set on the Work items page for a type is the order the Dashboard sections (Risks and issues, Open actions, Decisions) draw, in the page and
in the published report. One order for each type; the Dashboard has no order of its own. The Dashboard's ids (ico, title, owner, date, prio, id) map to the work ids (status,
item, owner, due, prio, id); a saved order that names the id loses it in a published file (a file has no Id column). Cards are not touched.

Run: python3 dev/run_tests.py test_column_order_dashboard_1534
The mapping runs in node on the bundled page source; the drawing (a real list in Chrome, 1400 and 900 px, light and dark) is NOT run by this file: source pins only. Fictional data only.
"""
import re
import unittest

from test_column_order_1534 import PAGE_SRC, run_node, source


def order(saved, section, with_id):
    return run_node(f"CO.dashboardOrder({saved}, {section!r}, {str(with_id).lower()})")


STD = ["ico", "title", "owner", "date", "prio", "id"]


class Mapping(unittest.TestCase):
    def test_the_order_set_on_a_dashboard_section_is_in_the_published_report(self):
        saved = '{"actions": ["status", "item", "prio", "owner", "due", "id"]}'
        self.assertEqual(order(saved, "actions", False), ["ico", "title", "prio", "owner", "date"])      # the file: no id
        self.assertEqual(order(saved, "actions", True), ["ico", "title", "prio", "owner", "date", "id"])      # the page keeps the id where it was saved
        self.assertEqual(order(f"JSON.stringify({saved})", "actions", False), ["ico", "title", "prio", "owner", "date"])      # the project carries it as text

    def test_each_section_reads_its_own_type(self):
        saved = '{"risks": ["status", "item", "date_not_a_column", "due", "owner", "prio"], "decisions": ["status", "item", "prio", "due", "owner"]}'
        self.assertEqual(order(saved, "raid", True), ["ico", "title", "date", "owner", "prio", "id"])
        self.assertEqual(order(saved, "decisions", True), ["ico", "title", "prio", "date", "owner", "id"])
        self.assertEqual(order(saved, "actions", True), STD)      # nothing saved for the actions: the standard order

    def test_a_saved_id_is_dropped_in_a_file(self):
        saved = '{"risks": ["status", "item", "id", "due", "owner", "prio"]}'
        self.assertEqual(order(saved, "raid", False), ["ico", "title", "date", "owner", "prio"])
        self.assertNotIn("id", order(saved, "raid", False))

    def test_status_and_title_always_lead_and_unnamed_columns_keep_their_place(self):
        self.assertEqual(order('{"actions": ["owner", "status", "item"]}', "actions", True), STD)
        self.assertEqual(order('{"actions": ["status", "item", "prio"]}', "actions", False), ["ico", "title", "prio", "owner", "date"])
        self.assertEqual(order('{"actions": ["status", "item", "prio", "prio", "workstream", "type"]}', "actions", True), ["ico", "title", "prio", "owner", "date", "id"])

    def test_nothing_or_rubbish_saved_draws_the_standard_order(self):
        for saved in ("null", "'not json'", "'[1]'", '{"actions": "x"}', "{}", "undefined"):
            self.assertEqual(order(saved, "actions", True), STD, saved)
        self.assertEqual(order('{"actions": ["status", "item", "prio"]}', "unknown", True), STD)      # a type with no switch (the All view) has no order
        self.assertEqual(run_node("CO.DASH_STD"), STD)


class Source(unittest.TestCase):
    def test_both_drawings_read_the_one_order_and_keep_none_of_their_own(self):
        rows, edit = source("components", "ItemRows.jsx"), source("edit", "ItemRowsEdit.jsx")
        self.assertIn("dashboardOrder(d && d.project ? d.project.column_orders : null, type, id)", rows)
        for text in (rows, edit):
            self.assertIn("cols.list.map((c) => cell[c])", text)
            self.assertNotRegex(text, r"remember\(|recall\(|localStorage|readChoice|writeChoice")      # the order is the project's, never a browser key
        self.assertIn("columnsFor(type, true)", edit)
        self.assertIn("columnsFor(type, !inFile)", rows)      # a file has no Id column

    def test_the_head_follows_the_order_and_stays_hidden_from_a_screen_reader(self):
        rows = source("components", "ItemRows.jsx")
        self.assertRegex(rows, r'<li class="wl-head" aria-hidden="true">\{list\.map\(\(c\) => head\[c\]\)\}</li>')
        self.assertNotIn("onDrag", rows)      # AP5 builds the order, not a drag on the Dashboard head
        self.assertNotIn("draggable", rows)

    def test_the_standard_order_adds_nothing_to_the_markup(self):
        rows = source("components", "ItemRows.jsx")
        self.assertIn('const place = (ord, c) => (ord ? { "--s": DASH_STD.indexOf(c) } : undefined);', rows.replace("export ", ""))
        self.assertIn("attrs: ord ? {", rows)
        self.assertIn(": {} }", rows)

    def test_the_css_gives_each_name_a_width_and_keeps_the_narrow_layouts_standard(self):
        css = (PAGE_SRC.parent / "shell.css").read_text(encoding="utf-8")
        for var in ("--w-ico", "--w-owner", "--w-date", "--w-prio", "--w-id"):
            self.assertIn(var + ":", css)
        self.assertRegex(css, r"@media \(min-width: 901px\) \{\s*\.irows\[data-ord\] \.wl-row, \.irows\[data-ord\] \.wl-head \{ grid-template-columns: var\(--cols-ord\); \}")
        self.assertRegex(css, r"@container half \(max-width: 700px\) \{\s*\.irows\[data-ord\] \.wl-row, \.irows\[data-ord\] \.wl-head \{ grid-template-columns: var\(--cols\); \}")
        self.assertIn("order: var(--s)", css)
        self.assertIn("minmax(0, 1fr)", source("components", "ItemRows.jsx"))

    def test_cards_are_not_touched(self):
        rows = source("components", "ItemRows.jsx") + source("edit", "ItemRowsEdit.jsx")
        self.assertIsNone(re.search(r"cards?\b.*column_orders", rows, re.I))
        self.assertFalse((PAGE_SRC / "components" / "Cards.jsx").exists() and "dashboardOrder" in source("components", "Cards.jsx"))


if __name__ == "__main__":
    unittest.main()
