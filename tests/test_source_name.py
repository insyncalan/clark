"""Row 1077 (the owner's ruling of 10-11-2026): a Source is shown by its NAME, never by a path, everywhere the line is drawn (the live
peek through activity_read, a published file through publish). clark.source_name.source_name is the one rule, a CHARACTER ALLOW-LIST
(fourth pass, the coordinator's design):
  A. Normalise: NFKC; decode %XX, %uXXXX, HTML numeric and named entities until nothing changes (at most 60 rounds); one space for any white space;
     control, format and zero-width characters out.
  B. PLAIN WORDS: every character is a letter or digit (str.isalnum) or one of  space , . - _ ( ) : ' & + #  and the value does not start
     with a drive letter (C:). Plain words keep their words, commas and a stored YYYY-MM-DD read day first.
  C. Anything else makes the value NOT plain: it publishes ONLY a final file name, the text after the last character that is not a letter,
     digit, space or one of . - _ ( ) ' & + # , and only when it ends in an extension (a dot and 1 to 8 letters or digits) after a non-empty
     stem; otherwise NOTHING.
  E. At most 120 characters, cut with an ellipsis.
Run: python3 dev/run_tests.py test_source_name
"""
import random
import re
import unittest

from _paths import SRC  # noqa: F401

from clark import source_name as sn
from clark.source_name import source_name

SEPARATORS = ["/", "\\", "\uff0f", "\uff3c", "\u2215", "\u2216", "\ufe68", "\u2571", "\u2572", "\u29f5", "\u29f8", "\u29f9", "\u27cb", "\u2afd", "\u2044",
              "%2F", "%5C", "%252F", "%2f", "%5c", "\uff05\uff12\uff26", "&#47;", "&#x2F;", "&sol;", "&bsol;", "%u002F", "%u005C", "%c0%af", "<", ">"]
OUTSIDE = re.compile(r"[^\w .\-()':,&+#]")                       # a character that plain words never hold (and a name never holds: no comma or colon either)


