"""Row 985: the Owner picker (Assign to) opens on a search box with Recent, People and a TBC entry, on the real page.

Run: python3 dev/run_tests.py test_assign_recent_live
A real server over a demo store (fictional people) and the committed page's sources, headless Chrome at 1400 and 900 px with real mouse
and key events. Covers: the picker opens with the box focused; Recent (up to five, newest first, kept in this browser per project, never
sent to clark); People (five, alphabetical) and "And N more. Keep typing to find them."; the current owner ticked; the TBC entry last, reading
"TBC (no one yet)" and storing TBC; typing searches the whole register (name, alias, email, role) and the project's names, eight at most, and
Enter still keeps what was typed; with the storage refused there is no Recent and nothing breaks; and the published page carries none of it.
The browser parts are required: they fail, never skip, without Chrome (set CLARK_CHROME).
"""
import json
import unittest

import test_inline_edits as T
from test_inline_edits import chrome, click, key
from _paths import SRC  # noqa: F401
import build_page  # noqa: E402  (dev/tools)

CELL = "[data-cell='TUL-A-001:owner']"
REGISTER = [("Aaron Wickham", "Programme Manager", "aaron.wickham@example.com", ""),
            ("Bryony Castellan", "Analyst", "", "Bry C"),
            ("Cedric Dunmore", "Supplier lead", "", ""),
            ("Delphine Ashgrove", "Architect", "", ""),
            ("Fenwick Marlowe", "Tester", "", ""),
            ("Gwen Hartnoll", "Tester", "", ""),
            ("Hugo Pellew", "Tester", "fen.search@example.com", ""),
            ("Isolde Penrose", "Tester", "", ""),
            ("Jasper Quill", "Tester", "", ""),
            ("Kestrel Lund", "Tester", "", "")]


