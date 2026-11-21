"""Row 1294: the paperclip, the picker and the drop in the ask panel follow the Files switch; unknown keeps them, as main does.

Run: python3 dev/run_tests.py test_ask_files_panel_1294
The panel reads GET /api/ask-files when it opens and again when the open project changes. Only a 200 answer that says ok and allowed false takes the paperclip away
(and empties the chips); a read that fails, a non-200 and an answer that cannot be read leave it, because main always has it and the server checks again for every question.
The page's fetch of /api/ask-files is replaced by the answers the server gives. Widths 1400 and 900. Chrome is required: fails, never skips.
"""
import json
import time
import unittest

from _new_page import reload_to_new_page
from test_ask_files_panel import DROP, PASTE, PICK, SETTLE
from test_ask_panel import Stub
from test_report_editor import Base
from test_server import chrome

# mode: allowed | denied | status500 | not_ok | throws | hold (the read waits for release()); `by_project` maps a project code to its mode
FAKE = """
window.__g = {urls: [], mode: '%s', by_project: %s, waiting: []};
const real = window.fetch;
const reply = (st, b) => new Response(JSON.stringify(b), {status: st, headers: {'Content-Type': 'application/json'}});
window.fetch = function (url, opts) {
  if (String(url).indexOf('/api/ask-files') < 0) return real.apply(this, arguments);
  const g = window.__g; g.urls.push(String(url));
  const m = (/project=([A-Z0-9]+)/.exec(String(url)) || [])[1];
  const mode = (m && g.by_project[m]) || g.mode;
  const answer = () => {
    if (mode === 'denied') return reply(200, {ok: true, on: true, off_here: true, allowed: false});
    if (mode === 'status500') return reply(500, {ok: false, allowed: false});
    if (mode === 'no_allowed') return reply(200, {ok: true, on: true});
    if (mode === 'not_ok') return reply(200, {ok: false, allowed: false});
    if (mode === 'throws') throw new TypeError('network');
    return reply(200, {ok: true, on: true, off_here: false, allowed: true});
  };
  if (mode === 'hold') return new Promise((res) => g.waiting.push(() => res(reply(200, {ok: true, allowed: false}))));
  if (mode === 'throws') return Promise.reject(new TypeError('network'));
  return Promise.resolve(answer());
};
"""
GONE = "!document.querySelector('#ask-attach') && !document.querySelector('#ask-file-input')"
HERE = "!!document.querySelector('#ask-attach') && !!document.querySelector('#ask-file-input')"
CHIPS_N = "document.querySelectorAll('#ask-files li[data-file]').length"


