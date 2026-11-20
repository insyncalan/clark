"""Row 1272: callout_lines(section) gives the client Excel's text lines for a callout, as pure data (no sheet).

Run: python3 dev/run_tests.py test_excel_callout_lines_1272
"""
import unittest

from _paths import ROOT   # noqa: F401

from clark.excel_callout_lines import callout_lines

BASE = {"v": 1, "tone": "decision", "title": "ZQ-Pick one", "paras": ["ZQ-para"], "category": "ZQ-Choice", "colour": "amber", "icon": "flag"}


def lines(**over):
    return callout_lines({"type": "callout", "content": {**BASE, **over}})


class CalloutLines(unittest.TestCase):
    def test_all_parts_in_order_with_heading_flagged(self):
        self.assertEqual(lines(), [("ZQ-Pick one", True), ("Category: ZQ-Choice. Colour: Amber. Icon: Flag.", False), ("ZQ-para", False)])

    def test_no_category(self):
        self.assertEqual(lines(category="")[1], ("Colour: Amber. Icon: Flag.", False))

    def test_no_colour_name(self):
        self.assertEqual(lines(colour="plain")[1], ("Category: ZQ-Choice. Icon: Flag.", False))

    def test_no_icon(self):
        self.assertEqual(lines(icon="none")[1], ("Category: ZQ-Choice. Colour: Amber.", False))

    def test_no_colour_and_no_icon(self):
        self.assertEqual(lines(colour="plain", icon="none")[1], ("Category: ZQ-Choice.", False))

    def test_no_part_at_all_has_no_line(self):
        self.assertEqual(lines(category="", colour="plain", icon="none"), [("ZQ-Pick one", True), ("ZQ-para", False)])

    def test_no_title_heading_is_callout(self):
        self.assertEqual(lines(title="")[0], ("Callout", True))

    def test_paras_only_one_entry_each(self):
        self.assertEqual(lines(paras=["ZQ-a", "ZQ-b"])[2:], [("ZQ-a", False), ("ZQ-b", False)])

    def test_editor_html_words_one_entry_per_paragraph(self):
        self.assertEqual(lines(html="<p>ZQ-one <b>x</b></p><p>ZQ-two</p>")[2:], [("ZQ-one x", False), ("ZQ-two", False)])

    def test_html_wins_over_paras(self):
        self.assertEqual(lines(html="<p>ZQ-h</p>")[-1], ("ZQ-h", False))

    def test_blank_paragraphs_are_dropped(self):
        self.assertEqual(lines(paras=["ZQ-a", "  ", "ZQ-b"])[2:], [("ZQ-a", False), ("ZQ-b", False)])

    def test_title_only(self):
        self.assertEqual(lines(paras=[])[0], ("ZQ-Pick one", True))

    def test_empty_callout_is_empty(self):
        self.assertEqual(lines(title="", paras=[], category="", colour="plain", icon="none"), [])

    def test_all_five_empty_with_the_fields_absent_is_empty(self):
        self.assertEqual(callout_lines({"type": "callout", "content": {"title": "", "paras": [], "category": "", "colour": "plain", "icon": "none"}}), [])

    def test_category_only_gets_heading_and_line(self):
        self.assertEqual(lines(title="", paras=[], colour="plain", icon="none"), [("Callout", True), ("Category: ZQ-Choice.", False)])

    def test_colour_only_gets_heading_and_line(self):
        self.assertEqual(lines(title="", paras=[], category="", icon="none"), [("Callout", True), ("Colour: Amber.", False)])

    def test_icon_only_gets_heading_and_line(self):
        self.assertEqual(lines(title="", paras=[], category="", colour="plain"), [("Callout", True), ("Icon: Flag.", False)])

    def test_category_only_heading_off_is_just_the_line(self):
        self.assertEqual(lines(title="", paras=[], colour="plain", icon="none", heading=False), [("Category: ZQ-Choice.", False)])

    def test_category_only_with_title_keeps_title_heading(self):
        self.assertEqual(lines(title="ZQ-T", paras=[], colour="plain", icon="none")[0], ("ZQ-T", True))

    def test_tile_switch_changes_nothing(self):
        self.assertEqual(lines(tile=False), lines(tile=True))
        self.assertEqual(lines(tile=False, title="", paras=[], colour="plain", icon="none"), lines(tile=True, title="", paras=[], colour="plain", icon="none"))

    def test_no_content_is_empty(self):
        self.assertEqual(callout_lines({"type": "callout"}), [])

    def test_only_the_heading_is_flagged(self):
        self.assertEqual([h for _, h in lines(heading=True)], [True, False, False])
        self.assertEqual([h for _, h in lines(heading=False)], [False, False])

    def test_heading_off_with_title_drops_only_the_heading(self):
        self.assertEqual(lines(heading=False), [("Category: ZQ-Choice. Colour: Amber. Icon: Flag.", False), ("ZQ-para", False)])

    def test_heading_off_without_title_drops_the_callout_fallback(self):
        self.assertEqual(lines(heading=False, title=""), [("Category: ZQ-Choice. Colour: Amber. Icon: Flag.", False), ("ZQ-para", False)])

    def test_heading_on_explicit(self):
        self.assertEqual(lines(heading=True), [("ZQ-Pick one", True), ("Category: ZQ-Choice. Colour: Amber. Icon: Flag.", False), ("ZQ-para", False)])

    def test_heading_flag_absent_is_on(self):
        self.assertEqual(lines(), lines(heading=True))
        self.assertEqual(lines()[0], ("ZQ-Pick one", True))

    def test_heading_off_and_empty_callout_is_empty(self):
        self.assertEqual(lines(heading=False, title="", paras=[], category="", colour="plain", icon="none"), [])

    def test_heading_off_title_only_keeps_the_parts_line(self):
        self.assertEqual(lines(heading=False, paras=[]), [("Category: ZQ-Choice. Colour: Amber. Icon: Flag.", False)])

    def test_heading_off_keeps_word_order(self):
        self.assertEqual(lines(heading=False, paras=["ZQ-a", "ZQ-b"])[1:], [("ZQ-a", False), ("ZQ-b", False)])


if __name__ == "__main__":
    unittest.main()
