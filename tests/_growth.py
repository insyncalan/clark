"""One shared growth check for the tests that guard against a blow-up in time (instead of a wall-clock limit in seconds).

`growth_ratio` times work(n) and work(4n) in CPU time; `assert_growth` fails when the cost climbs faster than linear, or when the
larger run is far slower than any healthy scan (so a slowdown that stays linear is still caught).

Why 4n and not 2n: a step of 2 puts linear at 2 and quadratic at 4, so the limit has to sit between them (3.5) and a milder-than-square cost
(a mutation measured 3.70) is only just over it. A step of 4 puts linear at 4 and quadratic at 16, so a limit of 8 is a factor of two from
each (a cost of n to the power 1.5 gives 8, and the limit fails anything above it).
"""
import time

GROWTH_STEP = 4         # the larger run is GROWTH_STEP times the size of the smaller one
GROWTH_LIMIT = 8        # t(4n) / t(n): linear is 4, n to the power 1.5 is 8, quadratic is 16, cubic is 64. Above 8 means the work is growing faster than n to the power 1.5; a square is a factor of two over it and linear a factor of two under.
GROWTH_FLOOR = 0.01     # CPU seconds; a faster t(n) than this is raised to it, so timer noise cannot fail a very quick run
ABSOLUTE_CAP = 30       # CPU seconds for the larger run: a generous bound, so a scan that stays linear but gets a hundred times slower still fails


def growth_ratio(work, n, tries=3):
    """Time work(n) and work(GROWTH_STEP * n), that is 4n, in CPU time (time.process_time, so a busy machine does not count against it),
    best of `tries` for each, and return (t(n), t(4n), t(4n) / max(t(n), GROWTH_FLOOR))."""
    def best(size):
        found = None
        for _ in range(tries):
            start = time.process_time()
            work(size)
            spent = time.process_time() - start
            found = spent if found is None else min(found, spent)
        return found
    small, big = best(n), best(GROWTH_STEP * n)
    return small, big, big / max(small, GROWTH_FLOOR)


def assert_growth(test, work, n, label, tries=3):
    """Run growth_ratio(work, n, tries), print the figures, and fail `test` if the ratio is above GROWTH_LIMIT or t(4n) is above
    ABSOLUTE_CAP. The failure names `label` and both times."""
    small, big, ratio = growth_ratio(work, n, tries)
    print("%s: t(n)=%.3f t(4n)=%.3f ratio=%.2f" % (label, small, big, ratio))
    test.assertLessEqual(ratio, GROWTH_LIMIT, "%s: t(n)=%.3f t(4n)=%.3f ratio=%.2f" % (label, small, big, ratio))
    test.assertLessEqual(big, ABSOLUTE_CAP, "%s: t(4n)=%.3f CPU seconds is over the absolute cap" % (label, big))
    return small, big, ratio
