"""Row 1485: the Feedback card is retired from Settings; the Feedback tag is the only way in. Run: python3 dev/run_tests.py test_feedback_page_retired_1485
AP1 to AP4 run in headless Chrome at 1400 and 900 px (Classic theme, the fictional demo data, the harness of test_feedback_tag_browser_1298.py);
AP5 reads the code (no layout). Required: fails, never skips, without Chrome."""
import json
import re
import unittest

import _paths
import test_feedback_tag_browser_1298 as TB
from test_feedback_tag_browser_1298 import tearDownModule  # noqa: F401
from test_server import chrome, wait

PAGE_SRC = _paths.SRC / "clark" / "page" / "src"
BAR = TB.BAR
CARDS = "[...document.querySelectorAll('.set-cards > section, .set-cards > .setting')].filter(c => !c.hidden && c.getClientRects().length > 0)"
FEEDBACK_CARDS = CARDS + ".filter(c => /^Feedback$/.test(((c.querySelector('h2, h3') || {}).textContent || '').trim()) || !!c.querySelector('#feedback-h'))"
SETTINGS_PAGES = TB.SETTINGS_PAGES


class Retired(unittest.TestCase):
    setUp = TB.FeedbackTagBrowser.setUp
    read = TB.FeedbackTagBrowser.read
    open_page = TB.FeedbackTagBrowser.open_page
    look = TB.FeedbackTagBrowser.look
    go = TB.FeedbackTagBrowser.go
    has_tag = TB.FeedbackTagBrowser.has_tag
    open_help = TB.FeedbackTagBrowser.open_help
    each = TB.FeedbackTagBrowser.each

    def test_the_version_page_has_no_feedback_card_at_1400_and_900(self):
        for cdp, sid, where in self.each():
            self.go(cdp, sid, "#settings&p=TUL&s=version")
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#update-h')", sid)), where + ": the Version and updates page drew")
            heads = json.loads(cdp.js(f"JSON.stringify({CARDS}.map(c => (c.querySelector('h2, h3') || {{}}).id || ''))", sid))
            self.assertEqual(heads, ["update-h", "quit-h"], where + ": Update and Quit, 2 cards")
            self.assertEqual(cdp.js(f"{FEEDBACK_CARDS}.length", sid), 0, where)
            self.assertEqual(cdp.js("document.querySelectorAll('#feedback-h, #feedback-message, #feedback-contact').length", sid), 0, where)

    def test_settings_search_for_feedback_shows_no_card_at_1400_and_900(self):
        for cdp, sid, where in self.each():
            self.go(cdp, sid, "#settings&p=TUL&s=profile")
            self.assertTrue(wait(lambda: cdp.js("!!document.getElementById('set-search-box')", sid)), where)
            cdp.js("var b = document.getElementById('set-search-box'); b.focus(); b.value = 'feedback'; b.dispatchEvent(new Event('input', { bubbles: true }))", sid)
            self.assertEqual(cdp.js(f"{FEEDBACK_CARDS}.length", sid), 0, where + ": search for feedback shows 0 Feedback cards")
            self.assertEqual(cdp.js("document.querySelectorAll('#feedback-h').length", sid), 0, where)

    def test_the_tag_is_drawn_on_the_version_page_and_every_settings_page_and_in_help_at_1400_and_900(self):
        for cdp, sid, where in self.each():
            for page in SETTINGS_PAGES:
                self.go(cdp, sid, f"#settings&p=TUL&s={page}")
                self.assertTrue(wait(lambda: self.has_tag(cdp, sid)), f"{where}: tag on Settings {page}")
                self.assertEqual(cdp.js("document.querySelectorAll('#feedback-tag').length", sid), 1, f"{where}: 1 tag on {page}")
            self.assertEqual(cdp.js("document.querySelector('.set-cards').getAttribute('data-page')", sid), "version", where)
            self.open_help(cdp, sid)
            self.assertEqual(cdp.js("document.querySelectorAll('#feedback-tag').length", sid), 1, where + ": 1 tag in Help")
            r = json.loads(cdp.js(f"JSON.stringify({BAR}.getBoundingClientRect())", sid))
            self.assertEqual(round(r["right"]), cdp.js("document.documentElement.clientWidth", sid), where + ": on the right edge")

    def test_help_has_no_settings_feedback_entry_and_no_link_to_it_at_1400_and_900(self):
        content = (PAGE_SRC / "help" / "helpContent.json").read_text(encoding="utf-8")
        self.assertNotIn("ref-feedback", content)
        self.assertNotIn("Settings › Feedback", content)
        data = json.loads(content)
        self.assertEqual([s for s in data["reference"]["sections"] if s["id"] == "feedback"], [])
        self.assertNotIn('"card": "feedback"', content)
        for cdp, sid, where in self.each():
            self.go(cdp, sid, "#settings&p=TUL&s=version")
            self.open_help(cdp, sid)
            self.assertEqual(cdp.js("document.querySelectorAll('a[href*=\"ref-feedback\"], [data-help-link=\"ref-feedback\"], #ref-feedback').length", sid), 0, where)
            self.assertFalse(cdp.js("document.body.textContent.includes('Settings › Feedback')", sid), where)

    def test_the_card_and_its_search_signal_are_gone_and_the_tag_keeps_its_version_check(self):
        self.assertFalse((PAGE_SRC / "edit" / "Feedback.jsx").exists())
        self.assertNotIn("Feedback.jsx", (PAGE_SRC / "edit" / "index.js").read_text(encoding="utf-8"))
        self.assertNotRegex((PAGE_SRC / "edit" / "index.js").read_text(encoding="utf-8"), r"\bFeedback,")
        for path in PAGE_SRC.rglob("*.js*"):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("settingsFeedbackShown", text, path.name)
            self.assertNotIn("feedbackCard", text, path.name)
            self.assertNotIn("feedback-h", text, path.name)
        tag = (PAGE_SRC / "edit" / "FeedbackTag.jsx").read_text(encoding="utf-8")
        self.assertRegex(tag, r"export async function healthVersion\(")
        self.assertRegex(tag, r"getVersion = healthVersion")
        views = (PAGE_SRC / "components" / "Views.jsx").read_text(encoding="utf-8")
        self.assertIn('["version", "Version and updates", ["Update", "Quit"]]', views)


if __name__ == "__main__":
    unittest.main()
