"""#74: what a Supporting Documents link may be (src/clark/doclinks.py), and what a person sees of it.

Run: python3 dev/run_tests.py test_doclinks
The tables are the one case list the page's JavaScript test and the store's test will also run (spec 74, point 3).
Every address is fictional (example.com, example.net, example.org, 192.0.2.x); the hostile strings are test inputs only.
"""
import ast
import json
import os
import random
import subprocess
import sys
import unittest

from clark import doclinks
from clark.doclinks import LinkError, check_link, link_host, link_label, looks_like_other_place

# (what was typed, what is kept). Only the scheme and the host change case; trimming spaces at the ends is the only other change.
ACCEPTED = [
    ("https://example.com", "https://example.com"),
    ("http://example.com", "http://example.com"),
    ("https://example.com/", "https://example.com/"),
    ("HTTPS://EXAMPLE.COM/Path?Q=1#Frag", "https://example.com/Path?Q=1#Frag"),
    ("HtTp://Example.Net:8080/a/B", "http://example.net:8080/a/B"),
    ("  https://example.com/x  ", "https://example.com/x"),
    ("https://portal.example.com/minutes/2026-10-28.pdf", "https://portal.example.com/minutes/2026-10-28.pdf"),
    ("https://example.com/a%20b", "https://example.com/a%20b"),
    ("https://example.com/?a=1&amp;b=2", "https://example.com/?a=1&amp;b=2"),
    ("https://example.com/@user", "https://example.com/@user"),
    ("https://example.com?x=y", "https://example.com?x=y"),
    ("https://example.com#top", "https://example.com#top"),
    ("https://example.com./x", "https://example.com./x"),
    ("https://192.0.2.10/report", "https://192.0.2.10/report"),
    ("https://intranet/plan", "https://intranet/plan"),
    ("https://xn--e1afmkfd.example.com/", "https://xn--e1afmkfd.example.com/"),
    ("https://example.com/caf\u00e9", "https://example.com/caf\u00e9"),
    ("https://example.com:443/", "https://example.com:443/"),
    ("https://a-b.example.com", "https://a-b.example.com"),
    ("https://example.com/path/with(parens)", "https://example.com/path/with(parens)"),
    ("https://example.com/a'b", "https://example.com/a'b"),
    ("https://example.com/%2e%2e/x", "https://example.com/%2e%2e/x"),
    ("https://example.com/javascript:alert(1)", "https://example.com/javascript:alert(1)"),   # a word in the path is only text
    ("https://example.com/?next=https://example.net/", "https://example.com/?next=https://example.net/"),
    ("https://example.org:65535/", "https://example.org:65535/"),
    ("https://example.com/\U0001FAE9", "https://example.com/\U0001FAE9"),            # assigned in newer Unicode only: accepted everywhere
    ("https://example.com/a\U0001FAE8b\U0001FAF7\U0001FAF8", "https://example.com/a\U0001FAE8b\U0001FAF7\U0001FAF8"),
    ("https://example.com/\u0378", "https://example.com/\u0378"),                    # never assigned: accepted
    ("mailto:alice@example.com", "mailto:alice@example.com"),
    ("MAILTO:Alice.Smith+plan@EXAMPLE.COM", "mailto:Alice.Smith+plan@example.com"),
    ("mailto:o'brien@example.net", "mailto:o'brien@example.net"),
    ("  mailto:a@example.org ", "mailto:a@example.org"),
    ("https://example.com/" + "a" * 1980, "https://example.com/" + "a" * 1980),           # exactly 2,000 characters
]

SCHEME_TRICKS = [
    "javascript:alert(1)", "JavaScript:alert(1)", "JAVASCRIPT:alert(1)", "jAvAsCrIpT:alert(1)",
    "java\tscript:alert(1)", "java\nscript:alert(1)", "java\rscript:alert(1)", "java\x00script:alert(1)",
    "java\x0bscript:alert(1)", "java\x0cscript:alert(1)", "java script:alert(1)", "java\u00a0script:alert(1)",
    "java\u200bscript:alert(1)", "java\u2028script:alert(1)", "java\ufeffscript:alert(1)", "javascript\x00:alert(1)",
    "jav&#x09;ascript:alert(1)", "jav&#9;ascript:alert(1)", "&#106;avascript:alert(1)", "&#x6A;avascript:alert(1)",
    "javascript&colon;alert(1)", "javascript&#58;alert(1)", "javas%63ript:alert(1)", "javascript%3Aalert(1)",
    " javascript:alert(1)", "   JAVASCRIPT:alert(1)  ", "\tjavascript:alert(1)", "\njavascript:alert(1)", "\x01javascript:alert(1)",
    "\u200bjavascript:alert(1)", "\u202ejavascript:alert(1)", "javascript://example.com/%0aalert(1)",
    "javascript://example.com", "javascript:/*https://example.com*/alert(1)", "javascript:https://example.com",
    "data:text/html,<script>alert(1)</script>", "data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==",
    "DATA:text/plain,hi", "da\tta:text/plain,hi", "vbscript:msgbox(1)", "VbScript:msgbox(1)", "vb\nscript:msgbox(1)",
    "file:///etc/passwd", "file://example.com/share/x.pdf", "FILE:///C:/x.pdf", "blob:https://example.com/0f8fad5b",
    "BLOB:https://example.com/x", "ftp://example.com/x", "FTP://example.com/x", "ftps://example.com/x",
    "sftp://example.com/x", "ws://example.com/socket", "wss://example.com/socket", "tel:+0000000000", "sms:+0000000000",
    "about:blank", "chrome://settings", "view-source:https://example.com", "intent://example.com#Intent;end",
    "ssh://example.com", "git://example.com/x.git", "gopher://example.com", "news:example.misc", "magnet:?xt=urn:btih:x",
    "x-apple-data-detectors://0", "ms-word:ofe|u|https://example.com/x.docx",
]

