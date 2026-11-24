"""Row 1503, slice 4 of the new-projects screen: what the page does with the answer to a change (the check on the answer, the Undo it offers, the words for a busy server).

Run: python3 dev/run_tests.py test_ask_np_kill_1503_np4
Classic, 1400. Chrome is required."""
import unittest

import test_ask_new_projects_ui_1503 as base
from test_server import chrome


class Answer(unittest.TestCase):
    # the helpers of the base page test are borrowed by name; its own tests are not inherited, so they are not run again here
    setUp = base.CannotBeSaved.setUp
    until = base.CannotBeSaved.until
    refused = base.CannotBeSaved.refused
    open_all = base.CannotBeSaved.open_all

    def test_an_answer_with_no_value_is_not_a_saved_change(self):
        """A 200 that says ok and carries a step but no value for the switch is not a save: the words show, the switch stays, no Undo."""
        self.refused(200, {"ok": True, "off_here": False, "apply_id": "x1"})
        with chrome() as cdp:
            js = self.open_all(cdp)
            js("document.querySelector('[data-new-switch]').click()")
            self.until(js, "!!document.querySelector('#ask-new-all .error')", "the words")
            self.assertEqual(js("document.querySelector('[data-new-switch]').getAttribute('aria-checked')"), "true", "the switch stays where it was")
            self.assertFalse(js("!!document.querySelector('[data-new-undo]')"), "no Undo for an answer with no value")

    def test_an_answer_that_is_not_json_is_a_failed_change(self):
        """The server answers 200 with words that are not JSON: the words show and the switch is open again."""
        with chrome() as cdp:
            js = self.open_all(cdp)
            js("(() => { const f = globalThis.fetch; globalThis.fetch = (u, i) => (i && i.method === 'POST' && String(u).includes('ask-new-projects')) ? Promise.resolve(new Response('oops', {status: 200})) : f(u, i); })()")
            js("document.querySelector('[data-new-switch]').click()")
            self.until(js, "!!document.querySelector('#ask-new-all .error')", "the words for an answer that is not JSON")
            self.assertEqual(js("document.querySelector('[data-new-switch]').getAttribute('aria-checked')"), "true", "the switch stays where it was")
            self.assertFalse(js("document.querySelector('[data-new-switch]').disabled"), "the switch is open again")

    def test_a_busy_server_says_to_wait_and_try_again(self):
        self.refused(503, {})
        with chrome() as cdp:
            js = self.open_all(cdp)
            js("document.querySelector('[data-new-switch]').click()")
            self.until(js, "!!document.querySelector('#ask-new-all .error')", "the words")
            self.assertEqual(js("document.querySelector('#ask-new-all .error').textContent"), "Could not save that choice just now. Wait a moment and try again.", "the words for a busy server")

    def test_the_undo_sends_the_step_of_the_change_it_undoes(self):
        real, sent, got = self.svc.change_new, [], []

        def log(body):
            sent.append(dict(body))
            status, out = real(body)
            got.append(out)
            # a server that also hands a step back with the answer to an Undo: the page must not offer an Undo of an Undo
            return (status, dict(out, apply_id="step-after-undo")) if "undo" in body and status == 200 else (status, out)
        self.svc.change_new = log
        self.addCleanup(setattr, self.svc, "change_new", real)
        with chrome() as cdp:
            js = self.open_all(cdp)
            js("document.querySelector('[data-new-switch]').click()")
            self.until(js, "!!document.querySelector('[data-new-undo]')", "the Undo")
            js("document.querySelector('[data-new-undo]').click()")
            self.until(js, "document.querySelector('[data-new-switch]').getAttribute('aria-checked') === 'true' && !document.querySelector('[data-new-switch]').disabled", "put back")
            self.assertFalse(js("!!document.querySelector('[data-new-undo]')"), "the answer to an Undo offers no further Undo")
        self.assertEqual(len(sent), 2, "one change, one Undo")
        step = got[0].get("apply_id")
        self.assertTrue(step, "the real change gave a step")
        self.assertEqual(sent[-1], {"undo": step}, "the Undo names the step the change gave")

    def _not_saved(self, status, body, what):
        self.refused(status, body)
        with chrome() as cdp:
            js = self.open_all(cdp)
            js("document.querySelector('[data-new-switch]').click()")
            self.until(js, "!!document.querySelector('#ask-new-all .error')", what)
            self.assertEqual(js("document.querySelector('[data-new-switch]').getAttribute('aria-checked')"), "true", "the switch stays where it was")
            self.assertFalse(js("!!document.querySelector('[data-new-undo]')"), "no Undo")

    def test_an_answer_whose_value_is_not_true_or_false_is_not_a_saved_change(self):
        self._not_saved(200, {"ok": True, "on": "false", "off_here": False, "apply_id": "x1"}, "the words for a value that is a string")

    def test_an_answer_whose_ok_is_not_true_is_not_a_saved_change(self):
        self._not_saved(200, {"ok": "yes", "on": False, "off_here": False, "apply_id": "x1"}, "the words for an ok that is not true")

    def test_an_answer_that_is_not_a_200_is_not_a_saved_change(self):
        self._not_saved(201, {"ok": True, "on": False, "off_here": False, "apply_id": "x1"}, "the words for a 201")

    def test_the_undo_reads_undo_and_looks_like_a_quiet_link(self):
        real = self.svc.change_new
        self.svc.change_new = lambda body: (lambda r: (r[0], dict(r[1], apply_id="step-1") if r[0] == 200 else r[1]))(real(body))
        self.addCleanup(setattr, self.svc, "change_new", real)
        with chrome() as cdp:
            js = self.open_all(cdp)
            js("document.querySelector('[data-new-switch]').click()")
            self.until(js, "!!document.querySelector('[data-new-undo]')", "the Undo")
            self.assertEqual(js("document.querySelector('[data-new-undo]').innerText"), "Undo", "the Undo's word")
            self.assertTrue(js("document.querySelector('[data-new-undo]').classList.contains('link')"), "the Undo is a link-looking button")
            self.assertTrue(js("document.querySelector('[data-new-undo]').parentElement.classList.contains('muted')"), "the Undo line is quiet")
            self.assertEqual(js("document.querySelector('[data-new-undo]').getAttribute('type')"), "button", "the Undo is a plain button")
            self.assertEqual(js("document.querySelector('#ask-new-all .ask-new-msg').getAttribute('aria-live')"), "polite", "the words are polite")
            self.assertEqual(js("document.querySelector('#ask-new-all .ask-new-msg').getAttribute('role')"), "alert", "the words are an alert")


if __name__ == "__main__":
    unittest.main()
