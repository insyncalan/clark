"""#353 (#130 point 4, after #120): the Publish box shows a spinner while the request is open, then a tick and "Published
(Publication N)", N being the number the server answers with, and the line saying where it was saved. A cancel or a failure shows no
tick. Under reduced motion the ring does not turn; the tick and the words are the same.

Run: python3 dev/run_tests.py test_publish_progress
The system's Save window is replaced by one that waits on an event, so the request stays open for as long as the test wants.
Chrome is required: the browser tests fail, never skip, without it. The route's answer needs no browser.
"""
import shutil
import threading
import unittest

from test_publish_dialog import Base
from test_server import chrome

SPIN = "document.querySelector('#pub-go #pub-spin')"    # #353: the spinner and the tick are on the Publish button itself
DONE = "document.querySelector('#pub-done')"
TICK = "document.querySelector('#pub-go [data-tick] svg')"
BTN = "document.querySelector('#pub-go').innerText.trim()"


class Progress(Base):
    def slow(self):
        """The Save window does not answer until the test sets the event."""
        gate = threading.Event()
        answer = self.rig.publisher.choose_save_file

        def wait_then_answer(prompt, default, start=None):
            gate.wait(20)
            return answer(prompt, default, start=start)

        self.rig.publisher.choose_save_file = wait_then_answer
        self.addCleanup(gate.set)
        return gate

    def reduced(self, cdp, p, value):
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": value}]}, p.sid)
        if value == "no-preference":
            # a Mac that reduces motion paints data-motion="reduce" at load, before this pin; clear it so the pin is what counts
            p.js("delete document.documentElement.dataset.motion")

    def test_the_route_answers_with_the_publication_number(self):
        status, body = self.rig.call("POST", "/api/publish", {"project": "PUB", "to_client": False})
        self.assertEqual((status, body["publication"]), (200, self.rig.rows()[-1]["number"]))
        status, body = self.rig.call("POST", "/api/publish", {"project": "PUB", "to_client": True})
        self.assertEqual((status, body["publication"]), (200, self.rig.rows()[-1]["number"]), "a copy to the client says it too")
        self.assertEqual([r["number"] for r in self.rig.rows()], [1, 2])

    def test_C_a_spinner_while_it_works_then_a_tick_and_the_number(self):
        gate = self.slow()
        with chrome() as cdp:
            p = self.page(cdp)
            p.open_publish()
            p.go()
            p.until(f"!!{SPIN}", "the spinner shows while the request is open")
            self.assertIn("Publishing…", p.message())
            self.assertIsNone(p.js(DONE), "no tick yet")
            self.assertEqual(self.rig.rows(), [], "nothing is recorded yet")
            gate.set()
            p.until(f"!!{DONE}", "the number shows when it is done")
            self.assertIsNone(p.js(SPIN), "the spinner is gone")
            number = self.rig.rows()[-1]["number"]
            self.assertEqual(p.js(f"{DONE}.innerText.trim()"), f"Published (Publication {number})")
            self.assertTrue(p.js(f"!!{TICK}"), "the tick is on the button")
            self.assertEqual(p.js(BTN), f"Published (Publication {number})", "and the button says it")
            self.assertRegex(p.message(), rf"^Published \(Publication {number}\)\. Saved locally as ", "the where-saved line follows")

    def test_C_a_second_publish_has_the_next_number(self):
        with chrome() as cdp:
            p = self.page(cdp)
            said = []
            for _ in range(2):
                p.open_publish()
                p.go()
                p.until(f"!!{DONE}", "done")
                said.append(p.js(f"{DONE}.innerText.trim()"))
                self.assertEqual(p.js(BTN), f"Published (Publication {len(said)})")
                p.js("document.querySelector('[data-go]').click()")
                p.until("!document.querySelector('#publish-dialog')", "closed")
            self.assertEqual(said, ["Published (Publication 1)", "Published (Publication 2)"])
            self.assertEqual([r["number"] for r in self.rig.rows()], [1, 2])

    def test_C_a_failure_has_no_tick(self):
        shutil.rmtree(self.rig.client)
        with chrome() as cdp:
            p = self.page(cdp)
            p.open_publish()
            p.js("document.querySelector('#pub-client').click()")
            p.go()
            p.until("document.querySelector('#pub-msg').getAttribute('role') === 'alert' && /Nothing was published/.test(document.querySelector('#pub-msg').innerText)", "the problem")
            self.assertIsNone(p.js(DONE), "no number on a failure")
            self.assertIsNone(p.js(TICK), "no tick on a failure")
            self.assertIsNone(p.js(SPIN), "no spinner left")
            self.assertNotIn("Published (Publication", p.dialog_text())

    def test_C_a_slow_cancel_shows_the_spinner_then_no_tick(self):
        self.rig.save_to = None
        gate = self.slow()
        with chrome() as cdp:
            p = self.page(cdp)
            p.open_publish()
            p.go()
            p.until(f"!!{SPIN}", "the spinner shows")
            gate.set()
            p.until("/Cancelled/.test(document.querySelector('#pub-msg').innerText)", "it says it was cancelled")
            self.assertIsNone(p.js(DONE), "no number")
            self.assertIsNone(p.js(TICK), "no tick")
            self.assertIsNone(p.js(SPIN), "no spinner")

    def test_C_reduced_motion_the_ring_is_still_and_the_tick_and_words_stay(self):
        gate = self.slow()
        with chrome() as cdp:
            p = self.page(cdp)
            self.reduced(cdp, p, "no-preference")
            p.open_publish()
            p.go()
            p.until(f"!!{SPIN}", "the spinner shows")
            p.until(f"getComputedStyle({SPIN}).animationName !== 'none'", "it turns when motion is allowed")
            self.reduced(cdp, p, "reduce")
            p.until(f"getComputedStyle({SPIN}).animationName === 'none'", "with reduced motion the ring does not turn")
            self.assertGreater(p.js(f"{SPIN}.getBoundingClientRect().width"), 0, "but it is still shown")
            self.assertIn("Publishing…", p.message())
            gate.set()
            p.until(f"!!{DONE}", "the tick and the words still appear")
            number = self.rig.rows()[-1]["number"]
            self.assertEqual(p.js(f"{DONE}.innerText.trim()"), f"Published (Publication {number})")
            self.assertTrue(p.js(f"!!{TICK}"), "the tick is there")
            self.assertEqual(p.js(f"getComputedStyle({TICK}).animationName"), "none")



class Widths(Progress):
    """The same spinner-then-tick at 1400 and 900 px wide (desktop only). Written, not run on the load-braked machine."""

    def test_C_spinner_then_tick_at_1400_and_900(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                gate = self.slow()
                with chrome() as cdp:
                    p = self.page(cdp)
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                    p.open_publish()
                    p.go()
                    p.until(f"!!{SPIN}", "the spinner shows")
                    gate.set()
                    p.until(f"!!{DONE}", "the number shows")
                    self.assertTrue(p.js(f"!!{TICK}"))
                    self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"), "no sideways scroll")


if __name__ == "__main__":
    unittest.main()
