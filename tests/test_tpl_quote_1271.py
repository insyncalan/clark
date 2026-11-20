"""Row 1271, Quote template: the store (up to six quotes, align, perRow, tile, heading; the older one-quote shape kept), the file, View look F
(Classic) at 1400 and 900, and Edit in place. Run: python3 dev/run_tests.py test_tpl_quote_1271
Needs Chrome (the #33 harness). Fictional data only. Widths 1400 and 900 only.
"""
import json
import unittest

import tempfile

import _tpl_notes as n
from clark import page
from clark.section_kinds import quote
from test_report_editor import real_server
from test_server import chrome, wait

Q = lambda t, by="", role="": {"quote": t, "by": by, "role": role}
LIST = {"v": 1, "quotes": [Q("Fictional first.", "Sam Example", "Fictional sponsor"), Q("Fictional second.", "Alex Example")], "align": "centre", "perRow": 3, "tile": False, "heading": False}


class Store(unittest.TestCase):
    def test_the_older_shape_is_kept_as_it_is(self):
        old = {"v": 1, "quote": "Fictional.", "by": "Sam", "role": "R"}
        self.assertEqual(quote.check(old, None), old)

    def test_the_list_shape_is_rebuilt_field_by_field(self):
        got = quote.check({**LIST, "extra": 1, "quotes": [{**LIST["quotes"][0], "x": 2}, LIST["quotes"][1]]}, None)
        self.assertEqual(got, LIST)

    def test_six_quotes_pass_and_seven_or_none_are_refused(self):
        six = {"v": 1, "quotes": [Q(f"Fictional {i}.") for i in range(6)]}
        self.assertEqual(len(quote.check(six, None)["quotes"]), 6)
        for bad in ([Q("a")] * 7, [], "x", [5]):
            with self.subTest(bad=bad), self.assertRaises(quote.Bad):
                quote.check({"v": 1, "quotes": bad}, None)

    def test_align_per_row_tile_and_heading_are_checked(self):
        for field, bad in (("align", "right"), ("align", 1), ("perRow", 4), ("perRow", "2"), ("perRow", True), ("tile", "no"), ("heading", 0)):
            with self.subTest(field=field, bad=bad), self.assertRaises(quote.Bad):
                quote.check({**LIST, field: bad}, None)

    def test_every_quote_keeps_its_own_limits(self):
        for q in (Q("x" * 601), Q("a", "x" * 121), Q("a", "", "x" * 121)):
            with self.subTest(q=q), self.assertRaises(quote.Bad):
                quote.check({"v": 1, "quotes": [Q("ok"), q]}, None)

    def test_a_reader_gets_every_field_filled_in(self):
        old = quote.upgrade({"v": 1, "quote": "Fictional.", "by": "Sam", "role": "R"})
        self.assertEqual(old, {"quotes": [Q("Fictional.", "Sam", "R")], "align": "left", "perRow": 2, "tile": True, "heading": True})
        self.assertEqual(quote.upgrade(LIST)["quotes"], LIST["quotes"])

    def test_the_file_carries_only_the_quotes_that_have_words(self):
        got = quote.published({"v": 1, "quotes": [Q("", "Only a name"), Q("Fictional kept.", "Sam"), Q("  ".strip())], "align": "centre"}, None)["content"]
        self.assertEqual(got["quotes"], [Q("Fictional kept.", "Sam")])
        self.assertEqual((got["quote"], got["by"], got["align"], got["perRow"], got["tile"], got["heading"]), ("Fictional kept.", "Sam", "centre", 2, True, True))

    def test_no_quote_with_words_is_not_in_the_file(self):
        self.assertIsNone(quote.published({"v": 1, "quotes": [Q("", "Sam"), Q("")]}, None))
        self.assertIsNone(quote.published({"v": 1, "quote": "", "by": "Sam", "role": ""}, None))


class Data(n.DataChecks):
    TYPE, GOOD, WORDS, HOSTILE_BODY = "quote", LIST, "Fictional first.", {"v": 1, "quotes": [Q(n.HOSTILE, n.HOSTILE, n.HOSTILE)]}
    LIMIT_BODY = {"v": 1, "quotes": [Q("x" * 601)]}
    BAD = ({"v": 1, "quotes": [Q("a")] * 7}, {"v": 1, "quotes": [Q("a")], "align": "middle"}, {"v": 1, "quotes": [Q("a")], "perRow": 5}, {"v": 1, "quotes": [{"quote": 5}]})

    def test_an_empty_quote_stays_in_the_store_and_out_of_the_file(self):
        ref = self.section()
        self.write(ref, {"v": 1, "quotes": [Q("Fictional kept."), Q("")]})
        self.assertEqual(len(json.loads(self.stored(ref))["quotes"]), 2)
        self.assertEqual(self.file_sections()[ref]["content"]["quotes"], [Q("Fictional kept.")])

    def test_an_older_quote_is_still_published(self):
        ref = self.section()
        self.write(ref, {"v": 1, "quote": "Fictional old.", "by": "Sam", "role": ""})
        self.assertEqual(self.file_sections()[ref]["content"]["quotes"], [Q("Fictional old.", "Sam")])


