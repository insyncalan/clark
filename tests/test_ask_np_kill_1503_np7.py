"""Row 1503, slice 7: the survivors of the mutation sweep over the project's own asking (AskHere) in the new-projects screen.

Run: python3 dev/run_tests.py test_ask_np_kill_1503_np7
The project's block keeps the look the theme gives the asking line, and the project's button keeps the button look. Classic, 1400. Chrome is required."""
import threading
import unittest

from ask_np_settings_base_1503 import SettingsBase
from test_server import chrome


class AskHereLook(SettingsBase):
    def test_the_project_block_and_its_button_keep_their_theme_classes(self):
        with chrome() as cdp:
            js = self.show(cdp)
            self.until(js, "!!document.querySelector('[data-ask-here]')", "the project's button")
            self.assertTrue(js("document.querySelector('#ask-new-here').classList.contains('ask-new')"), "the project's block carries the ask-new class")
            self.assertTrue(js("document.querySelector('[data-ask-here]').classList.contains('btn')"), "the project's button carries the btn class")

    def test_the_project_button_offers_an_undo_that_puts_it_back(self):
        real, gate, entered = self.svc.change_new, threading.Event(), threading.Event()

        def slow(body):
            if body.get("undo"):
                entered.set()
                gate.wait(20)
            return real(body)
        self.svc.change_new = slow
        self.addCleanup(gate.set)
        with chrome() as cdp:
            js = self.show(cdp)
            self.until(js, "!!document.querySelector('[data-ask-here]')", "the project's button")
            js("document.querySelector('[data-ask-here]').click()")
            self.until(js, "!!document.querySelector('#ask-new-here [data-new-undo]')", "the project's Undo is offered")
            self.assertFalse(js("document.querySelector('#ask-new-here [data-new-undo]').disabled"), "the Undo is open before it is used")
            js("document.querySelector('#ask-new-here [data-new-undo]').click()")
            self.assertTrue(entered.wait(20), "the Undo is being saved")
            self.until(js, "document.querySelector('[data-ask-here]').disabled === true", "the project's button is shut while the Undo is saved")
            gate.set()
            self.until(js, "document.querySelector('#ask-here-state').textContent === 'Asking is on for ABC.'", "put back")


if __name__ == "__main__":
    unittest.main()
