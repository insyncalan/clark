"""One shared growth check for the tests that guard against a blow-up in time (instead of a wall-clock limit in seconds).

`growth_ratio` times work(n) and work(2n) in CPU time; `assert_growth` fails when the cost climbs faster than linear, or when the
larger run is far slower than any healthy scan (so a slowdown that stays linear is still caught).
"""
import time

GROWTH_LIMIT = 3.5      # t(2n) / t(n): linear is 2, quadratic is 4, cubic is 8. Above 3.5 means the work is growing faster than linear (a square fails; linear measures 1.8 to 2.2).
GROWTH_FLOOR = 0.01     # CPU seconds; a faster t(n) than this is raised to it, so timer noise cannot fail a very quick run
ABSOLUTE_CAP = 30       # CPU seconds for the larger run: a generous bound, so a scan that stays linear but gets a hundred times slower still fails


def growth_ratio(work, n, tries=3):
    """Time work(n) and work(2 * n) in CPU time (time.process_time, so a busy machine does not count against it), best of
    `tries` for each, and return (t(n), t(2n), t(2n) / max(t(n), GROWTH_FLOOR))."""
    def best(size):
        found = None
        for _ in range(tries):
            start = time.process_time()
            work(size)
            spent = time.process_time() - start
            found = spent if found is None else min(found, spent)
        return found
    small, big = best(n), best(2 * n)
    return small, big, big / max(small, GROWTH_FLOOR)


def assert_growth(test, work, n, label, tries=3):
    """Run growth_ratio(work, n, tries), print the figures, and fail `test` if the ratio is above GROWTH_LIMIT or t(2n) is above
    ABSOLUTE_CAP. The failure names `label` and both times."""
    small, big, ratio = growth_ratio(work, n, tries)
    print("%s: t(n)=%.3f t(2n)=%.3f ratio=%.2f" % (label, small, big, ratio))
    test.assertLessEqual(ratio, GROWTH_LIMIT, "%s: t(n)=%.3f t(2n)=%.3f ratio=%.2f" % (label, small, big, ratio))
    test.assertLessEqual(big, ABSOLUTE_CAP, "%s: t(2n)=%.3f CPU seconds is over the absolute cap" % (label, big))
    return small, big, ratio