LOOKALIKE_SCHEMES = [
    "https2://example.com", "xhttps://example.com", "http+evil://example.com", "http.://example.com", "https-://example.com",
    "\uff48ttps://example.com", "https\uff1a//example.com", "ht\ttps://example.com", "https:\t//example.com",
    "\u0570ttps://example.com", "https://\texample.com", "h\u0442tp://example.com",
]

NOT_ABSOLUTE = [
    "//example.com/x", "///example.com", "//example.com", "/path/only", "./x", "../x", "example.com", "www.example.com",
    "example.com/path", "example.com:8080/x", "localhost:3000", "?q=1", "#frag", "", "   ", "\\\\example.com\\share",
    "\\example.com", "C:\\Users\\x.pdf", "~/x", "mailto", "https", "https:", "http:/", "https:/example.com",
    "https:example.com", "https:\\\\example.com", "https:\\example.com", "http:///example.com", "https://", "https:///",
    "https://:80/", "https://?x", "https://#x", "https://\\example.com", "http:////example.com",
]

CREDENTIALS = [
    "https://user:" "pass@example.com", "https://user@example.com", "https://@example.com", "https://example.com@example.net",
    "https://user:@example.com", "http://admin:" "secret@example.net/x", "https://example.com:" "80@example.net",
    "https://example.com:" "pass@example.net/", "https://user:" "pass@example.com:8080/x", "HTTPS://USER:" "PASS@EXAMPLE.COM",
]

HIDDEN_CHARACTERS = [
    "https://example.com/a b", "https://example.com/\tx", "https://example.com/x\n", "https://exa\nmple.com",
    "https://example.com/\x00", "https://example.com/\x7f", "https://example.com/\x1b[0m", "https://example.com/\u00a0x",
    "https://example.com/\u200b", "https://example.com/\u202eexe.pdf", "https://example.com/\u2028", "https://example.com/\ufeff",
    "https://example.com/%00", "https://example.com/%0d%0aSet-Cookie:x", "https://example.com/%0A", "https://example.com/%1B",
    "https://example.com/%7f", "https://example.com/%7F", "\nhttps://example.com", "https://example.com\n",
    "https://example.com\r\n", "https://example.com\t", "https://example.com/\u3000x", "https://example.com/\u0085",
    "https://example.com/\ud800", "https://example.com/\ue000",
    'https://example.com/"onmouseover=alert(1)', "https://example.com/<script>", "https://example.com/>",
    "https://example.com\\@example.net", "https://example.com\\x", "https://example.com/a\\b",
]

BAD_HOSTS = [
    "https://example..com", "https://.example.com", "https://-example.com", "https://example-.com", "https://exa_mple.com",
    "https://exa mple.com", "https://example.com:abc/", "https://example.com:/", "https://example.com:99999/",
    "https://example.com:65536/", "https://example.com:0/", "https://example.com:-1/", "https://example.com:80:80/",
    "https://[::1]/", "https://[2001:db8::1]:80/", "https://2130706433/", "https://0x7f000001/", "https://0x7f.0.0.1/",
    "https://0177.0.0.1/", "https://127.1/", "https://256.1.1.1/", "https://1.2.3/", "https://1.2.3.4.5/",
    "https://\uff11\uff12\uff17.0.0.1/", "https://ex\u0430mple.com/", "https://ex\u00e4mple.com/",
    "https://example.com\u3002example.net/", "https://example\uff0ecom/", "https://" + "a" * 64 + ".com/",
    "https://" + ".".join(["abcdefghi"] * 30) + "/", "https://%65xample.com/", "https://example.com%2f.example.net/",
    "https://exam!ple.com/", "https://exam,ple.com/", "https://example.com;x/", "https://*.example.com/",
    "https://example.com:8080:/", "https://[example.com]/",
]

TOO_LONG = ["https://example.com/" + "a" * 1981, "https://example.com/" + "a" * 5000, "mailto:" + "a" * 2000 + "@example.com"]

