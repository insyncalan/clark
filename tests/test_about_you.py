"""#180: Settings › Profile › About you (Your name, Your email) and the profile menu's top line, in a real browser at 1400 and 900 px.
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

from clark.settings import EMAIL_BAD, NAME_TOO_LONG    # the one place the refusal sentences are written; test_profile_settings pins their words
from _new_page import reload_to_new_page
from _paths import SRC
from test_publish_dialog import Base, PAGE_SRC
from test_server import chrome

WIDTHS = (1400, 900)
NAME_LINE = "Shown at the top of your menu, as the name on each change you make, and on Excel exports and publications. Optional."
EMAIL_LINE = "Optional. Used only to tell which email addresses are your own. Nothing here sends email."
ALIAS_LINE = "Your first name and your initials, worked out from your full name. You can change it."     # item 613: the Alias box under the name


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
        p.js("document.querySelector('#profile-menu [data-kind=settings], #profile-menu [data-kind=who]').click()")
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
        window.__answered counts the answers the page has been handed; window.__handled counts those it has had time to take in (their body read and two drawn frames),
        so a test that checks that a late answer changed nothing waits on it, not on a fixed time."""
        p.js("(() => { window.__answered = 0; window.__handled = 0; window.__sentn = 0; const d = " + json.dumps(delays) + "; const f = window.fetch; "
             "window.fetch = (u, o) => (String(u).includes('/api/profile') && o && o.method === 'POST') "
             f"? f(u, o).then((r) => new Promise((ok) => setTimeout(() => {{ const c = r.clone(); window.__answered++; ok(r); c.text().then(() => setTimeout(() => requestAnimationFrame(() => requestAnimationFrame(() => window.__handled++)), 0)); }}, d ? d[Math.min(window.__sentn++, d.length - 1)] : {ms}))) : f(u, o); }})()")

    def hold_the_read(self, cdp, p):
        """Reload the page with its first read of the profile held back (as on a busy computer) until window.__release() is called; the
        read is sent then, so it answers with what the file holds at that moment. window.__readDone is set when the answer has come."""
        hold = ("(() => { const f = window.fetch; window.fetch = (u, o) => (String(u).includes('/api/profile') && !(o && o.method === 'POST')) "
                "? new Promise((ok) => { window.__release = () => ok(f(u, o).then((r) => { window.__readDone = true; return r; })); }) : f(u, o); })()")
        cdp.call("Page.enable", {}, p.sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": hold}, p.sid)
        reload_to_new_page(p.js, "!!document.querySelector('#profile-btn') && typeof window.__release === 'function'",
                           "the page is up with its read held back")

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
                self.assertEqual(p.js("[...document.querySelectorAll('[data-about-you] label')].map(l => l.textContent)"), ["Your name", "Alias", "Your email"])
                self.assertEqual(p.js("[...document.querySelectorAll('[data-about-you] small')].map(l => l.textContent)"), [NAME_LINE, ALIAS_LINE, EMAIL_LINE])
                self.assertEqual(p.js("[document.querySelector('#about-name').value, document.querySelector('#about-email').value]"), ["", ""])
                self.assertEqual(self.saved(), {})
                self.assertEqual(p.js("Object.keys(localStorage).filter(k => /name|email|profile/i.test(k))"), [], "nothing is kept in the browser")

    def test_C_a_name_and_an_email_are_saved_by_clark_shown_at_once_and_kept_over_a_reload(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p)
            self.type_into(p, "name", "Sam Lee")
            self.handled(p, "Sam Lee")                     # row 773: the first save is taken before the second is sent, so two saves are never in flight at once (a slow runner answered them out of order)
            self.type_into(p, "email", "sam@example.test")
            p.until("document.querySelector('#about-name').value === 'Sam Lee'", "the box holds it")
            self.handled(p, "Sam Lee", "sam@example.test")
            self.assertEqual(self.saved(), {"profile_email": "sam@example.test", "profile_name": "Sam Lee", "profile_alias": "Sam, SL"})
            self.open_menu(p)
            self.assertEqual(self.top(p), {"name": "Sam Lee", "email": "sam@example.test", "title": "Sam Lee\nsam@example.test"})
            self.assertEqual(p.js("getComputedStyle(document.querySelector('#profile-menu .who b')).fontWeight >= 500"), True)
            self.close_menu(p)
            reload_to_new_page(p.js, "!!document.querySelector('#profile-btn')", "the page again (not the one being left)")
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
            p.until("!!document.querySelector('#about-name')", "Settings › Profile drew")
            p.until("document.activeElement && document.activeElement.id === 'about-name'", "the name box has the cursor")

    def test_C_the_link_when_already_on_profile_puts_the_cursor_in_the_name_box_and_leaves_no_stale_wish(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p)
            p.js("document.activeElement.blur()")
            self.open_menu(p)
            p.js("document.querySelector('#profile-menu .who-link').click()")      # already on s=profile: no new address, so no new draw from the address
            p.until("document.activeElement && document.activeElement.id === 'about-name'", "the name box has the cursor")
            p.js("document.activeElement.blur(); location.hash = '#dashboard&p=PUB'")
            p.until("!document.querySelector('#about-name')", "left Settings")
            p.js("location.hash = '#settings&p=PUB&s=profile'")
            p.until("!!document.querySelector('#about-name')", "Profile drew again")
            p.settled("Profile finished drawing")
            self.assertNotEqual(p.js("document.activeElement && document.activeElement.id"), "about-name", "the wish was spent, not kept")

    def test_C_a_wish_made_while_no_box_draws_is_spent_on_leaving_Settings(self):
        """"Add your name" can be asked for while the box is not drawn (here: the test hook asks on Backups). Leaving Settings spends the wish, so a
        later visit to Profile does not put the cursor in the name box."""
        with chrome() as cdp:
            p = self.page(cdp)
            p.js("location.hash = '#settings&p=PUB&s=backups'")
            p.until("!!document.getElementById('safety-h') && !document.querySelector('#about-name')", "Backups drew, with no name box")
            p.js("window.clarkPage.wantName(true)")
            p.js("location.hash = '#dashboard&p=PUB'")
            p.until("!document.getElementById('safety-h')", "left Settings")
            p.js("location.hash = '#settings&p=PUB&s=profile'")
            p.until("!!document.querySelector('#about-name')", "Profile drew")
            p.settled("Profile finished drawing")
            self.assertNotEqual(p.js("document.activeElement && document.activeElement.id"), "about-name", "the wish was spent on leaving, not kept")

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
                             NAME_TOO_LONG)
            self.assertEqual(p.js("document.querySelector('#about-name').value"), "N" * 61, "what was typed stays in the box")
            self.assertEqual(self.saved(), before, "nothing was written")
            self.type_into(p, "name", "Sam Lee")
            p.until("document.querySelector('#about-name').closest('.fld').querySelector('.fld-bad').textContent === ''", "the name is saved again and its refusal is gone")
            self.type_into(p, "email", "nope")
            p.until("document.querySelector('#about-email').closest('.fld').querySelector('.fld-bad').textContent !== ''", "the email refusal shows")
            self.assertEqual(p.js("document.querySelector('#about-email').closest('.fld').querySelector('.fld-bad').textContent"),
                             EMAIL_BAD)
            self.assertEqual(self.saved(), before)
            self.assertEqual(p.js("document.querySelector('#about-email').getAttribute('aria-invalid')"), "true")

    def test_C_a_refusal_is_the_servers_own_sentence_so_a_reworded_one_reaches_the_box(self):
        """#496: the page shows the sentence clark sends, not a copy of its own. The route's sentence is changed for this test only."""
        import clark.settings as settings
        reworded = "Your name is longer than 60 characters, so it was left as it was. Nothing was saved."
        self.assertNotEqual(reworded, NAME_TOO_LONG)
        old = settings.NAME_TOO_LONG
        settings.NAME_TOO_LONG = reworded
        self.addCleanup(setattr, settings, "NAME_TOO_LONG", old)
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p)
            self.type_into(p, "name", "N" * 61)
            bad = "document.querySelector('#about-name').closest('.fld').querySelector('.fld-bad').textContent"
            p.until(f"{bad} !== ''", "the refusal shows")
            self.assertEqual(p.js(bad), reworded)

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

    def refused_under(self, p, field):
        return p.js(f"document.querySelector('#about-{field}').closest('.fld').querySelector('.fld-bad').textContent")

    def test_C_a_refusal_shows_under_the_box_it_is_about_email_left_first_then_a_name_is_typed(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p)
            self.type_into(p, "email", "nope", leave="blur")
            p.until("document.querySelector('#about-email').closest('.fld').querySelector('.fld-bad').textContent !== ''", "the email refusal shows")
            self.type_into(p, "name", "Sam Lee")
            p.until("document.querySelector('#about-email').closest('.fld').querySelector('.fld-bad').textContent !== ''", "still under the email")
            time.sleep(1)
            self.assertEqual(self.refused_under(p, "name"), "", "nothing under the name box")
            self.assertEqual(self.refused_under(p, "email"), EMAIL_BAD)
            self.assertEqual(p.js("[document.querySelector('#about-name').value, document.querySelector('#about-email').value]"), ["Sam Lee", "nope"])
            self.assertEqual(self.saved(), {})

    def test_C_a_refusal_shows_under_the_box_it_is_about_name_left_first_then_an_email_is_typed(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p)
            self.type_into(p, "name", "N" * 61, leave="blur")
            p.until("document.querySelector('#about-name').closest('.fld').querySelector('.fld-bad').textContent !== ''", "the name refusal shows")
            self.type_into(p, "email", "sam@example.test")
            time.sleep(1)
            self.assertEqual(self.refused_under(p, "email"), "", "nothing under the email box")
            self.assertEqual(self.refused_under(p, "name"), NAME_TOO_LONG)
            self.assertEqual(p.js("[document.querySelector('#about-name').value, document.querySelector('#about-email').value]"), ["N" * 61, "sam@example.test"])
            self.assertEqual(self.saved(), {})

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
        It must not clear the refusal: the box still holds the refused text, so the message is what tells the person it is not saved.
        REGRESSION GUARD, not a test of #262's fix: this already held before it (the older answer is dropped by the existing `!r.newest` check)."""
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
            p.until("window.__handled >= 2", "the late answer has been taken in")
            self.assertEqual(p.js(bad), NAME_TOO_LONG, "the refusal is still shown")
            self.assertEqual(p.js("document.querySelector('#about-name').value"), "N" * 61, "what was typed is still in the box")
            self.assertEqual(p.js("document.querySelector('#about-name').getAttribute('aria-invalid')"), "true")
            self.assertEqual(self.saved().get("profile_name"), "Sam Lee", "the store holds the name that was saved, not the refused one")

    def test_C_an_older_refusal_arriving_late_does_not_show_over_a_newer_good_save(self):
        """A slow refused save is sent first, a good one second; the good one is answered first; the older refusal then arrives. It must not
        show over the good text: that text is saved.
        REGRESSION GUARD, not a test of #262's fix: this already held before it (the older answer is dropped by the existing `!r.newest` check)."""
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p)
            self.slow_saves(p, delays=[2500, 300])
            self.type_into(p, "name", "N" * 61)                      # sent first, refused, answered last
            self.type_into(p, "name", "Sam Lee")                     # sent second, answered first
            p.until("window.__answered >= 1", "the good save was answered")
            self.handled(p, "Sam Lee")
            p.until("window.__answered >= 2", "the older refused save was answered too")
            p.until("window.__handled >= 2", "the late answer has been taken in")
            bad = "document.querySelector('#about-name').closest('.fld').querySelector('.fld-bad').textContent"
            self.assertEqual(p.js(bad), "", "no refusal over the saved text")
            self.assertEqual(p.js("document.querySelector('#about-name').value"), "Sam Lee")
            self.assertEqual(p.js("document.querySelector('#about-name').getAttribute('aria-invalid')"), None)
            self.assertEqual(self.saved().get("profile_name"), "Sam Lee")
            self.handled(p, "Sam Lee")

    # ── the toast and Undo (#429) ───────────────────────────────────────────

    def toast_is(self, p, text):
        p.until(f"(document.querySelector('.toast .toast-text') || {{}}).textContent === {json.dumps(text)}", f"the toast says {text}")

    def has_undo(self, p):
        return p.js("!!document.querySelector('.toast [data-undo]')")

    def test_C_saving_the_name_or_the_email_says_so_with_undo_and_a_second_save_of_the_same_words_says_nothing(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p)
            self.type_into(p, "name", "Sam Lee")
            self.toast_is(p, "Name saved.")
            self.assertTrue(self.has_undo(p), "Undo is offered")
            self.type_into(p, "email", "sam@example.test")
            self.toast_is(p, "Email saved.")
            self.assertTrue(self.has_undo(p))
            p.js("document.querySelector('[data-dismiss]').click()")
            p.until("!document.querySelector('.toast')", "the toast went")
            self.type_into(p, "email", "sam@example.test")           # the same words again: nothing changed
            self.handled(p, "Sam Lee", "sam@example.test")
            time.sleep(0.3)
            self.assertIsNone(p.js("document.querySelector('.toast')"), "nothing changed, so nothing is said")

    def test_C_undo_puts_the_old_value_back_in_the_box_the_menu_and_the_store(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p)
            self.type_into(p, "name", "Sam Lee")
            self.handled(p, "Sam Lee")
            self.type_into(p, "name", "Sam Lee Two")
            self.toast_is(p, "Name saved.")
            self.handled(p, "Sam Lee Two")
            self.assertEqual(self.saved().get("profile_name"), "Sam Lee Two")
            p.js("document.querySelector('.toast [data-undo]').click()")
            self.handled(p, "Sam Lee")
            self.assertEqual(p.js("document.querySelector('#about-name').value"), "Sam Lee", "the box has the old name")
            self.assertEqual(self.saved().get("profile_name"), "Sam Lee", "clark has the old name")
            self.assertFalse(self.has_undo(p), "the Undo is used up")
            self.toast_is(p, "Name is back to Sam Lee.")

    def test_C_undo_of_the_first_name_empties_the_box_and_the_menu_asks_for_a_name_again(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p)
            self.type_into(p, "name", "Sam Lee")
            self.toast_is(p, "Name saved.")
            self.handled(p, "Sam Lee")
            p.js("document.querySelector('.toast [data-undo]').click()")
            self.handled(p, "", "")
            self.assertEqual(p.js("document.querySelector('#about-name').value"), "")
            self.assertEqual(self.saved().get("profile_name", ""), "")
            self.toast_is(p, "Name is blank again.")

    def test_C_a_refused_save_shows_no_toast_and_no_undo(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p)
            self.type_into(p, "name", "N" * 61)
            p.until("document.querySelector('#about-name').closest('.fld').querySelector('.fld-bad').textContent !== ''", "the refusal shows")
            time.sleep(0.3)
            self.assertIsNone(p.js("document.querySelector('.toast')"), "a refusal is said under the box, not in a toast")
            self.assertEqual(self.saved().get("profile_name", ""), "")

    def test_C_typing_again_after_a_save_takes_the_undo_away_and_nothing_goes_back(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p)
            self.type_into(p, "name", "Sam Lee")
            self.handled(p, "Sam Lee")
            self.type_into(p, "name", "Sam Lee Two")
            self.toast_is(p, "Name saved.")
            self.handled(p, "Sam Lee Two")
            self.type_into(p, "name", "Sam Lee Three", leave="none")
            p.until("!document.querySelector('.toast [data-undo]')", "the Undo is gone once the person has typed again")
            self.assertEqual(p.js("document.querySelector('#about-name').value"), "Sam Lee Three", "what was typed stays")
            self.assertEqual(self.saved().get("profile_name"), "Sam Lee Two")

    def test_C_a_late_read_does_not_make_a_save_of_the_stored_words_look_like_a_change(self):
        """Nothing is offered for a save until clark has said what it holds: a first save never turns the stored words into an 'old value'."""
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p)
            self.type_into(p, "name", "Sam Lee")
            self.handled(p, "Sam Lee")
            reload_to_new_page(p.js, "!!document.querySelector('#profile-btn')", "the page again")
            p.js("location.hash = '#settings&p=PUB&s=profile'")      # with a name given the circle's Settings entry opens Projects (item 1024), so the Profile page is asked for by its address
            p.until("!!document.querySelector('#about-name')", "About you drew")
            p.until("document.querySelector('#about-name').value === 'Sam Lee'", "the box follows what clark holds")
            self.type_into(p, "name", "Sam Lee")                      # the stored words, saved again
            self.handled(p, "Sam Lee")
            time.sleep(0.3)
            self.assertIsNone(p.js("document.querySelector('.toast')"))

    def both_boxes(self, p, name, email):
        """Change both boxes, then Enter in the name box: one save carries both."""
        p.js("(() => { for (const [f, v] of [['name', %s], ['email', %s]]) { const el = document.querySelector('#about-' + f); "
             "el.value = v; el.dispatchEvent(new Event('input', {bubbles: true})); } "
             "document.querySelector('#about-name').dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true, cancelable: true})); })()"
             % (json.dumps(name), json.dumps(email)))

    def test_C_an_emptied_box_says_cleared_and_undo_says_what_went_back(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p)
            self.type_into(p, "name", "Sam Lee")
            self.handled(p, "Sam Lee")
            self.type_into(p, "email", "sam@example.test")
            self.toast_is(p, "Email saved.")
            self.type_into(p, "name", "")
            self.toast_is(p, "Name cleared.")
            self.assertTrue(self.has_undo(p))
            p.js("document.querySelector('.toast [data-undo]').click()")
            self.toast_is(p, "Name is back to Sam Lee.")
            self.assertEqual(p.js("document.querySelector('#about-name').value"), "Sam Lee")
            self.type_into(p, "email", "")
            self.toast_is(p, "Email cleared.")
            p.js("document.querySelector('.toast [data-undo]').click()")
            self.toast_is(p, "Email is back to sam@example.test.")
            self.assertEqual(self.saved().get("profile_email"), "sam@example.test")

    def test_C_one_save_of_both_boxes_says_both_and_one_undo_takes_both_back(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p)
            self.both_boxes(p, "Sam Lee", "sam@example.test")
            self.toast_is(p, "Name and email saved.")
            p.js("document.querySelector('.toast [data-undo]').click()")
            self.toast_is(p, "Name and email are back as they were.")
            self.assertEqual(self.saved().get("profile_name", ""), "")
            self.assertEqual(self.saved().get("profile_email", ""), "")
            self.both_boxes(p, "Sam Lee", "sam@example.test")
            self.toast_is(p, "Name and email saved.")
            self.both_boxes(p, "", "")
            self.toast_is(p, "Name and email cleared.")
            self.both_boxes(p, "Sam Lee", "sam@example.test")
            self.toast_is(p, "Name and email saved.")
            self.both_boxes(p, "", "other@example.test")
            self.toast_is(p, "Name cleared. Email saved.")

    # ── the toast in View goes as it does in Edit (#429) ────────────────────

    def quick_toasts(self, p):
        """Make the toast's 5 seconds 0.4 s: the page's own timer (changes.js say), only shorter."""
        p.js("(() => { const t = window.setTimeout; window.setTimeout = (f, ms, ...a) => t(f, ms === 5000 ? 400 : ms, ...a); })()")

    def test_C_in_view_the_toast_goes_after_its_time_like_in_edit(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p)
            self.assertEqual(p.js("document.querySelectorAll('[data-mode]').length"), 0, "row 826: Settings has no View | Edit switch, so the page is in View")
            self.quick_toasts(p)
            self.type_into(p, "name", "Sam Lee")
            self.toast_is(p, "Name saved.")
            p.until("!document.querySelector('.toast')", "the toast went by itself in View")

    def test_C_in_view_close_takes_the_toast_away_and_the_line_after_undo_shows_and_closes(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p)
            self.type_into(p, "name", "Sam Lee")
            self.toast_is(p, "Name saved.")
            p.js("document.querySelector('.toast [data-dismiss]').click()")
            p.until("!document.querySelector('.toast')", "Close took it away")
            self.type_into(p, "name", "Sam Lee Two")
            self.toast_is(p, "Name saved.")
            self.handled(p, "Sam Lee Two")
            p.js("document.querySelector('.toast [data-undo]').click()")
            self.toast_is(p, "Name is back to Sam Lee.")
            self.assertFalse(self.has_undo(p), "no Undo on the line after Undo")
            p.js("document.querySelector('.toast [data-dismiss]').click()")
            p.until("!document.querySelector('.toast')", "the line after Undo closed")

    def test_C_in_view_typing_again_takes_the_toast_away(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p)
            self.type_into(p, "name", "Sam Lee")
            self.toast_is(p, "Name saved.")
            self.type_into(p, "name", "Sam Lee Two", leave="none")
            p.until("!document.querySelector('.toast')", "the toast went once the person typed again")

    def test_C_in_view_leaving_settings_takes_the_toast_and_its_undo_away(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p)
            self.type_into(p, "name", "Sam Lee")
            self.toast_is(p, "Name saved.")
            self.assertTrue(self.has_undo(p))
            p.js("[...document.querySelectorAll('.tab')].find((t) => t.dataset.view !== 'settings').click()")
            p.until("!document.querySelector('#about-name')", "Settings was left")
            p.until("!document.querySelector('.toast')", "the toast did not follow the person to the report")
            self.assertFalse(self.has_undo(p))
            self.assertEqual(self.saved().get("profile_name"), "Sam Lee", "leaving does not undo anything")


    def test_C_a_late_read_fills_a_box_that_was_typed_in_saved_and_left_alone(self):
        """The read of what clark has finishes after the person has typed a name and saved it: the box was typed in, but that text is saved
        and nobody has touched it since, so it follows clark again. (The file is changed behind the page's back to tell the two apart.)"""
        with chrome() as cdp:
            p = self.page(cdp)
            self.hold_the_read(cdp, p)
            self.open_settings(p)
            self.type_into(p, "email", "sam@example.test", leave="none")      # both boxes typed in: the save has nothing to wait for the read for (#420)
            self.type_into(p, "name", "Sam Lee")
            self.handled(p, "Sam Lee", "sam@example.test")
            self.assertEqual(self.saved().get("profile_name"), "Sam Lee")
            (self.rig.data_dir / "settings.json").write_text(json.dumps({**self.saved(), "profile_name": "Other Name"}), encoding="utf-8")
            p.js("window.__release()")
            p.until("document.querySelector('#about-name').value === 'Other Name'", "the late read filled the saved, untouched box")

    def test_C_a_save_made_before_the_first_read_has_landed_keeps_the_other_box_saved_value(self):
        """#420: clark holds a name and an email; the page's read of them is held back, and the person saves the name first. The email box has
        only the empty draw then, so the save must not send it as empty: the saved email is kept and the saved name is the new one."""
        with chrome() as cdp:
            p = self.page(cdp)
            (self.rig.data_dir / "settings.json").write_text(
                json.dumps({**self.saved(), "profile_name": "Old Name", "profile_email": "old@example.com"}), encoding="utf-8")
            self.hold_the_read(cdp, p)
            self.open_settings(p)
            self.assertEqual(p.js("document.querySelector('#about-email').value"), "", "the read has not landed: the box is the empty draw")
            self.type_into(p, "name", "Sam Lee")
            time.sleep(0.5)
            p.js("window.__release()")
            deadline = time.time() + 10
            while time.time() < deadline and self.saved().get("profile_name") != "Sam Lee":
                time.sleep(0.1)
            self.assertEqual(self.saved().get("profile_name"), "Sam Lee")
            self.assertEqual(self.saved().get("profile_email"), "old@example.com", "the other box's saved value is kept")

    def test_C_a_late_read_does_not_fill_a_box_typed_in_since_it_was_saved(self):
        """The same, with more typed after the save and not yet left: that box stays as typed."""
        with chrome() as cdp:
            p = self.page(cdp)
            self.hold_the_read(cdp, p)
            self.open_settings(p)
            self.type_into(p, "email", "sam@example.test", leave="none")      # both boxes typed in: the save has nothing to wait for the read for (#420)
            self.type_into(p, "name", "Sam Lee")
            self.handled(p, "Sam Lee", "sam@example.test")
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
            self.assertEqual(p.js(bad), NAME_TOO_LONG)
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
            self.assertEqual(p.js(bad), EMAIL_BAD, "the refusal is still shown")
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
    def test_the_toast_words_are_pinned(self):
        """The words agreed on #429 (01-11-2026), each as the file builds it."""
        text = (PAGE_SRC / "edit" / "aboutYouToast.js").read_text(encoding="utf-8")
        for words in ("Name ${said(r.name)}.", "Email ${said(r.email)}.", "Name and email ${said(r.name)}.", "Name ${said(r.name)}. Email ${said(r.email)}.",
                      '"cleared"', '"saved"', "Name is blank again.", "Name is back to ${b.name}.", "Email is blank again.", "Email is back to ${b.email}.",
                      "Name and email are back as they were."):
            self.assertIn(words, text)
        self.assertNotIn("Undone.", text)
        self.assertNotIn("Name and email saved. ", text)
        self.assertTrue((PAGE_SRC / "edit" / "ProfileMenu.jsx").read_text(encoding="utf-8").count("toast.value.own") == 1, "View draws only About you's own toast")

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


class KeysGroupHasNoFrame(unittest.TestCase):
    """Row 792: the Keys group on Settings, Personal takes the same frameless group look as Appearance (the .styles fieldset), not the browser's boxed fieldset."""

    def test_the_keys_fieldset_uses_the_frameless_group_class(self):
        import re
        src = (PAGE_SRC / "edit" / "Personal.jsx").read_text(encoding="utf-8")
        m = re.search(r'<fieldset\s+class="([^"]*)"[^>]*>\s*<legend>\s*Keys\s*</legend>', src)
        self.assertIsNotNone(m, "the Keys fieldset was not found in Personal.jsx")
        self.assertIn("styles", m.group(1).split(), "the Keys fieldset has no frameless .styles class, so it is drawn with the browser's 1 px box")


if __name__ == "__main__":
    unittest.main()
