"""Row 1251, slice 1: the starting text of the section templates is Edit-only. The words live in edit/startingText.js, are reached through the
edit tools, and are in NO shared source, NOT in page-view.html (the published bundle) and NOT in a published file built from a demo project.
Run: python3 dev/run_tests.py test_starting_text_1251
Without a browser: the built page files, the page sources and publish.build.
"""
import re
import unittest

from _demo import DemoStore
from _paths import SRC
from clark import page, publish

PAGE_SRC = SRC / "clark" / "page" / "src"
DATA = PAGE_SRC / "edit" / "startingText.js"

# The slice's words, verbatim from the ruled list (~/ag/1251-starting-text.md), by template id.
WANT = {
    "text": {"empty": ["Write here."]},
    "text-image": {"caption": "Say what the picture shows.", "empty": ["Write here.", "Add a picture."]},
    "gallery": {"caption": "Say what the picture shows.", "empty": ["Add a picture."]},
    "image-caption": {"caption": "Say what the picture shows.", "empty": ["Add a picture."]},
    "quote": {"empty": ["Write what they said.", "Say who said it."]},
    "callout": {"empty": ["Write the one thing the reader must see."]},
    "contacts": {"empty": ["Add a person."]},
    "one-doc": {"empty": ["Add the file."]},
    "current-state": {"empty": ["Say where the project stands."]},
}
WORDS = sorted({w for t in WANT.values() for v in t.values() for w in ([v] if isinstance(v, str) else v)})


def listed():
    """The data file's list, read as the page reads it: id -> {part: words}."""
    text = DATA.read_text(encoding="utf-8")
    body = text[text.index("export const STARTING_TEXT"):text.index("};", text.index("export const STARTING_TEXT"))]
    out = {}
    for m in re.finditer(r'"([a-z-]+)": \{ (.*?) \},', body):
        parts = {}
        for pm in re.finditer(r'(caption|empty): (\[[^\]]*\]|"[^"]*")', m.group(2)):
            vals = re.findall(r'"([^"]*)"', pm.group(2))
            parts[pm.group(1)] = vals if pm.group(2).startswith("[") else vals[0]
        out[m.group(1)] = parts
    return out


class TheList(unittest.TestCase):
    def test_the_list_is_the_ruled_words_verbatim_keyed_by_template_id(self):
        self.assertEqual(listed(), WANT)

    def test_every_listed_id_is_a_template_in_the_library(self):
        lib = (PAGE_SRC / "logic" / "templates.js").read_text(encoding="utf-8")
        for tid in WANT:
            self.assertIn(f'id: "{tid}"', lib, tid)

    def test_the_publish_switch_is_one_constant_that_shows_the_words_as_written(self):
        text = DATA.read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"export const (\w*PUBLISH\w*) = (\w+);", text), [("HIDE_STARTING_TEXT_ON_PUBLISH", "false")])

    def test_header_and_text_starts_with_the_title_Header(self):
        lib = (PAGE_SRC / "logic" / "templates.js").read_text(encoding="utf-8")
        m = re.search(r'\{ id: "current-state", name: "([^"]+)", kind: "text", fit: \[[^\]]*\], type: "text", title: "([^"]+)"', lib)
        self.assertEqual(m.groups(), ("Header and Text", "Header"))


class NotInTheShared(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        page.ensure_built()
        cls.view = page.VIEW_PAGE.read_text(encoding="utf-8")
        cls.edit = page.PAGE.read_text(encoding="utf-8")

    def test_the_published_bundle_holds_none_of_the_words(self):
        for w in WORDS:
            self.assertNotIn(w, self.view, w)

    def test_the_words_are_in_no_shared_source(self):
        for p in PAGE_SRC.rglob("*"):
            if p.suffix not in (".js", ".jsx", ".css", ".json") or "edit" in p.relative_to(PAGE_SRC).parts:
                continue
            text = p.read_text(encoding="utf-8")
            for w in WORDS:
                self.assertNotIn(w, text, f"{w!r} in shared source {p.relative_to(PAGE_SRC)}")

    def test_the_editor_build_holds_the_words(self):
        for w in WORDS:
            self.assertIn(w, self.edit, w)

    def test_a_published_file_from_a_demo_project_holds_none_of_the_words(self):
        demo = DemoStore()
        self.addCleanup(demo.close)
        body = publish.build(demo.store, "ABC", now="2030-01-15")["body"].decode("utf-8")
        for w in WORDS:
            self.assertNotIn(w, body, w)

    def test_the_check_can_fail(self):
        # a word the editor draws only is in the editor build and not the published one
        self.assertIn("Visible to client", self.edit)
        self.assertNotIn("Visible to client", self.view)


if __name__ == "__main__":
    unittest.main()
