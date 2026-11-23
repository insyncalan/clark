"""Item 1148: Delete a use case and a milestone the same way as a work item (item 658), from the new More actions menu.

Run: python3 dev/run_tests.py test_record_delete_1148
Drives the committed page against the real server in headless Chrome (set CLARK_CHROME to its path), at 1400 and 900 px. The menu is
Archive, then Delete last in the warning colour. The words are the work item's: the question "Delete <ID>? This removes it from your
project record." with Delete and Cancel, the toast "<ID> deleted." with Undo, and, when something points at the record, the refusal
"<ID> can't be deleted: something refers to it (...)." Rows: a use case's row on the Use cases page, its own page, a milestone's row
on the Milestones page and its peek.
"""
import json
import shutil
import unittest
from unittest import mock

from _demo import USER
from _new_page import reload_to_new_page_cdp
from _real_server import real_server
from clark import __main__ as launcher, page, server as sv, use_cases_read
from clark.store import open_store
from test_inline_edits import EMPTY_BRANDING, click, need_chrome, settle_motion, tearDownModule  # noqa: F401
from test_server import chrome, wait
from test_work_items import FIXED_DATE, load_demo, page_target

QUESTION = "Delete %s? This removes it from your project record."
USED_UC = "TUL-U-001"            # has linked work items
USED_MS = "TUL-M-002"            # a work item of the demo sits on it (TUL-A-006)


