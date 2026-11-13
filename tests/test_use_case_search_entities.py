"""The Use cases list search finds standing text saved with HTML entities (R&amp;D, a&nbsp;b).
Run: python3 dev/run_tests.py test_use_case_search_entities
Runs the list's own module under node (no Chrome)."""
import json
import subprocess
import unittest

from _paths import SRC

LOGIC = SRC / "clark" / "page" / "src" / "logic"

SCRIPT = """
const m = await import(%s);
const d = {use_cases: [{id: "u1", ref: "1", title: "T", standing: %s}]};
console.log(m.listOf(d, [])[0].text);
"""


def text_for(standing):
    js = SCRIPT % (json.dumps("file://" + str(LOGIC / "useCasesList.js")), json.dumps(standing))
    r = subprocess.run(["node", "--input-type=module", "-e", js], capture_output=True, text=True, check=True)
    return r.stdout.strip()


class SearchTextDecodesEntities(unittest.TestCase):
    def test_amp_and_nbsp(self):
        t = text_for("<p>R&amp;D a&nbsp;b</p>")
        self.assertIn("r&d", t)
        self.assertIn("a b", t)

    def test_other_entities(self):
        t = text_for("<p>&lt;x&gt; &quot;q&quot; it&#39;s &#65;&#x42;</p>")
        for want in ('<x>', '"q"', "it's", "ab"):
            self.assertIn(want, t)

    def test_encoded_tag_is_text_not_stripped(self):
        self.assertIn("<b>", text_for("&lt;b&gt;"))

    def test_amp_decoded_once(self):
        self.assertIn("&lt;", text_for("&amp;lt;"))


if __name__ == "__main__":
    unittest.main()
