"""Row 1306 slice C3: the Connectors block in Settings, in a real browser (desktop widths 1400 and 900).

Run: python3 dev/run_tests.py test_ask_settings_connectors
The page calls /api/ask-connectors (GET list, POST {id, on} or {project, id, off_here}); the server side is another slice, so these tests put in
the answers a server with the route would give by replacing the page's fetch for that one address. Chrome is required: fails, never skips.
"""
import tempfile
import unittest

from _editor_checks import for_project
from _paths import SRC  # noqa: F401
from test_ask_settings import make_db, service
from test_page import DATA, navigate
from test_server import Running, chrome, wait

from clark import page

ALL_NOTE = ("Mail, Teams, calendars and SharePoint are used only if you turn that connector on in Settings. Only connectors that are set up on this computer are listed, and the list is the same for every project. Off means clark never asks it anything. "
            "On lets ask clark read from it, read only, when your question needs it; each one it used is listed under the answer. A project can turn a connector off for itself in its own tab.")
WIDTHS = (1400, 900)
FAKE = """
window.__c = {calls: [], list: [{id: 'mail', label: 'Mail', on: false, off_here: false}, {id: 'teams', label: 'Teams', on: false, off_here: false}, {id: 'todoist', label: 'Todoist', on: true, off_here: false}], fail: false, none: false, steps: [], urls: []};
const real = window.fetch;
window.fetch = function (url, opts) {
  if (String(url).indexOf('/api/ask-connectors') < 0) return real.apply(this, arguments);
  const body = opts && opts.body ? JSON.parse(opts.body) : null;
  window.__c.calls.push(body); window.__c.urls.push(String(url));
  const reply = (status, out) => Promise.resolve(new Response(JSON.stringify(out), {status: status, headers: {'Content-Type': 'application/json'}}));
  if (window.__c.fail) return reply(500, null);
  if (body && body.undo !== undefined) { const u = window.__c.steps.pop(); if (u) window.__c.list.forEach((c) => { if (c.id === u.id) { c.on = u.on; c.off_here = u.off_here; } }); return reply(200, {ok: true, connectors: window.__c.list, message: 'Undone.'}); }
  if (!body) return reply(200, {ok: true, connectors: window.__c.none ? [] : window.__c.list});
  const keep = window.__c.list.map((c) => Object.assign({}, c));
  if (body && body.on !== undefined) window.__c.list.forEach((c) => { if (c.id === body.id) c.on = body.on; });
  if (body && body.off_here !== undefined) window.__c.list.forEach((c) => { if (c.id === body.id) c.off_here = body.off_here; });
  window.__c.steps.push(keep.filter((c) => c.id === body.id)[0]);
  return reply(200, {ok: true, connectors: window.__c.none ? [] : window.__c.list, message: 'SERVER LINE', apply_id: 'step-' + window.__c.steps.length});
};
"""


