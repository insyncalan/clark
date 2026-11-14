"""Row 1082, mutation audit: tests that kill the changes to PeekLatestHistory that the first test file let through.
Run: python3 dev/run_tests.py test_peek_history_1082_mutants

Each test names the change it guards: the link on an item that has no Latest update box, the words of a row with no new value, no name and no
way, the "how" and the time on a row, and the list that reads again when the data is replaced. Page in a real browser at 1400 and 900 px.
"""
import json
import unittest

from _paths import ROOT  # noqa: F401
from test_server import chrome, wait  # noqa: E402
import test_peek_history_1082 as base  # noqa: E402

BTN, ROWS = base.BTN, base.ROWS


class Mutants(unittest.TestCase):
    load = base.Browser.load
    press = base.Browser.press
    stub = base.Browser.stub

    def test_an_item_that_is_not_an_action_has_no_history_link(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.load(cdp, width)
                cdp.js("clarkPage.closePeek()", sid)
                cdp.js("clarkPage.openPeek('TUL-007')", sid)
                self.assertTrue(wait(lambda: "TUL-007" in (cdp.js("(document.querySelector('#peek') || {}).textContent || ''", sid) or "")))
                self.assertTrue(wait(lambda: not cdp.js("!!document.querySelector('[data-pk-lh]')", sid)), "a risk has no Latest update box and no history")
                self.assertEqual(cdp.js("document.querySelectorAll('[data-pk-lh]').length", sid), 0)

    def test_a_row_without_a_value_a_name_or_a_way_says_so_and_a_full_row_shows_its_way_and_time(self):
        rows = ('[{field:"Latest update",kind:"Changed",to:"",who:"",how:"",when_text:"WHEN-ONE",step:1},'
                '{field:"Latest update",kind:"Changed",to:"Newer words",who:"Ann Example",how:"from Peek",when_text:"WHEN-TWO",step:2}]')
        answer = "() => Promise.resolve(new Response(JSON.stringify({ok:true,activity:{rows:" + rows + "}})))"
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.load(cdp, width)
                self.stub(cdp, sid, answer)
                self.press(cdp, sid)
                self.assertTrue(wait(lambda: cdp.js(f"document.querySelectorAll({json.dumps(ROWS)}).length", sid) == 2))
                texts = cdp.js(f"[...document.querySelectorAll({json.dumps(ROWS)})].map(r => r.textContent)", sid)
                texts = sorted(texts, key=lambda t: "WHEN-ONE" in t)
                full, bare = texts
                self.assertIn("Ann Example", full)
                self.assertIn("from Peek", full)
                self.assertIn("WHEN-TWO", full)
                self.assertIn("Newer words", full)
                self.assertIn("WHEN-ONE", bare)
                self.assertIn("Someone on this computer", bare, "no name: the stand-in words")
                self.assertTrue(bare.endswith("nothing"), "no new value: the word nothing")
                self.assertNotIn(" · from", bare)
                self.assertNotIn("undefined", bare + full)

    def test_an_open_list_reads_again_when_the_data_is_replaced(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.load(cdp, width)
                cdp.js("window.__phase = 'FIRST-WORDS'; (f => { window.fetch = (u, o) => String(u).includes('/api/activity') ? Promise.resolve(new Response(JSON.stringify({ok:true,activity:{rows:[{field:'Latest update',kind:'Changed',to:window.__phase,who:'Ann Example',how:'',when_text:'t',step:1}]}}))) : f(u, o); })(window.fetch)", sid)
                self.press(cdp, sid)
                self.assertTrue(wait(lambda: "FIRST-WORDS" in (cdp.js(f"(document.querySelector({json.dumps(ROWS)}) || {{}}).textContent || ''", sid) or "")))
                cdp.js("window.__phase = 'SECOND-WORDS'; clarkPage.changeData(d => ({ ...d }))", sid)
                self.assertTrue(wait(lambda: "SECOND-WORDS" in (cdp.js(f"(document.querySelector({json.dumps(ROWS)}) || {{}}).textContent || ''", sid) or "")), "the open list is read again after a change anywhere")


    def test_the_panel_names_itself_the_button_points_at_it_and_the_list_takes_the_keyboard(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.load(cdp, width)
                self.press(cdp, sid)
                self.assertTrue(wait(lambda: cdp.js(f"document.querySelectorAll({json.dumps(ROWS)}).length", sid) == 7))
                got = cdp.js("(b => { const p = document.querySelector('[data-pk-lh-panel]'), l = document.querySelector('[data-pk-lh-list]'); return [b.getAttribute('aria-controls'), p.id, p.getAttribute('aria-label'), l.tabIndex, l.tagName, l.getAttribute('aria-label')]; })(document.querySelector('[data-pk-lh-btn]'))", sid)
                self.assertEqual(got[0], got[1], "the button controls the panel")
                self.assertTrue(got[1])
                self.assertEqual(got[2], "Latest update history")
                self.assertEqual(got[3], 0, "the scrolling list is reached by Tab")
                self.assertEqual(got[4], "OL")
                self.assertEqual(got[5], "Latest update changes, newest first")

    def test_the_words_wait_while_the_history_is_read(self):
        with chrome() as cdp:
            sid = self.load(cdp, 1400)
            cdp.js("(f => { window.fetch = (u, o) => String(u).includes('/api/activity') ? new Promise(() => {}) : f(u, o); })(window.fetch)", sid)
            self.press(cdp, sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-pk-lh-loading]')", sid)))
            self.assertEqual(cdp.js("document.querySelector('[data-pk-lh-loading]').textContent", sid), "Reading the history\u2026")

    def test_a_long_word_stays_inside_its_row_and_each_row_has_its_line_and_the_link_sits_at_the_right(self):
        word = "W" * 120
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.load(cdp, width)
                cdp.js("(f => { window.fetch = (u, o) => String(u).includes('/api/activity') ? Promise.resolve(new Response(JSON.stringify({ok:true,activity:{rows:[{field:'Latest update',kind:'Changed',to:'" + word + "',who:'Ann',how:'',when_text:'t',step:1},{field:'Latest update',kind:'Changed',to:'two',who:'Ann',how:'',when_text:'t',step:2}]}}))) : f(u, o); })(window.fetch)", sid)
                self.press(cdp, sid)
                self.assertTrue(wait(lambda: cdp.js(f"document.querySelectorAll({json.dumps(ROWS)}).length", sid) == 2))
                row = cdp.js(f"(r => [r.scrollWidth <= r.clientWidth + 1, getComputedStyle(r).borderTopWidth, getComputedStyle(r).borderTopStyle])(document.querySelector({json.dumps(ROWS)}))", sid)
                self.assertTrue(row[0], "a long unbroken word wraps inside the row")
                self.assertEqual(row[1:], ["1px", "solid"], "a light line above every row")
                right = cdp.js("(b => { const q = b.getBoundingClientRect(), p = document.querySelector('#peek').getBoundingClientRect(); return [q.right, p.right, q.left, p.left]; })(document.querySelector('[data-pk-lh-btn]'))", sid)
                self.assertGreater(right[2] - right[3], (right[1] - right[3]) / 2, "the link sits on the right half of the peek")

    def test_another_item_opens_with_its_history_closed(self):
        with chrome() as cdp:
            sid = self.load(cdp, 1400)
            self.press(cdp, sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-pk-lh-panel]')", sid)))
            cdp.js("clarkPage.openPeek('TUL-A-001')", sid)
            self.assertTrue(wait(lambda: "TUL-A-001" in (cdp.js("(document.querySelector('#peek') || {}).textContent || ''", sid) or "")))
            self.assertTrue(wait(lambda: not cdp.js("!!document.querySelector('[data-pk-lh-panel]')", sid)), "the next item starts with its history shut")
            self.assertEqual(cdp.js("document.querySelector('[data-pk-lh-btn]').textContent", sid), "Show history")


if __name__ == "__main__":
    unittest.main()
