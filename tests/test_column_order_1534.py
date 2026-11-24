"""Row 1534: the column order of the work item tables (Actions, Risks and issues, Decisions) is saved with the project (projects.column_orders, one schema
step, COLUMN_ORDERS_STEP) and is the order the published file draws; a heading is dragged, or moved with Alt+Shift and an arrow, or from the Columns menu.

Run: python3 dev/run_tests.py test_column_order_1534
Pins: one saved order for each work item table, the same for the Work items page and that table's Dashboard section; a different project or table keeps its own;
the order is written by the one writer with Undo and a history line, is read back from the file (so it survives a reload), and is refused when it is not a list of this
table's columns starting with status then item. The order has no browser key. The pure logic (move, order, words) runs in node on the bundled page source; the
Chrome flows (a real drag, the key, the menu, 1400 and 900 px, light and dark, touch) are NOT run by this file. Fictional data only.
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _demo import USER, DemoStore
from _paths import ROOT, SRC, TOOLS
from clark import changes, history, publish, store as store_module

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402

ORDER = ["status", "item", "due", "owner", "prio", "id"]
PAGE_SRC = SRC / "clark" / "page" / "src"
JS = PAGE_SRC / "logic" / "tableColumns.js"
ENTRY = ROOT / "tests" / "fixtures" / "colorder_node.js"
_BUNDLE = {}


def bundle():
    if "code" not in _BUNDLE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "co.js"
            done = esbuild.run(["--bundle", "--format=iife", "--global-name=CO", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(ENTRY), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            _BUNDLE["code"] = out.read_text(encoding="utf-8")
    return _BUNDLE["code"]


def run_node(probe, before=""):
    """Run `probe` (a JS expression) with the bundled logic as CO; `before` runs first (a blocked store, for one). The result comes back as JSON."""
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "probe.js"
        script.write_text(before + "\n" + bundle() + ";\nconsole.log(JSON.stringify(" + probe + "));", encoding="utf-8")
        done = subprocess.run([node, str(script)], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout)


def source(*parts):
    return PAGE_SRC.joinpath(*parts).read_text(encoding="utf-8")


class Saved(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.change = changes.make_change(self.s.path, [], USER)
        self.undo = changes.make_undo(self.s.path, [], USER)

    def save(self, value, project="ABC"):
        return self.change({"project": project, "kind": "projects", "op": "update", "changes": {"column_orders": value}})

    def stored(self, project="ABC"):
        return self.s.con.execute("SELECT column_orders FROM projects WHERE code = ?", (project,)).fetchone()[0]

    def test_column_order_is_published(self):
        self.assertEqual(self.stored(), "{}")
        status, body = self.save({"risks": ORDER, "actions": ORDER[:2] + ["owner"]})
        self.assertEqual((status, body.get("message")), (200, None), body)
        want = json.dumps({"actions": ["status", "item", "owner"], "risks": ORDER}, sort_keys=True, separators=(",", ":"))
        self.assertEqual(self.stored(), want)                       # in the file, not the browser: a reload reads this
        self.assertEqual(body["project"]["column_orders"], want)
        self.assertEqual(self.s.read("projects", ref="ABC")["column_orders"], want)
        self.assertNotIn("order", " ".join(re.findall(r'keyOf = [^\n]*', JS.read_text(encoding="utf-8"))), "no browser key for the order")
        # the published file carries it, and its page draws it
        self.assertIn("column_orders", publish.PUBLISH_FIELDS["projects"])
        self.assertEqual(publish.build(self.s, "ABC")["published"]["data"]["project"]["column_orders"], want)
        body_js = source("components", "WorkItems.jsx")
        self.assertIn("cols = cm ? cm.shown : publishedOrder(type)", body_js)
        self.assertIn("project.column_orders", body_js)

    def test_a_different_project_keeps_its_own_order(self):
        self.s.con.execute("INSERT INTO projects (code, name) VALUES ('XYZ', 'Second Programme')")
        self.assertEqual(self.save({"issues": ORDER})[0], 200)
        self.assertEqual(self.stored("XYZ"), "{}")
        self.assertEqual(self.stored(), json.dumps({"issues": ORDER}, separators=(",", ":")))

    def test_one_undo_puts_the_old_order_back_and_history_says_so(self):
        self.save({"risks": ORDER})
        status, body = self.save({"risks": ["status", "item", "id"]})
        status, back = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        self.assertEqual(status, 200, back)
        self.assertEqual(back["words"], "Put back: the column order.")
        self.assertEqual(json.loads(self.stored()), {"risks": ORDER})
        self.assertEqual(history.FIELD_NAMES["projects"]["column_orders"], "Column order")

    def test_the_standard_order_is_saved_as_nothing(self):
        self.save({"risks": ORDER})
        self.assertEqual(self.save({})[0], 200)
        self.assertEqual(self.stored(), "{}")

    def test_a_bad_order_is_refused_and_nothing_is_written(self):
        bad = [{"milestones": ORDER}, {"use_cases": ORDER}, {"risks": ["item", "status"]}, {"risks": ["owner", "status", "item"]},
               {"risks": ["status", "item", "item"]}, {"risks": ["status", "item", "nope"]}, {"risks": "status,item"}, {"risks": ["status", "item", 3]},
               {"risks": []}, ["status", "item"], "[1]", "not json", None, 5, True, {"risks": ORDER + ORDER}, {"risks": None}]
        for value in bad:
            with self.subTest(value=value):
                before = self.s.con.execute("SELECT count(*) FROM applies").fetchone()[0]
                status, body = self.save(value)
                self.assertEqual((status, body["ok"]), (400, False))
                self.assertEqual(body["message"], store_module.COLUMN_ORDERS_BAD)
                self.assertEqual(self.stored(), "{}")
                self.assertEqual(self.s.con.execute("SELECT count(*) FROM applies").fetchone()[0], before)

    def test_the_text_is_the_same_whatever_the_spelling(self):
        a = store_module.column_orders({"risks": ORDER, "actions": ORDER})
        self.assertEqual(a, store_module.column_orders(json.dumps({"actions": ORDER, "risks": ORDER}, indent=2)))
        self.assertEqual(store_module.column_orders(a), a)

    def test_the_ids_are_the_ids_of_the_pages_work_table(self):
        text = JS.read_text(encoding="utf-8")
        work = text[text.index("work: ["):text.index("uc: [")]
        self.assertEqual(tuple(re.findall(r'id: "([a-z]+)"', work)), store_module.WORK_COLUMN_IDS)


class Logic(unittest.TestCase):
    """The pure logic, bundled from the page source and run in node. The Chrome flows are not run here."""

    def test_column_drag_moves_header_and_rows(self):
        ids = json.dumps(["status", "item", "owner", "due", "prio", "id"])
        self.assertEqual(run_node(f"CO.moveColumn({ids}, 'due', null, 'owner')"), ["status", "item", "due", "owner", "prio", "id"])      # Due dropped in front of Owner
        self.assertEqual(run_node(f"CO.moveColumn({ids}, 'owner', null, 'prio')"), ["status", "item", "due", "owner", "prio", "id"])     # Owner dropped to the right of Due
        self.assertEqual(run_node(f"CO.moveColumn({ids}, 'owner', null, null)"), ["status", "item", "due", "prio", "id", "owner"])
        self.assertIsNone(run_node(f"CO.moveColumn({ids}, 'owner', null, 'due')"), "dropped where it already is: nothing changes")
        self.assertEqual(run_node(f"CO.inOrder({ids}, ['status', 'item', 'due', 'owner', 'prio', 'id'])"), ["status", "item", "due", "owner", "prio", "id"])
        src = source("components", "WorkItems.jsx")
        self.assertEqual(src.count("{rest(cols).map((id) =>"), 2, "the row and its fading copy take their cells from the columns' order")
        self.assertIn("{cols.map((id) => <th key={id}", src)                                              # the heading takes them from the same list
        self.assertIn("cm.headProps(id)", src)
        menu = source("edit", "ColumnsMenu.jsx")
        self.assertIn("onPointerDown", menu)
        self.assertIn('k.key === "Escape"', menu)                                                         # Esc cancels a drag; a drop outside the heading row has no target, so nothing moves
        self.assertIn("Math.hypot(m.clientX - x0, m.clientY - y0) < 5", menu)                            # a click or short press is not a drag, so it does what it did

    def test_column_keyboard_move_announced(self):
        ids = json.dumps(["status", "item", "due", "owner", "prio", "id"])
        self.assertEqual(run_node(f"CO.moveColumn({ids}, 'owner', -1)"), ["status", "item", "owner", "due", "prio", "id"])
        self.assertEqual(run_node(f"CO.moveColumn({ids}, 'owner', 1)"), ["status", "item", "due", "prio", "owner", "id"])
        self.assertIsNone(run_node(f"CO.moveColumn({ids}, 'id', 1)"), "the last column does not move right")
        self.assertEqual(run_node("CO.Words.MOVED('Owner', 2, 6)"), "Owner moved to position 2 of 6")
        self.assertEqual(run_node("[CO.Words.MOVE_LEFT, CO.Words.MOVE_RIGHT, CO.Words.RESET_ORDER]"), ["Move left", "Move right", "Reset to the standard order"])
        menu = source("edit", "ColumnsMenu.jsx")
        self.assertIn("e.altKey && e.shiftKey", menu)                                                     # Alt+Shift+Left and Alt+Shift+Right move
        self.assertIn("W.MOVED(labelOfId(id), to.indexOf(id) + 1, to.length)", menu)                      # the announcement names the column and its new place
        self.assertEqual(menu.count("step(fromId,"), 2, "the menu's Move left and Move right use the key's own step")
        widths = source("edit", "colWidths.jsx")
        self.assertIn("e.shiftKey", widths.split("const onKey")[1].split("addEventListener")[0], "Alt+Left and Alt+Right still resize: Shift is left to moving")

    def test_item_locked_status_first_when_shown(self):
        self.assertEqual(run_node("CO.TABLE_COLUMNS.work.filter((c) => c.locked).map((c) => c.id)"), ["item"], "only the Item is locked on Work items; the Status is not")
        shown = json.dumps(["owner", "due", "item", "status", "prio"])
        self.assertEqual(run_node(f"CO.inOrder({shown}, ['prio', 'owner', 'due'])"), ["status", "item", "prio", "owner", "due"])
        self.assertEqual(run_node("CO.inOrder(['item', 'owner', 'due'], ['owner'])"), ["item", "owner", "due"], "the Status hidden: the Item leads")
        self.assertIn("item", run_node("CO.shownIds('work', ['owner'])"), "the Item cannot be hidden")
        for fixed in ("status", "item"):
            self.assertIsNone(run_node(f"CO.moveColumn(['status', 'item', 'owner', 'due'], '{fixed}', 1)"))
        self.assertIsNone(run_node("CO.moveColumn(['status', 'item', 'owner'], 'owner', -5)"), "nothing moves in front of the Status and the Item")
        self.assertEqual(run_node("CO.moveColumn(['status', 'item', 'owner', 'due'], 'due', null, 'item')"), ["status", "item", "due", "owner"])
        self.assertEqual(run_node("CO.inOrder(['status', 'item', 'owner'], ['owner', 'nope', 'item', 'status'])"), ["status", "item", "owner"], "a hidden or unknown id has no place")
        self.assertEqual(run_node("CO.withOrder('{}', 'risk', ['item', 'due', 'owner']).risks"), ["status", "item", "due", "owner"],
                         "what is saved always starts with status then item, as the project's check asks")

    def test_columns_menu_order_matches_table(self):
        menu = source("edit", "ColumnsMenu.jsx")
        self.assertIn("const ordered = shownOrder(ordering, drawn, co, type);", menu)
        self.assertIn("return { shown: ordered,", menu)                                                    # the table draws `ordered` ...
        self.assertIn("ordered.map((id) => defsOf(table).find", menu)                                      # ... and the menu lists the same list, the hidden columns after
        self.assertEqual(menu.count("{listed."), 2, "both menus (Classic and Cards) list the columns in the table's order")
        self.assertIn("W.RESET_ORDER", menu)
        # "Reset to the standard order": the standard list is saved as nothing, so the type's key goes and the table follows the standard again
        std = json.dumps(["status", "item", "owner", "due", "prio", "id"])
        self.assertEqual(run_node(f"CO.withOrder({{risks: ['status', 'item', 'due', 'owner']}}, 'risk', {std})"), {})
        self.assertEqual(run_node(f"CO.withOrder({{risks: ['status', 'item', 'due', 'owner'], actions: ['status', 'item', 'id']}}, 'risk', {std})"), {"actions": ["status", "item", "id"]})
        self.assertEqual(run_node("CO.withOrder('{}', 'action', ['status', 'item', 'due', 'owner', 'prio', 'id'])"), {"actions": ["status", "item", "due", "owner", "prio", "id"]})
        self.assertEqual(run_node("CO.savedOrder('{\"risks\":[\"status\",\"item\",\"id\"]}', 'risk')"), ["status", "item", "id"])
        self.assertEqual(run_node("CO.savedOrder('{\"risks\":[\"status\",\"item\",\"id\"]}', 'all')"), [], "All keeps the standard order and is not movable")
        self.assertEqual(run_node("[CO.movable('all'), CO.movable('action'), CO.movable('risk'), CO.movable('decision')]"), [False, True, True, True])

    def test_column_order_blocked_store(self):
        blocked = "globalThis.window = { get localStorage() { throw new Error('blocked'); } };"
        self.assertEqual(run_node("CO.readChoice('work', 'ABC')", blocked), ["status", "item", "owner", "due", "prio", "id"])
        for bad in ("'not json'", "null", "undefined", "'[1,2]'", "5", "'{\"risks\":\"x\"}'"):
            with self.subTest(saved=bad):
                self.assertEqual(run_node(f"CO.inOrder(['status', 'item', 'owner', 'due'], CO.savedOrder({bad}, 'risk'))", blocked), ["status", "item", "owner", "due"])
        self.assertEqual(run_node("CO.withOrder('not json', 'risk', ['status', 'item', 'due', 'owner'])", blocked), {"risks": ["status", "item", "due", "owner"]})


    def test_column_click_still_sorts(self):
        """A click or short press on a heading is not a drag: the heading's own handlers stay, and only a press that travels 5 px or more moves a column. The real click is a Chrome flow and is NOT run here."""
        menu = source("edit", "ColumnsMenu.jsx")
        head = menu[menu.index("const headProps = (id) =>"):menu.index("onPointerDown: (e) =>")]
        self.assertNotIn("onClick", head, "the move props take over no click: the heading keeps the click it had")
        self.assertIn('if (!canMove || id === "status" || id === "item") return {};', head, "the Status and the Item add nothing to their heading")
        drag = menu[menu.index("onPointerDown: (e) =>"):menu.index("const up = () => done(true)")]
        self.assertNotIn("onClick", drag)
        self.assertIn("Math.hypot(m.clientX - x0, m.clientY - y0) < 5) return;", drag, "under 5 px nothing is a drag")
        self.assertIn("if (!moving) return;", drag, "a press that never became a drag ends without touching the click")
        after_moving = drag[drag.index("if (!moving) return;"):]
        self.assertLess(after_moving.index('addEventListener("click", quiet'), after_moving.index("moveTo(to, id)"))
        self.assertEqual(drag.count('addEventListener("click", quiet'), 1, "only the click that ends a real drag is swallowed")
        self.assertIn("e.target.closest(\".cgrip, button\")", drag, "a press on the resize grip or a button is left alone")
        # the heading keeps its own props, and the move props come after them without replacing a handler of the same name
        src = source("components", "WorkItems.jsx")
        self.assertIn("{...h(id, labelOf(id))} {...(cm && cm.headProps ? cm.headProps(id) : {})}", src)
        # nothing moves for a click: no target and no step
        self.assertIsNone(run_node("CO.moveColumn(['status', 'item', 'owner', 'due'], 'owner', 0)"))
        self.assertIsNone(run_node("CO.moveColumn(['status', 'item', 'owner', 'due'], 'owner', null, 'owner')"))

    def test_reset_to_standard_order(self):
        """'Reset to the standard order' saves the standard list, which is stored as nothing, so the table follows the standard again; it does nothing when no order is saved."""
        std = json.dumps(["status", "item", "owner", "due", "prio", "id"])
        self.assertEqual(run_node(f"CO.withOrder({{risks: ['status', 'item', 'due', 'owner', 'prio', 'id']}}, 'risk', {std})"), {}, "the standard list leaves no key")
        self.assertEqual(run_node(f"CO.withOrder({{risks: ['status', 'item', 'id'], actions: ['status', 'item', 'due']}}, 'risk', {std})"), {"actions": ["status", "item", "due"]},
                         "another table keeps its own order")
        self.assertEqual(run_node("CO.Words.RESET_ORDER"), "Reset to the standard order")
        menu = source("edit", "ColumnsMenu.jsx")
        self.assertIn("const resetOrder = () => { if (savedOrder(co, type).length) saveOrder(standardOrder(), W.RESET_ORDER); };", menu)
        self.assertIn("const standardOrder = () => defsOf(table).map((c) => c.id).filter((id) => ordered.includes(id));", menu, "the standard is the table's own list of columns")
        self.assertIn('data-order-reset="" tabIndex={-1} aria-disabled={savedOrder(co, type).length ? undefined : "true"} onClick={resetOrder}', menu)
        # and in the file: a saved order, then the standard one, is stored as nothing
        demo = DemoStore()
        self.addCleanup(demo.close)
        change = changes.make_change(demo.store.path, [], USER)
        put = lambda v: change({"project": "ABC", "kind": "projects", "op": "update", "changes": {"column_orders": v}})
        self.assertEqual(put({"risks": ORDER})[0], 200)
        self.assertEqual(put({})[0], 200)
        self.assertEqual(demo.store.con.execute("SELECT column_orders FROM projects WHERE code = 'ABC'").fetchone()[0], "{}")

    def test_column_move_saves_without_a_toast(self):
        """The ruling for the row: no 'Column moved. Undo' toast; the change is silent and the step is kept for the undo key."""
        menu = source("edit", "ColumnsMenu.jsx")
        save = menu[menu.index("const saveOrder = async"):menu.index("const moveTo = ")]
        self.assertIn('changes: { column_orders: next }, place: "menu" }, "", { silent: true });', save)
        self.assertEqual(menu.count("column_orders: next"), 1, "the order has one writer in the menu, and it is the silent one")
        changes_js = source("stores", "changes.js")
        self.assertIn("named && named.silent", changes_js, "change() still honours {silent: true}")
        code = "\n".join(l for l in (menu + source("logic", "columnsWords.js")).splitlines() if not l.lstrip().startswith("//"))
        self.assertNotIn("Column moved", re.sub(r"//[^\n]*", "", code), "no string of the dropped toast (a comment may name it)")


if __name__ == "__main__":
    unittest.main()
