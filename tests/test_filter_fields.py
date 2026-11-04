"""#640: the filter line's field list, the x that clears it, the five core tabs and the open tab's ▾ with "New view", in the real page.

Run: CLARK_CHROME=... python3 dev/run_tests.py test_filter_fields
Drives the committed page over the demo store in headless Chrome with real mouse and key events, at 1400 and 900 px, in light and
dark. The prototype it follows is PR 545 (system/prototype, branch pm-640-prototype). Required: fails, never skips, without Chrome.
"""
import json
import unittest

from _paths import ROOT  # noqa: F401
from _new_page import reload_to_new_page_cdp
from test_filter_line_page import CORE, INPUT, SIZES, THEMES, Line
from test_server import chrome, wait
from test_work_filters import click, expect, key

FIELDS = ["is:", "type:", "status:", "owner:", "priority:", "due:", "workstream:", "usecase:", "milestone:", "client:", "no:"]
# The plain words of the field list, pinned (the prototype's notes).
NOTES = {"is:": ("Is", "Open, closed, overdue, not reviewed…"), "status:": ("Status", "Where the item has got to"),
         "owner:": ("Owner", "Who it is with"), "due:": ("Due", "Overdue, today, in the next 7 days…"), "no:": ("No", "Has no owner, date, workstream…")}
LINES = {"core-open": ("open", "all"), "core-actions": ("open", "action"), "core-decisions": ("open", "decision"), "core-all": ("all", "all")}


def both():
    for width in SIZES:
        for theme in THEMES:
            yield width, theme


