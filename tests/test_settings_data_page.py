"""#444 (rows 44): Settings › Data in a real browser against the real routes: Import workbook (the two-step box, one step, Undo this import).
Run: python3 dev/run_tests.py test_settings_data_page

The server is the real one over the #39 plant in a temporary folder (tests/test_publish_route.py Rig) with the real workbook import. Widths 1400 and 900, light and dark. Chrome is required:
these tests fail, never skip, without it. The non-browser checks (the published page names none of these routes) need no browser.
"""
import base64
import json
import tempfile
import unittest
from pathlib import Path

from _paths import SRC
from test_publish_dialog import Base
from _new_page import reload_to_new_page
from test_server import chrome, wait

from clark import excel, excel_route

WIDTHS = (1400, 900)
USER = "Test Person"


def workbook(rig, tmp, new_text):
    """A workbook exported as the page's Export does it, with the first action's description changed; (base64, the action's id, its old text)."""
    from openpyxl import load_workbook
    path = Path(tmp) / "PUB work items.xlsx"
    made = excel.export_project(rig.store, "PUB", path, Path(tmp) / "state.json", on="2030-06-01")
    record = excel.load_state(Path(tmp) / "state.json", made)
    excel.save_state(rig.data_dir / excel.STATE_FILE, excel.id_key("PUB", record["export_id"]), record)
    action = rig.store.read("actions", "PUB")[0]
    wb = load_workbook(str(path))
    ws = wb["Actions"]
    head = {c.value: c.column for c in ws[1]}
    row = next(r for r in range(2, ws.max_row + 1) if ws.cell(r, head["ID"]).value == action["id"])
    ws.cell(row, head["Description"]).value = new_text
    wb.save(str(path))
    return base64.b64encode(path.read_bytes()).decode(), action["id"], action["description"]


class Source(unittest.TestCase):
    def test_the_published_page_names_none_of_these_routes_or_boxes(self):
        view = (SRC / "clark" / "page" / "page-view.html").read_text(encoding="utf-8")
        for needle in ("/api/excel-import", "Import workbook", "import-box"):
            self.assertNotIn(needle, view, needle)

    def test_only_the_data_files_name_the_two_routes(self):
        found = {}
        for f in (SRC / "clark" / "page" / "src").rglob("*"):
            if f.is_file() and f.suffix in (".js", ".jsx"):
                text = f.read_text(encoding="utf-8")
                for route in ('"/api/excel-import"', '"/api/project"'):
                    if route in text:
                        found.setdefault(route, []).append(f.name)
        self.assertEqual(found, {'"/api/excel-import"': ["dataApi.js"], '"/api/project"': ["dataApi.js"]})


