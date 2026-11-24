"""Item 658, the Delete entry on a work item: in the row menu and in the peek, with the question, the toast and Undo.

Run: python3 dev/run_tests.py test_row_delete
Drives the committed page against the real server in headless Chrome (set CLARK_CHROME to its path), at 1400 and 900 px, in light and dark.
The words are the approved ones: the question "Delete <ID>? This removes it from your project record." with Delete and
Cancel, and the toast "<ID> deleted." with Undo.
"""
import json
import unittest

from _demo import USER

from test_server import chrome  # noqa: E402
from test_row_menu import right_click  # noqa: E402
from test_work_filters import click, set_line  # noqa: E402
import test_work_board_page as board  # noqa: E402
import test_multi_select as ms  # noqa: E402

QUESTION = "Delete %s? This removes it from your project record."
ROW = "tr[data-id='%s']"


class DeleteItem(board.Base):
    def go_dark(self, cdp, sid):
        cdp.js("document.documentElement.dataset.theme = 'dark'", sid)
        self.until(cdp, sid, "getComputedStyle(document.body).backgroundColor !== 'rgb(255, 255, 255)'", "the page went dark")

    def open_menu(self, cdp, sid, a):
        right_click(cdp, sid, ROW % a)
        self.until(cdp, sid, "!!document.querySelector('.rowmenu [role=menuitem]')", "the menu")
        self.until(cdp, sid, "document.querySelector('.rowmenu').getAnimations({subtree: true}).length === 0", "the menu to settle")

    def dialog(self, cdp, sid):
        self.until(cdp, sid, "!!document.querySelector('[role=alertdialog] .bask-q')", "the question")
        return cdp.js("(() => ({q: document.querySelector('.bask-q').textContent, b: [...document.querySelectorAll('.bask-b button')].map(b => b.textContent)}))()", sid)

    def readable(self, cdp, sid, selector, where):
        got = cdp.js("[...document.querySelectorAll(" + json.dumps(selector) + ")].map(e => {"
                     " let b = e, bg = 'rgba(0, 0, 0, 0)';"
                     " while (b && /rgba\\(.*, 0\\)$|transparent/.test(bg = getComputedStyle(b).backgroundColor)) b = b.parentElement;"
                     " return [e.textContent.trim(), getComputedStyle(e).color, bg]; })", sid)
        self.assertTrue(got, where)
        for text, fg, bg in got:
            self.assertGreaterEqual(ms.contrast(fg, bg), 4.5, f"{where}: {text!r} is {fg} on {bg}")

    def test_cancel_does_nothing_delete_removes_the_row_and_undo_brings_it_back(self):
        a = self.id_of("Order the laptops")
        for width in (1400, 900):
            for dark in (False, True):
                where = f"{width} {'dark' if dark else 'light'}"
                with self.subTest(where), chrome() as cdp:
                    sid = self.visit(cdp, width=width)
                    if dark:
                        self.go_dark(cdp, sid)
                    before = self.steps()
                    self.open_menu(cdp, sid, a)
                    names = cdp.js("[...document.querySelectorAll('.rowmenu [role=menuitem] b')].map(b => b.textContent)", sid)
                    self.assertEqual(names[-1], "Delete", where)
                    click(cdp, sid, "[data-rm=delete]")
                    d = self.dialog(cdp, sid)
                    self.assertEqual(d, {"q": QUESTION % a, "b": ["Delete", "Cancel"]}, where)
                    self.readable(cdp, sid, ".bask-q, .bask-b button", where)
                    click(cdp, sid, "[data-bask=no]")                                   # Cancel: nothing happens
                    self.until(cdp, sid, "!document.querySelector('[role=alertdialog]')", "the question to close")
                    self.assertEqual((self.steps(), len(self.query("SELECT 1 FROM actions WHERE id = ?", a))), (before, 1), where)
                    self.assertTrue(cdp.js(f"!!document.querySelector(\"{ROW % a}\")", sid), where)
                    self.open_menu(cdp, sid, a)
                    click(cdp, sid, "[data-rm=delete]")
                    self.dialog(cdp, sid)
                    click(cdp, sid, "[data-bask=yes]")                                  # Delete
                    t = self.wait_toast(cdp, sid, "done")
                    self.assertEqual((t["text"], t["undo"]), (f"{a} deleted.", True), where)
                    self.until(cdp, sid, f"!document.querySelector(\"{ROW % a}\")", f"{where}: the row to leave")
                    self.assertEqual((self.steps(), self.query("SELECT 1 FROM actions WHERE id = ?", a)), (before + 1, []), where)
                    self.readable(cdp, sid, ".toast .toast-text, .toast [data-undo]", where + " toast")
                    click(cdp, sid, "[data-undo]")
                    self.until(cdp, sid, f"!!document.querySelector(\"{ROW % a}\")", f"{where}: the row to come back")
                    self.assertEqual(self.wait_toast(cdp, sid, "done")["text"], f"{a} is back.", where)
                    self.assertEqual(len(self.query("SELECT 1 FROM actions WHERE id = ?", a)), 1, where)
                    self.assertTrue(cdp.js("document.documentElement.scrollWidth <= window.innerWidth", sid), where)

    def test_the_peek_has_the_same_delete_and_it_closes_with_the_item(self):
        a = self.id_of("Order the laptops")
        with chrome() as cdp:
            sid = self.visit(cdp)
            before = self.steps()
            self.open_menu(cdp, sid, a)
            click(cdp, sid, "[data-rm=peek]")
            self.until(cdp, sid, f"!!document.querySelector('#peek[data-peek=\"{a}\"] [data-pk-delete]')", "the peek")
            click(cdp, sid, "[data-pk-delete]")
            d = self.dialog(cdp, sid)
            self.assertEqual(d, {"q": QUESTION % a, "b": ["Delete", "Cancel"]})
            click(cdp, sid, "[data-bask=no]")                                           # Cancel: nothing happens, the peek stays
            self.until(cdp, sid, "!document.querySelector('[role=alertdialog]')", "the question to close")
            self.assertEqual((self.steps(), len(self.query("SELECT 1 FROM actions WHERE id = ?", a))), (before, 1))
            self.assertTrue(cdp.js(f"!!document.querySelector('#peek[data-peek=\"{a}\"]')", sid))
            click(cdp, sid, "[data-pk-delete]")
            self.dialog(cdp, sid)
            click(cdp, sid, "[data-bask=yes]")
            t = self.wait_toast(cdp, sid, "done")
            self.assertEqual((t["text"], t["undo"]), (f"{a} deleted.", True))
            self.until(cdp, sid, "!document.querySelector('#peek')", "the peek to close")
            self.assertEqual((self.steps(), self.query("SELECT 1 FROM actions WHERE id = ?", a)), (before + 1, []))
            click(cdp, sid, "[data-undo]")
            self.until(cdp, sid, f"!!document.querySelector(\"{ROW % a}\")", "the row to come back")
            self.assertEqual(self.wait_toast(cdp, sid, "done")["text"], f"{a} is back.")
            self.assertEqual(len(self.query("SELECT 1 FROM actions WHERE id = ?", a)), 1)

    def test_delete_is_in_the_warning_colour(self):
        a = self.id_of("Order the laptops")
        with chrome() as cdp:
            sid = self.visit(cdp)
            self.open_menu(cdp, sid, a)
            red = cdp.js("(() => { const t = document.createElement('i'); t.style.color = 'var(--status-red-text)'; document.body.append(t); const c = getComputedStyle(t).color; t.remove(); return c; })()", sid)
            got = cdp.js("(() => { const d = document.querySelector('[data-rm=delete]'), o = document.querySelector('[data-rm=archive]'); return [d.classList.contains('danger'), getComputedStyle(d).color, getComputedStyle(o).color]; })()", sid)
            self.assertTrue(got[0])
            self.assertEqual(got[1], red)
            self.assertNotEqual(got[2], red)

    def test_an_archived_item_has_no_delete_in_its_row_or_its_peek(self):
        a = self.id_of("Order the laptops")
        with self.store.step("dashboard", USER) as st:
            st.archive("actions", a)
        with chrome() as cdp:
            sid = self.visit(cdp)
            set_line(cdp, sid, "is:archived")
            self.until(cdp, sid, f"!!document.querySelector(\"#archived-list tr[data-arch-id='{a}']\")", "the archived row")
            right_click(cdp, sid, f"#archived-list tr[data-arch-id='{a}']")             # its rows open no row menu
            cdp.js("new Promise(r => setTimeout(r, 400))", sid)
            self.assertFalse(cdp.js("!!document.querySelector('.rowmenu, [data-rm=delete]')", sid))
            click(cdp, sid, f"#archived-list tr[data-arch-id='{a}']")
            self.until(cdp, sid, f"document.querySelector('#peek-archived')?.dataset.peekArchived === '{a}'", "the archived peek")
            self.assertTrue(cdp.js("[...document.querySelectorAll('#peek-archived button')].some(b => /Restore/.test(b.textContent))", sid))
            self.assertFalse(cdp.js("!!document.querySelector('[data-pk-delete]') || [...document.querySelectorAll('#peek-archived button')].some(b => /Delete/i.test(b.textContent + (b.getAttribute('aria-label') || '') + (b.title || '')))", sid))

    def test_the_peek_more_actions_menu_ends_with_delete_in_the_warning_colour_and_asks_the_same_question(self):
        a = self.id_of("Order the laptops")
        for width in (1400, 900):
            with self.subTest(width), chrome() as cdp:
                sid = self.visit(cdp, width=width)
                before = self.steps()
                self.open_menu(cdp, sid, a)
                click(cdp, sid, "[data-rm=peek]")
                self.until(cdp, sid, f"!!document.querySelector('#peek[data-peek=\"{a}\"] #pk-more')", "the peek")
                self.assertEqual(cdp.js("(() => { const b = document.getElementById('pk-more'); return [b.getAttribute('aria-label'), b.title, !!document.querySelector('[data-pk-delete]')]; })()", sid), ["More actions", "More actions", True])
                click(cdp, sid, "#pk-more")
                self.until(cdp, sid, "!!document.querySelector('[role=menu] [role=menuitem]')", "the menu")
                self.until(cdp, sid, "document.querySelector('[role=menu]').getAnimations({subtree: true}).length === 0", "the menu to settle")
                got = cdp.js("(() => { const m = [...document.querySelectorAll('[role=menu] [role=menuitem]')]; return [m.map(b => b.textContent.trim()), m[m.length - 1].classList.contains('danger')]; })()", sid)
                self.assertEqual(got, [["Duplicate", "Archive", "Delete"], True])
                click(cdp, sid, "[role=menu] [data-kind=delete]")
                self.assertEqual(self.dialog(cdp, sid), {"q": QUESTION % a, "b": ["Delete", "Cancel"]})
                click(cdp, sid, "[data-bask=no]")
                self.until(cdp, sid, "!document.querySelector('[role=alertdialog]')", "the question to close")
                self.assertEqual((self.steps(), len(self.query("SELECT 1 FROM actions WHERE id = ?", a))), (before, 1))
                self.until(cdp, sid, "document.activeElement && document.activeElement.id === 'pk-more'", "the focus to come back to the More actions button")
                click(cdp, sid, "#pk-more")
                self.until(cdp, sid, "!!document.querySelector('[role=menu] [data-kind=delete]')", "the menu")
                self.until(cdp, sid, "document.querySelector('[role=menu]').getAnimations({subtree: true}).length === 0", "the menu to settle")
                click(cdp, sid, "[role=menu] [data-kind=delete]")
                self.dialog(cdp, sid)
                click(cdp, sid, "[data-bask=yes]")
                self.assertEqual(self.wait_toast(cdp, sid, "done")["text"], f"{a} deleted.")
                self.until(cdp, sid, "!document.querySelector('#peek')", "the peek to close")
                self.assertEqual(self.query("SELECT 1 FROM actions WHERE id = ?", a), [])
                click(cdp, sid, "[data-undo]")
                self.until(cdp, sid, f"!!document.querySelector(\"{ROW % a}\")", "the row to come back")


if __name__ == "__main__":
    unittest.main()
