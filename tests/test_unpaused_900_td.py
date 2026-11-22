"""Row 1509: the 900 px browser cases are un-paused (test_server.PAUSED_900 is None) and nothing still says they are paused.

Run: python3 dev/run_tests.py test_unpaused_900_td
"""
import pathlib
import unittest

import test_server


class Recorder(test_server._Pipe):
    def __init__(self):
        self.sent = []

    def _call_once(self, method, params=None, session=None):
        self.sent.append((method, params))
        return {}


class Unpaused(unittest.TestCase):
    def test_the_900_switch_is_off(self):
        self.assertIsNone(test_server.PAUSED_900)

    def test_a_900_window_is_sent_and_not_skipped(self):
        p = Recorder()
        p.call("Emulation.setDeviceMetricsOverride", {"width": 900, "height": 900, "deviceScaleFactor": 1, "mobile": False})
        self.assertEqual([m for m, _ in p.sent], ["Emulation.setDeviceMetricsOverride"])
        self.assertEqual(p.sent[0][1]["width"], 900)

    def test_no_test_file_still_says_not_proved_at_900_while_paused(self):
        here = pathlib.Path(__file__).resolve().parent
        bad = []
        for f in sorted(here.glob("test_*.py")):
            if f.name == pathlib.Path(__file__).name:
                continue
            for n, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if "Not proved at 900 px while PAUSED_900 is set" in line:
                    bad.append("%s:%d" % (f.name, n))
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
