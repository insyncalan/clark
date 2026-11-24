"""Row 1260 B5: the page never opens a system dialog (alert, confirm, prompt); it uses in-page boxes.

A source scan of every .js, .jsx and .html file under src/clark/page. A call is `alert(`, `confirm(`, `prompt(`, also
written `window.alert(`, `globalThis.confirm(` or `window["prompt"](`. Comments are dropped first; the name of a
variable or a property (`confirm: true`, `pub-confirm`, `confirmOverwrite(`) is not a call.

Run: python3 dev/run_tests.py test_no_system_dialogs_1260
"""
import re
import unittest

from _paths import ROOT

PAGE = ROOT / "src" / "clark" / "page"
CALL = re.compile(
    r"""(?:(?<![\w$.\-])|(?<=\bwindow\.)|(?<=\bglobalThis\.)|(?<=\bself\.))(?:alert|confirm|prompt)\s*\("""
    r"""|\b(?:window|globalThis|self)\s*\[\s*['"](?:alert|confirm|prompt)['"]\s*\]"""
)
BLOCK = re.compile(r"/\*.*?\*/|<!--.*?-->", re.S)
LINE = re.compile(r"(?m)(?:^|(?<=\s))//.*$")


def files():
    return sorted(p for p in PAGE.rglob("*") if p.suffix in (".js", ".jsx", ".html") and p.is_file())


def calls_in(text):
    text = BLOCK.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)
    text = LINE.sub("", text)
    return [(text.count("\n", 0, m.start()) + 1, m.group(0)) for m in CALL.finditer(text)]


class NoSystemDialogs(unittest.TestCase):
    def test_the_scan_reads_the_page_sources(self):
        self.assertGreater(len(files()), 100)

    def test_no_alert_confirm_or_prompt_call_in_the_page(self):
        found = [f"{p.relative_to(ROOT)}:{n}: {c}" for p in files() for n, c in calls_in(p.read_text(encoding="utf-8"))]
        self.assertEqual([], found)

    def test_the_scan_catches_each_form_and_skips_names_and_comments(self):
        for bad in ("alert('x')", "if (confirm(\"sure\")) go()", "window.prompt('n')", "globalThis.alert (1)", "window['confirm']('x')"):
            self.assertTrue(calls_in(bad), bad)
        for ok in ("// alert('x')", "/* confirm(1) */", "{ confirm: true }", "confirmOverwrite(v)", "id=\"pub-confirm\"",
                   "x.confirm(1)", "<!-- prompt(1) -->", "role=\"alert\""):
            self.assertEqual([], calls_in(ok), ok)


if __name__ == "__main__":
    unittest.main()
