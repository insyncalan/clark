"""Row 1288: source pins for the editor's format bubble line and the Text style menu tick (no browser).
Run: python3 dev/run_tests.py test_rt_bubble_ai_killers_1288
"""
import re
import unittest

from _paths import ROOT

SRC = ROOT / "src" / "clark" / "page" / "src" / "edit" / "RichText.jsx"


class BubbleLine(unittest.TestCase):
    def setUp(self):
        self.rt = SRC.read_text(encoding="utf-8")
        m = re.search(r"\{ai \? <button[^\n]*", self.rt)
        self.assertIsNotNone(m, "the bubble line is drawn only when the editor has the AI place (ai)")
        self.btn = m.group(0)

    def test_the_words_come_from_the_shared_constant_and_it_is_imported(self):
        self.assertRegex(self.rt, r'import \{ AiFlow, DRAFT_WITH_AI \} from "\./DraftAi\.jsx"')

    def test_the_button_is_a_plain_button_with_its_class_and_hook(self):
        self.assertIn('type="button" class="rt-btn rt-bubble-ai" data-rt-bubble-ai', self.btn)

    def test_the_button_never_takes_the_focus_from_the_text(self):
        self.assertIn("data-rt-bubble-ai onMouseDown={hold}", self.btn)

    def test_the_click_opens_the_menu_under_the_middle_of_the_bubble(self):
        self.assertIn("openAi(r.left + r.width / 2, r.bottom + 4)", self.btn)
        self.assertIn("bubble.current.getBoundingClientRect()", self.btn)

    def test_it_is_the_last_child_of_the_bubble_after_the_format_buttons(self):
        i = self.rt.index("{BUBBLE.map(button)}")
        self.assertLess(i, self.rt.index(self.btn), "after the format buttons")
        self.assertTrue(self.rt[i:].split("</div>", 1)[0].rstrip().endswith("null}"), "nothing follows it inside the bubble")


class StyleTick(unittest.TestCase):
    def test_the_tick_follows_the_current_line_and_defaults_to_paragraph(self):
        rt = SRC.read_text(encoding="utf-8")
        self.assertIn('checked: current ? current[0] === n : n === "paragraph"', rt)


if __name__ == "__main__":
    unittest.main()
