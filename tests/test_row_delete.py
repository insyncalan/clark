"""Item 658, the Delete entry on a work item: in the row menu and in the peek, with the question, the toast and Undo.

Run: python3 dev/run_tests.py test_row_delete
Drives the committed page against the real server in headless Chrome (set CLARK_CHROME to its path), at 1400 and 900 px, in light and dark.
The words are the approved ones: the question "Delete <ID>? This removes it from your project record. You can undo it straight away." with Delete and
Cancel, and the toast "<ID> deleted." with Undo.
"""
import json
import unittest

from _paths import SRC

from test_server import chrome  # noqa: E402
from test_row_menu import right_click  # noqa: E402
from test_work_filters import click  # noqa: E402
import test_work_board_page as board  # noqa: E402
import test_multi_select as ms  # noqa: E402

PAGE_SRC = SRC / "clark" / "page" / "src"
QUESTION = "Delete %s? This removes it from your project record. You can undo it straight away."
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
                    self.assertNotIn("brought back", d["q"])
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
                    self.assertEqual(len(self.query("SELECT 1 FROM actions WHERE id = ?", a)), 1, where)
                    self.assertTrue(cdp.js("document.documentElement.scrollWidth <= window.innerWidth", sid), where)

    def test_the_peek_has_the_same_delete_and_it_closes_with_the_item(self):
        a = self.id_of("Order the laptops")
        with chrome() as cdp:
            sid = self.visit(cdp)
            self.open_menu(cdp, sid, a)
            click(cdp, sid, "[data-rm=peek]")
            self.until(cdp, sid, f"!!document.querySelector('#peek[data-peek=\"{a}\"] [data-pk-delete]')", "the peek")
            click(cdp, sid, "[data-pk-delete]")
            self.assertEqual(self.dialog(cdp, sid)["q"], QUESTION % a)
            click(cdp, sid, "[data-bask=yes]")
            self.assertEqual(self.wait_toast(cdp, sid, "done")["text"], f"{a} deleted.")
            self.until(cdp, sid, "!document.querySelector('#peek')", "the peek to close")
            self.assertEqual(self.query("SELECT 1 FROM actions WHERE id = ?", a), [])

    def test_the_old_sentence_is_nowhere_in_the_page(self):
        for f in PAGE_SRC.rglob("*"):
            if f.suffix in (".js", ".jsx"):
                self.assertNotIn("cannot be brought back", f.read_text(encoding="utf-8"), f.name)


if __name__ == "__main__":
    unittest.main()
