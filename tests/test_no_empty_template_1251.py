"""Row 1251: no template adds an empty header, description or image. What Add makes (logic/templates.js plan) is read by node for every template in
the box and every built-in: a title with words, a name and a description with words; every body part the template starts without is covered by a
prompt in edit/startingText.js (or by the template's own hint, named below); every picture template draws a sample picture in an empty slot.
Run: python3 dev/run_tests.py test_no_empty_template_1251
Without a browser: node and the page sources. The sample on the page itself is tests/test_sample_slot_1251.py.
"""
import json
import re
import subprocess
import unittest

from _paths import SRC

PAGE_SRC = SRC / "clark" / "page" / "src"
LIB = PAGE_SRC / "logic" / "templates.js"
START = PAGE_SRC / "edit" / "startingText.js"
EDIT = PAGE_SRC / "edit" / "templates"

# Templates with no entry in STARTING_TEXT: each draws its own hint or its own live numbers (needle must be in the Edit part).
OWN_WORDS = {
    "report-headline": ("ReportHeadline.jsx", "{HINT}"),
    "full-image": ("FullImage.jsx", "{W.hint}"),
    "glance-template": ("GlanceTemplate.jsx", None),      # three live counts: not a blank box
}
PICTURE_TYPES = {"imagecap": ("ImageCap.jsx", "sample={classicLook()}"), "textimage": ("TextImage.jsx", "sample={classicLook()}"),
                 "gallery": ("Gallery.jsx", "samplePicture(n)")}


def added():
    """[{id, type, title, name, description, body, kind}] for each template in the box and each built-in, as Add makes it (Classic page)."""
    script = (f'globalThis.document = {{ getElementById: (i) => (i === "theme" ? {{}} : null) }}; import("{LIB.as_uri()}").then((T) => {{ const out = [];'
              ' for (const t of [...T.TEMPLATES, ...T.BUILT_INS]) { const id = t.id; const sections = t.builtIn ? [{ id: "S1", type: "text", title: "x", beside: 0 }] : [{ id: "S1", type: "text", title: "x", beside: 0 }];'
              ' const p = T.plan(sections, id, "S1", false); out.push({ id, ok: p.ok, message: p.message || "", values: p.ok ? p.requests[0].values : null, name: t.name, description: t.description, kind: t.kind, body: t.body }); }'
              ' console.log(JSON.stringify(out)); });')
    got = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=60)
    assert got.returncode == 0, got.stderr
    return json.loads(got.stdout)


def prompts():
    text = START.read_text(encoding="utf-8")
    body = text[text.index("export const STARTING_TEXT"):text.index("};", text.index("export const STARTING_TEXT"))]
    return {m.group(1): re.findall(r'"([^"]*)"', m.group(2)) for m in re.finditer(r'"([a-z0-9-]+)": \{ (.*?) \},', body)}


class NoEmptyTemplate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.all = added()
        cls.ok = [t for t in cls.all if t["ok"]]

    def test_the_check_reads_every_template_in_the_box_and_none_is_refused(self):
        self.assertGreaterEqual(len([t for t in self.all if not t["id"].startswith("built-in-")]), 24)
        self.assertEqual([(t["id"], t["message"]) for t in self.all if not t["ok"] and not t["id"].startswith("built-in-")], [])

    def test_each_template_adds_a_header_with_words(self):
        for t in self.ok:
            title = t["values"]["title"]
            self.assertTrue(title.strip(), t["id"])
            self.assertNotEqual(title.strip().lower(), "title", t["id"])

    def test_each_template_has_a_name_and_a_description_with_words(self):
        for t in self.ok:
            if t["id"].startswith("built-in-"):
                continue      # the built-ins are named by the section they restore
            self.assertTrue((t["name"] or "").strip(), t["id"])
            self.assertTrue((t["description"] or "").strip(), t["id"])

    def test_a_template_that_starts_without_a_body_has_a_prompt_or_its_own_words(self):
        have = prompts()
        for t in self.ok:
            tid = t["id"]
            if tid.startswith("built-in-") or "body" in t["values"] or t["body"]:
                continue      # a template that starts with a body (Work items, Plan summary) carries it
            if tid in OWN_WORDS:
                continue
            self.assertTrue(have.get(tid) and all(w.strip() for w in have[tid]), f"{tid} adds an empty part with no prompt")

    def test_the_own_words_templates_draw_them(self):
        for tid, (name, needle) in OWN_WORDS.items():
            text = (EDIT / name).read_text(encoding="utf-8")
            self.assertIn(needle or "tpl-", text, tid)

    def test_no_prompt_is_blank(self):
        have = prompts()
        self.assertGreaterEqual(len(have), 22)
        for tid, words in have.items():
            self.assertTrue(words and all(w.strip() for w in words), tid)

    def test_each_picture_template_draws_a_sample_in_an_empty_slot(self):
        types = {t["id"]: t["values"] for t in self.ok}
        found = {v["type"] for v in types.values()} & set(PICTURE_TYPES)
        self.assertEqual(found, set(PICTURE_TYPES))
        for typ, (name, needle) in PICTURE_TYPES.items():
            self.assertIn(needle, (EDIT / name).read_text(encoding="utf-8"), typ)
        self.assertIn("samplePicture(0)", (EDIT / "FullImage.jsx").read_text(encoding="utf-8"))

    def test_a_picture_template_does_not_start_with_a_stored_picture_or_blank_one(self):
        for t in self.ok:
            if t["values"] and t["values"]["type"] in PICTURE_TYPES:
                body = t["values"].get("body", "")
                self.assertNotIn("data:image", body, t["id"])


if __name__ == "__main__":
    unittest.main()
