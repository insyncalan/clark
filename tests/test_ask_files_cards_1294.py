"""Row 1294: the Files cards' words, answers and the order the ticket gives, in a real browser at 1400 and 900; Cards shows no Files card.

Run: python3 dev/run_tests.py test_ask_files_cards_1294
Ticket 1294 body, the order of the cards. All tab: "Standing instructions, Files, Slash commands, Source folders". Project tab:
"...Source folders, Standing instructions, Slash commands, Files and pictures, Chats and usage". A ruling at 03:31 on 20-11 said that the order stays as
the ticket body, and that the heading is "Files" (no "and pictures"): in this build the cards that exist are placed in that relative order
(Standing instructions, Files, Source folders on All; Source folders, Standing instructions, Files on a project). Slash commands and Chats are not built.
The page's fetch of /api/ask-files is replaced by the answers the server gives, each one a mode. Chrome is required: fails, never skips.
"""
import tempfile
import unittest

from _editor_checks import for_project
from test_ask_settings import make_db, service
from test_page import DATA, navigate
from test_server import Running, chrome, wait

from clark import page

WIDTHS = (1400, 900)
FILES_LINE = "Files: text, Markdown and CSV (5 files of 10 MB, for that question only). A project can turn these off for itself."
UNAVAILABLE = "Files cannot be checked just now. They are checked again when you ask, and none are sent if they are off."
# mode: ok | get500_ok (500 with an ok body) | get500 (the read fails) | get_not_ok (200, ok false) | on_not_bool (200, on is a word) | post503 | post_known (400 with a code and words) | hold (a change waits for release())
FAKE = """
window.__f = {calls: [], on: true, off_here: false, mode: '%s', next: 7, hist: [], held: null};
const real = window.fetch;
const reply = (st, b) => new Response(JSON.stringify(b), {status: st, headers: {'Content-Type': 'application/json'}});
window.fetch = function (url, opts) {
  if (String(url).indexOf('/api/ask-files') < 0) return real.apply(this, arguments);
  const f = window.__f, body = opts && opts.body ? JSON.parse(opts.body) : null;
  if (!body) {
    if (f.mode === 'get500') return Promise.resolve(reply(500, {ok: false}));
    if (f.mode === 'get_not_ok') return Promise.resolve(reply(200, {ok: false, on: true}));
    if (f.mode === 'get500_ok') return Promise.resolve(reply(500, {ok: true, on: true, off_here: false}));
    if (f.mode === 'on_not_bool') return Promise.resolve(reply(200, {ok: true, on: 'yes'}));
    return Promise.resolve(reply(200, {ok: true, on: f.on, off_here: f.off_here, allowed: f.on && !f.off_here}));
  }
  f.calls.push(body);
  const done = () => {
    if (f.mode === 'post503') return reply(503, {ok: false});
    if (f.mode === 'post_known') return reply(400, {ok: false, code: 'files_busy', message: 'Another change is being saved. Try again in a moment.'});
    if (body.undo !== undefined) { const h = f.hist.pop(); f.on = h.on; f.off_here = h.off_here; return reply(200, {ok: true, on: f.on, off_here: f.off_here, apply_id: f.next++}); }
    f.hist.push({on: f.on, off_here: f.off_here});
    if (body.on !== undefined) f.on = body.on;
    if (body.off_here !== undefined) f.off_here = body.off_here;
    return reply(200, {ok: true, on: f.on, off_here: f.off_here, apply_id: f.next++});
  };
  if (f.mode === 'hold') return new Promise((res) => { f.held = () => { f.mode = 'ok'; res(done()); }; });
  return Promise.resolve(done());
};
"""
ORDER = "JSON.stringify([...document.querySelectorAll('section.setting')].map(s => s.id).filter(i => %s))"


class Base(unittest.TestCase):
    theme = "prototype-2.0"

    def setUp(self):
        self.s = Running(data_for=lambda code, archived=None: DATA.get(code), page_html=lambda: page.page_html(tempfile.mkdtemp(), theme=self.theme))
        self.addCleanup(self.s.close)
        self.s.httpd.app_settings = service(make_db(tempfile.mkdtemp(), cleanup=self.addCleanup))

    def show(self, cdp, tab, mode="ok", pre=""):
        sid = self.sid = navigate(cdp, self.s.port, for_project("#settings&p=ABC&s=claude"))
        js = lambda e: cdp.js(e, sid)          # noqa: E731
        js(FAKE % mode)
        if pre:
            js(pre)
        js("location.hash = '#dashboard&p=ABC'")
        wait(lambda: js("!document.querySelector('#ask-settings')"), 10)
        js("location.hash = '#settings&p=ABC&s=claude'")
        self.assertTrue(wait(lambda: js("!!document.querySelector('#ask-settings')"), 20))
        if tab == "all":
            js("document.querySelector('[data-ask-tab=all]').click()")
        return js

    def calls(self, js):
        return js("JSON.stringify(window.__f.calls)")


