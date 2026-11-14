"""Item 1177: the one slim sticky header carries no published chip, no published-weeks list and no report-bar state text.
The published note lives in the profile menu alone. Chrome is required: these tests fail, never skip, without it.

Run: python3 dev/run_tests.py test_hdr1177_nochip
"""
import unittest

from test_publish_dialog import Base
from test_server import chrome

AREA = "[document.querySelector('.top'), document.querySelector('#report-bar')].filter(Boolean)"
TEXT = f"{AREA}.map(e => e.textContent).join(' | ')"
OLD_WORDS = r"/Draft|not published yet|Editing|each change saves|^Published|Published \d/"


class NoChip(Base):
    def publish(self, p):
        p.open_publish()
        p.go()
        p.until("document.querySelector('[data-go]').classList.contains('ok')", "published")
        p.go()
        p.until("!document.querySelector('#publish-dialog')", "closed")

    def test_no_state_chip_in_the_header_or_report_bar_before_or_after_publishing(self):
        for w in (1400, 900):
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                p.width(w, 700)
                self.assertEqual(p.js("document.querySelectorAll('#report-state, .rbar-state').length"), 0, f"{w}: a state chip is still drawn")
                self.assertFalse(p.js(f"{OLD_WORDS}.test({TEXT})"), f"{w}: old state words in the header, draft")
                self.publish(p)
                self.assertEqual(p.js("document.querySelectorAll('#report-state, .rbar-state, .hdr-published').length"), 0, f"{w}: a published chip appeared after publishing")
                self.assertFalse(p.js(f"{OLD_WORDS}.test({TEXT})"), f"{w}: published words in the header after publishing")

    def test_no_published_weeks_list_in_the_header_or_report_bar(self):
        for w in (1400, 900):
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                p.width(w, 700)
                self.assertEqual(p.js("document.querySelectorAll('#week-past, .rbar-past, .top select, #report-bar select').length"), 0, f"{w}: the published weeks list is still drawn")
                self.assertFalse(p.js("/Published weeks/.test(document.querySelector('.top').textContent + document.querySelector('.top').innerHTML)"), f"{w}: Published weeks wording in the header")

    def test_edit_mode_adds_no_state_text_to_the_header(self):
        with chrome() as cdp:
            p = self.page(cdp)
            p.width(1400, 700)
            p.js("document.querySelector('#mode-pill [data-mode=edit]').click()")
            p.until("document.querySelector('#report').dataset.mode === 'edit'", "edit")
            self.assertEqual(p.js("document.querySelectorAll('#report-state, .rbar-state').length"), 0, "edit: a state chip is drawn")
            self.assertFalse(p.js(f"{OLD_WORDS}.test({TEXT})"), "edit: old state words in the header")
            self.assertEqual(p.js("document.querySelector('#mode-pill').textContent.trim()"), "", "the floating pill has no text")

    def test_the_profile_menu_still_lists_the_published_info(self):
        for w in (1400, 900):
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                p.width(w, 700)
                self.publish(p)
                self.assertEqual(p.js("document.querySelectorAll('#report-state, .rbar-state').length"), 0, f"{w}: the chip is back")
                p.js("document.querySelector('.top #profile-menu, .top #profile-btn') && document.querySelector('#profile-btn').click()")
                p.until("!!document.querySelector('#profile-menu .lab')", "the note is in the menu")
                self.assertRegex(p.js("document.querySelector('#profile-menu .lab').textContent"), r"^Published \d\d-\d\d-\d{4} locally$", f"{w}: menu note")


if __name__ == "__main__":
    unittest.main()