MAILTO = [
    "mailto:", "mailto:a@example.com,b@example.net", "mailto:a@example.com;b@example.net", "mailto:a@example.com?cc=b@example.net",
    "mailto:a@example.com?bcc=b@example.net", "mailto:a@example.com?body=hello", "mailto:a@example.com?subject=hi",
    "mailto:a@example.com?", "mailto:?to=a@example.com", "mailto:a@example.com%2Cb@example.net", "mailto:a%40example.com",
    "mailto:a@example.com#x", "mailto://a@example.com", "mailto:a", "mailto:@example.com", "mailto:a@", "mailto:a@@example.com",
    "mailto:a@b@example.com", "mailto:a b@example.com", "mailto:A <a@example.com>", "mailto:a@example.com b@example.net",
    "mailto:.a@example.com", "mailto:a.@example.com", "mailto:a..b@example.com", "mailto:a@example..com",
    "mailto:a@-example.com", "mailto:a@[127.0.0.1]", 'mailto:"a b"@example.com', "mailto:a@example.com\n",
    "mailto:a@example.com\r\nBcc:x@example.net", "mailto:javascript:alert(1)", "mailto:a@example.com:80", "mailto:'@example.com",
    "MAILTO:A@EXAMPLE.COM,B@EXAMPLE.NET", "mailto:a@example.com&cc=b@example.net", "mailto:a/b@example.com",
]

NOT_TEXT = [None, 5, b"https://example.com", ["https://example.com"], {"url": "https://example.com"}, True]

REFUSED = {
    "scheme": SCHEME_TRICKS, "lookalike scheme": LOOKALIKE_SCHEMES, "not absolute": NOT_ABSOLUTE,
    "credentials": CREDENTIALS, "hidden character": HIDDEN_CHARACTERS, "host": BAD_HOSTS, "length": TOO_LONG, "mailto": MAILTO,
}


class Accepted(unittest.TestCase):
    def test_each_good_link_is_kept_with_only_its_scheme_and_host_lower_cased(self):
        for text, kept in ACCEPTED:
            with self.subTest(text=text[:60]):
                self.assertEqual(check_link(text), kept)

    def test_nothing_changes_but_case_and_the_spaces_at_the_ends(self):
        for text, kept in ACCEPTED:
            with self.subTest(text=text[:60]):
                self.assertEqual(kept.lower(), text.strip(" ").lower())

    def test_the_path_query_and_fragment_keep_their_case(self):
        self.assertEqual(check_link("HTTPS://Example.COM/Mixed/Case?Key=Value#Part"), "https://example.com/Mixed/Case?Key=Value#Part")
        self.assertEqual(check_link("MAILTO:Mixed.Case@Example.COM"), "mailto:Mixed.Case@example.com")

    def test_checking_again_changes_nothing(self):
        for text, _ in ACCEPTED:
            with self.subTest(text=text[:60]):
                once = check_link(text)
                self.assertEqual(check_link(once), once)

    def test_the_longest_link_is_2000_characters(self):
        self.assertEqual(doclinks.MAX_LENGTH, 2000)
        self.assertEqual(len(check_link("https://example.com/" + "a" * 1980)), 2000)
        with self.assertRaises(LinkError):
            check_link("https://example.com/" + "a" * 1981)

    def test_the_length_counts_after_trimming(self):
        self.assertEqual(len(check_link("   https://example.com/" + "a" * 1980 + "   ")), 2000)


class Refused(unittest.TestCase):
    def test_each_hostile_or_unusable_link_is_refused_in_plain_words(self):
        for kind, cases in REFUSED.items():
            for text in cases:
                with self.subTest(kind=kind, text=text[:60]):
                    with self.assertRaises(LinkError) as caught:
                        check_link(text)
                    self.assertTrue(str(caught.exception))
                    self.assertTrue(isinstance(caught.exception, ValueError))

    def test_something_that_is_not_text_is_refused(self):
        for value in NOT_TEXT:
            with self.subTest(value=repr(value)):
                with self.assertRaises(LinkError):
                    check_link(value)

    def test_there_are_enough_cases(self):
        self.assertGreaterEqual(sum(len(c) for c in REFUSED.values()), 60)
        self.assertGreaterEqual(len(ACCEPTED), 25)

    def test_the_messages_are_plain_words(self):
        for name in ("NOT_USABLE", "EMPTY", "TOO_LONG", "HIDDEN", "CREDENTIALS", "NO_SITE", "BAD_SITE", "BAD_PORT", "ONE_EMAIL",
                     "BAD_EMAIL"):
            text = getattr(doclinks, name)
            with self.subTest(name=name):
                self.assertTrue(text.endswith((".", "mailto:")), text)
                self.assertNotIn("port", text.lower())
                for word in ("URL", "URI", "scheme", "href", "payload", "sanitise", "sanitize", "report_hidden", "regex"):
                    self.assertNotIn(word.lower(), text.lower())
        self.assertEqual(doclinks.NOT_USABLE, "That link can't be used. It must start with https://, http:// or mailto:")
        self.assertEqual(doclinks.BAD_PORT, "That link's number after the site name isn't right. Copy the address from the address bar, then paste it again.")
        self.assertEqual(doclinks.BAD_SITE, "That site name can't be used. If it uses another alphabet, "
                         "open the site and copy its address from the address bar.")
        for word in ("punycode", "xn--", "invalid", "null", "!"):
            self.assertNotIn(word, doclinks.BAD_SITE.lower())

    def test_the_main_refusals_say_the_expected_thing(self):
        said = {
            "javascript:alert(1)": doclinks.NOT_USABLE, "data:text/html,x": doclinks.NOT_USABLE, "//example.com/x": doclinks.NOT_USABLE,
            "example.com": doclinks.NOT_USABLE, "ftp://example.com": doclinks.NOT_USABLE, "": doclinks.EMPTY, "   ": doclinks.EMPTY,
            "java\tscript:x": doclinks.HIDDEN, "https://user:" "pass@example.com": doclinks.CREDENTIALS,
            "https:///x": doclinks.NO_SITE, "https://exa_mple.com": doclinks.BAD_SITE, "https://example.com:x/": doclinks.BAD_PORT,
            "https://[::1]/": doclinks.BAD_SITE, "https://[2001:db8::1]:80/": doclinks.BAD_SITE,
            "https://example.com:000080000/": doclinks.BAD_PORT, "https://example.com:0000/": doclinks.BAD_PORT,
            "https://example.com/" + "a" * 1981: doclinks.TOO_LONG, "mailto:a@example.com,b@example.net": doclinks.ONE_EMAIL,
            "mailto:a@example.com?cc=b@example.net": doclinks.ONE_EMAIL, "mailto:nobody": doclinks.BAD_EMAIL,
        }
        for text, message in said.items():
            with self.subTest(text=text[:40]):
                with self.assertRaises(LinkError) as caught:
                    check_link(text)
                self.assertEqual(str(caught.exception), message)

    def test_a_refusal_never_echoes_the_hostile_text(self):
        for kind, cases in REFUSED.items():
            for text in cases:
                with self.subTest(kind=kind, text=text[:40]):
                    with self.assertRaises(LinkError) as caught:
                        check_link(text)
                    self.assertLess(len(str(caught.exception)), 120)
                    if len(text) > 12:
                        self.assertNotIn(text, str(caught.exception))


