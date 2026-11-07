"""#599 (PR 310 / #412): a use case can be Done, so it has four statuses. No document or screen text may still say there are three,
and the grey Done pill keeps its text readable.
Run: python3 dev/run_tests.py test_use_case_done_wording
Reads files only (no Chrome)."""
import re
import unittest

from _paths import ROOT, SRC

THREE = re.compile(r"\b(?:three|3)\s+(?:use[- ]?case\s+)?status(?:es)?\b", re.I)
SUFFIXES = {".md", ".txt", ".py", ".js", ".jsx", ".html", ".css", ".json"}


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def files():
    for top in (ROOT / "docs", SRC / "clark"):
        for p in sorted(top.rglob("*")):
            parts = set(p.parts)
            if p.is_file() and p.suffix in SUFFIXES and not parts & {"vendor", "node_modules", "__pycache__"}:
                yield p
    yield ROOT / "README.md"


def luminance(hex_colour):
    c = [int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def ratio(a, b):
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


class DoneWording(unittest.TestCase):
    def test_nothing_says_a_use_case_has_three_statuses(self):
        found = []
        n = 0
        for p in files():
            n += 1
            for i, line in enumerate(read(p).splitlines(), 1):
                if THREE.search(line):
                    found.append("%s:%d" % (p.relative_to(ROOT), i))
        self.assertGreater(n, 20, "the scan reaches the documents and the page source")
        self.assertEqual(found, [], "a use case has four statuses since it can be Done (#412)")

    def test_the_scan_finds_the_wording_it_looks_for(self):
        for text in ("three statuses", "Three use case statuses", "the 3 statuses", "three status words"):
            self.assertTrue(THREE.search(text), text)
        self.assertFalse(THREE.search("four statuses"))

    def test_the_four_statuses_are_still_four(self):
        words = re.search(r"STATUS_WORDS = \[([^\]]*)\]", read(SRC / "clark/page/src/logic/useCasesList.js")).group(1)
        self.assertEqual(len(re.findall(r'"[^"]+"', words)), 4)

    def test_the_grey_done_pill_text_reads_at_4_5_to_1_in_light_and_dark(self):
        css = read(SRC / "clark/brand/tokens.css")
        pill = re.search(r"\.pill\.n \{ background: var\(--(grey-\d+)\); color: var\(--(grey-\d+)\); \}", read(SRC / "clark/page/shell.css"))
        self.assertTrue(pill, "the Done pill is .pill.n")
        back, text = pill.groups()
        light = css.split("dark mode")[0]
        dark = css.split(":root[data-theme=dark] {")[1].split("}")[0]
        for name, block in (("light", light), ("dark", dark)):
            colour = {k: re.search(r"--%s:\s*(#[0-9A-Fa-f]{6})" % k, block).group(1) for k in (back, text)}
            self.assertGreaterEqual(ratio(colour[back], colour[text]), 4.5, name)


if __name__ == "__main__":
    unittest.main()
