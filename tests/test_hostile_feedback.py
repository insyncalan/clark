"""Hostile tests for the Feedback tab logic (#1069): empty, huge and odd input, repeated calls, the length edge and the refusal
sentences. Same harness as test_feedback_tab.py (headless Chrome). Fictional data only.

Run: python3 dev/run_tests.py test_hostile_feedback
"""
import json
import unittest
from urllib.parse import parse_qs, urlsplit

import test_feedback_tab as tft
from test_server import Running  # noqa: F401  (the Chrome harness the base class runs on; named here so the runner files this as a browser test)


class Hostile(tft.InBrowser):
    def test_empty_and_odd_forms_never_throw_and_give_no_link(self):
        for form in ("undefined", "null", "{}", "{message: null}", "{message: undefined, contact: 5}", "{message: ''}", "{message: '\\u00a0\\u2003\\n\\t '}"):
            r = self.val(f"T.logic.mail({form}, {{}})")
            self.assertEqual(r, {"href": "", "message": self.val("T.logic.NOTHING_YET")}, form)

    def test_a_huge_message_gives_no_link_the_refusal_sentence_and_a_whole_copy_text(self):
        r = self.val("T.logic.mail({message: 'x'.repeat(200000), contact: ''}, {})")
        self.assertEqual(r, {"href": "", "message": self.val("T.logic.TOO_LONG")})
        copy = self.val("T.logic.copyText({message: 'y'.repeat(200000), contact: ''}, {version: '1', platform: 'p'})")
        self.assertIn("y" * 200000, copy)

    def test_the_length_edge_is_exact_and_matches_the_limit(self):
        limit = self.val("T.logic.MAILTO_LIMIT")
        n = self.val("(function(){ var n = 1; while (T.logic.mail({message: 'a'.repeat(n + 1), contact: ''}, {}).href) n++; return n; })()")
        ok = self.val(f"T.logic.mail({{message: 'a'.repeat({n}), contact: ''}}, {{}})")
        self.assertTrue(ok["href"])
        self.assertLessEqual(len(ok["href"]), limit)
        self.assertGreater(len(ok["href"]) + 1, limit - 1)
        self.assertEqual(self.val(f"T.logic.mail({{message: 'a'.repeat({n + 1}), contact: ''}}, {{}})")["message"], self.val("T.logic.TOO_LONG"))

    def test_a_lone_surrogate_does_not_throw(self):
        # encodeURIComponent throws URIError on a lone surrogate (a half emoji from a cut paste); the card must still answer
        for form in ("{message: 'half \\ud83d emoji', contact: ''}", "{message: 'ok', contact: 'x\\udc00'}"):
            r = self.val(f"T.logic.mail({form}, {{}})")
            self.assertIn("message", r, form)

    def test_a_lone_surrogate_becomes_the_replacement_character_in_the_link(self):
        high = self.val("T.logic.mail({message: 'half \\ud83d emoji', contact: ''}, {})")
        self.assertIn("half%20%EF%BF%BD%20emoji", high["href"])
        low = self.val("T.logic.mail({message: 'ok', contact: 'x\\udc00'}, {})")
        self.assertIn("x%EF%BF%BD", low["href"])

    def test_odd_characters_stay_one_header_and_one_body(self):
        msg = "a&subject=evil&body=x#frag %0d%0aBcc: z <b>\u202e\u2028 \U0001F600 \x00"
        r = self.val(f"T.logic.mail({{message: {json.dumps(msg)}, contact: 'c\\u2028Bcc: q\\r\\n'}}, {{version: 'v\\nBcc: z', platform: 'p\\u0085'}})")
        self.assertTrue(r["href"])
        parts = urlsplit(r["href"])
        self.assertEqual(parts.fragment, "")
        q = parse_qs(parts.query, keep_blank_values=True)
        self.assertEqual(sorted(q), ["body", "subject"])
        self.assertEqual(q["subject"], ["Feedback about clark"])
        body = q["body"][0]
        self.assertIn("a&subject=evil&body=x#frag %0d%0aBcc: z", body)
        for line in body.split("\n"):
            self.assertFalse(line.startswith("Bcc:"), line)
        self.assertNotIn("\r", body)

    def test_repeated_calls_are_pure_and_order_does_not_matter(self):
        a = self.val("(function(){ var f = {message: 'one', contact: 'c'}; var c = {version: '1', platform: 'p'}; var x = T.logic.mail(f, c); T.logic.mail({message: '', contact: ''}, c); T.logic.copyText(f, c); return [x, T.logic.mail(f, c), f]; })()")
        self.assertEqual(a[0], a[1])
        self.assertEqual(a[2], {"message": "one", "contact": "c"})

    def test_typing_then_clearing_then_whitespace_removes_the_link_each_time(self):
        self.mount()
        self.type("#feedback-message", "hello")
        self.assertTrue(self.href())
        self.type("#feedback-message", "")
        self.assertEqual(self.href(), "")
        self.type("#feedback-message", "   \n  ")
        self.assertEqual(self.href(), "")
        self.assertEqual(self.text("#feedback-note").strip() in ("", self.val("T.logic.NOTHING_YET")), True)
        self.type("#feedback-message", "again")
        self.assertTrue(self.href())

    def test_a_huge_card_input_leaves_copy_working_and_no_link(self):
        self.mount()
        self.js("(function(){ var e = document.querySelector('#feedback-message'); e.value = 'z'.repeat(150000); e.dispatchEvent(new Event('input', {bubbles: true})); })()")
        self.settle()
        self.assertEqual(self.href(), "")
        self.assertIn(self.val("T.logic.TOO_LONG"), self.js("document.body.textContent"))
        self.click("button[data-feedback-copy]")
        self.assertEqual(self.text("#feedback-note"), "Copied")


if __name__ == "__main__":
    unittest.main()
