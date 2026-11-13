"""Mutation hunt on row 1025 (Spacing): the page's density store (stores/density.js) run in node with the signal and the browser stubbed.
It pins what the source-text checks in test_publish_style and test_section_style_cards do not: the default, what is read back from
the browser, what is painted, and that a published file's density is painted but never remembered.

Run: python3 dev/run_tests.py test_density_store
"""
import json
import re
import subprocess
import unittest
from pathlib import Path

from test_publish_style import need_node

SRC = (Path(__file__).resolve().parent.parent / "src" / "clark" / "page" / "src" / "stores" / "density.js").read_text(encoding="utf-8")


def run(test, body, stored=None, throws=False, document=True):
    """Run density.js then `body` (JS that ends by calling out(value)); the JSON of what it passed to out()."""
    node = need_node(test)
    src = re.sub(r"^import .*signals.*$", "const signal = (v) => ({ value: v });", SRC, flags=re.M)
    get = "() => { throw new Error('private'); }" if throws else f"(k) => (k === 'clark.density' ? {json.dumps(stored)} : null)"
    put = "() => { throw new Error('private'); }" if throws else "(k, v) => { kept[k] = v; }"
    code = ("const kept = {}; const painted = [];\n"
            f"globalThis.localStorage = {{ getItem: {get}, setItem: {put} }};\n"
            + ("globalThis.document = { documentElement: { dataset: { set density(v) { painted.push(v); }, get density() { return painted[painted.length - 1]; } } } };\n"
               if document else "")
            + src + "\nlet result;\nconst out = (v) => { result = v; };\n" + body + "\nconsole.log(JSON.stringify(result));")
    done = subprocess.run([node, "--input-type=module", "-e", code], capture_output=True, text=True)
    test.assertEqual(done.returncode, 0, done.stderr)
    return json.loads(done.stdout)


class DensityStore(unittest.TestCase):
    def test_nothing_chosen_is_compact_and_is_painted_at_load(self):
        self.assertEqual(run(self, "out({ d: density.value, painted, kept, def: DEFAULT_DENSITY, ids: IDS });"),
                         {"d": "compact", "painted": ["compact"], "kept": {}, "def": "compact", "ids": ["compact", "comfortable"]})

    def test_a_remembered_choice_wins_and_is_painted(self):
        self.assertEqual(run(self, "out({ d: density.value, painted });", stored="comfortable"), {"d": "comfortable", "painted": ["comfortable"]})
        self.assertEqual(run(self, "out({ d: density.value, painted });", stored="compact"), {"d": "compact", "painted": ["compact"]})

    def test_a_remembered_word_that_is_not_a_density_reads_as_compact(self):
        for bad in ("card", "roomy", "slim", "", "Comfortable", "bogus"):
            self.assertEqual(run(self, "out({ d: density.value, painted });", stored=bad), {"d": "compact", "painted": ["compact"]}, bad)

    def test_a_browser_that_will_not_remember_still_works(self):
        got = run(self, "setDensity('comfortable'); out({ d: density.value, painted });", throws=True)
        self.assertEqual(got, {"d": "comfortable", "painted": ["compact", "comfortable"]})
        self.assertEqual(run(self, "out(density.value);", throws=True), "compact")

    def test_no_document_is_not_an_error(self):
        self.assertEqual(run(self, "setDensity('comfortable'); out(density.value);", document=False), "comfortable")

    def test_choosing_is_painted_and_remembered_under_one_key(self):
        got = run(self, "setDensity('comfortable'); setDensity('compact'); out({ d: density.value, painted, kept });")
        self.assertEqual(got, {"d": "compact", "painted": ["compact", "comfortable", "compact"], "kept": {"clark.density": "compact"}})
        got = run(self, "setDensity('compact'); setDensity('comfortable'); out({ d: density.value, painted, kept });")
        self.assertEqual(got, {"d": "comfortable", "painted": ["compact", "compact", "comfortable"], "kept": {"clark.density": "comfortable"}})

    def test_a_word_that_is_not_a_density_changes_nothing_and_is_not_remembered(self):
        got = run(self, "setDensity('comfortable'); for (const b of ['bogus', 'roomy', 'card', '', null, undefined, 3]) setDensity(b); out({ d: density.value, painted, kept });")
        self.assertEqual(got, {"d": "comfortable", "painted": ["compact", "comfortable"], "kept": {"clark.density": "comfortable"}})

    def test_a_files_word_is_read_roomy_is_comfortable_and_anything_else_compact(self):
        got = run(self, "out(['roomy', 'card', 'slim', 'grey', undefined, null, 3, 'Roomy', 'comfortable'].map(densityOfWord));")
        self.assertEqual(got, ["comfortable"] + ["compact"] * 8)

    def test_a_files_density_is_painted_and_never_remembered(self):
        got = run(self, "useFileDensity('roomy'); const a = density.value; useFileDensity('card'); out({ a, b: density.value, painted, kept });")
        self.assertEqual(got, {"a": "comfortable", "b": "compact", "painted": ["compact", "comfortable", "compact"], "kept": {}})

    def test_the_words_sent_to_the_publish_code_are_the_two_it_knows(self):
        got = run(self, "out([sectionWord('comfortable'), sectionWord('compact'), sectionWord('x'), sectionWord(undefined)]);")
        self.assertEqual(got, ["roomy", "card", "card", "card"])

    def test_valid_names_exactly_the_two_densities(self):
        got = run(self, "out(['compact', 'comfortable', 'Compact', '', null, 'roomy'].map(valid));")
        self.assertEqual(got, [True, True, False, False, False, False])


if __name__ == "__main__":
    unittest.main()
