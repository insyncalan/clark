"""#438 row 28 (HIGH), rows 30 and 32: the PDF with no extra software. The Publish box's PDF tick opens the browser's own print box
on the published page, and the published page prints itself: its tabs one after another, no controls, light, with a page number.

Run: python3 dev/run_tests.py test_pdf_print
The Source and Words classes need no browser (they read the page's files and run the pure logic in node, which is skipped when node is not
on the machine). The Browser class needs headless Chrome (it fails, never skips, without it) and runs at 1400 and 900 px, light and dark.
Why the page prints, and clark does not: nothing is printed by a program clark starts, so no Chrome is needed on the computer, and what
is printed is only what the published page draws (the file has already been through the publish checks). The server-side PDF of PR 242
(pdf.py, publish_pdf.py) is still in the code, and the box no longer asks for it.
"""
import json
import re
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from _demo import USER, DemoStore
from _paths import ROOT
from clark import page, publish
from test_server import chrome, wait
from test_work_filters import need_chrome
from test_work_items import page_target
from test_published_work_no_add import open_page

SRC = ROOT / "src" / "clark" / "page"
PAGE_SRC = SRC / "src"
TODAY = "2026-10-28"
EMPTY_BRANDING = tempfile.mkdtemp(prefix="clark-no-brand-")
VARIANTS = [(w, s) for w in (1400, 900) for s in ("light", "dark")]
TICK_WORDS = "The page as it prints: its tabs one after another, no controls."
NOTE_WORDS = "Your browser’s print box opens; choose Save as PDF."


def tearDownModule():
    shutil.rmtree(EMPTY_BRANDING, ignore_errors=True)


def node(code):
    exe = shutil.which("node")
    if not exe:
        raise unittest.SkipTest("no node")
    done = subprocess.run([exe, "--input-type=module", "-e", code], capture_output=True, text=True, timeout=60)
    if done.returncode != 0:
        raise AssertionError(done.stderr)
    return json.loads(done.stdout)


def logic(expr):
    path = (PAGE_SRC / "logic" / "printView.js").as_uri()
    return node(f"import * as P from {json.dumps(path)}; console.log(JSON.stringify({expr}));")


def css_block(css, opener):
    """The text of the `opener {...}` block (braces matched) in `css`."""
    at = css.index(opener)
    depth, i = 0, css.index("{", at)
    start = i
    while True:
        depth += {"{": 1, "}": -1}.get(css[i], 0)
        i += 1
        if depth == 0:
            return css[start + 1:i - 1]


class Logic(unittest.TestCase):
    def test_the_tabs_print_in_the_page_order_with_use_cases_last_and_never_settings(self):
        self.assertEqual(logic('P.printTabs(["usecases","settings","milestones","work","dashboard"])'),
                         ["dashboard", "work", "milestones", "usecases"])

    def test_a_file_with_three_tabs_prints_three(self):
        self.assertEqual(logic('P.printTabs(["dashboard","work","milestones"])'), ["dashboard", "work", "milestones"])
        self.assertEqual(logic("P.printTabs([])"), [])

    def test_the_head_line_is_the_published_day_in_the_day_first_form(self):
        self.assertEqual(logic('P.publishedLine("2026-10-28")'), "Published 28-10-2026")
        self.assertEqual(logic('P.publishedLine("")'), "")
        self.assertEqual(logic('P.publishedLine("28/10/2026")'), "")

    def test_only_print_equals_one_starts_the_print_box(self):
        self.assertEqual(logic('[P.wantsPrint("?print=1"), P.wantsPrint(""), P.wantsPrint("?print=0"), P.wantsPrint("?x=1&print=1")]'),
                         [True, False, False, True])

    def test_the_print_address_adds_one_flag_to_the_one_visit_address(self):
        self.assertEqual(logic('P.printUrl("/preview?id=abc")'), "/preview?id=abc&print=1")
        self.assertEqual(logic('P.printUrl("/preview")'), "/preview?print=1")


