"""#96 Headline band (store type 'headline'): the message, a button (shown only with both its words and a safe link) and an
optional picture; its checker, what it publishes, the picture through R1's route (one step, one Undo), the file and the served
View, and the page. The picture rules and the route itself are tested in test_tpl_textimage.py.

Run: python3 dev/run_tests.py test_tpl_headline
Needs Chrome (the #33 harness) for the page tests. Fictional data only.
"""
import json
import unittest

from _pictures import GOOD, GOOD_JPEG, PictureSteps, check, published
from _pictures_cases import PicturePage
from _pictures_page import BarePage
from clark import changes, publish, store as store_module
from clark.section_kinds import headline, textimage
from test_changes import Api
from test_server import chrome  # noqa: F401  (a browser file: its page tests drive Chrome through _pictures_cases)

KIND = "headline"
MESSAGE = "Fictional pilot is live in all three regions."


class Checker(unittest.TestCase):
    def test_its_fields_and_the_link_rule(self):
        got = check(KIND, {"v": 1, "words": f" {MESSAGE} ", "label": "Read the plan", "href": "https://example.org/plan", "alt": ""})
        self.assertEqual(got, {"v": 1, "words": MESSAGE, "label": "Read the plan", "href": "https://example.org/plan"})
        for href in ("https://example.org", "mailto:someone@example.org", "#ref-plan", " HTTPS://EXAMPLE.ORG"):
            self.assertEqual(headline.link(href), publish.safe_href(href), href)
            self.assertTrue(check(KIND, {"v": 1, "href": href}))
        for href in ("javascript:alert(1)", "java\tscript:alert(1)", "http://example.org", "data:text/html,x", "//example.org", "plan.html"):
            self.assertEqual(headline.link(href), publish.safe_href(href), href)
            with self.assertRaises(store_module.Invalid) as e:
                check(KIND, {"v": 1, "label": "Go", "href": href})
            self.assertEqual(str(e.exception), headline.BAD_LINK if "\t" not in href else "That content can't hold control or invisible characters.")
        for bad, words in (({"v": 1, "words": "x" * 401}, headline.LONG_WORDS), ({"v": 1, "label": "x" * 41}, headline.LONG_LABEL),
                           ({"v": 1, "words": ["x"]}, textimage.NOT_A_LINE), ({"v": 1, "colour": "red"}, textimage.UNKNOWN_FIELD)):
            with self.assertRaises(store_module.Invalid) as e:
                check(KIND, bad)
            self.assertEqual(str(e.exception), words)
        self.assertTrue(headline.READY)

    def test_published_the_button_needs_both_parts(self):
        self.assertIsNone(published(KIND, {"v": 1}))
        self.assertIsNone(published(KIND, {"v": 1, "label": "Read the plan"}), "a button with no link is not shown")
        self.assertIsNone(published(KIND, {"v": 1, "alt": "Fictional"}))
        self.assertEqual(published(KIND, {"v": 1, "words": MESSAGE, "label": "Read the plan"}), {"content": {"words": MESSAGE}})
        self.assertEqual(published(KIND, {"v": 1, "label": "Go", "href": "#ref-plan", "alt": "A", "pictures": {"image": GOOD}}),
                         {"content": {"label": "Go", "href": "#ref-plan", "image": GOOD, "alt": "A"}})


