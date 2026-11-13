"""Row 986: Assign to adds a new person from the Owner picker, on the real page (1400 and 900 px, headless Chrome, real key and mouse events).

Run: ~/bin/clark-chrome-slot env CLARK_CHROME=/usr/local/bin/clark-chrome python3 dev/run_tests.py test_assign_new_person_live
A name with no match offers "Add {typed} as a new person" and "Keep the name only"; the form has Name and an optional Email; Enter saves
and assigns in ONE step with ONE Undo (the person goes too); the same name a second time says "Use this one"; the clear entry reads
"TBC (no one yet)" and stores TBC; a name with markup is text, never elements. Browser parts fail, never skip, without Chrome.
"""
import json
import unittest

import test_assign_recent_live as R
import test_inline_edits as T
from test_inline_edits import chrome, click, key

CELL = R.CELL


class NewPerson(R.Picker):
    def people_named(self, name):
        st = T.open_store(self.path, onedrive_roots=[])
        try:
            return [p for p in st.people(archived=None) if p["name"] == name]
        finally:
            st.close()

    def type_name(self, cdp, sid, text):
        self.clear_box(cdp, sid)
        cdp.call("Input.insertText", {"text": text}, sid)
        self.until(cdp, sid, "!!document.querySelector('[data-pop] [data-add]')", f"{text} has no match and offers to add")

    def open_form(self, cdp, sid, text):
        self.open_picker(cdp, sid)
        self.type_name(cdp, sid, text)
        click(cdp, sid, "[data-pop] [data-add]")
        self.until(cdp, sid, "!!document.querySelector('[data-pop] [data-new-name]')", "the form opened")

    # the other classes' tests are not run again here
    for _n in dir(R.Picker):
        if _n.startswith("test_"):
            locals()[_n] = None
    del _n

    def test_no_match_offers_add_and_keep_and_an_existing_name_does_not(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.open_page(cdp, width)
                self.open_picker(cdp, sid)
                self.type_name(cdp, sid, "Zelda Quince")
                self.assertEqual(cdp.js("document.querySelector('[data-pop] [data-add]').textContent.trim()", sid), "Add Zelda Quince as a new person")
                self.assertEqual(cdp.js("document.querySelector('[data-pop] [data-keep]').textContent.trim()", sid), "Keep the name only")
                self.clear_box(cdp, sid)
                cdp.call("Input.insertText", {"text": "Aaron Wickham"}, sid)
                self.until(cdp, sid, "!!document.querySelector('[data-pop] [data-name=\"Aaron Wickham\"]')", "the match drew")
                self.assertEqual(cdp.js("document.querySelectorAll('[data-pop] [data-add]').length", sid), 0, "a name on the list offers no add")

    def test_keep_the_name_only_assigns_and_adds_no_person(self):
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400)
            self.open_picker(cdp, sid)
            self.type_name(cdp, sid, "Zelda Quince")
            before = self.steps()
            click(cdp, sid, "[data-pop] [data-keep]")
            self.until(cdp, sid, "!!document.querySelector('[data-undo]')", "saved")
            self.changed_once(before, "owner")
            self.assertEqual(self.row("actions", "TUL-A-001")["owner"], "Zelda Quince")
            self.assertEqual(self.people_named("Zelda Quince"), [], "no person was added")

    def test_form_enter_adds_and_assigns_in_one_step_with_one_undo(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.open_page(cdp, width)
                self.open_form(cdp, sid, "Zelda Quince")
                self.assertEqual(cdp.js("document.querySelector('[data-pop] [data-new-name]').value", sid), "Zelda Quince")
                self.assertEqual(cdp.js("document.querySelector('[data-pop] [data-new-email]').value", sid), "")
                click(cdp, sid, "[data-pop] [data-new-email]")
                cdp.call("Input.insertText", {"text": "Zelda.Quince@Example.com"}, sid)
                before = self.steps()
                key(cdp, sid, "Enter")
                self.until(cdp, sid, "!!document.querySelector('[data-undo]')", "saved, with Undo")
                self.changed_once(before, "the owner and the new person")
                self.assertEqual(self.row("actions", "TUL-A-001")["owner"], "Zelda Quince")
                found = self.people_named("Zelda Quince")
                self.assertEqual(len(found), 1)
                self.assertEqual(found[0]["email"], "zelda.quince@example.com")
                self.assertEqual(self.toast(cdp, sid), "Owner of TUL-A-001 changed to Zelda Quince, added as a new person.")
                self.until(cdp, sid, "document.querySelectorAll('[data-pop]').length === 0", "the picker closed")
                self.undo(cdp, sid, "the add")
                self.assertEqual(self.row("actions", "TUL-A-001")["owner"], "Ada Quillfeather")
                self.assertEqual(self.people_named("Zelda Quince"), [], "one Undo takes the person back too")

    def test_a_second_same_name_says_use_this_one_and_uses_the_one_on_the_list(self):
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400)
            self.open_form(cdp, sid, "Zelda Quince")
            key(cdp, sid, "Enter")
            self.until(cdp, sid, "!!document.querySelector('[data-undo]')", "the first add saved")
            self.until(cdp, sid, "document.querySelectorAll('[data-pop]').length === 0", "closed")
            self.choose(cdp, sid, "Aaron Wickham", cell="[data-cell='TUL-A-001:owner']")      # move the owner on, so the name is new to the cell again
            self.open_picker(cdp, sid)
            self.clear_box(cdp, sid)
            cdp.call("Input.insertText", {"text": "zelda  quince"}, sid)
            self.until(cdp, sid, "!!document.querySelector('[data-pop] [data-name=\"Zelda Quince\"]')", "the person on the list is found by typing")
            self.assertEqual(cdp.js("document.querySelectorAll('[data-pop] [data-add]').length", sid), 0, "no offer to add what is on the list")
            # a forced second add, as a stale page would send it: the server refuses and the form offers the one on the list
            self.open_form_forced(cdp, sid, "Zelda Quince")
            before = self.steps()
            key(cdp, sid, "Enter")
            self.until(cdp, sid, "!!document.querySelector('[data-pop] [data-use]')", "Use this one is offered")
            self.assertEqual(cdp.js("document.querySelector('[data-pop] [data-use]').textContent.trim()", sid), "Use this one")
            self.assertIn("Use this one", cdp.js("document.querySelector('[data-pop] .cp-problem').textContent", sid))
            self.assertEqual(self.steps(), before, "a refused add changes nothing")
            self.assertEqual(len(self.people_named("Zelda Quince")), 1)
            click(cdp, sid, "[data-pop] [data-use]")
            self.assertTrue(T.wait(lambda: self.row("actions", "TUL-A-001")["owner"] == "Zelda Quince", 10), "the one on the list was used")
            self.assertEqual(len(self.people_named("Zelda Quince")), 1, "still one person")

    def open_form_forced(self, cdp, sid, text):
        """Open the form on a name the list already holds: type a different unknown name, open the form, then retype the name in its box."""
        self.clear_box(cdp, sid)
        cdp.call("Input.insertText", {"text": "Nobody Known"}, sid)
        self.until(cdp, sid, "!!document.querySelector('[data-pop] [data-add]')", "the offer")
        click(cdp, sid, "[data-pop] [data-add]")
        self.until(cdp, sid, "!!document.querySelector('[data-pop] [data-new-name]')", "the form opened")
        cdp.js("(() => { const i = document.querySelector('[data-pop] [data-new-name]'); i.focus(); i.select(); return true; })()", sid)
        cdp.call("Input.insertText", {"text": text}, sid)

    def test_row_1120_tab_in_the_form_moves_between_its_fields_and_keeps_the_picker(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.open_page(cdp, width)
                self.open_form(cdp, sid, "Zelda Quince")
                key(cdp, sid, "Tab")
                self.until(cdp, sid, "document.activeElement && document.activeElement.matches('[data-pop] [data-new-email]')", "Tab went to Email")
                key(cdp, sid, "Tab")
                self.until(cdp, sid, "document.activeElement && document.activeElement.matches('[data-pop] [data-new-back]')", "Tab went to Back")
                self.assertTrue(cdp.js("!!document.querySelector('[data-pop] [data-new-name]')", sid), "the picker and the form stay open")

    def tab(self, cdp, sid, shift=False):
        common = {"key": "Tab", "code": "Tab", "windowsVirtualKeyCode": 9, "modifiers": 8 if shift else 0}
        cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", **common}, sid)
        cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", **common}, sid)

    def test_row_1120_tab_walks_the_whole_form_both_ways_and_only_its_two_ends_leave(self):
        at = "document.activeElement && document.activeElement.matches('[data-pop] %s')"
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.open_page(cdp, width)
                self.open_form(cdp, sid, "Zelda Quince")
                self.tab(cdp, sid)                      # Name -> Email -> Back -> Add and assign: all inside the picker
                self.until(cdp, sid, at % "[data-new-email]", "Tab: Name to Email")
                self.tab(cdp, sid)
                self.until(cdp, sid, at % "[data-new-back]", "Tab: Email to Back")
                self.tab(cdp, sid)
                self.until(cdp, sid, at % "[data-new-save]", "Tab: Back to Add and assign")
                self.tab(cdp, sid, shift=True)          # and back again with Shift+Tab
                self.until(cdp, sid, at % "[data-new-back]", "Shift+Tab: Save to Back")
                self.tab(cdp, sid, shift=True)
                self.until(cdp, sid, at % "[data-new-email]", "Shift+Tab: Back to Email")
                self.tab(cdp, sid, shift=True)
                self.until(cdp, sid, at % "[data-new-name]", "Shift+Tab: Email to Name")
                self.assertTrue(cdp.js("!!document.querySelector('[data-pop] [data-new-name]')", sid), "the picker is still open inside the form")
                self.tab(cdp, sid, shift=True)          # off the first field: leaves and closes
                self.until(cdp, sid, "!document.querySelector('[data-pop]')", "Shift+Tab off Name closes the picker")
            with self.subTest(width=width, end="last"), chrome() as cdp:
                sid = self.open_page(cdp, width)
                self.open_form(cdp, sid, "Zelda Quince")
                cdp.js("document.querySelector('[data-pop] [data-new-save]').focus()", sid)
                self.tab(cdp, sid)                      # off the last button: leaves and closes
                self.until(cdp, sid, "!document.querySelector('[data-pop]')", "Tab off Add and assign closes the picker")

    def test_a_bad_email_is_said_in_the_form_and_nothing_is_sent(self):
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400)
            self.open_form(cdp, sid, "Zelda Quince")
            click(cdp, sid, "[data-pop] [data-new-email]")
            cdp.call("Input.insertText", {"text": "not an email"}, sid)
            before, sent = self.steps(), len(self.sent)
            key(cdp, sid, "Enter")
            self.until(cdp, sid, "!!document.querySelector('[data-pop] .cp-problem')", "the problem is said")
            self.assertEqual(self.steps(), before)
            self.assertEqual(len(self.sent), sent, "nothing was sent")
            self.assertTrue(cdp.js("!!document.querySelector('[data-pop] [data-new-name]')", sid), "the form stays, with what was typed")

    def test_markup_in_a_name_is_text_not_elements(self):
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400)
            name = "<b>Zed</b> <img src=x onerror=alert(1)>"
            self.open_picker(cdp, sid)
            self.type_name(cdp, sid, name)
            self.assertEqual(cdp.js("document.querySelectorAll('[data-pop] [data-add] b, [data-pop] [data-add] img').length", sid), 0)
            click(cdp, sid, "[data-pop] [data-add]")
            self.until(cdp, sid, "!!document.querySelector('[data-pop] [data-new-name]')", "form")
            key(cdp, sid, "Enter")
            self.until(cdp, sid, "!!document.querySelector('[data-undo]')", "saved")
            self.assertEqual(self.row("actions", "TUL-A-001")["owner"], name)
            self.assertEqual(cdp.js("document.querySelectorAll('#work img[src=x], #work td b').length", sid), 0, "drawn as text")

    def test_clear_entry_reads_tbc_no_one_yet_and_stores_tbc_with_the_link_cleared(self):
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400)
            self.open_form(cdp, sid, "Zelda Quince")
            key(cdp, sid, "Enter")
            self.until(cdp, sid, "!!document.querySelector('[data-undo]')", "added")
            self.until(cdp, sid, "document.querySelectorAll('[data-pop]').length === 0", "closed")
            self.assertIsNotNone(self.row("actions", "TUL-A-001").get("owner_id"), "linked to the new person")
            self.open_picker(cdp, sid)
            self.assertEqual(cdp.js("document.querySelector('[data-pop] [data-clear]').textContent.trim()", sid), "TBC (no one yet)")
            before = self.steps()
            click(cdp, sid, "[data-pop] [data-clear]")
            self.assertTrue(T.wait(lambda: self.steps() == before + 1, 10), "one step")
            row = self.row("actions", "TUL-A-001")
            self.assertEqual(row["owner"], "TBC")
            self.assertIsNone(row.get("owner_id"))

    def test_the_published_page_carries_none_of_it(self):
        import build_page
        published = build_page.build(build_page.ENTRY_VIEW)
        for word in ("as a new person", "Keep the name only", "Use this one", "data-new-person"):
            self.assertNotIn(word, published, word)


if __name__ == "__main__":
    unittest.main()