class Delete(unittest.TestCase):
    def setUp(self):
        need_chrome()
        self.store, self.folder, _ = load_demo()
        self.addCleanup(shutil.rmtree, str(self.folder), True)
        self.addCleanup(self.store.close)
        self.path = self.folder / "clark.db"
        with self.store.step("dashboard", USER) as st:             # one of each that nothing points at
            self.uc = st.create("use_cases", {"project": "TUL", "title": "Spare use case", "status": "On track", "source": "demo"})
            self.ms = st.create("milestones", {"project": "TUL", "name": "Spare milestone", "baseline_date": "2026-11-01", "source": "demo"})
        used = self.store.con.execute("SELECT count(*) FROM actions WHERE milestone = ?", (USED_MS,)).fetchone()[0] + self.store.con.execute("SELECT count(*) FROM raid WHERE milestone = ?", (USED_MS,)).fetchone()[0]
        self.assertTrue(used, "the demo has a work item on " + USED_MS)
        self.sent = []

        def seam(real, which):
            def call(req):
                self.sent.append((which, req))
                return real(req)
            return call
        self.s = real_server(self.path, self.read, projects=lambda archived=False: [{"code": "TUL", "name": "Tulip"}], page_html=lambda: page.page_html(EMPTY_BRANDING),
                             seam=seam)
        self.s.httpd.use_cases = use_cases_read.make_read(self.read, lambda code: set(), launcher.use_case_history(mock.Mock(path=self.path)))
        self.addCleanup(self.s.close)
        quiet = mock.patch.object(sv.LOG, "disabled", True)
        quiet.start()
        self.addCleanup(quiet.stop)

    def read(self, code, archived="hide"):
        st = open_store(self.path, onedrive_roots=[])
        try:
            return st.data_for(code, archived=archived)
        finally:
            st.close()

    def gone(self, table, ref):
        st = open_store(self.path, onedrive_roots=[])
        try:
            return st.read(table, ref=ref) is None
        finally:
            st.close()

    def archived(self, table, ref):
        st = open_store(self.path, onedrive_roots=[])
        try:
            return bool(st.read(table, ref=ref)["archived"])
        finally:
            st.close()

    def until(self, cdp, sid, expr, what, seconds=20):
        self.assertTrue(wait(lambda: cdp.js(expr, sid), seconds), what)

    def visit(self, cdp, hash_, ready, width):
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.s.port}/{hash_}"}, sid)
        self.until(cdp, sid, ready, "the page drew")
        return sid

    def pick(self, cdp, sid, button, entry):
        if button.endswith(".ucl-go"):      # row 1203: a use case's row has no More button, its menu is the right-click menu (the same two entries)
            cdp.js(f"document.querySelector({json.dumps(button)}).dispatchEvent(new MouseEvent('contextmenu', {{bubbles: true, cancelable: true, clientX: 300, clientY: 300}}))", sid)
        else:
            click(cdp, sid, button)
        self.until(cdp, sid, f"!!document.querySelector('.ddmenu [data-kind={entry}]')", "the More actions menu opened")
        return cdp.js("[...document.querySelectorAll('.ddmenu [role=menuitem]')].map(b => b.dataset.kind)", sid)

    def question(self, cdp, sid):
        self.until(cdp, sid, "!!document.querySelector('[role=alertdialog] .bask-q')", "the question")
        return cdp.js("({q: document.querySelector('.bask-q').textContent, b: [...document.querySelectorAll('.bask-b button')].map(b => b.textContent)})", sid)

    def refused(self, cdp, sid, ref):
        self.until(cdp, sid, "/can't be deleted/.test((document.querySelector('.toast-text') || {}).textContent || '')", "a refusal toast")
        text = cdp.js("document.querySelector('.toast-text').textContent", sid)
        self.assertRegex(text, "^" + ref + r" can't be deleted: something refers to it \((an action|a RAID item|a decision) [A-Z]+-")

    def toast(self, cdp, sid, text):
        self.until(cdp, sid, f"(document.querySelector('.toast-text') || {{}}).textContent === {json.dumps(text)}", f"the toast {text!r}")

    # ---- a use case ----
    def test_a_use_case_row_has_more_actions_archive_then_delete_and_delete_asks_then_undo_brings_it_back(self):
        row = f"#usecases [data-uc={json.dumps(self.uc)}]"
        for width in (1400, 900):
            with self.subTest(width), chrome() as cdp:
                sid = self.visit(cdp, "#usecases&p=TUL", f"document.querySelectorAll('#usecases .ucl-row[data-uc]').length > 0 && !!document.querySelector('{row}')", width)
                self.assertTrue(cdp.js("document.documentElement.scrollWidth <= window.innerWidth", sid), "no sideways scroll")
                names = self.pick(cdp, sid, f"{row} .ucl-go", "delete")
                self.assertEqual(names, ["archive", "delete"])
                self.assertTrue(cdp.js("document.querySelector('.ddmenu [data-kind=delete]').classList.contains('danger')", sid))
                click(cdp, sid, ".ddmenu [data-kind=delete]")
                d = self.question(cdp, sid)
                self.assertEqual(d["q"], QUESTION % self.uc)
                self.assertEqual(d["b"], ["Delete", "Cancel"])
                click(cdp, sid, "[role=alertdialog] [data-bask=no]")                      # Cancel changes nothing
                self.until(cdp, sid, "!document.querySelector('[role=alertdialog]')", "the question closed")
                self.assertFalse(self.gone("use_cases", self.uc))
                self.assertTrue(cdp.js(f"!!document.querySelector('{row}')", sid))
                self.pick(cdp, sid, f"{row} .ucl-go", "delete")
                click(cdp, sid, ".ddmenu [data-kind=delete]")
                self.question(cdp, sid)
                click(cdp, sid, "[role=alertdialog] [data-bask=yes]")
                self.toast(cdp, sid, f"{self.uc} deleted.")
                self.until(cdp, sid, f"!document.querySelector('{row}')", "the row left the list")
                self.assertTrue(self.gone("use_cases", self.uc))
                click(cdp, sid, "[data-undo]")
                self.until(cdp, sid, f"!!document.querySelector('{row}')", "the row came back")
                self.assertFalse(self.gone("use_cases", self.uc))

    def test_archive_is_in_the_row_menu_and_takes_the_archive_step(self):
        row = f"#usecases [data-uc={json.dumps(self.uc)}]"
        with chrome() as cdp:
            sid = self.visit(cdp, "#usecases&p=TUL", f"!!document.querySelector('{row}')", 1400)
            self.pick(cdp, sid, f"{row} .ucl-go", "archive")
            click(cdp, sid, ".ddmenu [data-kind=archive]")
            self.toast(cdp, sid, "Use case archived. It can be restored.")
            self.assertTrue(self.archived("use_cases", self.uc))

    def test_row_1203_the_rows_have_column_names_and_no_more_button_and_the_menu_key_opens_the_menu_and_esc_gives_the_focus_back(self):
        row = f"#usecases [data-uc={json.dumps(self.uc)}]"
        for width in (1400, 900):
            with self.subTest(width), chrome() as cdp:
                sid = self.visit(cdp, "#usecases&p=TUL", f"!!document.querySelector('{row}')", width)
                heads = cdp.js("[...document.querySelectorAll('#usecases .ucl-cols > span')].map(s => s.textContent).filter(Boolean)", sid)
                self.assertEqual(heads, ["Use case", "Where it stands", "Status", "Next steps"])
                self.assertEqual(cdp.js("document.querySelectorAll('#usecases .ucl-more').length", sid), 0, "no More button on a row")
                cdp.js(f"document.querySelector({json.dumps(row + ' .ucl-go')}).focus()", sid)
                cdp.js(f"document.querySelector({json.dumps(row + ' .ucl-go')}).dispatchEvent(new MouseEvent('contextmenu', {{bubbles: true, cancelable: true, clientX: 0, clientY: 0}}))", sid)      # the menu key or Shift+F10: no pointer
                self.until(cdp, sid, "!!document.querySelector('#ucl-ctx [data-kind=archive]')", "the menu opened")
                self.assertEqual(cdp.js("[...document.querySelectorAll('#ucl-ctx [role=menuitem]')].map(b => b.dataset.kind)", sid), ["archive", "delete"])
                cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27}, sid)
                cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27}, sid)
                self.until(cdp, sid, "!document.querySelector('#ucl-ctx')", "the menu closed")
                self.until(cdp, sid, f"document.activeElement === document.querySelector({json.dumps(row + ' .ucl-go')})", "the focus is back on the row's name")

    def ctx(self, cdp, sid, row, x=300, y=300):
        cdp.js(f"document.querySelector({json.dumps(row + ' .ucl-go')}).dispatchEvent(new MouseEvent('contextmenu', {{bubbles: true, cancelable: true, clientX: {x}, clientY: {y}}}))", sid)
        self.until(cdp, sid, "!!document.querySelector('#ucl-ctx [data-kind=archive]')", "the row's menu opened")

    def test_row_1203_the_row_menu_is_named_and_has_archive_a_separator_and_delete_in_the_warning_colour_at_the_pointer(self):
        row = f"#usecases [data-uc={json.dumps(self.uc)}]"
        for width in (1400, 900):
            with self.subTest(width), chrome() as cdp:
                sid = self.visit(cdp, "#usecases&p=TUL", f"!!document.querySelector('{row}')", width)
                self.ctx(cdp, sid, row)
                got = cdp.js("(() => { const m = document.querySelector('#ucl-ctx'), r = m.getBoundingClientRect(); return { role: m.getAttribute('role'), label: m.getAttribute('aria-label'), cls: m.classList.contains('ddmenu'), items: [...m.children].map(c => [c.getAttribute('role'), c.dataset.kind || '', c.textContent, c.classList.contains('danger')]), left: r.left, top: r.top, open: document.querySelectorAll('#ucl-ctx').length }; })()", sid)
                self.assertEqual((got["role"], got["label"], got["cls"], got["open"]), ("menu", "Use case actions", True, 1))
                self.assertEqual(got["items"], [["menuitem", "archive", "Archive", False], ["separator", "", "", False], ["menuitem", "delete", "Delete", True]])
                self.assertLess(abs(got["left"] - 300), 4, "the menu's left edge is at the pointer")
                self.assertTrue(300 <= got["top"] <= 312, "the menu is just under the pointer (got %s)" % got["top"])

    def test_row_1203_archive_in_the_row_menu_archives_that_row_only_and_closes_the_menu(self):
        row = f"#usecases [data-uc={json.dumps(self.uc)}]"
        with chrome() as cdp:
            sid = self.visit(cdp, "#usecases&p=TUL", f"!!document.querySelector('{row}')", 1400)
            self.ctx(cdp, sid, row)
            click(cdp, sid, "#ucl-ctx [data-kind=archive]")
            self.toast(cdp, sid, "Use case archived. It can be restored.")
            self.assertTrue(self.archived("use_cases", self.uc))
            self.assertFalse(self.archived("use_cases", USED_UC), "no other use case is archived")
            self.until(cdp, sid, "!document.querySelector('#ucl-ctx')", "the menu closed")

    def test_row_1203_delete_in_the_row_menu_asks_about_that_row_and_cancel_gives_the_focus_to_its_name(self):
        row = f"#usecases [data-uc={json.dumps(self.uc)}]"
        with chrome() as cdp:
            sid = self.visit(cdp, "#usecases&p=TUL", f"!!document.querySelector('{row}')", 1400)
            self.ctx(cdp, sid, row)
            click(cdp, sid, "#ucl-ctx [data-kind=delete]")
            q = self.question(cdp, sid)
            self.assertEqual(q["q"], QUESTION % self.uc)
            self.until(cdp, sid, "!document.querySelector('#ucl-ctx')", "the menu closed under the question")
            click(cdp, sid, "[role=alertdialog] [data-bask=no]")
            self.until(cdp, sid, "!document.querySelector('[role=alertdialog]')", "the question closed")
            self.until(cdp, sid, f"document.activeElement === document.querySelector({json.dumps(row + ' .ucl-go')})", "the focus is on the row's name")
            self.assertFalse(self.gone("use_cases", self.uc))

    def test_row_1203_the_column_names_are_over_the_rows_in_both_groupings_with_the_rows_six_columns(self):
        for width in (1400, 900):
            with self.subTest(width), chrome() as cdp:
                sid = self.visit(cdp, "#usecases&p=TUL", "document.querySelectorAll('#usecases .ucl-row[data-uc]').length > 0", width)
                for grouping in ("status", "nothing"):
                    cdp.js(f"localStorage.setItem('clark.ucPage', JSON.stringify({{TUL: {{line: '', tab: 'all', group: '{grouping}', sort: 'ref'}}}}))", sid)
                    reload_to_new_page_cdp(cdp, sid, "document.querySelectorAll('#usecases .ucl-row[data-uc]').length > 0", "the rows again on the new page")
                    got = cdp.js("""(() => {
                        const box = document.querySelector('#usecases .ucl-box'), cols = box.querySelectorAll('.ucl-cols'), first = box.querySelector('.ucl-row[data-uc]');
                        const tracks = (el) => getComputedStyle(el).gridTemplateColumns.split(' ').length;
                        const w = (el) => getComputedStyle(el).gridTemplateColumns;
                        return { n: cols.length, hidden: cols[0].getAttribute('aria-hidden'), heads: [...cols[0].children].map(s => s.textContent),
                                 headTracks: tracks(cols[0]), rowTracks: tracks(first), same: w(cols[0]).split(' ').slice(-3).join(' ') === w(first).split(' ').slice(-3).join(' ') && w(first).split(' ').slice(-3).join(' '),  above: cols[0].getBoundingClientRect().bottom <= first.getBoundingClientRect().top,
                                 span: getComputedStyle(cols[0].querySelector('.ucl-c1')).gridColumnStart + '/' + getComputedStyle(cols[0].querySelector('.ucl-c1')).gridColumnEnd };
                    })()""", sid)
                    self.assertEqual(got["n"], 1, f"one line of column names ({grouping})")
                    self.assertEqual(got["hidden"], "true")
                    self.assertEqual(got["heads"], ["Use case", "Where it stands", "Status", "Next steps", ""])
                    self.assertEqual((got["headTracks"], got["rowTracks"]), (6, 6), "six columns in the names and in a row")
                    self.assertTrue(got["same"], "the names sit on the rows' three fixed columns")
                    self.assertIn(got["same"], ("124px 112px 36px", "124px 96px 36px"), "the fixed columns are the rows' own")
                    self.assertTrue(got["above"], "the names are over the rows")
                    self.assertEqual(got["span"], "1/3", "the first name spans the reference and the title columns")

    def test_row_1203_a_row_has_no_more_button_in_source_or_page_and_arrows_go_name_then_eye_only(self):
        here = __import__("pathlib").Path(page.__file__).parent
        for part in (here / "src" / "edit" / "UseCasesPage.jsx", here / "src" / "edit" / "edit.css"):
            self.assertNotIn("ucl-more", part.read_text(encoding="utf-8"), part.name)
        row = f"#usecases [data-uc={json.dumps(self.uc)}]"
        with chrome() as cdp:
            sid = self.visit(cdp, "#usecases&p=TUL", f"!!document.querySelector('{row}')", 1400)
            key = lambda k: (cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": k, "code": k, "windowsVirtualKeyCode": {"ArrowRight": 39, "ArrowLeft": 37}[k]}, sid), cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": k, "code": k, "windowsVirtualKeyCode": {"ArrowRight": 39, "ArrowLeft": 37}[k]}, sid))
            on = lambda: cdp.js("document.activeElement.className", sid)
            cdp.js(f"document.querySelector({json.dumps(row + ' .ucl-go')}).focus()", sid)
            key("ArrowRight")
            self.until(cdp, sid, "document.activeElement.classList.contains('ucl-eye')", "the eye after the name")
            key("ArrowRight")
            self.assertTrue(cdp.js("document.activeElement.classList.contains('ucl-eye')", sid), "nothing after the eye")
            self.assertEqual(cdp.js(f"document.querySelectorAll({json.dumps(row + ' button')}).length", sid), 2, "the row has the name and the eye only")
            key("ArrowLeft")
            self.until(cdp, sid, "document.activeElement.classList.contains('ucl-go')", "the name before the eye")
            key("ArrowLeft")
            self.assertTrue(cdp.js("document.activeElement.classList.contains('ucl-go')", sid), "nothing before the name")

    def test_a_use_case_with_work_items_is_refused_by_name_and_stays(self):
        row = f"#usecases [data-uc={json.dumps(USED_UC)}]"
        with chrome() as cdp:
            sid = self.visit(cdp, "#usecases&p=TUL", f"!!document.querySelector('{row}')", 1400)
            self.pick(cdp, sid, f"{row} .ucl-go", "delete")
            click(cdp, sid, ".ddmenu [data-kind=delete]")
            self.question(cdp, sid)
            click(cdp, sid, "[role=alertdialog] [data-bask=yes]")
            self.refused(cdp, sid, USED_UC)
            self.assertFalse(self.gone("use_cases", USED_UC))
            self.assertTrue(cdp.js(f"!!document.querySelector('{row}')", sid))

    def test_the_use_case_page_has_more_actions_in_place_of_the_archive_link_and_delete_goes_back_to_the_list(self):
        for width in (1400, 900):
            with self.subTest(width), chrome() as cdp:
                sid = self.visit(cdp, f"#usecases&p=TUL&uc={self.uc}", "!!document.querySelector('[data-ucd]') && !!document.querySelector('#ucd-more')", width)
                self.assertFalse(cdp.js("!!document.querySelector('[data-archive]')", sid), "the foot link is gone")
                self.assertEqual(self.pick(cdp, sid, "#ucd-more", "delete"), ["archive", "delete"])
                click(cdp, sid, ".ddmenu [data-kind=delete]")
                self.assertEqual(self.question(cdp, sid)["q"], QUESTION % self.uc)
                click(cdp, sid, "[role=alertdialog] [data-bask=yes]")
                self.toast(cdp, sid, f"{self.uc} deleted.")
                self.until(cdp, sid, "location.hash === '#usecases&p=TUL'", "back at the list")
                self.assertTrue(self.gone("use_cases", self.uc))
                click(cdp, sid, "[data-undo]")                                                       # the next width starts with it back
                self.until(cdp, sid, f"!!document.querySelector('#usecases [data-uc={json.dumps(self.uc)}]')", "it came back")

    # ---- a milestone ----
    def test_a_milestone_row_and_its_peek_have_more_actions_and_delete_asks_then_undo_brings_it_back(self):
        row = f"li.msl-row[data-ms={json.dumps(self.ms)}]"
        for width in (1400, 900):
            with self.subTest(width), chrome() as cdp:
                sid = self.visit(cdp, "#milestones&p=TUL", f"!!document.querySelector({json.dumps(row)})", width)
                self.assertTrue(cdp.js("document.documentElement.scrollWidth <= window.innerWidth", sid), "no sideways scroll")
                self.assertEqual(self.pick(cdp, sid, f"{row} .ms-more", "delete"), ["archive", "delete"])
                click(cdp, sid, ".ddmenu [data-kind=delete]")
                self.assertEqual(self.question(cdp, sid)["q"], QUESTION % self.ms)
                click(cdp, sid, "[role=alertdialog] [data-bask=yes]")
                self.toast(cdp, sid, f"{self.ms} deleted.")
                self.until(cdp, sid, f"!document.querySelector({json.dumps(row)})", "the row left the list")
                self.assertTrue(self.gone("milestones", self.ms))
                click(cdp, sid, "[data-undo]")
                self.until(cdp, sid, f"!!document.querySelector({json.dumps(row)})", "the row came back")
                self.assertFalse(self.gone("milestones", self.ms))

    def test_the_milestone_peek_has_more_actions_and_delete_closes_the_peek(self):
        row = f"li.msl-row[data-ms={json.dumps(self.ms)}]"
        with chrome() as cdp:
            sid = self.visit(cdp, "#milestones&p=TUL", f"!!document.querySelector({json.dumps(row)})", 1400)
            click(cdp, sid, f"{row} .msl-cells")
            self.until(cdp, sid, "!!document.querySelector('#peek #pk-more')", "the peek has More actions")
            self.assertFalse(cdp.js("!!document.querySelector('#peek [data-pk-archive]')", sid))
            self.assertEqual(self.pick(cdp, sid, "#peek #pk-more", "delete"), ["archive", "delete"])
            click(cdp, sid, ".ddmenu [data-kind=delete]")
            self.question(cdp, sid)
            click(cdp, sid, "[role=alertdialog] [data-bask=yes]")
            self.toast(cdp, sid, f"{self.ms} deleted.")
            self.until(cdp, sid, "!document.querySelector('#peek')", "the peek closed with it")
            self.assertTrue(self.gone("milestones", self.ms))

    def test_the_press_on_more_actions_lands_after_the_peek_slide_has_ended(self):
        """Issue 1552: the peek slides in for half a second (pk-in); a press on its More button while that runs lands on a moving target (macOS shard 6/6 never saw the menu)."""
        row = f"li.msl-row[data-ms={json.dumps(self.ms)}]"
        with chrome() as cdp:
            sid = self.visit(cdp, "#milestones&p=TUL", f"!!document.querySelector({json.dumps(row)})", 1400)
            click(cdp, sid, f"{row} .msl-cells")
            self.until(cdp, sid, "!!document.querySelector('#peek #pk-more')", "the peek has More actions")
            cdp.js("window.__sliding = null; document.addEventListener('mousedown', () => { window.__sliding = document.getAnimations().filter(a => a.animationName && a.playState === 'running' && a.effect && a.effect.target && a.effect.target.closest && a.effect.target.closest('#peek')).length; }, true)", sid)
            click(cdp, sid, "#peek #pk-more")
            self.assertEqual(cdp.js("window.__sliding", sid), 0, "no animation was still running on the peek when the press landed")

    def test_settle_motion_waits_for_a_slide_that_is_still_running(self):
        """Issue 1552: a press waits for a finite animation on the control or around it, and does not wait for one that never ends."""
        row = f"li.msl-row[data-ms={json.dumps(self.ms)}]"
        slide = "document.getAnimations().filter(a => a.effect.target.id === 'd1552' && a.playState === 'running').length"
        with chrome() as cdp:
            sid = self.visit(cdp, "#milestones&p=TUL", f"!!document.querySelector({json.dumps(row)})", 1400)
            cdp.js("document.body.insertAdjacentHTML('beforeend', '<div id=d1552><b id=b1552>x</b></div>'); document.getElementById('d1552').animate([{transform: 'translateX(300px)'}, {transform: 'none'}], 1200); document.getElementById('b1552').animate([{opacity: 1}, {opacity: .5}], {duration: 1000, iterations: Infinity})", sid)
            self.assertEqual(cdp.js(slide, sid), 1, "the slide runs")
            settle_motion(cdp, sid, "#b1552")
            self.assertEqual(cdp.js(slide, sid), 0, "the slide around the control had ended")

    def test_a_milestone_a_work_item_sits_on_is_refused_by_name_and_stays(self):
        row = f"li.msl-row[data-ms={json.dumps(USED_MS)}]"
        with chrome() as cdp:
            sid = self.visit(cdp, "#milestones&p=TUL", f"!!document.querySelector({json.dumps(row)})", 1400)
            self.pick(cdp, sid, f"{row} .ms-more", "delete")
            click(cdp, sid, ".ddmenu [data-kind=delete]")
            self.question(cdp, sid)
            click(cdp, sid, "[role=alertdialog] [data-bask=yes]")
            self.refused(cdp, sid, USED_MS)
            self.assertFalse(self.gone("milestones", USED_MS))


if __name__ == "__main__":
    unittest.main()
