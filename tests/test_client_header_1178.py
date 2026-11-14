"""Item 1178: the client's published report header, carried over from the editor's option C. In a real browser, 1400 and 900 px, light and dark.

Run: python3 dev/run_tests.py test_client_header_1178        (needs Chrome; run only while the machine's load is under 70)
Checks: no "for <client>" in the heading line; the bar is 85 px (1400) and 125 px (900); the logo box is 147 x 22 (1400) and 120 x 18 (900);
no published chip or weeks list in the bar; the date is plain text; the file has no search or ask button; "Past reports" is the last
part of the profile menu. Fictional data.
"""
import re
import unittest

from _demo import USER
from test_glance_page import Published
from test_published_one_bar import BAR, CASES, InTheFile as Bar
from test_report_editor import tearDownModule  # noqa: F401

from _paths import SRC

LOGO = """(() => { const l = document.querySelector('header.top .logo'), b = l.getBoundingClientRect(), i = l.querySelector('.logo-icon').getBoundingClientRect();
  return {w: b.width, h: b.height, iconH: i.height, tag: l.tagName}; })()"""
DATE = """(() => { const d = document.querySelector('header.top .asat'); return d ? {tag: d.tagName, title: d.getAttribute('title'), role: d.getAttribute('role'), tab: d.getAttribute('tabindex'), aria: d.getAttribute('aria-label'), clickable: getComputedStyle(d).cursor === 'pointer'} : null; })()"""
CHIP = """(() => { const t = document.querySelector('header.top').textContent; return {published: /Published/i.test(t), weeks: /Published weeks/i.test(t), search: !!document.querySelector('header.top .pal-btn, header.top .tb-ask, header.top .ask-btn')}; })()"""


class Header(Published):
    close = Bar.close      # the file's browser helpers, without the other tests of that class
    bar = Bar.bar

    def setUp(self):
        super().setUp()
        with self.store.step("dashboard", USER) as st:
            st.update("projects", "ABC", {"client_name": "Example Client", "week_ending": "2026-10-23"})

    def test_the_heading_line_has_no_for_client(self):
        for width, dark in CASES:
            with self.subTest(width=width, dark=dark):
                cdp, p = self.bar(width, dark)
                line = p.js("document.querySelector('header.top .cover-line').textContent")
                self.assertIn("Week ending 23-10-2026", line)
                self.assertNotIn("Example Client", line)
                self.assertNotRegex(line, r"\bfor\b")

    def test_the_bar_is_25_percent_taller(self):
        for width, dark in CASES:
            with self.subTest(width=width, dark=dark):
                cdp, p = self.bar(width, dark)
                b = p.js(BAR)
                self.assertEqual(b["bar"]["h"], 85 if width == 1400 else 125)

    def test_the_logo_box_is_147_by_22_at_1400_and_120_by_18_at_900(self):
        for width, dark in CASES:
            with self.subTest(width=width, dark=dark):
                cdp, p = self.bar(width, dark)
                g = p.js(LOGO)
                want = (147, 22) if width == 1400 else (120, 18)
                self.assertEqual((round(g["w"]), round(g["h"])), want)
                self.assertLessEqual(g["iconH"], want[1])
                self.assertEqual(g["tag"], "SPAN", "a published file has no Home button")

    def test_the_profile_circle_is_at_the_right_edge_of_the_first_row(self):
        for width, dark in CASES:
            with self.subTest(width=width, dark=dark):
                cdp, p = self.bar(width, dark)
                b = p.js(BAR)
                self.assertGreater(b["badge"]["right"], width - 15 - 40, "at the right edge of the bar")

    def test_no_chip_and_no_weeks_list_in_the_bar_and_no_search_or_ask_button(self):
        for width, dark in CASES:
            with self.subTest(width=width, dark=dark):
                cdp, p = self.bar(width, dark)
                c = p.js(CHIP)
                self.assertEqual((c["published"], c["weeks"], c["search"]), (False, False, False))

    def test_the_date_is_plain_text_a_static_file_cannot_change_it(self):
        for width, dark in ((1400, False), (1400, True)):
            with self.subTest(width=width, dark=dark):
                cdp, p = self.bar(width, dark)
                d = p.js(DATE)
                self.assertEqual(d["tag"], "SPAN")
                self.assertEqual((d["title"], d["role"], d["tab"], d["clickable"]), (None, None, None, False))
                self.assertNotIn("Click to change date", d["aria"] or "")

    def test_past_reports_is_the_last_part_of_the_profile_menu(self):
        cdp, p = self.bar(1400, False)
        p.js("document.getElementById('client-menu-btn').click()")
        p.until("!!document.querySelector('#client-menu')", "the menu opened")
        last = p.js("(() => { const k = [...document.querySelector('#client-menu').children]; return k[k.length - 1].getAttribute('data-row'); })()")
        self.assertEqual(last, "past")

    def test_the_words_come_from_one_place(self):
        cover = (SRC / "clark" / "page" / "src" / "logic" / "cover.js").read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"push\(`for ", cover), "coverLine adds no 'for <client>'")


if __name__ == "__main__":
    unittest.main()
