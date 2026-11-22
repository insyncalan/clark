"""Row 702: the five core Work items tabs keep the names the code spells, and a core tab can still be renamed, deleted and given another
filter line from its own menu. Tests only: nothing in the page changes.

Run: python3 dev/run_tests.py test_core_view_names_702
The page tests drive the committed page in headless Chrome at 1400 and 900 px (the 900 cases are skipped with the stated reason while
test_server.PAUSED_900 is set, as in test_filter_line_page). The words test reads the source files.
"""
import json
import re
import unittest

from _paths import SRC
import test_filter_line_page as base
from test_filter_line_page import click, click_tab, key, shared, wait  # noqa: F401
from test_server import chrome  # noqa: E402,F401  (chrome: the runner tells a browser file by this import)

PAGE_SRC = SRC / "clark" / "page" / "src"
FIVE = ["Open items", "Actions", "Risks and issues", "Decisions", "All work items"]
CORE_IDS = ["core-open", "core-actions", "core-risks", "core-decisions", "core-all"]
WIDTHS = (1400, 900)
TABS = "[...document.querySelectorAll('.vtab span')].map(e => e.textContent)"


def source(*parts):
    return PAGE_SRC.joinpath(*parts).read_text(encoding="utf-8")


def core_views_in_source():
    """(id, name) of each entry of CORE_VIEWS in filterLine.js, in order."""
    text = source("logic", "filterLine.js")
    block = text[text.index("export const CORE_VIEWS = ["):]
    block = block[:block.index("];")]
    return re.findall(r'\{ id: "([^"]+)", name: "([^"]+)"', block)


