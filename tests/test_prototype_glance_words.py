"""#669: the prototype's At a glance tiles say the build's words and look (white tile, status dot, thin outline).

Run: python3 dev/run_tests.py test_prototype_glance_words
Quick tier: reads the prototype's files, starts no browser.
"""
import re
import unittest

from _paths import ROOT

PROTO = ROOT / "system" / "prototype"


class PrototypeGlance(unittest.TestCase):
    def test_words_are_the_builds(self):
        js = (PROTO / "views.js").read_text(encoding="utf-8")
        for w in ("of 1 open risk or issue", "of ${openRI} open risks and issues", "None high", "None open", "Oldest needed by ${D.fd(",
                  "No date set", "None waiting", "No open actions"):
            self.assertIn(w, js, w)
        for old in ("red or urgent", "None red", "Oldest ${"):
            self.assertNotIn(old, js, old)

    def test_risks_colour_does_not_use_the_red_count(self):
        js = (PROTO / "views.js").read_text(encoding="utf-8")
        line = next(x for x in js.splitlines() if "k: 'High risks and issues'" in x)
        self.assertIn("rag: high.length ? 'R' : openRI ? 'A' : 'G'", line)

    def test_tile_look_is_white_with_a_thin_outline_and_no_tint(self):
        css = (PROTO / "app.css").read_text(encoding="utf-8")
        rule = next(x for x in css.splitlines() if x.startswith(".glance .fig { background"))
        self.assertIn("background: var(--surface)", rule)
        self.assertIn("border: 1px solid", rule)
        self.assertIsNone(re.search(r"\.glance \.rag-[GAR] \{ background", css))
        self.assertIn(".rag-R .ragdot", css)


if __name__ == "__main__":
    unittest.main()
