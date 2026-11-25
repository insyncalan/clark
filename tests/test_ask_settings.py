"""#47: the Settings entry for asking, in a real browser against the real server (desktop widths 1400 and 900 only).

Run: python3 dev/run_tests.py test_ask_settings
The switch is kept by the server for this computer (/api/ask-enabled, app_settings.ask_enabled), on by default, and the browser's
storage plays no part; until the server has answered, or when it cannot, asking reads as off, and a data file that cannot keep the
switch reads as off too. The folder choice calls
/api/ask-folders, which the server does not have in these tests (it answers 404, and the page says so in plain words); the answers a
server with the route would give are put in by replacing the page's fetch for that one address. Chrome is required: fails, never skips.
"""
import os
import json
import re
import shutil
import sqlite3
import tempfile
import unittest
from _editor_checks import for_project
from pathlib import Path
from unittest import mock

from _paths import SRC
from _new_page import reload_to_new_page
from test_page import DATA, navigate
from test_server import Running, chrome, wait

from clark import app_settings, page, store as st

PAGE_SRC = Path(page.PAGE).parent / "src"
WIDTHS = (1400, 900)
ON = "Asking is on."
OFF = "Asking is off. Turn it on in Settings."
CHECKING = "Checking whether asking is on…"
UNAVAILABLE = "Asking is off, because clark could not check the setting just now. Reload the page to try again."
NOT_KEPT = "This computer's saved data can't keep this choice yet, so asking stays off. Restart clark to bring the saved data up to date."
NOT_READY = "Choosing folders isn't ready on this computer yet. Asking uses only this project's data until it is."
NONE = "No folders are set. Asking uses only this project's data."
FAKE = """
window.__ask = {folders: [], calls: []};
const real = window.fetch;
window.fetch = function (url, opts) {
  if (window.__ask.provider && String(url).indexOf('/api/providers') >= 0 && String(url).indexOf('connect') < 0) { window.__ask.providerRead = true; return Promise.resolve(new Response(JSON.stringify({ok: true, claude: {}, chatgpt: {}, models: [], active: window.__ask.provider}), {status: 200, headers: {'Content-Type': 'application/json'}})); }
  if (String(url).indexOf('/api/ask-folders') < 0) return real.apply(this, arguments);
  const body = opts && opts.body ? JSON.parse(opts.body) : null;
  window.__ask.calls.push(body);
  const f = window.__ask.folders;
  let status = 200, out = {ok: true, folders: f, warnings: window.__ask.open || []};
  if (body && body.action === 'choose') {
    window.__ask.choices = window.__ask.choices || ['/Example/Programme files'];
    const next = window.__ask.choices.shift();
    if (next === '/bad') { status = 409; out = {ok: false, code: 'closed_place', message: 'Asking can not read that folder, because it holds your passwords.'}; }
    else if (next === '/nowin') { status = 409; out = {ok: false, code: 'no_window', message: 'The folder window needs the Mac. Type the folder location below.'}; }
    else if (next === '/cancel') { out = {ok: true, folders: f}; }
    else if (next === '/gone') { status = 500; out = null; }
    else { if (f.indexOf(next) < 0) f.push(next); out = {ok: true, folders: f, message: 'Added.', warnings: window.__ask.warn || []}; }
  } else if (body && body.action === 'add') {
    if (body.path === '/bad') { status = 409; out = {ok: false, code: 'client_folder_refused', message: 'That folder holds your passwords, so asking cannot read it.'}; }
    else { f.push(body.path); out = {ok: true, folders: f, message: 'Folder added.', warnings: window.__ask.warn || []}; }
  } else if (body && (body.action === 'accept' || body.action === 'decline')) {
    const list = (window.__ask.open || []).length ? window.__ask.open : (window.__ask.warn || []);
    list.forEach(w => { if (w.folder === body.path) w.accepted = body.action === 'accept'; });
    out = {ok: true, folders: f, apply_id: 8, warnings: list};
  } else if (body && body.action === 'exclude') { window.__ask.open = []; window.__ask.warn = []; out = {ok: true, folders: f, apply_id: 7, warnings: window.__ask.excludeKeep || []};
  } else if (body && body.action === 'remove' && window.__ask.removeFail) { status = 500; out = null;
  } else if (body && body.action === 'remove') { window.__ask.folders = f.filter(x => x !== body.path); out = {ok: true, folders: window.__ask.folders}; }
  return Promise.resolve(new Response(JSON.stringify(out), {status: status, headers: {'Content-Type': 'application/json'}}));
};
"""


def make_db(folder, ready=True, cleanup=None):
    """clark.db in `folder` with project ABC. `ready=False` makes it as the version before the settings step left it (no
    app_settings, version 5) and holds this clark at version 5 until `cleanup` runs, so opening it does not migrate it."""
    db = Path(folder) / "clark.db"
    store = st.open_store(db, onedrive_roots=[])
    with store.step("dashboard", "tester", place="menu") as s:
        s.create("projects", {"code": "ABC", "name": "Example Programme"})
    store.close()
    if not ready:
        con = sqlite3.connect(str(db), isolation_level=None)
        con.execute("DROP TABLE app_settings")
        con.execute("UPDATE meta SET v = '5' WHERE k = 'schema_version'")
        con.close()
        for patcher in (mock.patch.object(st, "SCHEMA_VERSION", 5), mock.patch.object(st, "MIGRATIONS", st.MIGRATIONS[:4])):
            patcher.start()
            cleanup(patcher.stop)
    return db


def service(db):
    return app_settings.AppSettings(db, [], by_user=lambda: "tester")


def read(db):
    """(ask_enabled,) read straight from the file."""
    store = st.open_store(db, onedrive_roots=[])
    try:
        return (store.ask_enabled(),)
    finally:
        store.close()