class Evasion(unittest.TestCase):
    """The same refusals found by building the evasions, not listing them."""

    SEPARATORS = ["\t", "\n", "\r", "\x00", "\x0b", "\x0c", "\x1f", "\x7f", " ", "\u00a0", "\u200b", "\u200d", "\u2028", "\u202e",
                  "\u3000", "\ufeff", "\x85"]

    def test_a_hidden_character_at_any_place_in_a_scheme_is_refused(self):
        for scheme in ("javascript", "data", "vbscript", "file", "blob", "https", "mailto"):
            for place in range(1, len(scheme)):
                for sep in self.SEPARATORS:
                    text = scheme[:place] + sep + scheme[place:] + ":x"
                    with self.subTest(text=repr(text)):
                        with self.assertRaises(LinkError):
                            check_link(text)

    def test_a_hidden_character_before_or_inside_a_good_link_is_refused(self):
        for sep in self.SEPARATORS:
            for text in ("https://example.com/x", "mailto:a@example.com"):
                for place in (0, 1, 3, len(text) - 1, len(text)):
                    bad = text[:place] + sep + text[place:]
                    if sep == " " and place in (0, len(text)):
                        continue                                    # a space at either end is only trimmed
                    with self.subTest(text=repr(bad)):
                        with self.assertRaises(LinkError):
                            check_link(bad)

    def test_every_letter_case_of_a_refused_scheme_is_refused(self):
        rng = random.Random(74)
        for scheme in ("javascript", "data", "vbscript", "file", "blob", "ftp"):
            for _ in range(20):
                cased = "".join(c.upper() if rng.random() < 0.5 else c for c in scheme)
                with self.subTest(scheme=cased):
                    with self.assertRaises(LinkError):
                        check_link(cased + "://example.com/x")
                    with self.assertRaises(LinkError):
                        check_link(cased + ":alert(1)")

    def test_every_letter_case_of_a_good_scheme_is_kept_lower(self):
        rng = random.Random(75)
        for scheme in ("http", "https"):
            for _ in range(20):
                cased = "".join(c.upper() if rng.random() < 0.5 else c for c in scheme)
                self.assertEqual(check_link(cased + "://EXAMPLE.com/Path"), scheme + "://example.com/Path")

    def test_spaces_in_the_ends_are_trimmed_but_not_other_whitespace(self):
        self.assertEqual(check_link(" " * 50 + "https://example.com" + " " * 50), "https://example.com")
        for white in ("\t", "\n", "\r", "\u00a0", "\u3000"):
            with self.subTest(white=repr(white)):
                for text in (white + "https://example.com", "https://example.com" + white):
                    with self.assertRaises(LinkError):
                        check_link(text)

    def test_a_good_link_never_comes_back_with_a_space_or_control_character(self):
        rng = random.Random(76)
        starts = ["https://", "http://", "mailto:", "HTTP://", "//", "javascript:", "", "https:", "MAILTO:"]
        pieces = ["example.com", "EXAMPLE.NET", "a@b.example.org", "/", "?", "#", "%", "%0a", "@", ":", ":80", ".", "-", " ", "\t",
                  "\n", "\\", "<", ">", '"', "x", "\u00e9", "\u202e", ",", ";", "&amp;", "[", "]", "0x7f", "1.2.3.4", "\x00", "/x/y"]
        accepted = 0
        for _ in range(30000):
            text = rng.choice(starts) + "".join(rng.choice(pieces) for _ in range(rng.randint(0, 5)))
            try:
                kept = check_link(text)
            except LinkError:
                continue
            accepted += 1
            self.assertTrue(kept.startswith(("http://", "https://", "mailto:")), text)
            self.assertFalse(any(ord(c) < 33 or ord(c) == 127 for c in kept), repr(text))
            self.assertNotIn("\\", kept)
            self.assertEqual(check_link(kept), kept)
            if not kept.startswith("mailto:"):
                self.assertNotIn("@", kept.split("://", 1)[1].split("/")[0].split("?")[0].split("#")[0])
        self.assertGreater(accepted, 50)                            # the fuzz reached good links, not only refusals