class Core(base.Line):
    """Borrows the page set-up (server, shared Chrome, load, put) of test_filter_line_page.Line; none of its own tests run here."""

    def menu_items(self, cdp, sid):
        base.wait_tabs_still(cdp, sid)
        click(cdp, sid, "#viewTabMenu")
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#viewTabMenuList')", sid)), "the tab menu opened")
        return cdp.js("[...document.querySelectorAll('#viewTabMenuList [role=menuitem]')].map(b => b.textContent)", sid)

    def close_menu(self, cdp, sid):
        key(cdp, sid, "Escape")
        self.assertTrue(wait(lambda: not cdp.js("!!document.querySelector('#viewTabMenuList')", sid)), "the tab menu closed")

    def pick(self, cdp, sid, kind):
        click(cdp, sid, f"#viewTabMenuList [data-kind={kind}]")

    def rename_to(self, cdp, sid, name, enter=True):
        self.assertTrue(wait(lambda: cdp.js("document.activeElement.id", sid) == "vname"), "the name box has the focus")
        cdp.js("document.querySelector('#vname').select()", sid)
        self.type(cdp, sid, name)
        if enter:
            key(cdp, sid, "Enter")

    def test_core_tabs_keep_the_five_code_spelled_names(self):
        spelled = core_views_in_source()
        self.assertEqual([n for _, n in spelled], FIVE, "CORE_VIEWS in filterLine.js spells the five names")
        self.assertEqual([i for i, _ in spelled], CORE_IDS)
        s = self.serve()
        for width in WIDTHS:
            with self.subTest(width=width), shared.page() as cdp:
                sid = self.load(cdp, s.port, width)
                self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('.vtab').length", sid) >= 5), "the tabs drew")
                self.assertEqual(cdp.js(TABS, sid)[:5], FIVE, "the first five tabs read as the code spells them")
                self.assertEqual(cdp.js("[...document.querySelectorAll('.vtab')].map(e => e.dataset.viewId).slice(0, 5)", sid), CORE_IDS)
                self.assertEqual(cdp.js("document.querySelector('.vtab[aria-pressed=true] span').textContent", sid), "Open items")
                cdp.js("localStorage.clear(); sessionStorage.clear()", sid)

    def test_core_tab_menu_offers_rename_delete_and_filter_edit_at_both_widths(self):
        rules = source("logic", "filterLine.js")
        self.assertIn("export const MAX_NAME = 40;", rules)
        self.assertIn("`Keep the name to ${MAX_NAME} characters or fewer.`", rules)
        self.assertIn("`A view called ${n} already exists. Choose another name.`", rules)
        s = self.serve()
        too_long = "x" * 41
        just_fits = "y" * 40
        for width in WIDTHS:
            for n, cid in enumerate(CORE_IDS):
                with self.subTest(width=width, tab=cid), shared.page() as cdp:
                    sid = self.load(cdp, s.port, width)
                    self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('.vtab').length", sid) >= 5), "the tabs drew")
                    click_tab(cdp, sid, f".vtab[data-view-id={cid}]")
                    self.assertTrue(wait(lambda: cdp.js("document.querySelector('.vtab[aria-pressed=true]').dataset.viewId", sid) == cid))
                    items = self.menu_items(cdp, sid)
                    self.assertIn("Rename view", items)
                    self.assertIn("Delete view", items)
                    self.close_menu(cdp, sid)
                    # change the filter line: the dot shows, and the menu now offers Update view
                    self.put(cdp, sid, "priority:High")
                    self.assertTrue(wait(lambda: cdp.js(f"document.querySelectorAll('.vtab[data-view-id={cid}] [data-dot]').length", sid) == 1), "a dot on the tab")
                    items = self.menu_items(cdp, sid)
                    self.assertEqual(items[0], "Update view")
                    self.assertIn("Rename view", items)
                    self.assertIn("Delete view", items)
                    self.pick(cdp, sid, "save")
                    self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('[data-dot]').length", sid) == 0), "updated: the dot goes")
                    other = "Actions" if cid != "core-actions" else "Decisions"
                    other_id = CORE_IDS[FIVE.index(other)]
                    click_tab(cdp, sid, f".vtab[data-view-id={other_id}]")
                    click_tab(cdp, sid, f".vtab[data-view-id={cid}]")
                    self.assertTrue(wait(lambda: "priority:High" in self.chips(cdp, sid)), "the tab keeps the changed line")
                    # rename: the box stops at 40 characters, a name in use is refused, 40 characters is kept
                    self.menu_items(cdp, sid)
                    self.pick(cdp, sid, "rename")
                    self.assertEqual(cdp.js("document.querySelector('#vname').maxLength", sid), 40, "the name box holds 40 characters")
                    self.rename_to(cdp, sid, too_long, enter=False)
                    self.assertEqual(cdp.js("document.querySelector('#vname').value", sid), too_long[:40], "a 41st character is not taken")
                    cdp.js("document.querySelector('#vname').select()", sid)
                    self.rename_to(cdp, sid, other)
                    self.assertTrue(wait(lambda: cdp.js("document.querySelector('.vmsg').textContent", sid) == f"A view called {other} already exists. Choose another name."), "the already-exists message")
                    self.rename_to(cdp, sid, just_fits)
                    self.assertTrue(wait(lambda: just_fits in cdp.js(TABS, sid)), "40 characters is kept as the tab name")
                    self.assertEqual(cdp.js(TABS, sid).index(just_fits), n, "in the same place")
                    # delete
                    self.menu_items(cdp, sid)
                    self.pick(cdp, sid, "delete")
                    self.assertTrue(wait(lambda: just_fits not in cdp.js(TABS, sid)), "the core tab is deleted")
                    self.assertEqual(len([t for t in cdp.js(TABS, sid) if t in FIVE]), 4, "the other four core tabs stay")
                    cdp.js("localStorage.clear(); sessionStorage.clear()", sid)

    def test_help_and_list_template_use_the_same_names(self):
        core = [n for _, n in core_views_in_source()]
        self.assertEqual(core, FIVE)
        # Help: the entry that lists the tabs every project starts with
        help_json = json.loads(source("help", "helpContent.json"))
        found = []

        def walk(node):
            if isinstance(node, dict):
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)
            elif isinstance(node, str) and "Every project starts with the tabs" in node:
                found.append(node)
        walk(help_json)
        self.assertEqual(len(found), 1, "one Help entry lists the starting tabs")
        listed = re.search(r"Every project starts with the tabs (.*?)(?:, then|\.)", found[0]).group(1)
        self.assertEqual(listed, "Open items, Actions, Risks and issues, Decisions and All work items")
        self.assertEqual(re.split(r", | and (?=All work)", listed), core, "Help names the five names of CORE_VIEWS, in order")
        # the Work items list template: its saved views, and the same views kept by filterLine.js for it
        template = source("templates", "workItemsList.js")
        block = template[template.index("export const VIEWS = ["):]
        tpl_names = re.findall(r'name: "([^"]+)"', block[:block.index("];")])
        pv = source("logic", "filterLine.js")
        pv = pv[pv.index("workitemslist: ["):]
        pv_names = re.findall(r'name: "([^"]+)"', pv[:pv.index("],")])
        self.assertEqual(tpl_names, pv_names, "the template and PAGE_VIEWS workitemslist agree")
        # The template has no Open items tab (it lists items of every state); every other core name is spelled the same (the template lists All work items first, as its mock-up does).
        self.assertEqual(sorted(n for n in tpl_names if n in core), sorted(n for n in core if n != "Open items"))
        self.assertEqual([n for n in tpl_names if n not in core], ["Overdue"])
        self.assertNotIn("Open items", tpl_names)


for _name in dir(base.Line):
    if _name.startswith("test_"):
        setattr(Core, _name, None)             # the borrowed tests run in test_filter_line_page, not here

if __name__ == "__main__":
    unittest.main()
