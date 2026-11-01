"""#215: text read from a saved folder is screened for secrets before it is sent.

Run: python3 dev/run_tests.py test_secret_screen
Every fake secret is built from pieces at run time, so this file holds nothing a secrets scan would find.
"""
import json
import logging
import re
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401

import test_ask_passages as tp
import test_ask_route as tr
import test_docx_read as tdx
from clark import ask, ask_passages, ask_service, secret_screen, store as st
from _growth import assert_growth

PW = "Hunt" + "er2-Zq-99x"
FAMILIES = {
    "private key": "-----BEGIN " + "RSA PRIVATE KEY-----\nMIIE" + "A" * 40 + "\n-----END " + "RSA PRIVATE KEY-----",
    "aws key": "id AK" + "IAIOSFODNN7EXAMPLE here",
    "github token": "use gh" + "p_" + "A1b2C3d4" * 5,
    "slack token": "xo" + "xb-" + "1234567890-abcdefghij",
    "bearer header": "Authorization: " + "Bear" + "er " + "abcDEF123456" * 3,
    "web token": "ey" + "J" + "a" * 12 + ".ey" + "J" + "b" * 12 + "." + "c" * 12,
    "api key": "sk-" + "ant-" + "a1B2c3D4e5F6",
    "address with password": "postgres://admin:" + PW + "@db.example.org/main",
    "password line": "pass" + "word = " + PW,
    "secret line": "client_" + "secret: " + "a1b2c3d4e5f6a7b8",
    "env line": "DB_PASS" + "WORD=" + PW,
    "env key line": "AWS_SECRET" + "_ACCESS_KEY=" + "wJalr" + "XUtnFEMI9K7MDENG",
    "stripe live key": "sk_" + "live_" + "A1b2C3d4E5f6G7h8",
    "google api key": "AI" + "za" + "SyA1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6",
    "npm token": "npm" + "_" + "A1b2C3d4E5f6G7h8I9j0K1l2",
    "npm auth line": "//registry.example.org/:_auth" + "Token=" + "A1b2C3d4E5f6G7h8I9j0",
    "pypi token": "py" + "pi-" + "A1b2C3d4E5f6G7h8I9j0K1l2",
    "prefixed quoted key": "DB_PASS" + 'WORD="' + "Welcome" + '2026!"',
    "exported quoted key": "export ADMIN_P" + "WD='" + "Welcome" + "2026!'",
    "json password": '{"db_pass' + 'word": "' + "Welcome" + '2026!"}',
    "json short api key": '"api_' + 'key": "a1b2c3d4e5f6"',
    "word table row": "Pass" + "word | " + "Welcome" + "2026!",
    "word table row with colon": "Pass" + "word: | " + "Welcome" + "2026!",
    "csv columns": "user,pass" + "word\nmail," + "Welcome" + "2026!",
    "tsv columns": "user\tpass" + "word\nmail\t" + "Welcome" + "2026!",
    "zero-width in the key": "DB_PASS\u200b" + "WORD=" + PW,
    "look-alike letter in the key": "DB_PASS" + "W\u039fRD=" + PW,
    "prose password": "The wifi pass" + "word is " + "Sunshine" + "2026",
    "prose pw": "the p" + "w is " + "Zk4" + "mQ9xLw2",
    "prose was": "the pass" + "code was " + "Blue" + "7Harbour",
    "pass key": "pa" + "ss=" + PW,
    "pw key": "p" + "w: " + PW,
    "creds key": "cre" + "ds: " + PW,
    "credentials key": "credent" + "ials = " + PW,
    "pin key": "PIN: " + "4829" + "15ab",
    "ssh key name": "ssh_private" + "_key=" + "A1b2C3d4E5f6G7h8I9j0K1l2",
    "pass header table": "user,p" + "w\nmail," + "Welcome" + "2026!",
    "quoted passphrase with spaces": "pass" + 'word = "correct horse 9 battery"',
    "long token near a word": "the api " + "key is " + "Xk9" + "Qm2Lp7" * 5 + "Zt4Rw8Vb1Nc",
}

