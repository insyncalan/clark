"""Row 1503: the survivors of the mutation sweep over the first part of the new-projects read in the Settings screen (the effect that reads the switch and the project's own value).

Run: python3 dev/run_tests.py test_ask_np_kill_1503_np2
An answer that is not a good one (a refusal that still carries ok and a boolean, a 200 that does not say ok, ok as a word) shows no switch and no project button, whatever value
it carries. Classic for Settings. Chrome is required."""
import unittest

import ask_np_settings_base_1503 as base
from test_server import chrome, wait


class NotAGoodRead(base.SettingsBase):
    def shows_nothing(self, status, body):
        real = self.svc.read_new
        self.svc.read_new = lambda project=None: (status, body)
        self.addCleanup(setattr, self.svc, "read_new", real)
        with chrome() as cdp:
            js = self.show(cdp)
            self.until(js, "!!document.querySelector('#ask-state')", "the project tab")
            js("document.querySelector('[data-ask-tab=all]').click()")
            self.until(js, "!!document.querySelector('#ask-new-all')", "the row")
            self.assertFalse(wait(lambda: js("!!document.querySelector('[data-new-switch]')"), 3), "no switch for the row")
            js("document.querySelector('[data-ask-tab]:not([data-ask-tab=all])').click()")
            self.until(js, "!!document.querySelector('#ask-state')", "the project tab again")
            self.assertFalse(wait(lambda: js("!!document.querySelector('[data-ask-here]')"), 3), "no button for the project")

    def test_a_server_error_that_still_says_ok_and_a_value_is_not_a_read(self):
        self.shows_nothing(500, {"ok": True, "on": True, "off_here": False})

    def test_a_refusal_that_still_says_ok_and_a_value_is_not_a_read(self):
        self.shows_nothing(404, {"ok": True, "on": True, "off_here": False})

    def test_a_200_that_says_not_ok_is_not_a_read(self):
        self.shows_nothing(200, {"ok": False, "on": True, "off_here": False})

    def test_a_200_that_says_ok_as_a_word_is_not_a_read(self):
        self.shows_nothing(200, {"ok": "true", "on": True, "off_here": False})

    def test_a_200_with_no_ok_is_not_a_read(self):
        self.shows_nothing(200, {"on": True, "off_here": False})


if __name__ == "__main__":
    unittest.main()
