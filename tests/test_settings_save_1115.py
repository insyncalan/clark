"""Row 1115, S5: every setting saves at once. Appearance and Spacing say their new choice in a quiet toast with one Undo; the Brand choice has no Save
button and the Backups copy-folder keeps its Save (a half-typed path must not be saved). In a real browser at 1400 and 900 px, light and dark. Run: python3 dev/run_tests.py test_settings_save_1115
Chrome is required: these tests fail, never skip, without it."""
import unittest

from test_settings_head import Head
from test_server import chrome

WIDTHS = (1400, 900)
MODES = ("light", "dark")
TEXT = "(document.querySelector('.toast .toast-text') || {}).textContent"


class SaveAtOnce(Head):
    def test_S5_appearance_and_spacing_save_at_once_with_a_toast_and_one_undo(self):
        for w in WIDTHS:
            for mode in MODES:
                with self.subTest(width=w, mode=mode), chrome() as cdp:
                    p = self.page(cdp)
                    self.open_settings(p, w, mode)
                    p.js("document.querySelector('[data-theme-pick=dark]').click()")
                    p.until(f"{TEXT} === 'Appearance: Dark.'", "the toast says the new look")
                    self.assertEqual(p.js("document.querySelectorAll('.toast [data-undo]').length"), 1, "one Undo")
                    self.assertEqual(p.js("document.querySelector('[data-theme-pick=dark]').getAttribute('aria-checked')"), "true")
                    p.js("document.querySelector('.toast [data-undo]').click()")
                    p.until(f"{TEXT} === 'Appearance: System.'", "Undo says the look it put back")
                    self.assertEqual(p.js("document.querySelector('[data-theme-pick=system]').getAttribute('aria-checked')"), "true")
                    self.assertEqual(p.js("document.querySelectorAll('.toast [data-undo]').length"), 0, "no Undo of an Undo")
                    p.js("document.querySelector('[data-density-pick] input[value=comfortable]').click()")
                    p.until(f"{TEXT} === 'Spacing: Comfortable.'", "the toast says the new spacing")
                    p.js("document.querySelector('.toast [data-undo]').click()")
                    p.until(f"{TEXT} === 'Spacing: Compact.'", "Undo says the spacing it put back")
                    self.assertTrue(p.js("document.querySelector('[data-density-pick] input[value=compact]').checked"))

    def test_item_1168_the_motion_switch_says_its_new_state_in_a_toast_with_one_undo(self):
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                self.open_settings(p, w)
                start = p.js("document.querySelector('[data-ess-motion]').getAttribute('aria-checked')")
                now, was = ("Off", "On") if start == "true" else ("On", "Off")
                p.js("document.querySelector('[data-ess-motion]').click()")
                p.until(f"{TEXT} === 'Motion: {now}.'", "the toast says the new motion state")
                self.assertEqual(p.js("document.querySelectorAll('.toast [data-undo]').length"), 1, "one Undo")
                p.js("document.querySelector('.toast [data-undo]').click()")
                p.until(f"{TEXT} === 'Motion: {was}.'", "Undo says the state it put back")
                self.assertEqual(p.js("document.querySelector('[data-ess-motion]').getAttribute('aria-checked')"), start)
                self.assertEqual(p.js("document.querySelectorAll('.toast [data-undo]').length"), 0, "no Undo of an Undo")

    def test_S5_choosing_what_is_already_chosen_says_nothing(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p, 1400)
            p.js("document.querySelector('[data-theme-pick=system]').click()")
            p.settled("nothing to say")
            self.assertFalse(p.js("!!document.querySelector('.toast')"))

    def test_S5_the_only_save_left_is_the_backups_copy_folder_which_must_not_save_half_a_path(self):
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                self.open_settings(p, w)
                self.assertEqual(p.js("[...document.querySelectorAll('.set-cards button')].filter(b => /^save\\b/i.test(b.textContent.trim())).filter(b => !b.matches('[data-copy-save]')).map(b => b.textContent)"), [])
                self.assertEqual(p.js("document.querySelectorAll('[data-brand-save]').length"), 0, "choosing a brand saves at once")


if __name__ == "__main__":
    unittest.main()
