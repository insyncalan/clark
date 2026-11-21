"""Row 1364, slice 2: the font colour classes in the published file's stylesheet and the other two cleaners.

Contrast: each of the six colours (from the token the class names) on the surface keeps 4.5:1 in light and in every dark block.
Run: python3 dev/run_tests.py test_font_colour_1364
"""
import json
import pathlib
import re
import shutil
import subprocess
import tempfile
import unittest

from _paths import ROOT
from test_dark_contrast import dark_blocks, ratio

from clark import publish

TOKENS = (ROOT / "src" / "clark" / "brand" / "tokens.css").read_text(encoding="utf-8")
CSS = (ROOT / "src" / "clark" / "page" / "shell.css").read_text(encoding="utf-8")
FLOOR = 4.5
WANT = {"grey": "--text-muted", "brand": "--brand-blue", "red": "--tone-red-text", "amber": "--tone-amber-text",
        "green": "--tone-green-text", "blue": "--tone-blue-text"}
JS = (ROOT / "src" / "clark" / "page" / "src" / "core" / "richHtml.js").read_text(encoding="utf-8")


def light_tokens():
    m = re.search(r":root\s*\{(.*?)\n\s*\}", TOKENS, re.S)
    got = {n: v.upper() for n, v in re.findall(r"(--[\w-]+):\s*(#[0-9A-Fa-f]{6})\b", m.group(1))}
    got["--surface"] = "#FFFFFF"          # tokens.css first line: --surface: #fff
    return got


class Stylesheet(unittest.TestCase):
    def test_each_class_is_one_token_and_no_hex(self):
        for name, token in WANT.items():
            self.assertEqual(re.findall(r"(?m)^\.rt-c-%s \{([^}]*)\}" % name, CSS), [f" color: var({token}); "])
        for sel in (r":root\[data-theme=dark\] \.rt-c-brand", r"@media \(prefers-color-scheme: dark\) \{ :root\[data-theme=auto\] \.rt-c-brand"):
            self.assertRegex(CSS, sel + r" \{ color: var\(--brand-blue-strong\); \}")
        self.assertEqual(len(re.findall(r"(?m)^\.rt-c-[a-z]+ \{", CSS)), 6)

    def test_published_page_carries_the_classes(self):
        from clark import page
        html = page.page_html()
        for name in WANT:
            self.assertIn(f".rt-c-{name} {{", html)


class Contrast(unittest.TestCase):
    def test_light(self):
        t = light_tokens()
        for name, token in WANT.items():
            r = ratio(t[token], t["--surface"])
            print(f"1364 {name} on surface, light: {r:.2f}:1")
            self.assertGreaterEqual(r, FLOOR, name)

    def test_every_dark_block(self):
        blocks = dark_blocks(TOKENS)
        self.assertTrue(blocks)
        for b in blocks:
            for name, token in WANT.items():
                token = "--brand-blue-strong" if name == "brand" else token      # the dark rule above
                r = ratio(b.get(token) or light_tokens()[token], b["--surface"])
                print(f"1364 {name} on surface, dark: {r:.2f}:1")
                self.assertGreaterEqual(r, FLOOR, name)


class PublishCleaner(unittest.TestCase):
    def test_colour_class_kept_alone(self):
        for name in WANT:
            self.assertEqual(publish.clean_html(f'<p><span class="rt-c-{name}">x</span></p>'), f'<p><span class="rt-c-{name}">x</span></p>')

    def test_anything_else_is_dropped(self):
        for src in ('<span class="rt-c-pink">x</span>', '<span class="rt-c-red extra">x</span>', '<span class="RT-C-RED">x</span>',
                    '<span style="color:#f00">x</span>', '<span class="chip">x</span>', '<span>x</span>'):
            self.assertEqual(publish.clean_html(src), "<span>x</span>", src)
        self.assertEqual(publish.clean_html('<span class="rt-c-red" style="color:#f00" id="i" onclick="a()">x</span>'),
                         '<span class="rt-c-red">x</span>')

    def test_colour_class_only_survives_on_a_span(self):
        for tag in ("p", "strong", "em", "a", "li", "blockquote"):
            got = publish.clean_html(f'<{tag} class="rt-c-red">x</{tag}>')
            self.assertNotIn("rt-c-", got, tag)

    def test_last_class_wins_like_the_page(self):
        self.assertEqual(publish.clean_html('<span class="rt-c-blue" class="x">x</span>'), "<span>x</span>")


SCRIPT = """
import { toHtml } from "./richHtml.js";
const m = (text, marks) => ({ content: [{ type: "paragraph", content: [{ type: "text", text, marks }] }] });
const c = (colour) => ({ type: "fontColour", attrs: { colour } });
console.log(JSON.stringify([
  toHtml(m("a<b", [c("red"), { type: "bold" }])),
  toHtml(m("x", [c("pink")])), toHtml(m("x", [c("RED")])), toHtml(m("x", [{ type: "fontColour" }])), toHtml(m("x", [c("red extra")])),
  toHtml(m("x", [c("blue"), { type: "link", attrs: { href: "https://x.example/" } }, { type: "strike" }, { type: "italic" }])),
  ...["grey", "brand", "red", "amber", "green", "blue"].map((n) => toHtml(m("t", [c(n)]))),
]));
"""


class ToHtml(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("node"):
            raise unittest.SkipTest("needs node")

    def test_colour_mark_becomes_the_class_span_in_a_fixed_order(self):
        core = ROOT / "src" / "clark" / "page" / "src" / "core"
        done = subprocess.run(["node", "--input-type=module", "-e", SCRIPT], cwd=core, capture_output=True, text=True, check=True)
        got = json.loads(done.stdout)
        self.assertEqual(got[0], '<p><strong><span class="rt-c-red">a&lt;b</span></strong></p>')
        self.assertEqual(got[1:5], ["<p>x</p>"] * 4)               # not in the set: no colour, the text stays
        self.assertEqual(got[5], '<p><a href="https://x.example/" rel="noopener noreferrer"><em><s><span class="rt-c-blue">x</span></s></em></a></p>')
        self.assertEqual(got[6:], [f'<p><span class="rt-c-{n}">t</span></p>' for n in WANT])

    def test_emission_itself_drops_an_unknown_colour(self):
        # cleanHtml would strip a stray class later, so read richHtml's own output: its cleaner is swapped for a pass-through in a copy
        core = ROOT / "src" / "clark" / "page" / "src" / "core"
        with tempfile.TemporaryDirectory() as tmp:
            (pathlib.Path(tmp) / "core").mkdir()
            (pathlib.Path(tmp) / "logic").mkdir()
            (pathlib.Path(tmp) / "package.json").write_text('{"type":"module"}')
            (pathlib.Path(tmp) / "logic" / "cleanHtml.js").write_text("export const cleanHtml = (s) => s;")
            shutil.copy(core / "richHtml.js", pathlib.Path(tmp) / "core" / "richHtml.js")
            script = SCRIPT
            done = subprocess.run(["node", "--input-type=module", "-e", script], cwd=pathlib.Path(tmp) / "core", capture_output=True, text=True, check=True)
        got = json.loads(done.stdout)
        self.assertEqual(got[1:5], ["<p>x</p>"] * 4)
        self.assertEqual(got[0], '<p><strong><span class="rt-c-red">a&lt;b</span></strong></p>')


if __name__ == "__main__":
    unittest.main()