class Port(unittest.TestCase):
    def test_leading_zeros_of_a_port_are_dropped(self):
        for typed, kept in (("https://example.com:08080", "https://example.com:8080"), ("http://example.com:0443/a", "http://example.com:443/a"),
                            ("https://example.com:00001?x=1", "https://example.com:1?x=1"),
                            ("https://example.com:8080", "https://example.com:8080")):
            with self.subTest(typed=typed):
                self.assertEqual(check_link(typed), kept)
                self.assertEqual(check_link(kept), kept)
        self.assertEqual(check_link("https://example.com:08080/"), check_link("https://example.com:8080/"))

    def test_a_port_out_of_range_or_not_a_number_is_refused_with_the_plain_message(self):
        for typed in ("https://example.com:0/", "https://example.com:00000/", "https://example.com:65536/", "https://example.com:099999/",
                      "https://example.com:x/", "https://example.com:/", "https://example.com:-1/", "https://example.com:1_0/"):
            with self.subTest(typed=typed):
                with self.assertRaises(LinkError) as caught:
                    check_link(typed)
                self.assertEqual(str(caught.exception), doclinks.BAD_PORT)

    def test_a_bracketed_address_is_a_site_problem_not_a_number_one(self):
        for typed in ("https://[::1]/", "https://[::1]:80/", "https://[2001:db8::1]/", "https://[example.com]/", "https://[::1"):
            with self.subTest(typed=typed):
                with self.assertRaises(LinkError) as caught:
                    check_link(typed)
                self.assertEqual(str(caught.exception), doclinks.BAD_SITE)

    def test_an_empty_site_name_is_still_no_site(self):
        for typed in ("https://:80/", "https://:abc/", "https:///x"):
            with self.subTest(typed=typed):
                with self.assertRaises(LinkError) as caught:
                    check_link(typed)
                self.assertEqual(str(caught.exception), doclinks.NO_SITE)


class Host(unittest.TestCase):
    def test_the_site_name_of_each_kind_of_link(self):
        cases = [
            ("https://example.com/x", "example.com"), ("HTTPS://Portal.Example.COM:8080/x?y=1#z", "portal.example.com"),
            ("http://example.net", "example.net"), ("https://example.com./x", "example.com"), ("https://192.0.2.10/x", "192.0.2.10"),
            ("mailto:alice@example.org", "example.org"), ("MAILTO:Alice@EXAMPLE.ORG", "example.org"),
            ("  https://example.com/x  ", "example.com"), ("https://www.example.com", "www.example.com"),
        ]
        for url, host in cases:
            with self.subTest(url=url):
                self.assertEqual(link_host(url), host)

    def test_a_link_that_cannot_be_used_has_no_site_name(self):
        for url in ("javascript:alert(1)", "", None, "example.com", "https://user:" "pass@example.com", "mailto:a@example.com?cc=b@example.net"):
            with self.subTest(url=url):
                with self.assertRaises(LinkError):
                    link_host(url)


