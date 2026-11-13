"""#112 H2/H3/M1/M2: the leak scan stays fast on hostile input of the largest size a file may have.

Run: python3 dev/run_tests.py test_publish_scan_time
Each hostile shape is run in its own child process, so a scan that stops being linear FAILS here in seconds (the child is
killed after a hard limit) instead of hanging the whole test run. In the child, outside_addresses, check_brand and
to_client.check_copy each get the same input, up to the 5 MB limit, and must finish well inside the bound.
"""
import os
import subprocess
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor

from _paths import ROOT, SRC  # noqa: F401

# BOUND is a loose hang guard, not a speed test: CPU seconds for one function on 5 MB. Shapes measured on a busy arm64 box took up
# to about 8 s while linear; the escapes shape is the slowest (12.4 s on a quiet Python 3.9 Linux box on main, 14.4 s with the brand-scan
# change of row 815, 3.6 s and 3.9 s on a Mac; 20.7 s for check_brand alone on a busy CI runner), and a quadratic scan takes minutes, so
# 30 s separates them. Linearity itself is checked by the size-growth test below (a ratio measured in the same run), so a slow machine
# does not fail the absolute check.
BOUND = 30.0
HARD = 180           # seconds for the whole child (three functions, each up to BOUND): past this it is killed and the case fails (it was 90 s: a slow
                     # shared runner killed the escapes shape at 90 s with check_brand at 20.7 s and the third function still running)
LIMIT = 5 * 1024 * 1024

# name -> a python expression for the hostile text, `n` being how many characters it should be
SHAPES = {
    "open script tags": '"<script " * (n // 8)',
    "open meta tags": '"<meta " * (n // 6)',
    "meta http-equiv": '"<meta http-equiv=" * (n // 17)',
    "open link tags": '"<link " * (n // 6)',
    "open a tags": '"<a " * (n // 3)',
    "open quotes": '\'<a b="\' * (n // 6)',
    "entities": '\'<img src="\' + "&#47;" * (n // 5) + \'x">\'',
    "comment openers in style": '"<style>" + "/*" * (n // 2) + "</style>"',
    "url openers": '"<style>" + "url(" * (n // 4) + "</style>"',
    "data url openers": '"<style>" + "url(data:" * (n // 9) + "</style>"',
    "data url openers, no style": '"url(data:" * (n // 9)',
    "escapes": '"<style>" + "\\\\\\\\" * (n // 2) + "</style>"',
    "hex escapes": '"<style>" + "\\\\75 " * (n // 4) + "</style>"',
    "srcset commas": '\'<img srcset="\' + "," * n + \'">\'',
    "srcset words": '\'<img srcset="\' + "a " * (n // 2) + \'">\'',
    "style attrs": '\'<a style="\' * (n // 10)',
    "ampersands": '\'<a href="\' + "&" * n + \'">\'',
    "image-set": '"<style>" + "image-set(" * (n // 10) + "</style>"',
    "endless end tag lookalikes": '"<style></style " * (n // 15)',
    "style starts": '"<style>" * (n // 7)',
    "svg starts": '"<svg " * (n // 5)',
    "cdata starts": '"<![CDATA[" * (n // 9)',
    "comment titles": '\'<!-- <a title=" -->\' * (n // 19)',
    "textarea titles": '\'<textarea><a title="</textarea>\' * (n // 32)',
    "equals attributes": '\'<a ="x" href=\' * (n // 15)',
    "quote then tags": '\'<a b="\' + "<a c=x " * (n // 7)',
    "quote then bare tag starts": '\'<a b="\' + "<a" * ((n - 16) // 2) + \'">\'',
    "quote then script starts": '\'<a b="\' + "<script" * ((n - 16) // 7) + \'">\'',
    "single quote then tag starts": '"<a b=\'" + "<a" * ((n - 16) // 2) + "\'>"',
    "quote then lone angle brackets then tail": '\'<a b="\' + "<" * (n // 2) + \'">\' + "x" * (n // 2)',
    "only angle brackets then tail": '"<" * (n // 2) + "x" * (n // 2)',
    "src spaces": '"src" + " " * n',
    "src equals": '"src= " * (n // 5)',
    "href quotes": '"href=\\"" * (n // 6)',
    "long link tag": '"<link " + "x" * n',
}