class Fields(Line):
    def expanded(self, cdp, sid):
        return cdp.js("document.querySelector('#fline-input').getAttribute('aria-expanded')", sid)

    def hints(self, cdp, sid):
        return cdp.js("getComputedStyle(document.querySelector('.fhints')).visibility", sid)

    def x(self, cdp, sid):
        return cdp.js("!!document.querySelector('#fline-clear')", sid)

    def test_a_click_into_the_empty_box_lists_the_fields_and_picking_one_shows_its_values(self):
        s = self.serve()
        for width, theme in both():
            with self.subTest(width=width, theme=theme), chrome() as cdp:
                sid = self.load(cdp, s.port, width, theme=theme)
                rows = self.rows(cdp, sid)
                self.assertEqual(self.expanded(cdp, sid), "false")
                self.focus(cdp, sid)
                self.assertTrue(wait(lambda: self.listed(cdp, sid) == FIELDS), self.listed(cdp, sid))
                self.assertEqual(self.expanded(cdp, sid), "true")
                self.assertEqual(cdp.js("document.querySelector('#fline-list').getAttribute('role')", sid), "listbox")
                self.assertEqual(cdp.js("document.querySelector('#fline-input').getAttribute('role')", sid), "combobox")
                self.assertEqual(cdp.js("document.querySelector('#fline-list').getAttribute('aria-label')", sid), "Suggestions")
                got = cdp.js("Object.fromEntries([...document.querySelectorAll('#fline-list [role=option]')].map(o => [o.dataset.ins, [o.querySelector('.fl1').textContent, o.querySelector('.fl2').textContent]]))", sid)
                for ins, words in NOTES.items():
                    self.assertEqual(tuple(got[ins]), words, ins)
                self.assertEqual(cdp.js("document.querySelectorAll('#fline-list [role=option] svg.fic').length", sid), len(FIELDS), "each field has its icon")
                self.assertEqual(self.hints(cdp, sid), "hidden", "the example chips do not show with the list")
                box = cdp.js("(() => { const l = document.querySelector('#fline-list').getBoundingClientRect(), f = document.querySelector('.fline').getBoundingClientRect(); return [l.top >= f.bottom - 1, l.right <= innerWidth, l.left >= 0]; })()", sid)
                self.assertEqual(box, [True, True, True], "right under the box, inside the window")
                self.assertEqual(cdp.js("document.documentElement.scrollWidth <= window.innerWidth", sid), True)
                # Esc closes it; a click brings it back
                key(cdp, sid, "Escape")
                self.assertTrue(wait(lambda: self.expanded(cdp, sid) == "false"))
                self.assertEqual(cdp.js("!document.querySelector('#fline-list')", sid), True)
                self.assertEqual(self.hints(cdp, sid), "visible")
                click(cdp, sid, INPUT)
                self.assertTrue(wait(lambda: self.expanded(cdp, sid) == "true"))
                # typing narrows it, as before
                self.type(cdp, sid, "pr")
                self.assertTrue(wait(lambda: self.listed(cdp, sid) == ["priority:"]))
                key(cdp, sid, "Backspace"); key(cdp, sid, "Backspace")
                self.assertTrue(wait(lambda: self.listed(cdp, sid) == FIELDS), "back to every field once the word is gone")
                # a click on Status puts status: in the box and lists its values with their counts
                click(cdp, sid, "#fline-list [data-ins='status:']")
                self.assertTrue(wait(lambda: cdp.js("document.querySelector('#fline-input').value", sid) == "status:"))
                self.assertTrue(wait(lambda: "status:Closed" in self.listed(cdp, sid)))
                counts = cdp.js("Object.fromEntries([...document.querySelectorAll('#fline-list [role=option]')].map(o => [o.dataset.ins, +o.querySelector('.c').textContent]))", sid)
                self.assertEqual(counts["status:Closed"], len([r for r in rows if r["status"] == "Closed"]))
                self.assertEqual(cdp.js("document.activeElement.id", sid), "fline-input")

    def test_the_keyboard_path_tab_down_enter_esc(self):
        s = self.serve()
        for width, theme in both():
            with self.subTest(width=width, theme=theme), chrome() as cdp:
                sid = self.load(cdp, s.port, width, theme=theme)
                # Tab into the box from the control before it
                cdp.js("(() => { const b = document.createElement('button'); b.id = 'before'; b.textContent = 'before'; document.querySelector('.fline').before(b); b.focus(); })()", sid)
                key(cdp, sid, "Tab")                                             # past the is:open chip's own remove button
                self.assertEqual(cdp.js("document.activeElement.dataset.fx", sid), "is")
                self.assertEqual(self.expanded(cdp, sid), "false")
                key(cdp, sid, "Tab")
                self.assertTrue(wait(lambda: cdp.js("document.activeElement.id", sid) == "fline-input"))
                self.assertTrue(wait(lambda: self.expanded(cdp, sid) == "true"), "Tab into the empty box opens the field list")
                key(cdp, sid, "Escape")
                self.assertTrue(wait(lambda: self.expanded(cdp, sid) == "false"))
                # Down opens it again, then the arrows move and Enter picks
                key(cdp, sid, "ArrowDown")
                self.assertTrue(wait(lambda: cdp.js("document.querySelector('#fline-input').getAttribute('aria-activedescendant')", sid) == "fo-0"))
                key(cdp, sid, "ArrowDown")
                self.assertEqual(cdp.js("document.querySelector('#fline-input').getAttribute('aria-activedescendant')", sid), "fo-1")
                self.assertEqual(cdp.js("document.querySelector('#fo-1').getAttribute('aria-selected')", sid), "true")
                key(cdp, sid, "ArrowUp"); key(cdp, sid, "ArrowUp")
                self.assertEqual(cdp.js("document.querySelector('#fline-input').getAttribute('aria-activedescendant')", sid), f"fo-{len(FIELDS) - 1}", "the arrows wrap round")
                key(cdp, sid, "ArrowDown"); key(cdp, sid, "ArrowDown")       # round to the first, then Type
                key(cdp, sid, "Enter")
                self.assertTrue(wait(lambda: cdp.js("document.querySelector('#fline-input').value", sid) == "type:"))
                self.assertTrue(wait(lambda: "type:action" in self.listed(cdp, sid)))
                key(cdp, sid, "ArrowDown")
                key(cdp, sid, "Enter")
                self.assertTrue(wait(lambda: len(self.chips(cdp, sid)) == 2 and self.chips(cdp, sid)[1].startswith("type:")),
                                (self.chips(cdp, sid), cdp.js("document.querySelector('#fline-input').value", sid), self.listed(cdp, sid)))
                key(cdp, sid, "Escape")
                self.assertEqual(self.expanded(cdp, sid), "false")

    def test_the_x_shows_only_off_the_starting_line_and_clears_it_in_one_step(self):
        s = self.serve()
        for width, theme in both():
            with self.subTest(width=width, theme=theme), chrome() as cdp:
                sid = self.load(cdp, s.port, width, theme=theme)
                rows = self.rows(cdp, sid)
                self.assertFalse(self.x(cdp, sid), "not on the starting line")
                self.focus(cdp, sid)
                self.type(cdp, sid, "supp")
                self.assertTrue(wait(lambda: self.x(cdp, sid)), "a typed word is something to clear")
                cdp.js("document.querySelector('#fline-input').select()", sid)
                key(cdp, sid, "Backspace")
                self.assertTrue(wait(lambda: not self.x(cdp, sid)))
                self.type(cdp, sid, "priority:High type:action")
                key(cdp, sid, "Enter")
                self.assertTrue(wait(lambda: self.chips(cdp, sid) == ["is:open", "priority:High", "type:action"]))
                self.assertTrue(self.x(cdp, sid))
                self.assertEqual(cdp.js("document.querySelector('#fline-clear').getAttribute('aria-label')", sid), "Clear the filter")
                r = cdp.js("(() => { const b = document.querySelector('#fline-clear').getBoundingClientRect(), f = document.querySelector('.fline').getBoundingClientRect(); return [b.width, b.height, f.right - b.right]; })()", sid)
                self.assertGreaterEqual(r[0], 24); self.assertGreaterEqual(r[1], 24)
                self.assertLess(r[2], 24, "at the right end of the box")
                # Esc in the box does not clear
                key(cdp, sid, "Escape"); key(cdp, sid, "Escape")
                self.assertEqual(self.chips(cdp, sid), ["is:open", "priority:High", "type:action"])
                # Tab after the box reaches it; a click (or Enter) clears in one step and the focus stays in the box
                key(cdp, sid, "Tab")
                self.assertTrue(wait(lambda: cdp.js("document.activeElement.id", sid) == "fline-clear"))
                click(cdp, sid, "#fline-clear")
                self.assertTrue(wait(lambda: self.chips(cdp, sid) == ["is:open"]))
                self.assertEqual(cdp.js("document.activeElement.id", sid), "fline-input", "the focus stays in the box")
                self.assertIn("Filter cleared", self.say(cdp, sid))
                self.assertEqual(cdp.js("document.querySelector('#fline-msg').getAttribute('aria-live')", sid), "polite")
                self.assertFalse(self.x(cdp, sid))
                self.assertEqual(self.shown(cdp, sid), expect(rows, "open"))
                self.assertEqual(cdp.js("location.hash", sid), "#work&p=TUL", "the same as Clear all")
                # by keyboard: Enter on the x
                self.type(cdp, sid, "due:overdue")
                key(cdp, sid, "Enter")
                self.assertTrue(wait(lambda: self.x(cdp, sid)))
                key(cdp, sid, "Tab")
                self.assertTrue(wait(lambda: cdp.js("document.activeElement.id", sid) == "fline-clear"))
                key(cdp, sid, "Enter")
                self.assertTrue(wait(lambda: self.chips(cdp, sid) == ["is:open"]))
                self.assertEqual(cdp.js("document.activeElement.id", sid), "fline-input")
                # Clear all stays
                self.type(cdp, sid, "priority:High")
                key(cdp, sid, "Enter")
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#clearAll')", sid)))
                cdp.js("sessionStorage.clear()", sid)

    def test_the_core_five_come_first_with_their_counts_and_set_the_line(self):
        s = self.serve()
        tabs = "[...document.querySelectorAll('.vtab span')].map(e => e.textContent)"
        for width, theme in both():
            with self.subTest(width=width, theme=theme), chrome() as cdp:
                sid = self.load(cdp, s.port, width, theme=theme)
                rows = self.rows(cdp, sid)
                self.assertEqual(cdp.js(tabs, sid)[:5], CORE)
                self.assertEqual(cdp.js("document.querySelector('.vtab[aria-pressed=true]').dataset.viewId", sid), "core-open")
                raid = sorted(r["id"] for r in rows if r["kind"] in ("risk", "issue") and r["id"] in expect(rows, "open"))
                want = {**{k: len(expect(rows, m, t)) for k, (m, t) in LINES.items()}, "core-raid": len(raid)}
                for vid, n in want.items():
                    self.assertEqual(cdp.js(f"+document.querySelector('.vtab[data-view-id={vid}] em').textContent", sid), n, vid)
                for vid, (m, t) in LINES.items():
                    click(cdp, sid, f".vtab[data-view-id={vid}]")
                    self.assertTrue(wait(lambda: self.shown(cdp, sid) == expect(rows, m, t)), vid)
                    self.assertEqual(cdp.js(f"document.querySelector('.vtab[data-view-id={vid}]').getAttribute('aria-pressed')", sid), "true")
                click(cdp, sid, ".vtab[data-view-id=core-raid]")
                self.assertTrue(wait(lambda: self.shown(cdp, sid) == raid))
                self.assertEqual(self.chips(cdp, sid), ["is:open", "type:risk,issue"])
                click(cdp, sid, ".vtab[data-view-id=core-all]")
                self.assertTrue(wait(lambda: self.chips(cdp, sid) == []))
                self.assertEqual(len(self.shown(cdp, sid)), len(rows), "closed items are in All work items")
                # at 900 px the row stays one line and scrolls in its own box; the page itself never scrolls sideways
                if width == 900:
                    self.assertEqual(cdp.js("getComputedStyle(document.querySelector('.vtabs')).overflowX", sid), "auto")
                    self.assertEqual(cdp.js("new Set([...document.querySelectorAll('.vtab')].map(t => Math.round(t.getBoundingClientRect().top))).size", sid), 1)
                self.assertEqual(cdp.js("document.documentElement.scrollWidth <= window.innerWidth", sid), True)
                # no Rename or Archive on a core tab; Save changes is not offered on one either
                click(cdp, sid, ".vtab[data-view-id=core-actions]")
                self.put(cdp, sid, "priority:High")
                self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('.vtab[data-view-id=core-actions] ~ [data-dot], .vtab[data-view-id=core-actions] [data-dot]').length", sid) == 1))
                click(cdp, sid, "#vtabMenu")
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#vtabMenuList')", sid)))
                kinds = cdp.js("[...document.querySelectorAll('#vtabMenuList [role=menuitem]')].map(b => b.dataset.kind)", sid)
                self.assertEqual(kinds, ["discard", "saveas"])
                key(cdp, sid, "Escape")
                cdp.js("localStorage.clear(); sessionStorage.clear()", sid)

    def test_a_project_with_stored_views_keeps_them_after_the_core_five(self):
        s = self.serve()
        stored = [{"id": "open", "name": "Open items", "line": "is:open"}, {"id": "v7", "name": "Build risks", "line": "is:open workstream:Build"},
                  {"id": "overdue", "name": "Late", "line": "is:open due:overdue"}, {"id": "v8", "name": "Gone", "line": "is:closed", "archived": True}]
        for width in SIZES:
            with self.subTest(width=width), chrome() as cdp:
                sid = self.load(cdp, s.port, width)
                cdp.js("localStorage.setItem('clark.fviews', JSON.stringify({TUL: %s}))" % json.dumps(stored), sid)
                reload_to_new_page_cdp(cdp, sid)
                self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('.vtab').length", sid) == 7))
                self.assertEqual(cdp.js("[...document.querySelectorAll('.vtab span')].map(e => e.textContent)", sid), CORE + ["Build risks", "Late"])
                self.assertEqual(cdp.js("JSON.parse(localStorage.getItem('clark.fviews')).TUL", sid), stored, "nothing stored is lost or rewritten")
                cdp.js("localStorage.clear(); sessionStorage.clear()", sid)

    def test_the_tab_menu_and_new_view_by_keyboard_and_pointer(self):
        s = self.serve()
        for width, theme in both():
            with self.subTest(width=width, theme=theme), chrome() as cdp:
                sid = self.load(cdp, s.port, width, theme=theme)
                self.assertEqual(cdp.js("document.querySelectorAll('#vtabMenu').length", sid), 1, "one ▾, on the open tab")
                self.assertEqual(cdp.js("document.querySelector('#vtabMenu').closest('.vtabw').querySelector('.vtab').dataset.viewId", sid), "core-open")
                for sel in ("#vtabMenu", "#vnew"):
                    r = cdp.js(f"(b => [b.width, b.height])(document.querySelector('{sel}').getBoundingClientRect())", sid)
                    self.assertGreaterEqual(min(r), 24, sel)
                # a person's own view: Save changes appears only with the dot, and puts it out
                click(cdp, sid, ".vtab[data-view-id=overdue]")
                self.assertTrue(wait(lambda: self.chips(cdp, sid) == ["is:open", "due:overdue"]))
                cdp.js("document.querySelector('#vtabMenu').focus()", sid)
                key(cdp, sid, "Enter")
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#vtabMenuList')", sid)))
                kinds = cdp.js("[...document.querySelectorAll('#vtabMenuList [role=menuitem]')].map(b => b.dataset.kind)", sid)
                self.assertEqual(kinds, ["saveas", "rename", "archive"], "no Save changes without the dot")
                self.assertEqual(cdp.js("document.activeElement.dataset.kind", sid), "saveas")
                m = cdp.js("(r => [r.left >= 0, r.right <= innerWidth])(document.querySelector('#vtabMenuList').getBoundingClientRect())", sid)
                self.assertEqual(m, [True, True], "the menu is inside the window")
                key(cdp, sid, "Escape")
                self.assertTrue(wait(lambda: cdp.js("!document.querySelector('#vtabMenuList') && document.activeElement.id === 'vtabMenu'", sid)), "Esc closes, focus back on the ▾")
                self.put(cdp, sid, "priority:High")
                self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('.vtab[data-view-id=overdue] [data-dot]').length", sid) == 1))
                click(cdp, sid, "#vtabMenu")
                self.assertTrue(wait(lambda: cdp.js("[...document.querySelectorAll('#vtabMenuList [role=menuitem]')].map(b => b.textContent)", sid)
                                     == ["Save changes", "Discard changes", "Save as a new view…", "Rename…", "Archive"]))
                click(cdp, sid, "#vtabMenuList [data-kind=save]")
                self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('[data-dot]').length", sid) == 0), "saved: the dot goes")
                # + New view: the name box, then the new tab with its count, chosen
                self.put(cdp, sid, "type:decision")
                click(cdp, sid, "#vnew")
                self.assertTrue(wait(lambda: cdp.js("document.activeElement.id", sid) == "vname"))
                self.type(cdp, sid, "Decisions")
                key(cdp, sid, "Enter")
                self.assertTrue(wait(lambda: "already exists" in cdp.js("document.querySelector('.vmsg').textContent", sid)), "a core name is taken")
                cdp.js("document.querySelector('#vname').select()", sid)
                self.type(cdp, sid, "Late decisions")
                key(cdp, sid, "Enter")
                self.assertTrue(wait(lambda: cdp.js("(t => t && t.querySelector('span').textContent)(document.querySelector('.vtab[aria-pressed=true]'))", sid) == "Late decisions"))
                self.assertEqual(cdp.js("[...document.querySelectorAll('.vtab span')].map(e => e.textContent)", sid)[-1], "Late decisions", "after the others")
                self.assertEqual(cdp.js("+document.querySelector('.vtab[aria-pressed=true] em').textContent", sid), len(self.shown(cdp, sid)))
                # Archive from the ▾, and Bring back from it
                click(cdp, sid, "#vtabMenu")
                click(cdp, sid, "#vtabMenuList [data-kind=archive]")
                self.assertTrue(wait(lambda: "Late decisions" not in cdp.js("[...document.querySelectorAll('.vtab span')].map(e => e.textContent)", sid)))
                click(cdp, sid, ".vtab[data-view-id=core-open]")
                click(cdp, sid, "#vtabMenu")
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector(\"#vtabMenuList [data-kind^='restore:']\")", sid)))
                click(cdp, sid, "#vtabMenuList [data-kind^='restore:']")
                self.assertTrue(wait(lambda: "Late decisions" in cdp.js("[...document.querySelectorAll('.vtab span')].map(e => e.textContent)", sid)))
                cdp.js("localStorage.clear(); sessionStorage.clear()", sid)

    def test_the_plain_words_note_is_not_under_the_line_and_nothing_goes_into_the_published_file(self):
        s = self.serve()
        with chrome() as cdp:
            sid = self.load(cdp, s.port)
            self.focus(cdp, sid)
            key(cdp, sid, "Escape")
            self.assertNotIn("Plain words search titles", cdp.js("document.querySelector('#work').innerText", sid))
        view = (ROOT / "src" / "clark" / "page" / "page-view.html").read_text(encoding="utf-8")
        for word in ("fline-clear", "vtabMenu", "core-actions", "Has no owner, date, workstream"):
            self.assertNotIn(word, view, f"{word} is the app's only, never in the published file")


# Fields borrows Line's set-up and helpers only: Line's own tests run in test_filter_line_page, not twice.
for _name in [n for n in dir(Line) if n.startswith("test_") and n not in vars(Fields)]:
    setattr(Fields, _name, None)
del Line

if __name__ == "__main__":
    unittest.main()
