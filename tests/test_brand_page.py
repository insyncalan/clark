"""Settings › Brands, the page's side (src/clark/page/src/edit/Brands.jsx and logic/brand.js), over a fake server, at 1400 and 900
pixels wide in light and dark. The routes are tests/test_brand_routes.py; the library is tests/test_brands_*.py. RED until the
card exists (the bundle cannot be built without it).

Run (browser file, headless, one at a time):
  flock /tmp/clark-chrome-lock env CLARK_CHROME=/usr/local/bin/clark-chrome python3 dev/run_tests.py test_brand_page
The card's contract: #brands holds #brands-list (one li[data-brand=<id>] per brand with its name and version, and a
[data-remove] button), a [data-choose] button ("Choose zip…"), [data-review] (the newest matching file in Downloads),
#brands-panel after a review (the id, name, version, the added / replaced / removed names, and [data-install], labelled Install for a
new brand and Replace for one already installed), [data-remove-confirm] after Remove, [data-undo] when there is something to put
back, and .pub-msg for the one sentence the server last said. Sentences come from the server's answer (code and message) and are
drawn as text, never changed.
"""
import re
import unittest

import test_update_page as up
from _paths import ROOT
from test_update_page import InBrowser, OK, lit

DEMO = ROOT / "tests" / "fixtures" / "brand_demo.jsx"
LIST = {"ok": True, "brands": [{"id": "example-brand", "name": "Example Brand", "version": "1.0.0"}], "undo": False}
REVIEW = {"review_id": "r1", "id": "other-brand", "name": "Other Brand", "version": "2.0.0", "zip_sha256": "ab" * 32,
          "added": ["tokens.css", "assets/cover.png"], "replaced": [], "removed": []}
REFUSAL = {"ok": False, "code": "damaged", "message": "This update file is damaged or has been changed. Download it again."}