CHILD = r"""
import sys, time
sys.path[:0] = [{src!r}]
from clark import publish, to_client
publish.SCAN_BUDGET = 10 ** 12          # no budget here: this measures that the scan itself is linear (test_publish_scan_budget tests the budget)
n = {n}
text = {expr}
text = text[:{limit}]
data = text.encode("utf-8")
for name, call in (("outside_addresses", lambda: publish.outside_addresses(text)),
                   ("check_brand", lambda: publish.check_brand(text)),
                   ("check_copy", lambda: to_client.check_copy(data, markers=()))):
    began = time.process_time()
    try:
        call()
    except publish.PublishError:
        pass
    print(name, "%.3f" % (time.process_time() - began), flush=True)
"""


def workers(cpus):
    """How many children run at once: at most eight, and at most half the cores, so a small or loaded runner is not starved."""
    return min(8, max(1, (cpus or 1) // 2))


def child_limit(cpus):
    """Wall-clock seconds one child may take: HARD for each child that shares the machine with it. The CPU-time BOUND is unchanged;
    this only keeps the hang guard from killing a slow-but-linear child when several run side by side."""
    return HARD * workers(cpus)


def run_shape(expr, n):
    code = CHILD.format(src=str(SRC), n=n, expr=expr, limit=LIMIT)
    hard = child_limit(os.cpu_count())
    try:
        done = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=hard)
    except subprocess.TimeoutExpired as e:
        return None, (e.stdout or "")
    return done.stdout.split("\n"), done.stderr


def run_all(shapes):
    """{key: run_shape(expr, n)} for every (key, expr, n) in `shapes`, the children running side by side (they are separate
    processes, so threads waiting on them are enough). Each child's own limits are unchanged. Eight at a time at most, so a
    small runner is not starved, and the CPU seconds each child measures for itself stay the same."""
    shapes = list(shapes)
    with ThreadPoolExecutor(max_workers=workers(os.cpu_count())) as pool:
        return dict(zip((k for k, _, _ in shapes), pool.map(lambda t: run_shape(t[1], t[2]), shapes)))


class Parallelism(unittest.TestCase):
    def test_wall_clock_limit_scales_with_the_parallelism(self):
        for cpus in (1, 2, 4, 16):
            with self.subTest(cpus=cpus):
                self.assertGreaterEqual(child_limit(cpus), HARD * workers(cpus))
                self.assertGreaterEqual(child_limit(cpus), HARD)
        self.assertEqual(workers(16), 8)
        self.assertEqual(child_limit(16), HARD * 8)
        self.assertEqual(child_limit(2), HARD)

    def test_a_small_runner_is_not_oversubscribed(self):
        self.assertEqual(workers(None), 1)
        for cpus in (1, 2, 3, 4, 8, 16):
            with self.subTest(cpus=cpus):
                self.assertLessEqual(workers(cpus), max(1, cpus // 2))
                self.assertLessEqual(workers(cpus), 8)


class Fast(unittest.TestCase):
    def test_each_hostile_shape_finishes_quickly_on_every_function(self):
        done = run_all((name, expr, LIMIT) for name, expr in SHAPES.items())
        for name in SHAPES:
            with self.subTest(name):
                lines, err = done[name]
                self.assertIsNotNone(lines, f"{name}: still running after {HARD} s (partial output: {err!r})")
                times = {l.split()[0]: float(l.split()[1]) for l in lines if l.strip()}
                self.assertEqual(sorted(times), ["check_brand", "check_copy", "outside_addresses"], f"{name}: {err}")
                for fn, took in times.items():
                    self.assertLess(took, BOUND, f"{name}: {fn} took {took} s on {LIMIT} bytes")

    def test_a_quadratic_scan_would_fail_at_three_sizes(self):
        # the url( scan, at 3 sizes of url(data: openers: doubling the input must not much more than double the time
        sizes = (500_000, 1_000_000, 2_000_000)
        done = run_all((n, '"url(data:" * (n // 9)', n) for n in sizes)
        times = []
        for n in sizes:
            lines, err = done[n]
            self.assertIsNotNone(lines, "url(data: openers still running")
            times.append(max(float(l.split()[1]) for l in lines if l.strip() and l.split()[0] != "check_copy_unused"))
        self.assertLess(times[2], max(0.3, times[0] * 12), f"time grows faster than the size: {times}")


if __name__ == "__main__":
    unittest.main()
