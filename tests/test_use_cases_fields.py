"""Row 830: the Use cases page's inline pieces (U3 archived list, U4 Add a use case, U5 Export to Excel, U7 next step and link).

Run: python3 dev/run_tests.py test_use_cases_fields
Source-level checks (no browser): the words are the prototype's (system/prototype/usecases.js), the pieces sit on the page and the
detail with no Edit gate, and the published file (page-view.html) carries none of them. Owner on a use case (U6) is not built:
changes.py does not take it for use_cases. The browser run at 1400 and 900 px is the lead's, under the box lock.
"""
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _demo import USER
from _paths import SRC
from _real_server import real_server
from clark import __main__ as launcher, changes, page, server as sv, use_cases_read
from clark.store import open_store
from test_inline_edits import EMPTY_BRANDING, click, key, need_chrome, tearDownModule  # noqa: F401
from test_publish import chrome as pub_chrome, opened, wait as pub_wait
from test_publish_usecases import made
from test_server import chrome, wait
from test_work_items import FIXED_DATE, load_demo, page_target

PAGE = SRC / "clark" / "page"
SRCS = PAGE / "src"


def text(path):
    return path.read_text(encoding="utf-8")


class UseCaseFields(unittest.TestCase):
    def test_page_has_the_pieces(self):
        page = re.sub(r"\s+", " ", text(SRCS / "edit" / "UseCasesPage.jsx"))
        for want in ("Add a use case", "Export to Excel", "Show archived", "Hide archived", "Restore", "archived use case"):
            self.assertIn(want, page)
        self.assertIn('op: "restore"', page)
        self.assertIn("exportExcel", page)
        self.assertIn('plural(n, "archived use case")} ${n === 1 ? "is" : "are"} hidden.', page)     # plural() gives "1 archived use case" / "2 archived use cases"
        self.assertIn('Showing ${plural(n, "archived use case")}.', page)
        helper = text(SRCS / "workItems.js")
        self.assertIn('n === 1 ? one : (many || one + "s")', helper)

    def test_detail_offers_next_step_and_link_without_edit_mode(self):
        detail = text(SRCS / "components" / "UseCaseDetail.jsx")
        self.assertRegex(detail, r"!ro && ed \?[^\n]*NextStep[^\n]*LinkButton")
        self.assertNotIn('mode.value', detail)
        edit = text(SRCS / "edit" / "UseCasesEdit.jsx")
        self.assertIn("b.live", edit)
        self.assertIn('"Done"', edit)

    def test_published_file_has_none(self):
        view = text(PAGE / "page-view.html")
        for gone in ("data-arch-toggle", "ucAddPage", "data-uc-step"):
            self.assertNotIn(gone, view)


UC = "TUL-U-001"                     # demo: "Flag", on the dashboard, 1.1
LIST = "#usecases&p=TUL"
SIZES = ((1400, 1400), (915, 900))   # (window, page): the box's scrollbars take 15 px
GONE = re.compile(r"Add a use case|Export to Excel|Add a next step|Link an existing work item|Show archived|Restore", re.I)


