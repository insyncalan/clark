"""#440 row 5: a good save of Settings › Personal › About you's Name or Email box says "Name saved" / "Email saved" in the toast, with Undo
(as the prototype does, system/prototype/views.js setProfile's toast). Undo puts back what that box held before, in clark's settings and in
the box, and leaves the other box as it is. A save that changed nothing says nothing. In a real browser at 1400 and 900 px.
Run: python3 dev/run_tests.py test_about_you_toast
Chrome is required: these tests fail, never skip, without it.
"""
import unittest

import test_about_you as base                 # the module, so its own tests are not collected again here
from test_publish_dialog import Base
from test_server import chrome

TEXT = "((document.querySelector('.toasts .toast .toast-text') || {}).textContent || '')"


class AboutYouToast(Base):
    # test_about_you's helpers, borrowed one by one (not by subclassing, which would run all of its tests again here)
    saved, open_menu, close_menu, open_settings, type_into, handled, slow_saves = (
        base.AboutYou.saved, base.AboutYou.open_menu, base.AboutYou.close_menu, base.AboutYou.open_settings,
        base.AboutYou.type_into, base.AboutYou.handled, base.AboutYou.slow_saves)

    def toast_says(self, p, words):
        p.until(f"{TEXT} === {words!r}", f"the toast says {words}")

    def test_C_at_1400_name_and_email_saves_say_so_with_undo_and_undo_puts_each_back(self):
        self.saves_and_undo(1400)

    def test_C_at_900_name_and_email_saves_say_so_with_undo_and_undo_puts_each_back(self):
        self.saves_and_undo(900)

    def saves_and_undo(self, w):
        """One width per test: each test has its own fresh store (the rig), so the first save always changes something."""
        with chrome() as cdp:
            p = self.page(cdp)
            p.width(w)
            self.open_settings(p)
            self.type_into(p, "name", "Sam Lee")
            self.toast_says(p, "Name saved")
            self.assertTrue(p.js("!!document.querySelector('.toasts .toast [data-undo]')"), "the toast carries Undo")
            self.assertEqual(p.js("document.querySelector('.toasts .toast [data-undo]').textContent"), "Undo")
            self.type_into(p, "email", "sam@example.test")
            self.toast_says(p, "Email saved")
            self.handled(p, "Sam Lee", "sam@example.test")
            self.assertEqual(self.saved(), {"profile_email": "sam@example.test", "profile_name": "Sam Lee"})

            p.js("document.querySelector('.toasts .toast [data-undo]').click()")
            self.toast_says(p, "Undone.")
            p.until("document.querySelector('#about-email').value === ''", "the email box is back to what it held")
            self.handled(p, "Sam Lee")
            self.assertEqual(self.saved(), {"profile_email": "", "profile_name": "Sam Lee"}, "only the email went back")
            self.assertEqual(p.js("document.querySelector('#about-name').value"), "Sam Lee", "the name box is left as it is")

            self.type_into(p, "name", "Sam Moe")
            self.toast_says(p, "Name saved")
            p.js("document.querySelector('.toasts .toast [data-undo]').click()")
            self.toast_says(p, "Undone.")
            p.until("document.querySelector('#about-name').value === 'Sam Lee'", "the name box is back to what it held")
            self.handled(p, "Sam Lee")
            self.assertEqual(self.saved().get("profile_name"), "Sam Lee")
            self.assertFalse(p.js("!!document.querySelector('.toasts .toast [data-undo]')"), "Undone. carries no Undo")

    def test_C_a_save_that_changed_nothing_or_was_refused_says_no_saved_toast(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p)
            self.type_into(p, "name", "Sam Lee")
            self.toast_says(p, "Name saved")
            p.js("document.querySelector('.toasts .toast [data-dismiss]').click()")
            p.until(f"{TEXT} === ''", "the toast is gone")
            self.slow_saves(p, ms=0)
            self.type_into(p, "name", "Sam Lee")                          # the same again: nothing changed
            p.until("window.__handled >= 1", "the page has taken the answer")
            self.assertEqual(p.js(TEXT), "", "no toast for a save that changed nothing")
            self.type_into(p, "name", "N" * 61)                           # refused: the refusal shows under the box
            p.until("document.querySelector('#about-name').closest('.fld').querySelector('.fld-bad').textContent !== ''", "the refusal shows")
            self.assertEqual(p.js(TEXT), "", "no toast for a refused save")


if __name__ == "__main__":
    unittest.main()