class Connectors(unittest.TestCase):
    def setUp(self):
        self.s = Running(data_for=lambda code, archived=None: DATA.get(code), page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(self.s.close)
        self.s.httpd.app_settings = service(make_db(tempfile.mkdtemp(), cleanup=self.addCleanup))

    def show(self, cdp, tab, setup=""):
        sid = navigate(cdp, self.s.port, for_project("#settings&p=ABC&s=claude"))
        self.sid = sid
        js = lambda e: cdp.js(e, sid)          # noqa: E731
        js(FAKE + setup)
        js("location.hash = '#dashboard&p=ABC'")
        wait(lambda: js("!document.querySelector('#ask-settings')"), 10)
        js("location.hash = '#settings&p=ABC&s=claude'")
        self.assertTrue(wait(lambda: js("!!document.querySelector('#ask-settings')"), 20))
        if tab == "all":
            js("document.querySelector('[data-ask-tab=all]').click()")
        return js

    def test_all_projects_lists_only_found_connectors_off_by_default_with_the_row_wording_and_switches_them(self):
        with chrome() as cdp:
            js = self.show(cdp, "all")
            self.assertTrue(wait(lambda: js("document.querySelectorAll('[data-connector]').length") == 2, 10))
            self.assertFalse(js("!!document.querySelector('#ask-connectors-line')"), "the extra row sentence is gone: the footnote says it")
            self.assertEqual(js("window.__c.urls.filter((u) => u.indexOf('/api/ask-connectors') >= 0).slice(-1)[0]"), "/api/ask-connectors", "the All tab sends no project (the project tab's earlier read is the one with it)")
            self.assertIn("/api/ask-connectors", js("window.__c.urls.join()"))
            self.assertEqual(js("document.querySelector('#ask-connectors h2').innerText"), "Other connectors found on this computer")
            self.assertEqual(js("document.querySelector('#ask-connectors-note-all').innerText"), ALL_NOTE)
            self.assertEqual(js("document.querySelector('#ask-connectors-readonly').innerText"), "A connector is only read from, never changed.")
            self.assertEqual(js("[...document.querySelectorAll('[data-connector]')].map(b => b.closest('li').querySelector('.muted').innerText + '/' + b.getAttribute('aria-checked') + '/' + b.getAttribute('aria-label') + '/' + b.getAttribute('role')).join()"),
                             "Off for clark/false/Allow clark to use Mail/switch,Off for clark/false/Allow clark to use Teams/switch")
            for w in WIDTHS:
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                self.assertTrue(wait(lambda: js("document.documentElement.scrollWidth <= window.innerWidth"), 10), f"no sideways scroll at {w}")
            js("document.querySelector('[data-connector=mail]').click()")
            state = lambda i: js("document.querySelector('[data-connector=" + i + "]').closest('li').querySelector('.muted').innerText")          # noqa: E731
            self.assertTrue(wait(lambda: state("mail") == "On for clark", 10))
            self.assertEqual(js("window.__c.calls.slice(-1)[0].on"), True)
            self.assertEqual(state("teams"), "Off for clark")
            said = "document.querySelector('[data-connector-said]')"
            self.assertEqual(js(said + ".innerText"), "Mail turned on for clark. Undo", "the mock-up's own line, not the server's")
            js("document.querySelector('[data-connector-undo]').click()")
            self.assertTrue(wait(lambda: state("mail") == "Off for clark", 10))
            self.assertEqual(js("window.__c.calls.slice(-1)[0].undo"), "step-1")
            self.assertFalse(js("!!document.querySelector('[data-connector-said]')"), "the line goes with the Undo")
            js("document.querySelector('[data-connector=mail]').click()")
            js("document.querySelector('[data-connector=mail]').click()")
            self.assertTrue(wait(lambda: js(said + " && " + said + ".innerText") == "Mail turned off for clark. It is never asked anything. Undo", 10))

    def test_a_project_tab_shows_only_connectors_on_for_all_and_turns_one_off_for_that_project(self):
        with chrome() as cdp:
            js = self.show(cdp, "project", "window.__c.list[0].on = true;")
            self.assertTrue(wait(lambda: js("!!document.querySelector('[data-connector-here]')"), 10))
            self.assertEqual(js("document.querySelectorAll('[data-connector-here]').length"), 1, "Teams is off for all, so it is not offered")
            self.assertIn("/api/ask-connectors?project=ABC", js("window.__c.urls.join()"), "a project's tab asks with its project")
            self.assertEqual(js("document.querySelector('#ask-connectors-project h2').innerText"), "Connectors in ABC")
            self.assertEqual(js("document.querySelector('#ask-connectors-note-project').innerText"), "Only the connectors that are On for all projects appear here.")
            self.assertEqual(js("document.querySelector('#ask-connectors-project li .muted').innerText"), "On for all projects. Turn it off here for ABC only.")
            sw = "document.querySelector('[data-connector-here=mail]')"
            self.assertEqual(js(sw + ".getAttribute('role') + '/' + " + sw + ".getAttribute('aria-label') + '/' + " + sw + ".getAttribute('aria-checked')"), "switch/Use Mail in ABC/true")
            js(sw + ".click()")
            self.assertTrue(wait(lambda: js(sw + ".getAttribute('aria-checked')") == "false", 10))
            self.assertEqual(js("document.querySelector('[data-connector-said]').innerText"), "Mail turned off for ABC only. Undo")
            self.assertEqual(js("window.__c.calls.slice(-1)[0].project"), "ABC")
            self.assertEqual(js("window.__c.calls.slice(-1)[0].off_here"), True)

    def test_the_todoist_switch_is_never_drawn_even_when_the_server_lists_it_as_on(self):
        with chrome() as cdp:
            js = self.show(cdp, "all")
            self.assertTrue(wait(lambda: js("document.querySelectorAll('[data-connector]').length") == 2, 10))
            self.assertEqual(js("document.querySelector('#ask-connectors').innerText.indexOf('Todoist')"), -1)
            self.assertFalse(js("!!document.querySelector('[data-connector=todoist]')"))
        with chrome() as cdp:
            js = self.show(cdp, "project", "window.__c.list.forEach((c) => { c.on = true; });")
            self.assertTrue(wait(lambda: js("document.querySelectorAll('[data-connector-here]').length") == 2, 10))
            self.assertFalse(js("!!document.querySelector('[data-connector-here=todoist]')"))

    def test_none_found_says_so_and_an_unreachable_server_offers_no_switch(self):
        with chrome() as cdp:
            js = self.show(cdp, "all", "window.__c.none = true;")
            self.assertTrue(wait(lambda: js("!!document.querySelector('#ask-connectors-none')"), 10))
            self.assertEqual(js("document.querySelectorAll('[data-connector]').length"), 0)
        with chrome() as cdp:
            js = self.show(cdp, "all", "window.__c.fail = true;")
            self.assertTrue(wait(lambda: js("!!document.querySelector('#ask-connectors-unavailable')"), 10))
            self.assertEqual(js("document.querySelectorAll('[data-connector]').length"), 0)
            self.assertFalse(js("!!document.querySelector('#ask-connectors-none')"), "an unreachable server is not 'none found'")
            self.assertEqual(js("document.querySelector('#ask-connectors-unavailable').innerText"), "Connectors can't be checked just now. None is used until they can be.")

    def test_a_refused_change_leaves_the_switch_off_and_says_so(self):
        with chrome() as cdp:
            js = self.show(cdp, "all")
            self.assertTrue(wait(lambda: js("!!document.querySelector('[data-connector=mail]')"), 10))
            js("window.__c.fail = true; document.querySelector('[data-connector=mail]').click()")
            self.assertTrue(wait(lambda: js("!!document.querySelector('#ask-connectors .pub-msg .error')"), 10))
            self.assertEqual(js("document.querySelector('[data-connector=mail]').closest('li').querySelector('.muted').innerText"), "Off for clark")


if __name__ == "__main__":
    unittest.main()