class Source(unittest.TestCase):
    css = page.strip_css_comments((SRC / "shell.css").read_text(encoding="utf-8"))

    def test_the_print_rules_are_in_the_pages_own_style_and_name_no_address(self):
        block = css_block(self.css, "@media print")
        for need in ("print-all", ".top", ".toc", ".peek", ".fbar", ".wbar", "print-color-adjust", ".print-tab", "break-inside", "break-before"):
            self.assertIn(need, block, need)
        self.assertNotRegex(self.css, r"@media print[^{]*\{[^@]*(url\(|https?:|//)", "no address in the print rules")

    def test_the_page_is_a4_with_a_page_number_in_the_foot(self):
        page_rule = css_block(self.css, "@page")
        self.assertIn("size:A4", page_rule.replace(" ", ""))
        self.assertIn("counter(page)", page_rule)

    def test_print_mode_changes_nothing_on_screen(self):
        # every rule that hides a control is inside the print media block or under the print-all class
        outside = re.sub(r"@media print\s*\{(?:[^{}]|\{[^{}]*\})*\}", "", self.css)
        self.assertNotIn("print-all", outside.replace("@page", ""))

    def test_only_the_published_entry_asks_for_the_print_box(self):
        self.assertIn("printWhenAsked", (PAGE_SRC / "view.jsx").read_text(encoding="utf-8"))
        self.assertNotIn("printWhenAsked", (PAGE_SRC / "main.jsx").read_text(encoding="utf-8"))

    def test_the_stack_is_drawn_for_a_published_file_only(self):
        app = (PAGE_SRC / "components" / "App.jsx").read_text(encoding="utf-8")
        self.assertIn("fromFile.value && printing.value", app)
        self.assertIn("printTabs(tabs.value)", app)

    def test_the_use_cases_open_for_the_print(self):
        self.assertIn("open={printing.value}", (PAGE_SRC / "components" / "UseCasesTab.jsx").read_text(encoding="utf-8"))

    def test_the_box_no_longer_needs_chrome(self):
        for name in ("Publish.jsx", "publishState.js"):
            text = (PAGE_SRC / "edit" / name).read_text(encoding="utf-8")
            self.assertNotIn("Chrome", text, name)
            self.assertNotIn("pdfInfo", text, name)
        state = (PAGE_SRC / "edit" / "publishState.js").read_text(encoding="utf-8")
        self.assertNotIn("body.pdf", state, "the box asks the server for no PDF")

    def test_the_built_published_page_carries_the_print_and_the_editor_never_prints_itself(self):
        view = (SRC / "page-view.html").read_text(encoding="utf-8")
        self.assertIn("beforeprint", view)
        self.assertIn("print-all", view)
        self.assertNotIn("/api/preview", view, "the published page has no route")

    def test_the_published_file_holds_the_print_and_no_new_address(self):
        demo = DemoStore()
        folder = tempfile.mkdtemp(prefix="clark-pub-")
        self.addCleanup(demo.close)
        self.addCleanup(shutil.rmtree, folder, True)
        path = Path(publish.publish(demo.store, "ABC", folder, by_user=USER, now=TODAY, branding=EMPTY_BRANDING)["path"])
        text = path.read_text(encoding="utf-8")
        self.assertIn("beforeprint", text)
        self.assertEqual(list(publish.outside_addresses(text)), [], "the print code adds no outside address")


class Words(unittest.TestCase):
    def test_the_tick_has_the_prototypes_words(self):
        jsx = (PAGE_SRC / "edit" / "Publish.jsx").read_text(encoding="utf-8")
        self.assertIn("Also a PDF", jsx)
        self.assertIn(TICK_WORDS, jsx)
        self.assertIn(NOTE_WORDS, jsx)
        self.assertNotIn("The client will see this page and the PDF.", jsx)

    def test_help_says_the_prototypes_words_in_both_places(self):
        text = (PAGE_SRC / "help" / "helpContent.json").read_text(encoding="utf-8")
        data = json.loads(text)
        flat = json.dumps(data, ensure_ascii=False)
        self.assertEqual(flat.count("**Also a PDF**"), 2, "the steps and the Publishing bullets both name the tick")
        self.assertIn("your browser’s print box opens on the page in a new tab, and you choose **Save as PDF**", flat)
        self.assertIn("untick Headers and footers", flat)
        self.assertNotIn("Chrome", flat)


