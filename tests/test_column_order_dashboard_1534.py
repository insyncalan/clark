"""Row 1534, AP5 test 6: the order set on the Work items page for a type is the order the Dashboard sections (Risks and issues, Open actions, Decisions) draw, in the page and
in the published report. One order for each type; the Dashboard has no order of its own. The Dashboard's ids (ico, title, owner, date, prio, id) map to the work ids (status,
item, owner, due, prio, id); a saved order that names the id loses it in a published file (a file has no Id column). Cards are not touched.

Run: python3 dev/run_tests.py test_column_order_dashboard_1534
The mapping runs in node on the bundled page source; the drawing (a real list in Chrome, 1400 and 900 px, light and dark) is NOT run by this file: source pins only. Fictional data only.
"""
import json
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
        self.assertIn("dashboardOrder(d && d.project ? d.project.column_orders : null, type, id, classic)", rows)
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
        from clark import theme
        css = theme.css("prototype-2.0")      # the Classic theme layer: shell.css and edit.css are shared with Cards, whose page keeps its bytes (the byte pins)
        for shared in (PAGE_SRC.parent / "shell.css", PAGE_SRC / "edit" / "edit.css"):
            self.assertNotIn("Row 1534", shared.read_text(encoding="utf-8"), shared.name + ": the rules for the saved order are in the Classic layer only")
        for var in ("--w-ico", "--w-owner", "--w-date", "--w-prio", "--w-id"):
            self.assertIn(var + ":", css)
        self.assertRegex(css, r"@media \(min-width: 901px\) \{\s*\.irows\[data-ord\] \.wl-row, \.irows\[data-ord\] \.wl-head \{ grid-template-columns: var\(--cols-ord\); \}")
        self.assertRegex(css, r"@container half \(max-width: 700px\) \{\s*\.irows\[data-ord\] \.wl-row, \.irows\[data-ord\] \.wl-head \{ grid-template-columns: var\(--cols\); \}")
        self.assertIn("order: var(--s)", css)
        self.assertIn("minmax(0, 1fr)", source("components", "ItemRows.jsx"))
        self.assertIn(".wil-table th.col-move { cursor: grab; touch-action: none; }", css)      # a finger drags the heading of a Dashboard list (Edit only: the class comes from edit/colWidths.jsx)
        self.assertNotIn("data-move", css)      # the published file carries the theme: no edit-only hook name in it
        self.assertIn('id === "status" || !ids || !ids.includes(id) ? "" : " col-move"', source("edit", "colWidths.jsx"))

