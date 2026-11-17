"""#96 G5, Quote: the content rules (section_kinds/quote.py), the file, and the page's View and Edit parts.
Run: python3 dev/run_tests.py test_tpl_quote
Needs Chrome (the #33 harness): the page tests fail, never skip, without it. Fictional data only.
"""
import json
import unittest

import _tpl_notes as n
from test_server import chrome

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

    def test_enter_in_the_quote_words_saves_them_as_one_line(self):
        ref = self.make(self.GOOD)
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            sel = n.field_js(ref, "Quote words")
            p.until(f"!!{sel}", "the field is there")
            self.assertEqual(p.js(f"{sel}.tagName"), "INPUT", "one line: Enter can't add a line break")
            p.js(f"(function(){{ var el = {sel}; el.focus(); el.select(); }})()")
            p.until(f"document.activeElement === {sel}", "focus")
            p.type("Fictional enter words")
            p.cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13, "text": "\r"}, p.sid)
            p.cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13}, p.sid)
            p.saved()
            self.assertEqual(json.loads(self.body_of(ref))["quote"], "Fictional enter words")

    # ---- #1271 slice 2: look B in View, the Tile and Heading switches in Edit ----
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

    # ---- #1271 gaps: dark theme at 1400 and 900 in View and Edit; the 600 limit in Edit ----
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
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            for label, most in (("Quote words", 600), ("Quote said by", 120), ("Quote role", 120)):
                sel = n.field_js(ref, label)
                p.until(f"!!{sel}", label)
                self.assertEqual(p.js(f"{sel}.maxLength"), most, label)


if __name__ == "__main__":
    unittest.main()