class Panel(Base):
    def setUp(self):
        super().setUp()
        self.stub = Stub()
        self.s.httpd.ask = self.stub

    def open_panel(self, cdp, mode, width=1400, other=None):
        p = self.visit(cdp)
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]}, p.sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        src = FAKE % (mode, json.dumps({"DEMO": other} if other else {}))
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": src}, p.sid)      # a project change is a fresh page load: the answers come back with it
        p.js(src)
        p.key("/", code="Slash", vk=191)
        p.until("!!document.querySelector('#ask-panel')", "the panel opened on /")
        p.until(SETTLE, "the panel is ready to take a question")
        return p

    def switch_to(self, p, code):
        """The header's project menu, as a person uses it: the page stays, the panel stays open, the project changes."""
        p.js("document.querySelector('#project-name').click()")
        sel = "#project-menu [role=menuitemradio][data-kind=%s]" % code
        p.until("!!document.querySelector('%s')" % sel, "the menu lists " + code)
        p.js("document.querySelector('%s').click()" % sel)

    def test_allowed_keeps_the_paperclip_and_the_picker_and_asks_for_this_project(self):
        for w in (1400, 900):
            with self.subTest(width=w), chrome() as cdp:
                p = self.open_panel(cdp, "allowed", w)
                p.until(HERE, "the paperclip and the picker")
                self.assertEqual(json.loads(p.js("JSON.stringify(window.__g.urls)"))[0], "/api/ask-files?project=ABC")

    def test_not_allowed_leaves_no_paperclip_no_picker_and_no_drop_line(self):
        with chrome() as cdp:
            p = self.open_panel(cdp, "denied")
            p.until(GONE, "the paperclip and the picker are gone")
            self.assertEqual(p.js("document.querySelector('#ask-box') !== null"), True)
            self.assertTrue(p.js("!!document.querySelector('#ask-send')"), "Send is still there")
            p.js(DROP % "[mk('b.csv',100)]")
            self.assertEqual(p.js(CHIPS_N), 0, "a drop makes no chip: hasFiles says no, so the drag is not taken")

    def test_a_read_that_cannot_tell_keeps_the_paperclip_as_main_has_it(self):
        for mode in ("status500", "not_ok", "throws"):
            with self.subTest(mode=mode), chrome() as cdp:
                p = self.open_panel(cdp, mode)
                p.until("window.__g.urls.length >= 1", "the panel asked")
                p.until(HERE, "still the paperclip and the picker")
                p.js(PICK % "[mk('a.txt',10)]")
                p.until(CHIPS_N + " === 1", "a chosen file still becomes a chip")

    def test_the_paperclip_is_there_at_once_and_does_not_flash_before_the_answer(self):
        with chrome() as cdp:
            p = self.open_panel(cdp, "hold")
            self.assertTrue(p.js(HERE), "the answer has not come and the paperclip is there")
            p.js("window.__g.waiting.forEach(f => f())")
            p.until(GONE, "then the answer says not allowed and it goes")

    def test_a_paste_when_not_allowed_makes_no_chip(self):
        with chrome() as cdp:
            p = self.open_panel(cdp, "denied")
            p.until(GONE, "denied")
            p.js(PASTE % "[mk('c.md',10)]")
            self.assertEqual(p.js(CHIPS_N), 0, "a paste makes no chip while not allowed (the guard in addFiles)")

    def test_a_denied_answer_empties_the_chips_that_waited(self):
        with chrome() as cdp:
            p = self.open_panel(cdp, "hold")
            p.js(PICK % "[mk('a.txt',10)]")
            p.until(CHIPS_N + " === 1", "a chip while the answer is out")
            p.js("window.__g.waiting.forEach(f => f())")
            p.until(GONE, "the answer says not allowed")
            self.assertEqual(p.js(CHIPS_N), 0, "the chips that waited are dropped")

    def test_a_late_answer_that_comes_after_a_newer_one_is_ignored(self):
        with chrome() as cdp:
            p = self.open_panel(cdp, "hold")
            p.key("Escape", code="Escape", vk=27)
            p.until("!document.querySelector('#ask-panel')", "the panel closed")
            p.js("window.__g.mode = 'allowed'")
            p.key("/", code="Slash", vk=191)
            p.until("!!document.querySelector('#ask-panel') && window.__g.urls.length === 2", "opened again and read again")
            p.until(HERE, "the newer read said allowed")
            p.js("window.__g.waiting.forEach(f => f())")        # the first read's 'not allowed' arrives late
            time.sleep(0.3)
            self.assertTrue(p.js(HERE), "the late answer of the read that was replaced did not take the paperclip away")

    def test_the_panel_asks_nothing_while_it_has_never_been_opened(self):
        with chrome() as cdp:
            p = self.open_panel(cdp, "allowed")
            p.key("Escape", code="Escape", vk=27)
            p.until("!document.querySelector('#ask-panel')", "closed")
            reload_to_new_page(p.js, "typeof window.__g === 'object'", "the page loaded again")
            time.sleep(0.5)
            self.assertEqual(p.js("window.__g.urls.length"), 0, "a closed panel does not read the switch")
            p.key("/", code="Slash", vk=191)
            p.until("window.__g.urls.length === 1", "opening it reads once")

    def test_a_file_dragged_over_is_taken_only_while_allowed(self):
        DRAG = "(function(){var dt=new DataTransfer();dt.items.add(new File(['a'],'a.txt',{type:'text/plain'}));var a=document.querySelector('#ask-panel');var e=new DragEvent('dragover',{dataTransfer:dt,bubbles:true,cancelable:true});a.dispatchEvent(e);return e.defaultPrevented})()"
        for mode, taken in (("allowed", True), ("denied", False)):
            with self.subTest(mode=mode), chrome() as cdp:
                p = self.open_panel(cdp, mode)
                p.until(HERE if taken else GONE, mode)
                self.assertEqual(p.js(DRAG), taken)
                self.assertEqual(p.js("!!document.querySelector('#ask-drop-line')"), taken)

    def test_an_answer_without_allowed_does_not_take_the_paperclip(self):
        with chrome() as cdp:
            p = self.open_panel(cdp, "no_allowed")
            p.until("window.__g.urls.length >= 1", "asked")
            time.sleep(0.3)
            self.assertTrue(p.js(HERE))

    def test_it_reads_again_for_another_project_and_follows_its_answer(self):
        with chrome() as cdp:
            p = self.open_panel(cdp, "allowed", other="denied")
            p.until(HERE, "allowed for ABC")
            self.switch_to(p, "DEMO")
            p.until("location.hash.indexOf('p=DEMO') >= 0 && !!document.querySelector('#ask-box, body')", "the other project's page")
            p.until("typeof window.__g === 'object' && document.readyState === 'complete'", "the new page loaded")
            p.key("/", code="Slash", vk=191)
            p.until("!!document.querySelector('#ask-panel')", "the panel opened")
            p.until("window.__g.urls.some(u => u.indexOf('project=DEMO') >= 0)", "asked for the new project")
            p.until(GONE, "denied for the new project")


if __name__ == "__main__":
    unittest.main()