class Cards(unittest.TestCase):
    """PM ruling: Cards are frozen. The saved order (drag, Move items, the table's and the Dashboard's drawing) is the Classic look's; Cards draws the standard order, as on main."""

    SAVED = '{"actions": ["status", "item", "prio", "owner", "due", "id"], "risks": ["status", "item", "prio", "owner", "due", "id"]}'

    def test_the_dashboard_mapping_given_cards_is_the_standard_order(self):
        for with_id in (True, False):
            std = [c for c in STD if with_id or c != "id"]
            self.assertEqual(run_node(f"CO.dashboardOrder({self.SAVED}, 'actions', {str(with_id).lower()}, false)"), std)
            self.assertEqual(run_node(f"CO.dashboardOrder({self.SAVED}, 'raid', {str(with_id).lower()}, false)"), std)
        self.assertNotEqual(order(self.SAVED, "actions", True), STD)      # the same saved order does move the columns in the Classic look
        self.assertEqual(run_node(f"CO.dashboardOrder({self.SAVED}, 'actions', true, true)"), order(self.SAVED, "actions", True))

    def test_the_table_order_given_cards_is_what_it_was_given(self):
        shown = '["status", "item", "owner", "due", "prio", "id"]'
        self.assertEqual(run_node(f"CO.shownOrder(false, {shown}, {self.SAVED}, 'action')"), json.loads(shown))
        self.assertEqual(run_node(f"CO.shownOrder(true, {shown}, {self.SAVED}, 'action')"), ["status", "item", "prio", "owner", "due", "id"])

    def test_cards_add_nothing_to_the_markup(self):
        # the standard order draws no data-ord, no --cols-ord and no --s: the attrs are empty when the list is the standard one
        rows = source("components", "ItemRows.jsx")
        self.assertIn("attrs: ord ? {", rows)
        self.assertIn("const ord = !list.every((c, i) => c === std[i]);", rows)

    def test_every_use_of_the_saved_order_is_behind_the_classic_check(self):
        rows, edit, work, menu = (source("components", "ItemRows.jsx"), source("edit", "ItemRowsEdit.jsx"), source("components", "WorkItems.jsx"), source("edit", "ColumnsMenu.jsx"))  # the menu is read only for the Cards line below; no Move or Reset menu line is pinned here
        self.assertIn("export function columnsFor(type, id, classic = classicTheme())", rows)
        self.assertIn("project.column_orders : null, type, id, classic)", rows)
        self.assertEqual(len(re.findall(r"columnsFor\(", edit)), 1)      # the one call (the import line has no bracket), which takes the default: Classic only
        self.assertIn("columnsFor(type, true)", edit)
        self.assertEqual(len(re.findall(r"dashboardOrder\(", rows)), 1)
        self.assertNotIn("dashboardOrder(", edit)
        self.assertIn("shownOrder(classicTheme(), STD, ", work)      # the published order of the Work items table
        self.assertNotRegex(work, r"\b(inOrder|savedOrder)\(")
        # Cards keeps the Status always shown, even for the Work items table with an order
        self.assertIn('drawn = table === "work" && !classic &&', menu)

    def test_the_word_copy_keeps_the_standard_order(self):
        """src/clark/docx_build.py draws fixed tables and never reads column_orders: on purpose, the Word copy has the standard order whatever is saved."""
        import test_docx_build as wd
        saved = json.dumps({"actions": ["status", "item", "prio", "owner", "due", "id"], "risks": ["status", "item", "prio", "owner", "due", "id"],
                            "decisions": ["status", "item", "prio", "owner", "due", "id"]})
        plain = wd.published()
        with_order = wd.with_project(plain, column_orders=saved)
        self.assertEqual(with_order["data"]["project"]["column_orders"], saved)
        heads = {}
        for tag, p in (("plain", plain), ("saved", with_order)):
            heads[tag] = [b["rows"][0] for b in wd.blocks(wd.docx_build.build(p)) if b["kind"] == "table"]
        self.assertEqual(heads["saved"], heads["plain"])
        for want in (["ID", "Action", "Owner", "Priority", "Due", "Status"],
                     ["Id", "Type", "Title", "Owner", "Priority", "Impact / likelihood", "Review by", "Status"],
                     ["ID", "Decision", "Status", "Made by", "Date"]):
            self.assertIn(want, heads["saved"])