class Live(unittest.TestCase):
    """The page as the real server serves it, with NO Edit mode on (row 830)."""

    def setUp(self):
        need_chrome()
        self.store, self.folder, _ = load_demo()
        self.addCleanup(shutil.rmtree, str(self.folder), True)
        self.addCleanup(self.store.close)
        self.path = self.folder / "clark.db"
        self.s = real_server(self.path, self.read, projects=lambda archived=False: [{"code": "TUL", "name": "Tulip"}],
                             page_html=lambda: page.page_html(EMPTY_BRANDING))
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

    def sql(self, query, *args):
        st = open_store(self.path, onedrive_roots=[])
        try:
            return st.con.execute(query, args).fetchall()
        finally:
            st.close()

    def steps(self):
        return self.sql("SELECT count(*) FROM applies")[0][0]

    def archived(self):
        return bool(self.sql("SELECT archived FROM use_cases WHERE id=?", UC)[0][0])

    def archive(self):
        changes.make_change(self.path, [], USER)({"project": "TUL", "kind": "use_cases", "op": "archive", "id": UC, "place": "cell"})

    def until(self, cdp, sid, expr, what, seconds=20):
        self.assertTrue(wait(lambda: cdp.js(expr, sid), seconds), what)

    def visit(self, cdp, window, scheme, hash_):
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": window, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
        cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.s.port}/{hash_}"}, sid)
        return sid

    def each(self):
        for window, shown in SIZES:
            for scheme in ("light", "dark"):
                with self.subTest(width=shown, scheme=scheme), chrome() as cdp:
                    yield cdp, window, scheme

    def no_sideways(self, cdp, sid):
        self.assertTrue(cdp.js("document.documentElement.scrollWidth <= window.innerWidth", sid), "no horizontal scroll")

    def test_head_buttons_and_the_add_box_with_no_edit_mode(self):
        for n, (cdp, window, scheme) in enumerate(self.each()):
            sid = self.visit(cdp, window, scheme, LIST)
            self.until(cdp, sid, "document.querySelectorAll('#usecases .ucl-row[data-uc]').length > 0", "the list drew")
            self.assertFalse(cdp.js("!!document.querySelector('[data-mode=edit][aria-pressed=true]')", sid), "not in Edit")
            add = cdp.js("(document.querySelector('#usecases .head #ucAddPage') || {}).textContent || ''", sid)
            exp = cdp.js("(document.querySelector('#usecases .head #ucExp') || {}).textContent || ''", sid)
            self.assertRegex(add, r"Add a use case")
            self.assertRegex(exp, r"Export to Excel")
            self.no_sideways(cdp, sid)
            rows = cdp.js("document.querySelectorAll('#usecases .ucl-row[data-uc]').length", sid)
            before, ref, title = self.steps(), f"9.{n}", f"Row 830 case {n}"
            click(cdp, sid, "#ucAddPage")
            self.until(cdp, sid, "!!document.querySelector('#ucF')", "the Add box opened")
            cdp.js(f"(() => {{ for (const [id, v] of [['ucI', {json.dumps(ref)}], ['ucT', {json.dumps(title)}]]) {{ const e = document.getElementById(id); e.value = v; e.dispatchEvent(new Event('input', {{bubbles: true}})); }} }})()", sid)
            click(cdp, sid, "#ucF [data-place]")
            self.until(cdp, sid, "/hidden from the client/.test((document.querySelector('.toast-text') || {}).textContent || '')", "the toast said it starts hidden")
            self.until(cdp, sid, f"document.querySelectorAll('#usecases .ucl-row[data-uc]').length === {rows + 1}", "the new row is in the list")
            made_row = self.sql("SELECT client_visible FROM use_cases WHERE title=?", title)
            self.assertEqual(len(made_row), 1)
            self.assertFalse(made_row[0][0], "hidden from the client")
            self.assertEqual(self.steps(), before + 1, "one step")
            self.no_sideways(cdp, sid)

    def test_archived_list_restore_and_undo(self):
        for cdp, window, scheme in self.each():
            if not self.archived():
                self.archive()
            sid = self.visit(cdp, window, scheme, LIST)
            self.until(cdp, sid, "!!document.querySelector('#usecases [data-archived-uc] [data-arch-toggle]')", "the Show archived footer drew")
            self.assertEqual(re.sub(r"\s+", " ", cdp.js("document.querySelector('[data-archived-uc] .ucx-foot').textContent", sid)).strip(), "1 archived use case is hidden. Show archived")
            self.assertFalse(cdp.js(f"!!document.querySelector('#usecases .ucl-row[data-uc={json.dumps(UC)}]')", sid), "not in the live list")
            click(cdp, sid, "[data-arch-toggle]")
            self.until(cdp, sid, f"!!document.querySelector('.ucl-arch [data-arch-uc={json.dumps(UC)}] [data-restore]')", "the archived list with Restore")
            self.assertEqual(re.sub(r"\s+", " ", cdp.js("document.querySelector('[data-archived-uc] .ucx-foot').textContent", sid)).strip(), "Showing 1 archived use case. Hide archived")
            self.no_sideways(cdp, sid)
            before = self.steps()
            click(cdp, sid, ".ucl-arch [data-restore]")
            self.until(cdp, sid, f"!!document.querySelector('#usecases .ucl-row[data-uc={json.dumps(UC)}]')", "Restore brought it back to the list")
            self.assertEqual((self.archived(), self.steps()), (False, before + 1), "Restore is one step")
            click(cdp, sid, "[data-undo]")
            self.until(cdp, sid, f"!document.querySelector('#usecases .ucl-row[data-uc={json.dumps(UC)}]')", "Undo put it back in the archive")
            self.assertEqual((self.archived(), self.steps()), (True, before + 2), "Undo is one step")

    def test_detail_offers_next_step_and_link_with_no_edit_mode(self):
        for cdp, window, scheme in self.each():
            sid = self.visit(cdp, window, scheme, f"{LIST}&uc=1.1")
            self.until(cdp, sid, "!!document.querySelector('[data-ucd] [data-uc-step]') && !!document.querySelector('[data-ucd] [data-uc-link]')", "next step and link are on the detail")
            self.assertFalse(cdp.js("!!document.querySelector('[data-mode=edit][aria-pressed=true]')", sid), "not in Edit")
            self.assertRegex(cdp.js("document.querySelector('[data-ucd] [data-uc-step]').placeholder", sid), r"Add a next step")
            self.assertRegex(cdp.js("document.querySelector('[data-ucd] [data-uc-link]').textContent", sid), r"Link an existing work item")
            self.no_sideways(cdp, sid)
            click(cdp, sid, "[data-ucd] [data-uc-link]")
            self.until(cdp, sid, "!!document.querySelector('.uclink')", "the link box opened")
            key(cdp, sid, "Escape")
            self.until(cdp, sid, "!document.querySelector('.uclink')", "Esc closed it")


class Published(unittest.TestCase):
    def test_a_published_file_has_none_of_the_buttons(self):
        need_chrome()
        plant, pub, text = made()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "r.html"
            path.write_text(text, encoding="utf-8")
            for window, shown in SIZES:
                for scheme in ("light", "dark"):
                    with self.subTest(width=shown, scheme=scheme), pub_chrome() as cdp:
                        sid = opened(cdp, path.as_uri(), window)
                        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
                        self.assertTrue(pub_wait(lambda: cdp.js("document.documentElement.dataset.ready", sid) == "1"))
                        cdp.js("document.querySelector('[data-view=usecases]').click()", sid)
                        self.assertTrue(pub_wait(lambda: cdp.js("document.querySelector('h1').textContent", sid) == "Use cases"))
                        cdp.js("document.querySelector('.ucp summary').click()", sid)
                        self.assertEqual(cdp.js("document.querySelectorAll('#ucAddPage, #ucExp, [data-uc-step], [data-uc-link], [data-arch-toggle], [data-restore]').length", sid), 0)
                        self.assertIsNone(GONE.search(cdp.js("document.body.innerText", sid)), "none of the page's buttons")
                        self.assertTrue(cdp.js("document.documentElement.scrollWidth <= window.innerWidth", sid), "no horizontal scroll")


if __name__ == "__main__":
    unittest.main()
