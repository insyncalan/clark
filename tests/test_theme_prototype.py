"""Row 1260, step 3: the prototype-2.0 Theme folder (tokens.css and rules.css) under src/clark/themes.

Run: python3 dev/run_tests.py test_theme_prototype

Values are read from the files; the contrast ratios are computed, never written down.
"""
import re
import unittest

from _paths import ROOT

BASE = (ROOT / "src" / "clark" / "brand" / "tokens.css").read_text(encoding="utf-8")
FOLDER = ROOT / "src" / "clark" / "themes" / "prototype-2.0"
TOKENS = (FOLDER / "tokens.css").read_text(encoding="utf-8")
RULES = (FOLDER / "rules.css").read_text(encoding="utf-8")
NAME = re.compile(r"(--[a-z0-9-]+)\s*:")
DECL = re.compile(r"(--[a-z0-9-]+)\s*:\s*([^;]+);")
SHELL_DECLARED = {"--sec-pad-t", "--sec-px"}      # row 1195: set by shell.css (the section padding), read by the Work items gear rule
THEME_ONLY = {"--sec-band-bg", "--set-ring", "--set-win", "--set-shadow", "--ms-amber-shape", "--tile-on-bg", "--tile-on-fg"}      # rows 1311, 1299, 1396 and 1395: set and read by this Theme alone; declaring them in the committed file would change the Cards page bytes; row 1299 adds --set-ring and --set-win (the Settings window, Classic only)
NEW_NINE = {"--page-bg", "--page-grad", "--band-bg", "--line-soft", "--gutter-rule", "--sec-number-color", "--sec-number-size", "--logo-width", "--logo-height"}


def blocks(css):
    """{'light','dark','auto'} -> declaration text of the block."""
    light = re.search(r"^:root \{(.*?)^\}", css, re.S | re.M).group(1)
    dark = re.search(r":root\[data-theme=dark\]\s*\{(.*?)\n\}", css, re.S).group(1)
    auto = re.search(r":root\[data-theme=auto\]\s*\{(.*?)\n  \}", css, re.S).group(1)
    return {"light": light, "dark": dark, "auto": auto}


def decls(text):
    return {n: re.sub(r"\s+", " ", v.strip()) for n, v in DECL.findall(text)}


def lum(hex_colour):
    parts = [int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= .03928 else ((c + .055) / 1.055) ** 2.4 for c in parts]
    return .2126 * lin[0] + .7152 * lin[1] + .0722 * lin[2]


def ratio(a, b):
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + .05) / (lo + .05)


class ThemePrototype(unittest.TestCase):
    def merged(self, mode):
        base = decls(blocks(BASE)["light"])
        if mode != "light":
            base.update(decls(blocks(BASE)["dark"]))
        base.update(decls(blocks(TOKENS)[mode]))
        return base

    def test_the_folder_has_the_two_files(self):
        self.assertTrue((FOLDER / "tokens.css").is_file())
        self.assertTrue((FOLDER / "rules.css").is_file())

    def test_it_sets_only_names_the_committed_tokens_declare(self):
        declared = set(NAME.findall(BASE)) | NEW_NINE | SHELL_DECLARED | THEME_ONLY      # the nine are declared by the sibling row 1260 tokens PR
        self.assertEqual(sorted(set(NAME.findall(TOKENS)) - declared), [], "a Theme sets existing names only")
        used = set(re.findall(r"var\((--[a-z0-9-]+)", RULES))
        own = set(re.findall(r"(--(?:wil|pri|adc|badge)-[a-z0-9-]+)\s*:", RULES))      # row 1347: the four --adc-blue* properties (Draft ready button blue, a named exception, ruling 19-11); row 1195: the Work items colours the mock-up measures; row 1409: the four --pri-* priority pairs; row 1194: the --badge-* file-type colours of Documents and links; set and read by rules.css alone
        self.assertEqual(sorted(used - declared - own - {"--ly", "--sb", "--ask-w", "--ad-r"}), [], "rules.css reads declared names only, and four the page sets itself: --ly inline and --sb on its box (row 1315), --ask-w on the root while the ask panel is open (row 1292, askPanelState.js), --ad-r on the Draft sheet from AskDraft.jsx (row 1346)")

    def test_the_two_dark_copies_are_equal(self):
        b = blocks(TOKENS)
        self.assertEqual(decls(b["auto"]), decls(b["dark"]))

    def test_it_sets_the_new_tokens_in_light_and_dark(self):
        b = blocks(TOKENS)
        for mode in ("light", "dark"):
            got = set(decls(b[mode]))
            self.assertTrue({"--page-bg", "--page-grad", "--band-bg", "--line-soft", "--gutter-rule"} <= got, mode)

    def test_rules_hold_no_colour_literals_and_no_client_text(self):
        # the primary-buttons block carries three literals from the prototype (gradient start, dark text, ring): see its own comment and test_theme_primary_1319
        # one named exemption (row 1343 final table): the filter-line underline is the mock-up's rgb(137,148,176) and no token holds that value (--grey-500 is rgb(135,148,179))
        fline_underline = ".fline { border: 0; border-bottom: 1px solid #8994b0;"
        self.assertEqual(RULES.count(fline_underline), 1, "the exempt literal is on the one .fline rule")
        # and the typed-word box on that line (row 1343): background rgb(238,240,246) has no token; text rgb(29,36,51) is the mock-up pair, kept literal so the box reads the same in dark
        ftxt = "border-radius: 6px; background: #eef0f6; color: #1d2433; box-shadow: none; }"
        self.assertEqual(RULES.count(ftxt), 1, "the exempt literals are on the one .fk.k-txt rule")
        self.assertIsNone(re.search(r"#[0-9a-fA-F]{3,8}\b", RULES.replace(fline_underline, "").replace(ftxt, "").split("/* Row 1319, primary buttons")[0]), "colours come from tokens")
        self.assertIsNone(re.search(r"/\*[^*]*#\d", RULES + TOKENS), "no hash-digit in a comment")

    def test_body_and_muted_text_reach_4_5_to_1_in_light_and_dark(self):
        for mode, grounds in (("light", ("--page-bg", "--grey-50", "--band-bg")), ("dark", ("--bg", "--surface", "--page-bg", "--band-bg"))):
            t = self.merged(mode)
            ground_values = [t[g] for g in grounds]
            if mode == "light":
                ground_values += ["#FFFFFF", "#FCFDFE", "#F7F9FC"]
            else:
                ground_values += ["#0F1523", "#121A2A"]
            for fg in ("--text", "--heading", "--text-muted"):
                for bg in ground_values:
                    self.assertGreaterEqual(ratio(t[fg].upper(), bg.upper()), 4.5, f"{mode} {fg} on {bg}")

    def test_status_words_reach_4_5_to_1_on_their_tints(self):
        for mode in ("light", "dark"):
            t = self.merged(mode)
            for tone in ("red", "amber", "green", "blue", "grey"):
                self.assertGreaterEqual(ratio(t[f"--tone-{tone}-text"].upper(), t[f"--tone-{tone}-tint"].upper()), 4.5, f"{mode} {tone}")
            self.assertGreaterEqual(ratio(t["--tone-on-urgent"].upper(), t["--tone-urgent"].upper()), 4.5, f"{mode} urgent")

    def test_the_section_number_and_gutter_reach_3_to_1_for_ui(self):
        for mode, ground in (("light", "#FFFFFF"), ("dark", None)):
            t = self.merged(mode)
            g = ground or t["--surface"]
            self.assertGreaterEqual(ratio(t["--brand-blue"].upper(), g.upper()), 3.0, mode)


if __name__ == "__main__":
    unittest.main()
