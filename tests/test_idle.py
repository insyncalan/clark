"""#71: a launcher-started server stops by itself two minutes after the last clark page closes (src/clark/idle.py).

Run: python3 dev/run_tests.py test_idle
The time is a fake clock the test moves, so nothing waits two minutes; one test runs the watcher for real, with the times
shortened the way CLARK_STOP_AFTER and CLARK_STOP_CHECK shorten them.
"""
import threading
import time
import unittest
from unittest import mock

from _paths import SRC  # noqa: F401  (puts src/ on the path)

from clark import idle


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class Due(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.idle = idle.Idle(clock=self.clock, sleep=self.clock.sleep)

    def test_the_defaults_are_two_minutes_looked_at_every_five_seconds(self):
        self.assertEqual((idle.STOP_AFTER, idle.STOP_CHECK, idle.HEARTBEAT), (120.0, 5.0, 10))
        self.assertEqual((self.idle.stop_after, self.idle.check), (120.0, 5.0))

    def test_not_due_until_more_than_two_minutes_have_passed(self):
        self.clock.now += 120.0
        self.assertFalse(self.idle.due())
        self.clock.now += 0.1
        self.assertTrue(self.idle.due())

    def test_a_page_saying_it_is_here_starts_the_minute_again(self):
        self.clock.now += 119
        self.idle.here()
        self.clock.now += 119
        self.assertFalse(self.idle.due())
        self.assertAlmostEqual(self.idle.quiet_for(), 119)

    def test_a_background_tab_that_beats_once_a_minute_keeps_the_server_alive(self):
        # Finding 33: Chrome slows a hidden tab's timers to about one a minute after five minutes. At the old 60 s limit a beat that lands a
        # second late left the server due; at 120 s a once-a-minute beat, even a few seconds late, never does.
        for _ in range(30):
            self.clock.now += 65
            self.assertFalse(self.idle.due(), "a beat 65 s after the last one must not stop the server")
            self.idle.here()
        self.clock.now += 61
        self.assertFalse(self.idle.due())
        self.assertGreater(idle.STOP_AFTER, 65 + 10, "the limit is more than one throttled beat plus its lateness")

    def test_the_start_counts_as_here_because_the_window_is_about_to_open(self):
        self.assertEqual(self.idle.quiet_for(), 0)

    def test_never_while_a_job_runs(self):
        self.clock.now += 3600
        self.assertFalse(self.idle.due(busy=True))
        self.assertTrue(self.idle.due(busy=False))

    def test_it_reads_a_clock_that_a_change_of_the_computers_time_does_not_move(self):
        self.assertIs(idle.Idle().clock, time.monotonic)


class Watch(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.idle = idle.Idle(clock=self.clock, sleep=self.clock.sleep)
        self.said, self.stopped = [], []

    def run_watch(self, busy=lambda: False, rounds=1000):
        left = [rounds]

        def keep_going():
            left[0] -= 1
            return left[0] >= 0
        self.idle.watch(lambda: self.stopped.append(self.clock.now), busy, self.said.append, keep_going)

    def test_it_stops_once_after_a_minute_and_says_so_in_plain_words(self):
        self.run_watch()
        self.assertEqual(len(self.stopped), 1)
        self.assertEqual(self.stopped[0] - 1000.0, 125.0, "the first look after the minute: 5 seconds apart")
        self.assertEqual(self.said, ["No clark window has been open for 120 seconds, so clark is stopping."])

    def test_a_page_that_keeps_saying_it_is_here_keeps_it_running(self):
        def keep_going():
            self.idle.here()
            return self.clock.now < 1000 + 600
        self.idle.watch(lambda: self.stopped.append(1), lambda: False, self.said.append, keep_going)
        self.assertEqual((self.stopped, self.said), ([], []))

    def test_it_waits_for_a_job_and_then_stops(self):
        working = [True]

        def busy():
            if self.clock.now > 1000 + 300:
                working[0] = False
            return working[0]
        self.run_watch(busy)
        self.assertEqual(len(self.stopped), 1)
        self.assertGreater(self.stopped[0], 1000 + 300, "not before the job ended")

    def test_a_server_that_was_not_started_by_the_launcher_is_never_given_a_watcher(self):
        self.assertFalse(idle.launched({}))
        self.assertFalse(idle.launched({"CLARK_LAUNCHED": "0"}))
        self.assertFalse(idle.launched({"CLARK_LAUNCHED": "true"}))
        self.assertTrue(idle.launched({"CLARK_LAUNCHED": "1"}))


class InDocker(unittest.TestCase):
    """Row 1080: the Docker web server never stops by itself, whatever else is set (no window is ever left open in a container)."""

    def setUp(self):
        self.clock = Clock()
        self.said, self.stopped = [], []

    def make(self, in_container):
        return idle.Idle(clock=self.clock, sleep=self.clock.sleep, container=lambda: in_container)

    def watch(self, watcher, rounds=1000):
        left = [rounds]

        def keep_going():
            left[0] -= 1
            return left[0] >= 0
        watcher.watch(lambda: self.stopped.append(self.clock.now), lambda: False, self.said.append, keep_going)

    def test_the_stop_is_refused_in_docker_however_long_it_is_quiet(self):
        watcher = self.make(True)
        self.watch(watcher)                                     # 1000 rounds of 5 seconds, far past the minute
        self.assertGreater(self.clock.now - 1000.0, 3600)
        self.assertFalse(watcher.due())
        self.assertEqual((self.stopped, self.said), ([], []))

    def test_outside_docker_the_stop_is_unchanged(self):
        watcher = self.make(False)
        self.watch(watcher)
        self.assertEqual(len(self.stopped), 1)
        self.assertEqual(self.stopped[0] - 1000.0, 125.0)
        self.assertEqual(self.said, ["No clark window has been open for 120 seconds, so clark is stopping."])

    def test_launched_is_false_in_docker_even_with_the_launcher_mark(self):
        self.assertFalse(idle.launched({"CLARK_LAUNCHED": "1"}, container=lambda: True))
        self.assertTrue(idle.launched({"CLARK_LAUNCHED": "1"}, container=lambda: False))
        self.assertFalse(idle.launched({}, container=lambda: False))

    def test_the_real_container_check_is_the_default(self):
        from clark import platform
        self.assertIs(idle.Idle().container, platform.container_mode)

    def test_the_real_container_check_is_read_when_asked_not_when_the_module_loads(self):
        """A patch of clark.platform.container_mode put in place after idle was imported still reaches both defaults."""
        with mock.patch("clark.platform.container_mode", return_value=True):
            self.assertFalse(idle.launched({"CLARK_LAUNCHED": "1"}))
            watcher = idle.Idle(clock=self.clock, sleep=self.clock.sleep)
            self.clock.now += 3600
            self.assertFalse(watcher.due())
        with mock.patch("clark.platform.container_mode", return_value=False):
            self.assertTrue(idle.launched({"CLARK_LAUNCHED": "1"}))
            self.assertTrue(watcher.due())


class Environment(unittest.TestCase):
    def test_the_times_can_be_shortened_for_a_test(self):
        i = idle.Idle.from_environ({"CLARK_STOP_AFTER": "0.5", "CLARK_STOP_CHECK": "0.05"})
        self.assertEqual((i.stop_after, i.check), (0.5, 0.05))

    def test_a_bad_value_keeps_the_default(self):
        for bad in ("", "soon", "0", "-3", "nan"):
            i = idle.Idle.from_environ({"CLARK_STOP_AFTER": bad, "CLARK_STOP_CHECK": bad})
            expected = (idle.STOP_AFTER, idle.STOP_CHECK) if bad != "nan" else None
            if expected:
                self.assertEqual((i.stop_after, i.check), expected, bad)

    def test_number_refuses_non_finite_values(self):
        default = object()
        for bad in ("inf", "-inf", "nan", "1e999", "0", "-5", "abc", ""):
            self.assertIs(idle.number({"X": bad}, "X", default), default, bad)
        self.assertIs(idle.number({}, "X", default), default, "a missing name")
        self.assertEqual(idle.number({"X": "2.5"}, "X", default), 2.5)
        self.assertEqual(idle.number({"X": "90"}, "X", default), 90.0)
        self.assertEqual(idle.number({"X": "0.1"}, "X", default), 0.1)


class ForReal(unittest.TestCase):
    def test_a_watcher_stops_a_server_after_its_page_goes_and_not_before(self):
        i = idle.Idle(stop_after=0.4, check=0.05)
        stopped = threading.Event()
        threading.Thread(target=i.watch, args=(stopped.set, lambda: False, lambda text: None), daemon=True).start()
        t0 = time.monotonic()
        while time.monotonic() - t0 < 0.8:             # a page is open for 0.8 s
            i.here()
            time.sleep(0.05)
            self.assertFalse(stopped.is_set(), "stopped while a page was open")
        self.assertTrue(stopped.wait(10), "did not stop after the page went")


if __name__ == "__main__":
    unittest.main()
