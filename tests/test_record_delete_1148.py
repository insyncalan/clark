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
from _real_server import real_server
from clark import __main__ as launcher, page, server as sv, use_cases_read
from clark.store import open_store
from test_inline_edits import EMPTY_BRANDING, click, need_chrome, tearDownModule  # noqa: F401
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
                names = self.pick(cdp, sid, f"{row} .ucl-more", "delete")
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
                self.pick(cdp, sid, f"{row} .ucl-more", "delete")
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
            self.pick(cdp, sid, f"{row} .ucl-more", "archive")
            click(cdp, sid, ".ddmenu [data-kind=archive]")
            self.toast(cdp, sid, "Use case archived. It can be restored.")
            self.assertTrue(self.archived("use_cases", self.uc))

    def test_a_use_case_with_work_items_is_refused_by_name_and_stays(self):
        row = f"#usecases [data-uc={json.dumps(USED_UC)}]"
        with chrome() as cdp:
            sid = self.visit(cdp, "#usecases&p=TUL", f"!!document.querySelector('{row}')", 1400)
            self.pick(cdp, sid, f"{row} .ucl-more", "delete")
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
