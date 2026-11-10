"""Row 1071: the filter tabs can be picked up and moved left or right (no handle); the tab menu has Rename view, Move view, Duplicate view
and Delete view; Move view is Left and Right keys with Enter or Esc to finish; Delete view gives an Undo message. The order is kept per project.

Run (one browser file at a time): python3 dev/run_tests.py test_filter_tabs_drag
"""
import unittest

from _new_page import reload_to_new_page_cdp
from test_server import chrome
from test_work_filters import click, key
from test_filter_line_page import Line as _Line, wait


class Tabs(_Line):
    IDS = "[...document.querySelectorAll('.vtab')].map(b => b.dataset.viewId)"
    NAMES = "[...document.querySelectorAll('.vtab')].map(b => b.querySelector('span').textContent)"

    def fresh(self, cdp):
        s = self.serve()
        sid = self.load(cdp, s.port)
        cdp.js("localStorage.clear(); sessionStorage.clear()", sid)
        reload_to_new_page_cdp(cdp, sid)
        self.assertTrue(wait(lambda: len(cdp.js(self.IDS, sid) or []) == 8), "eight tabs")
        return sid

    def mouse(self, cdp, sid, kind, x, y, **kw):
        cdp.call("Input.dispatchMouseEvent", {"type": kind, "x": x, "y": y, **kw}, sid)

    def centre(self, cdp, sid, view):
        cdp.js("document.querySelector('.vtab[data-view-id=%s]').scrollIntoView({inline: 'center', block: 'nearest', behavior: 'instant'})" % view, sid)
        return cdp.js("(() => { const r = document.querySelector('.vtab[data-view-id=%s]').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; })()" % view, sid)

    def drag(self, cdp, sid, view, onto):
        """Press on a tab, move in steps over another tab, release: a real mouse sequence."""
        x0, y0 = self.centre(cdp, sid, view)
        x1, y1 = self.centre(cdp, sid, onto)
        self.mouse(cdp, sid, "mouseMoved", x0, y0)
        self.mouse(cdp, sid, "mousePressed", x0, y0, button="left", buttons=1, clickCount=1)
        for i in range(1, 11):
            self.mouse(cdp, sid, "mouseMoved", x0 + (x1 - x0) * i / 10, y0, buttons=1)
        self.mouse(cdp, sid, "mouseReleased", x1, y0, button="left", buttons=0, clickCount=1)

    def menu(self, cdp, sid, kind):
        click(cdp, sid, "#viewTabMenu")
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#viewTabMenuList')", sid)))
        click(cdp, sid, "#viewTabMenuList [data-kind=%s]" % kind)

    def test_a_tab_is_dragged_to_the_right_and_kept(self):
        with chrome() as cdp:
            sid = self.fresh(cdp)
            before = cdp.js("document.querySelector('.vtab[aria-pressed=true]').dataset.viewId", sid)
            self.drag(cdp, sid, "core-actions", "core-decisions")
            self.assertTrue(wait(lambda: cdp.js(self.IDS, sid)[:4] == ["core-open", "core-risks", "core-decisions", "core-actions"]), cdp.js(self.IDS, sid))
            self.assertEqual(cdp.js("document.querySelector('.vtab[aria-pressed=true]').dataset.viewId", sid), before, "a drag does not choose the tab")
            reload_to_new_page_cdp(cdp, sid)
            self.assertTrue(wait(lambda: (cdp.js(self.IDS, sid) or [])[:4] == ["core-open", "core-risks", "core-decisions", "core-actions"]), "kept in this browser")
            cdp.js("localStorage.clear(); sessionStorage.clear()", sid)

    def test_a_tab_is_dragged_to_the_left(self):
        with chrome() as cdp:
            sid = self.fresh(cdp)
            self.drag(cdp, sid, "mine", "core-actions")
            self.assertTrue(wait(lambda: cdp.js(self.IDS, sid)[1] == "mine"), cdp.js(self.IDS, sid))
            cdp.js("localStorage.clear(); sessionStorage.clear()", sid)

    def test_a_click_without_a_move_still_chooses_the_tab(self):
        with chrome() as cdp:
            sid = self.fresh(cdp)
            x, y = self.centre(cdp, sid, "overdue")
            self.mouse(cdp, sid, "mousePressed", x, y, button="left", buttons=1, clickCount=1)
            self.mouse(cdp, sid, "mouseReleased", x, y, button="left", buttons=0, clickCount=1)
            self.assertTrue(wait(lambda: cdp.js("document.querySelector('.vtab[aria-pressed=true]').dataset.viewId", sid) == "overdue"))
            self.assertEqual(cdp.js(self.IDS, sid)[5], "overdue", "and it did not move")
            cdp.js("localStorage.clear(); sessionStorage.clear()", sid)

    def test_move_view_by_keys(self):
        with chrome() as cdp:
            sid = self.fresh(cdp)
            self.menu(cdp, sid, "move")
            self.assertTrue(wait(lambda: cdp.js("document.activeElement.classList.contains('vtab') && document.activeElement.dataset.viewId", sid) == "core-open"), "the tab has the focus")
            self.assertEqual(cdp.js("document.activeElement.dataset.moving", sid), "true", "and a focus ring while it moves")
            self.assertFalse(cdp.js("!!document.querySelector('.vmove')", sid), "no bar")
            key(cdp, sid, "ArrowRight")
            key(cdp, sid, "ArrowRight")
            self.assertTrue(wait(lambda: cdp.js(self.IDS, sid)[:3] == ["core-actions", "core-risks", "core-open"]), cdp.js(self.IDS, sid))
            self.assertEqual(cdp.js("document.activeElement.dataset.viewId", sid), "core-open", "the focus stays on the tab")
            key(cdp, sid, "ArrowLeft")
            self.assertTrue(wait(lambda: cdp.js(self.IDS, sid)[:3] == ["core-actions", "core-open", "core-risks"]))
            key(cdp, sid, "Enter")
            self.assertTrue(wait(lambda: not cdp.js("document.activeElement.dataset.moving", sid)))
            key(cdp, sid, "ArrowRight")
            self.assertEqual(cdp.js(self.IDS, sid)[:3], ["core-actions", "core-open", "core-risks"], "Enter finished it")
            self.menu(cdp, sid, "move")
            self.assertTrue(wait(lambda: cdp.js("document.activeElement.dataset.moving", sid) == "true"))
            key(cdp, sid, "ArrowLeft")
            key(cdp, sid, "Escape")
            self.assertTrue(wait(lambda: not cdp.js("document.activeElement.dataset.moving", sid)), "Esc finishes too")
            self.assertEqual(cdp.js(self.IDS, sid)[:3], ["core-open", "core-actions", "core-risks"], "and keeps the place it reached")
            reload_to_new_page_cdp(cdp, sid)
            self.assertTrue(wait(lambda: (cdp.js(self.IDS, sid) or [])[:3] == ["core-open", "core-actions", "core-risks"]))
            cdp.js("localStorage.clear(); sessionStorage.clear()", sid)

    def test_duplicate_view(self):
        with chrome() as cdp:
            sid = self.fresh(cdp)
            click(cdp, sid, ".vtab[data-view-id=overdue]")
            self.menu(cdp, sid, "duplicate")
            self.assertTrue(wait(lambda: "Overdue copy" in cdp.js(self.NAMES, sid)), cdp.js(self.NAMES, sid))
            names = cdp.js(self.NAMES, sid)
            self.assertEqual(names[names.index("Overdue") + 1], "Overdue copy", "right after the original")
            cdp.js("localStorage.clear(); sessionStorage.clear()", sid)

    def test_delete_view_gives_an_undo_that_puts_it_back_in_place(self):
        with chrome() as cdp:
            sid = self.fresh(cdp)
            click(cdp, sid, ".vtab[data-view-id=core-risks]")
            self.menu(cdp, sid, "delete")
            self.assertTrue(wait(lambda: "core-risks" not in cdp.js(self.IDS, sid)))
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-undo]')", sid)), "an Undo message")
            click(cdp, sid, "[data-undo]")
            self.assertTrue(wait(lambda: cdp.js(self.IDS, sid)[2] == "core-risks"), cdp.js(self.IDS, sid))
            self.assertEqual(len(cdp.js(self.IDS, sid)), 8)
            cdp.js("localStorage.clear(); sessionStorage.clear()", sid)


if __name__ == "__main__":
    unittest.main()