class Plain(unittest.TestCase):
    def test_plain_words_are_as_they_were(self):
        for words in ("Added by hand in clark", "Added by ask clark", "Duplicated from ABC-A-001", "Demo data (fictional)", "People list",
                      "Jan 5, 2026", "v1.2 notes", "Q&A + R&D (final) #3", "Duplicated from: ABC-A-001", "Réunion du comité", "会议记录", "Steering notes"):
            self.assertEqual(source_name(words), words)

    def test_dates_read_day_first_in_plain_words_and_digits_that_are_not_a_date_stay(self):
        self.assertEqual(source_name("Excel import, 2026-10-01, plan.xlsx"), "Excel import, 01-10-2026, plan.xlsx")
        self.assertEqual(source_name("Word import, 2026-11-07, notes.docx, under Risks"), "Word import, 07-11-2026, notes.docx, under Risks")
        for text in ("Ref 12345-67-89 from the PMO", "Ticket 2026-13-45 filed", "Batch 20261001 and 2026-10-1"):
            self.assertEqual(source_name(text), text, text)

    def test_published_is_the_file_name_only_and_free_text_is_dropped(self):
        """Ruling A of row 1077 (the Source line in a file): plain words are not published as they stand."""
        for words in ("Added by hand in clark", "Plan: v2", "Steering notes", "Jan 5, 2026", "Word import, 2026-11-11, under a person's name"):
            self.assertEqual(source_name(words, published=True), "", words)
        for words, shown in (("Word import, 2026-11-11, plan.docx, under Risks", "plan.docx"), ("Excel import, 2026-10-01, plan.xlsx", "plan.xlsx"),
                             ("plan.xlsx", "plan.xlsx"), ("/a/b/plan.xlsx", "plan.xlsx")):
            self.assertEqual(source_name(words, published=True), shown, words)

    def test_only_a_known_file_extension_makes_a_listed_file_name(self):
        for words in ("john.smith", "acme.com", "v1.2", "Import, 2026-11-11, john.smith", "Import, acme.com"):
            self.assertEqual(source_name(words, published=True), "", words)
        for words, shown in (("Plan.docx", "Plan.docx"), ("notes.PDF", "notes.PDF"), ("a b.xlsx", "a b.xlsx"), ("Import, a b.xlsx", "a b.xlsx")):
            self.assertEqual(source_name(words, published=True), shown, words)

    def test_a_huge_value_is_cut_before_it_is_read_the_name_at_the_end_is_kept_when_published(self):
        huge = "x " * 50000
        self.assertEqual(source_name(huge + ", plan.xlsx", published=True), "plan.xlsx")
        self.assertLessEqual(len(source_name(huge)), 120)

    def test_a_left_over_numeric_entity_start_is_never_plain_words(self):
        """The guard `not _ENTITY.search(text)` in _is_plain: these hold only allowed characters, so only that guard refuses them."""
        for words in ("&#abc", "notes &# more", "a&#", "&#x", "&#xyz plan"):
            self.assertEqual(source_name(words), "", words)

    def test_nothing_or_not_text_is_nothing(self):
        for v in (None, "", "   ", 7, [], "/", "\\", " / , / ", "C:\\", "C:", "https://intranet.example/", "https://intranet.example", "smb://h/Priv/"):
            self.assertEqual(source_name(v), "", repr(v))

    def test_the_words_are_trimmed_hidden_characters_dropped_and_white_space_is_one_space(self):
        self.assertEqual(source_name("  Added by hand in clark \n"), "Added by hand in clark")
        self.assertEqual(source_name("plan\u0007.xlsx"), "plan.xlsx")
        self.assertEqual(source_name("a/b\u200b.xlsx"), "b.xlsx")
        self.assertEqual(source_name("line1\nline2"), "line1 line2")
        self.assertEqual(source_name("a \t\r\n  b\u00a0\u2003\u3000c"), "a b c")

    def test_a_long_name_is_cut_with_an_ellipsis(self):
        got = source_name("Q" * 300 + " plan.xlsx")
        self.assertEqual(len(got), 120)
        self.assertTrue(got.endswith("\u2026"))
        self.assertEqual(source_name("x" * 120), "x" * 120)