class Label(unittest.TestCase):
    URL = "https://portal.example.com/minutes/2026-10-28.pdf"

    def test_the_title_is_what_a_person_sees(self):
        self.assertEqual(link_label("Minutes, 28 October", self.URL), "Minutes, 28 October")

    def test_a_blank_title_shows_the_site_name_and_never_the_whole_address(self):
        for title in ("", "   ", None, "\t\n", "\u200b", "\u00a0", "\u202e"):
            with self.subTest(title=repr(title)):
                self.assertEqual(link_label(title, self.URL), "portal.example.com")
        self.assertEqual(link_label("", "mailto:alice@example.org"), "example.org")

    def test_the_address_is_never_the_label(self):
        urls = [self.URL, "https://example.com/?next=https://example.net/", "mailto:a@example.com", "HTTP://EXAMPLE.COM:8080/x"]
        for url in urls:
            for title in ("", " ", "Plan", "Plan v2", "Report"):
                with self.subTest(url=url, title=title):
                    label = link_label(title, url)
                    self.assertNotIn("://", label)
                    self.assertNotIn("mailto:", label)
                    self.assertNotEqual(label, check_link(url))
                    self.assertNotEqual(label, url)

    def test_a_title_that_says_something_different_is_not_replaced_by_the_address(self):
        self.assertEqual(link_label("Weekly plan", "https://example.net/a"), "Weekly plan")
        self.assertNotIn("example.net", link_label("Weekly plan", "https://example.net/a"))

    def test_runs_of_spaces_and_line_breaks_become_one_space(self):
        self.assertEqual(link_label("  Weekly   plan \n v2\t", self.URL), "Weekly plan v2")

    def test_hidden_characters_are_dropped(self):
        self.assertEqual(link_label("Plan\u202e fdp.", self.URL), "Plan fdp.")
        self.assertEqual(link_label("Pl\u200ban\ufeff", self.URL), "Plan")
        self.assertEqual(link_label("A\x00B\x1bC", self.URL), "A B C")
        self.assertEqual(link_label("A\u2028B\u3000C", self.URL), "A B C")

    def test_markup_stays_as_the_text_it_is(self):
        self.assertEqual(link_label("<b>x</b>", self.URL), "<b>x</b>")
        self.assertEqual(link_label("a & b <script>", self.URL), "a & b <script>")

    def test_accents_and_emoji_are_kept(self):
        self.assertEqual(link_label("Rapport d'avancement \u00e9t\u00e9", self.URL), "Rapport d'avancement \u00e9t\u00e9")
        self.assertEqual(link_label("Plan \U0001F468\u200d\U0001F469", self.URL), "Plan \U0001F468\U0001F469")

    def test_a_non_text_title_is_shown_as_text_or_as_blank(self):
        self.assertEqual(link_label(5, self.URL), "5")
        self.assertEqual(link_label(0, self.URL), "portal.example.com")

    def test_a_link_that_cannot_be_used_has_no_label(self):
        for url in ("javascript:alert(1)", "", "example.com"):
            with self.subTest(url=url):
                with self.assertRaises(LinkError):
                    link_label("Plan", url)

    def test_the_rule_is_in_the_docstring(self):
        text = link_label.__doc__
        for phrase in ("the title, or the site name when the title is blank", "never the whole address"):
            self.assertIn(phrase, text)


class OtherPlace(unittest.TestCase):
    """True when the title names an address for a different place from the link's."""

    CASES = [
        # (title, url, looks like another place)
        ("portal.example.com", "https://evil.example.net/login", True),
        ("portal.example.com", "https://portal.example.com/x", False),
        ("PORTAL.Example.COM", "https://portal.example.com/x", False),
        ("https://portal.example.com/minutes", "https://evil.example.net/", True),
        ("https://portal.example.com/minutes", "https://portal.example.com/other", False),
        ("http://portal.example.com", "https://portal.example.com/", False),
        ("www.example.com", "https://example.com/", False),
        ("example.com", "https://www.example.com/", False),
        ("www.example.com", "https://evil.example.net/", True),
        ("example.com", "https://portal.example.com/", False),                  # a page inside the named site
        ("portal.example.com", "https://example.com/", True),                   # the named place is narrower than the link
        ("example.com", "https://example.com.example.net/", True),              # the named site only at the front
        ("example.com", "https://notexample.com/", True),
        ("example.com", "https://example.com.evil.example.net/", True),
        ("example.com", "https://evil-example.com/", True),
        ("example.com", "https://example.com:8080/x", False),
        ("example.com:8080", "https://example.com/x", False),
        ("Sign in at portal.example.com now", "https://evil.example.net/", True),
        ("Sign in at portal.example.com now", "https://portal.example.com/", False),
        ("Sign in at portal.example.com.", "https://portal.example.com/", False),
        ("(portal.example.com)", "https://evil.example.net/", True),
        ("portal.example.com/login", "https://evil.example.net/", True),
        ("portal.example.com?x=1", "https://evil.example.net/", True),
        ("https://user:" "pw@portal.example.com/", "https://evil.example.net/", True),
        ("https://example.com", "https://evil.example.net/", True),
        ("https://example.com and https://example.net", "https://example.com/", True),
        ("https://example.com and https://example.com/x", "https://example.com/", False),
        ("javascript://example.com", "https://example.com/", False),
        ("example.com and example.net", "https://example.com/", True),
        ("portal\uff0eexample\uff0ecom", "https://evil.example.net/", True),    # full-width dots
        ("portal\u3002example\u3002com", "https://evil.example.net/", True),
        ("\uff50ortal.example.com", "https://portal.example.com/", False),     # full-width p reads as p
        ("p\u043ertal.example.com", "https://portal.example.com/", True),      # a Cyrillic o is another place
        ("portal.ex\u0430mple.com", "https://portal.example.com/", True),
        ("portal.example.com\u202e", "https://portal.example.com/", False),
        ("portal.exa\u200bmple.com", "https://portal.example.com/", False),
        ("192.0.2.10", "https://198.51.100.7/", True),
        ("192.0.2.10", "https://192.0.2.10/x", False),
        ("Go to 192.0.2.10", "https://example.com/", True),
        ("alice@example.com", "mailto:alice@example.com", False),
        ("Alice@Example.com", "mailto:alice@example.com", False),
        ("alice@example.com", "mailto:mallory@example.com", True),
        ("alice@example.com", "mailto:alice@example.net", True),
        ("alice@example.com", "https://example.com/team", False),
        ("alice@example.com", "https://example.net/team", True),
        ("example.com", "mailto:alice@example.com", False),
        ("example.com", "mailto:alice@example.net", True),
        ("Email alice@example.com", "mailto:alice@example.com", False),
        ("a.bc@example.com", "mailto:a.bc@example.com", False),
        ("a.bc@example.com", "https://evil.example.net/", True),
        ("Weekly plan", "https://example.com/", False),
        ("Minutes, 28 October", "https://example.com/", False),
        ("", "https://example.com/", False),
        ("   ", "https://example.com/", False),
        (None, "https://example.com/", False),
        ("Report v1.2", "https://example.com/", False),
        ("Version 1.2.3", "https://example.com/", False),
        ("Q3 results (draft).", "https://example.com/", False),
        ("e.g. the plan", "https://example.com/", False),
        ("minutes.pdf", "https://example.com/", False),
        ("Minutes 28-10-2026.docx", "https://example.com/", False),
        ("budget.xlsx", "https://example.com/", False),
        ("<b>x</b>", "https://example.com/", False),
        ("x.y", "https://example.com/", False),                                 # a one-letter ending is not a site
        ("Plan / actions", "https://example.com/", False),
        ("a--b", "https://example.com/", False),
        ("evil.zip", "https://example.com/", True),                             # .zip is a site ending, so it counts
        ("A very long plain title " * 5, "https://example.com/", False),
    ]

    def test_each_title_against_each_link(self):
        for title, url, expected in self.CASES:
            with self.subTest(title=title, url=url):
                self.assertIs(looks_like_other_place(title, url), expected)

    def test_there_are_enough_cases(self):
        self.assertGreaterEqual(len(self.CASES), 60)

    def test_a_link_that_cannot_be_used_raises(self):
        for url in ("javascript:alert(1)", "", "example.com", "https://user:" "pass@example.com"):
            with self.subTest(url=url):
                with self.assertRaises(LinkError):
                    looks_like_other_place("portal.example.com", url)

    def test_the_answer_does_not_depend_on_the_address_case_or_trimming(self):
        for title, url, expected in self.CASES:
            scheme, rest = url.split(":", 1)
            host, slash, tail = rest[2:].partition("/") if scheme != "mailto" else (rest, "", "")
            typed = "  " + scheme.upper() + ":" + ("//" if scheme != "mailto" else "") + host.upper() + slash + tail + " "
            with self.subTest(title=title, url=typed):
                self.assertIs(looks_like_other_place(title, typed), expected)

    def test_it_agrees_with_the_label_rule_a_title_naming_the_site_needs_no_warning(self):
        url = "https://portal.example.com/x"
        host = link_host(url)
        self.assertEqual(link_label("", url), host)
        self.assertFalse(looks_like_other_place(link_label("", url), url))     # the site name used as a label is its own place


