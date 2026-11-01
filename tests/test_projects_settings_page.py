"""A-S6: Settings › Projects, the table of projects (Name, Code, Client, Workstreams, Items) with Open, Archive, Restore and Show archived.

Run: python3 dev/run_tests.py test_projects_settings_page
Part 1 runs the page's pure rules (src/clark/page/src/logic/projectsTable.js) in headless Chrome. Part 2 loads the committed page from the
real server (demo database, fictional data) at 1400 and 900 px, light and dark, and uses the routes that already exist: the list of
projects, one project's data, and a change of kind projects (archive and restore) with its Undo. The server's change and undo are small
stand-ins that record what the page sent; the store's own archive is tested in test_changes_archive. Adding and editing a project are not
on the page (no route yet), and a published file has no Settings. The browser parts are required: they fail, never skip, without Chrome.
"""
import json
import tempfile
import unittest

from _paths import SRC

from clark import page
from test_server import Running, chrome, wait
from test_work_items import FIXED_DATE, bundled, load_demo, page_target

MODULE = SRC / "clark" / "page" / "src" / "logic" / "projectsTable.js"
SRC_DIR = SRC / "clark" / "page" / "src"


class Rules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = {"project": {"client_name": " Example Client "},
                "workstreams": [{"name": "Build", "status": "Active", "archived": 0}, {"name": "Old", "status": "Closed", "archived": 0},
                                {"name": "Gone", "status": "Active", "archived": 1}],
                "actions": [{}, {}], "raid": [{}], "decisions": [{}, {}, {}]}
        script = (bundled(MODULE, "PT") + ";\n(" + """(d) => ({
            live: PT.rowOf({code: 'ABC', name: 'Alpha'}, d, false),
            gone: PT.rowOf({code: 'ABC', name: 'Alpha'}, d, true),
            bare: PT.rowOf({code: 'XYZ', name: 'Bare'}, null, false),
            count: [PT.countLabel(0), PT.countLabel(2)],
        })""" + ")(" + json.dumps(data) + ")")
        with chrome() as cdp:
            sid = page_target(cdp)
            res = cdp.call("Runtime.evaluate", {"expression": script, "returnByValue": True}, sid)
            assert "exceptionDetails" not in res, res
            cls.out = res["result"]["value"]

    def test_a_live_project_shows_its_client_active_workstreams_and_every_work_item(self):
        self.assertEqual(self.out["live"], {"code": "ABC", "name": "Alpha", "client": "Example Client", "workstreams": "Build", "items": 6, "archived": False})

    def test_an_archived_project_lists_all_its_workstreams(self):
        self.assertEqual(self.out["gone"]["workstreams"], "Build, Old, Gone")
        self.assertTrue(self.out["gone"]["archived"])

    def test_a_project_with_nothing_read_shows_dashes_and_no_items(self):
        self.assertEqual(self.out["bare"], {"code": "XYZ", "name": "Bare", "client": "—", "workstreams": "—", "items": 0, "archived": False})

    def test_show_archived_carries_a_count_only_when_there_is_one(self):
        self.assertEqual(self.out["count"], ["Show archived", "Show archived (2)"])


class Source(unittest.TestCase):
    def test_the_published_page_has_no_projects_table_and_no_way_to_archive(self):
        view = (SRC / "clark" / "page" / "page-view.html").read_text(encoding="utf-8")
        for needle in ("projects-table", "Show archived", '"kind":"projects"', "kind: \"projects\""):
            self.assertNotIn(needle, view, needle)

    def test_nothing_creates_a_project_from_the_page(self):
        text = (SRC_DIR / "edit" / "projectsApi.js").read_text(encoding="utf-8") + (SRC_DIR / "edit" / "Projects.jsx").read_text(encoding="utf-8")
        self.assertNotIn('"new"', text)
        self.assertNotIn("op: \"update\"", text)


