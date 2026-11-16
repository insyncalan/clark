"""#96 G5, Callout: the content rules (section_kinds/callout.py), the file, and the page's View and Edit parts.
Run: python3 dev/run_tests.py test_tpl_callout
Needs Chrome (the #33 harness): the page tests fail, never skip, without it. Fictional data only.
"""
import json
import unittest

import _tpl_notes as n
from test_server import chrome

GOOD = {"v": 1, "tone": "decision", "title": "Fictional decision", "paras": ["Fictional words about the budget.", "A second fictional line."]}
HOSTILE = {"v": 1, "tone": "warning", "title": n.HOSTILE, "paras": [n.HOSTILE]}


class Data(n.DataChecks):
    TYPE, GOOD, WORDS, HOSTILE_BODY = "callout", GOOD, "Fictional words about the budget.", HOSTILE
    LIMIT_BODY = {"v": 1, "title": "x" * 121}
    BAD = ({"v": 1, "tone": "loud"}, {"v": 1, "title": 5}, {"v": 1, "paras": "one"}, {"v": 1, "paras": [{"a": 1}]},
           {"v": 1, "paras": ["x"] * 7}, {"v": 1, "paras": ["x" * 601]},
           {"v": 1, "category": "x" * 31}, {"v": 1, "category": 5}, {"v": 1, "colour": "pink"}, {"v": 1, "icon": "emoji"}, {"v": 1, "tile": "yes"}, {"v": 1, "heading": 1})

    def test_the_tone_and_empty_paragraphs(self):
        ref = self.section()
        self.write(ref, {"v": 1, "title": "Fictional", "paras": ["", "  ", "Kept"]})
        self.assertEqual(json.loads(self.stored(ref)), {"paras": ["Kept"], "title": "Fictional", "tone": "info", "v": 1})

    def test_the_new_fields_are_kept_and_an_older_callout_is_unchanged(self):
        ref = self.section()
        self.write(ref, GOOD)
        self.assertEqual(json.loads(self.stored(ref)), {"v": 1, "tone": "decision", "title": "Fictional decision", "paras": GOOD["paras"]})
        self.write(ref, {**GOOD, "category": " Budget ", "colour": "green", "icon": "none", "tile": False, "heading": True})
        got = json.loads(self.stored(ref))
        self.assertEqual((got["category"], got["colour"], got["icon"], got["tile"], got["heading"]), ("Budget", "green", "none", False, True))

    def test_the_file_says_the_category_colour_and_icon_in_words(self):
        ref = self.section()
        self.write(ref, {**GOOD, "category": "Budget", "colour": "violet", "icon": "bulb"})
        c = self.file_sections()[ref]["content"]
        self.assertEqual((c["category"], c["colour_name"], c["icon_name"]), ("Budget", "Violet", "Light bulb"))
        self.write(ref, GOOD)                       # an older callout: the colour and icon its tone drew
        c = self.file_sections()[ref]["content"]
        self.assertEqual((c["category"], c["colour_name"], c["icon_name"], c["tile"], c["heading"]), ("", "Amber", "Question", True, True))

    def test_a_tone_alone_is_not_content(self):
        ref = self.section()
        self.write(ref, {"v": 1, "tone": "warning"})
        self.assertNotIn(ref, self.file_sections())


class Words(unittest.TestCase):
    """The named lists and defaults themselves (mutation check): every colour and icon, the tone looks, words() alone."""

    def test_every_colour_and_icon_is_named_and_the_tone_looks_are_kept(self):
        from clark.section_kinds import callout
        self.assertEqual(tuple(callout.COLOURS), ("plain", "violet", "amber", "red", "green", "grey"))
        self.assertEqual(len(callout.ICONS), 21)
        self.assertIn("shield", callout.ICONS)
        self.assertEqual(callout.COLOURS["grey"], "Grey")
        self.assertEqual(callout.TONE_LOOK, {"info": ("violet", "info"), "decision": ("amber", "question"), "warning": ("red", "warning")})
        self.assertEqual(callout.upgrade({"v": 1, "tone": "warning"}),
                         {"v": 1, "tone": "warning", "category": "", "colour": "red", "icon": "warning", "tile": True, "heading": True})

    def test_words_alone_carries_the_category_colour_and_icon(self):
        from clark.section_kinds import callout
        self.assertEqual(callout.words({"v": 1, "tone": "warning", "category": "Budget", "colour": "grey", "icon": "shield"}),
                         {"category": "Budget", "colour_name": "Grey", "icon_name": "Shield"})
        self.assertEqual(callout.words({"v": 1, "icon": "none", "colour": "plain"}), {"category": "", "colour_name": "Plain", "icon_name": ""})