# Characters assigned in a newer Unicode than an older Python knows (Unicode 13 in Python 3.9, 17 in the newest): the answer
# must be the same on every Python, and for a character that isn't a control, format, separator, surrogate or private-use one it is "fine".
NEWER_CHARACTERS = ["\U0001FAE9", "\U0001FAE8", "\U0001FAF7", "\U0001FAF8", "\U0001FAC6", "\U0001FADC", "\U0001FADB", "\u0378"]

# Every code point in the planes where Unicode has assigned characters, and the ends of the private-use planes.
SWEEP = (list(range(0x0, 0x32000)) + list(range(0xE0000, 0xE1000)) + list(range(0xF0000, 0xF0010)) + list(range(0xFFFF0, 0x100010))
         + list(range(0x10FFF0, 0x110000)))

THIS_FILE_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")

# Runs in each interpreter: reads the texts on stdin, answers with what the rule says. It imports nothing but clark.doclinks.
CHILD = r"""
import json, sys
sys.path.insert(0, sys.argv[1])
from clark.doclinks import LinkError, check_link, link_label, looks_like_other_place
data = json.load(sys.stdin)
def outcome(f, *args):
    try:
        return ["ok", f(*args)]
    except LinkError as e:
        return ["refused", str(e)]
out = {"check": [outcome(check_link, t) for t in data["links"]],
       "label": [outcome(link_label, t, u) for t, u in data["labels"]],
       "other": [outcome(looks_like_other_place, t, u) for t, u in data["others"]]}
out["sweep_link"] = "".join("1" if outcome(check_link, "https://example.com/a" + chr(i) + "b")[0] == "ok" else "0"
                            for i in data["sweep"])
out["sweep_label"] = "".join("1" if link_label("a" + chr(i) + "b", "https://example.com/") == "a" + chr(i) + "b" else "0"
                             for i in data["sweep"])
out["sweep_place"] = "".join("1" if looks_like_other_place("example" + chr(i) + ".com", "https://example.com/") else "0"
                             for i in data["sweep"])
print(json.dumps(out))
"""


