"""#455: the Dashboard's use case summary in Edit follows the prototype: a status button on each row, the headline and the name changed
in place, the growing Add button with its box "Add a use case", and "Add a use case from your project record (N)".
#485: and the four controls of the prototype's use case row: the eye, "Where it stands" in place, "+ Add a next step", and
"+ Link an existing work item", each one change with one Undo.

Run: python3 dev/run_tests.py test_uc_dashboard_edit
Same harness and fictional data as test_glance_page (two use cases on the dashboard, 1.1 and 1.2), with two more that are not on it.
The page is the committed one, served over a real store, so every change is checked in the store. Laptop widths only: 1400 and 900 px,
light and dark. A published file is opened from file:// and checked for nothing of Edit.
"""
import json
import unittest

from _demo import USER
from test_glance_page import Published, Setup, tearDownModule  # noqa: F401
from test_server import chrome

PICKER = "Add a use case from your project record"
ADDED = "Use case 3.1 added, hidden from the client until its eye is turned on. Archive it from the Use cases page if it is not wanted."


class Edit(Setup):
    def setUp(self):
        super().setUp()
        with self.store.step("dashboard", USER) as st:
            self.uc3 = st.create("use_cases", {"project": "ABC", "title": "Supplier portal", "status": "High risk", "ref": "1.10", "sort_order": 3,
                                               "headline": "No login for the smallest suppliers", "client_visible": 0, "source": "demo"})
            self.uc4 = st.create("use_cases", {"project": "ABC", "title": "Month end close", "status": "On track", "ref": "2.1", "sort_order": 4,
                                               "headline": "Done in two days", "client_visible": 0, "source": "demo"})

    def edit(self, cdp, width=1400, dark=False):
        p = self.show(cdp, width, dark)
        p.js("document.querySelector('[data-mode=edit]').click()")
        p.until("!!document.querySelector('.uc [data-uc-status]')", "Edit shows the status buttons")
        p.until("document.getAnimations().length === 0", "the animations to end before anything is measured")
        return p

    def row(self, uc):
        return self.store.read("use_cases", ref=uc)

    def click(self, p, selector):
        p.js(f"document.querySelector({json.dumps(selector)}).scrollIntoView({{block: 'center'}})")
        x, y, _ = p.box(selector)
        p.mouse("mouseMoved", x, y)
        p.mouse("mousePressed", x, y, 1)
        p.mouse("mouseReleased", x, y)

    def type_in(self, p, selector, text):
        p.js(f"(() => {{ const e = document.querySelector({json.dumps(selector)}); e.focus(); e.select(); }})()")
        p.cdp.call("Input.insertText", {"text": text}, p.sid)

    def test_view_has_none_of_it_and_edit_has_the_button_the_status_buttons_and_the_link(self):
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark), chrome() as cdp:
                    p = self.show(cdp, width, dark)
                    self.assertEqual(p.js("document.querySelectorAll('.uc textarea, #ucAdd, [data-uc-status], [data-uc-back]').length"), 0, "View has none of Edit's parts")
                    p.js("document.querySelector('[data-mode=edit]').click()")
                    p.until("!!document.querySelector('.uc [data-uc-status]')", "Edit")
                    self.assertEqual(p.js("document.querySelectorAll('.uc [data-uc-status]').length"), 2)
                    self.assertEqual(p.js("document.querySelectorAll('.ucrow textarea.uchead-in').length"), 2)
                    self.assertEqual(p.js("document.querySelector('#ucAdd').getAttribute('aria-label')"), "Add use case")
                    self.assertEqual(p.js("document.querySelector('[data-uc-back]').textContent"), "+ Add a use case from your project record (2)")
                    self.assertEqual(p.js("document.querySelector('[data-uc-status] button').getAttribute('aria-label')"), "Status: On track. Change")

    def test_the_add_button_is_a_plus_that_grows_to_its_words_on_the_pointer_and_the_keyboard(self):
        with chrome() as cdp:
            p = self.edit(cdp)
            width = lambda: p.js("document.querySelector('#ucAdd').getBoundingClientRect().width")
            rest = width()
            self.assertLess(rest, 40, "a plus at rest")
            p.js("document.querySelector('#ucAdd').focus()")
            p.until("document.querySelector('#ucAdd').getBoundingClientRect().width > 90 && document.getAnimations().length === 0", "it grew with the keyboard on it")
            self.assertEqual(p.js("document.querySelector('#ucAdd .w').textContent"), "Add use case")

    def test_the_status_menu_changes_the_status_in_one_step_with_undo(self):
        with chrome() as cdp:
            p = self.edit(cdp)
            before = self.store.con.execute("SELECT count(*) FROM applies").fetchone()[0]
            self.click(p, "[data-uc-status] button")
            p.until("!!document.querySelector('[role=menu] [data-kind=\"High risk\"]')", "the three words")
            self.assertEqual(p.js("[...document.querySelectorAll('[role=menu] [role=menuitemradio]')].map(b => b.textContent.replace('✓', ''))"), ["On track", "Flag", "High risk"])
            p.js("document.querySelector('[role=menu] [data-kind=\"High risk\"]').click()")
            p.saved()
            self.assertEqual(self.row(self.demo.use_case)["status"], "High risk")
            self.assertEqual(p.toast(), "Use case 1.1 set to High risk.")
            self.assertEqual(self.store.con.execute("SELECT count(*) FROM applies").fetchone()[0], before + 1)
            self.assertEqual(p.js("document.querySelector('[data-uc-status] .ucword').textContent"), "High risk")
            self.undo(p)
            self.assertEqual(self.row(self.demo.use_case)["status"], "On track")

    def test_the_headline_and_the_name_change_in_place_and_a_press_in_them_does_not_open_the_row(self):
        with chrome() as cdp:
            p = self.edit(cdp)
            self.click(p, ".ucrow .uchead-in")
            self.assertEqual(p.js("!!document.querySelector('.ucdetail')"), False, "a press in the headline leaves the row shut")
            self.type_in(p, ".ucrow .uchead-in", "Live for three suppliers")
            p.js("document.querySelector('.ucrow .uchead-in').blur()")
            p.saved()
            self.assertEqual(self.row(self.demo.use_case)["headline"], "Live for three suppliers")
            self.assertEqual(p.toast(), "Use case 1.1 saved.")
            p.clear_toast()                                                      # the headline's Undo toast is still up: saved() would return on it
            self.click(p, ".ucrow .ucref")
            p.until("!!document.querySelector('.ucdetail .ucx-in')", "the row opened with its name")
            self.assertEqual(p.js("document.querySelector('.ucdetail .ucx-ref').textContent"), "Use case 1.1:")
            self.type_in(p, ".ucdetail .ucx-in", "Invoice matching, live")
            p.js("document.querySelector('.ucdetail .ucx-in').blur()")
            p.saved()
            self.assertEqual(self.row(self.demo.use_case)["title"], "Invoice matching, live")
            self.assertEqual(p.js("!!document.querySelector('.ucdetail')"), True, "the row stays open after a save")

    def test_add_use_case_opens_the_box_and_adds_it_hidden_from_the_client(self):
        with chrome() as cdp:
            p = self.edit(cdp)
            self.click(p, "#ucAdd")
            p.until("!!document.querySelector('#ucF')", "the box")
            self.assertEqual(p.js("document.querySelector('#ucm-title').textContent"), "Add a use case")
            self.assertEqual(p.js("[...document.querySelectorAll('#ucF label')].map(l => l.textContent)"), ["ID", "Use case", "Status", "Headline"])
            p.until("document.activeElement && document.activeElement.id === 'ucI'", "focus in the ID field")
            self.assertEqual(p.js("!document.querySelector('#main').contains(document.querySelector('#ucF')) && document.querySelector('#main').inert"), True,
                             "the box is beside <main>, which is inert behind it: the box itself is not")
            self.assertEqual(p.js("!!document.querySelector('#ucF').closest('[inert]')"), False)
            p.key("Escape", code="Escape", vk=27)
            p.until("!document.querySelector('#ucF')", "Esc closed the box")
            p.until("document.activeElement && document.activeElement.id === 'ucAdd'", "focus went back to the + button")
            self.assertEqual(p.js("document.querySelector('#main').inert"), False)
            self.click(p, "#ucAdd")
            p.until("!!document.querySelector('#ucF')", "the box again")
            self.type_in(p, "#ucI", "3.1")
            self.type_in(p, "#ucT", "Report checks")
            p.js("document.querySelector('#ucS').value = 'Flag'")
            self.type_in(p, "#ucH", "Two checks left")
            p.js("document.querySelector('#ucF').requestSubmit()")
            p.until("!document.querySelector('#ucF')", "the box closed")
            # a new use case is archived, never deleted, so its toast has no Undo (saved() waits for one): wait for its words
            p.until("(document.querySelector('.toast-text') || {}).textContent === " + json.dumps(ADDED), "the added toast")
            made = {r["ref"]: r for r in self.store.read("use_cases", "ABC")}["3.1"]
            # #455 (the owner, 03-11-2026): a new use case is hidden from the client by default (eye off): it is not on the dashboard,
            # it is counted in "from your project record", and the use cases already there are as they were
            self.assertEqual((made["title"], made["status"], made["headline"], made["client_visible"]), ("Report checks", "Flag", "Two checks left", 0))
            p.until("document.querySelector('[data-uc-back]').textContent === '+ Add a use case from your project record (3)'", "the new one is counted as off")
            self.assertEqual(p.js("document.querySelectorAll('.ucrow').length"), 2, "the new one is not on the dashboard")
            self.assertEqual(p.js("document.querySelector('.uctotal').textContent"), "2 use cases")
            self.assertEqual((self.row(self.uc3)["client_visible"], self.row(self.uc4)["client_visible"]), (0, 0))

    def test_a_new_use_case_is_hidden_at_each_width_and_theme_and_turning_its_eye_on_shows_it(self):
        """#455: at 1400 and 900 px, light and dark: the toast says the new use case is hidden from the client; it is off the
        dashboard and counted in "from your project record" until it is picked (the picker turns its eye on)."""
        n = 0
        for width in (1400, 900):
            for dark in (False, True):
                n += 1
                ref = f"7.{n}"
                with self.subTest(width=width, dark=dark), chrome() as cdp:
                    p = self.edit(cdp, width, dark)
                    off = p.js("document.querySelector('[data-uc-back]').textContent")
                    self.click(p, "#ucAdd")
                    p.until("!!document.querySelector('#ucF')", "the box")
                    # focus is in ID as soon as the box is there, not a paint later: a late focus pulled the typing from Use case back to ID
                    self.assertEqual(p.js("document.activeElement && document.activeElement.id"), "ucI", "focus is in ID when the box opens")
                    self.type_in(p, "#ucI", ref)
                    self.type_in(p, "#ucT", f"Hidden {ref}")
                    p.js("document.querySelector('#ucF').requestSubmit()")
                    p.until("!document.querySelector('#ucF')", "the box closed")
                    want = ADDED.replace("3.1", ref)
                    p.until("(document.querySelector('.toast-text') || {}).textContent === " + json.dumps(want), "the hidden toast")
                    made = {r["ref"]: r for r in self.store.read("use_cases", "ABC")}[ref]
                    self.assertEqual(made["client_visible"], 0)
                    p.until("document.querySelector('[data-uc-back]').textContent !== " + json.dumps(off), "the count went up")
                    self.assertEqual(p.js("document.querySelectorAll('.ucrow').length"), 2 + n - 1, "not on the dashboard")
                    self.assertEqual(p.js("document.documentElement.scrollWidth <= window.innerWidth"), True, "no sideways scroll")
                    self.click(p, "[data-uc-back]")
                    p.until("!!document.querySelector('form.picker')", "the picker")
                    p.js("document.querySelector('form.picker .pick input[value=\"%s\"]').click()" % made["id"])
                    p.js("document.querySelector('form.picker button[type=submit]').click()")
                    p.until("!document.querySelector('form.picker')", "the picker closed")
                    p.until("document.querySelectorAll('.ucrow').length === %d" % (2 + n), "on the dashboard once its eye is on")
                    self.assertEqual(self.store.read("use_cases", ref=made["id"])["client_visible"], 1)

    def test_an_id_already_used_is_not_added(self):
        with chrome() as cdp:
            p = self.edit(cdp)
            before = len(self.store.read("use_cases", "ABC"))
            self.click(p, "#ucAdd")
            p.until("!!document.querySelector('#ucF')", "the box")
            self.type_in(p, "#ucI", "1.2")
            self.type_in(p, "#ucT", "Same ID again")
            p.js("document.querySelector('#ucF').requestSubmit()")
            self.assertEqual(len(self.store.read("use_cases", "ABC")), before, "nothing was added")
            self.assertEqual(p.js("!!document.querySelector('#ucF')"), True, "the box stays")
            p.key("Escape", code="Escape", vk=27)
            p.until("!document.querySelector('#ucF')", "Esc closed the box")

    def test_add_from_your_project_record_offers_the_use_cases_that_are_off_and_puts_them_on(self):
        with chrome() as cdp:
            p = self.edit(cdp)
            before = self.store.con.execute("SELECT count(*) FROM applies").fetchone()[0]
            self.click(p, "[data-uc-back]")
            p.until("!!document.querySelector('form.picker')", "the picker")
            self.assertEqual(p.js("document.querySelector('form.picker h2').textContent"), PICKER)
            self.assertEqual(p.js("!!document.querySelector('form.picker').closest('[inert]')"), False, "the picker is not inside the inert page")
            self.assertEqual(p.js("document.querySelectorAll('form.picker .pick li').length"), 2)
            self.assertEqual(p.js("document.querySelector('form.picker input[type=search]').placeholder"), "Search by name, ID, owner or use case")
            p.js("document.querySelector('form.picker .pick input[value=\"%s\"]').click()" % self.uc3)
            p.js("document.querySelector('form.picker button[type=submit]').click()")
            p.until("!document.querySelector('form.picker')", "the picker closed")
            p.saved()
            self.assertEqual(self.row(self.uc3)["client_visible"], 1)
            self.assertEqual(self.row(self.uc4)["client_visible"], 0)
            self.assertEqual(self.store.con.execute("SELECT count(*) FROM applies").fetchone()[0], before + 1, "one step")
            p.until("document.querySelectorAll('.ucrow').length === 3", "the row is on the dashboard")
            self.assertEqual(p.js("document.querySelector('[data-uc-back]').textContent"), "+ Add a use case from your project record (1)")

    # ---- #485: the eye, where it stands, a next step, a link ----
    def steps(self):
        return self.store.con.execute("SELECT count(*) FROM applies").fetchone()[0]

    def open_row(self, p, ref="1.1"):
        self.click(p, ".ucrow .ucref")
        p.until("!!document.querySelector('.ucdetail')", "the row opened")

    def test_view_has_none_of_the_four_and_edit_has_them_on_each_row_and_in_an_opened_row(self):
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark), chrome() as cdp:
                    p = self.show(cdp, width, dark)
                    p.js("document.querySelector('.ucrow .ucbar').click()")
                    p.until("!!document.querySelector('.ucdetail')", "a row opened in View")
                    self.assertEqual(p.js("document.querySelectorAll('[data-uc-eye], [data-uc-step], [data-uc-link], [data-rich=standing]').length"), 0, "View has none of Edit's parts")
                    p.js("document.querySelector('[data-mode=edit]').click()")
                    p.until("!!document.querySelector('.uc [data-uc-eye]')", "Edit shows the eyes")
                    p.js("if (!document.querySelector('.ucdetail')) document.querySelector('.ucrow .ucbar').click()")
                    self.assertEqual(p.js("document.querySelectorAll('.ucrow [data-uc-eye]').length"), 2)
                    self.assertEqual(p.js("document.querySelector('[data-uc-eye]').getAttribute('aria-label')"), "Take use case 1.1 off the page")
                    p.until("!!document.querySelector('.ucdetail [data-uc-step]')", "an opened row has the box for a next step")
                    self.assertEqual(p.js("document.querySelector('[data-uc-step]').placeholder"), "+ Add a next step: \u201cOwner: what it is\u201d, then Enter")
                    self.assertEqual(p.js("document.querySelector('[data-uc-link]').textContent"), "+ Link an existing work item")
                    self.assertEqual(p.js("!!document.querySelector('.ucdetail [data-rich=standing]')"), True)
                    self.assertEqual(p.js("document.querySelectorAll('[data-uc-del], .ucdetail .danger').length"), 0, "no Delete use case: a use case is archived, never deleted")
                    self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"), "no sideways scroll")

    def test_the_eye_takes_a_use_case_off_the_page_in_one_step_and_undo_puts_it_back(self):
        with chrome() as cdp:
            p = self.edit(cdp)
            before = self.steps()
            p.js("document.querySelector('[data-uc-eye=\"%s\"]').click()" % self.uc2)
            p.saved()
            self.assertEqual(self.row(self.uc2)["client_visible"], 0)
            self.assertEqual(self.row(self.demo.use_case)["client_visible"], 1)
            self.assertEqual(p.toast(), "Use case 1.2 taken off the page.")
            self.assertEqual(self.steps(), before + 1, "one step")
            p.until("document.querySelectorAll('.ucrow').length === 1", "the row left the dashboard")
            self.assertEqual(p.js("document.querySelector('[data-uc-back]').textContent"), "+ Add a use case from your project record (3)")
            p.js("document.querySelector('[data-undo]').click()")      # row 865: Undo names the change
            p.until("((document.querySelector('.toast-text') || {}).textContent || '').startsWith('Undone')", "undone")
            self.assertEqual(self.row(self.uc2)["client_visible"], 1)
            p.until("document.querySelectorAll('.ucrow').length === 2", "Undo brought the row back")

    def test_row_865_undo_of_the_eye_names_the_use_case_and_focus_returns_to_its_eye_at_both_widths_in_both_themes(self):
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark), chrome() as cdp:
                    p = self.edit(cdp, width, dark)
                    p.js("document.querySelector('[data-uc-eye=\"%s\"]').click()" % self.uc2)
                    p.until("document.querySelectorAll('.ucrow').length === 1", "the row left the dashboard")
                    p.js("document.activeElement && document.activeElement.blur()")
                    p.until("(document.querySelector('.toast-text') || {}).textContent === 'Use case 1.2 taken off the page.'", "the toast")
                    p.until("document.getAnimations().length === 0", "the toast finished arriving")
                    p.js("document.querySelector('[data-undo]').click()")
                    p.until("(document.querySelector('.toast-text') || {}).textContent === 'Undone: Use case 1.2 taken off the page.'", "Undo names the use case")
                    p.until("document.getAnimations().length === 0", "the animations ended before focus is read")
                    p.until("document.activeElement && document.activeElement.dataset.ucEye === %s" % json.dumps(self.uc2), "focus is on the use case's eye")

    def test_where_it_stands_is_changed_in_place_in_one_step_with_one_undo(self):
        with chrome() as cdp:
            p = self.edit(cdp)
            self.click(p, ".ucrow .ucref")
            p.until("!!document.querySelector('.ucdetail [data-rich=standing]')", "the row opened with its text")
            before, was = self.steps(), self.row(self.demo.use_case)["standing"]
            p.js("document.querySelector('.ucdetail [data-rich=standing]').click()")
            p.until("!!document.querySelector('.ProseMirror')", "the editor opened in place")
            p.until("document.activeElement && document.activeElement.classList.contains('ProseMirror')", "the editor has focus")
            p.js("document.querySelector('.ProseMirror').cxed.editor.commands.insertContent('Added by the test. '); true")
            p.key("Enter", modifiers=4 if p.js("/Mac/.test(navigator.platform)") else 2, code="Enter", vk=13)
            p.saved()
            self.assertIn("Added by the test.", self.row(self.demo.use_case)["standing"])
            self.assertEqual(self.steps(), before + 1, "one save is one step")
            self.assertEqual(p.toast(), "Use case 1.1 saved.")
            self.undone(p)
            self.assertEqual(self.row(self.demo.use_case)["standing"], was)

    def test_a_next_step_is_added_with_enter_names_the_use_case_and_has_one_undo(self):
        with chrome() as cdp:
            p = self.edit(cdp)
            self.click(p, ".ucrow .ucref")
            p.until("!!document.querySelector('.ucdetail [data-uc-step]')", "the row opened")
            before = self.steps()
            self.type_in(p, "[data-uc-step]", "Sam Demo: Check the totals")
            p.key("Enter", code="Enter", vk=13)
            p.saved()
            made = [r for r in self.store.read("actions", "ABC") if r["description"] == "Check the totals"]
            self.assertEqual(len(made), 1)
            self.assertEqual((made[0]["owner"], made[0]["use_case"], made[0]["client_visible"], made[0]["status"]), ("Sam Demo", self.demo.use_case, 1, "Open"))
            self.assertIsNotNone(made[0]["due_date"], "due a week on, as in the prototype")
            self.assertEqual(self.steps(), before + 1, "one step")
            self.assertEqual(p.toast(), "Next step added to use case 1.1.")
            p.until("document.querySelector('[data-uc-step]').value === ''", "the box is empty again")
            p.until("[...document.querySelectorAll('.ucdetail ul.plain li')].some(l => l.textContent.includes('Sam Demo: Check the totals'))", "the step is in the row")
            self.undone(p)
            self.assertEqual([r for r in self.store.read("actions", "ABC") if r["description"] == "Check the totals"], [])

    def test_a_next_step_with_no_owner_keeps_the_words_and_leaves_the_owner_to_clark(self):
        with chrome() as cdp:
            p = self.edit(cdp)
            self.click(p, ".ucrow .ucref")
            p.until("!!document.querySelector('.ucdetail [data-uc-step]')", "the row opened")
            self.type_in(p, "[data-uc-step]", "Order the new cables")
            p.key("Enter", code="Enter", vk=13)
            p.saved()
            made = [r for r in self.store.read("actions", "ABC") if r["description"] == "Order the new cables"]
            self.assertEqual((len(made), made[0]["owner"]), (1, "TBC"))

    def test_the_box_is_inert_behind_and_gives_the_focus_back_even_when_the_page_is_slow_to_run_after_paint_work(self):
        """macOS CI saw the box drawn with <main> not yet inert, and Esc not giving the focus back: the page's after-paint work (Preact's
        useEffect) had not run yet. With the frame callback held back, that work waits for its tenth-of-a-second timer; the box must
        already be modal in the step that draws it, and an Esc straight away must still hand the focus back."""
        with chrome() as cdp:
            p = self.edit(cdp)
            p.js("window.requestAnimationFrame = () => 0")
            self.click(p, "#ucAdd")
            p.until("!!document.querySelector('#ucF')", "the box")
            self.assertEqual(p.js("document.querySelector('#main').inert && document.activeElement.id === 'ucI'"), True,
                             "inert behind and the focus in the ID field, as the box is drawn")
            p.key("Escape", code="Escape", vk=27)
            p.until("!document.querySelector('#ucF')", "Esc closed the box")
            self.assertEqual(p.js("document.activeElement.id === 'ucAdd' && !document.querySelector('#main').inert"), True,
                             "the focus is back on the + button and <main> is live, as the box closes")

    def test_a_toast_that_arrives_while_the_box_is_open_is_inert_and_is_released_on_close(self):
        """#425 for the use case boxes: they hold the page through inertBehind, so a toast added while one is open (it has Undo and
        Close buttons) is made inert at once, and live again when the box closes; a toast after the close is live too."""
        add = ("(() => { const t = document.createElement('div'); t.className = 'toast'; t.id = %s; t.innerHTML = '<button type=\"button\">x</button>';"
               " document.querySelector('.toasts').appendChild(t); })()")
        with chrome() as cdp:
            p = self.edit(cdp)
            self.click(p, "#ucAdd")
            p.until("!!document.querySelector('#ucF')", "the box")
            p.js(add % "'late-1'")
            p.until("document.getElementById('late-1').hasAttribute('inert')", "the late toast is inert while the box is open")
            self.assertEqual(p.js("document.querySelector('.toasts').hasAttribute('inert')"), False, "the toast region itself stays live")
            p.key("Escape", code="Escape", vk=27)
            p.until("!document.querySelector('#ucF')", "Esc closed the box")
            self.assertEqual(p.js("document.getElementById('late-1').hasAttribute('inert')"), False, "released on close")
            p.js(add % "'late-2'")
            self.assertEqual(p.js("document.getElementById('late-2').hasAttribute('inert')"), False, "a toast after the close is live")

    def test_a_step_with_a_colon_but_no_person_keeps_all_its_words_and_no_owner(self):
        """"Fix: the loader cables" names nobody: "Fix" is not taken as the owner, and the whole text is the step."""
        with chrome() as cdp:
            p = self.edit(cdp)
            self.click(p, ".ucrow .ucref")
            p.until("!!document.querySelector('.ucdetail [data-uc-step]')", "the row opened")
            self.type_in(p, "[data-uc-step]", "Fix: the loader cables")
            p.key("Enter", code="Enter", vk=13)
            p.saved()
            self.assertEqual([r for r in self.store.read("actions", "ABC") if r["owner"] == "Fix"], [], "Fix is not an owner")
            made = [r for r in self.store.read("actions", "ABC") if r["description"] == "Fix: the loader cables"]
            self.assertEqual((len(made), made[0]["owner"]), (1, "TBC"))

    def test_link_an_existing_work_item_opens_a_box_beside_main_and_links_several_in_one_step(self):
        with chrome() as cdp:
            p = self.edit(cdp)
            self.click(p, ".ucrow .ucref")
            p.until("!!document.querySelector('.ucdetail [data-uc-link]')", "the row opened")
            self.click(p, "[data-uc-link]")
            p.until("!!document.querySelector('form.uclink')", "the box")
            p.until("document.activeElement && document.activeElement.type === 'search'", "the search box has the focus")
            self.assertEqual(p.js("document.querySelector('form.uclink h2').textContent"), "Link work items to use case 1.1")
            self.assertEqual(p.js("!document.querySelector('#main').contains(document.querySelector('form.uclink')) && document.querySelector('#main').inert"), True,
                             "the box is beside <main>, which is inert behind it: the box itself is not")
            self.assertEqual(p.js("!!document.querySelector('form.uclink').closest('[inert]')"), False)
            self.assertEqual(p.js("[...document.querySelectorAll('form.uclink .seg button')].map(b => b.textContent)"), ["All", "Actions", "Risks", "Issues", "Decisions"])
            listed = p.js("[...document.querySelectorAll('form.uclink .pick input')].map(i => i.value)")
            self.assertNotIn(self.a_open, listed, "an item already linked to this use case is not offered")
            self.assertIn(self.a_later, listed, "an item linked to another use case is offered, and says so")
            self.assertIn("now in use case 1.2", p.js("document.querySelector('form.uclink .pick input[value=\"%s\"]').closest('label').textContent" % self.a_later))
            risk = self.store.read("raid", "ABC")[0]["id"]
            decision = self.store.read("decisions", "ABC")[0]["id"]
            before = self.steps()
            for item in (self.a_later, risk, decision):
                p.js("document.querySelector('form.uclink .pick input[value=\"%s\"]').click()" % item)
            self.assertEqual(p.js("document.querySelector('form.uclink [type=submit]').textContent"), "Add 3")
            p.js("document.querySelector('form.uclink [type=submit]').click()")
            p.until("!document.querySelector('form.uclink')", "the box closed")
            p.saved()
            self.assertEqual(self.store.read("actions", ref=self.a_later)["use_case"], self.demo.use_case)
            self.assertEqual(self.store.read("raid", ref=risk)["use_case"], self.demo.use_case)
            self.assertEqual(self.store.read("decisions", ref=decision)["use_case"], self.demo.use_case)
            self.assertEqual(self.steps(), before + 1, "three kinds, one step")
            self.assertEqual(p.toast(), "3 work items linked to use case 1.1.")
            self.undone(p)
            self.assertEqual(self.store.read("actions", ref=self.a_later)["use_case"], self.uc2)
            self.assertIsNone(self.store.read("raid", ref=risk)["use_case"])

    def test_the_link_box_closes_with_esc_and_gives_the_focus_back(self):
        with chrome() as cdp:
            p = self.edit(cdp)
            self.click(p, ".ucrow .ucref")
            p.until("!!document.querySelector('.ucdetail [data-uc-link]')", "the row opened")
            self.click(p, "[data-uc-link]")
            p.until("!!document.querySelector('form.uclink')", "the box")
            p.until("document.activeElement && document.activeElement.type === 'search'", "the search box has the focus")
            p.key("Escape", code="Escape", vk=27)
            p.until("!document.querySelector('form.uclink')", "Esc closed the box")
            p.until("document.activeElement && document.activeElement.hasAttribute('data-uc-link')", "focus went back to the button")
            self.assertEqual(p.js("document.querySelector('#main').inert"), False)

    def undone(self, p):
        """Press Undo and wait for the page to say it is undone (the store has been written back by then)."""
        p.js("document.querySelector('[data-undo]').click()")
        p.until("(document.querySelector('.toast-text') || {}).textContent === 'Undone.'", "undone")

    def undo(self, p):
        p.js("document.querySelector('[data-undo]').click()")
        p.until("document.querySelector('.toast-text') && document.querySelector('.toast-text').textContent === 'Undone.'", "the Undone. toast")


class PublishedFile(Published):
    def test_the_file_has_none_of_edit_for_the_use_cases(self):
        path = self.publish()
        text = path.read_text(encoding="utf-8")
        for edit_only in ("Add a use case", "Add use case", "from your project record", "data-uc-back", "uchead-in",
                          "Link an existing work item", "Add a next step", "data-uc-eye", "off the page", "data-uc-step", "data-uc-link"):
            self.assertNotIn(edit_only, text, edit_only)
        with chrome() as cdp:
            p = self.draw(cdp, path)
            self.assertEqual(p.js("document.querySelectorAll('#ucAdd, [data-uc-status], [data-uc-back], [data-uc-eye], [data-uc-step], [data-uc-link], [data-rich], .uc textarea, .uc button').length"), 0)


if __name__ == "__main__":
    unittest.main()
