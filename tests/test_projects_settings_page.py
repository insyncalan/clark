"""A-S6 and #444: Settings › Projects, the table of projects (Name, Code, Client, Workstreams, Items) with Open, Edit, Archive, Restore, Show archived and Add project.

Run: python3 dev/run_tests.py test_projects_settings_page
Part 1 runs the page's pure rules (src/clark/page/src/logic/projectsTable.js) in headless Chrome. Part 2 loads the committed page from the
real server (demo database, fictional data) at 1400 and 900 px, light and dark, and uses the routes that already exist: the list of
projects, one project's data, and a change of kind projects (archive and restore) with its Undo; Add project and Edit send POST /api/project
(#444). The server's change, undo and project_save are small stand-ins that record what the page sent; the store's own archive is tested in
test_changes_archive and the project route in test_project_route. A published file has no Settings. The browser parts are required: they
fail, never skip, without Chrome.
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
        self.assertEqual(self.out["live"], {"code": "ABC", "name": "Alpha", "client": "Example Client", "workstreams": "Build", "items": 6, "archived": False,
                                            "clientName": "Example Client", "wsNames": ["Build"]})

    def test_an_archived_project_lists_all_its_workstreams(self):
        self.assertEqual(self.out["gone"]["workstreams"], "Build, Old, Gone")
        self.assertTrue(self.out["gone"]["archived"])

    def test_a_project_with_nothing_read_shows_dashes_and_no_items(self):
        self.assertEqual(self.out["bare"], {"code": "XYZ", "name": "Bare", "client": "—", "workstreams": "—", "items": 0, "archived": False,
                                           "clientName": "", "wsNames": []})

    def test_show_archived_carries_a_count_only_when_there_is_one(self):
        self.assertEqual(self.out["count"], ["Show archived", "Show archived (2)"])


class Source(unittest.TestCase):
    def test_the_published_page_has_no_projects_table_and_no_way_to_archive(self):
        view = (SRC / "clark" / "page" / "page-view.html").read_text(encoding="utf-8")
        for needle in ("projects-table", "Show archived", '"kind":"projects"', "kind: \"projects\""):
            self.assertNotIn(needle, view, needle)

    def test_a_project_is_made_and_edited_only_through_the_project_route(self):       # #444
        form = (SRC_DIR / "edit" / "dataApi.js").read_text(encoding="utf-8")
        self.assertIn('"/api/project"', form)
        for name in ("Projects.jsx", "projectsApi.js", "ProjectForm.jsx"):
            text = (SRC_DIR / "edit" / name).read_text(encoding="utf-8")
            self.assertNotIn("/api/change", text, name)       # the change route is named in api.js alone
            self.assertNotIn('kind: "projects"', text, name)


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
        self.gone, self.sent, self.undone, self.saved, self.refuse = set(), [], [], [], False
        self.names, self.data = dict(type(self).names), dict(type(self).data)             # a test that adds or renames a project changes its own copy only

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

        def project_save(req):                                    # #444: what POST /api/project answers; the real one is tested in test_project_route
            self.saved.append(req)
            if self.refuse:
                return 409, {"ok": False, "code": "code_taken", "message": "That code is already in use. Choose another."}
            code, base = req["code"], self.data.get(req["code"]) or self.data["MOSS"]
            self.names[code] = req["name"]
            self.data[code] = {**base, "project": {**base["project"], "code": code, "name": req["name"], "client_name": req["client"] or None}}
            return 200, {"ok": True, "op": req["op"], "code": code, "name": req["name"], "apply_id": 50, "message": "saved"}

        s = Running(data_for=lambda code, **kw: self.data.get(code), projects=projects, change=change, undo=undo,
                    page_html=lambda: page.page_html(tempfile.mkdtemp()))
        s.httpd.project_save = project_save
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
                        self.assertIn("Archive", r["buttons"], "Archive is offered on every project, the open one too (#444)")
                        self.assertIn("Edit", r["buttons"])
                    self.assertEqual(cdp.js("document.documentElement.scrollWidth <= window.innerWidth", sid), True, "no sideways page scroll")
                    self.assertIn("Open now", cdp.js("document.querySelector('tr[data-project=TUL]').innerText", sid))
                    self.assertEqual(cdp.js("[...document.querySelectorAll('tr[data-project=TUL] button')].map(b => b.textContent)", sid), ["Edit", "Archive"], "no Open on the open project")
                    self.assertEqual(cdp.js("document.querySelector('#npBtn').getAttribute('aria-label')", sid), "Add project")
                    self.assertEqual(cdp.js("document.querySelector('#show-archived').textContent.trim()", sid), "Show archived")

    def test_archive_hides_the_project_with_undo_and_show_archived_brings_it_back_to_restore(self):
        s = self.serve()
        with chrome() as cdp:
            sid = self.visit(cdp, s.port, 1400)
            cdp.js("document.querySelector('[data-mode=edit]').click()", sid)
            cdp.js("document.querySelector('tr[data-project=MOSS] [data-archive]').click()", sid)
            self.until(cdp, sid, "!document.querySelector('tr[data-project=MOSS]')", "the project to leave the list")
            self.assertEqual(self.sent, [{"project": "MOSS", "kind": "projects", "op": "archive", "id": "MOSS"}])
            self.assertEqual(cdp.js("document.activeElement && document.activeElement.id", sid), "projects-h", "focus stays on the Projects heading after Archive")
            self.until(cdp, sid, "document.querySelector('.toast [data-undo]')", "Undo")
            self.assertIn("archived. To bring it back, choose Show archived, then Restore.", cdp.js("document.querySelector('.toast-text').textContent", sid))
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

    def test_the_open_project_can_be_archived_and_the_page_opens_the_first_other_live_project(self):       # #444, row 46
        s = self.serve()
        with chrome() as cdp:
            sid = self.visit(cdp, s.port, 1400)
            cdp.js("document.querySelector('[data-mode=edit]').click()", sid)
            cdp.js("document.querySelector('tr[data-project=TUL] [data-archive]').click()", sid)
            self.until(cdp, sid, "location.hash.includes('p=MOSS')", "the page to open the other live project")
            self.assertEqual(self.sent, [{"project": "TUL", "kind": "projects", "op": "archive", "id": "TUL"}])
            self.until(cdp, sid, "!document.querySelector('tr[data-project=TUL]')", "the archived project to leave the list")
            self.until(cdp, sid, "document.querySelector('.toast-text')", "the message")
            text = cdp.js("document.querySelector('.toast-text').textContent", sid)
            self.assertIn("archived. clark has opened", text)
            self.assertIn(self.names["MOSS"], text)
            self.assertIn("Show archived brings it back.", text)

    def test_the_only_live_project_is_not_archived_and_the_page_says_so(self):       # #444, row 46
        s = self.serve()
        self.gone.add("MOSS")
        with chrome() as cdp:
            sid = self.visit(cdp, s.port, 1400)
            cdp.js("document.querySelector('[data-mode=edit]').click()", sid)
            cdp.js("document.querySelector('tr[data-project=TUL] [data-archive]').click()", sid)
            self.until(cdp, sid, "document.querySelector('.toast.problem')", "the refusal")
            self.assertEqual(cdp.js("document.querySelector('.toast-text').textContent", sid),
                             "This is your only project, so it can't be archived. Add another project first.")
            self.assertEqual(self.sent, [])
            self.assertTrue(cdp.js("location.hash.includes('p=TUL')", sid))

    def fill(self, cdp, sid, field, value):
        cdp.js("(() => { const f = document.querySelector('%s'); f.value = %s; f.dispatchEvent(new Event('input', {bubbles: true})); })()" % (field, json.dumps(value)), sid)

    def open_form(self, cdp, sid, opener):
        cdp.js("document.querySelector('[data-mode=edit]').click()", sid)
        cdp.js("document.querySelector('%s').click()" % opener, sid)
        self.until(cdp, sid, "document.querySelector('#project-form')", "the project form")

    def test_add_project_suggests_a_code_sends_the_request_and_opens_the_new_project_on_work_items(self):       # #444, row 45
        s = self.serve()
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                    sid = self.visit(cdp, s.port, width, scheme)
                    self.saved.clear()
                    self.open_form(cdp, sid, "#npBtn")
                    self.assertEqual(cdp.js("document.querySelector('#project-form-t').textContent", sid), "New project")
                    self.assertEqual(cdp.js("document.activeElement.id", sid), "pN", "focus starts in the name")
                    self.assertEqual(cdp.js("[...document.querySelectorAll('#project-form label')].map(l => l.textContent)", sid), ["Name", "Short code", "Client", "Workstreams"])
                    self.assertEqual(cdp.js("document.querySelector('#pW').value", sid), "Delivery")
                    self.assertTrue(cdp.js("document.documentElement.scrollWidth <= window.innerWidth", sid), "no sideways page scroll")
                    self.fill(cdp, sid, "#pN", "Finance System Upgrade")
                    self.until(cdp, sid, "document.querySelector('#pC').value === 'FSU'", "the suggested code")
                    cdp.js("document.querySelector('#project-form [type=submit]').click()", sid)
                    self.until(cdp, sid, "location.hash.includes('p=FSU') && location.hash.startsWith('#work')", "the new project open on Work items")
                    self.assertEqual(self.saved, [{"op": "new", "code": "FSU", "name": "Finance System Upgrade", "client": "", "workstreams": ["Delivery"]}])
                    self.until(cdp, sid, "!document.querySelector('#project-form')", "the form to close")
                    self.names.pop("FSU", None)
                    self.data.pop("FSU", None)

    def test_edit_shows_the_projects_own_words_keeps_the_code_and_sends_the_change(self):       # #444, row 45
        s = self.serve()
        with chrome() as cdp:
            sid = self.visit(cdp, s.port, 1400)
            self.open_form(cdp, sid, "tr[data-project=MOSS] [data-edit]")
            d = self.data["MOSS"]
            self.assertEqual(cdp.js("document.querySelector('#project-form-t').textContent", sid), "Edit " + self.names["MOSS"])
            self.assertEqual(cdp.js("[document.querySelector('#pC').value, document.querySelector('#pC').disabled]", sid), ["MOSS", True])
            self.assertEqual(cdp.js("document.querySelector('#pN').value", sid), self.names["MOSS"])
            self.assertEqual(cdp.js("document.querySelector('#pW').value", sid), ", ".join(w["name"] for w in d["workstreams"] if not w.get("archived") and w.get("status") != "Closed"))
            self.fill(cdp, sid, "#pN", "Renamed Grove")
            self.fill(cdp, sid, "#pCl", "New Client")
            self.fill(cdp, sid, "#pW", "Build, Run")
            cdp.js("document.querySelector('#project-form [type=submit]').click()", sid)
            self.until(cdp, sid, "document.querySelector('tr[data-project=MOSS]').innerText.includes('Renamed Grove')", "the new name in the table")
            self.assertEqual(self.saved, [{"op": "edit", "code": "MOSS", "name": "Renamed Grove", "client": "New Client", "workstreams": ["Build", "Run"]}])
            self.assertEqual(cdp.js("document.activeElement && document.activeElement.id", sid), "projects-h")

    def test_a_refusal_is_said_in_the_box_which_stays_open_and_escape_gives_focus_back(self):       # #444
        s = self.serve()
        with chrome() as cdp:
            sid = self.visit(cdp, s.port, 1400)
            self.open_form(cdp, sid, "#npBtn")
            self.refuse = True
            self.fill(cdp, sid, "#pN", "Another One")
            self.fill(cdp, sid, "#pC", "TUL")
            cdp.js("document.querySelector('#project-form [type=submit]').click()", sid)
            self.until(cdp, sid, "document.querySelector('#project-problem').textContent", "the refusal")
            self.assertEqual(cdp.js("document.querySelector('#project-problem').textContent", sid), "That code is already in use. Choose another.")
            self.assertTrue(cdp.js("!!document.querySelector('#project-form')", sid))
            cdp.js("document.querySelector('#project-form').dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))", sid)
            self.until(cdp, sid, "!document.querySelector('#project-form')", "Esc to close the box")
            self.until(cdp, sid, "document.activeElement && document.activeElement.id === 'npBtn'", "focus back on Add project")

    def test_a_code_that_is_too_short_is_not_sent(self):       # #444: the form's own pattern; the server checks it again
        s = self.serve()
        with chrome() as cdp:
            sid = self.visit(cdp, s.port, 1400)
            self.open_form(cdp, sid, "#npBtn")
            self.fill(cdp, sid, "#pN", "Ab")
            self.fill(cdp, sid, "#pC", "AB")
            cdp.js("document.querySelector('#project-form [type=submit]').click()", sid)
            self.assertEqual(self.saved, [])
            self.assertTrue(cdp.js("!!document.querySelector('#project-form')", sid))

    def test_the_heading_can_be_focused_and_the_table_is_labelled(self):
        s = self.serve()
        with chrome() as cdp:
            sid = self.visit(cdp, s.port, 1400)
            self.assertEqual(cdp.js("(() => { const h = document.querySelector('#projects-h'); h.focus(); return [h.tagName, h.tabIndex, document.activeElement === h]; })()", sid), ["H2", -1, True])
            self.assertEqual(cdp.js("document.querySelector('#projects-table').getAttribute('aria-label')", sid), "Projects")

    def test_an_archive_goes_through_the_change_queue(self):
        text = (SRC_DIR / "edit" / "Projects.jsx").read_text(encoding="utf-8")
        self.assertIn("await enqueue(", text)
        self.assertRegex(text, r"try \{\s*await enqueue\([\s\S]*\} finally \{\s*setBusy\(\"\"\);", "the buttons come back on even when a change fails")

    def test_each_row_button_names_its_project_and_Projects_comes_before_Data(self):
        s = self.serve()
        with chrome() as cdp:
            sid = self.visit(cdp, s.port, 1400)
            self.assertEqual(cdp.js("document.querySelector('tr[data-project=MOSS] [data-archive]').getAttribute('aria-label')", sid), "Archive " + self.names["MOSS"])
            self.assertEqual(cdp.js("document.querySelector('tr[data-project=MOSS] [data-open]').getAttribute('aria-label')", sid), "Open " + self.names["MOSS"])
            self.assertEqual(cdp.js("document.querySelector('tr[data-project=MOSS] [data-edit]').getAttribute('aria-label')", sid), "Edit " + self.names["MOSS"])
            self.assertEqual(cdp.js("document.querySelector('#projects-table thead th:last-child').getAttribute('aria-label')", sid), "What you can do")
            self.assertEqual(cdp.js("document.querySelector('#projects').compareDocumentPosition(document.querySelector('#data-card')) & 4", sid), 4, "the Data card follows the Projects table")

    def test_open_goes_to_that_project_s_dashboard(self):
        s = self.serve()
        with chrome() as cdp:
            sid = self.visit(cdp, s.port, 1400)
            cdp.js("document.querySelector('tr[data-project=MOSS] [data-open]').click()", sid)
            self.until(cdp, sid, "location.hash.includes('p=MOSS') && location.hash.startsWith('#dashboard')", "the dashboard of the other project")


if __name__ == "__main__":
    unittest.main()
