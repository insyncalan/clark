"""#47e part 2: a suggested change in the ask panel, in a real browser, against the real page, the real change routes and the real
store (the answer comes from a STUB provider; nothing here calls a model).

Run: python3 dev/run_tests.py test_ask_change_page
Covers: the card's before and after come from the data, Apply saves once and the board shows it, Done with Undo puts it back, a
change from an answer that read your files needs the box ticked and Enter alone never applies it, a refusal is one plain line,
the off state leaves nothing to press, the card at 1400 and 900 px in light and dark, and every new sentence in askWords.js.
Fictional data only.
"""
import json
import re
import time
import unittest
from unittest import mock

from _demo import USER
from _paths import ROOT
from test_report_editor import Base
from test_server import chrome
from clark import ask, ask_apply, ask_passages, ask_service

WORDS = (ROOT / "src" / "clark" / "page" / "src" / "edit" / "askWords.js").read_text(encoding="utf-8")
CARD = (ROOT / "src" / "clark" / "page" / "src" / "edit" / "AskChange.jsx").read_text(encoding="utf-8")
NEVER = re.compile(r"\w*(Error|Exception)\b|Traceback|JSON|Not allowed|Bad request|\bAPI\b|\bHTTP\b|!")
FILE = ask.Passage("notes/plan.md", "The cut-over plan was signed off on Monday, so it can be closed.")
NEW_WORDS = ("CHANGE_HEAD", "NEW_HEAD", "FIELD", "NOW", "AFTER", "NOT_SET", "APPLY", "APPLYING_LINE", "FROM_FILE", "CONFIRM_LINE",
             "CONFIRM_NO_PASSAGE_LINE", "CONFIRM_BOX", "DONE_LINE", "UNDO", "UNDONE_LINE", "UNDO_FAILED_LINE", "REFUSED_LINE",
             "NOT_SAVED_LINE", "CHANGES_GONE_LINE")


class Card(Base):
    def setUp(self):
        super().setUp()
        self.action = self.demo.action(owner="Sam Lee", client_visible=1)
        self.provider = ask.StubProvider(reply="")
        self.files = ()
        self.service = ask_service.AskService(self.store.path, self.provider, [],
                                              applier=ask_apply.AskApply(self.store.path, [], USER))
        self.s.httpd.ask = self.service
        patch = mock.patch.object(ask_service.ask_passages, "folder_data",
                                  lambda *_a, **_k: ask_passages.FolderData(passages=tuple(self.files)))
        patch.start()
        self.addCleanup(patch.stop)

    def says(self, *lines, files=()):
        self.files = files
        self.provider.reply = "\n".join(("Here is what I found.",) + lines)

    def close_it(self, **more):
        return "CHANGE: " + json.dumps({"op": "change", "id": self.action, "current_title": "Draft the cut-over plan",
                                        "status": "Closed", **more})

    def opened(self, cdp):
        p = self.visit(cdp)
        p.key("/", code="Slash", vk=191)
        p.until("!!document.querySelector('#ask-panel') && !document.querySelector('#ask-box').disabled", "the panel is ready")
        return p

    def ask_it(self, p, text="What should change?"):
        p.js("document.querySelector('#ask-box').focus()")
        p.type(text)
        p.key("Enter", code="Enter", vk=13)

    def card(self, p):
        p.until("!!document.querySelector('[data-ask-change], [data-ask-refused]')", "the card came")

    def status(self):
        return self.store.read("actions", ref=self.action)["status"]