class Settings(unittest.TestCase):
    ready = True

    def setUp(self):
        self.s = Running(data_for=lambda code, archived=None: DATA.get(code), page_html=lambda: page.page_html(tempfile.mkdtemp(), theme=self.theme()))
        self.addCleanup(self.s.close)
        self.db = make_db(self.folder(), ready=self.ready, cleanup=self.addCleanup)
        self.s.httpd.app_settings = service(self.db)

    def theme(self):
        """Row 1365: the amber notice is a Classic rule (themes/prototype-2.0/rules-2.css), so its test layers the Classic theme; the rest stay as they were."""
        name = self._testMethodName
        return "prototype-2.0" if any(k in name for k in ("amber", "accept", "decline", "provider", "saved_notice", "leave_these", "leave_out")) else None

    def folder(self):
        d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, d, True)
        return d

    def show_page(self, cdp, fake=False):
        sid = navigate(cdp, self.s.port, for_project("#settings&p=ABC&s=claude"))
        self.sid = sid
        js = lambda e: cdp.js(e, sid)          # noqa: E731
        if fake:
            js(FAKE)
            js("location.hash = '#dashboard&p=ABC'")
            self.assertTrue(wait(lambda: js("!document.querySelector('#ask-settings')"), 10), "the dashboard drew")
            js("location.hash = '#settings&p=ABC&s=claude'")
        self.assertTrue(wait(lambda: js("!!document.querySelector('#ask-settings')"), 20), "the Asking entry is in Settings")
        if fake:
            self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ask-choose]')"), 20), "the folders part has its answer")
            self.assertTrue(wait(lambda: js("window.__ask.calls.length >= 1"), 20), "the page has read the folders through the fake")
        return js

    def until(self, read_value, expected, what, seconds=20):
        """The bounded wait the other browser tests use (test_server.wait), with the last value seen in the failure: a single read
        straight after a click or a reload can come before the page, or the file, has caught up under load."""
        seen = []

        def check():
            seen[:] = [read_value()]
            return seen[0] == expected
        self.assertTrue(wait(check, seconds), f"{what}: wanted {expected!r}, last seen {seen[0] if seen else 'nothing'!r}")

    def test_the_switch_is_on_by_default_changes_what_the_server_keeps_and_survives_a_reload(self):
        with chrome() as cdp:
            js = self.show_page(cdp)
            for w in WIDTHS:
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                self.until(lambda: js("document.documentElement.scrollWidth <= window.innerWidth"), True, f"no sideways scroll at {w}")
                self.until(lambda: js("var r=document.querySelector('[data-ask-switch]').getBoundingClientRect(); r.width > 0 && r.right <= window.innerWidth"),
                           True, f"the switch is inside the page at {w}")
            ready = "(document.querySelector('[data-ask-switch]') || {disabled: true}).disabled === false"
            state = "(document.querySelector('#ask-state') || {}).innerText"
            self.until(lambda: js(state), ON, "asking is on by default")
            self.until(lambda: js(ready), True, "the switch can be pressed")
            self.assertEqual(js("localStorage.getItem('clark.askEnabled')"), None)
            js("document.querySelector('[data-ask-switch]').click()")
            self.until(lambda: js(state), OFF, "asking is off after the press")
            self.until(lambda: js("(document.querySelector('[data-ask-switch]') || {}).innerText"), "Turn on asking", "the switch offers to turn it on")
            self.until(lambda: read(self.db)[0], False, "the database holds it, for this computer")
            self.assertEqual(js("localStorage.getItem('clark.askEnabled')"), None, "nothing is kept in the browser")
            js("localStorage.clear()")
            reload_to_new_page(js, seconds=20)      # the old page still shows OFF until it goes
            self.until(lambda: js(state), OFF, "off after a reload")
            self.until(lambda: js(ready), True, "the switch can be pressed after a reload")
            js("document.querySelector('[data-ask-switch]').click()")
            self.until(lambda: js(state), ON, "asking is on after the second press")
            self.until(lambda: read(self.db)[0], True, "the database holds it again")

    def test_a_choice_left_in_the_browsers_storage_by_an_earlier_build_is_ignored(self):
        with chrome() as cdp:
            sid = navigate(cdp, self.s.port, for_project("#settings&p=ABC&s=claude"))
            js = lambda e: cdp.js(e, sid)          # noqa: E731
            js("localStorage.setItem('clark.askEnabled', 'off')")
            reload_to_new_page(js, seconds=20)
            self.until(lambda: js("(document.querySelector('#ask-state') || {}).innerText"), ON, "the database says on, so the page says on")
            self.assertEqual(read(self.db)[0], True)

    def test_asking_reads_as_off_when_the_server_cannot_say(self):
        self.s.httpd.app_settings = None                      # a server with no settings route: 404
        with chrome() as cdp:
            js = self.show_page(cdp)
            self.assertTrue(wait(lambda: js("document.querySelector('#ask-state').innerText") == UNAVAILABLE, 10))
            self.assertEqual(js("document.querySelector('[data-ask-switch]').disabled"), True, "nothing to press when it cannot be kept")
            self.assertEqual(js("document.querySelector('[data-ask-switch]').getAttribute('aria-pressed')"), "false")

    def test_a_slow_server_leaves_the_switch_unpressable_until_it_answers(self):
        with chrome() as cdp:
            sid = navigate(cdp, self.s.port, for_project("#dashboard&p=ABC"))
            js = lambda e: cdp.js(e, sid)          # noqa: E731
            self.assertTrue(wait(lambda: js("!!document.querySelector('#report')"), 20))
            js("""window.__pending = []; window.__held = () => window.__pending.splice(0).forEach((f) => f()); const real = window.fetch;
                  window.fetch = function (url) { if (String(url).indexOf('/api/ask-enabled') >= 0) { const a = arguments; return new Promise((r) => { window.__pending.push(() => r(real.apply(window, a))); }); }
                                                  return real.apply(this, arguments); };
                  location.hash = '#settings&p=ABC&s=claude'""")
            self.assertTrue(wait(lambda: js("(document.querySelector('#ask-state') || {}).innerText") == CHECKING, 10))
            self.assertEqual(js("document.querySelector('[data-ask-switch]').disabled"), True)
            # Release whatever the page has asked so far on every poll, until the answer is on screen (it asks after it draws the words).
            self.assertTrue(wait(lambda: js("window.__held(), document.querySelector('#ask-state').innerText") == ON, 20))
            self.assertEqual(js("document.querySelector('[data-ask-switch]').disabled"), False)

    def test_two_overlapping_reads_answered_in_reverse_order_leave_the_newer_answer_on_screen(self):
        # Settings asks again each time it opens. Open it twice quickly, then let the SECOND ask answer first (on) and the FIRST last (off):
        # the older answer must not overwrite the newer one (askState.js numbers its requests).
        with chrome() as cdp:
            sid = navigate(cdp, self.s.port, for_project("#dashboard&p=ABC"))
            js = lambda e: cdp.js(e, sid)          # noqa: E731
            self.assertTrue(wait(lambda: js("!!document.querySelector('#report')"), 20))
            js("""window.__q = []; const real = window.fetch;
                  window.answer = (i, on) => window.__q[i](new Response(JSON.stringify({ok: true, ask_enabled: on, saved: true}), {status: 200, headers: {'Content-Type': 'application/json'}}));
                  window.fetch = function (url) { if (String(url).indexOf('/api/ask-enabled') >= 0) return new Promise((r) => { window.__q.push(r); });
                                                  return real.apply(this, arguments); };
                  location.hash = '#settings&p=ABC&s=claude'""")
            self.assertTrue(wait(lambda: js("window.__q.length") == 1, 10), "the first ask is out")
            js("location.hash = '#dashboard&p=ABC'")
            self.assertTrue(wait(lambda: js("!document.querySelector('#ask-settings')"), 10))
            js("location.hash = '#settings&p=ABC&s=claude'")
            self.assertTrue(wait(lambda: js("window.__q.length") == 2, 10), "the second ask is out")
            js("window.answer(1, true)")                                  # the newer ask answers first: on
            self.assertTrue(wait(lambda: js("(document.querySelector('#ask-state') || {}).innerText") == ON, 10), "the newer answer shows")
            js("window.answer(0, false)")                                 # the older ask answers last: off, and is ignored
            import time
            time.sleep(1)
            self.assertEqual(js("document.querySelector('#ask-state').innerText"), ON, "the older answer did not overwrite it")
            self.assertEqual(js("document.querySelector('[data-ask-switch]').getAttribute('aria-pressed')"), "true")

    def test_a_change_answered_after_a_newer_read_was_started_does_not_touch_the_switch(self):
        # Press "Turn off asking" (a change, held), then open Settings again (a newer read, held). The newer read answers first (on); the
        # change answers last. askState.js numbers its requests, so the late change answer must leave the page as the newer read set it:
        # on. Both kinds of late answer are tried: the change kept (off) and the change refused (setAsk's "off anyway" branch). Without
        # the `stale` check in setAsk, either one would turn the page off.
        import json
        import time
        answers = ((200, {"ok": True, "ask_enabled": False, "saved": True}), (500, {"ok": False}))
        with chrome() as cdp:
            js = self.show_page(cdp)
            self.until(lambda: js("(document.querySelector('#ask-state') || {}).innerText"), ON, "asking is on to begin with")
            js("""window.__q = []; const real = window.fetch;
                  window.answer = (i, status, body) => window.__q[i](new Response(JSON.stringify(body), {status: status, headers: {'Content-Type': 'application/json'}}));
                  window.fetch = function (url) { if (String(url).indexOf('/api/ask-enabled') >= 0) return new Promise((r) => { window.__q.push(r); });
                                                  return real.apply(this, arguments); };""")
            for status, body in answers:
                with self.subTest(late=status):
                    self.until(lambda: js("(document.querySelector('[data-ask-switch]') || {disabled: true}).disabled"), False, "the switch can be pressed")
                    first = js("window.__q.length")
                    js("document.querySelector('[data-ask-switch]').click()")
                    self.until(lambda: js("window.__q.length"), first + 1, "the change is out")
                    js("location.hash = '#dashboard&p=ABC'")
                    self.assertTrue(wait(lambda: js("!document.querySelector('#ask-settings')"), 10))
                    js("location.hash = '#settings&p=ABC&s=claude'")
                    self.until(lambda: js("window.__q.length"), first + 2, "the newer read is out")
                    js(f"window.answer({first + 1}, 200, {{ok: true, ask_enabled: true, saved: true}})")      # the newer read answers first: on
                    self.until(lambda: js("(document.querySelector('#ask-state') || {}).innerText"), ON, "the newer answer shows")
                    js(f"window.answer({first}, {status}, {json.dumps(body)})")                              # the older change answers last
                    time.sleep(1)
                    self.assertEqual(js("document.querySelector('#ask-state').innerText"), ON, "the late change answer did not touch the page")
                    self.assertEqual(js("document.querySelector('[data-ask-switch]').getAttribute('aria-pressed')"), "true")

    def test_the_switch_says_its_state_in_a_toast_with_one_undo_and_keeps_the_focus(self):
        """Row 849: each press says 'ask clark is off' / 'ask clark is on' with one Undo that puts it back, and the focus is on the switch
        again once the request has answered (it is disabled while it runs). 1400 and 900, light and dark."""
        text = "(document.querySelector('.toast .toast-text') || {}).textContent"
        sw = "document.querySelector('[data-ask-switch]')"
        with chrome() as cdp:
            js = self.show_page(cdp)
            ready = f"({sw} || {{disabled: true}}).disabled === false"
            for scheme in ("light", "dark"):
                cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, self.sid)
                for w in WIDTHS:
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                    where = f"{scheme} {w}"
                    self.until(lambda: js(ready), True, f"{where}: the switch can be pressed")
                    was = js(f"{sw}.getAttribute('aria-pressed')")
                    word = "off" if was == "true" else "on"
                    other = "on" if word == "off" else "off"
                    js(f"{sw}.focus(); {sw}.click()")
                    self.until(lambda: js(text), f"ask clark is {word}", f"{where}: the toast says {word}")
                    self.until(lambda: js(f"document.activeElement === {sw}"), True, f"{where}: focus is back on the switch")
                    self.assertEqual(js("document.querySelectorAll('.toast [data-undo]').length"), 1, f"{where}: one Undo")
                    js("document.querySelector('.toast [data-undo]').click()")
                    self.until(lambda: js(text), f"ask clark is {other}", f"{where}: Undo puts it back and says so")
                    self.until(lambda: js(f"{sw}.getAttribute('aria-pressed')"), was, f"{where}: the switch is as it was")
                    self.until(lambda: read(self.db)[0], was == "true", f"{where}: the database holds it")
                    self.assertEqual(js("document.querySelectorAll('.toast [data-undo]').length"), 0, f"{where}: no Undo of an Undo")
                    self.until(lambda: js(ready), True, f"{where}: ready again")
            js("location.hash = '#dashboard&p=ABC'")
            self.until(lambda: js("!document.querySelector('.toast')"), True, "leaving Settings takes the toast")

    def test_a_file_that_cannot_keep_the_switch_reads_as_off_and_turning_it_on_is_refused_in_plain_words(self):
        self.s.httpd.app_settings = service(make_db(self.folder(), ready=False, cleanup=self.addCleanup))      # a data file made before the settings step
        with chrome() as cdp:
            js = self.show_page(cdp)
            self.assertTrue(wait(lambda: js("(document.querySelector('#ask-unsaved') || {}).innerText") == NOT_KEPT, 20))
            self.assertTrue(wait(lambda: js("document.querySelector('#ask-state').innerText") == OFF, 20), "never on by default when nothing is kept")      # the line first reads "Checking whether asking is on" until the check ends
            js("document.querySelector('[data-ask-switch]').click()")
            self.assertTrue(wait(lambda: bool(js("(document.querySelector('#ask-settings .pub-msg') || {}).innerText")), 20))
            text = js("document.querySelector('#ask-settings .pub-msg').innerText")
            self.assertIn("Nothing was changed.", text)
            self.assertFalse(text.lower().startswith("clark"), text)
            self.assertEqual(js("document.querySelector('#ask-state').innerText"), OFF)
            self.assertEqual(js("document.querySelectorAll('.toast').length"), 0, "a refused change says why under the switch, with no toast and no Undo")

    def test_without_the_server_route_the_folders_part_says_so_in_plain_words(self):
        with chrome() as cdp:
            js = self.show_page(cdp)
            self.assertTrue(wait(lambda: js("(document.querySelector('#ask-folders-note') || {}).innerText") == NOT_READY, 10))
            self.assertFalse(js("!!document.querySelector('#ask-folder-path')"), "no way to add a folder that cannot be saved")

    def test_choose_refuse_and_remove_a_folder(self):
        with chrome() as cdp:
            js = self.show_page(cdp, fake=True)
            self.assertTrue(wait(lambda: js("(document.querySelector('#ask-folders-none') || {}).innerText") == NONE, 10))
            self.assertFalse(js("!!document.querySelector('#ask-folder-path')"), "no box to type a location into")
            self.assertEqual(js("document.querySelector('[data-ask-choose]').innerText"), "Choose folder")
            self.assertIn("Parts of the files in these folders can be sent to Claude", js("document.querySelector('#ask-folders-card').innerText"))
            msg = "(document.querySelector('#ask-folders-card .pub-msg') || {}).innerText"
            js("window.__ask.choices = ['/bad', '/gone', '/Example/Programme files']")
            js("document.querySelector('[data-ask-choose]').click()")
            self.assertTrue(wait(lambda: js(msg) == "Asking can not read that folder, because it holds your passwords.", 10))
            self.assertFalse(js("!!document.querySelector('#ask-folders')"), "a refused folder is not listed")
            js("document.querySelector('[data-ask-choose]').click()")
            self.assertTrue(wait(lambda: "could not be saved" in (js(msg) or ""), 10))
            text = js(msg)
            self.assertFalse(text.lower().startswith("clark"), text)
            self.assertIn("try again", text.lower())
            js("document.querySelector('[data-ask-choose]').click()")
            self.assertTrue(wait(lambda: js("(document.querySelector('#ask-folders') || {innerText: ''}).innerText").startswith("/Example/Programme files"), 10))
            js("document.querySelector('[data-ask-remove]').click()")
            self.assertTrue(wait(lambda: js("(document.querySelector('#ask-folders-none') || {}).innerText") == NONE, 10))
            self.assertEqual(js("window.__ask.calls.map(c => c && c.action).filter(Boolean)"), ["choose", "choose", "choose", "remove"])

    def warn_page(self, cdp, width, scheme, provider=None, open_warn=None):
        """The fake route in a window of `width` with the colour scheme; `provider` is answered by the fake providers route and read once
        from the All projects tab; `open_warn` is a warning already on the list when the tab opens."""
        js = self.show_page(cdp, fake=True)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, self.sid)
        js("window.__ask.warn = [{folder: '/Example/Programme files', accepted: false, items: [{name: 'Contract 2026', readable_files: 12}, {name: 'Salary bands', readable_files: 3}]}]")
        if provider:
            js(f"window.__ask.provider = {json.dumps(provider)}")
            js("document.querySelector('[data-ask-tab=all]').click()")
            self.assertTrue(wait(lambda: js("!!document.querySelector('#ask-all')"), 10))
            self.assertTrue(wait(lambda: js("window.__ask.providerRead === true"), 10), "the providers route was read")
            self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ai-tile=claude]')"), 10), "the card has the answer")      # the page has used the answer: the tab is left only now
            js("document.querySelector('[data-ask-tab=project]').click()")
            self.assertTrue(wait(lambda: js("!!document.querySelector('#ask-settings')"), 10))
            self.assertTrue(wait(lambda: provider in (js("(document.querySelector('#ask-notice') || {}).innerText") or ""), 10), "the page reads the provider before the notice is drawn")
        if open_warn:
            js(f"window.__ask.folders = ['/Example/Programme files']; window.__ask.open = {json.dumps(open_warn)}")
            js("location.hash = '#dashboard&p=ABC'")
            wait(lambda: js("!document.querySelector('#ask-settings')"), 10)
            js("location.hash = '#settings&p=ABC&s=claude'")
            self.assertTrue(wait(lambda: js("!!document.querySelector('#ask-folders')"), 10))
        return js

    def test_a_saved_folder_with_people_or_contract_names_shows_one_amber_notice_under_its_line(self):
        """Row 1365: the notice sits directly under the flagged folder's line, full width in the same list, alert on save; the
        approved words; amber computed style (tint, text, radius 6, padding 6px 12px, 13px, names weight 500, margin-top 6, no icon, no border);
        buttons in the Settings button class (Accept and Decline, neither primary), gap 8. 1400 then 900, light and dark."""
        amber = {"light": ("rgb(251, 241, 218)", "rgb(138, 90, 0)"), "dark": ("rgb(53, 42, 16)", "rgb(240, 190, 90)")}
        for width in WIDTHS:
            for scheme in ("light", "dark"):
                with chrome() as cdp:
                    js = self.warn_page(cdp, width, scheme)
                    js("document.querySelector('[data-ask-choose]').click()")
                    self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ask-warn]')"), 10), f"{width} {scheme}")
                    self.assertEqual(js("document.querySelectorAll('[data-ask-warn]').length"), 1)
                    box = "document.querySelector('[data-ask-warn]')"
                    self.assertEqual(js(f"{box}.getAttribute('role')"), "alert")
                    self.assertTrue(js(f"{box}.previousElementSibling && {box}.previousElementSibling.innerText.startsWith('/Example/Programme files')"), "directly under the folder's line")
                    self.assertEqual(js(f"{box}.parentElement.id"), "ask-folders", "in the same group")
                    self.assertTrue(js(f"Math.abs({box}.getBoundingClientRect().width - {box}.parentElement.getBoundingClientRect().width) < 2"), "full width")
                    text = js(f"{box}.innerText")
                    flat = text.replace("\n", " ")
                    self.assertIn("This folder holds Contract 2026 and Salary bands. Passages from it may go to Claude, which Anthropic runs, and they can contain personal information.", flat)
                    self.assertIn("Send passages from this folder to Claude?", flat)
                    self.assertIn("Left out of ask clark.", flat, "no choice is Declined")
                    self.assertEqual(js(f"[...{box}.querySelectorAll('button')].map(b => b.innerText)"), ["Accept", "Decline"])
                    self.assertTrue(js(f"{box}.getBoundingClientRect().right <= innerWidth"), "no sideways overflow")
                    bg, fg = amber[scheme]
                    cs = f"getComputedStyle({box})"
                    self.assertEqual(js(f"{cs}.backgroundColor"), bg, f"{width} {scheme}")
                    self.assertEqual(js(f"{cs}.color"), fg, f"{width} {scheme}")
                    self.assertEqual(js(f"[{cs}.borderTopLeftRadius, {cs}.paddingTop, {cs}.paddingRight, {cs}.fontSize, {cs}.marginTop, {cs}.borderTopWidth]"),
                                     ["6px", "6px", "12px", "13px", "6px", "0px"])
                    self.assertFalse(js(f"!!{box}.querySelector('svg, img, .i')"), "no icon")
                    self.assertEqual(js(f"[...{box}.querySelectorAll('[data-ask-warn-name]')].map(n => getComputedStyle(n).fontWeight)"), ["500", "500"])
                    ch, kp = f"{box}.querySelector('[data-ask-warn-accept]')", f"{box}.querySelector('[data-ask-warn-decline]')"
                    self.assertTrue(js(f"{ch}.classList.contains('btn') && !{ch}.classList.contains('pri')"), "Accept is a plain Settings button")
                    self.assertTrue(js(f"{kp}.classList.contains('btn') && !{kp}.classList.contains('pri')"), "Decline is a plain Settings button")
                    self.assertEqual(js(f"getComputedStyle({ch}).borderTopLeftRadius"), js(f"getComputedStyle({kp}).borderTopLeftRadius"), "both buttons share one radius")
                    self.assertEqual(js(f"getComputedStyle({kp}).borderTopLeftRadius"), js("getComputedStyle(document.querySelector('[data-ask-choose]')).borderTopLeftRadius"), "the existing Settings button class, not a new radius")
                    self.assertEqual(js(f"getComputedStyle({ch}.parentElement).columnGap"), "8px")

    def test_accept_then_decline_send_only_the_folder_and_say_which_is_so_and_the_folder_stays_listed(self):
        """Row 1365: Accept sends {action: accept, path: the saved folder} and the notice then says 'Passages may go to Claude.'; Decline sends decline and the
        notice says 'Left out of ask clark.'; the folder stays listed and the buttons stay (a choice can always be changed). 1400 and 900."""
        for width in WIDTHS:
            with chrome() as cdp:
                js = self.warn_page(cdp, width, "light")
                js("document.querySelector('[data-ask-choose]').click()")
                self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ask-warn]')"), 10))
                state = "document.querySelector('[data-ask-warn-state]').innerText"
                self.assertEqual(js(state), "Left out of ask clark.")
                js("document.querySelector('[data-ask-warn-accept]').click()")
                self.assertTrue(wait(lambda: js(state) == "Passages may go to Claude.", 10), width)
                self.assertEqual(js("document.querySelector('[data-ask-warn-accept]').getAttribute('aria-pressed')"), "true")
                js("document.querySelector('[data-ask-warn-decline]').click()")
                self.assertTrue(wait(lambda: js(state) == "Left out of ask clark.", 10), width)
                self.assertEqual(js("document.querySelector('[data-ask-warn-decline]').getAttribute('aria-pressed')"), "true")
                self.assertEqual(js("window.__ask.calls.filter(c => c && (c.action === 'accept' || c.action === 'decline'))"),
                                 [{"project": "ABC", "action": "accept", "path": "/Example/Programme files"}, {"project": "ABC", "action": "decline", "path": "/Example/Programme files"}])
                self.assertEqual(js("window.__ask.folders"), ["/Example/Programme files"])
                self.assertEqual(js("[...document.querySelectorAll('#ask-folders .folder-now')].map(e => e.innerText)"), ["/Example/Programme files"])
                self.assertTrue(js("document.querySelector('[data-ask-warn]').getBoundingClientRect().right <= innerWidth"), "no sideways overflow")

    def test_an_accepted_folder_reads_passages_may_go_on_open_and_the_old_buttons_are_gone(self):
        with chrome() as cdp:
            js = self.warn_page(cdp, 1400, "light", open_warn=[{"folder": "/Example/Programme files", "accepted": True, "items": [{"name": "Contract", "readable_files": 2, "dir": False}]}])
            box = "document.querySelector('[data-ask-warn]')"
            self.assertEqual(js(f"{box}.querySelector('[data-ask-warn-state]').innerText"), "Passages may go to Claude.")
            self.assertEqual(js(f"[...{box}.querySelectorAll('button')].map(b => b.innerText)"), ["Accept", "Decline"])
            text = js(f"{box}.innerText")
            self.assertNotIn("Keep it", text)
            self.assertNotIn("Choose other folders", text)

    def test_leave_these_subfolders_out_is_a_third_button_that_sends_only_the_folder_and_the_notice_goes(self):
        """Row 1365 line 14: the button shows only when a flagged hit is a folder, sends {action: exclude, path: the saved folder} and nothing else, and
        the notice goes with the answer. 1400 and 900, Classic."""
        for width in WIDTHS:
            with chrome() as cdp:
                js = self.warn_page(cdp, width, "light", open_warn=[{"folder": "/Example/Programme files", "items": [{"name": "Contract", "readable_files": 2, "dir": True}]}])
                box = "document.querySelector('[data-ask-warn]')"
                self.assertEqual(js(f"[...{box}.querySelectorAll('button')].map(b => b.innerText)"), ["Accept", "Decline", "Leave these subfolders out"], width)
                self.assertTrue(js(f"{box}.getBoundingClientRect().right <= innerWidth"), "no sideways overflow")
                js(f"{box}.querySelector('[data-ask-warn-leave]').click()")
                self.assertTrue(wait(lambda: js("!document.querySelector('[data-ask-warn]')"), 10), "the notice goes")
                self.assertEqual(js("window.__ask.calls.filter(c => c && c.action === 'exclude')"), [{"project": "ABC", "action": "exclude", "path": "/Example/Programme files"}])
                self.assertEqual(js("[...document.querySelectorAll('#ask-folders .folder-now')].map(e => e.innerText)"), ["/Example/Programme files"], "the folder stays listed")

    def test_leave_out_button_is_not_offered_for_a_hit_that_is_only_a_file(self):
        with chrome() as cdp:
            js = self.warn_page(cdp, 1400, "light", open_warn=[{"folder": "/Example/Programme files", "items": [{"name": "Payroll.csv", "readable_files": 1, "dir": False}]}])
            self.assertEqual(js("document.querySelectorAll('[data-ask-warn-leave]').length"), 0)

    def test_a_failed_leave_out_says_so_and_keeps_the_notice(self):
        with chrome() as cdp:
            js = self.warn_page(cdp, 1400, "light", open_warn=[{"folder": "/Example/Programme files", "items": [{"name": "Contract", "readable_files": 2, "dir": True}]}])
            js("window.__ask.excludeFail = true; const f = window.fetch; window.fetch = (u, o) => (o && o.body && String(o.body).indexOf('exclude') >= 0) ? Promise.resolve(new Response(JSON.stringify({ok: false, code: 'cant_save', message: 'That folder could not be saved. Nothing was changed.'}), {status: 409, headers: {'Content-Type': 'application/json'}})) : f(u, o)")
            js("document.querySelector('[data-ask-warn-leave]').click()")
            self.assertTrue(wait(lambda: "Nothing was changed" in js("document.querySelector('#ask-folders-card').innerText"), 10))
            self.assertTrue(js("!!document.querySelector('[data-ask-warn]')"))

    def test_warning_names_connected_provider(self):
        """Row 1365 test 5: ChatGPT is named when it is the provider (and 'which Anthropic runs' is dropped); on open the notice is a labelled region, not an alert."""
        with chrome() as cdp:
            js = self.warn_page(cdp, 1400, "light", provider="ChatGPT", open_warn=[{"folder": "/Example/Programme files", "accepted": False, "items": [{"name": "Payroll", "readable_files": 1}]}])
            self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ask-warn]')"), 10))
            box = "document.querySelector('[data-ask-warn]')"
            self.assertEqual(js(f"{box}.getAttribute('role')"), "region")
            flat = lambda: " ".join(js(f"{box}.innerText").split())      # the paragraphs are joined by line breaks: one space between words and between sentences
            self.assertTrue(wait(lambda: "may go to ChatGPT, and they can contain personal information." in flat(), 10), "the provider in use is named")
            self.assertIn("This folder holds Payroll. Passages from it may go to ChatGPT, and they can contain personal information. Send passages from this folder to ChatGPT?", flat())
            self.assertNotIn("Claude", flat())
            self.assertNotIn("Anthropic", flat())
            js(f"{box}.querySelector('[data-ask-warn-accept]').click()")
            self.assertTrue(wait(lambda: "Passages may go to ChatGPT." in flat(), 10))

    def test_leaving_the_all_tab_in_the_commit_that_draws_the_card_keeps_the_provider(self):
        """Row 1417 (CI run 45523455732, the 1621 race): the card keeps the provider's answer in the commit that draws it. The tab is left from a
        MutationObserver, which runs the moment the card's tile is in the page and before any effect that waits for the paint: a plain effect
        was lost there and the Asking notice kept saying Claude. No sleep, no timing: the order is the browser's own."""
        with chrome() as cdp:
            js = self.show_page(cdp, fake=True)
            js("window.__ask.provider = 'ChatGPT'")
            js("""new MutationObserver((_, o) => { if (document.querySelector('[data-ai-tile=claude]')) { o.disconnect(); window.__ask.left = true;
                document.querySelector('[data-ask-tab=project]').click(); } }).observe(document.body, {childList: true, subtree: true})""")
            js("document.querySelector('[data-ask-tab=all]').click()")
            self.assertTrue(wait(lambda: js("window.__ask.left === true"), 10), "the tab was left as the card drew")
            self.assertTrue(wait(lambda: js("!!document.querySelector('#ask-settings')"), 10))
            self.assertTrue(wait(lambda: "ChatGPT" in (js("(document.querySelector('#ask-notice') || {}).innerText") or ""), 10),
                            "the notice names the provider the card was told, though the tab was left as the card drew")

    def test_a_folder_without_such_names_shows_no_warning(self):
        with chrome() as cdp:
            js = self.show_page(cdp, fake=True)
            js("document.querySelector('[data-ask-choose]').click()")
            self.assertTrue(wait(lambda: js("window.__ask.folders.length") == 1, 20), "the choose was answered")
            self.assertTrue(wait(lambda: js("!!document.querySelector('#ask-folders')"), 20), "the folder is listed")
            self.assertFalse(js("!!document.querySelector('[data-ask-warn]')"))

    def test_cards_shows_the_same_notice_so_a_left_out_folder_has_its_two_buttons(self):
        """Row 1365: a folder with such names is left out by default in every theme, so Cards shows the notice (its words and buttons; the amber is Classic's) and
        the person can always press Accept."""
        with chrome() as cdp:
            js = self.warn_page(cdp, 1400, "light")
            js("document.querySelector('[data-ask-choose]').click()")
            self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ask-warn]')"), 10))
            self.assertEqual(js("[...document.querySelectorAll('[data-ask-warn] button')].map(b => b.innerText)"), ["Accept", "Decline"])
            self.assertIn("Left out of ask clark.", js("document.querySelector('[data-ask-warn]').innerText"))

    def test_saved_notice_goes_from_alert_to_region_after_cancel_and_after_remove(self):
        """Row 1365 survivors: once another request has come back, a notice is no longer fresh: role region labelled with the folder, after a
        cancelled Choose folder and after Remove of another folder."""
        for step in ("cancel", "remove"):
            with chrome() as cdp:
                js = self.warn_page(cdp, 1400, "light")
                js("window.__ask.folders = ['/Example/Plain']")
                js("location.hash = '#dashboard&p=ABC'")
                wait(lambda: js("!document.querySelector('#ask-settings')"), 10)
                js("location.hash = '#settings&p=ABC&s=claude'")
                self.assertTrue(wait(lambda: js("!!document.querySelector('#ask-folders')"), 10))
                js("document.querySelector('[data-ask-choose]').click()")
                self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ask-warn]')"), 10))
                self.assertEqual(js("document.querySelector('[data-ask-warn]').getAttribute('role')"), "alert", step)
                if step == "cancel":
                    js("window.__ask.choices = ['/cancel']; document.querySelector('[data-ask-choose]').click()")
                    self.assertTrue(wait(lambda: js("window.__ask.calls.filter(c => c && c.action === 'choose').length") == 2, 10))
                else:
                    js("document.querySelector('[data-ask-remove=\"/Example/Plain\"]').click()")
                    self.assertTrue(wait(lambda: js("window.__ask.folders.length") == 1, 10))
                self.assertTrue(wait(lambda: js("document.querySelector('[data-ask-warn]').getAttribute('role')") == "region", 10), step)
                self.assertEqual(js("document.querySelector('[data-ask-warn]').getAttribute('aria-label')"), "/Example/Programme files", step)

    def test_choose_and_remove_keep_the_focus_in_the_folders_part(self):
        """Choose folder and Remove are disabled while the request runs: the focus comes back to Choose folder, or after a Remove to
        the Remove button now in that place (Choose folder when none is left). 1400 and 900."""
        act = "document.activeElement"
        choose = "document.querySelector('[data-ask-choose]')"
        with chrome() as cdp:
            js = self.show_page(cdp, fake=True)
            self.assertTrue(wait(lambda: js("(document.querySelector('#ask-folders-none') || {}).innerText") == NONE, 10))
            for w in WIDTHS:
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                js("window.__ask.choices = ['/Example/One', '/Example/Two']")
                for _ in range(2):
                    js(f"{choose}.focus(); {choose}.click()")
                    self.until(lambda: js(f"{act} === {choose}"), True, f"{w}: focus is back on Choose folder")
                self.until(lambda: js("document.querySelectorAll('[data-ask-remove]').length"), 2, f"{w}: two folders")
                rm = "document.querySelectorAll('[data-ask-remove]')"
                js(f"{rm}[0].focus(); {rm}[0].click()")
                self.until(lambda: js(f"{act} === {rm}[0] && {rm}.length === 1"), True, f"{w}: focus is on the Remove button that took its place")
                js(f"{rm}[0].focus(); {rm}[0].click()")
                self.until(lambda: js(f"{act} === {choose} && !document.querySelector('#ask-folders')"), True, f"{w}: none left, focus is on Choose folder")

    def test_when_no_window_can_open_a_box_to_type_the_location_appears(self):
        for scheme, width in [(a, b) for a in ("light", "dark") for b in WIDTHS]:
            with chrome() as cdp:
                js = self.show_page(cdp, fake=True)
                cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, self.sid)
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ask-choose]')"), 10))
                msg = "(document.querySelector('#ask-folders-card .pub-msg') || {}).innerText"
                js("window.__ask.choices = ['/nowin']")
                js("document.querySelector('[data-ask-choose]').click()")
                self.assertTrue(wait(lambda: "Type the folder location" in (js(msg) or ""), 10))
                self.assertTrue(js("!!document.querySelector('#ask-folder-path')"))
                self.assertTrue(js("document.querySelector('[data-ask-add]').disabled"), "nothing to add yet")
                js("(() => { const i = document.querySelector('#ask-folder-path'); i.value = '/Example/typed'; i.dispatchEvent(new Event('input', {bubbles: true})); })()")
                self.assertTrue(wait(lambda: not js("document.querySelector('[data-ask-add]').disabled"), 10))
                js("document.querySelector('[data-ask-add]').click()")
                self.assertTrue(wait(lambda: js("(document.querySelector('#ask-folders') || {innerText: ''}).innerText").startswith("/Example/typed"), 10))
                self.assertEqual(js("window.__ask.calls.filter(Boolean).pop().path"), "/Example/typed")
                self.assertEqual(js("document.querySelector('#ask-folder-path').value"), "")
                self.assertLessEqual(js("document.documentElement.scrollWidth"), width)

    def test_add_folder_pressed_with_the_keyboard_keeps_the_focus_in_the_folders_part(self):
        """Add folder is disabled while it runs, which drops the focus: a real Enter on the button puts it back in the location box. 1400 and 900."""
        for width in WIDTHS:
            with chrome() as cdp:
                js = self.show_page(cdp, fake=True)
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ask-choose]')"), 10))
                js("window.__ask.choices = ['/nowin']")
                js("document.querySelector('[data-ask-choose]').click()")
                self.assertTrue(wait(lambda: js("!!document.querySelector('#ask-folder-path')"), 10))
                js("(() => { const i = document.querySelector('#ask-folder-path'); i.value = '/Example/typed'; i.dispatchEvent(new Event('input', {bubbles: true})); })()")
                self.assertTrue(wait(lambda: not js("document.querySelector('[data-ask-add]').disabled"), 10))
                js("document.querySelector('[data-ask-add]').focus()")
                for typ in ("keyDown", "keyUp"):
                    cdp.call("Input.dispatchKeyEvent", {"type": typ, "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13, **({"text": "\r"} if typ == "keyDown" else {})}, self.sid)
                self.assertTrue(wait(lambda: js("(document.querySelector('#ask-folders') || {innerText: ''}).innerText").startswith("/Example/typed"), 10))
                self.until(lambda: js("document.activeElement.id"), "ask-folder-path", f"{width}: focus is in the location box after Add folder")

    def test_add_folder_keeps_the_focus_in_the_location_box(self):
        """Add folder is disabled while the request runs and again once the box is emptied: the focus goes to the box, refused or not."""
        with chrome() as cdp:
            js = self.show_page(cdp, fake=True)
            self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ask-choose]')"), 10))
            js("window.__ask.choices = ['/nowin']")
            js("document.querySelector('[data-ask-choose]').click()")
            self.assertTrue(wait(lambda: js("!!document.querySelector('#ask-folder-path')"), 10))
            put = lambda text: js("(() => { const i = document.querySelector('#ask-folder-path'); i.value = %s; i.dispatchEvent(new Event('input', {bubbles: true})); })()" % json.dumps(text))
            for text in ("/bad", "/Example/typed"):
                put(text)
                self.assertTrue(wait(lambda: not js("document.querySelector('[data-ask-add]').disabled"), 10))
                js("document.querySelector('[data-ask-add]').focus(); document.querySelector('[data-ask-add]').click()")
                self.until(lambda: js("document.activeElement === document.querySelector('#ask-folder-path')"), True, f"{text}: focus is in the box")

    def test_the_typed_location_is_trimmed_spaces_alone_add_nothing_and_a_refused_one_stays_in_the_box(self):
        with chrome() as cdp:
            js = self.show_page(cdp, fake=True)
            self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ask-choose]')"), 10))
            js("window.__ask.choices = ['/nowin']")
            js("document.querySelector('[data-ask-choose]').click()")
            self.assertTrue(wait(lambda: js("!!document.querySelector('#ask-folder-path')"), 10))
            put = lambda text: js("(() => { const i = document.querySelector('#ask-folder-path'); i.value = %s; i.dispatchEvent(new Event('input', {bubbles: true})); })()" % json.dumps(text))
            put("    ")
            self.assertTrue(wait(lambda: js("document.querySelector('#ask-folder-path').value") == "    ", 10))
            self.assertTrue(js("document.querySelector('[data-ask-add]').disabled"), "spaces alone are nothing to add")
            before = js("window.__ask.calls.filter(Boolean).length")
            js("document.querySelector('#ask-folder-form').requestSubmit()")                    # Enter in the box submits even when the button is off
            self.assertEqual(js("window.__ask.calls.filter(Boolean).length"), before, "nothing was sent for spaces")
            put("/bad")                                                                           # the server refuses it: the words stay to be corrected
            self.assertTrue(wait(lambda: not js("document.querySelector('[data-ask-add]').disabled"), 10))
            js("document.querySelector('[data-ask-add]').click()")
            self.assertTrue(wait(lambda: "passwords" in (js("(document.querySelector('#ask-folders-card .pub-msg') || {}).innerText") or ""), 10))
            self.assertEqual(js("document.querySelector('#ask-folder-path').value"), "/bad", "a refused location is not cleared")
            put("  /Example/typed  ")
            self.assertTrue(wait(lambda: not js("document.querySelector('[data-ask-add]').disabled"), 10))
            js("document.querySelector('[data-ask-add]').click()")
            self.assertTrue(wait(lambda: js("(document.querySelector('#ask-folders') || {innerText: ''}).innerText").startswith("/Example/typed"), 10))
            self.assertEqual(js("window.__ask.calls.filter(Boolean).pop().path"), "/Example/typed", "sent without the spaces")

    def test_the_sources_hold_no_sentence_that_starts_with_the_product_name_and_the_published_page_has_none_of_it(self):
        text = "\n".join((PAGE_SRC / "edit" / n).read_text(encoding="utf-8") for n in ("AskSettings.jsx", "askState.js"))
        self.assertNotIn("window.localStorage", text, "the switch is kept by the server, not by the browser")
        shown = re.findall(r'>([^<>{}]{6,})<|"([A-Z][^"]{20,})"', text)
        self.assertNotIn("full path", text.lower(), "a person is never asked for a full path")
        for a, b in shown:
            self.assertFalse(re.match(r"\s*(ask )?clark\b", a or b, re.I), a or b)
        view = (Path(page.PAGE).parent / "page-view.html").read_text(encoding="utf-8")
        for needle in ("/api/ask-folders", "/api/ask-enabled", "clark.askEnabled", "Folders asking may read"):
            self.assertNotIn(needle, view, "a published file has no Settings, so none of this")


if __name__ == "__main__":
    unittest.main()