class Page(InBrowser):
    @classmethod
    def setUpClass(cls):
        up.DEMO = DEMO
        up._PAGE.clear()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        up._PAGE.clear()

    def setUp(self):
        super().setUp()
        self.replies(list=OK(LIST), review=OK({"ok": True, "review": REVIEW}), install=OK({"ok": True}), remove=OK({"ok": True}),
                     undo=OK({"ok": True}))

    def test_the_list_shows_each_brand_with_its_name_and_version(self):
        self.mount()
        self.assertEqual(self.val("[...document.querySelectorAll('#brands-list li[data-brand]')].map(e => e.dataset.brand)"), ["example-brand"])
        row = self.text("#brands-list li[data-brand]")
        self.assertIn("Example Brand", row)
        self.assertIn("1.0.0", row)
        self.assertTrue(self.present("[data-choose]"))
        self.assertFalse(self.present("[data-undo]"), "nothing to put back yet")

    def test_review_then_install_is_a_second_click(self):
        self.mount()
        self.click("[data-review]")
        self.assertEqual(self.calls(), ["list", "review"], "nothing is installed by the first click")
        self.assertEqual(self.val("T.calls[1][1]"), {"from": "downloads"})
        panel = self.text("#brands-panel")
        for line in ("Other Brand", "2.0.0", "Colours and fonts", "tokens.css", "Cover picture", "assets/cover.png"):
            self.assertIn(line, panel)
        self.assertEqual(self.text("[data-install]"), "Install")
        self.click("[data-install]")
        self.assertEqual(self.val("T.calls.slice(-2)[0]"), ["install", "r1"])
        self.assertEqual(self.val("T.calls.at(-1)[0]"), "list", "the list is read again")

    def test_a_brand_already_installed_says_replace_and_lists_what_goes(self):
        self.replies(review=OK({"ok": True, "review": {**REVIEW, "id": "example-brand", "added": [], "replaced": ["tokens.css"],
                                                         "removed": ["assets/old.png"]}}))
        self.mount()
        self.click("[data-review]")
        self.assertEqual(self.text("[data-install]"), "Replace")
        self.assertIn("assets/old.png", self.text("#brands-panel"))

    def test_review_labels_come_first_and_the_file_name_is_small_and_grey_after(self):
        self.replies(review=OK({"ok": True, "review": {**REVIEW, "added": ["clark-brand.json", "tokens.css", "assets/cover.png", "assets/logo.png"]}}))
        self.mount()
        self.click("[data-review]")
        items = self.val("[...document.querySelectorAll('#brands-panel li')].map(e => [e.firstChild.textContent.trim(), e.querySelector('small').textContent])")
        self.assertEqual(items, [["Brand details", "clark-brand.json"], ["Colours and fonts", "tokens.css"],
                                 ["Cover picture", "assets/cover.png"], ["Logo", "assets/logo.png"]])
        self.assertTrue(self.val("parseFloat(getComputedStyle(document.querySelector('#brands-panel small')).fontSize)"
                                 " < parseFloat(getComputedStyle(document.querySelector('#brands-panel li')).fontSize)"))

    def test_no_file_chosen_is_the_servers_real_answer_and_a_calm_sentence_not_an_error(self):
        from _brand_rig import make_dirs
        from clark import server as sv
        root, data, scratch = make_dirs(self)
        (scratch / "Downloads").mkdir()
        lib = sv.BrandLibrary(root, data, choose=lambda *a, **k: None, downloads=scratch / "Downloads")
        for source in ("file", "downloads"):
            self.assertEqual(lib.review({"from": source}), (200, {"ok": True, "review": None}))
        real = lib.review({"from": "file"})[1]
        for source in ("file", "downloads"):
            with self.subTest(source):
                self.replies(review=OK(real))
                self.mount()
                self.click("[data-choose]" if source == "file" else "[data-review]")
                want = "No file was chosen, so nothing was changed." if source == "file" else "No brand file was found."
                self.assertEqual(self.text(".pub-msg"), want)
                self.assertEqual(self.val("document.querySelector('.pub-msg p').className"), "info")
                self.assertFalse(self.present("#brands-panel"))

    def test_a_brand_with_no_folder_of_its_own_has_no_remove_button_at_1400_and_900(self):
        listing = {**LIST, "brands": [LIST["brands"][0], {"id": "fabrikam", "name": "Fabrikam", "version": "2.1.0", "own_folder": False},
                                              {"id": "local-brand", "name": "local-brand", "version": "", "own_folder": False, "alias": "local-brand"}]}
        for width in up.WIDTHS:
            with self.subTest(width=width):
                self.load(width=width, theme="light")
                self.replies(list=OK(listing))
                self.mount()
                self.assertTrue(self.present("#brands-list li[data-brand='example-brand'] [data-remove]"))
                self.assertTrue(self.present("#brands-list li[data-brand='fabrikam']"))
                self.assertFalse(self.present("#brands-list li[data-brand='fabrikam'] [data-remove]"))
                self.assertTrue(self.present("#brands-list li[data-brand='local-brand']"))
                self.assertFalse(self.present("#brands-list li[data-brand='local-brand'] [data-remove]"))

    def test_the_red_error_can_be_dismissed(self):
        self.replies(review=OK(REFUSAL, 409))
        self.mount()
        self.click("[data-review]")
        self.assertEqual(self.val("document.querySelector('.pub-msg p').className"), "error")
        self.assertTrue(self.present(".pub-msg [data-dismiss]"))
        self.click(".pub-msg [data-dismiss]")
        self.assertEqual(self.text(".pub-msg"), "")
        self.assertFalse(self.present(".pub-msg [data-dismiss]"))

    def test_a_calm_line_has_no_dismiss_button(self):
        self.replies(review=OK({"ok": True, "review": None}))
        self.mount()
        self.click("[data-review]")
        self.assertFalse(self.present(".pub-msg [data-dismiss]"))

    def test_review_is_the_primary_button_only_when_there_is_something_to_review(self):
        for ready in (False, True):
            with self.subTest(ready=ready):
                self.replies(list=OK({**LIST, "review_ready": ready}))
                self.mount()
                self.assertEqual(self.val("document.querySelector('[data-review]').classList.contains('pri')"), ready)

    def test_choose_asks_for_a_file(self):
        self.mount()
        self.click("[data-choose]")
        self.assertEqual(self.val("T.calls[1][1]"), {"from": "file"})

    def test_remove_is_two_clicks(self):
        self.mount()
        self.click("#brands-list [data-remove]")
        self.assertEqual(self.calls(), ["list"], "the first click only asks")
        self.assertIn("Back to the default look", self.text("#brands"))
        self.click("[data-remove-confirm]")
        self.assertEqual(self.val("T.calls.slice(-2)[0]"), ["remove", "example-brand"])

    def test_keys_cancel_and_escape_hand_the_focus_back(self):
        """Item keys-settings: Cancel (or Esc) on Remove's question, and on the review panel, took the focus with it; it now goes back to the
        button that opened them (that brand's Remove; Review or Choose)."""
        for how in ("cancel", "escape"):
            with self.subTest(how=how, what="remove"):
                self.mount()
                self.js("document.querySelector('#brands-list [data-remove]').focus()")
                self.click("#brands-list [data-remove]")
                self.assertTrue(self.present("[data-remove-confirm]"))
                self.js("document.querySelector('[data-remove-confirm]').focus()")
                if how == "cancel":
                    self.click("[data-remove-confirm] + button")
                else:
                    self.press("Escape", 27)
                self.assertFalse(self.present("[data-remove-confirm]"), "the question closed")
                self.assertEqual(self.focused(), "button[data-remove]", "the focus is back on that brand's Remove")
            for opener in ("data-review", "data-choose"):
                with self.subTest(how=how, what=opener):
                    self.mount()
                    self.js(f"document.querySelector('[{opener}]').focus()")
                    self.click(f"[{opener}]")
                    self.assertTrue(self.present("#brands-panel"))
                    if how == "cancel":
                        self.click("#brands-panel [data-cancel]")
                    else:
                        self.press("Escape", 27)
                    self.assertFalse(self.present("#brands-panel"), "the panel closed")
                    self.assertEqual(self.focused(), f"button[{opener}]", "the focus is back on the button that opened the panel")

    def test_a_refused_or_empty_review_hands_the_focus_back_to_the_button_pressed(self):
        for what, reply in (("refused", OK(REFUSAL, 409)), ("empty", OK({"ok": True, "review": None}))):
            with self.subTest(what=what):
                self.mount()
                self.replies(review=reply)
                self.js("document.querySelector('[data-review]').focus()")
                self.click("[data-review]")
                self.assertEqual(self.focused(), "button[data-review]", "the focus is back on Review")

    def test_undo_is_one_click(self):
        self.replies(list=OK({**LIST, "undo": True}))
        self.mount()
        self.click("[data-undo]")
        self.assertEqual(self.val("T.calls.slice(-2)[0]"), ["undo", None])

    def test_a_refusal_is_shown_verbatim_and_nothing_else_changes(self):
        self.replies(review=OK(REFUSAL, 409))
        self.mount()
        self.click("[data-review]")
        self.assertEqual(self.val("document.querySelector('.pub-msg p').firstChild.textContent.trim()"), REFUSAL["message"])
        self.assertFalse(self.present("#brands-panel"))
        self.assertEqual(self.calls(), ["list", "review"])

    def test_a_refusal_with_no_message_says_the_one_general_sentence(self):
        self.replies(review=OK({"ok": False, "code": "damaged"}, 409))
        self.mount()
        self.click("[data-review]")
        self.assertEqual(self.val("document.querySelector('.pub-msg p').firstChild.textContent.trim()"), self.val("T.logic.GENERIC"))

    def test_the_card_holds_no_deny_list_word(self):
        from clark import brands
        self.mount()
        self.click("[data-review]")
        shown = self.text("#brands").lower() + " " + " ".join(self.val("Object.values(T.logic).filter(v => typeof v === 'string')")).lower()
        for word in brands.DENY_WORDS:
            self.assertNotIn(word.lower(), shown)

    def test_hostile_text_is_drawn_as_text(self):
        evil = '<img src=x onerror="window.pwned = 1">'
        self.replies(list=OK({**LIST, "brands": [{"id": "e", "name": evil, "version": evil}]}),
                     review=OK({"ok": True, "review": {**REVIEW, "name": evil, "added": [evil]}}))
        self.mount()
        self.click("[data-review]")
        self.assertFalse(self.val("!!window.pwned"))
        self.assertFalse(self.present("#brands img"))

    def test_hunt18_the_focus_stays_on_the_button_while_the_server_answers_and_after_a_refusal(self):
        """Review and Choose were disabled while the server answered, so the focus fell to the page."""
        for opener in ("data-review", "data-choose"):
            with self.subTest(opener):
                self.mount()
                self.js("T.replies.review = () => new Promise((ok) => { window.__ok = ok; })")
                self.js(f"document.querySelector('[{opener}]').focus()")
                self.click(f"[{opener}]")
                self.assertEqual(self.focused(), f"button[{opener}]", "the focus stays on the button while it waits")
                self.assertEqual(self.val(f"document.querySelector('[{opener}]').disabled"), False)
                self.assertEqual(self.val(f"document.querySelector('[{opener}]').getAttribute('aria-disabled')"), "true")
                self.js("window.__ok({status: 409, body: " + lit(REFUSAL) + "})")
                self.settle()
                self.assertEqual(self.focused(), f"button[{opener}]", "and after the refusal")

    def test_hunt18_after_install_remove_and_undo_the_focus_is_not_dropped_to_the_page(self):
        self.replies(list=OK({**LIST, "undo": True}))
        self.mount()
        self.js("document.querySelector('[data-review]').focus()")
        self.click("[data-review]")
        self.click("[data-install]")
        self.settle()
        self.assertEqual(self.focused(), "button[data-review]", "Install has gone: the focus is on the button that opened the panel")
        self.js("document.querySelector('#brands-list [data-remove]').focus()")
        self.click("#brands-list [data-remove]")
        self.js("document.querySelector('[data-remove-confirm]').focus()")
        self.replies(list=OK({"ok": True, "brands": [], "undo": True}))
        self.click("[data-remove-confirm]")
        self.settle()
        self.assertEqual(self.focused(), "button[data-review]", "the confirm button and that brand's Remove have gone: the focus is on Review")

    def test_hunt18_after_remove_that_leaves_the_brand_the_focus_is_on_its_remove_button(self):
        self.mount()
        self.js("document.querySelector('#brands-list [data-remove]').focus()")
        self.click("#brands-list [data-remove]")
        self.js("document.querySelector('[data-remove-confirm]').focus()")
        self.click("[data-remove-confirm]")
        self.assertEqual(self.focused(), "button[data-remove]", "the brand is still listed: the focus goes to its Remove")

    def test_hunt18_after_undo_the_focus_is_on_undo_while_there_is_more_to_put_back_and_on_review_when_not(self):
        self.replies(list=OK({**LIST, "undo": True}))
        self.mount()
        self.js("document.querySelector('[data-undo]').focus()")
        self.click("[data-undo]")
        self.assertEqual(self.focused(), "button[data-undo]", "Undo is still there")
        self.replies(list=OK({**LIST, "undo": False}))
        self.click("[data-undo]")
        self.assertFalse(self.present("[data-undo]"))
        self.assertEqual(self.focused(), "button[data-review]", "Undo has gone: the focus is on Review")

    def test_hunt18_cancel_and_escape_on_remove_fall_back_to_review_when_that_brands_remove_is_gone(self):
        for how in ("cancel", "escape"):
            with self.subTest(how=how):
                self.replies(list=OK({**LIST, "undo": True}))
                self.mount()
                self.click("#brands-list [data-remove]")
                self.js("document.querySelector('[data-remove-confirm]').focus()")
                self.replies(list=OK({"ok": True, "brands": [], "undo": True}))
                self.click("[data-undo]")
                self.assertFalse(self.present("#brands-list [data-remove]"), "the brand has gone while the question was open")
                self.assertTrue(self.present("[data-remove-confirm]"))
                self.js("document.querySelector('[data-remove-confirm]').focus()")
                if how == "cancel":
                    self.click("[data-remove-confirm] + button")
                else:
                    self.press("Escape", 27)
                self.assertFalse(self.present("[data-remove-confirm]"))
                self.assertEqual(self.focused(), "button[data-review]")

    def test_hunt18_a_click_while_the_server_is_answering_does_nothing(self):
        self.replies(list=OK({**LIST, "undo": True}))
        for first, others in (("[data-review]", ("[data-review]", "[data-choose]", "[data-undo]")),
                              ("[data-undo]", ("[data-undo]", "[data-review]", "[data-choose]"))):
            with self.subTest(first=first):
                self.mount()
                self.js("T.calls.length = 0; T.replies.review = () => new Promise(() => {}); T.replies.undo = () => new Promise(() => {})")
                self.click(first)
                for other in others:
                    self.click(other)
                want = "review" if first == "[data-review]" else "undo"
                self.assertEqual(self.calls(), [want], "only the first click reached the server")

    def test_plain_words_only(self):
        words = self.val("Object.values(T.logic).filter(v => typeof v === 'string')")
        for text in words:
            self.assertIsNone(re.search(r"(?i)\b(zip|manifest|sha|token|json|database)\b", text.replace("Choose zip…", "")), text)

    def test_keyboard_reaches_every_control(self):
        self.mount()
        self.assertTrue(self.val("[...document.querySelectorAll('#brands button')].every(b => b.tabIndex === 0)"))

    def test_focus_follows_the_keyboard_through_remove_install_and_cancel(self):
        self.mount()
        act = "document.activeElement && (document.activeElement.hasAttribute('data-remove-confirm') ? 'confirm' : document.activeElement.hasAttribute('data-remove') ? 'remove' : document.activeElement.hasAttribute('data-review') ? 'review' : document.activeElement.id)"
        self.click("#brands-list [data-remove]")
        self.assertEqual(self.val(act), "confirm", "Remove asks, and the Confirm button has the focus")
        self.click("#brands .row .quiet")
        self.assertEqual(self.val(act), "remove", "the ask is closed; the focus is back on Remove")
        self.click("[data-review]")
        self.click("[data-cancel]")
        self.assertEqual(self.val(act), "review", "the panel is closed; the focus is back on the button that opened it")
        self.click("[data-review]")
        self.click("[data-install]")
        self.assertEqual(self.val(act), "review", "after Install the focus is on Review")

    def test_nothing_runs_sideways_and_the_text_reads_at_1400_and_900_in_light_and_dark(self):
        for width in up.WIDTHS:
            for theme in up.THEMES:
                with self.subTest(width=width, theme=theme):
                    self.load(width=width, theme=theme)
                    self.replies(list=OK({**LIST, "undo": True}), review=OK({"ok": True, "review": REVIEW}))
                    self.mount()
                    self.click("[data-review]")
                    self.assertTrue(self.val("document.documentElement.scrollWidth <= document.documentElement.clientWidth"))
                    self.assertTrue(self.val("[...document.querySelectorAll('#brands button')].every(b => b.getBoundingClientRect().right <= innerWidth)"))
                    worst = self.val("Math.min(...[...document.querySelectorAll('#brands p, #brands li, #brands h2, #brands summary')]"
                                     ".filter(e => e.textContent.trim()).map(%s))" % up.CONTRAST)
                    self.assertGreaterEqual(worst, 4.5)


del InBrowser          # only Page runs here, not the imported base
if __name__ == "__main__":
    unittest.main()
