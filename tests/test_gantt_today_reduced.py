"""The Gantt Today button jumps at once under reduced motion, and a bar drops its grow class when the grow has ended.

Run: python3 dev/run_tests.py test_gantt_today_reduced
Reads the source of the Gantt chart.
"""
import unittest

from _paths import SRC

JSX = (SRC / "clark" / "page" / "src" / "gantt" / "components" / "GanttChart.jsx").read_text(encoding="utf-8")


class Today(unittest.TestCase):
    def test_go_today_asks_reduced(self):
        i = JSX.index("const goToday =")
        block = JSX[i:JSX.index("};", i)]
        self.assertIn('reduced() ? "auto" : "smooth"', block)
        self.assertNotIn('behavior: "smooth"', block)

    def test_grow_class_leaves_the_bar_when_the_grow_ends(self):
        line = next(l for l in JSX.splitlines() if "onAnimationEnd=" in l and "born.current.set" in l)
        self.assertIn('classList.remove("gt-grow")', line)


if __name__ == "__main__":
    unittest.main()