def _every_case():
    links = [text for text, _ in ACCEPTED] + [text for cases in REFUSED.values() for text in cases if isinstance(text, str)]
    links += ["https://example.com/" + c for c in NEWER_CHARACTERS] + ["https://example.com:08080/", "https://[::1]/"]
    others = [(t, u) for t, u, _ in OtherPlace.CASES if isinstance(t, str) or t is None]
    others += [("example" + c + ".com", "https://example.com/") for c in NEWER_CHARACTERS]
    labels = [(t, "https://example.com/") for t in ("Plan", "  A  B ", "A\u200bB", "A\u202eB") + tuple("Plan " + c for c in NEWER_CHARACTERS)]
    return {"links": links, "labels": labels, "others": others, "sweep": SWEEP}


class SameOnEveryPython(unittest.TestCase):
    """The rule never reads a Python's own Unicode table, so an old and a new Python agree on every character."""

    def test_a_character_assigned_only_in_newer_Unicode_is_accepted_in_a_path(self):
        for c in NEWER_CHARACTERS:
            for url in ("https://example.com/" + c, "https://example.com/a" + c + "b?q=" + c + "#" + c):
                with self.subTest(character=hex(ord(c)), url=url):
                    self.assertEqual(check_link(url), url)

    def test_it_is_accepted_in_a_label_and_the_title_keeps_it(self):
        for c in NEWER_CHARACTERS:
            with self.subTest(character=hex(ord(c))):
                self.assertEqual(link_label("Plan " + c, "https://example.com/"), "Plan " + c)
                self.assertFalse(looks_like_other_place("Plan " + c, "https://example.com/"))

    def test_only_the_listed_kinds_of_character_are_refused(self):
        import unicodedata                              # here only, to check the fixed lists against this Python's table
        for i in SWEEP:
            c = chr(i)
            kind = unicodedata.category(c)
            hidden = doclinks._hidden_character(c)
            if kind in ("Cc", "Zs", "Zl", "Zp", "Cs", "Co", "Cf"):
                self.assertTrue(hidden, hex(i))
            elif kind == "Cn":                  # unassigned here: refused only if it is a newer format character in the fixed list
                self.assertEqual(hidden, doclinks._in(c, doclinks._FORMAT), hex(i))
            else:
                self.assertFalse(hidden, hex(i))

    def test_unassigned_characters_are_not_refused_unless_in_the_fixed_format_list(self):
        for i in (0x378, 0x379, 0x1FAE9, 0xFFFE, 0xFFFF, 0x2FFFE, 0xE0080, 0x3FFFF):
            c = chr(i)
            with self.subTest(code_point=hex(i)):
                self.assertFalse(doclinks._hidden_character(c))
                self.assertEqual(check_link("https://example.com/" + c), "https://example.com/" + c)
        for i in (0x890, 0x891, 0x13439, 0x1343F):              # format characters, new in later Unicode: refused on every Python
            with self.subTest(code_point=hex(i)):
                self.assertTrue(doclinks._hidden_character(chr(i)))
                with self.assertRaises(LinkError):
                    check_link("https://example.com/" + chr(i))

    def test_the_module_does_not_use_the_unicode_tables(self):
        self.assertFalse(hasattr(doclinks, "unicodedata"))
        with open(doclinks.__file__, encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        used = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
        imported = {alias.name for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom)) for alias in node.names}
        self.assertEqual(imported, {"re"})
        for name in ("normalize", "category", "name", "isalpha", "isalnum", "isidentifier", "isdecimal", "isnumeric", "casefold"):
            self.assertNotIn(name, used)

    def test_the_interpreters_found_here_give_the_same_answers(self):
        # This Python, and /usr/bin/python3 when this machine has one (not Windows, nor some Linux images) and it is not the same file.
        found = [sys.executable]
        if os.path.exists("/usr/bin/python3") and not os.path.samefile("/usr/bin/python3", sys.executable):
            found.append("/usr/bin/python3")
        payload = json.dumps(_every_case())
        answers = {}
        for exe in found:
            done = subprocess.run([exe, "-I", "-c", CHILD, THIS_FILE_SRC], input=payload, capture_output=True, encoding="utf-8",
                                  timeout=600)
            self.assertEqual(done.returncode, 0, exe + ": " + done.stderr[-500:])      # an unusable interpreter fails, never skips
            answers[exe] = json.loads(done.stdout)
        first = answers[found[0]]
        for exe in found[1:]:
            second = answers[exe]
            for part in first:
                if part.startswith("sweep"):
                    differ = [hex(i) for i, (a, b) in enumerate(zip(first[part], second[part])) if a != b][:10]
                    self.assertEqual(differ, [], exe + " " + part)
                else:
                    self.assertEqual(first[part], second[part], exe + " " + part)
        self.assertGreater(len(first["check"]), 250)
        # and what they agree on is what this Python says
        here = [_outcome(check_link, t) for t in _every_case()["links"]]
        self.assertEqual(first["check"], here)


def _outcome(f, *args):
    try:
        return ["ok", f(*args)]
    except LinkError as error:
        return ["refused", str(error)]


if __name__ == "__main__":
    unittest.main()
