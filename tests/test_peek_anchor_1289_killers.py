"""Row 1289 killers: static node-free checks on shell.css and Peek.jsx for the mutants in ~/ag/p1-1289-mutants.md that test_peek_anchor_1289 does not reach.
Run: python3 dev/run_tests.py test_peek_anchor_1289_killers
"""
import re
import unittest

from _paths import ROOT

CSS = (ROOT / "src" / "clark" / "page" / "shell.css").read_text(encoding="utf-8")
JSX = (ROOT / "src" / "clark" / "page" / "src" / "components" / "Peek.jsx").read_text(encoding="utf-8")


def line(prefix):
    hits = [l for l in CSS.splitlines() if l.lstrip().startswith(prefix)]
    assert len(hits) == 1, (prefix, len(hits))
    return hits[0]


class Frame(unittest.TestCase):
    def test_base_rule_exact_edges_and_layer(self):
        body = line(".peek { position: fixed;")
        for want in ("top: var(--topbar);", "right: 0;", "bottom: 0;", "z-index: 30;", "max-width: 100vw;"):
            self.assertIn(want, body)
        self.assertNotRegex(body, r"calc\(")

    def test_no_peek_rule_has_a_card_gap_or_radius(self):
        for l in CSS.splitlines():
            if re.match(r"\.peek[\s.:{,]", l) and "pk-" not in l.split("{")[0]:
                self.assertNotRegex(l, r"border-radius|top:\s*calc|right:\s*\d*[1-9]\d*px|bottom:\s*\d*[1-9]\d*px|width:\s*calc\(100% - 32px\)")

    def test_wide_is_full_width_for_every_peek(self):
        self.assertIn(".peek.wide { width: 100%; }", CSS)
        self.assertNotIn(".peek.wide:not(.hpk)", CSS)

    def test_the_old_card_rules_are_gone(self):
        self.assertNotIn("box-shadow: 0 10px 40px", CSS)
        self.assertNotRegex(CSS, r"\.peek:not\(\.hpk\) \{ top:")


class Narrow(unittest.TestCase):
    def test_below_1000_full_width_important_and_edge_hidden(self):
        l = line("@media (max-width: 999px) { .peek:not(.hpk)")
        self.assertIn("{ width: 100% !important; }", l)
        self.assertRegex(l, r"\.peek:not\(\.hpk\) \.pk-edge \{ display: none; \}")
        self.assertNotIn("32px", l)


class Motion(unittest.TestCase):
    def test_entry_is_inside_the_motion_ok_block_not_the_reduced_one(self):
        start = CSS.index("@media (prefers-reduced-motion: no-preference) {\n")
        pos = CSS.index(".peek:not(.leaving) { animation: pk-in")
        end = CSS.index("\n}\n", start)
        self.assertTrue(start < pos < end)
        self.assertNotIn("m-slide var(--dur-state)", line(".peek:not(.leaving) { animation: pk-in"))

    def test_exit_keyframe_and_class_unchanged(self):
        self.assertIn(".peek.leaving { pointer-events: none; animation: pk-out var(--dur-instant) var(--ease-exit) forwards; }", CSS)
        self.assertIn("@keyframes pk-out { to { transform: translateX(104%); } }", CSS)

    def test_reduced_motion_exit_hidden_and_entry_fade_use_enter_ease(self):
        l = line("@media (prefers-reduced-motion: reduce) { .peek.leaving")
        self.assertIn(".peek.leaving { display: none; }", l)
        self.assertIn("animation: pk-fade var(--dur-instant) var(--ease-enter) 1;", l)
        self.assertIn("@keyframes pk-fade { from { opacity: 0; } }", CSS)
        self.assertNotIn("transform", line("@keyframes pk-fade"))

    def test_keyframe_is_from_only_to_rest(self):
        self.assertEqual(line("@keyframes pk-in"), "@keyframes pk-in { from { transform: translateX(100%); } }")

    def test_tokens_exact(self):
        self.assertEqual(len(re.findall(r"--peek-dur:", CSS)), 1)
        self.assertEqual(len(re.findall(r"--peek-ease:", CSS)), 1)
        self.assertIn("--peek-dur: 500ms;", CSS)
        self.assertIn("--peek-ease: cubic-bezier(.22, 1, .36, 1);", CSS)


class Drag(unittest.TestCase):
    def test_pointer_move_width_is_viewport_minus_pointer_with_no_gap(self):
        self.assertIn("setWidth(document.documentElement.clientWidth - e.clientX)", JSX)
        self.assertNotRegex(JSX, r"clientWidth\s*-\s*\d+\s*-\s*e\.clientX")

    def test_move_only_follows_after_pointer_down(self):
        self.assertIn("const move = (e) => { if (start.current) setWidth(", JSX)
        self.assertIn("const down = (e) => { start.current = true;", JSX)
        self.assertIn("const up = () => { start.current = null; };", JSX)

    def test_key_steps_unchanged(self):
        self.assertIn("const step = e.shiftKey ? 80 : 20;", JSX)
        self.assertIn('"ArrowLeft") setWidth(width.value + step)', JSX)
        self.assertIn('"ArrowRight") setWidth(width.value - step)', JSX)


if __name__ == "__main__":
    unittest.main()