class Words(Base):
    def test_the_all_tab_says_the_files_line_and_the_heading(self):
        with chrome() as cdp:
            js = self.show(cdp, "all")
            self.assertTrue(wait(lambda: js("!!document.querySelector('[data-files-switch]')"), 10))
            self.assertEqual(js("document.querySelector('#ask-files-all h2').innerText"), "Files")
            self.assertEqual(js("document.querySelector('#ask-files-line').innerText"), FILES_LINE)
            self.assertFalse(js("!!document.querySelector('#ask-files-unavailable')"), "no unavailable line while the check works")

    def test_unavailable_says_so_keeps_the_line_and_draws_no_switch_for_each_kind_of_bad_answer(self):
        for mode in ("get500", "get_not_ok", "get500_ok", "on_not_bool"):
            for tab, sw in (("all", "[data-files-switch]"), ("project", "[data-files-here]")):
                with self.subTest(mode=mode, tab=tab), chrome() as cdp:
                    js = self.show(cdp, tab, mode)
                    self.assertTrue(wait(lambda: js("!!document.querySelector('#ask-files-unavailable')"), 10))
                    self.assertEqual(js("document.querySelector('#ask-files-unavailable').innerText"), UNAVAILABLE)
                    self.assertFalse(js(f"!!document.querySelector('{sw}')"))
                    if tab == "all":
                        self.assertEqual(js("document.querySelector('#ask-files-line').innerText"), FILES_LINE)

    def test_a_project_row_says_on_for_all_projects_with_a_switch_at_1400_and_900(self):
        with chrome() as cdp:
            js = self.show(cdp, "project")
            self.assertTrue(wait(lambda: js("!!document.querySelector('[data-files-here]')"), 10))
            self.assertEqual(js("document.querySelector('#ask-files-here-line').innerText"), "On for all projects. Turn it off here for ABC only.")
            self.assertEqual(js("document.querySelector('#ask-files-project .folder-now').innerText"), "Files")
            self.assertEqual(js("document.querySelector('[data-files-here]').getAttribute('aria-checked')"), "true")
            for w in WIDTHS:
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                self.assertTrue(wait(lambda: js("document.documentElement.scrollWidth <= window.innerWidth"), 10), f"no sideways scroll at {w}")

    def test_a_project_row_says_off_for_all_projects_and_has_no_switch_when_the_all_switch_is_off(self):
        with chrome() as cdp:
            js = self.show(cdp, "project", pre="window.__f.on = false")
            self.assertTrue(wait(lambda: js("!!document.querySelector('#ask-files-here-line')"), 10))
            self.assertEqual(js("document.querySelector('#ask-files-here-line').innerText"), "Off for all projects.")
            self.assertFalse(js("!!document.querySelector('[data-files-here]')"))

    def test_a_project_turned_off_here_shows_the_switch_off_and_turning_it_back_on_sends_off_here_false(self):
        with chrome() as cdp:
            js = self.show(cdp, "project", pre="window.__f.off_here = true")
            self.assertTrue(wait(lambda: js("!!document.querySelector('[data-files-here]')"), 10))
            self.assertEqual(js("document.querySelector('[data-files-here]').getAttribute('aria-checked')"), "false")
            js("document.querySelector('[data-files-here]').click()")
            self.assertTrue(wait(lambda: js("document.querySelector('[data-files-here]').getAttribute('aria-checked')") == "true", 10))
            js("document.querySelector('[data-files-here]').click()")
            self.assertTrue(wait(lambda: js("document.querySelector('[data-files-here]').getAttribute('aria-checked')") == "false", 10))
            self.assertEqual(self.calls(js), '[{"project":"ABC","off_here":false},{"project":"ABC","off_here":true}]')