class Screen(unittest.TestCase):
    def test_each_family_is_caught(self):
        for name, text in FAMILIES.items():
            with self.subTest(name):
                self.assertTrue(secret_screen.looks_like_secret("Notes before.\n" + text + "\nNotes after."))

    def test_ordinary_technical_text_is_not(self):
        text = "\n".join((
            "Release 2.5.1 ships on Friday; run git commit -m fix and open https://example.org/docs/plan?page=2.",
            "The token: 2026 plan covers three workstreams. The password policy is reviewed each year.",
            "Set the ticket id to ABC-A-003 and the build to 20261031-final-report-v2.",
            "Uses AES and SHA256 for the file checks; the key owner is the security lead.",
        ))
        self.assertFalse(secret_screen.looks_like_secret(text))

    def test_a_break_inside_the_secret_does_not_hide_it(self):
        token = "gh" + "p_" + "A1b2C3d4" * 5
        self.assertTrue(secret_screen.looks_like_secret(token[:20] + "\n" + token[20:]))
        short = "gh" + "p_" + "A1b2C3d4" * 3
        self.assertFalse(secret_screen.looks_like_secret(short[:8]))                 # neither piece alone is a key
        self.assertFalse(secret_screen.looks_like_secret(short[8:]))
        self.assertTrue(secret_screen.looks_like_secret(short[:8] + "\n" + short[8:]))      # only the joined text is
        self.assertTrue(secret_screen.looks_like_secret("pass" + "word:\r\n" + PW))

    def test_not_text_counts_as_a_hit(self):
        self.assertTrue(secret_screen.looks_like_secret(b"bytes"))

    def test_the_lists_are_the_publish_scans(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "dev" / "tools"))
        try:
            import publish_public as pp
        finally:
            sys.path.pop(0)
        self.assertEqual([(k, rx.pattern.decode()) for k, rx in pp.SECRET_PATTERNS], list(secret_screen.SECRET_PATTERNS))
        self.assertEqual(pp.GENERIC_SECRET.pattern.decode(), secret_screen.GENERIC_SECRET)       # kept as the publish scan's; this
        self.assertEqual(pp.UNQUOTED_SECRET.pattern.decode(), secret_screen.UNQUOTED_SECRET)     # screen reads the wider local forms
        self.assertEqual(pp.BASE64_RUN.pattern.decode(), secret_screen.BASE64_RUN)

    def test_base64_hidden_key_is_caught(self):
        import base64
        text = "data: " + base64.b64encode(("-----BEGIN " + "PRIVATE KEY-----").encode()).decode()
        self.assertTrue(secret_screen.looks_like_secret(text))

    # The old check was a wall-clock limit (VERY_LARGE_OLD_LIMIT, 30 s, for the full-size texts); a loaded runner took 74.6 s. It is now the
    # growth from n to 4n in CPU time, with the same ten shapes at n tenths of the old size. Kept as documentation, no longer asserted.
    VERY_LARGE_OLD_LIMIT = 30

    def test_a_very_large_text_is_screened_quickly(self):
        def work(tenths):
            for text in ("a" * (100_000 * tenths), ("word " * (20_000 * tenths)), "x1" * (50_000 * tenths),
                         "password=" + "a" * (90_000 * tenths), "-----BEGIN " * (8_000 * tenths), ("A1" * 40 + " ") * (1_200 * tenths),
                         "a://" * (25_000 * tenths), "http://" + "a" * (100_000 * tenths), "x://a:" + "b" * (100_000 * tenths),
                         "authorization: " + " " * (100_000 * tenths)):
                secret_screen.looks_like_secret(text)
        assert_growth(self, work, 1, "very large text")

    def test_a_run_of_key_words_takes_time_that_grows_with_the_size(self):
        # The old check was wall-clock: eight times the text had to take under 24 times as long (or 2 s), and 200,000 words under 30 s.
        # It is now the growth from n to 4n in CPU time, over 16,000 to 400,000 words.
        for n in (16000, 100000):
            assert_growth(self, lambda size: secret_screen.looks_like_secret("token" * size), n, "key words %d" % n)

    def test_many_ordinary_long_runs_are_not_a_secret(self):
        import uuid
        self.assertFalse(secret_screen.looks_like_secret("\n".join(str(uuid.UUID(int=i * 7919 + 12345678901234567890)) for i in range(5000))))

    def test_ordinary_text_that_looks_a_little_like_a_key_is_not(self):
        for text in ("https://docs.google.com/document/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit",
                     "getProjectMilestoneSummaryForReport2026V2", "Token: 2026-11-01", "The secret is good-quality data.",
                     "![x](data:image/png;base64," + "iVBORw0KGgo" * 40 + ")", "user,name\nmail,bob",
                     "Password,Owner,Date\nreset,Sam,01-11-2026"):
            with self.subTest(text[:30]):
                self.assertFalse(secret_screen.looks_like_secret(text))

    def test_harmless_prose_about_a_password_is_not_a_secret(self):
        for text in ("the password is required", "the password was reset yesterday", "The secret is good-quality data.",
                     "The pin is loose and the pass is closed.", "the credentials are stored safely", "password is Required."):
            with self.subTest(text):
                self.assertFalse(secret_screen.looks_like_secret(text))

    def test_a_letters_only_quoted_password_is_refused(self):
        word = "orange" + "bicycle"
        for q1, q2 in (('"', '"'), ("'", "'"), ("`", "`"), ("\u201c", "\u201d"), ("\u2018", "\u2019")):
            for lead in ("password: ", "pwd=", "passphrase: ", "secret: ", "pw = ", "the password is ", "The wifi password was ", "password "):
                with self.subTest(lead + q1):
                    self.assertTrue(secret_screen.looks_like_secret(lead + q1 + word + q2))
        self.assertTrue(secret_screen.looks_like_secret("Notes.\nPassword: \"" + "swordfish" + "\" (shared)"))

    def test_a_short_or_unquoted_word_after_a_password_word_is_not_refused(self):
        for text in ('password "ok"', 'the password "must" be long', "password: reset", "the password policy is reviewed each year",
                     'the token "refresh" is renewed', 'a "required" field', 'pass `revert` to the call', 'password: "two words here"'):
            with self.subTest(text):
                self.assertFalse(secret_screen.looks_like_secret(text))

    def test_near_misses_of_the_quoted_letters_rule_pass(self):
        """The key word must start a word, a bare secret needs a connector, the two quotes must be one pair, and a config's own
        placeholder values are not passwords."""
        for text in ('password "abcde"', "Secretary 'Harrington'", 'secrets: "inherit"', 'the secret "ingredient"', 'password: "string"',
                     'click "Forgot password" "Submit"', "the password is 'orangebicycle\"", 'secret "orangebicycle"'):
            with self.subTest(text):
                self.assertFalse(secret_screen.looks_like_secret(text))

    def test_a_prefixed_or_suffixed_key_word_with_a_quoted_letters_value_is_refused(self):
        """The commonest config shapes: a prefix such as DB_ or client_, camel case, and a suffix that still names the secret."""
        word = "orange" + "bicycle"
        for key in ("DB_PASSWORD=", "client_secret: ", "db_password: ", "userPassword: ", "mysql_pwd=", "admin_pw: ", "api_secret=",
                    "secret_key: ", "clientSecret = ", "DB_PASSWORD_PROD=", "password_new: ", '"db_password": '):
            with self.subTest(key):
                self.assertTrue(secret_screen.looks_like_secret(key + '"' + word + '"'))
                self.assertTrue(secret_screen.looks_like_secret(key + "'" + word + "'"))

    def test_the_false_refusals_of_ordinary_text_pass(self):
        """A word that only starts with a key word, a setting about a secret, a heading, and another language's word are not secrets."""
        for text in ("Secretary 'Clinton' arrived", 'the secret "ingredient"', 'password: "string"', 'secretName: "postgres"', 'secrets: "inherit"',
                     'secreto "abierto"', 'password_auth: "enabled"', 'Subject: Password "Expired"', 'password_hint: "favourite"',
                     'passwords: "abcdefgh"', 'secretary: "Harrington"'):
            with self.subTest(text):
                self.assertFalse(secret_screen.looks_like_secret(text))

    def test_a_bare_password_word_and_a_quoted_word_on_the_next_line_are_not_joined_into_a_hit(self):
        """The text is also read with its line breaks taken out. A password word at the end of a line and a quoted word that
        starts the next one are two lines of ordinary text; a key word cut in two by a break, and a connector, are still caught."""
        word = "orange" + "bicycle"
        for text in ('Forgot password \n"Continue"', 'Enter your password \r\n"Continue" to go on', 'Reset the password \n\n`Confirm`'):
            with self.subTest(text):
                self.assertFalse(secret_screen.looks_like_secret(text))
        for text in ('pass\nword "%s"' % word, 'pass\nword \n"%s"' % word, 'pass\r\nword: "%s"' % word,
                     'password:\n"%s"' % word, 'the password is\n"%s"' % word, "the secret =\n'%s'" % word):
            with self.subTest(text):
                self.assertTrue(secret_screen.looks_like_secret(text))

    ORDINARY = ("Secretary 'Clinton' arrived", 'the secret "ingredient"', 'password: "string"', 'click "Forgot password" "Submit"',
                'Forgot password \n"Continue"', "the password policy is reviewed each year")
    REFUSED = ('password: "Sunshine"', 'password is "orangebicycle"', 'DB_PASSWORD="orangebicycle"', 'client_secret: "abcdefgh"',
               'pass\nword "orangebicycle"', "pass" + "word=" + PW, 'password is "contrase\u00f1a"')

    def test_base64_text_gets_the_same_checks_as_plain_text_both_ways(self):
        """Ordinary text passes in base64 as it does plain, and each text that is refused plain is refused in base64: on its own, with
        text around it, with its padding left off, inside two layers of base64, and with its characters %-escaped."""
        import base64
        import urllib.parse

        def b64(text):
            return base64.b64encode(text.encode()).decode()
        for text in self.ORDINARY:
            with self.subTest("ordinary " + text):
                self.assertFalse(secret_screen.looks_like_secret(text))
                self.assertFalse(secret_screen.looks_like_secret(b64(text)))
                self.assertFalse(secret_screen.looks_like_secret("Notes.\n" + b64("so we know " + text + " in full") + "\n(more notes)"))
        for text in self.REFUSED:
            with self.subTest("refused " + text):
                self.assertTrue(secret_screen.looks_like_secret(text))
                self.assertTrue(secret_screen.looks_like_secret(b64(text)))
                self.assertTrue(secret_screen.looks_like_secret("Notes.\n" + b64("so we know " + text + " in full") + "\n(more notes)"))
                self.assertTrue(secret_screen.looks_like_secret(b64(b64(text))))
                self.assertTrue(secret_screen.looks_like_secret(b64("so we know " + urllib.parse.quote(text, safe="") + " in full")))
        self.assertTrue(secret_screen.looks_like_secret(b64('password: "Sunshine"').rstrip("=")))

    def test_a_base64_run_that_ends_mid_group_is_still_read_to_its_end(self):
        """A run stops at "=", so its last group may be short; the last characters hold the quoted word's closing quote."""
        import base64
        for tail in ("", " ", "  "):                             # one, none and two characters of padding
            encoded = base64.b64encode(('password: "Sunshine"' + tail).encode()).decode()
            with self.subTest(tail=len(tail)):
                self.assertTrue(secret_screen.looks_like_secret(encoded.rstrip("=")))
                self.assertTrue(secret_screen.looks_like_secret(encoded))

    def test_base64_of_a_key_word_cut_by_a_break_and_of_a_heading_line_follow_the_plain_rules(self):
        import base64
        self.assertTrue(secret_screen.looks_like_secret(base64.b64encode(b'a note.\npass\nword "orangebicycle"').decode()))
        self.assertFalse(secret_screen.looks_like_secret(base64.b64encode(b'Forgot password \n"Continue" to go on').decode()))

    def test_base64_inside_base64_is_read_a_few_levels_down_and_refused_past_that(self):
        import base64
        text = 'password: "Sunshine"'
        for levels in range(1, secret_screen.MAX_DEPTH + 1):
            text_n = text
            for _ in range(levels):
                text_n = base64.b64encode(text_n.encode()).decode()
            with self.subTest(levels=levels):
                self.assertTrue(secret_screen.looks_like_secret(text_n))
        deep = "so we know the weather is fine today"
        for _ in range(secret_screen.MAX_DEPTH + 2):
            deep = base64.b64encode(deep.encode()).decode()
        self.assertTrue(secret_screen.looks_like_secret(deep))                              # too deep to read: left out

    def test_a_letters_only_value_in_another_alphabet_of_letters_is_refused(self):
        self.assertTrue(secret_screen.looks_like_secret('password is "contrase\u00f1a"'))

    def test_six_letters_are_refused_and_five_are_not(self):
        self.assertTrue(secret_screen.looks_like_secret('password "abcdef"'))
        self.assertFalse(secret_screen.looks_like_secret('password "abcde"'))
        self.assertTrue(secret_screen.looks_like_secret('the secret is "orangebicycle"'))
        self.assertTrue(secret_screen.looks_like_secret('"password": "orangebicycle"'))

    def test_the_address_shape_still_finds_an_address(self):
        self.assertTrue(secret_screen.looks_like_secret("see s3://user:" + PW + "@host/x"))

    def test_encoded_and_other_language_forms_are_caught(self):
        import base64
        import urllib.parse
        line = "pass" + "word=" + PW
        for name, text in (("base64", base64.b64encode(line.encode()).decode()),
                           ("url-encoded", "q=" + urllib.parse.quote(line, safe="")),
                           ("url-encoded and quoted", urllib.parse.quote("pass" + 'word: "' + PW + '"', safe="")),
                           ("German", "Pass" + "wort: " + PW), ("German quoted", "Kenn" + 'wort = "' + PW + '"'),
                           ("French", "mot de " + "passe : " + PW), ("Spanish", "contra" + "seña: " + PW),
                           ("Russian", "пар" + "оль: " + PW), ("Arabic", "كلمة " + "المرور: " + PW),
                           ("short secret key", "SECRET" + "_KEY=" + "ab12cd34ef56gh7")):
            with self.subTest(name):
                self.assertTrue(secret_screen.looks_like_secret("Notes.\n" + text + "\n(more notes)"))

    def test_a_secret_in_a_file_name_is_caught(self):
        for name in ("notes-pass" + "word-" + PW.replace("-", "") + ".txt", "pass" + "word=" + PW + ".md"):
            with self.subTest(name):
                self.assertTrue(secret_screen.name_looks_like_secret("saved/" + name))
        for name in ("pass" + "word-reset-2026.docx", "Q4 plan v2.docx", "token_policy.md", "secret santa list.txt"):
            with self.subTest(name):
                self.assertFalse(secret_screen.name_looks_like_secret("saved/" + name))

    def test_forms_not_screened_on_purpose_stay_clean(self):
        for text in ("The token: 2026 plan covers three workstreams.", "Mot de " + "passe oublié ? Cliquez ici.",
                     "100% done, 50%25 left", "token: ab12cd34 ef56gh78", "secret: ab12cd"):
            with self.subTest(text):
                self.assertFalse(secret_screen.looks_like_secret(text))