class Route(PictureSteps, Api):
    def test_one_step_one_undo_and_the_words_keep_the_picture(self):
        ref = self.made(KIND)
        self.words(ref, {"v": 1, "words": MESSAGE})
        status, got = self.put(ref, "image", GOOD)
        self.assertEqual(status, 200, got)
        self.undone(got["apply_id"])
        self.assertEqual(self.body(ref), {"v": 1, "words": MESSAGE}, "one Undo takes the picture out")
        self.put(ref, "image", GOOD_JPEG)
        self.words(ref, {"v": 1, "words": MESSAGE, "label": "Read the plan", "href": "https://example.org/plan"})
        self.assertEqual(self.body(ref)["pictures"], {"image": GOOD_JPEG})
        self.assertEqual(self.words(ref, {"v": 1, "href": "javascript:alert(1)"})[1]["message"], headline.BAD_LINK)
        self.assertEqual(self.body(ref)["href"], "https://example.org/plan", "a refusal writes nothing")

    def test_in_the_file_and_never_when_hidden_or_empty(self):
        shown = self.made(KIND, "Fictional band")
        self.words(shown, {"v": 1, "words": MESSAGE, "label": "Read the plan", "href": "https://example.org/plan"})
        empty = self.made(KIND, "Fictional empty")
        self.words(empty, {"v": 1, "label": "Fictional lonely button"})
        hidden = self.made(KIND, "Fictional hidden")
        self.words(hidden, {"v": 1, "words": "Fictional hidden message"})
        self.ok(changes.UPDATE, id=hidden, changes={"hidden": 1})
        sections, text = self.file()
        self.assertEqual(sections[shown]["content"], {"words": MESSAGE, "label": "Read the plan", "href": "https://example.org/plan"})
        self.assertNotIn(empty, sections)
        self.assertNotIn(hidden, sections)
        self.assertNotIn("Fictional lonely button", text)
        self.assertNotIn("Fictional hidden message", text)


class Parity(BarePage):
    def test_the_page_shows_what_publish_publishes(self):
        self.assertTrue(self.val("P.ready.headline"))
        self.parity(KIND, [{"v": 1}, {"v": 1, "label": "Go"}, {"v": 1, "words": MESSAGE}, {"v": 1, "pictures": {"image": GOOD}},
                           {"v": 1, "words": MESSAGE, "label": "Go", "href": "mailto:someone@example.org", "alt": "A",
                            "pictures": {"image": GOOD_JPEG}}])


class InThePage(PicturePage):
    KIND = KIND

    def test_view_and_edit(self):
        full = self.add({"v": 1, "words": MESSAGE, "label": "Read the plan", "href": "https://example.org/plan", "alt": "Fictional",
                         "pictures": {"image": GOOD}})
        ref = self.add(title="Fictional new")
        with self.chrome() as cdp:
            p = self.visit(cdp)
            sel = f"[data-id={json.dumps(full)}]"
            p.until(f"!!document.querySelector('{sel} .tpl-band')", "View draws the band")
            self.assertEqual(p.js(f"document.querySelector('{sel} .tpl-band-words').textContent"), MESSAGE)
            link = p.js(f"(function(){{var a=document.querySelector('{sel} a.tpl-band-btn'); return [a.textContent, a.getAttribute('href'), a.rel];}})()")
            self.assertEqual(link, ["Read the plan", "https://example.org/plan", "noopener noreferrer"])
            self.assertTrue(p.js(f"!!document.querySelector('{sel} .tpl-band img')"))
            self.assertFalse(p.js(f"!!document.querySelector('[data-id={json.dumps(ref)}]')"), "empty: not in View")
            self.at_widths(cdp, p, sel, ".tpl-band-text, img")
            p.edit()
            new = f"[data-id={json.dumps(ref)}]"
            p.until(f"!!document.querySelector('{new} .tpl-band-edit')", "the Edit part")
            start = self.applies()
            p.js(f"document.querySelector('{new} input[id$=-href]').focus()")
            p.type("javascript:alert(1)")
            p.key("Enter", code="Enter", vk=13)
            p.until("(document.querySelector('.toast-text') || {}).textContent === " + json.dumps(headline.BAD_LINK), "the link rule is said")
            self.assertEqual(self.applies(), start, "nothing was sent")
            p.clear_toast()
            p.js(f"document.querySelector('{new} input[id$=-words]').focus()")
            p.type(MESSAGE)
            p.key("Enter", code="Enter", vk=13)
            p.saved()
            self.assertEqual(self.body(ref), {"v": 1, "words": MESSAGE})
            self.assertEqual(self.applies(), start + 1)
            p.view()
            p.until(f"!!document.querySelector('{new} .tpl-band-words')", "now in View")
            self.assertFalse(p.js(f"!!document.querySelector('{new} a')"), "no button without its link")


if __name__ == "__main__":
    unittest.main()
