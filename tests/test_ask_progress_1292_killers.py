"""Row 1292 (S6) sweep killers: the working line is drawn with its style class and the clock restarts on each send."""
import unittest

from _paths import ROOT

EDIT = ROOT / "src" / "clark" / "page" / "src" / "edit"
PANEL = (EDIT / "AskPanel.jsx").read_text(encoding="utf-8")


class WorkingLineSweep(unittest.TestCase):
    def test_the_step_span_carries_the_class_the_one_row_rule_styles(self):
        self.assertIn('<span class="ask-quip ask-step" id="ask-step" aria-hidden="true">', PANEL)

    def test_the_clock_effect_runs_again_on_each_change_of_busy_not_only_on_mount(self):
        self.assertIn("return () => clearInterval(c);\n    }", PANEL)
        self.assertIn("return () => clearTimeout(t);\n  }, [busy]);", PANEL)


if __name__ == "__main__":
    unittest.main()