class FromFolders(tp.Folders):
    def test_each_family_in_a_file_is_left_out_whole_and_counted(self):
        for i, (name, text) in enumerate(FAMILIES.items()):
            self.put(self.box, f"f{i}.txt", "ZQ-PLAN the plan is fine\n" + text)
        self.put(self.box, "ok.txt", "ZQ-OK the plan is fine")
        got = self.run_it()
        self.assertEqual(self.labels(got), ["saved/ok.txt"])
        self.assertEqual(got.safety, len(FAMILIES))
        self.assertEqual(len(got.secret_labels), len(FAMILIES))
        self.assertNotIn("ZQ-PLAN", self.text_of(got))                      # the whole file, not just the line

    def test_a_secret_in_a_word_file_is_left_out(self):
        self.put(self.box, "w.docx", tdx.docx(tdx.P("ZQ-WORD budget") + tdx.P("pass" + "word: " + PW)), binary=True)
        self.put(self.box, "split.docx", tdx.docx(tdx.P("gh" + "p_" + "A1b2C3d4" * 2) + tdx.P("A1b2C3d4" * 3)), binary=True)
        got = self.run_it()
        self.assertEqual(got.passages, ())
        self.assertEqual(sorted(got.secret_labels), ["saved/split.docx", "saved/w.docx"])

    def test_a_file_whose_name_holds_a_secret_is_left_out(self):
        self.put(self.box, "notes-pass" + "word-" + PW.replace("-", "") + ".txt", "ZQ-NAME the plan is fine")
        got = self.run_it()
        self.assertNotIn("ZQ-NAME", self.text_of(got))
        self.assertEqual(got.safety, 1)

    def test_a_normal_file_is_unchanged(self):
        self.put(self.box, "a.md", "ZQ-A Release 2.5.1 on 31-10-2026; token: 2026 plan.")
        got = self.run_it()
        self.assertIn("ZQ-A Release 2.5.1 on 31-10-2026; token: 2026 plan.", self.text_of(got))
        self.assertEqual((got.safety, got.secret_labels), (0, ()))

    def test_a_secret_far_down_a_long_file_is_still_found_and_it_is_fast(self):
        # The old check was wall-clock (30 s for 40,000 lines); the secret must still be found at both sizes, and the growth from 10,000 to
        # 40,000 lines in CPU time is judged by growth_ratio.
        def work(lines):
            self.put(self.box, "long.txt", "plain words here\n" * lines + "pass" + "word=" + PW)
            got = self.run_it()
            self.assertEqual(got.passages, ())
            self.assertEqual(got.secret_labels, ("saved/long.txt",))
        assert_growth(self, work, 10000, "long file")

    def test_removing_the_screen_lets_the_secret_through(self):
        self.put(self.box, "s.txt", "ZQ-S pass" + "word=" + PW)
        with mock.patch.object(secret_screen, "looks_like_secret", return_value=False):
            got = self.run_it()
        self.assertIn(PW, self.text_of(got))                                # so the tests above depend on the screen
        self.assertEqual(self.run_it().passages, ())


class OnTheRoute(tp.OnTheRoute):
    def test_the_person_is_told_the_file_and_the_next_step_and_the_secret_goes_nowhere(self):
        (self.mine / "creds.txt").write_text("ZQ-CREDS pass" + "word=" + PW, encoding="utf-8")
        with self.assertLogs(level="DEBUG") as logs:
            logging.getLogger().debug("start")
            status, got = self.question("What is the cutover plan?")
        self.assertEqual(status, 200, got)
        (text,) = self.provider.sent
        self.assertIn("ZQ-MINE", text)
        self.assertNotIn(PW, text)
        self.assertNotIn("ZQ-CREDS", text)
        note = [n for n in got["notes"] if "creds.txt" in n]
        self.assertEqual(len(note), 1, got["notes"])
        self.assertIn("looks like it holds a secret", note[0])
        self.assertIn("Remove the secret from the file or move it out of the saved folder.", note[0])
        self.assertGreaterEqual(got["left_out_for_safety"], 2)
        for blob in (json.dumps(got), "\n".join(logs.output)):
            self.assertNotIn(PW, blob)


if __name__ == "__main__":
    unittest.main()
