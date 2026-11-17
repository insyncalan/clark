"""#96 G5, Quote: the content rules (section_kinds/quote.py), the file, and the page's View and Edit parts.
Run: python3 dev/run_tests.py test_tpl_quote
Needs Chrome (the #33 harness): the page tests fail, never skip, without it. Fictional data only.
"""
import json
import unittest

import _tpl_notes as n
from test_server import chrome, wait

GOOD = {"v": 1, "quote": "Fictional words of thanks.", "by": "Sam Example", "role": "Fictional sponsor"}
HOSTILE = {"v": 1, "quote": n.HOSTILE, "by": n.HOSTILE, "role": n.HOSTILE}


class Data(n.DataChecks):
    TYPE, GOOD, WORDS, HOSTILE_BODY = "quote", GOOD, "Fictional words of thanks.", HOSTILE
    LIMIT_BODY = {"v": 1, "quote": "x" * 601}
    BAD = ({"v": 1, "quote": 5}, {"v": 1, "by": ["a"]}, {"v": 1, "role": "x" * 121}, {"v": 1, "by": "x" * 121})

    def test_who_said_it_alone_is_not_a_quote(self):
        ref = self.section()
        self.write(ref, {"v": 1, "by": "Sam Example"})
        self.assertNotIn(ref, self.file_sections())


    def test_tile_and_heading_are_two_switches_stored_only_when_off(self):
        ref = self.section()
        for off, want in (({}, {}), ({"tile": False}, {"tile": False}), ({"heading": False}, {"heading": False}),
                          ({"tile": False, "heading": False}, {"tile": False, "heading": False}), ({"tile": True, "heading": None}, {})):
            with self.subTest(off=off):
                status, got = self.write(ref, {**GOOD, **off})
                self.assertEqual(status, 200, got)
                self.assertEqual(json.loads(self.stored(ref)), {**GOOD, **want})
                content = self.file_sections()[ref]["content"]
                self.assertEqual({k: v for k, v in content.items() if k in ("tile", "heading")}, want)

    def test_a_switch_that_is_not_true_or_false_is_refused(self):
        ref = self.section()
        for bad in ({"tile": "no"}, {"heading": 0}, {"tile": []}):
            with self.subTest(bad=bad):
                before = self.snapshot()
                status, got = self.write(ref, {**GOOD, **bad})
                self.assertEqual(status, 400, got)
                self.assertEqual(self.snapshot(), before)

    def test_the_limits_are_600_for_the_words_and_120_for_name_and_role_exactly(self):
        ref = self.section()
        for field, most in (("quote", 600), ("by", 120), ("role", 120)):
            with self.subTest(field=field):
                status, got = self.write(ref, {**GOOD, field: "x" * most})
                self.assertEqual(status, 200, got)
                kept = self.stored(ref)
                status, got = self.write(ref, {**GOOD, field: "x" * (most + 1)})
                self.assertEqual(status, 400, got)
                self.assertEqual(self.stored(ref), kept, "a refused save changes nothing")

    def test_a_quote_with_a_switch_off_and_no_words_stays_out_of_the_file(self):
        ref = self.section()
        self.write(ref, {"v": 1, "by": "Sam Example", "tile": False, "heading": False})
        self.assertNotIn(ref, self.file_sections())