class Look:
    """The page checks that need the Classic look and Edit in place (a mixin: the page tests below run it on the Classic page)."""

    def _at(self, cdp, p, width):
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)

    def _quotes(self, ref):
        return f"document.querySelector('[data-id={json.dumps(ref)}] .tpl-quotes')"

    def test_view_look_f_at_1400_and_900(self):
        ref = self.make({"v": 1, "quotes": [Q("Fictional first.", "Sam Example", "Fictional sponsor"), Q("Fictional second.", "Alex Example"), Q("Fictional third.")], "align": "centre"})
        for width, cols in ((1400, 2), (900, 1)):
            with self.subTest(width=width), chrome() as cdp:
                p = self.visit(cdp)
                self._at(cdp, p, width)
                g = self._quotes(ref)
                self.assertEqual(p.js(f"getComputedStyle({g}).gridTemplateColumns.split(' ').length"), cols)
                one = f"{g}.querySelector('.tpl-quote')"
                self.assertEqual(p.js(f"getComputedStyle({one}).textAlign"), "center")
                self.assertEqual(p.js(f"getComputedStyle({one}.querySelector('.tpl-quote-by'), '::before').width"), "32px")
                self.assertEqual(p.js(f"getComputedStyle({one}.querySelector('.tpl-quote-by'), '::before').height"), "2px")
                self.assertEqual(p.js(f"getComputedStyle({one}.querySelector('.tpl-quote-name')).textTransform"), "uppercase")
                qq = f"{one}.querySelector('.tpl-quote-q')"
                self.assertEqual(p.js(f"(function(){{ var q = {qq}, now = getComputedStyle(q).maxWidth; q.style.maxWidth = '62ch'; var want = getComputedStyle(q).maxWidth; q.style.maxWidth = ''; return now === want; }})()"), True, "the words are at most 62ch wide")
                self.assertFalse(p.js("document.documentElement.scrollWidth > document.documentElement.clientWidth"), "no sideways scroll")

    def test_left_is_the_default_and_three_to_a_row_when_stored(self):
        plain = self.make({"v": 1, "quotes": [Q("Fictional a."), Q("Fictional b."), Q("Fictional c.")]})
        three = self.make({"v": 1, "quotes": [Q("Fictional a."), Q("Fictional b."), Q("Fictional c.")], "perRow": 3})
        with chrome() as cdp:
            p = self.visit(cdp)
            self._at(cdp, p, 1400)
            self.assertEqual(p.js(f"{self._quotes(plain)}.dataset.align"), "left")
            self.assertEqual(p.js(f"getComputedStyle({self._quotes(plain)}.querySelector('.tpl-quote')).textAlign"), "left")
            self.assertEqual(p.js(f"getComputedStyle({self._quotes(plain)}).gridTemplateColumns.split(' ').length"), 2)
            self.assertEqual(p.js(f"getComputedStyle({self._quotes(three)}).gridTemplateColumns.split(' ').length"), 3)

    def test_view_leaves_out_an_empty_quote_and_the_old_shape_still_shows(self):
        ref = self.make({"v": 1, "quotes": [Q("Fictional kept."), Q("", "Only a name")]})
        old = self.make({"v": 1, "quote": "Fictional old.", "by": "Sam", "role": "R"})
        with chrome() as cdp:
            p = self.visit(cdp)
            self.assertEqual(p.js(f"{self._quotes(ref)}.querySelectorAll('.tpl-quote').length"), 1)
            self.assertEqual(p.js(f"{self._quotes(old)}.querySelector('figcaption').textContent"), "Sam, R")

    def test_the_tile_and_heading_switches_give_four_states_in_view(self):
        refs = {(t, h): self.make({"v": 1, "quotes": [Q("Fictional.")], "tile": t, "heading": h}) for t in (True, False) for h in (True, False)}
        with chrome() as cdp:
            p = self.visit(cdp)
            for (t, h), ref in refs.items():
                cls = p.js(f"document.querySelector('[data-id={json.dumps(ref)}]').className")
                self.assertEqual(("no-tile" not in cls, "no-head" not in cls), (t, h))

    def test_edit_in_place_add_remove_and_count(self):
        ref = self.make({"v": 1, "quotes": [Q("Fictional first.")]})
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            sec = f"[data-id={json.dumps(ref)}]"
            q = lambda css: f"document.querySelector('{sec} {css}')"
            p.until(f"!!{q('[data-tq-count]')}", "the toolbar")
            self.assertEqual(p.js(f"{q('[data-tq-count]')}.textContent"), "Up to 6 quotes (1 of 6)")
            self.assertEqual(p.js(f"{q('[data-tq-words]')}.textContent"), "16 of 600")
            self.assertFalse(p.js(f"!!{q('.tq-rm')}"), "one quote: no Remove")
            p.js(f"{q('.tq-add')}.click()")
            self.assertTrue(wait(lambda: len(json.loads(self.body_of(ref))["quotes"]) == 2, 10), self.body_of(ref))
            p.until(f"document.querySelectorAll('{sec} .tpl-quote-pe').length === 2", "two boxes")
            self.assertEqual(p.js(f"{q('[data-tq-count]')}.textContent"), "Up to 6 quotes (2 of 6)")
            self.assertEqual(p.js(f"document.querySelectorAll('{sec} .tq-rm').length"), 2)
            p.js(f"document.querySelectorAll('{sec} .tq-rm')[1].click()")
            self.assertTrue(wait(lambda: len(json.loads(self.body_of(ref))["quotes"]) == 1, 10), self.body_of(ref))

    def test_edit_add_is_off_at_six(self):
        ref = self.make({"v": 1, "quotes": [Q(f"Fictional {i}.") for i in range(6)]})
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            p.until(f"!!document.querySelector('[data-id={json.dumps(ref)}] .tq-add')", "Add")
            self.assertTrue(p.js(f"document.querySelector('[data-id={json.dumps(ref)}] .tq-add').disabled"))
            self.assertEqual(p.js(f"document.querySelector('[data-id={json.dumps(ref)}] [data-tq-count]').textContent"), "Up to 6 quotes (6 of 6)")

    def test_edit_the_switches_align_and_per_row_save(self):
        ref = self.make({"v": 1, "quotes": [Q("Fictional first.")]})
        with chrome() as cdp:
            p = self.visit(cdp)
            self._at(cdp, p, 1400)
            p.edit()
            sec = f"[data-id={json.dumps(ref)}]"
            q = lambda css: f"document.querySelector('{sec} {css}')"
            p.until(f"!!{q('[aria-label=\"Show the heading\"]')}", "the toolbar")
            p.js(f"{q('[aria-label=\"Show the tile (the card around the quote)\"]')}.click()")
            self.assertTrue(wait(lambda: json.loads(self.body_of(ref)).get("tile") is False, 10), self.body_of(ref))
            p.js(f"{q('[aria-label=\"Show the heading\"]')}.click()")
            self.assertTrue(wait(lambda: json.loads(self.body_of(ref)).get("heading") is False, 10), self.body_of(ref))
            p.js(f"[...document.querySelectorAll('{sec} [aria-label=Align] button')].find(b => b.textContent === 'Centre').click()")
            self.assertTrue(wait(lambda: json.loads(self.body_of(ref)).get("align") == "centre", 10), self.body_of(ref))
            p.js(f"[...document.querySelectorAll('{sec} [aria-label=\"Per row\"] button')].find(b => b.textContent === '3').click()")
            self.assertTrue(wait(lambda: json.loads(self.body_of(ref)).get("perRow") == 3, 10), self.body_of(ref))
            self.assertIn("no-tile", p.js(f"{q('')}.className"))

    def test_edit_per_row_is_off_at_900(self):
        ref = self.make({"v": 1, "quotes": [Q("Fictional first.")]})
        with chrome() as cdp:
            p = self.visit(cdp)
            self._at(cdp, p, 900)
            p.edit()
            sel = f"document.querySelector('[data-id={json.dumps(ref)}] [aria-label=\"Per row\"] button')"
            p.until(f"!!{sel}", "Per row")
            p.until(f"{sel}.disabled", "off at 900")