class Changes(Base):
    def test_a_change_the_server_cannot_save_says_so_in_words_leaves_the_switch_and_offers_no_undo(self):
        with chrome() as cdp:
            js = self.show(cdp, "all", "post503")
            self.assertTrue(wait(lambda: js("!!document.querySelector('[data-files-switch]')"), 10))
            js("document.querySelector('[data-files-switch]').click()")
            self.assertTrue(wait(lambda: js("!!document.querySelector('#ask-files-all .pub-msg .error')"), 10))
            self.assertEqual(js("document.querySelector('#ask-files-all .pub-msg .error').innerText"), "Could not save that choice just now. Wait a moment and try again.")
            self.assertEqual(js("document.querySelector('[data-files-switch]').getAttribute('aria-checked')"), "true")
            self.assertFalse(js("!!document.querySelector('[data-files-undo]')"))
            self.assertEqual(js("document.querySelector('#ask-files-all .pub-msg').getAttribute('role')"), "alert")
            self.assertFalse(js("document.querySelector('[data-files-switch]').disabled"), "the switch is usable again")

    def test_the_next_change_clears_the_old_error(self):
        with chrome() as cdp:
            js = self.show(cdp, "all", "post503")
            self.assertTrue(wait(lambda: js("!!document.querySelector('[data-files-switch]')"), 10))
            js("document.querySelector('[data-files-switch]').click()")
            self.assertTrue(wait(lambda: js("!!document.querySelector('#ask-files-all .pub-msg .error')"), 10))
            js("window.__f.mode = 'ok'; document.querySelector('[data-files-switch]').click()")
            self.assertTrue(wait(lambda: js("!document.querySelector('#ask-files-all .pub-msg .error') && document.querySelector('[data-files-switch]').getAttribute('aria-checked') === 'false'"), 10))

    def test_a_refusal_with_a_code_shows_the_servers_own_words(self):
        with chrome() as cdp:
            js = self.show(cdp, "project", "post_known")
            self.assertTrue(wait(lambda: js("!!document.querySelector('[data-files-here]')"), 10))
            js("document.querySelector('[data-files-here]').click()")
            self.assertTrue(wait(lambda: js("!!document.querySelector('#ask-files-project .pub-msg .error')"), 10))
            self.assertEqual(js("document.querySelector('#ask-files-project .pub-msg .error').innerText"), "Another change is being saved. Try again in a moment.")

    def test_the_switch_and_the_undo_are_disabled_while_a_change_is_out_and_a_second_change_clears_the_old_error(self):
        with chrome() as cdp:
            js = self.show(cdp, "all", "hold")
            self.assertTrue(wait(lambda: js("!!document.querySelector('[data-files-switch]')"), 10))
            js("document.querySelector('[data-files-switch]').click()")
            self.assertTrue(wait(lambda: js("document.querySelector('[data-files-switch]').disabled"), 10), "busy: the switch is disabled while the change is out")
            self.assertEqual(js("document.querySelector('[data-files-switch]').getAttribute('aria-checked')"), "true", "not turned over before the server answers")
            js("document.querySelector('[data-files-switch]').click()")          # a click on a disabled button does nothing
            self.assertEqual(self.calls(js), '[{"on":false}]')
            js("window.__f.held()")
            self.assertTrue(wait(lambda: js("!document.querySelector('[data-files-switch]').disabled"), 10))
            self.assertEqual(js("document.querySelector('[data-files-switch]').getAttribute('aria-checked')"), "false")

    def test_undo_takes_the_change_back_and_the_undo_itself_has_no_undo(self):
        with chrome() as cdp:
            js = self.show(cdp, "all")
            self.assertTrue(wait(lambda: js("!!document.querySelector('[data-files-switch]')"), 10))
            js("document.querySelector('[data-files-switch]').click()")
            self.assertTrue(wait(lambda: js("!!document.querySelector('[data-files-undo]')"), 10))
            js("document.querySelector('[data-files-undo]').click()")
            self.assertTrue(wait(lambda: js("document.querySelector('[data-files-switch]').getAttribute('aria-checked')") == "true", 10))
            self.assertFalse(js("!!document.querySelector('[data-files-undo]')"), "the answer to an Undo carries a step number, and still no Undo is offered")
            self.assertEqual(self.calls(js), '[{"on":false},{"undo":7}]')


class Order(Base):
    def test_the_cards_come_in_the_ticket_order_on_both_tabs_at_1400_and_900(self):
        for tab, ids, want in (("all", ["ask-instructions-all-card", "ask-files-all", "ask-all-folders"], None),
                               ("project", ["ask-folders-card", "ask-instructions-own-card", "ask-files-project"], None)):
            with self.subTest(tab=tab), chrome() as cdp:
                js = self.show(cdp, tab)
                self.assertTrue(wait(lambda: js("!!document.querySelector('[data-files-switch],[data-files-here]')"), 10))
                for w in WIDTHS:
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                    cond = "[" + ",".join(repr(i) for i in ids) + "].indexOf(i) >= 0"
                    self.assertEqual(js(ORDER % cond), "[" + ",".join('"%s"' % i for i in ids) + "]", f"{tab} at {w}")


class Cards(Base):
    theme = None

    def test_cards_draws_no_files_card_on_either_tab_and_asks_nothing_of_the_files_route(self):
        for tab in ("all", "project"):
            with self.subTest(tab=tab), chrome() as cdp:
                js = self.show(cdp, tab)
                self.assertFalse(js("!!document.querySelector('#theme')"), "this is the Cards page")
                self.assertFalse(js("!!document.querySelector('#ask-files-all, #ask-files-project')"))
                self.assertEqual(js("JSON.stringify(window.__f.calls)"), "[]")


if __name__ == "__main__":
    unittest.main()
