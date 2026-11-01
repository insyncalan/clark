"""#157, the two parts together: the real route of the Use cases page, in a real browser (what each part's own tests cannot see).

Run: python3 dev/run_tests.py test_use_cases_page_e2e
Open #usecases&p=TUL, click a row's name, land on the use case's own page at #usecases&p=TUL&uc=<ref>, check two columns at 1400 px and
one at 900 px, change the status (one change, one Undo), press Esc and see the focus come back to that row, then Back and Forward.
At 1400 and 900 px, light and dark. The page is the committed one (page.html) served by a real server over the real change and undo
routes and a real store in a temporary folder (fictional data).
"""
import json
import shutil
import unittest
from unittest import mock

from _demo import USER
from _real_server import real_server
from clark import __main__ as launcher, changes, page, server as sv, use_cases_read
from clark.store import open_store
from test_inline_edits import EMPTY_BRANDING, click, key, need_chrome, tearDownModule  # noqa: F401
from test_server import chrome, wait
from test_work_items import FIXED_DATE, load_demo, page_target

UC = "TUL-U-001"                     # demo: "Flag", on the dashboard; its reference is 1.1
LIST = "#usecases&p=TUL"


class Walk(unittest.TestCase):
    def setUp(self):
        need_chrome()
        self.store, self.folder, _ = load_demo()
        self.addCleanup(shutil.rmtree, str(self.folder), True)
        self.addCleanup(self.store.close)
        self.path = self.folder / "clark.db"
        self.sent = []

        def seam(real, which):
            def call(req):
                self.sent.append((which, req))
                return real(req)
            return call
        self.s = real_server(self.path, self.read, projects=lambda: [{"code": "TUL", "name": "Tulip"}], page_html=lambda: page.page_html(EMPTY_BRANDING),
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

    def row(self):
        st = open_store(self.path, onedrive_roots=[])
        try:
            return st.read("use_cases", ref=UC)
        finally:
            st.close()

    def steps(self):
        st = open_store(self.path, onedrive_roots=[])
        try:
            return st.con.execute("SELECT count(*) FROM applies").fetchone()[0]
        finally:
            st.close()

    def until(self, cdp, sid, expr, what, seconds=20):
        self.assertTrue(wait(lambda: cdp.js(expr, sid), seconds), what)

    def test_the_list_opens_the_use_case_and_esc_back_and_forward_walk_it(self):
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                    self.walk(cdp, width, scheme)

    def walk(self, cdp, width, scheme):
        self.sent.clear()
        sid = page_target(cdp)
        js = lambda expr: cdp.js(expr, sid)  # noqa: E731
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
        cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.s.port}/{LIST}"}, sid)
        self.until(cdp, sid, f"location.hash === {json.dumps(LIST)} && document.querySelectorAll('#usecases .ucl-row[data-uc]').length > 0", "the list drew at its own address")
        js("document.querySelector('[data-mode=edit]').click()")
        self.until(cdp, sid, "!!document.querySelector('#usecases [data-eye]')", "Edit")
        ref = js(f"document.querySelector('[data-uc={json.dumps(UC)}] .ucl-ref').textContent.replace(/^UC /, '')")
        self.assertEqual(ref, "1.1")
        detail = f"{LIST}&uc={ref}"

        # the name opens the use case, at its own address, with its own page
        click(cdp, sid, f"[data-uc={json.dumps(UC)}] .ucl-go")
        self.until(cdp, sid, f"location.hash === {json.dumps(detail)} && !!document.querySelector('[data-ucd]') && !document.querySelector('#usecases')", "the use case page, at its address")
        self.until(cdp, sid, "document.activeElement && document.activeElement.classList.contains('ucd-h')", "the heading took the focus")
        columns = js("getComputedStyle(document.querySelector('.ucd-grid')).gridTemplateColumns.split(' ').length")
        self.assertEqual(columns, 2 if width == 1400 else 1, "two columns at 1400 px, one at 900 px")
        self.assertEqual(js("document.querySelector('.ucd-crumb').textContent"), "Use cases › UC 1.1")
        self.assertLessEqual(js("document.documentElement.scrollWidth"), width, "no sideways scroll")
        small = js("[...document.querySelectorAll('[data-ucd] button, [data-ucd] a, [data-ucd] textarea')].filter(e => { const b = e.getBoundingClientRect(); return b.width && (b.height < 24 || b.width < 24); }).map(e => e.className + ':' + e.textContent.slice(0, 20))")
        self.assertEqual(small, [], "every control is at least 24 px")

        # the status: one change, one Undo
        before = self.steps()
        self.assertEqual(self.row()["status"], "Flag")
        click(cdp, sid, "#ucd-status")
        self.until(cdp, sid, "!!document.querySelector('[role=menu]')", "the status menu opened")
        click(cdp, sid, "[role=menu] [data-kind='High risk']")
        self.until(cdp, sid, "!!document.querySelector('[data-undo]') && document.querySelector('[data-ucd] [data-word]').textContent === 'High risk'", "the word changed")
        self.assertEqual((self.row()["status"], self.steps()), ("High risk", before + 1), "one change")
        click(cdp, sid, "[data-undo]")
        self.until(cdp, sid, "/Undone/.test((document.querySelector('.toast-text') || {}).textContent || '')", "the Undo said so")
        self.until(cdp, sid, "document.querySelector('[data-ucd] [data-word]').textContent === 'Flag'", "the old word is back")
        self.assertEqual((self.row()["status"], self.steps()), ("Flag", before + 2), "one Undo is one step")
        self.assertEqual([w for w, _ in self.sent], ["change", "undo"])

        # Esc leaves for the list and the row it came from takes the focus
        js("document.activeElement && document.activeElement.blur && document.activeElement.blur()")
        key(cdp, sid, "Escape")
        self.until(cdp, sid, f"location.hash === {json.dumps(LIST)} && document.querySelectorAll('#usecases .ucl-row[data-uc]').length > 0", "Esc leaves for the list")
        self.until(cdp, sid, f"!!document.activeElement.closest && !!document.activeElement.closest('.ucl-row') && document.activeElement.closest('.ucl-row').dataset.uc === {json.dumps(UC)}", "the row takes the focus")
        self.assertTrue(js("document.activeElement.classList.contains('ucl-go')"), "on the name")

        # Back goes to the use case, Forward to the list
        js("history.back()")
        self.until(cdp, sid, f"location.hash === {json.dumps(detail)} && !!document.querySelector('[data-ucd] [data-word]')", "Back to the use case")
        self.assertEqual(js("getComputedStyle(document.querySelector('.ucd-grid')).gridTemplateColumns.split(' ').length"), 2 if width == 1400 else 1)
        js("history.forward()")
        self.until(cdp, sid, f"location.hash === {json.dumps(LIST)} && document.querySelectorAll('#usecases .ucl-row[data-uc]').length > 0", "Forward to the list")


    def test_an_archived_use_case_address_opens_it_read_only_with_restore(self):
        """The address of an archived use case (not in the page's live data) opens its own page, read-only, with Restore: one step back."""
        ref = "1.1"                  # the demo's reference for UC (the walk above reads it from the list)
        made = changes.make_change(self.path, [], USER)({"project": "TUL", "kind": "use_cases", "op": "archive", "id": UC, "place": "cell"})
        self.assertTrue(self.row()["archived"], made)
        before = self.steps()
        detail = f"{LIST}&uc={ref}"
        with chrome() as cdp:
            sid = page_target(cdp)
            js = lambda expr: cdp.js(expr, sid)  # noqa: E731
            cdp.call("Page.enable", {}, sid)
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": 1400, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
            cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.s.port}/{detail}"}, sid)
            self.until(cdp, sid, "!!document.querySelector('[data-mode=edit]')", "the page drew")
            js("document.querySelector('[data-mode=edit]').click()")
            self.until(cdp, sid, f"location.hash === {json.dumps(detail)} && !!document.querySelector('[data-ucd][data-archived] [data-restore]')", "the archived use case opened at its own address, with Restore")
            self.assertFalse(js("!!document.querySelector('#usecases')"), "not the list")
            self.assertEqual(js("document.querySelectorAll('[data-ucd] textarea, [data-ucd] input').length"), 0, "read-only")
            click(cdp, sid, "[data-restore]")
            self.until(cdp, sid, "/Use case restored/.test((document.querySelector('.toast-text') || {}).textContent || '')", "the Restore said so")
            self.assertEqual((bool(self.row()["archived"]), self.steps()), (False, before + 1), "Restore is one step")

if __name__ == "__main__":
    unittest.main()