class Page(n.PageChecks):
    TYPE, GOOD, HOSTILE_BODY = "callout", GOOD, HOSTILE
    SHOWS = ("Decision needed", "Fictional decision", "Fictional words about the budget.", "A second fictional line.")
    FIELD, TYPED = "Callout title", "Fictional new title"
    CHANGED = lambda self, body: json.loads(body)["title"] == "Fictional new title"

    def test_the_tone_is_a_word_and_not_colour_alone(self):
        ref = self.make(self.GOOD)
        with chrome() as cdp:
            p = self.visit(cdp)
            self.assertEqual(p.js(f"document.querySelector('[data-id={json.dumps(ref)}] .tpl-callout-tone').textContent"), "Decision needed")
            self.assertEqual(p.js(f"document.querySelector('[data-id={json.dumps(ref)}] .tpl-callout').getAttribute('role')"), "note")

    def test_two_quick_saves_both_keep_their_words(self):
        ref = self.make(self.GOOD)
        n.slow_saves(self)
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            p.until(f"!!document.querySelector('[data-id={json.dumps(ref)}] [data-rich=callout]')", "the fields")
            n.fill(p, n.field_js(ref, "Callout title"), "Fictional first title")
            # the words are the one editor (row 1005): typed in it and saved with Cmd or Ctrl+Enter while the title's save is still in flight
            sec = f"[data-id={json.dumps(ref)}]"
            p.js(f"document.querySelector('{sec} [data-rich]').click()")
            p.until(f"!!document.querySelector('{sec} .ProseMirror')", "the editor opened")
            p.js(f"document.querySelector('{sec} .ProseMirror').cxed.editor.commands.insertContent('<p>Fictional second words</p>'); true")
            p.key("Enter", 4 if p.js("/Mac/.test(navigator.platform)") else 2, code="Enter", vk=13)
            from test_server import wait
            self.assertTrue(wait(lambda: "Fictional second words" in json.loads(self.body_of(ref)).get("html", ""), 10), self.body_of(ref))
            got = json.loads(self.body_of(ref))
            self.assertEqual(got["title"], "Fictional first title", "the second save kept the first one's words")

    def test_a_refused_save_puts_the_saved_words_back_and_the_page_says_what_to_do(self):
        ref = self.make(self.GOOD)
        before = self.body_of(ref)
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            p.until(f"!!{n.field_js(ref, 'Callout title')}", "the fields")
            n.fill(p, n.field_js(ref, "Callout title"), "bad\u202ewords")                  # an invisible direction mark: the store refuses it
            p.until("!!document.querySelector('.toast')", "the page said something")
            p.until(f"{n.field_js(ref, 'Callout title')}.value === 'Fictional decision'", "the saved title is back in the field")
            self.assertEqual(self.body_of(ref), before)
            self.assertTrue(p.toast().endswith((".", "?")), p.toast())

    # ---- #1272 slice 2: the look in View and the controls in Edit ----
    def _at(self, cdp, p, width):
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)

    def test_view_draws_the_colour_the_icon_and_the_category_word(self):
        ref = self.make({**GOOD, "category": "Legal hold", "colour": "green", "icon": "lock"})
        old = self.make(GOOD)
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.visit(cdp)
                self._at(cdp, p, width)
                box = lambda r: f"document.querySelector('[data-id={json.dumps(r)}] .tpl-callout')"
                self.assertEqual(p.js(f"{box(ref)}.dataset.colour + ' ' + {box(ref)}.dataset.icon"), "green lock")
                self.assertEqual(p.js(f"{box(ref)}.querySelector('.tpl-callout-tone').textContent"), "Legal hold")
                self.assertTrue(p.js(f"!!{box(ref)}.querySelector('svg[data-icn=lock]')"))
                self.assertEqual(p.js(f"{box(old)}.dataset.colour + ' ' + {box(old)}.dataset.icon"), "amber question", "an older callout draws its tone's look")
                self.assertEqual(p.js(f"{box(old)}.querySelector('.tpl-callout-tone').textContent"), "Decision needed")

    def test_a_colour_with_no_word_and_no_icon_draws_its_own_shape_and_plain_draws_none(self):
        a = self.make({**GOOD, "category": "", "colour": "red", "icon": "none"})
        b = self.make({**GOOD, "category": "", "colour": "plain", "icon": "none"})
        with chrome() as cdp:
            p = self.visit(cdp)
            self.assertTrue(p.js(f"!!document.querySelector('[data-id={json.dumps(a)}] .tpl-callout svg[data-icn=shRed]')"))
            self.assertFalse(p.js(f"!!document.querySelector('[data-id={json.dumps(b)}] .tpl-callout svg')"))

    def test_no_tile_and_no_heading_in_view_and_the_heading_keeps_its_name(self):
        ref = self.make({**GOOD, "tile": False, "heading": False})
        with chrome() as cdp:
            p = self.visit(cdp)
            sec = f"document.querySelector('[data-id={json.dumps(ref)}]')"
            self.assertTrue(p.js(f"{sec}.classList.contains('no-tile') && {sec}.classList.contains('no-head')"))
            self.assertEqual(p.js(f"getComputedStyle({sec}).backgroundColor"), "rgba(0, 0, 0, 0)")
            self.assertLessEqual(p.js(f"{sec}.querySelector('.sec-h').getBoundingClientRect().width"), 2)
            self.assertIn("Fictional callout", p.js(f"{sec}.querySelector('.sec-h').textContent"), "the heading is still in the page for a screen reader")

    def test_edit_a_suggestion_sets_the_word_the_colour_and_the_icon_as_one_step(self):
        for width in (1400, 900):
            ref = self.make(GOOD)
            with self.subTest(width=width), chrome() as cdp:
                p = self.visit(cdp)
                self._at(cdp, p, width)
                p.edit()
                sec = f"[data-id={json.dumps(ref)}]"
                p.until(f"!!document.querySelector('{sec} [aria-label=\"Use Warning\"]')", "the toolbar")
                p.js(f"document.querySelector('{sec} [aria-label=\"Use Warning\"]').click()")
                p.saved()
                got = json.loads(self.body_of(ref))
                self.assertEqual((got["category"], got["colour"], got["icon"], got["tone"]), ("Warning", "red", "warning", "warning"))
                p.js(f"document.querySelector('{sec} [aria-label=\"No category\"]').click()")
                from test_server import wait
                self.assertTrue(wait(lambda: "category" not in json.loads(self.body_of(ref)), 10), self.body_of(ref))
                self.assertEqual(json.loads(self.body_of(ref))["colour"], "red")

    def test_edit_the_colour_the_icon_and_the_switches_save(self):
        ref = self.make(GOOD)
        from test_server import wait
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            sec = f"[data-id={json.dumps(ref)}]"
            q = lambda label: f"document.querySelector('{sec} [aria-label=\"{label}\"]')"
            p.until(f"!!{q('Green')}", "the toolbar")
            self.assertEqual(p.js(f"{q('Amber')}.getAttribute('aria-checked')"), "true", "an older callout shows its tone's colour")
            p.js(f"{q('Green')}.click()")
            self.assertTrue(wait(lambda: json.loads(self.body_of(ref)).get("colour") == "green", 10), self.body_of(ref))
            self.assertEqual(json.loads(self.body_of(ref))["category"], "Decision needed", "the word an older callout drew is kept")
            p.js(f"{q('Choose an icon')}.click()")
            p.until(f"!!document.querySelector('{sec} [role=listbox]')", "the icons are listed")
            self.assertEqual(p.js(f"document.querySelectorAll('{sec} [role=option]').length"), 21, "20 icons and No icon")
            p.js(f"[...document.querySelectorAll('{sec} [role=option]')].find(o => o.textContent === 'Key').click()")
            self.assertTrue(wait(lambda: json.loads(self.body_of(ref)).get("icon") == "key", 10), self.body_of(ref))
            self.assertFalse(p.js(f"!!document.querySelector('{sec} [role=listbox]')"), "choosing closes the list")
            p.js(f"{q('Show the tile (the card around the callout)')}.click()")
            self.assertTrue(wait(lambda: json.loads(self.body_of(ref)).get("tile") is False, 10), self.body_of(ref))
            p.js(f"{q('Show the heading')}.click()")
            self.assertTrue(wait(lambda: json.loads(self.body_of(ref)).get("heading") is False, 10), self.body_of(ref))
            self.assertTrue(p.js(f"document.querySelector('{sec}').classList.contains('no-tile')"), "Edit keeps the card, dashed")
            self.assertEqual(p.js(f"getComputedStyle(document.querySelector('{sec}')).borderStyle"), "dashed")

    def test_edit_a_category_is_typed_in_the_toolbar_and_over_30_characters_is_not_typed(self):
        ref = self.make(GOOD)
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            sel = n.field_js(ref, "Category")
            p.until(f"!!{sel}", "the category field")
            self.assertEqual(p.js(f"{sel}.maxLength"), 30)
            n.fill(p, sel, "Legal hold")
            p.saved()
            got = json.loads(self.body_of(ref))
            self.assertEqual((got["category"], got["colour"], got["icon"]), ("Legal hold", "amber", "question"))


if __name__ == "__main__":
    unittest.main()
