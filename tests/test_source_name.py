"""Row 1077 (the owner's ruling of 10-11-2026): a Source is shown by its NAME, never by a path, everywhere the line is drawn (the live
peek through activity_read, a published file through publish). clark.source_name.source_name is the one rule: each part of the stored
words keeps only what follows its last / or \\, a stored YYYY-MM-DD reads DD-MM-YYYY, and the words are otherwise as they were.
Run: python3 dev/run_tests.py test_source_name
"""
import unittest

from _paths import SRC  # noqa: F401

from clark.source_name import source_name


class Name(unittest.TestCase):
    def test_plain_words_are_as_they_were(self):
        for words in ("Added by hand in clark", "Added by ask clark", "Duplicated from ABC-A-001", "Demo data (fictional)", "People list"):
            self.assertEqual(source_name(words), words)

    def test_words_with_no_path_in_them_are_as_they_were(self):
        for words in ("Steering, 01/10/2026", "<b>x</b>"):
            self.assertEqual(source_name(words), words, words)

    def test_any_other_slash_is_a_path_and_names_a_file_or_nothing(self):
        # reader A, MEDIUM: stricter than before ("Either/or" and "A/B test notes" were kept whole); these are paths with no file in them
        for words in ("Either/or", "A/B test notes", "Added by hand in clark / checked", "Reviewed 3/4 of the list"):
            self.assertNotIn("/", source_name(words), words)
        self.assertEqual(source_name("Word import, 2026-11-07, team/notes.docx, under Risks"), "Word import, 07-11-2026, notes.docx, under Risks")

    def test_a_path_keeps_its_last_part_only(self):
        self.assertEqual(source_name("projects/HRB secret/minutes/2026-10-20 Pilot readiness review.html"), "20-10-2026 Pilot readiness review.html")
        self.assertEqual(source_name("ZQ-SOURCE-PATH/actions.xlsx"), "actions.xlsx")
        self.assertEqual(source_name("C:\\Users\\someone\\Documents\\plan.xlsx"), "plan.xlsx")
        self.assertEqual(source_name("https://example.test/share/notes.docx"), "notes.docx")

    def test_a_folder_names_nothing(self):
        # reader A, MEDIUM: a trailing separator, or a last part with no file extension, names a folder: the file carries nothing for it
        for v in ("/Users/someone/Private Clients/", "Private Clients/Q3 plan", "C:\\Users\\x\\Private Clients\\", "/Users/someone/folder/", "\\\\fileserver\\share\\Clients"):
            self.assertEqual(source_name(v), "", v)
        self.assertEqual(source_name("Excel import, 2026-10-01, /Volumes/Secret Drive/"), "Excel import, 01-10-2026")

    def test_a_comma_inside_a_path_leaks_no_folder(self):
        # reader A, HIGH: the path rule runs on the whole string, then the words are split
        self.assertEqual(source_name("Excel import, 2026-10-01, C:\\Users\\xuser\\OneDrive - Acme, Inc\\actions.xlsx"), "Excel import, 01-10-2026, actions.xlsx")
        self.assertEqual(source_name("/Users/Doe, Pat/Private Clients, Inc/Q3, final.xlsx"), "Q3, final.xlsx", "a comma in the file's own name stays")
        self.assertEqual(source_name("\\\\fileserver\\share, a\\Clients, b\\risks.xlsx"), "risks.xlsx")
        self.assertEqual(source_name("~/Library/Mobile Documents/com~apple~CloudDocs/minutes.docx"), "minutes.docx")
        self.assertEqual(source_name("Réunion, 2026-10-01, /Volumes/Dossiers, privés/plan été.xlsx"), "Réunion, 01-10-2026, plan été.xlsx")

    def test_other_slashes_are_separators_and_a_url_gives_its_file_or_nothing(self):
        self.assertEqual(source_name("C:\uff0fUsers\uff0fxuser\uff0fplan.xlsx".replace("\\uff0f", "\uff0f")), "plan.xlsx")
        self.assertEqual(source_name("Q3\u2215Q4/plan.xlsx"), "plan.xlsx")
        self.assertEqual(source_name("\uff3cUsers\uff3cxuser\uff3cplan.xlsx"), "plan.xlsx")
        self.assertEqual(source_name("https://firm.example/sites/Private/plan.xlsx?web=1&user=xuser#top"), "plan.xlsx")
        for bare in ("https://intranet.example/", "https://intranet.example", "https://intranet.example/?a=1"):
            self.assertEqual(source_name(bare), "", bare)

    def test_a_prefix_before_a_root_is_cleaned_by_the_same_rule(self):
        # delta reader, MEDIUM: words before the root were kept raw
        self.assertEqual(source_name("Priv Clients/Acme, C:\\foo\\a.xlsx"), "a.xlsx")
        self.assertEqual(source_name("see Priv/x, then /Users/me/a.xlsx"), "a.xlsx")
        self.assertEqual(source_name("Excel import, 2026-10-01, /Users/me/a.xlsx"), "Excel import, 01-10-2026, a.xlsx")

    def test_lookalike_slashes_and_percent_escapes_are_separators(self):
        # delta reader, LOW
        for ch in ("\u2216", "\ufe68", "\u2571", "\u29f5", "\uff0f", "\uff3c", "\u2215"):
            self.assertEqual(source_name(f"C:{ch}Users{ch}xuser{ch}plan.xlsx"), "plan.xlsx", hex(ord(ch)))
            self.assertEqual(source_name(f"Priv{ch}Folder{ch}plan.xlsx"), "plan.xlsx", hex(ord(ch)))
        for esc in ("%2F", "%2f", "%5C", "%5c"):
            self.assertEqual(source_name(f"https://h.example/Private{esc}Clients{esc}plan.xlsx"), "plan.xlsx", esc)
        self.assertEqual(source_name("C%3A%5CUsers%5Cxuser%5Cplan.xlsx"), "plan.xlsx")
        self.assertEqual(source_name("https://h.example/Private%252FClients%252Fplan.xlsx"), "plan.xlsx", "an escape of an escape")

    def test_a_rootless_path_with_a_comma_names_a_file_or_nothing(self):
        # delta reader, LOW: the last part of a rootless relative path with no extension names a folder
        self.assertEqual(source_name("Notes, 2026-10-01 Priv/Folder, a.xlsx"), "Notes")
        self.assertEqual(source_name("Notes, Priv/Folder"), "Notes")
        self.assertEqual(source_name("Word import, 2026-11-07, team/notes.docx, under Risks"), "Word import, 07-11-2026, notes.docx, under Risks")

    def test_property_no_published_value_holds_a_separator_or_a_folder_of_the_stored_path(self):
        """2000 seeded stored values: a prefix, a root (or none), 1 to 4 folders (commas, spaces, unicode), a separator kind, a file name, a tail.
        Every folder carries a unique tag QZ<i>k<j>; no output has a separator of any kind or any tag, and, when rooted, no piece of any folder."""
        import random
        rnd = random.Random(11)
        seps = ["/", "\\", "\uff0f", "\uff3c", "\u2215", "\u2216", "\ufe68", "\u2571", "\u29f5", "%2F", "%5C"]
        names = ["Priv Clients", "Acme, Inc", "OneDrive - Acme, Inc", "M\u00fcller (Q3)", "\u4f1a\u8bae, \u8bb0\u5f55", "a b", "x,y", "Zed"]
        roots = ["C:\\", "D:/", "/", "~/", "\\\\srv\\", "file:///", "https://h.example/", "//h/", "./", "../", ""]
        pre = ["", "Excel import, 2026-10-01, ", "see ", "Notes, ", "Priv Clients/Acme, ", "see Priv/x, then ", "a\\b, "]
        post = ["", ", then", "  ", "?q=1", "#f/g"]
        for i in range(2000):
            root, sep = rnd.choice(roots), rnd.choice(seps)
            folders = [rnd.choice(names) + f" QZ{i}k{j}" for j in range(rnd.randint(1, 4))]
            stored = rnd.choice(pre) + root + sep.join(folders) + sep + rnd.choice(["a.xlsx", "plan.docx", "my plan (v2).xlsx"]) + rnd.choice(post)
            out = source_name(stored)
            self.assertFalse(set(out) & set("/\\\uff0f\uff3c\u2215\u2216\ufe68\u2571\u29f5"), (stored, out))
            self.assertNotIn("%2F", out.upper().replace("%2f", "%2F"), (stored, out))
            for j, folder in enumerate(folders):
                self.assertNotIn(f"QZ{i}k{j}", out, (stored, out))
                if root:
                    for piece in [folder] + [x.strip() for x in folder.split(",")]:
                        if piece and not piece.startswith("Zed"):
                            self.assertNotIn(piece, [x.strip() for x in out.split(",")], (stored, out))      # as a whole word of the output (a short piece such as "x" is also inside "a.xlsx")

    def test_a_long_name_is_cut_with_an_ellipsis(self):
        long = "Q" * 300 + " plan.xlsx"
        got = source_name(long)
        self.assertEqual(len(got), 120)
        self.assertTrue(got.endswith("\u2026"))
        self.assertEqual(source_name("x" * 120), "x" * 120)

    def test_each_comma_part_is_named_on_its_own(self):
        self.assertEqual(source_name("Excel import, 2026-10-01, /Volumes/share/HRB/plan.xlsx"), "Excel import, 01-10-2026, plan.xlsx")
        self.assertEqual(source_name("Word import, 2026-11-07, team/notes.docx, under Risks"), "Word import, 07-11-2026, notes.docx, under Risks")

    def test_a_date_reads_day_first_and_digits_that_are_not_a_date_stay(self):
        self.assertEqual(source_name("Excel import, 2026-10-01, plan.xlsx"), "Excel import, 01-10-2026, plan.xlsx")
        for text in ("Ref 12345-67-89 from the PMO", "Ticket 2026-13-45 filed", "Batch 20261001 and 2026-10-1"):
            self.assertEqual(source_name(text), text, text)

    def test_nothing_or_not_text_is_nothing(self):
        for v in (None, "", "   ", 7, "/", "\\", " / , / ", "C:\\"):
            self.assertEqual(source_name(v), "", repr(v))

    def test_the_words_are_trimmed_and_hidden_characters_dropped(self):
        self.assertEqual(source_name("  Added by hand in clark \n"), "Added by hand in clark")
        self.assertEqual(source_name("plan\u0007.xlsx"), "plan.xlsx")
        self.assertEqual(source_name("a/b\u200b.xlsx"), "b.xlsx")


if __name__ == "__main__":
    unittest.main()