class Browser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store, cls.folder, cls.ids = load_demo()
        cls.names = {p["code"]: p["name"] for p in cls.store.read("projects")}
        cls.data = {c: cls.store.data_for(c) for c in cls.names}

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        import shutil
        shutil.rmtree(str(cls.folder), ignore_errors=True)

    def serve(self):
        self.gone, self.sent, self.undone = set(), [], []

        def projects(archived=False):
            return [{"code": c, "name": n} for c, n in sorted(self.names.items()) if (c in self.gone) == bool(archived)]

        def change(req):
            self.sent.append(req)
            (self.gone.add if req["op"] == "archive" else self.gone.discard)(req["id"])
            return 200, {"ok": True, "apply_id": 40 + len(self.sent), "ref": req["id"], "archived": 1 if req["op"] == "archive" else 0}

        def undo(req):
            self.undone.append(req)
            self.gone.symmetric_difference_update({self.sent[-1]["id"]})
            return 200, {"ok": True, "sections": [], "words": "", "skipped": []}

        s = Running(data_for=lambda code, **kw: self.data.get(code), projects=projects, change=change, undo=undo,
                    page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(s.close)
        return s

    def visit(self, cdp, port, width, scheme="light"):
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
        cdp.call("Page.navigate", {"url": "about:blank"}, sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{port}/#settings&p=TUL"}, sid)
        self.until(cdp, sid, "document.querySelectorAll('#projects-table tbody tr').length > 0", "the projects table")
        return sid

    def until(self, cdp, sid, expr, what, secs=30):
        self.assertTrue(wait(lambda: bool(cdp.js(f"!!({expr})", sid)), secs), f"timed out waiting for {what}")

    def table(self, cdp, sid):
        return cdp.js("[...document.querySelectorAll('#projects-table tbody tr')].map(r => ({code: r.dataset.project, cells: [...r.cells].map(c => c.innerText.trim()),"
                      " buttons: [...r.querySelectorAll('button')].map(b => b.textContent)}))", sid)

    def test_the_table_lists_each_project_with_its_columns_at_1400_and_900_px_in_light_and_dark(self):
        s = self.serve()
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                    sid = self.visit(cdp, s.port, width, scheme)
                    heads = cdp.js("[...document.querySelectorAll('#projects-table thead th')].map(h => h.textContent.trim())", sid)
                    self.assertEqual(heads[:5], ["Name", "Code", "Client", "Workstreams", "Items"])
                    rows = self.table(cdp, sid)
                    self.assertEqual({r["code"] for r in rows}, set(self.names))
                    for r in rows:
                        d = self.data[r["code"]]
                        self.assertIn(self.names[r["code"]], r["cells"][0])
                        self.assertEqual(r["cells"][1], r["code"])
                        self.assertEqual(r["cells"][4], str(sum(len(d[k]) for k in ("actions", "raid", "decisions"))))
                        if r["code"] == "TUL":
                            self.assertNotIn("Archive", r["buttons"], "the open project cannot be archived from the table")
                        else:
                            self.assertIn("Archive", r["buttons"])
                    self.assertEqual(cdp.js("document.documentElement.scrollWidth <= window.innerWidth", sid), True, "no sideways page scroll")
                    self.assertIn("Open now", cdp.js("document.querySelector('tr[data-project=TUL]').innerText", sid))
                    self.assertNotIn("Open", cdp.js("[...document.querySelectorAll('tr[data-project=TUL] button')].map(b => b.textContent)", sid))
                    self.assertEqual(cdp.js("document.querySelector('#show-archived').textContent.trim()", sid), "Show archived")

    def test_archive_hides_the_project_with_undo_and_show_archived_brings_it_back_to_restore(self):
        s = self.serve()
        with chrome() as cdp:
            sid = self.visit(cdp, s.port, 1400)
            cdp.js("document.querySelector('[data-mode=edit]').click()", sid)
            cdp.js("document.querySelector('tr[data-project=MOSS] [data-archive]').click()", sid)
            self.until(cdp, sid, "!document.querySelector('tr[data-project=MOSS]')", "the project to leave the list")
            self.assertEqual(self.sent, [{"project": "MOSS", "kind": "projects", "op": "archive", "id": "MOSS"}])
            self.until(cdp, sid, "document.querySelector('.toast [data-undo]')", "Undo")
            self.assertIn("archived. Show archived brings it back.", cdp.js("document.querySelector('.toast-text').textContent", sid))
            self.assertEqual(cdp.js("document.querySelector('#show-archived').textContent.trim()", sid), "Show archived (1)")
            cdp.js("document.querySelector('.toast [data-undo]').click()", sid)
            self.until(cdp, sid, "document.querySelector('tr[data-project=MOSS]')", "Undo to put the project back")
            self.assertEqual(len(self.undone), 1)
            cdp.js("document.querySelector('tr[data-project=MOSS] [data-archive]').click()", sid)
            self.until(cdp, sid, "!document.querySelector('tr[data-project=MOSS]')", "archived again")
            cdp.js("document.querySelector('#show-archived').click()", sid)
            self.until(cdp, sid, "document.querySelector('tr[data-project=MOSS].arch')", "the archived row")
            self.assertEqual(cdp.js("document.querySelector('#show-archived').getAttribute('aria-pressed')", sid), "true")
            self.assertEqual([b for r in self.table(cdp, sid) if r["code"] == "MOSS" for b in r["buttons"]], ["Restore"])
            cdp.js("document.querySelector('tr[data-project=MOSS] [data-restore]').click()", sid)
            self.until(cdp, sid, "document.querySelector('tr[data-project=MOSS]:not(.arch)')", "the restored row")
            self.assertEqual(self.sent[-1]["op"], "restore")

    def test_the_open_project_has_no_archive_and_says_how_to_archive_it(self):
        s = self.serve()
        with chrome() as cdp:
            sid = self.visit(cdp, s.port, 1400)
            self.assertEqual(cdp.js("document.querySelectorAll('tr[data-project=TUL] [data-archive]').length", sid), 0)
            self.assertIn("Open another project to archive this one.", cdp.js("document.querySelector('tr[data-project=TUL] [data-open-note]').textContent", sid))
            cdp.js("document.querySelector('tr[data-project=MOSS] [data-open]').click()", sid)
            self.until(cdp, sid, "location.hash.includes('p=MOSS')", "the other project")
            cdp.js("location.hash = '#settings&p=MOSS'", sid)
            self.until(cdp, sid, "document.querySelector('tr[data-project=TUL] [data-archive]') && !document.querySelector('tr[data-project=MOSS] [data-archive]')", "Archive moved to the other row")
            self.assertEqual(self.sent, [])

    def test_the_heading_can_be_focused_and_the_table_is_labelled(self):
        s = self.serve()
        with chrome() as cdp:
            sid = self.visit(cdp, s.port, 1400)
            self.assertEqual(cdp.js("(() => { const h = document.querySelector('#projects-h'); h.focus(); return [h.tagName, h.tabIndex, document.activeElement === h]; })()", sid), ["H2", -1, True])
            self.assertEqual(cdp.js("document.querySelector('#projects-table').getAttribute('aria-label')", sid), "Projects")

    def test_an_archive_goes_through_the_change_queue(self):
        text = (SRC_DIR / "edit" / "Projects.jsx").read_text(encoding="utf-8")
        self.assertIn("await enqueue(", text)

    def test_open_goes_to_that_project_s_dashboard(self):
        s = self.serve()
        with chrome() as cdp:
            sid = self.visit(cdp, s.port, 1400)
            cdp.js("document.querySelector('tr[data-project=MOSS] [data-open]').click()", sid)
            self.until(cdp, sid, "location.hash.includes('p=MOSS') && location.hash.startsWith('#dashboard')", "the dashboard of the other project")


if __name__ == "__main__":
    unittest.main()