class WorkItemsListSection(unittest.TestCase):
    """The Dashboard's Work items list sections (store type workitems: templates/WorkItemsList.jsx) draw and drag the order saved for their one type, in View, Edit and the published file."""
    SAVED = '{"actions": ["status", "item", "prio", "due", "owner", "id"]}'
    IDS = '["status", "owner", "due", "priority", "id"]'

    def test_a_list_of_one_type_draws_the_saved_order_and_a_mixed_list_does_not(self):
        self.assertEqual(run_node(f"CO.listType(['risk', 'issue'])"), "risk")
        self.assertEqual(run_node("CO.listType(['action'])"), "action")
        self.assertIsNone(run_node("CO.listType(['action', 'risk'])"))      # a mixed list keeps the order of this browser (row 1195)
        self.assertIsNone(run_node("CO.listType([])"))
        self.assertEqual(run_node(f"CO.listOrder({self.SAVED}, 'action', {self.IDS})"), ["status", "priority", "due", "owner", "id"])
        self.assertEqual(run_node(f"CO.listOrder(JSON.stringify({self.SAVED}), 'action', {self.IDS})"), ["status", "priority", "due", "owner", "id"])      # the project carries it as text
        self.assertEqual(run_node(f"CO.listOrder({self.SAVED}, 'risk', {self.IDS})"), ["status", "owner", "due", "priority", "id"])      # another type keeps its own (here the standard)
        self.assertEqual(run_node(f"CO.listOrder({self.SAVED}, 'action', ['owner', 'due', 'priority'])"), ["priority", "due", "owner"])      # Status hidden: it has no place

    def test_blocked_or_bad_saved_order_draws_the_standard_order(self):
        for saved in ("null", "'not json'", "undefined", "{}"):
            self.assertEqual(run_node(f"CO.listOrder({saved}, 'action', {self.IDS})"), ["status", "owner", "due", "priority", "id"], saved)

    def test_a_drag_saves_the_list_order_with_the_project(self):
        self.assertEqual(run_node("CO.listSave({}, 'action', ['status', 'priority', 'owner', 'due', 'id'])"), {"actions": ["status", "item", "prio", "owner", "due", "id"]})
        self.assertEqual(run_node("CO.listSave({'risks': ['status', 'item', 'prio']}, 'action', ['status', 'owner', 'due', 'priority', 'id'])"), {"risks": ["status", "item", "prio"]})      # the standard saves nothing; the other type is kept

    def test_published_view_edit_and_cards_source(self):
        view, edit, cw = source("templates", "WorkItemsList.jsx"), source("edit", "templates", "WorkItemsList.jsx"), source("edit", "colWidths.jsx")
        self.assertIn("listOrder(project ? project.column_orders : null, typ, base)", view)      # the file draws from the project's saved order, not a browser key
        self.assertIn("moved && ord ? ord.props(c, moved)", view)      # View has no ord: the saved order draws, only Edit drags
        self.assertIn("classicTheme() ? (typ ?", view)      # Cards: no saved order, its markup is what it was
        self.assertIn("typ={fromFile.value ? listType(rows.map((r) => r.kind)) : listType((filterOf(section) || {}).kinds)}", view)      # View: the filter's one type; a published file carries no filter, so the type of its rows
        self.assertIn("const typ = classicTheme() ? listType(", edit)
        self.assertIn("changes: { column_orders: next }", edit)      # saved with the project, no browser key
        self.assertIn("setSaid(MOVED(WORDS.columns[id] || id, lead + o.indexOf(id) + 1, lead + o.length))", edit)      # announced, counting every drawn column (the Item, and the Type when shown, lead)
        self.assertIn('{typ ? <p class="sr" role="status" aria-live="polite" data-wil-live="">{said}</p> : null}', edit)      # said in the list's own live line (Classic, one type); Cards draws none
        self.assertNotIn("data-wil-live", view)      # View and the published file carry no live line
        self.assertNotIn("announce.value", edit)      # the Work items page's live line is not on the Dashboard
        self.assertIn("if (shared) shared.write(o, a); else { setSaved(o); remember(key, o); }", cw)
        keys = cw.split("const keys = (id, ids) => (e) => {")[1].split("};")[0]
        self.assertIn("if (!e.altKey || e.ctrlKey || e.metaKey || (e.key !== \"ArrowLeft\" && e.key !== \"ArrowRight\")) return;", keys)      # a list of one type: Alt+Shift and Alt with an arrow both move; Ctrl is the resize
        self.assertNotIn("shiftKey", keys)
        self.assertNotIn("shared", cw.split("onDragEnd: () =>")[1].split("const cls")[0])      # a mixed list keeps its row 1195 key handler as it was (Alt and an arrow, no Shift)

    def test_a_dragged_heading_keeps_its_width_at_any_width(self):
        view = source("templates", "WorkItemsList.jsx")
        self.assertIn("style={cw ? cw.style(c) : undefined}", view)      # the width is keyed by the column id, so it follows the heading wherever it is dropped


if __name__ == "__main__":
    unittest.main()