class NotPlain(unittest.TestCase):
    def test_a_path_publishes_only_its_file_name(self):
        for stored, shown in (
                ("/Users/someone/Desktop/Private Clients/Q3 plan.xlsx", "Q3 plan.xlsx"), ("C:\\Users\\xuser\\OneDrive - Firm\\actions.xlsx", "actions.xlsx"),
                ("\\\\fileserver\\share\\Clients\\risks.xlsx", "risks.xlsx"), ("~/Library/Mobile Documents/com~apple~CloudDocs/minutes.docx", "minutes.docx"),
                ("https://example.test/share/notes.docx", "notes.docx"), ("项目/会议/计划.xlsx", "计划.xlsx"),
                ("Excel import, 2026-10-01, /Volumes/share/HRB/plan.xlsx", "plan.xlsx"),                 ("Priv Clients / Acme / a.xlsx", "a.xlsx"), ("Acme, Inc/a.xlsx", "a.xlsx"), ("Excel import, Acme, Inc/Q3/a.xlsx", "a.xlsx"),
                ("Notes, 2026-10-01 Priv/Folder, a.xlsx", "a.xlsx"), ("/Users/Doe, Pat/Private Clients, Inc/Q3, final.xlsx", "final.xlsx"),
                ("Excel import, 2026-10-01, C:\\Users\\xuser\\OneDrive - Acme, Inc\\actions.xlsx", "actions.xlsx"),
                ("Priv Clients/Acme, C:\\foo\\a.xlsx", "a.xlsx"), ("see Priv/x, then /Users/me/a.xlsx", "a.xlsx"), ("C:foo.xlsx", "foo.xlsx")):
            self.assertEqual(source_name(stored), shown, stored)

    def test_a_folder_or_a_value_with_no_file_name_publishes_nothing(self):
        for stored in ("/Users/someone/Private Clients/", "Private Clients/Q3 plan", "C:\\Users\\x\\Private Clients\\", "Notes, Priv/Folder",
                       "Phone call, Maria Hill / Q3 review", "Word import, 2026-11-07, team/notes.docx, under Risks", "T&C / review, final", "Either/or", "A/B test notes", "Reviewed 3/4 of the list",
                       "Steering, 01/10/2026", "c:Zq0, Inc/x", "Zq9/1/2", "Priv Clients 1/2/3", "https://h.example/a.xlsx?q=Zq",
                       "<b>x</b>", "a/.xlsx", "Priv/.env"):
            self.assertEqual(source_name(stored), "", stored)

    def test_the_fourth_pass_strings(self):
        # HIGH: a lone "<" or ">" and digits before a separator were kept
        for stored, shown in (("Priv Clients</a.xlsx", "a.xlsx"), ("Priv/>a.xlsx", "a.xlsx"), ("Acme2026/10/01.xlsx", "01.xlsx"),
                              ("Acme2026/10/01 plan.xlsx", "01 plan.xlsx"), ("Acme Corp 5/6/7 a.xlsx", "7 a.xlsx"), ("Zq9/1/2", ""), ("Priv Clients 1/2/3", "")):
            self.assertEqual(source_name(stored), shown, stored)
        # LOW: other lookalikes, fullwidth and encoded separators
        for sep in SEPARATORS:
            self.assertEqual(source_name(f"Priv Clients{sep}Acme{sep}a.xlsx"), "a.xlsx", repr(sep))
            self.assertEqual(source_name(f"C:{sep}Users{sep}xuser{sep}plan.xlsx"), "plan.xlsx", repr(sep))
            self.assertEqual(source_name(f"Priv Clients{sep}Acme{sep}"), "", repr(sep))
        self.assertEqual(source_name("https://h.example/Private%252FClients%252Fplan.xlsx"), "plan.xlsx")
        self.assertEqual(source_name("Priv%\n5CAcme%\t5Ca.xlsx"), "a.xlsx", "an escape with a newline or tab inside it")
        self.assertEqual(source_name("Priv%\u200b5CAcme%u00\u200b5Ca.xlsx"), "a.xlsx", "or a zero-width character")

    def test_markup_is_not_a_name(self):
        # W27: Source is a name, not markup
        self.assertEqual(source_name("<b>x</b>"), "")
        self.assertEqual(source_name("<script>alert(1)</script>"), "")
        self.assertEqual(source_name("a<b>c.xlsx"), "c.xlsx")

    def test_a_drive_letter_start_is_never_plain(self):
        self.assertEqual(source_name("C:\\a\\b.xlsx"), "b.xlsx")
        self.assertEqual(source_name("c:b.xlsx"), "b.xlsx")
        self.assertEqual(source_name("c: some words"), "")
        self.assertEqual(source_name("Cx: some words"), "Cx: some words", "only a single letter and a colon is a drive")

    def test_the_allow_list_is_exactly_these_characters(self):
        """Mutation guard: one character more (a slash lookalike) in the allow-list breaks the pins above; this pins the list itself."""
        self.assertEqual(sn.PLAIN_EXTRA, " ,.-_():'&+#")
        self.assertEqual(sn.NAME_EXTRA, " .-_()'&+#")


