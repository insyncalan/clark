"""#656: with no project open Settings still opens, with its Projects card (Add project) and its Data card (Import workbook), so a fresh
install (and the Docker start with empty data) can make its first project. The Dashboard, Work items, Milestones and Use cases still say
"No project open". Nothing new is said and nothing saved changes.

Run: python3 dev/run_tests.py test_settings_no_project
Loads the committed page from the real server with no projects at 1400 and 900 px, light and dark. The browser parts fail, never skip, without Chrome.
"""
import json
import tempfile
import unittest

from clark import page
from test_server import Running, chrome, wait
from test_work_items import FIXED_DATE, load_demo, page_target


class Browser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store, cls.folder, cls.ids = load_demo()
        cls.base = cls.store.data_for("TUL")

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        import shutil
        shutil.rmtree(str(cls.folder), ignore_errors=True)

    def serve(self):
        self.names, self.data, self.saved = {}, {}, []

        def projects(archived=False):
            return [] if archived else [{"code": c, "name": n} for c, n in sorted(self.names.items())]

        def project_save(req):
            self.saved.append(req)
            code = req["code"]
            self.names[code] = req["name"]
            self.data[code] = {**self.base, "project": {**self.base["project"], "code": code, "name": req["name"], "client_name": req["client"] or None}}
            return 200, {"ok": True, "op": req["op"], "code": code, "name": req["name"], "apply_id": 50, "message": "saved"}

        s = Running(data_for=lambda code, **kw: self.data.get(code), projects=projects, page_html=lambda: page.page_html(tempfile.mkdtemp()))
        s.httpd.project_save = project_save
        self.addCleanup(s.close)
        return s

    def until(self, cdp, sid, expr, what, secs=30):
        self.assertTrue(wait(lambda: bool(cdp.js(f"!!({expr})", sid)), secs), f"timed out waiting for {what}")

    def visit(self, cdp, port, width, scheme, hash_):
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
        cdp.call("Page.navigate", {"url": "about:blank"}, sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{port}/{hash_}"}, sid)
        return sid

    def test_settings_opens_with_no_project_and_has_add_project_and_import_workbook(self):
        s = self.serve()
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                    sid = self.visit(cdp, s.port, width, scheme, "#settings")
                    self.until(cdp, sid, "document.querySelector('#npBtn') && document.querySelector('#import-workbook')", "the Projects and Data cards")
                    self.assertEqual(cdp.js("document.querySelector('#npBtn').getAttribute('aria-label')", sid), "Add project")
                    self.assertEqual(cdp.js("document.querySelector('#import-workbook').textContent.trim()", sid), "Import workbook")
                    self.assertEqual(cdp.js("document.querySelector('h1').textContent", sid), "Settings")
                    self.assertEqual(cdp.js("document.querySelectorAll('[data-mode]').length", sid), 0, "row 826: no View | Edit on Settings")
                    self.assertNotIn("No project open", cdp.js("document.querySelector('main').innerText", sid))
                    self.assertTrue(cdp.js("document.documentElement.scrollWidth <= window.innerWidth", sid), "no sideways page scroll")
                    cdp.js("document.querySelector('[data-view=work]').click()", sid)
                    self.until(cdp, sid, "document.querySelector('main').innerText.includes('No project open')", "the Gate on Work items")
                    cdp.js("document.querySelector('[data-view=settings]').click()", sid)
                    self.until(cdp, sid, "document.querySelector('#npBtn')", "Settings again from its tab")

    def test_item_682_only_the_cards_that_work_show_and_import_says_why(self):
        s = self.serve()
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.visit(cdp, s.port, width, "light", "#settings")
                self.until(cdp, sid, "document.querySelector('#npBtn') && document.querySelector('#import-workbook')", "the cards")
                for gone in ("client-folder-h", "review-days-h"):
                    self.assertFalse(cdp.js(f"!!document.getElementById('{gone}')", sid), gone)
                text = cdp.js("document.querySelector('main').innerText", sid)
                for word in ("Publishing", "Choose folder", "Published reports", "Freshness"):
                    self.assertNotIn(word, text)
                chips = cdp.js("[...document.querySelectorAll('.set-chip')].map(c => c.textContent).join('|')", sid)
                self.assertNotIn("Publishing", chips)
                self.assertNotIn("Freshness", chips)
                for kept in ("personal-h", "data-card-h", "safety-h", "diagnostics-h"):
                    self.assertTrue(cdp.js(f"!!document.getElementById('{kept}')", sid), kept)
                self.assertTrue(cdp.js("document.querySelector('#import-workbook').disabled", sid))
                self.assertEqual(cdp.js("document.getElementById('import-why').textContent", sid), "Add a project first.")  # logic/dataCard.js IMPORT_NEEDS_PROJECT
                self.assertEqual(cdp.js("document.querySelector('#import-workbook').getAttribute('aria-describedby')", sid), "import-why")
                self.assertTrue(cdp.js("document.querySelector('#export-workbook').disabled", sid))
                self.assertEqual(cdp.js("document.getElementById('export-why').textContent", sid), "Add a project first.")
                self.assertEqual(cdp.js("document.querySelector('#export-workbook').getAttribute('aria-describedby')", sid), "export-why")
                self.assertTrue(cdp.js("document.documentElement.scrollWidth <= window.innerWidth", sid), "no sideways page scroll")

    # ---- item 701: the same no-project Settings, checked in both themes at 900 and 1400 px ------------------------------------------------
    # the card names the task uses, and the heading each one wears on the page
    WORKING = {"Personal": "Personal", "Projects": "Projects", "People": "People", "Data": "Data", "Safety": "Backups", "Update": "Version and updates", "Diagnostics": "Logs and diagnostics", "AI": "AI"}
    PROBE = """(() => {
        const rgb = (c) => { const m = c.match(/[\\d.]+/g).map(Number); return {r: m[0], g: m[1], b: m[2], a: m.length > 3 ? m[3] : 1}; };
        const over = (t, b) => ({r: t.r * t.a + b.r * (1 - t.a), g: t.g * t.a + b.g * (1 - t.a), b: t.b * t.a + b.b * (1 - t.a), a: 1});
        const bg = (el) => { const dark = matchMedia('(prefers-color-scheme: dark)').matches; let c = dark ? {r: 0, g: 0, b: 0, a: 1} : {r: 255, g: 255, b: 255, a: 1}; const l = []; for (let e = el; e; e = e.parentElement) l.push(rgb(getComputedStyle(e).backgroundColor)); for (const x of l.reverse()) c = over(x, c); return c; };
        const hex = (c) => '#' + [c.r, c.g, c.b].map(v => Math.round(v).toString(16).padStart(2, '0')).join('');
        const out = {};
        for (const id of ['import-why', 'export-why']) {
            const el = document.getElementById(id); if (!el) { out[id] = null; continue; }
            const fg = over(rgb(getComputedStyle(el).color), bg(el));
            const r = el.getBoundingClientRect();
            out[id] = {text: el.textContent, fg: hex(fg), bg: hex(bg(el)), visible: r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== 'hidden'};
        }
        return JSON.stringify(out);
    })()"""

    def test_item_701_no_project_settings_in_light_and_dark_at_900_and_1400(self):
        from test_dark_contrast import ratio
        s = self.serve()
        for width in (900, 1400):
            for scheme in ("light", "dark"):
                with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                    sid = self.visit(cdp, s.port, width, scheme, "#settings")
                    self.until(cdp, sid, "document.querySelector('#npBtn') && document.querySelector('#import-workbook') && document.querySelector('#import-why')", "the cards")
                    heads = json.loads(cdp.js("JSON.stringify([...document.querySelectorAll('main h2, main h3')].map(h => h.textContent.trim()))", sid))
                    for card, head in self.WORKING.items():
                        self.assertTrue(head in heads, f"{card} card missing from {heads}")
                    for gone in ("Publishing", "Published reports", "Freshness"):
                        self.assertFalse(any(gone in h for h in heads), f"{gone} card still shown: {heads}")
                    chips = json.loads(cdp.js("JSON.stringify([...document.querySelectorAll('.set-chip')].map(c => c.textContent.trim()))", sid))
                    self.assertTrue(chips, "the section chips show")
                    for gone in ("Publishing", "Published reports", "Freshness"):
                        self.assertFalse(any(gone in c for c in chips), f"{gone} chip still shown: {chips}")
                    probe = json.loads(cdp.js(self.PROBE, sid))
                    for which in ("import", "export"):
                        why = probe[which + "-why"]
                        self.assertIsNotNone(why, which + "-why missing")
                        self.assertEqual(why["text"], "Add a project first.")
                        self.assertTrue(why["visible"], which + "-why not visible")
                        self.assertEqual(cdp.js("(() => { const b = document.getElementById('%s-workbook'); const d = document.getElementById(b.getAttribute('aria-describedby')); return !!d && d.id === '%s-why' && d.textContent === 'Add a project first.' && d.getBoundingClientRect().height > 0; })()" % (which, which), sid), True)
                        self.assertGreaterEqual(ratio(why["fg"], why["bg"]), 4.5, f"{which}-why text {why['fg']} on {why['bg']} in {scheme}")
                    self.assertTrue(cdp.js("document.documentElement.scrollWidth <= window.innerWidth", sid), "no sideways page scroll")
                    self.assertTrue(cdp.js("document.body.scrollWidth <= window.innerWidth", sid), "no sideways body scroll")

    def test_the_other_four_screens_still_say_no_project_open(self):
        s = self.serve()
        for view in ("dashboard", "work", "milestones", "usecases"):
            with self.subTest(view=view), chrome() as cdp:
                sid = self.visit(cdp, s.port, 1400, "light", "#" + view)
                self.until(cdp, sid, "document.querySelector('main').innerText.includes('There are no projects yet.')", "the Gate")
                self.assertIn("No project open", cdp.js("document.querySelector('main').innerText", sid))
                self.assertFalse(cdp.js("!!document.querySelector('#npBtn')", sid))

    def test_add_project_with_none_makes_it_and_opens_it_on_work_items(self):
        s = self.serve()
        with chrome() as cdp:
            sid = self.visit(cdp, s.port, 1400, "light", "#settings")
            self.until(cdp, sid, "document.querySelector('#npBtn')", "Add project")
            cdp.js("document.querySelector('#npBtn').click()", sid)
            self.until(cdp, sid, "document.querySelector('#project-form')", "the project form")
            cdp.js("(() => { const f = document.querySelector('#pN'); f.value = %s; f.dispatchEvent(new Event('input', {bubbles: true})); })()" % json.dumps("Finance System Upgrade"), sid)
            self.until(cdp, sid, "document.querySelector('#pC').value === 'FSU'", "the suggested code")
            cdp.js("document.querySelector('#project-form [type=submit]').click()", sid)
            self.until(cdp, sid, "location.hash.includes('p=FSU') && location.hash.startsWith('#work')", "the new project open on Work items")
            self.until(cdp, sid, "document.querySelectorAll('#work tbody tr[data-id]').length > 0", "its work items")
            self.assertEqual(self.saved, [{"op": "new", "code": "FSU", "name": "Finance System Upgrade", "client": "", "workstreams": ["Delivery"]}])


if __name__ == "__main__":
    unittest.main()