class Picker(T.Live):
    def setUp(self):
        super().setUp()
        st = T.open_store(self.path, onedrive_roots=[])
        try:
            from _demo import USER
            for name, role, email, alias in REGISTER:
                fields = {"name": name, "role": role, "source": "test"}
                if email:
                    fields["email"] = email
                if alias:
                    fields["aliases"] = alias
                with st.step("dashboard", USER) as w:
                    w.add_person(**fields)
        finally:
            st.close()

    def open_picker(self, cdp, sid, cell=CELL):
        click(cdp, sid, cell)
        self.until(cdp, sid, "!!document.querySelector('[data-pop] input.cp-in')", "the owner picker opened")
        self.until(cdp, sid, "document.querySelectorAll('[data-pop] [data-name]').length > 0", "the names drew")

    def clear_box(self, cdp, sid):
        cdp.js("(() => { const i = document.querySelector('[data-pop] input.cp-in'); i.focus(); i.value = ''; i.dispatchEvent(new Event('input', {bubbles: true})); return true; })()", sid)

    def section(self, cdp, sid, which):
        return cdp.js(f"[...document.querySelectorAll('[data-pop] [data-section={which}] [data-name]')].map(b => b.dataset.name)", sid)

    def recent_is(self, cdp, sid, want, what):
        """The Recent section shows exactly `want`: waited for (the picker draws Recent from what the page has read back, which a slow
        runner delivers a moment after the picker opens), and then read again and compared whole by the test."""
        self.until(cdp, sid, f"JSON.stringify([...document.querySelectorAll('[data-pop] [data-section=recent] [data-name]')].map(b => b.dataset.name)) === {json.dumps(json.dumps(want, separators=(',', ':')))}", what)
        self.assertEqual(self.section(cdp, sid, "recent"), want, what)

    def all_names(self, cdp, sid):
        return cdp.js("[...document.querySelectorAll('[data-pop] [data-name]')].map(b => b.dataset.name)", sid)

    def choose(self, cdp, sid, name, cell=CELL):
        before = self.steps()
        self.open_picker(cdp, sid, cell)
        want = f"[data-pop] [data-name='{name}']"
        if not cdp.js(f"!!document.querySelector({json.dumps(want)})", sid):          # not drawn before typing: find them by typing
            self.clear_box(cdp, sid)
            cdp.call("Input.insertText", {"text": name}, sid)
            self.until(cdp, sid, f"!!document.querySelector({json.dumps(want)})", f"typing finds {name}")
        click(cdp, sid, want)
        self.assertTrue(T.wait(lambda: self.steps() == before + 1, 10), f"{name} saved as one step")
        self.until(cdp, sid, "document.querySelectorAll('[data-pop]').length === 0", "the picker closed")

    # the other class's tests are not run again here
    for _n in dir(T.Live):
        if _n.startswith("test_"):
            locals()[_n] = None
    del _n

    def test_opens_on_the_box_with_people_alphabetical_five_and_the_count_of_the_rest(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.open_page(cdp, width)
                self.open_picker(cdp, sid)
                self.assertTrue(cdp.js("document.activeElement.classList.contains('cp-in')", sid), "the search box has the focus")
                self.assertEqual(self.section(cdp, sid, "recent"), [], "nothing was assigned yet, so no Recent")
                self.assertEqual(cdp.js("document.querySelectorAll('[data-pop] [data-section=recent]').length", sid), 0, "no Recent heading either")
                people = self.section(cdp, sid, "people")
                self.assertEqual(len(people), 5)
                self.assertEqual(people, sorted(people, key=lambda n: n.lower()), "alphabetical")
                self.assertEqual(people[0], "Aaron Wickham")
                more = cdp.js("(document.querySelector('[data-pop] [data-more]') || {}).textContent || ''", sid)
                self.assertRegex(more, r"^And \d+ more\. Keep typing to find them\.$")
                self.assertGreaterEqual(int(more.split()[1]), len(REGISTER) - 5, "counts everyone not drawn")
                last = cdp.js("(() => { const l = document.querySelector('[data-pop] [data-clear]'); const all = [...document.querySelectorAll('[data-pop] button')]; return [l ? l.textContent.trim() : '', all[all.length - 1] === l]; })()", sid)
                self.assertEqual(last, ["TBC (no one yet)", True], "the TBC entry is last")

    def test_the_current_owner_is_ticked_wherever_it_is_drawn(self):
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400)
            self.choose(cdp, sid, "Aaron Wickham")
            self.open_picker(cdp, sid)
            ticked = cdp.js("[...document.querySelectorAll('[data-pop] [data-name][aria-pressed=true]')].map(b => b.dataset.name)", sid)
            self.assertEqual(ticked, ["Aaron Wickham"], "one tick, on the owner, whichever section holds them")

    def test_recent_is_newest_first_five_at_most_distinct_and_per_browser(self):
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400)
            order = ["Aaron Wickham", "Bryony Castellan", "Cedric Dunmore", "Delphine Ashgrove", "Fenwick Marlowe", "Gwen Hartnoll", "Aaron Wickham"]
            for i, name in enumerate(order):
                self.choose(cdp, sid, name, cell=f"[data-cell='TUL-A-001:owner']")
                if i == 0:
                    self.open_picker(cdp, sid)
                    self.recent_is(cdp, sid, ["Aaron Wickham"], "the first one is on top at once")
                    key(cdp, sid, "Escape")
            self.open_picker(cdp, sid)
            self.recent_is(cdp, sid, ["Aaron Wickham", "Gwen Hartnoll", "Fenwick Marlowe", "Delphine Ashgrove", "Cedric Dunmore"],
                           "newest first, each once, five at most")
            names = self.all_names(cdp, sid)
            self.assertEqual(len(names), len(set(names)), "a name is drawn once in the picker")
            kept = cdp.js("Object.keys(localStorage).filter(k => k.indexOf('assignRecent') >= 0)", sid)
            self.assertEqual(kept, ["clark.assignRecent.TUL"], "one list, for this project, in this browser")
        sent = json.dumps([r for _, r in self.sent])
        self.assertNotIn("assignRecent", sent)
        self.assertNotIn("recent", sent.lower().replace("recently", ""), "recents are never sent to clark")

    def test_typing_searches_the_register_by_name_alias_email_and_role_and_the_projects_names(self):
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400)
            self.open_picker(cdp, sid)
            for typed, want in (("hartn", ["Gwen Hartnoll"]), ("bry c", ["Bryony Castellan"]), ("fen.search", ["Hugo Pellew"]),
                                ("supplier", ["Cedric Dunmore"]), ("MARB", ["Edna Marblethorpe"])):
                with self.subTest(typed=typed):
                    self.clear_box(cdp, sid)
                    cdp.call("Input.insertText", {"text": typed}, sid)
                    box_value = cdp.js('document.querySelector("[data-pop] input.cp-in").value', sid)
                    self.until(cdp, sid, f"{json.dumps(want)}.every(n => [...document.querySelectorAll('[data-pop] [data-name]')].some(b => b.dataset.name === n))",
                               f"{typed} finds {want}, the box holds {box_value!r} and the picker draws {self.all_names(cdp, sid)}")
                    got = self.all_names(cdp, sid)
                    self.assertTrue(set(want) <= set(got), (typed, got))
                    self.assertEqual(cdp.js("document.querySelectorAll('[data-pop] [data-more]').length", sid), 0, "a search has no 'And N more'")
            self.clear_box(cdp, sid)
            cdp.call("Input.insertText", {"text": "e"}, sid)
            self.until(cdp, sid, "document.querySelectorAll('[data-pop] [data-name]').length > 0", "names drew")
            self.assertLessEqual(len(self.all_names(cdp, sid)), 8, "a search draws eight at most")

    def test_enter_still_keeps_what_was_typed_and_a_typed_name_not_on_the_list_is_assigned(self):
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400)
            self.open_picker(cdp, sid)
            before = self.steps()
            self.clear_box(cdp, sid)
            cdp.call("Input.insertText", {"text": "Zelda Quince"}, sid)
            key(cdp, sid, "Enter")
            self.until(cdp, sid, "!!document.querySelector('[data-undo]')", "saved")
            self.assertEqual(self.row("actions", "TUL-A-001")["owner"], "Zelda Quince")
            self.changed_once(before, "owner")

    def test_the_tbc_entry_stores_tbc_in_one_step_and_is_not_kept_as_a_recent(self):
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400)
            self.open_picker(cdp, sid)
            before = self.steps()
            click(cdp, sid, "[data-pop] [data-clear]")
            self.assertTrue(T.wait(lambda: self.steps() == before + 1, 10), "saved as one step: " + cdp.js("document.body.innerText.slice(0, 300) + ' | ' + (document.querySelector('[data-pop]') || {innerText: 'closed'}).innerText", sid))
            self.assertEqual(self.row("actions", "TUL-A-001")["owner"], "TBC")
            self.changed_once(before, "owner")
            self.until(cdp, sid, "(document.querySelector('.toast-text')||{}).textContent === 'Owner of TUL-A-001 changed to TBC.'", "the toast")
            self.assertEqual(self.toast(cdp, sid), "Owner of TUL-A-001 changed to TBC.")
            self.open_picker(cdp, sid)
            self.assertEqual(self.section(cdp, sid, "recent"), [], "TBC is not a name to come back to")

    def test_with_the_storage_refused_there_is_no_recent_and_nothing_breaks(self):
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400)
            cdp.js("Storage.prototype.setItem = function () { throw new Error('refused'); }; Storage.prototype.getItem = function () { throw new Error('refused'); }; true", sid)
            before = self.steps()
            self.choose(cdp, sid, "Aaron Wickham")
            self.changed_once(before, "owner")
            self.open_picker(cdp, sid)
            self.assertEqual(self.section(cdp, sid, "recent"), [])
            self.assertEqual(len(self.section(cdp, sid, "people")), 5)

    def test_the_published_page_carries_none_of_it(self):
        published = build_page.build(build_page.ENTRY_VIEW)
        for word in ("Keep typing to find them", "no one yet", "assignRecent", "data-more"):
            self.assertNotIn(word, published, word)


if __name__ == "__main__":
    unittest.main()