class Entities(unittest.TestCase):
    """Fifth pass: an entity that survives the decode, or one made after a hidden character is taken out, is never shown."""
    Z = "\u200b"
    LEFT = ["&" + "amp;" * 5 + "#47", "&" + "amp;" * 5 + "#x2f", "&" + "amp;" * 5 + "#92", "&" + "amp;" * 5 + "lt", "&#" + Z + "47", "&l" + Z + "t",
            "&" + "amp;" * 40 + "#47", "&#" + Z + "x2" + Z + "f", "&a" + Z + "mp;#47", "&#4" + Z + "7;", "Notes &lt;b&gt; x", "a &#47; b"]

    def test_the_five_inputs_and_the_zero_width_ones_show_nothing_of_an_entity(self):
        for stored in self.LEFT:
            out = source_name(stored)
            self.assertNotRegex(out, r"&#|&[A-Za-z0-9]+;", (stored, out))
            self.assertNotRegex(out, r"&#?[A-Za-z0-9]*$", (stored, out))
            self.assertEqual(out, "", stored)

    def test_ampersand_and_hash_in_plain_words_stay_plain(self):
        for words in ("R&D", "C#", "R&D review, C# notes", "Q&A (Q3)", "AT&T"):
            self.assertEqual(source_name(words), words)

    def test_a_seeded_mix_of_nested_and_split_entities_leaks_none(self):
        pieces = ["amp;", "#47", "#x2f", "#92", "lt", "gt", ";", "&", self.Z, " ", "\n", "%2F", "x", "R", "5", "&amp;"]
        for seed in (51, 5150, 20261110):
            rnd = random.Random(seed)
            for _ in range(3000):
                stored = "".join(rnd.choice(pieces) for _ in range(rnd.randint(1, 14)))
                out = source_name(stored)
                self.assertNotRegex(out, r"&#|&[A-Za-z0-9]+;|[<>/\\%]", (stored, out))


class Property(unittest.TestCase):
    ROOTS = ["C:\\", "c:", "D:/", "\\\\srv\\share\\", "/Users/x/", "~/", "file:///", "smb://h/", "https://usr" + ":" + "pw@host.example:8080/", "//h/", "./", ""]
    PRE = ["", "Excel import, ", "Excel import, 2026-10-01, ", "see ", "Notes, ", "Phone call, ", "Added by hand in clark, ", "Priv Clients/Acme, ", "<b>x</b> "]
    POST = ["", ", then", "?q=Zqquery1&b=2", "#Zqfrag/f", "\n", "\t", ", more words", "\u200b"]
    EXTRA = ["", ", Inc", " (Q3)", "\u4f1a\u8bae", "\U0001f642", "..", "~", "2026", " 5", "1", " 12/3 "]

    def check(self, stored, tags):
        out = source_name(stored)
        self.assertFalse(OUTSIDE.search(out), (stored, out))
        self.assertNotRegex(out, r"%[0-9A-Fa-f]{2}|&#|&[a-z]+;", (stored, out))
        for tag in tags:
            self.assertNotIn(tag.lower(), out.lower(), (stored, out))
        for bit in ("usr" + ":" + "pw", "host.example", "Zqquery", "Zqfrag", "Excel import", "Phone call", "Notes", "Added by hand", "see ", "Priv Clients"):
            self.assertNotIn(bit, out, (stored, out))

    def test_seeded_generator_finds_no_leak(self):
        """Folders with digits, tildes, tags, emoji, lookalike and encoded separators in every combination; four seeds of 1500 values."""
        for seed in (777123, 4242, 90210, 31337):
            rnd = random.Random(seed)
            for i in range(1500):
                tags = [f"Zq{i}x{j}" for j in range(rnd.randint(1, 5))]
                body = "".join(g + rnd.choice(self.EXTRA) + rnd.choice(SEPARATORS + [" / ", " \\ "]) for g in tags)
                self.check(rnd.choice(self.PRE) + rnd.choice(self.ROOTS) + body + rnd.choice(["a.xlsx", "my plan, v2.xlsx", "noext", "a,b.xlsx", "01.xlsx"]) + rnd.choice(self.POST), tags)

    def test_a_value_made_only_of_allowed_characters_is_left_alone(self):
        rnd = random.Random(5)
        alphabet = "abcXYZ 019,.-_():'&+#\u00e9\u4f1a"
        for _ in range(1000):
            words = "".join(rnd.choice(alphabet) for _ in range(rnd.randint(1, 60))).strip()
            words = re.sub(r" {2,}", " ", words)
            if re.search(r"&#|&\w", words) or re.match(r"[A-Za-z]:", words) or re.search(r":(?![\s\d]|$)", words) or re.search(r"(?<![\d-])\d{4}-\d{2}-\d{2}(?![\d-])", words) or not words:
                continue
            self.assertEqual(source_name(words), words if len(words) <= 120 else source_name(words), words)


if __name__ == "__main__":
    unittest.main()