class TheCard(Card):
    def test_before_and_after_from_the_data_then_apply_then_undo(self):
        self.says(self.close_it())
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask_it(p)
            self.card(p)
            row = "document.querySelector('[data-ask-change] tr[data-field=status]')"
            self.assertEqual(p.js(f"{row}.querySelector('[data-before]').textContent"), "Open")
            self.assertEqual(p.js(f"{row}.querySelector('[data-after]').textContent"), "Closed")
            self.assertEqual(p.js("document.querySelector('[data-ask-change]').dataset.ref"), self.action)
            self.assertEqual(p.js("document.querySelectorAll('[data-ask-confirm]').length"), 0, "a change from the report needs no Confirm")
            self.assertEqual(self.status(), "Open", "showing it saved nothing")
            p.js("document.querySelector('[data-ask-apply]').click()")
            p.until("document.querySelector('[data-ask-line]') && document.querySelector('[data-ask-line]').textContent.startsWith('Done.')", "Done.")
            self.assertEqual(self.status(), "Closed")
            self.assertEqual(p.js("document.querySelectorAll('[data-ask-apply]').length"), 0, "Apply is gone: one Apply, one step")
            p.js("document.querySelector('[data-ask-undo]').click()")
            p.until("document.querySelector('[data-ask-line]').textContent === 'Undone. The old values are back.'", "Undone")
            self.assertEqual(self.status(), "Open")
            self.assertEqual(p.js("document.querySelectorAll('[data-ask-undo]').length"), 0)
            self.assertTrue(any(w == "undo" for w, _r in self.sent), "Undo went through the board's own /api/undo")
            self.assertFalse(any(w == "change" for w, _r in self.sent), "Apply never used the hand-edit route")

    def test_a_change_from_your_files_needs_the_box_and_enter_alone_never_applies(self):
        self.says(self.close_it(), "CITE: P5", files=(FILE,))
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask_it(p)
            self.card(p)
            p.until("!!document.querySelector('[data-ask-confirm]')", "the Confirm box")
            self.assertIn("signed off on Monday", p.js("document.querySelector('[data-ask-passage] blockquote').textContent"))
            self.assertEqual(p.js("document.querySelector('[data-ask-passage] figcaption').textContent"), "From your file: notes/plan.md")
            self.assertTrue(p.js("document.querySelector('[data-ask-apply]').disabled"), "Apply waits for the box")
            p.js("document.querySelector('[data-ask-apply]').click()")
            p.js("document.querySelector('[data-ask-confirm]').focus()")
            p.key("Enter", code="Enter", vk=13)
            self.assertFalse(p.js("document.querySelector('[data-ask-confirm]').checked"), "Enter does not tick the box")
            p.js("document.querySelector('#ask-box').focus()")
            p.key("Enter", code="Enter", vk=13)
            self.assertEqual(self.status(), "Open")
            p.js("document.querySelector('[data-ask-confirm]').click()")
            p.until("!document.querySelector('[data-ask-apply]').disabled", "Apply is ready once ticked")
            p.js("document.querySelector('[data-ask-apply]').focus()")
            p.key("Enter", code="Enter", vk=13)
            time.sleep(0.4)
            self.assertEqual(self.status(), "Open", "Enter alone on Apply never applies a change from a file")
            p.js("document.querySelector('[data-ask-apply]').click()")
            p.until("document.querySelector('[data-ask-line]') && document.querySelector('[data-ask-line]').textContent.startsWith('Done.')", "Done.")
            self.assertEqual(self.status(), "Closed")

    def test_a_refusal_is_one_plain_line_with_a_next_step(self):
        self.says("CHANGE: " + json.dumps({"op": "archive", "id": self.action}))
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask_it(p)
            self.card(p)
            text = p.js("document.querySelector('[data-ask-refused]').textContent")
            self.assertIn("isn't available yet", text)
            self.assertIn("Nothing was changed", text)
            self.assertEqual(p.js("document.querySelectorAll('[data-ask-apply]').length"), 0)

    def test_off_leaves_nothing_to_press(self):
        self.says(self.close_it())
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask_it(p)
            self.card(p)
            with self.store.step("dashboard", USER) as st:
                st.update("app_settings", "1", {"ask_enabled": False})
            p.js("document.querySelector('[data-ask-apply]').click()")
            p.until("!!document.querySelector('#ask-off')", "the panel went to the off line")
            self.assertEqual(p.js("document.querySelectorAll('[data-ask-change] button, [data-ask-change] input').length"), 0)
            self.assertEqual(self.status(), "Open")

    def test_markup_in_a_passage_is_inert_text(self):
        planted = ask.Passage("notes/x.md", '<img src=x onerror="window.__pwn=1"><b>bold</b>')
        self.says(self.close_it(), "CITE: P5", files=(planted,))
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask_it(p)
            self.card(p)
            p.until("!!document.querySelector('[data-ask-passage]')", "the passage")
            self.assertEqual(p.js("document.querySelectorAll('.ask-changes img, .ask-changes b').length"), 0)
            self.assertEqual(p.js("typeof window.__pwn"), "undefined")

    def test_laptop_widths_light_and_dark(self):
        self.says(self.close_it(), "CITE: P5", files=(FILE,))
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask_it(p)
            self.card(p)
            p.until("!!document.querySelector('[data-ask-confirm]')", "the card with its Confirm")
            for width in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                for theme in ("light", "dark"):
                    p.js(f"document.documentElement.dataset.theme = '{theme}'")
                    card = "document.querySelector('[data-ask-change]')"
                    self.assertTrue(p.js(f"{card}.scrollWidth <= {card}.clientWidth + 1"), f"{width} {theme}: the card fits")
                    self.assertTrue(p.js("document.documentElement.scrollWidth <= document.documentElement.clientWidth"), "no sideways scroll")
                    bg = p.js(f"getComputedStyle({card}).backgroundColor")
                    fg = p.js(f"getComputedStyle({card}).color")
                    self.assertNotEqual(bg, fg)
                    if theme == "dark":
                        self.assertNotEqual(bg, "rgb(255, 255, 255)", "the card follows dark mode")
                    r = p.js("(function(){var a=document.querySelector('[data-ask-apply]').getBoundingClientRect(),"
                             "b=document.querySelector('#ask-panel').getBoundingClientRect();return a.right<=b.right && a.left>=b.left})()")
                    self.assertTrue(r, "Apply is inside the panel")


