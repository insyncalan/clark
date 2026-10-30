"""#47: the Settings entry for asking, in a real browser against the real server (desktop widths 1400 and 900 only).

Run: python3 dev/run_tests.py test_ask_settings
The switch is one saved choice in the browser's storage (clark.askEnabled), on by default; the folder choice calls
/api/ask-folders, which the server does not have yet (it answers 404, and the page says so in plain words); the answers a server
with the route would give are put in by replacing the page's fetch for that one address. Chrome is required: fails, never skips.
"""
import re
import tempfile
import unittest
from pathlib import Path

from _paths import SRC
from test_page import DATA, navigate
from test_server import Running, chrome, wait

from clark import page

PAGE_SRC = Path(page.PAGE).parent / "src"
WIDTHS = (1400, 900)
ON = "Asking is on. Your question and the passages it needs go to Claude, which Anthropic runs."
OFF = "Asking is off. Turn it on in Settings."
NOT_READY = "Choosing folders isn't ready on this computer yet. Asking uses only this project's data until it is."
NONE = "No folders are set. Asking uses only this project's data."
FAKE = """
window.__ask = {folders: [], calls: []};
const real = window.fetch;
window.fetch = function (url, opts) {
  if (String(url).indexOf('/api/ask-folders') < 0) return real.apply(this, arguments);
  const body = opts && opts.body ? JSON.parse(opts.body) : null;
  window.__ask.calls.push(body);
  const f = window.__ask.folders;
  let status = 200, out = {ok: true, folders: f};
  if (body && body.action === 'choose') {
    window.__ask.choices = window.__ask.choices || ['/Example/Programme files'];
    const next = window.__ask.choices.shift();
    if (next === '/bad') { status = 409; out = {ok: false, code: 'closed_place', message: 'Asking can not read that folder, because it holds your passwords.'}; }
    else if (next === '/gone') { status = 500; out = null; }
    else { if (f.indexOf(next) < 0) f.push(next); out = {ok: true, folders: f, message: 'Added.'}; }
  } else if (body && body.action === 'add') {
    if (body.path === '/bad') { status = 409; out = {ok: false, code: 'client_folder_refused', message: 'That folder holds your passwords, so asking cannot read it.'}; }
    else { f.push(body.path); out = {ok: true, folders: f, message: 'Folder added.'}; }
  } else if (body && body.action === 'remove') { window.__ask.folders = f.filter(x => x !== body.path); out = {ok: true, folders: window.__ask.folders}; }
  return Promise.resolve(new Response(JSON.stringify(out), {status: status, headers: {'Content-Type': 'application/json'}}));
};
"""


class Settings(unittest.TestCase):
    def setUp(self):
        self.s = Running(data_for=DATA.get, page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(self.s.close)

    def open(self, cdp, fake=False):
        sid = navigate(cdp, self.s.port, "#settings&p=ABC")
        self.sid = sid
        js = lambda e: cdp.js(e, sid)          # noqa: E731
        if fake:
            js(FAKE)
            js("location.hash = '#dashboard&p=ABC'")
            wait(lambda: js("!document.querySelector('#ask-settings')"), 10)
            js("location.hash = '#settings&p=ABC'")
        self.assertTrue(wait(lambda: js("!!document.querySelector('#ask-settings')"), 20), "the Asking entry is in Settings")
        return js

    def test_the_switch_is_on_by_default_changes_the_saved_choice_and_survives_a_reload(self):
        with chrome() as cdp:
            js = self.open(cdp)
            for w in WIDTHS:
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                self.assertEqual(js("document.documentElement.scrollWidth <= window.innerWidth"), True, f"no sideways scroll at {w}")
                self.assertEqual(js("var r=document.querySelector('[data-ask-switch]').getBoundingClientRect(); r.width > 0 && r.right <= window.innerWidth"), True)
            self.assertEqual(js("document.querySelector('#ask-state').innerText"), ON)
            self.assertEqual(js("localStorage.getItem('clark.askEnabled')"), None, "nothing is saved until the person chooses")
            js("document.querySelector('[data-ask-switch]').click()")
            self.assertTrue(wait(lambda: js("document.querySelector('#ask-state').innerText") == OFF, 10))
            self.assertEqual(js("document.querySelector('[data-ask-switch]').innerText"), "Turn on asking")
            self.assertEqual(js("localStorage.getItem('clark.askEnabled')"), "off")
            js("location.reload()")
            self.assertTrue(wait(lambda: js("(document.querySelector('#ask-state') || {}).innerText") == OFF, 20), "off after a reload")
            js("document.querySelector('[data-ask-switch]').click()")
            self.assertTrue(wait(lambda: js("document.querySelector('#ask-state').innerText") == ON, 10))
            self.assertEqual(js("localStorage.getItem('clark.askEnabled')"), "on")

    def test_without_the_server_route_the_folders_part_says_so_in_plain_words(self):
        with chrome() as cdp:
            js = self.open(cdp)
            self.assertTrue(wait(lambda: js("(document.querySelector('#ask-folders-note') || {}).innerText") == NOT_READY, 10))
            self.assertFalse(js("!!document.querySelector('#ask-folder-path')"), "no way to add a folder that cannot be saved")

    def test_choose_refuse_and_remove_a_folder(self):
        with chrome() as cdp:
            js = self.open(cdp, fake=True)
            self.assertTrue(wait(lambda: js("(document.querySelector('#ask-folders-none') || {}).innerText") == NONE, 10))
            self.assertFalse(js("!!document.querySelector('#ask-folder-path')"), "no box to type a location into")
            self.assertEqual(js("document.querySelector('[data-ask-choose]').innerText"), "Choose folder")
            self.assertIn("Parts of the files in these folders can be sent to Claude", js("document.querySelector('#ask-settings').innerText"))
            msg = "(document.querySelector('#ask-settings .pub-msg') || {}).innerText"
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

    def test_the_sources_hold_no_sentence_that_starts_with_the_product_name_and_the_published_page_has_none_of_it(self):
        text = "\n".join((PAGE_SRC / "edit" / n).read_text(encoding="utf-8") for n in ("AskSettings.jsx", "askState.js"))
        shown = re.findall(r'>([^<>{}]{6,})<|"([A-Z][^"]{20,})"', text)
        self.assertNotIn("full path", text.lower(), "a person is never asked for a full path")
        for a, b in shown:
            self.assertFalse(re.match(r"\s*(ask )?clark\b", a or b, re.I), a or b)
        view = (Path(page.PAGE).parent / "page-view.html").read_text(encoding="utf-8")
        for needle in ("/api/ask-folders", "clark.askEnabled", "Folders asking may read"):
            self.assertNotIn(needle, view, "a published file has no Settings, so none of this")


if __name__ == "__main__":
    unittest.main()
