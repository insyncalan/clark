"""Row 1485: the Feedback card is retired from Settings; the Feedback tag is the only way in (Classic theme, 1400 and 900 px).
Run: python3 dev/run_tests.py test_feedback_page_retired_1485
AP1 and AP2 and AP3 are drawn in headless Chrome over the fictional demo data (the harness of the tag's browser test); AP4 and AP5 read the source.
Required: the browser tests fail, never skip, without Chrome."""
import json
import re
import unittest

import test_feedback_tag_browser_1298 as B
from test_feedback_tag_browser_1298 import tearDownModule  # noqa: F401
from test_server import chrome, wait  # noqa: F401  (the harness: named here so the runner files this as a browser test)
from _paths import SRC

PAGE = SRC / "clark" / "page" / "src"
HELP = json.loads((PAGE / "help" / "helpContent.json").read_text(encoding="utf-8"))
CARDS = "document.querySelectorAll('.set-cards > section, .set-cards > .setting')"
SHOWN = f"[...{CARDS}].filter(c => !c.hidden && c.getClientRects().length > 0)"


def words(node):
    """Every string in a nested JSON value."""
    if isinstance(node, str):
        yield node
    elif isinstance(node, list):
        for x in node:
            yield from words(x)
    elif isinstance(node, dict):
        for x in node.values():
            yield from words(x)


class Page(B.FeedbackTagBrowser):
    def settings(self, cdp, sid, page):
        self.go(cdp, sid, f"#settings&p=TUL&s={page}")
        self.assertTrue(wait(lambda: cdp.js(f"document.querySelector('.set-cards') && document.querySelector('.set-cards').getAttribute('data-page') === {json.dumps(page)}", sid)), f"the {page} page drew")

    def test_the_version_page_has_no_feedback_card_at_1400_and_900(self):
        for cdp, sid, where in self.each():
            self.settings(cdp, sid, "version")
            heads = lambda: json.loads(cdp.js(f"JSON.stringify({SHOWN}.map(c => (c.querySelector('h2') || {{}}).id))", sid))
            self.assertTrue(wait(lambda: "quit-h" in heads()), f"{where}: the Quit card drew")
            self.assertEqual(heads(), ["update-h", "quit-h"], where + ": 2 cards, Update and Quit")
            self.assertEqual(cdp.js("document.querySelectorAll('#feedback, #feedback-h').length", sid), 0, where + ": 0 Feedback cards")

    def test_settings_search_for_feedback_shows_no_card_at_1400_and_900(self):
        for cdp, sid, where in self.each():
            for page in ("version", "appearance"):
                self.settings(cdp, sid, page)
                cdp.js("var b = document.getElementById('set-search-box'); b.focus(); b.value = 'feedback'; b.dispatchEvent(new Event('input', { bubbles: true }))", sid)
                self.assertTrue(wait(lambda: cdp.js("document.getElementById('set-search-box').value === 'feedback'", sid)), where)
                self.assertEqual(cdp.js(f"{SHOWN}.filter(c => /^feedback$/i.test(((c.querySelector('h2, h3') || {{}}).textContent || '').trim())).length", sid), 0, f"{where}, {page}: 0 Feedback cards")
                self.assertEqual(cdp.js("document.querySelectorAll('#feedback').length", sid), 0, f"{where}, {page}")
                cdp.js("var b = document.getElementById('set-search-box'); b.value = ''; b.dispatchEvent(new Event('input', { bubbles: true }))", sid)

    def test_the_tag_is_drawn_on_the_version_page_and_every_settings_page_and_in_help_at_1400_and_900(self):
        for cdp, sid, where in self.each():
            for page in B.SETTINGS_PAGES:
                self.settings(cdp, sid, page)
                self.assertTrue(wait(lambda: self.has_tag(cdp, sid)), f"{where}: the tag on Settings {page}")
                self.assertEqual(cdp.js("document.querySelectorAll('#feedback-tag').length", sid), 1, f"{where}: 1 tag on {page}")
            self.settings(cdp, sid, "version")
            cdp.js("var b = document.getElementById('set-search-box'); b.focus(); b.value = 'feedback'; b.dispatchEvent(new Event('input', { bubbles: true }))", sid)
            self.assertTrue(wait(lambda: self.has_tag(cdp, sid)), f"{where}: the tag stays while a search for feedback is typed")
            r = json.loads(cdp.js(f"JSON.stringify({B.BAR}.getBoundingClientRect())", sid))
            self.assertEqual(round(r["right"]), cdp.js("document.documentElement.clientWidth", sid), where + ": on the right edge")
            self.open_help(cdp, sid)
            self.assertEqual(cdp.js("document.querySelectorAll('#feedback-tag').length", sid), 1, where + ": 1 tag in Help")

    def test_help_has_no_settings_feedback_entry_and_no_link_to_it_at_1400_and_900(self):
        every = list(words(HELP))
        self.assertEqual([w for w in every if "ref-feedback" in w], [], "0 links to ref-feedback")
        self.assertEqual([w for w in every if "Settings › Feedback" in w], [], "0 Help lines name the Settings Feedback page")
        self.assertEqual([s["id"] for s in HELP["reference"]["sections"] if s["id"] == "feedback"], [], "0 reference page Settings Feedback")
        settings = next(s for s in HELP["reference"]["sections"] if s["id"] == "settings")
        self.assertEqual([r for r in words(settings["b"]) if re.search(r"\bFeedback\b", r)], [], "0 Feedback words in the Settings overview")
        self.assertEqual([c for c in words(HELP["context"]) if c == "feedback"], [], "0 context cards named feedback")
        for cdp, sid, where in self.each():
            self.open_help(cdp, sid)
            cdp.js("window.clarkPage.help.open('ref-settings')", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#ref-settings, [id=ref-settings]') || /Version and updates/.test(document.body.textContent)", sid)), where)
            self.assertEqual(cdp.js("document.querySelectorAll('a[href=\"#ref-feedback\"], #ref-feedback').length", sid), 0, where + ": 0 links to ref-feedback")
            self.assertFalse(cdp.js("/Settings › Feedback/.test(document.body.textContent)", sid), where)


class Source(unittest.TestCase):
    def read(self, *p):
        return (PAGE.joinpath(*p)).read_text(encoding="utf-8")

    def test_the_card_and_its_search_signal_are_gone_and_the_tag_keeps_its_version_check(self):
        self.assertFalse((PAGE / "edit" / "Feedback.jsx").exists(), "the card component is gone")
        self.assertNotIn("Feedback.jsx", self.read("edit", "index.js"), "0 imports of the Feedback card in edit/index.js")
        self.assertIsNone(re.search(r"\bFeedback\b(?!Tag)", re.search(r"export const EDIT = \{(.*?)\};", self.read("edit", "index.js"), re.S).group(1)), "the card is not an edit part")
        for f in [p for p in PAGE.rglob("*") if p.suffix in (".js", ".jsx")]:
            t = f.read_text(encoding="utf-8")
            self.assertNotIn("settingsFeedbackShown", t, f"{f.name}: 0 uses of settingsFeedbackShown")
            self.assertNotIn("feedbackCard", t, f"{f.name}: the feedbackCard parameter is gone")
        views = self.read("components", "Views.jsx")
        self.assertNotIn("feedback-h", views)
        self.assertIn('["Update", "Quit"]', views)
        tag = self.read("edit", "FeedbackTag.jsx")
        self.assertIn("export async function healthVersion()", tag, "the tag keeps its version check")
        self.assertIn('fetch("/health"', tag)
        self.assertIn("getVersion = healthVersion", tag)


if __name__ == "__main__":
    unittest.main()
