"""#246 and #289: the arrow keys while the peek is open. Run: python3 dev/run_tests.py test_peek_arrows

Real browser at 1400 and 900 px with the test build. With the peek open, Up and Down step to the item before and after in the list it
was opened from (the same list Previous and Next use); the focus stays where it was (Close, Previous, Next), and is never left on a
button that has just turned off; Esc puts the focus on the row of the item shown. A plain arrow on a row still reaches the row and
the peek follows it; an arrow inside a box, on the width edge, on a tab, with a menu open, or with a modifier is left alone.
"""
import json
import unittest

import test_peek as TP
from test_server import chrome, wait
from test_work_filters import dblclick

KEYS = {"ArrowUp": (38, ""), "ArrowDown": (40, ""), "ArrowLeft": (37, ""), "ArrowRight": (39, ""), "Escape": (27, "")}


def key(cdp, sid, name):
    vk, text = KEYS[name]
    common = {"key": name, "code": name, "windowsVirtualKeyCode": vk}
    cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", **common}, sid)
    cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", **common}, sid)


class Arrows(unittest.TestCase):
    setUpClass = classmethod(TP.Browser.setUpClass.__func__)
    tearDownClass = classmethod(TP.Browser.tearDownClass.__func__)
    load_page = TP.Browser.load_page
    edit_mode = TP.Browser.edit_mode
    ids_on_page = TP.Browser.ids_on_page

    def shown(self, cdp, sid):
        return cdp.js("clarkPage.peek() && clarkPage.peek().id", sid)

    def on_close(self, cdp, sid):
        return cdp.js("document.activeElement.hasAttribute('data-pk-close')", sid)

    def open_by_double_click(self, cdp, sid, ids, at):
        dblclick(cdp, sid, f"#work tbody tr[data-id='{ids[at]}'] .c-item")
        self.assertTrue(wait(lambda: self.shown(cdp, sid) == ids[at]))
        self.assertTrue(wait(lambda: self.on_close(cdp, sid)), "focus went into the peek, on Close")

    def live(self, cdp, sid):
        return cdp.js("(document.querySelector('#peek [data-pk-live]') || {textContent: ''}).textContent", sid)

    def test_down_and_up_from_close_step_through_the_list_and_the_focus_stays(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                s, sid = self.load_page(cdp, width)
                ids = self.ids_on_page(cdp, sid)
                self.open_by_double_click(cdp, sid, ids, 1)
                length = cdp.js("history.length", sid)
                key(cdp, sid, "ArrowDown")
                self.assertTrue(wait(lambda: self.shown(cdp, sid) == ids[2]), "Down steps to the next item of the list")
                self.assertTrue(self.on_close(cdp, sid), "the focus stays on Close")
                key(cdp, sid, "ArrowUp")
                key(cdp, sid, "ArrowUp")
                self.assertTrue(wait(lambda: self.shown(cdp, sid) == ids[0]))
                self.assertEqual(cdp.js("history.length", sid), length, "stepping adds no history entry")
                self.assertTrue(self.on_close(cdp, sid))

    def test_the_ends_do_not_wrap_and_the_line_says_so(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                s, sid = self.load_page(cdp, width)
                ids = self.ids_on_page(cdp, sid)
                self.open_by_double_click(cdp, sid, ids, 0)
                key(cdp, sid, "ArrowUp")
                self.assertTrue(wait(lambda: "first" in self.live(cdp, sid).lower()), self.live(cdp, sid))
                self.assertEqual(self.shown(cdp, sid), ids[0], "Up at the first item stays on it")
                key(cdp, sid, "ArrowDown")
                self.assertTrue(wait(lambda: self.shown(cdp, sid) == ids[1]))
                self.assertIn(f"2 of {len(ids)}", self.live(cdp, sid))
                self.assertIn(ids[1], self.live(cdp, sid))
                cdp.js(f"clarkPage.openPeek({json.dumps(ids[-1])})", sid)
                self.assertTrue(wait(lambda: self.shown(cdp, sid) == ids[-1]))
                cdp.js("document.querySelector('[data-pk-close]').focus()", sid)
                key(cdp, sid, "ArrowDown")
                self.assertTrue(wait(lambda: "last" in self.live(cdp, sid).lower()), self.live(cdp, sid))
                self.assertEqual(self.shown(cdp, sid), ids[-1], "Down at the last item stays on it")

    def test_an_arrow_on_a_row_reaches_the_row_and_the_peek_follows_it_once(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                s, sid = self.load_page(cdp, width)
                ids = self.ids_on_page(cdp, sid)
                self.open_by_double_click(cdp, sid, ids, 1)
                cdp.js(f"document.querySelector(\"#work tbody tr[data-id='{ids[1]}']\").focus()", sid)
                key(cdp, sid, "ArrowDown")
                self.assertTrue(wait(lambda: cdp.js("document.activeElement.dataset.id", sid) == ids[2]), "the row's own handler moved the cursor")
                self.assertTrue(wait(lambda: self.shown(cdp, sid) == ids[2]), "the peek follows the cursor")
                self.assertEqual(cdp.js("document.activeElement.dataset.id", sid), ids[2], "the focus stays on the row")
                key(cdp, sid, "ArrowUp")
                self.assertTrue(wait(lambda: self.shown(cdp, sid) == ids[1]), "and follows it back, one step for one key")
                # focus that arrives without an arrow (Tab, a click away) does not move the peek
                cdp.js(f"document.querySelector(\"#work tbody tr[data-id='{ids[4]}']\").focus()", sid)
                cdp.js("new Promise(r => setTimeout(r, 150))", sid)
                self.assertEqual(self.shown(cdp, sid), ids[1])

    def test_esc_puts_the_focus_on_the_row_of_the_item_shown(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                s, sid = self.load_page(cdp, width)
                ids = self.ids_on_page(cdp, sid)
                self.open_by_double_click(cdp, sid, ids, 1)
                key(cdp, sid, "ArrowDown")
                key(cdp, sid, "ArrowDown")
                self.assertTrue(wait(lambda: self.shown(cdp, sid) == ids[3]))
                key(cdp, sid, "Escape")
                self.assertTrue(wait(lambda: self.shown(cdp, sid) is None))
                self.assertTrue(wait(lambda: cdp.js("document.activeElement.dataset.id", sid) == ids[3]), "focus is on the row the peek last showed")

    def test_a_button_that_turns_off_does_not_leave_the_focus_on_nothing(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                s, sid = self.load_page(cdp, width)
                ids = self.ids_on_page(cdp, sid)
                self.open_by_double_click(cdp, sid, ids, len(ids) - 2)
                cdp.js("document.querySelector('[data-pk-next]').focus()", sid)
                key(cdp, sid, "ArrowDown")
                self.assertTrue(wait(lambda: self.shown(cdp, sid) == ids[-1]))
                self.assertTrue(cdp.js("document.querySelector('[data-pk-next]').disabled", sid))
                self.assertTrue(wait(lambda: self.on_close(cdp, sid)), "the focus moved to Close, not to the page")

    def test_a_key_inside_a_box_on_the_edge_or_on_a_tab_is_left_alone(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                s, sid = self.load_page(cdp, width)
                self.edit_mode(cdp, sid)
                ids = self.ids_on_page(cdp, sid)
                target = ids[1]
                cdp.js(f"clarkPage.openPeek({json.dumps(target)})", sid)
                self.assertTrue(wait(lambda: self.on_close(cdp, sid)))
                # a tab: Right moves to the next tab (the tabs' own key), Down does nothing to the item
                cdp.js("document.querySelector('#peek [role=tab]').focus()", sid)
                key(cdp, sid, "ArrowDown")
                key(cdp, sid, "ArrowUp")
                cdp.js("new Promise(r => setTimeout(r, 100))", sid)
                self.assertEqual(self.shown(cdp, sid), target, "Up and Down on a tab do not step the item")
                key(cdp, sid, "ArrowRight")
                self.assertTrue(wait(lambda: cdp.js("document.activeElement.getAttribute('role')", sid) == "tab" and cdp.js("document.activeElement.id", sid) == "pk-tab-activity"), "Right is still the tabs' own key")
                cdp.js("document.querySelector('#pk-tab-details').click(); document.querySelector('#pk-tab-details').focus()", sid)
                # the width edge: Left still widens it, Down leaves the item alone
                cdp.js("document.querySelector('.pk-edge').focus()", sid)
                before = cdp.js("Number(document.querySelector('.pk-edge').getAttribute('aria-valuenow'))", sid)
                key(cdp, sid, "ArrowLeft")
                self.assertTrue(wait(lambda: cdp.js("Number(document.querySelector('.pk-edge').getAttribute('aria-valuenow'))", sid) > before), "Left on the edge is still the edge's")
                key(cdp, sid, "ArrowDown")
                cdp.js("new Promise(r => setTimeout(r, 100))", sid)
                self.assertEqual(self.shown(cdp, sid), target, "Down on the edge does not step the item")
                # a box: the words box keeps its arrows (the caret moves, the item does not change)
                cdp.js("document.querySelector('[data-sneak-open]').click()", sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.sn-in')", sid)))
                cdp.js("(() => { const i = document.querySelector('.sn-in'); i.value = 'abc'; i.dispatchEvent(new Event('input', {bubbles: true})); i.focus(); i.setSelectionRange(3, 3); })()", sid)
                key(cdp, sid, "ArrowLeft")
                self.assertEqual(cdp.js("document.querySelector('.sn-in').selectionStart", sid), 2, "Left moved the caret in the box")
                key(cdp, sid, "ArrowDown")
                key(cdp, sid, "ArrowUp")
                cdp.js("new Promise(r => setTimeout(r, 100))", sid)
                self.assertEqual(self.shown(cdp, sid), target, "Up and Down in the box do not step the item")
                self.assertEqual(cdp.js("document.querySelector('.sn-in').value", sid), "abc")

    def test_a_menu_open_or_a_modifier_held_leaves_the_arrow_alone(self):
        with chrome() as cdp:
            s, sid = self.load_page(cdp, 1400)
            ids = self.ids_on_page(cdp, sid)
            self.open_by_double_click(cdp, sid, ids, 1)
            fire = "document.activeElement.dispatchEvent(new KeyboardEvent('keydown', {key: 'ArrowDown', bubbles: true, cancelable: true, %s}))"
            for mod in ("shiftKey: true", "ctrlKey: true", "metaKey: true", "altKey: true"):
                cdp.js(fire % mod, sid)
            cdp.js("(() => { const m = document.createElement('div'); m.setAttribute('role', 'menu'); m.id = 'fake-menu'; document.body.appendChild(m); })()", sid)
            key(cdp, sid, "ArrowDown")
            cdp.js("new Promise(r => setTimeout(r, 100))", sid)
            self.assertEqual(self.shown(cdp, sid), ids[1], "no step with a modifier or with a menu open")
            cdp.js("document.getElementById('fake-menu').remove()", sid)
            key(cdp, sid, "ArrowDown")
            self.assertTrue(wait(lambda: self.shown(cdp, sid) == ids[2]), "and it steps again once the menu is gone")


if __name__ == "__main__":
    unittest.main()
