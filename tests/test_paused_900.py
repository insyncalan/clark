"""The 900 px browser cases are paused in ONE place (test_server.PAUSED_900, read by _Pipe.call): 900 is skipped with the stated reason, other widths pass through,
and switching the constant off lets 900 through again.

Run: python3 dev/run_tests.py test_paused_900
"""
import unittest
from unittest import mock

import test_server


class Recorder(test_server._Pipe):
    def __init__(self):
        self.sent = []

    def _call_once(self, method, params=None, session=None):
        self.sent.append((method, params))
        return {}


class Paused(unittest.TestCase):
    def test_the_reason_is_the_stated_words(self):
        self.assertEqual(test_server.PAUSED_900, "paused until Bifrost online (21-11)")

    def test_a_width_of_900_is_skipped_with_the_reason_and_never_sent(self):
        p = Recorder()
        with self.assertRaises(unittest.SkipTest) as caught:
            p.call("Emulation.setDeviceMetricsOverride", {"width": 900, "height": 900, "deviceScaleFactor": 1, "mobile": False})
        self.assertEqual(str(caught.exception), "paused until Bifrost online (21-11)")
        self.assertEqual(p.sent, [])

    def test_other_widths_and_other_calls_go_through(self):
        p = Recorder()
        p.call("Emulation.setDeviceMetricsOverride", {"width": 1400, "height": 900, "deviceScaleFactor": 1, "mobile": False})
        p.call("Emulation.setDeviceMetricsOverride", {"width": 360, "height": 900, "deviceScaleFactor": 1, "mobile": False})
        p.call("Page.navigate", {"url": "about:blank", "width": 900})
        self.assertEqual(len(p.sent), 3)

    def test_the_height_alone_being_900_is_not_paused(self):
        p = Recorder()
        p.call("Emulation.setDeviceMetricsOverride", {"width": 1400, "height": 900})
        self.assertEqual(len(p.sent), 1)

    def test_the_two_watching_pipes_pause_900_too(self):
        import test_back_forward, test_publish
        for mod in (test_back_forward, test_publish):
            p = mod.Watching.__new__(mod.Watching)
            with self.assertRaises(unittest.SkipTest):
                p.call("Emulation.setDeviceMetricsOverride", {"width": 900, "height": 900})

    def test_switched_off_a_width_of_900_runs_again(self):
        p = Recorder()
        with mock.patch.object(test_server, "PAUSED_900", None):
            p.call("Emulation.setDeviceMetricsOverride", {"width": 900, "height": 900})
        self.assertEqual(len(p.sent), 1)


if __name__ == "__main__":
    unittest.main()