class Page(n.PageChecks):
    TYPE, GOOD, HOSTILE_BODY = "quote", GOOD, HOSTILE
    SHOWS = ("Fictional words of thanks.", "Sam Example, Fictional sponsor")
    FIELD, TYPED = "Quote words", "Fictional new words"
    CHANGED = lambda self, body: json.loads(body)["quote"] == "Fictional new words"

    def test_the_quote_is_a_blockquote_with_who_said_it_under_it(self):
        ref = self.make(self.GOOD)
        with chrome() as cdp:
            p = self.visit(cdp)
            base = f"[data-id={json.dumps(ref)}]"
            self.assertEqual(p.js(f"document.querySelector('{base} blockquote').textContent"), "Fictional words of thanks.")
            self.assertEqual(p.js(f"document.querySelector('{base} figcaption').textContent"), "Sam Example, Fictional sponsor")

    def _words_view(self, ref):
        return f"document.querySelector('[data-id={json.dumps(ref)}] [data-rich=quote]')"

    def test_edit_saves_a_field_as_one_step_and_undo_puts_it_back(self):
        ref = self.make(self.GOOD)
        before = self.body_of(ref)
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            ed = self._open_words(p, ref)
            p.js(f"{ed}.commands.selectAll()")
            p.type(self.TYPED)
            p.key("Enter", code="Enter", vk=13)
            p.saved()
            self.assertTrue(self.CHANGED(self.body_of(ref)), self.body_of(ref))
            sent = [r for which, r in self.sent if which == "change" and r.get("op") == "update"]
            self.assertEqual(len(sent), 1, "one save, one request")
            self.assertEqual(sent[0]["place"], "report")
            p.js("document.querySelector('[data-undo]').click()")
            p.until("document.querySelector('.toast-text').textContent === 'Undone.'", "Undo")
            self.assertEqual(self.body_of(ref), before)

    def test_edit_leaving_a_field_alone_saves_nothing(self):
        ref = self.make(self.GOOD)
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            self._open_words(p, ref)
            p.key("Escape", code="Escape", vk=27)
            p.until("!document.querySelector('.ProseMirror')", "closed")
            p.js("new Promise(r => setTimeout(r, 300))")
            self.assertEqual([r for which, r in self.sent if which == "change" and r.get("op") == "update"], [])

    def _open_words(self, p, ref):
        """Open the Quote words editor (the RichField view is clicked, as a person does) and return the editor's JS handle."""
        view = f"document.querySelector('[data-id={json.dumps(ref)}] [data-rich=quote]')"
        p.until(f"!!{view}", "the words view is there")
        p.js(f"{view}.click()")
        p.until("!!document.activeElement.cxed", "the words editor has the focus")
        return "(document.activeElement.cxed.editor)"

    def test_enter_in_the_quote_words_saves_them_as_one_line_and_the_box_grows_with_long_words(self):
        ref = self.make(self.GOOD)
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.visit(cdp)
                self._at(cdp, p, width)
                p.edit()
                ed = self._open_words(p, ref)
                p.js(f"{ed}.commands.selectAll()")
                p.type("Fictional enter words")
                p.key("Enter", code="Enter", vk=13)
                p.saved()
                self.assertEqual(json.loads(self.body_of(ref))["quote"], "Fictional enter words")
                p.until(f"!document.querySelector('[data-id={json.dumps(ref)}] .ProseMirror')", "Enter closed the editor")
                ed = self._open_words(p, ref)
                p.js(f"{ed}.commands.clearContent()")
                p.js("(function(){var b = document.activeElement; var d = new DataTransfer(); d.setData('text/plain', 'Fictional first\\n\\nsecond   third');"
                     " b.dispatchEvent(new ClipboardEvent('paste', {clipboardData: d, bubbles: true, cancelable: true}));})()")
                p.until(f"{ed}.getText().includes('third')", "pasted")
                p.key("Enter", code="Enter", vk=13)
                p.until("!document.querySelector('.ProseMirror')", "closed")
                self.assertTrue(wait(lambda: json.loads(self.body_of(ref))["quote"] == "Fictional first second third", 10), self.body_of(ref))
                self.assertNotIn("\n", json.loads(self.body_of(ref))["quote"])
                # long words wrap in the box and nothing runs wide
                self.assertLessEqual(p.js("document.documentElement.scrollWidth - document.documentElement.clientWidth"), 0)

    # ---- item 1271 slice 2: look B in View, the Tile and Heading switches in Edit ----
    def _at(self, cdp, p, width):
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)

    def test_view_look_b_has_the_rule_the_name_in_capitals_and_the_role_under_it_and_nothing_runs_wide(self):
        ref = self.make({**GOOD, "quote": "Fictional " + "words " * 90})
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.visit(cdp)
                self._at(cdp, p, width)
                q = f"document.querySelector('[data-id={json.dumps(ref)}] .tpl-quote')"
                self.assertEqual(p.js(f"getComputedStyle({q}, '::before').height"), "3px", "the short rule above the words")
                self.assertEqual(p.js(f"getComputedStyle({q}.querySelector('.tpl-quote-nm')).textTransform"), "uppercase")
                self.assertEqual(p.js(f"{q}.querySelector('.tpl-quote-nm').textContent"), "Sam Example")
                self.assertGreater(p.js(f"{q}.querySelector('.tpl-quote-rl').getBoundingClientRect().top"), p.js(f"{q}.querySelector('.tpl-quote-nm').getBoundingClientRect().bottom") - 1, "the role is under the name")
                self.assertLessEqual(p.js(f"{q}.scrollWidth"), p.js(f"{q}.clientWidth"), "no sideways overflow")

    def test_no_tile_and_no_heading_in_view_keep_the_heading_for_a_screen_reader(self):
        ref = self.make({**GOOD, "tile": False, "heading": False})
        with chrome() as cdp:
            p = self.visit(cdp)
            sec = f"document.querySelector('[data-id={json.dumps(ref)}]')"
            self.assertTrue(p.js(f"{sec}.classList.contains('no-tile') && {sec}.classList.contains('no-head')"))
            self.assertEqual(p.js(f"getComputedStyle({sec}).backgroundColor"), "rgba(0, 0, 0, 0)")
            self.assertLessEqual(p.js(f"{sec}.querySelector('.sec-h').getBoundingClientRect().width"), 2)
            self.assertIn("Fictional quote", p.js(f"{sec}.querySelector('.sec-h').textContent"))

    def test_a_quote_with_no_heading_hides_only_the_heading_and_keeps_its_tile(self):
        for off, head_hidden, tile_kept in (({"heading": False}, True, True), ({"tile": False}, False, False)):
            ref = self.make({**GOOD, **off})
            with self.subTest(off=off), chrome() as cdp:
                p = self.visit(cdp)
                sec = f"document.querySelector('[data-id={json.dumps(ref)}]')"
                self.assertEqual(p.js(f"{sec}.classList.contains('no-head')"), head_hidden)
                self.assertEqual(p.js(f"{sec}.querySelector('.sec-h').getBoundingClientRect().width <= 2"), head_hidden)
                self.assertEqual(p.js(f"{sec}.querySelector('.sec-head').getBoundingClientRect().height <= 2"), head_hidden)
                self.assertEqual(p.js(f"getComputedStyle({sec}).backgroundColor !== 'rgba(0, 0, 0, 0)'"), tile_kept)

    def test_edit_the_two_switches_save_and_the_off_state_tags_say_so(self):
        from test_server import wait
        for width in (1400, 900):
            ref = self.make(GOOD)
            with self.subTest(width=width), chrome() as cdp:
                p = self.visit(cdp)
                self._at(cdp, p, width)
                p.edit()
                sec = f"[data-id={json.dumps(ref)}]"
                q = lambda label: f"document.querySelector('{sec} [aria-label=\"{label}\"]')"
                tag = lambda: p.js(f"(document.querySelector('{sec} .tag.hid') || {{}}).textContent || ''")
                p.until(f"!!{q('Show the heading')}", "the toolbar")
                self.assertEqual(p.js(f"document.querySelector('{sec} [role=toolbar]').getAttribute('aria-label')"), "Quote tools")
                self.assertEqual(p.js(f"{q('Show the heading')}.getAttribute('aria-checked')"), "true")
                self.assertEqual(tag(), "")
                p.js(f"{q('Show the tile (the card around the quote)')}.click()")
                self.assertTrue(wait(lambda: json.loads(self.body_of(ref)).get("tile") is False, 10), self.body_of(ref))
                p.until(f"({q('Show the tile (the card around the quote)')}).getAttribute('aria-checked') === 'false'", "the tile switch is off")
                self.assertEqual(tag(), "Tile not shown in View")
                self.assertEqual(p.js(f"getComputedStyle(document.querySelector('{sec}')).borderStyle"), "dashed", "Edit keeps the card, dashed")
                p.js(f"{q('Show the heading')}.click()")
                self.assertTrue(wait(lambda: json.loads(self.body_of(ref)).get("heading") is False, 10), self.body_of(ref))
                p.until(f"document.querySelector('{sec} .tag.hid') && document.querySelector('{sec} .tag.hid').textContent === 'Tile and heading not shown in View'", "both tags")
                self.assertIn("line-through", p.js(f"getComputedStyle(document.querySelector('{sec} .sec-h')).textDecorationLine"))
                p.js(f"{q('Show the tile (the card around the quote)')}.click()")
                self.assertTrue(wait(lambda: "tile" not in json.loads(self.body_of(ref)), 10), self.body_of(ref))
                p.until(f"document.querySelector('{sec} .tag.hid') && document.querySelector('{sec} .tag.hid').textContent === 'Heading not shown in View'", "heading tag")

    # ---- item 1271 gaps: dark theme at 1400 and 900 in View and Edit; the 600 limit in Edit ----
    @staticmethod
    def _lum(css):
        """Relative brightness 0..1 of an 'rgb(r, g, b)' / 'rgba(...)' string."""
        r, g, b = [int(float(x)) for x in css[css.index("(") + 1:css.index(")")].split(",")[:3]]
        return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255

    def test_view_and_edit_keep_look_b_readable_in_dark_at_1400_and_900(self):
        ref = self.make({**GOOD, "quote": "Fictional " + "words " * 90})
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.visit(cdp)
                self._at(cdp, p, width)
                q = f"document.querySelector('[data-id={json.dumps(ref)}] .tpl-quote')"
                for mode in ("view", "edit"):
                    if mode == "edit":
                        p.edit()
                        p.until(f"!!{q}", "the Quote in Edit")
                    seen = {}
                    for theme in ("light", "dark"):
                        p.js(f"document.documentElement.setAttribute('data-theme', '{theme}')")
                        where = f"{mode} {theme} {width}"
                        seen[theme] = self._lum(p.js(f"getComputedStyle({q}).backgroundColor"))
                        self.assertEqual(p.js(f"getComputedStyle({q}, '::before').height"), "3px", f"{where}: the rule")
                        self.assertLessEqual(p.js(f"{q}.scrollWidth"), p.js(f"{q}.clientWidth"), f"{where}: no sideways overflow")
                        self.assertLessEqual(p.js("document.documentElement.scrollWidth - document.documentElement.clientWidth"), 0, f"{where}: the page does not scroll sideways")
                        if mode == "view":
                            words = self._lum(p.js(f"getComputedStyle({q}.querySelector('.tpl-quote-q')).color"))
                            name = self._lum(p.js(f"getComputedStyle({q}.querySelector('.tpl-quote-nm')).color"))
                            role = self._lum(p.js(f"getComputedStyle({q}.querySelector('.tpl-quote-rl')).color"))
                            for what, ink in (("words", words), ("name", name), ("role", role)):
                                self.assertGreater(abs(ink - seen[theme]), 0.3, f"{where}: the {what} read against the panel")
                    self.assertGreater(seen["light"] - seen["dark"], 0.3, f"{mode} {width}: the panel goes dark with the theme")

    def test_edit_stops_the_words_at_600_and_the_name_and_role_at_120(self):
        ref = self.make(GOOD)
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.visit(cdp)
                self._at(cdp, p, width)
                p.edit()
                for label, most in (("Quote said by", 120), ("Quote role", 120)):
                    sel = n.field_js(ref, label)
                    p.until(f"!!{sel}", label)
                    self.assertEqual(p.js(f"{sel}.maxLength"), most, label)
                ed = self._open_words(p, ref)
                before = self.body_of(ref)
                p.js(f"{ed}.commands.selectAll()")
                p.type("w" * 601)
                p.key("Enter", code="Enter", vk=13)
                p.js("new Promise(r => setTimeout(r, 500))")
                self.assertEqual(self.body_of(ref), before, "601 characters are not saved")
                self.assertTrue(p.js("!!document.querySelector('.ProseMirror')"), "the editor stays open on too long words")
                p.js(f"{ed}.commands.selectAll()")
                p.type("w" * 600)
                p.key("Enter", code="Enter", vk=13)
                self.assertTrue(wait(lambda: json.loads(self.body_of(ref))["quote"] == "w" * 600, 10), "600 characters are saved")


if __name__ == "__main__":
    unittest.main()