class Classic(Look, n.PageChecks):
    """The editor page with the Classic Theme layered (the look is Classic only; Cards keeps shell.css)."""
    TYPE, GOOD, HOSTILE_BODY = "quote", LIST, {"v": 1, "quotes": [Q(n.HOSTILE, n.HOSTILE, n.HOSTILE)]}
    SHOWS = ("Fictional first.",)
    FIELD, TYPED = "Quote words", "Fictional new words"
    CHANGED = lambda self, body: json.loads(body)["quotes"][0]["quote"] == "Fictional new words"

    def setUp(self):
        super().setUp()
        self.s.close()
        self.s = real_server(self.store.path, self.store.data_for, page_html=lambda: page.page_html(tempfile.mkdtemp(), theme="prototype-2.0"), seam=self.seam)
        self.addCleanup(self.s.close)


class Page(n.PageChecks):
    TYPE, GOOD, HOSTILE_BODY = "quote", LIST, {"v": 1, "quotes": [Q(n.HOSTILE, n.HOSTILE, n.HOSTILE)]}
    SHOWS = ("Fictional first.", "Fictional second.", "Sam Example, Fictional sponsor")
    FIELD, TYPED = "Quote words", "Fictional new words"
    CHANGED = lambda self, body: json.loads(body)["quotes"][0]["quote"] == "Fictional new words"

if __name__ == "__main__":
    unittest.main()
