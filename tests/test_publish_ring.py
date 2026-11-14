"""Item 614 (after #380): the Publish ring keeps turning for as long as "Publishing…" shows, and stops the moment the work ends.

Run: python3 dev/run_tests.py test_publish_ring
#380 gave the ring four turns (about 3.6 s), so on a slow publish it stood still beside "Publishing…" and read as finished. Here
the publish reply is held in the page (the way test_motion and test_publish_dialog hold it) past that old stop time: the ring must
still be running, and its clock must still be moving. When the reply is let go the ring is gone, so nothing turns after the
publish. With reduced motion (the computer's setting, or clark's own <html data-motion="reduce">) the ring is there and still.
Chrome is required: these tests fail, never skip, without it.
"""
import time
import unittest

import test_publish_dialog as tpd
from test_server import chrome

OLD_STOP = 3.6          # seconds: #380's four turns of 900 ms
ALLOW = [{"name": "prefers-reduced-motion", "value": "no-preference"}]
REDUCE = [{"name": "prefers-reduced-motion", "value": "reduce"}]
HOLD = """(function(){ var f = window.fetch.bind(window); window.__release = null;
  window.fetch = function(u, o){ if (String(u).indexOf('/api/publish') === 0 && o && o.method === 'POST') {
    return new Promise(function(res){ window.__release = function(){ res(f(u, o)); }; }); } return f(u, o); }; })()"""
RING = "(function(){ var e = document.querySelector('#pub-go .spin'); if (!e) return null; var a = e.getAnimations();" \
       " return [getComputedStyle(e).animationName, a.length, a.length ? a[0].playState : '', a.length ? a[0].currentTime : 0, e.offsetWidth]; })()"


class Ring(tpd.Base):
    def held(self, cdp, features, own=False):
        p = self.page(cdp, motion="no-preference" if features == ALLOW else None)      # before the load: a Mac that reduces motion paints data-motion=reduce at load
        cdp.call("Emulation.setEmulatedMedia", {"features": features}, p.sid)
        if own:
            p.js("document.documentElement.dataset.motion = 'reduce'")
        p.js(HOLD)
        p.open_publish()
        p.go()
        p.until("!!document.querySelector('#pub-go .spin')", "the ring shows while the publish is open")
        return p

    def finish(self, p):
        p.js("window.__release()")
        p.until("document.querySelector('[data-go]').classList.contains('ok')", "published")
        self.assertIsNone(p.js(RING), "the ring is gone the moment the work ends")
        self.assertEqual(p.js("document.getAnimations().filter(function(a){ return a.animationName === 'pub-spin'; }).length"), 0,
                         "and nothing is left turning after the publish")

    def test_C_the_ring_still_turns_after_the_old_stop_time_while_publishing(self):
        with chrome() as cdp:
            p = self.held(cdp, ALLOW)
            start = time.monotonic()
            self.assertEqual(p.message().strip(), "Publishing…")
            time.sleep(max(0.0, OLD_STOP + 0.8 - (time.monotonic() - start)))
            first = p.js(RING)
            self.assertEqual(first[:3], ["pub-spin", 1, "running"], "past #380's 3.6 s the ring is still running")
            self.assertGreater(first[3], OLD_STOP * 1000, "its clock is past the old stop time")
            time.sleep(0.4)
            second = p.js(RING)
            self.assertEqual(second[2], "running")
            self.assertGreater(second[3], first[3], "and it is still moving, not resting")
            self.assertEqual(p.message().strip(), "Publishing…", "the words still say the work is going on")
            self.finish(p)

    def test_C_reduced_motion_shows_a_still_ring_for_the_whole_publish(self):
        for name, features, own in (("media", REDUCE, False), ("setting", ALLOW, True)):
            with self.subTest(mode=name), chrome() as cdp:
                p = self.held(cdp, features, own)
                time.sleep(0.5)
                ring = p.js(RING)
                self.assertEqual(ring[:2], ["none", 0], "no spin with reduced motion")
                self.assertGreater(ring[4], 0, "a still ring is there beside the words")
                self.assertEqual(p.message().strip(), "Publishing…")
                self.finish(p)


if __name__ == "__main__":
    unittest.main()