class Card(Base):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.rig.httpd.excel_import = excel_route.make_excel_import(self.rig.db, [], USER)

    def settle(self, p, expr, what, seconds=20):
        def got():
            try:
                return bool(p.js(expr))
            except Exception:                    # the page is reloading
                return False
        self.assertTrue(wait(got, seconds), what)

    def open_settings(self, p):
        p.js("document.querySelector('#profile-btn').click()")
        p.until("!!document.querySelector('#profile-menu')", "the menu opened")
        p.js("document.querySelector('#profile-menu [data-kind=settings], #profile-menu [data-kind=who]').click()")
        p.until("!!document.querySelector('#data-card')", "the Data card drew")

    def choose(self, p, b64, through=True):
        """Choose the file; with `through` also press Continue on the sheet list (#655) when the file got that far."""
        self.pick_file(p, b64)
        if through:
            p.until("!!document.querySelector('#import-continue') || !!document.querySelector('#import-problem').textContent", "the sheet list or a refusal")
            if p.js("!!document.querySelector('#import-continue')"):
                p.js("document.querySelector('#import-continue').click()")

    def pick_file(self, p, b64):
        p.js("""(() => { const bin = atob(%s), a = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) a[i] = bin.charCodeAt(i);
          const dt = new DataTransfer(); dt.items.add(new File([a], 'PUB work items.xlsx')); const inp = document.querySelector('#import-file');
          inp.files = dt.files; inp.dispatchEvent(new Event('change', {bubbles: true})); })()""" % json.dumps(b64))

    def test_the_card_has_export_and_import_and_nothing_else(self):
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                p.width(w)
                self.open_settings(p)
                self.settle(p, "!!document.querySelector('#import-workbook')", "the Import workbook button")
                self.assertEqual(p.js("[...document.querySelectorAll('#data-card .row button')].map(b => b.textContent)"),
                                 ["Export workbook", "Import workbook", "Excel file layout", "Export to Word…", "Import from Word…"])
                self.assertLessEqual(p.js("document.documentElement.scrollWidth"), w)

    def test_import_checks_then_imports_in_one_step_and_undo_puts_it_back(self):
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                # a fresh workbook for each width: the first width's import and Undo touched the row, so the old workbook would be a clash
                folder = Path(self.tmp.name) / str(w)
                folder.mkdir()
                b64, action, old = workbook(self.rig, folder, "Agree the cut-over plan, version two")
                p = self.page(cdp)
                p.width(w)
                self.open_settings(p)
                p.js("document.querySelector('#import-workbook').click()")
                p.until("!!document.querySelector('#import-box')", "the box opened")
                self.assertEqual(p.js("document.querySelector('#import-box-t').textContent"), "Import from Excel")
                self.settle(p, "document.activeElement && document.activeElement.id === 'import-choose'", "focus on Choose a file")
                self.assertEqual(p.js("document.querySelector('#import-columns') && document.querySelector('#import-columns').textContent.length > 0"), True)
                self.choose(p, b64)
                p.until("!!document.querySelector('#import-summary')", "the check")
                self.assertEqual(p.js("document.querySelector('#import-box-t').textContent"), "Check the import")
                self.assertIn("1 updated", p.js("document.querySelector('#import-summary').textContent"))
                self.assertIn(action, p.js("document.querySelector('.imp-list li').innerText"))
                self.assertEqual(p.js("[...document.querySelectorAll('.imp-list li:first-child input')].map(i => i.type + ':' + i.checked)"), ["radio:true", "radio:false"], "Accept is chosen, Reject is not")
                self.assertEqual(p.js("[...document.querySelectorAll('.st-bar button')].map(b => b.textContent)"), ["Accept all", "Reject all"])
                self.assertEqual(self.rig.store.read("actions", ref=action)["description"], old, "a check writes nothing")
                self.assertLessEqual(p.js("document.documentElement.scrollWidth"), w)
                steps = self.rig.store.con.execute("SELECT count(*) FROM applies").fetchone()[0]
                p.js("document.querySelector('#import-go').click()")
                p.until("!!document.querySelector('#import-result')", "the result")
                self.assertIn("1 changed", p.js("document.querySelector('#import-result').textContent"))
                self.assertEqual(self.rig.store.read("actions", ref=action)["description"], "Agree the cut-over plan, version two")
                self.assertEqual(self.rig.store.con.execute("SELECT count(*) FROM applies").fetchone()[0], steps + 1, "ONE step")
                p.js("document.querySelector('#import-undo').focus(); document.querySelector('#import-undo').click()")
                p.until("document.querySelector('#import-result') && document.querySelector('#import-result').textContent.startsWith('Put back')", "Undo")
                self.assertEqual(self.rig.store.read("actions", ref=action)["description"], old)
                self.assertEqual(p.js("document.activeElement && document.activeElement.id"), "import-close", "Undo took its button away: the focus is on Close, so Esc and Tab still work")
                p.js("document.querySelector('#import-close').click()")
                p.until("!document.querySelector('#import-box')", "the box closed")

    def test_a_double_click_on_import_and_on_undo_applies_once_and_shows_no_error(self):
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                folder = Path(self.tmp.name) / ("dbl" + str(w))
                folder.mkdir()
                b64, action, old = workbook(self.rig, folder, "Agree the cut-over plan, version three")
                p = self.page(cdp)
                p.width(w)
                self.open_settings(p)
                p.js("document.querySelector('#import-workbook').click()")
                p.until("!!document.querySelector('#import-box')", "the box opened")
                self.choose(p, b64)
                p.until("!!document.querySelector('#import-go')", "the check")
                steps = self.rig.store.con.execute("SELECT count(*) FROM applies").fetchone()[0]
                p.js("(() => { const b = document.querySelector('#import-go'); b.click(); b.click(); })()")
                p.until("!!document.querySelector('#import-result')", "the result")
                self.settle(p, "!!document.querySelector('#import-undo')", "Undo offered")
                self.assertEqual(p.js("document.querySelector('#import-problem').textContent"), "", "no error after a double click")
                self.assertEqual(self.rig.store.con.execute("SELECT count(*) FROM applies").fetchone()[0], steps + 1, "ONE step")
                p.js("(() => { const b = document.querySelector('#import-undo'); b.click(); b.click(); })()")
                p.until("document.querySelector('#import-result') && document.querySelector('#import-result').textContent.startsWith('Put back')", "Undo")
                self.assertEqual(p.js("document.querySelector('#import-problem').textContent"), "", "no error after a double click on Undo")
                self.assertEqual(self.rig.store.read("actions", ref=action)["description"], old)

    def open_box(self, p):
        self.open_settings(p)
        p.js("document.querySelector('#import-workbook').click()")
        p.until("!!document.querySelector('#import-box')", "the box opened")

    def test_after_a_file_is_chosen_the_box_lists_its_sheets_all_ticked_with_their_rows(self):
        """#655: What to import."""
        b64, action, old = workbook(self.rig, self.tmp.name, "Agree the cut-over plan, version two")
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                p.width(w)
                self.open_box(p)
                self.assertIn("You choose which after you pick a file", p.js("document.querySelector('#import-box').innerText"))
                self.pick_file(p, b64)
                p.until("!!document.querySelector('#import-continue')", "the sheet list")
                self.assertEqual(p.js("document.querySelector('#import-box-t').textContent"), "What to import")
                self.assertEqual(p.js("document.querySelector('#import-box p').textContent"),
                                 "Tick the sheets to import. Anything you leave unticked is not read and not changed.")
                rows = p.js("[...document.querySelectorAll('#import-sheet-list li')].map(li => [li.innerText.trim(), li.querySelector('input').checked])")
                self.assertEqual([r[1] for r in rows], [True] * 5, "all ticked to start")
                def word(table, name):
                    n = len([r for r in self.rig.store.read(table, "PUB") if not r.get("archived")])
                    return "%s (%d %s)" % (name, n, "row" if n == 1 else "rows")
                self.assertEqual([r[0] for r in rows], [word("actions", "Actions"), word("raid", "Risks & Issues"), word("decisions", "Decisions"),
                                                        word("milestones", "Milestones"), word("use_cases", "Use cases")])
                self.assertEqual(p.js("[...document.querySelectorAll('.st-bar button')].map(b => b.textContent)"), ["Select all", "Clear"])
                self.assertEqual(p.js("document.querySelector('#import-continue').textContent"), "Continue")
                self.assertFalse(p.js("document.querySelector('#import-continue').disabled"))
                self.assertEqual(p.js("document.querySelector('#import-tick-one').textContent"), "", "the status line is there, empty, while a sheet is ticked")
                self.assertEqual(p.js("(() => { const g = document.querySelector('#import-sheet-list').closest('[role=group]'); return [g.getAttribute('aria-labelledby'), document.getElementById(g.getAttribute('aria-labelledby')).textContent]; })()"), ["import-box-t", "What to import"])
                self.assertEqual(p.js("[document.querySelector('#import-tick-one').getAttribute('role'), document.querySelector('#import-tick-one').getAttribute('aria-live')]"), ["status", "polite"])
                self.assertLessEqual(p.js("document.documentElement.scrollWidth"), w)
                p.js("document.querySelector('#import-clear').click()")
                p.until("document.querySelector('#import-continue').disabled", "Continue off with no tick")
                self.assertEqual(p.js("document.querySelector('#import-tick-one').textContent"), "Tick at least one sheet.")
                self.assertEqual(p.js("document.querySelectorAll('#import-sheet-list input:checked').length"), 0)
                p.js("document.querySelector('#import-select-all').click()")
                p.until("!document.querySelector('#import-continue').disabled", "Select all ticks them again")
                self.assertEqual(p.js("document.querySelectorAll('#import-sheet-list input:checked').length"), 5)
                self.assertEqual(self.rig.store.read("actions", ref=action)["description"], old, "choosing and listing write nothing")

    def test_only_the_ticked_sheets_are_checked_and_an_unticked_one_is_left_alone(self):
        b64, action, old = workbook(self.rig, self.tmp.name, "Agree the cut-over plan, version two")
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_box(p)
            self.pick_file(p, b64)
            p.until("!!document.querySelector('#import-continue')", "the sheet list")
            p.js("document.querySelector('[data-sheet=actions]').click()")              # Actions unticked
            p.js("document.querySelector('#import-continue').click()")
            p.until("!!document.querySelector('#import-none') || !!document.querySelector('#import-summary')", "the check")
            self.assertEqual(p.js("document.querySelector('#import-box-t').textContent"), "Check the import")
            self.assertEqual(p.js("document.querySelectorAll('.imp-list li').length"), 0, "the Actions change is not even listed")
            self.assertEqual(self.rig.store.read("actions", ref=action)["description"], old)
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_box(p)
            self.pick_file(p, b64)
            p.until("!!document.querySelector('#import-continue')", "the sheet list")
            p.js("document.querySelector('#import-clear').click()")
            p.js("document.querySelector('[data-sheet=actions]').click()")              # only Actions ticked
            p.js("document.querySelector('#import-continue').click()")
            p.until("!!document.querySelector('#import-summary')", "the check")
            self.assertIn("1 updated", p.js("document.querySelector('#import-summary').textContent"))
            self.assertEqual(p.js("document.querySelectorAll('.imp-list li').length"), 1)
            p.js("document.querySelector('#import-go').click()")
            p.until("!!document.querySelector('#import-result')", "the result")
            self.assertEqual(self.rig.store.read("actions", ref=action)["description"], "Agree the cut-over plan, version two")

    def test_the_sheets_ticked_are_saved_in_the_browser_and_ticked_again_next_time(self):
        """Row 1106: Continue keeps the ticked sheets in localStorage and the next What to import opens with only those ticked."""
        b64, _, _ = workbook(self.rig, self.tmp.name, "Agree the cut-over plan, version two")
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_box(p)
            self.pick_file(p, b64)
            p.until("!!document.querySelector('#import-continue')", "the sheet list")
            p.js("document.querySelector('#import-clear').click()")
            p.js("document.querySelector('[data-sheet=actions]').click()")              # only Actions ticked
            p.js("document.querySelector('#import-continue').click()")
            p.until("!!document.querySelector('#import-summary')", "the check")
            self.assertEqual(p.js("localStorage.getItem('clark.import.sheets')"), '["actions"]')
            reload_to_new_page(p.js, ready="!!document.querySelector('#profile-btn')", what="the page came back")
            self.open_box(p)
            self.pick_file(p, b64)
            p.until("!!document.querySelector('#import-continue')", "the sheet list again")
            self.assertEqual(p.js("[...document.querySelectorAll('#import-sheet-list input')].filter(i => i.checked).map(i => i.dataset.sheet)"), ["actions"])

    def test_a_sheet_the_file_does_not_have_is_not_shown(self):
        from openpyxl import load_workbook
        b64, _, _ = workbook(self.rig, self.tmp.name, "Agree the cut-over plan, version two")
        path = Path(self.tmp.name) / "PUB work items.xlsx"
        wb = load_workbook(str(path))
        del wb["Decisions"]
        wb.save(str(path))
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_box(p)
            self.pick_file(p, base64.b64encode(path.read_bytes()).decode())
            p.until("!!document.querySelector('#import-continue')", "the sheet list")
            self.assertEqual(p.js("[...document.querySelectorAll('#import-sheet-list li')].map(li => li.innerText.trim().split(' (')[0])"),
                             ["Actions", "Risks & Issues", "Milestones", "Use cases"])

    def test_the_sheets_ticked_last_time_are_ticked_again_when_the_box_is_opened_again(self):
        """#1106, in the browser: Continue keeps exactly the ticked sheets, and the next time the sheet list opens only those are ticked."""
        b64, _, _ = workbook(self.rig, self.tmp.name, "Agree the cut-over plan, version two")
        ticks = "[...document.querySelectorAll('#import-sheet-list li')].map(li => li.querySelector('input').checked)"
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                p.width(w)
                self.open_box(p)
                self.pick_file(p, b64)
                p.until("!!document.querySelector('#import-continue')", "the sheet list")
                self.assertEqual(p.js(ticks), [True] * 5, "nothing remembered: all ticked")
                p.js("document.querySelector('#import-clear').click()")
                p.js("document.querySelector('[data-sheet=raid]').click()")
                p.js("document.querySelector('[data-sheet=milestones]').click()")
                p.js("document.querySelector('#import-continue').click()")
                p.until("!!document.querySelector('#import-none') || !!document.querySelector('#import-summary')", "the check")
                self.assertEqual(p.js("JSON.parse(localStorage.getItem('clark.import.sheets'))"), ["raid", "milestones"], "the ticked tables are kept")
                p.js("document.querySelector('#import-box').dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))")
                p.until("!document.querySelector('#import-box')", "Esc closed it")
                p.js("document.querySelector('#import-workbook').click()")
                p.until("!!document.querySelector('#import-box')", "the box opened again")
                self.pick_file(p, b64)
                p.until("!!document.querySelector('#import-continue')", "the sheet list again")
                self.assertEqual(p.js(ticks), [False, True, False, True, False], "Risks & Issues and Milestones are ticked again, the rest are not")

    def test_the_first_box_lists_each_sheets_columns_as_the_export_writes_them(self):
        from clark import excel_import
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p)
            self.settle(p, "!!document.querySelector('#import-workbook')", "the Import workbook button")
            p.js("document.querySelector('#import-workbook').click()")
            p.until("!!document.querySelector('#import-box')", "the box opened")
            self.settle(p, "!!document.querySelector('#import-columns')", "the column lists")
            self.assertEqual(p.js("document.querySelector('#import-columns').previousElementSibling.textContent"),
                             "Columns, in any order (the ID column and the name or title are needed):")
            shown = p.js("[...document.querySelectorAll('#import-columns > span')].map(s => [s.querySelector('b').textContent, s.textContent.slice(s.querySelector('b').textContent.length).trim().split(', ')])")
        want = {name: [label for label, field in cols if field == "id" or field not in (set(locked) | excel_import.LOCKED)]
                for name, _, cols, locked in excel.SHEETS}
        self.assertEqual({name: cols for name, cols in shown}, want)
        self.assertEqual([name for name, _ in shown], ["Actions", "Risks & Issues", "Decisions", "Milestones", "Use cases"])

    def test_a_file_that_is_not_a_workbook_is_said_in_words_in_the_first_box(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p)
            p.js("document.querySelector('#import-workbook').click()")
            p.until("!!document.querySelector('#import-box')", "the box opened")
            self.choose(p, base64.b64encode(b"not a workbook").decode())
            p.until("!!document.querySelector('#import-problem').textContent", "the refusal")
            self.assertIn("can't be read as an Excel workbook", p.js("document.querySelector('#import-problem').textContent"))
            self.assertTrue(p.js("!!document.querySelector('#import-choose') && !document.querySelector('#import-summary')"))

    def test_tab_and_shift_tab_move_on_from_choose_a_file_and_back_1121(self):
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                p.width(w)
                self.open_settings(p)
                p.js("document.querySelector('#import-workbook').click()")
                p.until("!!document.querySelector('#import-box')", "the box opened")
                self.settle(p, "document.activeElement && document.activeElement.id === 'import-choose'", "focus on Choose a file")
                here = "document.activeElement && document.activeElement.id"
                tab = lambda shift: [p.cdp.call("Input.dispatchKeyEvent", {"type": k, "key": "Tab", "code": "Tab", "windowsVirtualKeyCode": 9, "modifiers": 8 if shift else 0}, p.sid) for k in ("keyDown", "keyUp")]
                tab(False)
                self.settle(p, here + " === 'import-template'", "Tab from Choose a file wraps to the first visible control")
                tab(True)
                self.settle(p, here + " === 'import-choose'", "Shift+Tab from the first control wraps back to Choose a file")
                tab(True)
                self.settle(p, "document.querySelector('#import-box').contains(document.activeElement) && document.activeElement.id !== 'import-choose'", "Shift+Tab moves to the control before it")
                p.key("Escape", code="Escape", vk=27)
                p.until("!document.querySelector('#import-box')", "Esc closed it")

    def test_escape_closes_the_box_and_focus_goes_back_to_the_button(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p)
            p.js("document.querySelector('#import-workbook').click()")
            p.until("!!document.querySelector('#import-box')", "the box opened")
            self.settle(p, "document.activeElement && document.activeElement.id === 'import-choose'", "focus moved into the box")
            p.js("document.querySelector('#import-box').dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))")
            p.until("!document.querySelector('#import-box')", "Esc closed it")
            self.settle(p, "document.activeElement && document.activeElement.id === 'import-workbook'", "focus back on Import workbook")

    def test_the_buttons_and_the_boxes_are_readable_in_light_and_dark(self):
        b64, _, _ = workbook(self.rig, self.tmp.name, "Agree the cut-over plan, again")
        probe = """(sel) => { const b = document.querySelector(sel); const cs = getComputedStyle(b);
          const px = (c) => c.match(/[\\d.]+/g).map(Number).slice(0, 3);
          const lum = ([r, g, bl]) => { const f = (v) => { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); }; return .2126 * f(r) + .7152 * f(g) + .0722 * f(bl); };
          let bg = b, c; while (bg) { c = getComputedStyle(bg).backgroundColor; if (!/rgba\\(.*, 0\\)|transparent/.test(c)) break; bg = bg.parentElement; }
          const a = lum(px(cs.color)), z = lum(px(c)); return (Math.max(a, z) + .05) / (Math.min(a, z) + .05); }"""
        for scheme in ("light", "dark"):
            with self.subTest(scheme=scheme), chrome() as cdp:
                p = self.page(cdp)
                p.js(f"document.documentElement.setAttribute('data-theme', '{scheme}')")
                self.open_settings(p)
                self.settle(p, "!!document.querySelector('#import-workbook')", "the Import workbook button")
                for sel in ("#export-workbook", "#import-workbook"):
                    self.assertGreaterEqual(p.js(f"({probe})('{sel}')"), 4.5, sel)
                p.js("document.querySelector('#import-workbook').click()")
                p.until("!!document.querySelector('#import-box')", "the box opened")
                self.choose(p, b64)
                p.until("!!document.querySelector('#import-go')", "the check")
                for sel in ("#import-go", "#import-box .btn.quiet"):
                    self.assertGreaterEqual(p.js(f"({probe})('{sel}')"), 4.5, sel)


if __name__ == "__main__":
    unittest.main()