class Browser(unittest.TestCase):
    """The published file, opened from disk, as the browser prints it (print media emulated; the beforeprint event is what Ctrl+P sends)."""

    def setUp(self):
        need_chrome()
        self.demo = DemoStore()
        self.folder = tempfile.mkdtemp(prefix="clark-pub-")
        self.addCleanup(self.demo.close)
        self.addCleanup(shutil.rmtree, self.folder, True)
        self.path = Path(publish.publish(self.demo.store, "ABC", self.folder, by_user=USER, now=TODAY, branding=EMPTY_BRANDING)["path"])

    def printed(self, cdp, sid):
        cdp.call("Emulation.setEmulatedMedia", {"media": "print", "features": [{"name": "prefers-color-scheme", "value": "dark"}]}, sid)
        cdp.js("window.dispatchEvent(new Event('beforeprint'))", sid)
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.print-tab')", sid)), "the stack was drawn")

    def test_the_tabs_are_stacked_in_order_with_no_controls_and_light(self):
        for width, scheme in VARIANTS:
            with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                sid = open_page(cdp, self.path.as_uri(), width, scheme)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.tab')", sid)))
                tabs = cdp.js("[...document.querySelectorAll('.tab')].map(t => t.textContent.trim())", sid)
                self.printed(cdp, sid)
                titles = cdp.js("[...document.querySelectorAll('.print-tab-title')].map(t => t.textContent.trim())", sid)
                self.assertEqual(titles, tabs, "the printed tabs are the file's tabs, in its order")
                if "Use Cases" in tabs:
                    self.assertEqual(titles[-1], "Use Cases", "Use Cases last")
                self.assertEqual(cdp.js("getComputedStyle(document.querySelector('.top')).display", sid), "none")
                self.assertEqual(cdp.js("document.querySelectorAll('.print-tab').length", sid), len(tabs))
                self.assertEqual(cdp.js("getComputedStyle(document.body).backgroundColor", sid), "rgb(255, 255, 255)", "light, whatever the computer prefers")
                self.assertEqual(cdp.js("document.querySelectorAll('.ucp:not([open])').length", sid), 0, "no use case is left closed")
                cdp.js("window.dispatchEvent(new Event('afterprint'))", sid)
                self.assertTrue(wait(lambda: cdp.js("!document.querySelector('.print-tab')", sid)), "back to one tab after the print")

    def test_the_print_stack_holds_only_text_the_page_already_draws(self):
        with chrome() as cdp:
            sid = open_page(cdp, self.path.as_uri(), 1400, "light")
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.tab')", sid)))
            seen = set()
            names = cdp.js("[...document.querySelectorAll('.tab')].map(t => t.textContent.trim())", sid) or []
            for i in range(len(names)):
                cdp.js(f"document.querySelectorAll('.tab')[{i}].click()", sid)
                self.assertTrue(wait(lambda: cdp.js(f"document.querySelectorAll('.tab')[{i}].getAttribute('aria-selected') === 'true'", sid)), f"{names[i]} is the open tab")
                time.sleep(0.3)      # the tab's page is drawn after the tab is marked, so read it only once it has settled
                cdp.js("document.querySelectorAll('.ucp').forEach(d => { d.open = true; })", sid)      # the print opens every use case, so a person could have opened each
                time.sleep(0.2)
                seen |= set(re.findall(r"[^\W\d_]{4,}", cdp.js("document.getElementById('main').innerText", sid) or ""))
            self.printed(cdp, sid)
            stacked = set(re.findall(r"[^\W\d_]{4,}", cdp.js("document.getElementById('main').innerText", sid) or ""))
            titled = {w for n in names for w in re.findall(r"[^\W\d_]{4,}", n)}      # the print gives each tab its name as a heading
            extra = {w for w in stacked - seen - titled if w.lower() not in ("published",)}
            self.assertEqual(extra, set(), "nothing in the print that no tab draws")

    def test_a_page_with_the_flag_opens_the_print_box_once_it_has_drawn_and_a_page_without_it_does_not(self):
        for flag, times in (("?print=1", 1), ("", 0)):
            with self.subTest(flag=flag), chrome() as cdp:
                sid = page_target(cdp)
                cdp.call("Page.enable", {}, sid)
                cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": "window.__printed = 0; window.print = function(){ window.__printed++ };"}, sid)
                cdp.call("Page.navigate", {"url": self.path.as_uri() + flag}, sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.tab')", sid)), "the page drew")
                if times:
                    self.assertTrue(wait(lambda: cdp.js("window.__printed === 1", sid), 20), "print() was asked for, once")
                else:
                    wait(lambda: cdp.js("window.__printed > 0", sid), 3)
                    self.assertEqual(cdp.js("window.__printed", sid), 0)


if __name__ == "__main__":
    unittest.main()