class Words(unittest.TestCase):
    def test_every_new_sentence_is_plain_and_starts_with_what_happened_or_the_next_step(self):
        said = dict(re.findall(r'export const ([A-Z_]+) = "((?:[^"\\]|\\.)*)"', WORDS))
        for name in NEW_WORDS:
            self.assertIn(name, said)
            text = said[name]
            self.assertIsNone(NEVER.search(text), f"{name}: {text}")
            self.assertFalse(re.match(r"(ask )?clark", text, re.I), f"{name} starts with the product name")
        for name in NEW_WORDS:
            if name.endswith("_LINE"):
                self.assertRegex(said[name], r"[.…]$", name)
        for name in ("REFUSED_LINE", "NOT_SAVED_LINE", "CHANGES_GONE_LINE", "UNDO_FAILED_LINE", "CONFIRM_LINE"):
            self.assertRegex(said[name], r"(Ask again|Make it yourself|change it back yourself|press Apply)", f"{name} has a next step")

    def test_the_card_draws_text_only_and_says_nothing_of_its_own(self):
        self.assertNotIn("innerHTML", CARD)
        self.assertNotIn("dangerouslySetInnerHTML", CARD)
        self.assertIsNone(re.search(r'>\s*[A-Za-z][^<{]*[a-z]\s*<', CARD), "every sentence comes from askWords.js")

    def test_the_published_page_has_no_card(self):
        html = (ROOT / "src" / "clark" / "page" / "page-view.html").read_text(encoding="utf-8")
        for needle in ("/api/ask/change", "ask-change", "data-ask-apply", "After Apply"):
            self.assertNotIn(needle, html)
        self.assertIn("/api/ask/change/apply", (ROOT / "src" / "clark" / "page" / "page.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
