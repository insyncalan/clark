"""Mutation-kill tests for src/clark/idle.py: cases the existing tests let a hand-made mutant through, and hostile environment text.
Run from tests/: python3 -m unittest test_idle_mutants"""
import unittest

from _paths import SRC  # noqa: F401

from clark import idle


def rounds(n):
    left = [n]

    def keep_going():
        left[0] -= 1
        return left[0] >= 0
    return keep_going


def clock_and_sleep(start=0.0):
    now = [start]
    slept = []

    def sleep(s):
        slept.append(s)
        now[0] += s
    return now, slept, (lambda: now[0]), sleep


class Say(unittest.TestCase):
    def test_the_stop_line_cuts_the_seconds_and_never_rounds_them_up(self):
        """int(90.7) is 90; a round() would say 91."""
        now, _, clock, sleep = clock_and_sleep()
        said, stopped = [], []
        watcher = idle.Idle(stop_after=90.7, check=100, clock=clock, sleep=sleep, container=lambda: False)
        watcher.watch(lambda: stopped.append(1), lambda: False, said.append, rounds(50))
        self.assertEqual(said, ["No clark window has been open for 90 seconds, so clark is stopping."])
        self.assertEqual(stopped, [1])

    def test_the_stop_line_for_a_short_wait_says_zero_not_one(self):
        now, _, clock, sleep = clock_and_sleep()
        said = []
        watcher = idle.Idle(stop_after=0.6, check=1, clock=clock, sleep=sleep, container=lambda: False)
        watcher.watch(lambda: None, lambda: False, said.append, rounds(50))
        self.assertEqual(said, ["No clark window has been open for 0 seconds, so clark is stopping."])


class Hostile(unittest.TestCase):
    """The two timing variables are text from the environment; none of it may give a zero, negative or non-finite wait."""

    def test_text_that_is_not_a_positive_finite_number_gives_the_default(self):
        default = object()
        for bad in ("   ", "\t", "1,5", "0x10", "ten", "--5", "+-5", "-0", "0.0", "-0.0", "-1e-9", "Infinity", "-Infinity", "NaN",
                    "1e400", "\x00", "5\x00", "5 seconds", "​5", "'5'", "None"):
            self.assertIs(idle.number({"X": bad}, "X", default), default, repr(bad))

    def test_a_number_with_spaces_or_a_plus_or_an_exponent_is_taken_as_written(self):
        self.assertEqual(idle.number({"X": " 5 "}, "X", None), 5.0)
        self.assertEqual(idle.number({"X": "+5"}, "X", None), 5.0)
        self.assertEqual(idle.number({"X": "1e2"}, "X", None), 100.0)
        self.assertEqual(idle.number({"X": "1e-3"}, "X", None), 0.001)

    def test_a_tiny_positive_number_is_still_positive(self):
        self.assertEqual(idle.number({"X": "1e-300"}, "X", None), 1e-300)

    def test_a_missing_name_gives_the_default_unchanged_whatever_its_type(self):
        for default in (None, 0, 60.0, "x"):
            self.assertIs(idle.number({}, "X", default), default)

    def test_from_environ_reads_each_name_into_its_own_field(self):
        i = idle.Idle.from_environ({"CLARK_STOP_AFTER": "7", "CLARK_STOP_CHECK": "3"})
        self.assertEqual((i.stop_after, i.check), (7.0, 3.0))
        j = idle.Idle.from_environ({"CLARK_STOP_AFTER": "inf", "CLARK_STOP_CHECK": "-1"})
        self.assertEqual((j.stop_after, j.check), (idle.STOP_AFTER, idle.STOP_CHECK))

    def test_the_launcher_mark_is_exactly_the_one_character_1(self):
        for bad in ("", " 1", "1 ", "01", "1\n", "yes", "True", "１", None):
            self.assertFalse(idle.launched({"CLARK_LAUNCHED": bad}, container=lambda: False), repr(bad))
        self.assertTrue(idle.launched({"CLARK_LAUNCHED": "1"}, container=lambda: False))


class Edges(unittest.TestCase):
    def test_due_exactly_at_the_limit_is_not_yet_and_busy_beats_a_long_quiet(self):
        now, _, clock, _ = clock_and_sleep()
        i = idle.Idle(stop_after=10, clock=clock, container=lambda: False)
        now[0] = 10
        self.assertFalse(i.due())
        now[0] = 10.000001
        self.assertTrue(i.due())
        self.assertFalse(i.due(busy=True))
        self.assertFalse(idle.Idle(stop_after=10, clock=lambda: 0, container=lambda: True).due())

    def test_here_moves_last_to_the_clock(self):
        now, _, clock, _ = clock_and_sleep(5.0)
        i = idle.Idle(clock=clock)
        now[0] = 50.0
        self.assertEqual(i.quiet_for(), 45.0)
        i.here()
        self.assertEqual(i.last, 50.0)
        self.assertEqual(i.quiet_for(), 0.0)

    def test_watch_looks_every_check_seconds_and_stops_once(self):
        now, slept, clock, sleep = clock_and_sleep()
        stopped = []
        i = idle.Idle(stop_after=10, check=4, clock=clock, sleep=sleep, container=lambda: False)
        i.watch(lambda: stopped.append(now[0]), lambda: False, lambda t: None, rounds(50))
        self.assertEqual(slept, [4, 4, 4])
        self.assertEqual(stopped, [12.0])


if __name__ == "__main__":
    unittest.main()
