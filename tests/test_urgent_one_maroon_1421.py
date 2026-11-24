"""Row 1421: one maroon for Urgent in the page, the Word file and the Excel export. The ruled value is 6B1D2A (ruling: "Maroon is 6B1D2A (export tokens)").
Run: python3 dev/run_tests.py test_urgent_one_maroon_1421"""
import re
import unittest

from _paths import ROOT

SRC = ROOT / "src" / "clark"
RULED = "6B1D2A"
LIGHT_TOKENS = [SRC / "brand" / "tokens.css", SRC / "themes" / "prototype-2.0" / "tokens.css"]


def light_urgent(path):
    # the first --tone-urgent in a file is the light value (the dark values follow in the dark blocks)
    return re.search(r"--tone-urgent:\s*#([0-9A-Fa-f]{6})", path.read_text(encoding="utf-8")).group(1).upper()


class OneMaroon(unittest.TestCase):
    def test_the_ruled_maroon_is_the_value_of_tone_urgent(self):
        for path in LIGHT_TOKENS:
            self.assertEqual(light_urgent(path), RULED, path.name)

    def test_page_chip_word_and_excel_read_the_same_token(self):
        read = lambda p: (SRC / p).read_text(encoding="utf-8")
        self.assertRegex(read("page/shell.css"), r"\.ico\.u\s*\{\s*background:\s*var\(--tone-urgent\)")
        self.assertIn("--pri-urgent-bg: var(--tone-urgent)", read("themes/prototype-2.0/rules.css"))
        self.assertIn('"tone-urgent"', read("excel_colours.py"))
        self.assertIn('ctx.tok["tone-urgent"]', read("docx_build.py"))
        # no second maroon hex anywhere under src/clark (the dark tile values are the dark theme's own)
        dark = set()
        for path in LIGHT_TOKENS:
            dark |= {m.upper() for m in re.findall(r"--tone-urgent:\s*#([0-9A-Fa-f]{6})", path.read_text(encoding="utf-8"))}
        allowed = {RULED} | dark
        for path in SRC.rglob("*"):
            if path.suffix not in (".css", ".py", ".js", ".html"):
                continue
            for hx in re.findall(r"7A1B2E|6B1D2A", path.read_text(encoding="utf-8", errors="ignore"), re.I):
                self.assertIn(hx.upper(), allowed, f"{path} names a second maroon {hx}")


if __name__ == "__main__":
    unittest.main()
