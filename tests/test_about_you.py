"""#180: Settings › Personal › About you (Your name, Your email) and the profile menu's top line, in a real browser at 1400 and 900 px.
Run: python3 dev/run_tests.py test_about_you

Both are kept by clark in the data folder's settings.json (not in the browser). What is asserted: the two boxes and their words; saving
when a box is left, a reload keeps them (read from clark, not the browser); the menu's top line shows the name in bold with the email
under it, only the name when there is no email, and with neither the link "Add your name in Settings", which opens Settings and puts
the cursor in the name box; emptying the name brings the link back at once; a fresh store has no "@" anywhere in the menu; a 60
character name and email are cut with an ellipsis on one line each, never widen the menu, and carry the whole text as the tooltip;
a refusal says why in its words, ends "Nothing was saved.", writes nothing and leaves the typed text in its box.
Chrome is required: these tests fail, never skip, without it.
"""
import json
import time
import unittest

from _paths import SRC
from test_publish_dialog import Base, PAGE_SRC
from test_server import chrome

WIDTHS = (1400, 900)
NAME_LINE = "Shown at the top of your menu, as the name on each change you make, and on Excel exports and publications. Optional."
EMAIL_LINE = "Optional. Used only to tell which email addresses are your own. Nothing here sends email."


class AboutYou(Base):
    def saved(self):
        f = self.rig.data_dir / "settings.json"
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}

    def open_menu(self, p):
        """Open the profile menu, clicking again if the first click is lost: right after a page load the button is already in the page before
        the page's own script has taken it, so a click on a slow computer does nothing. It never clicks twice within a second (a second click
        would close a menu that is still drawing), and it stops at once when the menu is there."""
        p.until("(() => { if (document.querySelector('#profile-menu')) return true; "
                "if (Date.now() - (window.__menuTried || 0) > 1000) { window.__menuTried = Date.now(); document.querySelector('#profile-btn').click(); } "
                "return !!document.querySelector('#profile-menu'); })()", "the menu opened")

    def close_menu(self, p):
        p.js("document.querySelector('#profile-menu').dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))")
        p.until("!document.querySelector('#profile-menu')", "the menu closed")

    def open_settings(self, p):
        self.open_menu(p)
        p.js("document.querySelector('#profile-menu [data-kind=settings]').click()")
        p.until("!!document.querySelector('#about-name')", "About you drew")

    def type_into(self, p, field, text, leave="enter"):
        """Type `text` into the box and leave it: Enter, or a blur (headless Chrome's page has no focus, so a real blur never fires and
        is dispatched), or not at all (leave="none")."""
        p.js(f"(() => {{ const el = document.querySelector('#about-{field}'); el.value = {json.dumps(text)}; "
             "el.dispatchEvent(new Event('input', {bubbles: true})); "
             + {"enter": "el.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true, cancelable: true}));",
                "blur": "el.dispatchEvent(new FocusEvent('blur'));", "none": ""}[leave] + " })()")

    def handled(self, p, name, email=""):
        """Wait on the page, not the store: the menu's top line shows what the page has taken from clark's answer to its save (the same kind of
        signal test_report_editor.py waits on, the page has handled its save). Leaves the menu closed."""
        self.open_menu(p)
        if name or email:
            p.until(f"(() => {{ const w = document.querySelector('#profile-menu .who'); return !!w && w.querySelector('b').textContent === {json.dumps(name)} "
                    f"&& ((w.querySelector('small') || {{}}).textContent || '') === {json.dumps(email)}; }})()", "the page has taken the save")
        else:
            p.until("!!document.querySelector('#profile-menu .who-link')", "the page has taken the save")
        self.close_menu(p)

    def slow_saves(self, p, ms=1500, delays=None):
        """Hold back clark's answer to each save by `ms` in the page itself (the save is written at once; the page hears of it late), as on a
        busy computer. `delays` instead gives the hold for each save in the order they are sent (a later one can be answered first).
        window.__answered counts the answers the page has been handed."""
        p.js("(() => { window.__answered = 0; window.__sentn = 0; const d = " + json.dumps(delays) + "; const f = window.fetch; "
             "window.fetch = (u, o) => (String(u).includes('/api/profile') && o && o.method === 'POST') "
             f"? f(u, o).then((r) => new Promise((ok) => setTimeout(() => {{ window.__answered++; ok(r); }}, d ? d[Math.min(window.__sentn++, d.length - 1)] : {ms}))) : f(u, o); }})()")

    def hold_the_read(self, cdp, p):
        """Reload the page with its first read of the profile held back (as on a busy computer) until window.__release() is called; the
        read is sent then, so it answers with what the file holds at that moment. window.__readDone is set when the answer has come."""
        hold = ("(() => { const f = window.fetch; window.fetch = (u, o) => (String(u).includes('/api/profile') && !(o && o.method === 'POST')) "
                "? new Promise((ok) => { window.__release = () => ok(f(u, o).then((r) => { window.__readDone = true; return r; })); }) : f(u, o); })()")
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": hold}, p.sid)
        p.js("location.reload()")
        p.until("!!document.querySelector('#profile-btn') && typeof window.__release === 'function'", "the page is up with its read held back")

    def top(self, p):
        return p.js("(() => { const w = document.querySelector('#profile-menu .who'); if (w) return {name: w.querySelector('b').textContent, "
                    "email: (w.querySelector('small') || {}).textContent || '', title: w.title}; "
                    "const l = document.querySelector('#profile-menu .who-link'); return l ? {link: l.textContent} : null; })()")

    def test_C_the_two_boxes_and_their_words_start_empty_and_the_fresh_menu_has_no_at_sign(self):
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                p.width(w)
                self.open_menu(p)
                self.assertEqual(self.top(p), {"link": "Add your name in Settings"})
                self.assertNotIn("@", p.js("document.querySelector('#profile-menu').innerText"))
                self.close_menu(p)
                self.open_settings(p)
                self.assertEqual(p.js("document.querySelector('[data-about-you] legend').textContent"), "About you")
                self.assertEqual(p.js("[...document.querySelectorAll('[data-about-you] label')].map(l => l.textContent)"), ["Your name", "Your email"])
                self.assertEqual(p.js("[...document.querySelectorAll('[data-about-you] small')].map(l => l.textContent)"), [NAME_LINE, EMAIL_LINE])
                self.assertEqual(p.js("[document.querySelector('#about-name').value, document.querySelector('#about-email').value]"), ["", ""])
                self.assertEqual(self.saved(), {})
                self.assertEqual(p.js("Object.keys(localStorage).filter(k => /name|email|profile/i.test(k))"), [], "nothing is kept in the browser")

    def test_C_a_name_and_an_email_are_saved_by_clark_shown_at_once_and_kept_over_a_reload(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p)
            self.type_into(p, "name", "Sam Lee")
            self.type_into(p, "email", "sam@example.test")
            p.until("document.querySelector('#about-name').value === 'Sam Lee'", "the box holds it")
            self.handled(p, "Sam Lee", "sam@example.test")
            self.assertEqual(self.saved(), {"profile_email": "sam@example.test", "profile_name": "Sam Lee"})
            self.open_menu(p)
            self.assertEqual(self.top(p), {"name": "Sam Lee", "email": "sam@example.test", "title": "Sam Lee\nsam@example.test"})
            self.assertEqual(p.js("getComputedStyle(document.querySelector('#profile-menu .who b')).fontWeight >= 500"), True)
            self.close_menu(p)
            p.js("window.__before_reload = true; location.reload()")
            p.until("!window.__before_reload && !!document.querySelector('#profile-btn')", "the page again (not the one being left)")
            self.open_menu(p)
            p.until("!!document.querySelector('#profile-menu .who')", "the menu shows who you are after a reload (read from clark)")
            self.assertEqual(self.top(p)["name"], "Sam Lee")

    def test_C_a_name_alone_shows_only_the_name_and_emptying_it_brings_the_link_back_at_once(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p)
            self.type_into(p, "name", "Sam Lee", leave="blur")
            self.handled(p, "Sam Lee")
            self.assertEqual(self.saved().get("profile_name"), "Sam Lee", "leaving the box saves it")
            self.open_menu(p)
            p.until("!!document.querySelector('#profile-menu .who')", "the name shows")
            self.assertEqual(self.top(p), {"name": "Sam Lee", "email": "", "title": "Sam Lee"})
            self.close_menu(p)
            self.type_into(p, "name", "")
            self.handled(p, "")
            self.assertEqual(self.saved().get("profile_name"), "")
            self.open_menu(p)
            p.until("!!document.querySelector('#profile-menu .who-link')", "the link is back")
            self.assertEqual(self.top(p), {"link": "Add your name in Settings"})

    def test_C_the_link_opens_settings_and_puts_the_cursor_in_the_name_box(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_menu(p)
            p.js("document.querySelector('#profile-menu .who-link').click()")
            p.until("!!document.querySelector('#about-name')", "Settings › Personal drew")
            p.until("document.activeElement && document.activeElement.id === 'about-name'", "the name box has the cursor")

    def test_C_long_values_are_cut_on_one_line_each_and_never_widen_the_menu(self):
        name, email = "N" * 60, ("e" * 48) + "@example.test"
        self.assertEqual((len(name), len(email)), (60, 61))
        email = ("e" * 47) + "@example.test"
        self.assertEqual(len(email), 60)
        with chrome() as cdp:
            p = self.page(cdp)
            p.width(900)
            self.open_settings(p)
            self.type_into(p, "name", name)
            self.type_into(p, "email", email)
            self.handled(p, name, email)
            self.assertEqual(self.saved().get("profile_email"), email)
            self.open_menu(p)
            p.until("!!document.querySelector('#profile-menu .who small')", "both lines show")
            box = "document.querySelector('#profile-menu')"
            b, sm = "document.querySelector('#profile-menu .who b')", "document.querySelector('#profile-menu .who small')"
            shape = {"menu": p.js(f"Math.round({box}.getBoundingClientRect().width)"),
                     "cutName": p.js(f"{b}.scrollWidth > {b}.clientWidth"), "cutEmail": p.js(f"{sm}.scrollWidth > {sm}.clientWidth"),
                     "oneName": p.js(f"{b}.getBoundingClientRect().height < 26"), "oneEmail": p.js(f"{sm}.getBoundingClientRect().height < 26"),
                     "tip": p.js("document.querySelector('#profile-menu .who').title"),
                     "side": p.js("document.documentElement.scrollWidth <= window.innerWidth")}
            self.assertLessEqual(shape["menu"], 282, "the menu stays within 280 px")
            self.assertTrue(shape["cutName"] and shape["cutEmail"], "both are cut")
            self.assertTrue(shape["oneName"] and shape["oneEmail"], "one line each")
            self.assertEqual(shape["tip"], name + "\n" + email, "the whole text is the tooltip")
            self.assertTrue(shape["side"], "no sideways scroll")

    def test_C_a_refusal_says_why_ends_nothing_was_saved_writes_nothing_and_keeps_what_was_typed(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p)
            self.type_into(p, "name", "Sam Lee")
            self.handled(p, "Sam Lee")
            before = self.saved()
            self.assertEqual(before.get("profile_name"), "Sam Lee")
            self.type_into(p, "name", "N" * 61)
            p.until("document.querySelector('#about-name-line').parentElement.querySelector('.fld-bad').textContent !== ''", "the refusal shows")
            self.assertEqual(p.js("document.querySelector('#about-name').closest('.fld').querySelector('.fld-bad').textContent"),
                             "Your name is too long. Use 60 characters or fewer. Nothing was saved.")
            self.assertEqual(p.js("document.querySelector('#about-name').value"), "N" * 61, "what was typed stays in the box")
            self.assertEqual(self.saved(), before, "nothing was written")
            self.type_into(p, "name", "Sam Lee")
            p.until("document.querySelector('#about-name').closest('.fld').querySelector('.fld-bad').textContent === ''", "the name is saved again and its refusal is gone")
            self.type_into(p, "email", "nope")
            p.until("document.querySelector('#about-email').closest('.fld').querySelector('.fld-bad').textContent !== ''", "the email refusal shows")
            self.assertEqual(p.js("document.querySelector('#about-email').closest('.fld').querySelector('.fld-bad').textContent"),
                             "That email address is not complete. Check it, or leave it empty. Nothing was saved.")
            self.assertEqual(self.saved(), before)
            self.assertEqual(p.js("document.querySelector('#about-email').getAttribute('aria-invalid')"), "true")

    def test_C_the_menu_still_opens_when_the_first_click_is_lost(self):
        """The helper that opens the menu must survive a click the page never took (a slow computer right after a load): the first click is
        swallowed here, and the menu is there all the same, once and not toggled shut."""
        with chrome() as cdp:
            p = self.page(cdp)
            p.js("window.__swallow = 1; document.addEventListener('click', (e) => { if (window.__swallow && e.target.closest('#profile-btn')) "
                 "{ window.__swallow = 0; e.stopImmediatePropagation(); } }, true)")
            self.open_menu(p)
            self.assertEqual(p.js("window.__swallow"), 0, "the first click really was swallowed")
            self.assertEqual(p.js("document.querySelectorAll('#profile-menu').length"), 1)
            self.close_menu(p)

    def test_C_text_typed_while_a_save_is_on_its_way_stays_in_the_box(self):
        """The page must not put the saved value back over a box typed in since the save was sent (a person who keeps typing during a slow
        save would see the box go back)."""
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p)
            self.slow_saves(p)
            self.type_into(p, "name", "Sam Lee")
            self.type_into(p, "name", "Sam Lee and more", leave="none")
            p.until("window.__answered >= 1", "the page was handed the answer to its first save")
            self.handled(p, "Sam Lee")
            self.assertEqual(p.js("document.querySelector('#about-name').value"), "Sam Lee and more", "what was typed since stays in the box")
            self.type_into(p, "name", "Sam Lee and more")      # now leave it: the longer name is saved, and shown
            self.handled(p, "Sam Lee and more")
            self.assertEqual(self.saved().get("profile_name"), "Sam Lee and more")

    def test_C_an_older_good_answer_arriving_late_does_not_clear_a_newer_refusal(self):
        """A slow good save is sent first, a refused one second; the refusal is answered first and shows; the older good answer then arrives.
        It must not clear the refusal: the box still holds the refused text, so the message is what tells the person it is not saved."""
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p)
            self.type_into(p, "name", "Old Name")
            self.handled(p, "Old Name")
            self.slow_saves(p, delays=[2500, 300])
            self.type_into(p, "name", "Sam Lee")                     # sent first, answered last
            self.type_into(p, "name", "N" * 61)                      # sent second, refused, answered first
            bad = "document.querySelector('#about-name').closest('.fld').querySelector('.fld-bad').textContent"
            p.until("window.__answered >= 1", "the refusal was answered")
            p.until(f"{bad} !== ''", "the refusal shows")
            p.until("window.__answered >= 2", "the older good save was answered too")
            self.handled(p, "Sam Lee")                               # the page has taken the good answer
            time.sleep(0.3)
            self.assertEqual(p.js(bad), "Your name is too long. Use 60 characters or fewer. Nothing was saved.", "the refusal is still shown")
            self.assertEqual(p.js("document.querySelector('#about-name').value"), "N" * 61, "what was typed is still in the box")
            self.assertEqual(p.js("document.querySelector('#about-name').getAttribute('aria-invalid')"), "true")
            self.assertEqual(self.saved().get("profile_name"), "Sam Lee", "the store holds the name that was saved, not the refused one")

    def test_C_an_older_refusal_arriving_late_does_not_show_over_a_newer_good_save(self):
        """A slow refused save is sent first, a good one second; the good one is answered first; the older refusal then arrives. It must not
        show over the good text: that text is saved."""
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p)
            self.slow_saves(p, delays=[2500, 300])
            self.type_into(p, "name", "N" * 61)                      # sent first, refused, answered last
            self.type_into(p, "name", "Sam Lee")                     # sent second, answered first
            p.until("window.__answered >= 1", "the good save was answered")
            self.handled(p, "Sam Lee")
            p.until("window.__answered >= 2", "the older refused save was answered too")
            time.sleep(0.3)
            bad = "document.querySelector('#about-name').closest('.fld').querySelector('.fld-bad').textContent"
            self.assertEqual(p.js(bad), "", "no refusal over the saved text")
            self.assertEqual(p.js("document.querySelector('#about-name').value"), "Sam Lee")
            self.assertEqual(p.js("document.querySelector('#about-name').getAttribute('aria-invalid')"), None)
            self.assertEqual(self.saved().get("profile_name"), "Sam Lee")
            self.handled(p, "Sam Lee")


    def test_C_a_late_read_fills_a_box_that_was_typed_in_saved_and_left_alone(self):
        """The read of what clark has finishes after the person has typed a name and saved it: the box was typed in, but that text is saved
        and nobody has touched it since, so it follows clark again. (The file is changed behind the page's back to tell the two apart.)"""
        with chrome() as cdp:
            p = self.page(cdp)
            self.hold_the_read(cdp, p)
            self.open_settings(p)
            self.type_into(p, "name", "Sam Lee")
            self.handled(p, "Sam Lee")
            self.assertEqual(self.saved().get("profile_name"), "Sam Lee")
            (self.rig.data_dir / "settings.json").write_text(json.dumps({**self.saved(), "profile_name": "Other Name"}), encoding="utf-8")
            p.js("window.__release()")
            p.until("document.querySelector('#about-name').value === 'Other Name'", "the late read filled the saved, untouched box")

    def test_C_a_late_read_does_not_fill_a_box_typed_in_since_it_was_saved(self):
        """The same, with more typed after the save and not yet left: that box stays as typed."""
        with chrome() as cdp:
            p = self.page(cdp)
            self.hold_the_read(cdp, p)
            self.open_settings(p)
            self.type_into(p, "name", "Sam Lee")
            self.handled(p, "Sam Lee")
            self.type_into(p, "name", "Sam Lee and more", leave="none")
            (self.rig.data_dir / "settings.json").write_text(json.dumps({**self.saved(), "profile_name": "Other Name"}), encoding="utf-8")
            p.js("window.__release()")
            p.until("window.__readDone === true", "the late read was answered")
            time.sleep(0.5)
            self.assertEqual(p.js("document.querySelector('#about-name').value"), "Sam Lee and more", "what was typed since stays in the box")

    def test_C_text_typed_back_to_what_was_sent_takes_what_clark_kept(self):
        """A box that was changed while a save was on its way and then typed back to the text that was sent holds what was sent, so the
        answer goes in it: the spaces clark cut off the ends go from the box too, and the box and the saved name agree."""
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p)
            self.slow_saves(p)
            self.type_into(p, "name", "  Sam Lee  ")
            self.type_into(p, "name", "Sam", leave="none")
            self.type_into(p, "name", "  Sam Lee  ", leave="none")
            p.until("window.__answered >= 1", "the page was handed the answer")
            self.handled(p, "Sam Lee")
            self.assertEqual(p.js("document.querySelector('#about-name').value"), "Sam Lee")
            self.assertEqual(self.saved().get("profile_name"), "Sam Lee")

    def test_C_a_refused_text_typed_back_still_shows_its_refusal(self):
        """The refused text is moved away from while its answer is on its way and typed back before it arrives: the box holds the text that
        was refused, so the refusal shows, and nothing was saved."""
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p)
            self.slow_saves(p)
            self.type_into(p, "name", "N" * 61)
            self.type_into(p, "name", "Sam", leave="none")
            self.type_into(p, "name", "N" * 61, leave="none")
            p.until("window.__answered >= 1", "the refusal was answered")
            bad = "document.querySelector('#about-name').closest('.fld').querySelector('.fld-bad').textContent"
            p.until(f"{bad} !== ''", "the refusal shows")
            self.assertEqual(p.js(bad), "Your name is too long. Use 60 characters or fewer. Nothing was saved.")
            self.assertEqual(p.js("document.querySelector('#about-name').value"), "N" * 61)
            self.assertEqual(self.saved().get("profile_name"), None, "nothing was written")

    def test_C_an_older_good_email_answer_arriving_late_changes_nothing_on_the_page(self):
        """An email save is sent first and answered last; a refused one is sent second and answered first. When the older good answer arrives,
        the refusal is still under the email box, the box still holds the refused text, and the name box is as it was."""
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p)
            self.type_into(p, "name", "Old Name")
            self.handled(p, "Old Name")
            self.slow_saves(p, delays=[2500, 300])
            self.type_into(p, "email", "sam@example.com")             # sent first, answered last
            self.type_into(p, "email", "nope")                         # sent second, refused, answered first
            bad = "document.querySelector('#about-email').closest('.fld').querySelector('.fld-bad').textContent"
            p.until("window.__answered >= 1", "the refusal was answered")
            p.until(f"{bad} !== ''", "the refusal shows")
            p.until("window.__answered >= 2", "the older good save was answered too")
            time.sleep(0.5)
            self.assertEqual(p.js(bad), "That email address is not complete. Check it, or leave it empty. Nothing was saved.", "the refusal is still shown")
            self.assertEqual(p.js("document.querySelector('#about-email').value"), "nope", "what was typed is still in the box")
            self.assertEqual(p.js("document.querySelector('#about-email').getAttribute('aria-invalid')"), "true")
            self.assertEqual(p.js("document.querySelector('#about-name').value"), "Old Name", "the name box is as it was")
            self.assertEqual(p.js("document.querySelector('#about-name').getAttribute('aria-invalid')"), None)
            self.assertEqual(self.saved().get("profile_email"), "sam@example.com", "the store holds the email that was saved, not the refused one")

    def test_C_an_older_email_refusal_arriving_late_changes_nothing_on_the_page(self):
        """A refused email save is sent first and answered last; a good one is sent second and answered first. When the older refusal
        arrives, nothing shows under the email box and the box keeps the saved text."""
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p)
            self.slow_saves(p, delays=[2500, 300])
            self.type_into(p, "email", "nope")                         # sent first, refused, answered last
            self.type_into(p, "email", "sam@example.com")             # sent second, answered first
            p.until("window.__answered >= 1", "the good save was answered")
            p.until("window.__answered >= 2", "the older refused save was answered too")
            time.sleep(0.5)
            bad = "document.querySelector('#about-email').closest('.fld').querySelector('.fld-bad').textContent"
            self.assertEqual(p.js(bad), "", "no refusal over the saved text")
            self.assertEqual(p.js("document.querySelector('#about-email').value"), "sam@example.com")
            self.assertEqual(p.js("document.querySelector('#about-email').getAttribute('aria-invalid')"), None)
            self.assertEqual(self.saved().get("profile_email"), "sam@example.com")


class Source(unittest.TestCase):
    def test_the_words_are_pinned(self):
        text = (PAGE_SRC / "edit" / "Personal.jsx").read_text(encoding="utf-8")
        for words in ("<legend>About you</legend>", '"Your name"', '"Your email"', NAME_LINE, EMAIL_LINE):
            self.assertIn(words, text)
        self.assertIn("Add your name in Settings", (PAGE_SRC / "edit" / "ProfileMenu.jsx").read_text(encoding="utf-8"))

    def test_a_published_file_has_none_of_it(self):
        from clark import page
        view = page.VIEW_PAGE.read_text(encoding="utf-8")
        for word in ("About you", "Your email", "/api/profile", "Add your name in Settings"):
            self.assertNotIn(word, view)


if __name__ == "__main__":
    unittest.main()
