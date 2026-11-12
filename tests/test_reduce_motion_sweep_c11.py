"""Sweep c11: the timeline buttons, the contents card, the legend popover, the marker and the two tab underlines respect reduced motion.

Run: python3 dev/run_tests.py test_reduce_motion_sweep_c11
Reads the sources: the reduce rules must not depend on the window width, and the scrolls must ask reduced().
"""
import re
import unittest

from _paths import SRC

PAGE = SRC / "clark" / "page"
CSS = (PAGE / "shell.css").read_text(encoding="utf-8")
JSX = (PAGE / "src" / "components" / "MsTimeline.jsx").read_text(encoding="utf-8")


def reduce_text():
    """Everything inside the plain (no width condition) reduce media blocks, comments removed."""
    css = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)
    out = []
    for m in re.finditer(r"@media \(prefers-reduced-motion: reduce\) \{", css):
        depth, i = 1, m.end()
        while depth:
            depth += {"{": 1, "}": -1}.get(css[i], 0)
            i += 1
        out.append(css[m.end():i - 1])
    return "\n".join(out)


def stilled(selector):
    for m in re.finditer(r"([^{}]+)\{([^}]*)\}", reduce_text()):
        if "transition: none" in m.group(2) and selector in [s.strip() for s in m.group(1).split(",")]:
            return True
    return False


class Css(unittest.TestCase):
    def test_each_selector_is_still_under_reduce_at_any_width(self):
        for sel in (".toc-card", ".toc.open .toc-card", ".toc-lines", ".toc-lines i", ".toc-lines:hover", ".toc.open .toc-lines",
                    ".mlg-p", ".mv-mk", ".hp-tabs button", ".hp-tabs button::after", ".tab", ".tab::after"):
            self.assertTrue(stilled(sel), sel)

    def test_the_old_narrow_only_reduce_rule_is_gone(self):
        self.assertNotIn("(max-width: 900px) and (prefers-reduced-motion: reduce)", CSS)

    def test_popover_and_marker_do_not_move_under_reduce(self):
        self.assertRegex(reduce_text(), r"\.mlg-p[^{}]*\{[^}]*transform: none")
        self.assertRegex(reduce_text(), r"\.mv-mk:hover[^{}]*\{[^}]*transform: none")


class Scroll(unittest.TestCase):
    def test_imports_reduced(self):
        self.assertRegex(JSX, r'import \{[^}]*\breduced\b[^}]*\} from "\.\./stores/motion\.js"')

    def test_step_asks_reduced(self):
        line = next(l for l in JSX.splitlines() if "const step =" in l)
        self.assertIn('reduced() ? "auto" : "smooth"', line)

    def test_to_today_asks_reduced(self):
        line = next(l for l in JSX.splitlines() if "const toToday =" in l)
        self.assertIn('reduced() ? "auto" : (smooth ? "smooth" : "auto")', line)


if __name__ == "__main__":
    unittest.main()
