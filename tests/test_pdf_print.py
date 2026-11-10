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
import sqlite3
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
TICK_WORDS = "The page as it prints: the tabs one after another, no controls, with the publication number in the foot"      # the prototype's (system/prototype/io.js:348)
NOTE_WORDS = "Your browser’s print box opens; choose Save as PDF. In the print box, untick Headers and footers, so the PDF carries no web address."


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


def css_block(css, opener, after=""):
    """The text of the `opener {...}` block (braces matched) in `css`: the last `opener` before the first `after` text, if one is given."""
    at = css.rindex(opener, 0, css.index(after)) if after else css.index(opener)
    depth, i = 0, css.index("{", at)
    start = i
    while True:
        depth += {"{": 1, "}": -1}.get(css[i], 0)
        i += 1
        if depth == 0:
            return css[start + 1:i - 1]


def _tasks(node):
    """Every dict under `node` that has an "id" and an "s" list (a how-to entry)."""
    if isinstance(node, dict):
        if "id" in node and isinstance(node.get("s"), list):
            yield node
        for v in node.values():
            yield from _tasks(v)
    elif isinstance(node, list):
        for v in node:
            yield from _tasks(v)


class Logic(unittest.TestCase):
    def test_the_tabs_print_in_the_page_order_with_use_cases_last_and_never_settings(self):
        self.assertEqual(logic('P.printTabs(["usecases","settings","milestones","work","dashboard"])'),
                         ["dashboard", "work", "milestones", "usecases"])

    def test_1065_a_tab_that_is_no_longer_offered_is_not_printed(self):
        self.assertEqual(logic('P.printTabs(["usecases","clientreport","milestones","work","dashboard"])'),
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

    def test_the_print_address_adds_the_flag_and_the_publication_number_to_the_one_visit_address(self):
        self.assertEqual(logic('P.printUrl("/preview?id=abc", 7)'), "/preview?id=abc&print=1&n=7")
        self.assertEqual(logic('P.printUrl("/preview")'), "/preview?print=1")
        self.assertEqual(logic('P.printUrl("/preview?id=abc", 0)'), "/preview?id=abc&print=1", "no number, no n")

    def test_the_number_asked_for_is_a_whole_number_and_nothing_else(self):
        self.assertEqual(logic('[P.numberAsked("?n=12"), P.numberAsked("?n=0"), P.numberAsked("?n=-3"), P.numberAsked("?n=1.5"), P.numberAsked("?n=%22%3Bx"), P.numberAsked("?n=1234567"), P.numberAsked("")]'),
                         [12, 0, 0, 0, 0, 0, 0])

    def test_the_foot_is_publication_n_dot_date_day_first_and_nothing_without_a_number(self):
        self.assertEqual(logic('P.footLine(7, "2026-10-28")'), "Publication 7 · 28-10-2026")
        self.assertEqual(logic('P.footLine(7, "")'), "Publication 7")
        self.assertEqual(logic('P.footLine(0, "2026-10-28")'), "")
        self.assertEqual(logic('P.footLine("7", "2026-10-28")'), "", "a number only")

    def test_the_foot_rule_is_one_bottom_left_margin_box_and_cannot_be_broken_out_of(self):
        rule = logic('P.footRule("Publication 7 · 28-10-2026")')
        self.assertEqual(rule, '@page { @bottom-left { content: "Publication 7 · 28-10-2026"; font: 13px Arial, sans-serif; } }')
        self.assertEqual(logic('P.footRule("")'), "")
        self.assertNotIn('"; }', logic('P.footRule("a\\"; } body { display: none } /*")')[len('@page { @bottom-left { content: "'):-len('"; font: 13px Arial, sans-serif; } }')])


class Source(unittest.TestCase):
    css = page.strip_css_comments((SRC / "shell.css").read_text(encoding="utf-8"))

    def test_the_printed_timeline_is_drawn_to_the_page_and_does_not_scroll(self):
        block = css_block(self.css, "@media print", "html.print-all, html.print-all body")
        self.assertRegex(block, r"html\.print-all \.mv-wrap \{[^}]*overflow: hidden[^}]*resize: none", "row 767: no sideways scroll or drag handle on paper")
        jsx = (PAGE_SRC / "components" / "MsTimeline.jsx").read_text(encoding="utf-8")
        self.assertIn("printing.value", jsx, "the timeline knows the page is printing")
        self.assertIn("PRINT_W / Math.max(1, dayNumber(end) - dayNumber(start))", jsx, "the whole span is fitted to the printed width")

    def test_the_hover_only_legend_button_is_not_printed(self):
        block = css_block(self.css, "@media print", "html.print-all, html.print-all body")
        hide = re.search(r"((?:html\.print-all [^{,]+,\s*)+html\.print-all [^{,]+)\{\s*display: none;", block).group(1)
        self.assertRegex(hide, r"html\.print-all \.mlg(?![\w-])", "the Legend help control is not content")

    def test_the_print_rules_are_in_the_pages_own_style_and_name_no_address(self):
        block = css_block(self.css, "@media print", "html.print-all, html.print-all body")
        for need in ("print-all", ".top", ".toc", ".peek", ".fbar", ".wbar", "print-color-adjust", ".print-tab", "break-inside", "break-before"):
            self.assertIn(need, block, need)
        self.assertNotRegex(self.css, r"@media print[^{]*\{[^@]*(url\(|https?:|//)", "no address in the print rules")

    def test_the_page_is_a4_with_a_page_number_in_the_foot(self):
        page_rule = css_block(self.css, "@page")
        self.assertIn("size:A4", page_rule.replace(" ", ""))
        self.assertIn("counter(page)", page_rule)
        self.assertIn("@bottom-right", page_rule)

    def test_the_on_screen_publication_line_is_not_printed_twice(self):
        self.assertIn("html.print-all .pubfoot", css_block(self.css, "@media print", "html.print-all, html.print-all body"))

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

    def test_the_foot_is_set_from_the_publication_and_the_date_when_the_browser_prints_and_taken_off_after(self):
        text = (PAGE_SRC / "stores" / "print.js").read_text(encoding="utf-8")
        self.assertIn("footRule(footLine(numberAsked(location.search) || publication.value, asAt.value))", text, "the number on the address wins")
        self.assertIn('window.addEventListener("beforeprint", () => set(true))', text)
        self.assertIn('window.addEventListener("afterprint", () => set(false))', text)

    def test_the_printed_page_comes_from_one_function_in_the_publish_state(self):
        state = (PAGE_SRC / "edit" / "publishState.js").read_text(encoding="utf-8")
        self.assertEqual(state.count("export function printSource("), 1)
        self.assertNotIn("previewRequest", state, "the print tab is the published bytes (item 465), not a second build")
        self.assertIn("body.print = true", state)
        self.assertIn("printSource(r.body, Number.isInteger(r.body.publication) ? r.body.publication : 0)", state)

    def test_the_box_sends_no_pdf_key_and_has_no_pdf_clash_keys(self):
        state = (PAGE_SRC / "edit" / "publishState.js").read_text(encoding="utf-8")
        self.assertNotIn("pdf_", state)
        self.assertNotIn("body.pdf", state)
        self.assertNotIn("pdf: true", state)
        self.assertIn("body.on_clash = s.choice", state, "the report's own clash answer stays")
        self.assertIn("Number.isInteger(b.publication)", state, "the number handling of the success line stays")

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
        entry = next(t for t in _tasks(data) if t["id"] == "save-as-a-pdf")
        steps = " ".join(entry["s"])
        self.assertIn("tick **Also a PDF**", steps)
        self.assertIn("untick Headers and footers", steps)
        self.assertIn("Use cases last", steps)
        self.assertNotIn("Chrome", " ".join(entry["s"]) + entry.get("n", "").replace("Checked in Google Chrome", ""), "no Chrome needed")
        self.assertIn("Checked in Google Chrome", entry["n"], "says which browser was checked")
        self.assertNotIn("needs Google Chrome", flat)


class Browser(unittest.TestCase):
    """The published file, opened from disk, as the browser prints it (print media emulated; the beforeprint event is what Ctrl+P sends)."""

    def setUp(self):
        need_chrome()
        self.demo = DemoStore()
        self.folder = tempfile.mkdtemp(prefix="clark-pub-")
        self.addCleanup(self.demo.close)
        self.addCleanup(shutil.rmtree, self.folder, True)
        self.shown = self.demo.action(description="Shown on the printed page")
        self.hidden = self.demo.action(description="Eye hidden zebra item")
        self.left_out = self.demo.action(description="Client invisible quokka item", client_visible=0)
        con = sqlite3.connect(str(self.demo.dir / "clark.db"))
        con.execute("INSERT INTO report_hidden (project, item_id) VALUES ('ABC', ?)", (self.hidden,))
        con.commit()
        con.close()
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
                self.assertEqual(titles, ["Dashboard", "Work items", "Milestones", "Use cases"], "every tab the file has, in print order, Use cases last")
                self.assertEqual(len(tabs), len(titles), "the file's tab bar has the same tabs")
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
            heads = cdp.js("[...document.querySelectorAll('.print-tab-title')].map(t => t.textContent.trim())", sid)
            titled = {w for n in heads for w in re.findall(r"[^\W\d_]{4,}", n)}      # the print gives each tab its name as a heading
            extra = {w for w in stacked - seen - titled if w.lower() not in ("published",)}
            self.assertEqual(extra, set(), "nothing in the print that no tab draws")

    def test_the_foot_carries_publication_n_and_the_date_while_printing_and_not_after(self):
        for width, scheme in VARIANTS:
            with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                sid = open_page(cdp, self.path.as_uri(), width, scheme)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.tab')", sid)))
                self.assertEqual(cdp.js("!!document.getElementById('print-foot')", sid), False, "no foot on screen")
                self.printed(cdp, sid)
                self.assertEqual(cdp.js("document.getElementById('print-foot').textContent", sid),
                                 '@page { @bottom-left { content: "Publication 1 · 28-10-2026"; font: 13px Arial, sans-serif; } }')
                cdp.js("window.dispatchEvent(new Event('afterprint'))", sid)
                self.assertTrue(wait(lambda: cdp.js("!document.getElementById('print-foot')", sid)), "taken off after the print")

    def test_the_printed_preview_shows_the_number_just_published_not_the_next(self):
        # The Publish box prints the bytes just published (item 465: the publish reply's print_url), not a second build. This test stands
        # a stale page in at /preview that carries the next number, 2, and the address carries the number it was given (&n=1): that is the
        # one the foot must show.
        text = self.path.read_text(encoding="utf-8")
        own = re.search(r',"publication":\{"n":1\}', text)
        self.assertTrue(own, "the published file carries its own number, 1")
        preview = Path(self.folder) / "preview.html"
        preview.write_text(text.replace(own.group(0), ',"publication":{"n":2}', 1), encoding="utf-8")
        bare = Path(self.folder) / "bare.html"
        bare.write_text(text.replace(own.group(0), "", 1), encoding="utf-8")
        cases = ((preview, "?n=1", 'content: "Publication 1 · 28-10-2026"'), (preview, "", 'content: "Publication 2 · 28-10-2026"'),
                 (bare, "?n=7", 'content: "Publication 7 · 28-10-2026"'), (bare, "", None), (bare, "?n=x", None))
        for path, query, want in cases:
            with self.subTest(file=path.name, query=query), chrome() as cdp:
                sid = open_page(cdp, path.as_uri() + query, 1400, "light")
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.tab')", sid)))
                self.printed(cdp, sid)
                foot = cdp.js("(document.getElementById('print-foot') || {}).textContent || ''", sid)
                if want:
                    self.assertIn(want, foot)
                else:
                    self.assertEqual(foot, "", "no number, no foot line")

    def test_left_out_and_hidden_rows_are_not_in_the_printed_page(self):
        for width, scheme in VARIANTS:
            with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                sid = open_page(cdp, self.path.as_uri(), width, scheme)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.tab')", sid)))
                self.printed(cdp, sid)
                body = cdp.js("document.body.innerText + ' ' + document.documentElement.outerHTML", sid)
                self.assertIn("Shown on the printed page", body, "a shown row is printed")
                self.assertNotIn("zebra", body)
                self.assertNotIn("quokka", body)

    def test_nothing_internal_is_in_the_print_stack(self):
        for width, scheme in VARIANTS:
            with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                sid = open_page(cdp, self.path.as_uri(), width, scheme)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.tab')", sid)))
                self.printed(cdp, sid)
                self.assertEqual(cdp.js("document.querySelectorAll('.de, #ask-panel, [data-publish], #profile-btn, #publish-dialog, [role=dialog]').length", sid), 0)
                self.assertEqual(cdp.js("document.querySelectorAll('a[href^=mailto]').length", sid), 0, "no mail link")
                printed = cdp.js("document.getElementById('main').innerText", sid)
                self.assertNotIn(USER, printed, "the name of the person who published")
                self.assertNotIn("Ask clark", printed)

    def test_the_printed_milestones_timeline_shows_its_marks_and_labels(self):
        # row 767: the line scrolls inside its box on screen, opened at today; on paper nothing can scroll, so a milestone far from today
        # left the printed box empty (only the Legend was left). Printed, the line is drawn to the page and every mark is inside the box.
        probe = """(() => {
          const out = {};
          for (const wrap of document.querySelectorAll('.print-tab .mv-wrap')) {
            const w = wrap.getBoundingClientRect();
            const inside = (el) => { const r = el.getBoundingClientRect(); return r.width > 0 && r.left >= w.left - 1 && r.right <= w.right + 1; };
            const marks = [...wrap.querySelectorAll('.mv-mk')], labs = [...wrap.querySelectorAll('.mv-lab')];
            out[wrap.closest('.print-tab').querySelector('.print-tab-title').textContent] = { marks: marks.length, labs: labs.length,
              marksIn: marks.filter(inside).length, labsIn: labs.filter(inside).length, strip: wrap.querySelector('.mv-strip').getBoundingClientRect().width, box: w.width };
          }
          return JSON.stringify(out);
        })()"""
        for width, scheme in VARIANTS:
            with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                sid = open_page(cdp, self.path.as_uri(), width, scheme)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.tab')", sid)))
                self.printed(cdp, sid)
                time.sleep(0.6)      # the labels are measured once they have drawn
                for page_width in (width, 703):      # the window, and the printed A4 page's own width
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": page_width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
                    time.sleep(0.4)
                    got = json.loads(cdp.js(probe, sid))
                    self.assertIn("Milestones", got)
                    for name, g in got.items():
                        self.assertGreater(g["marks"], 0, f"{name} draws a mark")
                        self.assertEqual(g["marksIn"], g["marks"], f"{name}: every mark is inside the printed box at {page_width}: {g}")
                        self.assertEqual(g["labsIn"], g["labs"], f"{name}: every label is inside the printed box at {page_width}: {g}")
                        self.assertLessEqual(g["strip"], g["box"] + 1, f"{name}: the line is no wider than its box (nothing to scroll)")
                cdp.js("window.dispatchEvent(new Event('afterprint'))", sid)
                self.assertTrue(wait(lambda: cdp.js("!document.querySelector('.print-tab')", sid)))

    def test_the_printed_milestone_marks_are_drawn_shapes_with_a_colour(self):
        # #1012: the milestone graphics on paper. Every mark is an svg with a visible width and at least one shape that is filled or stroked.
        probe = """JSON.stringify([...document.querySelectorAll('.print-tab .mv-mk svg')].map((s) => { const r = s.getBoundingClientRect();
          const shapes = [...s.querySelectorAll('circle, path')].filter((e) => { const c = getComputedStyle(e); return (c.fill !== 'none' && c.fill !== 'rgba(0, 0, 0, 0)') || (c.stroke !== 'none' && c.strokeWidth !== '0px'); });
          return [Math.round(r.width), shapes.length]; }))"""
        with chrome() as cdp:
            sid = open_page(cdp, self.path.as_uri(), 1400, "light")
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.tab')", sid)))
            self.printed(cdp, sid)
            time.sleep(0.6)
            got = json.loads(cdp.js(probe, sid))
            self.assertTrue(got, "the printed milestones draw marks")
            for width, shapes in got:
                self.assertGreater(width, 4)
                self.assertGreater(shapes, 0, "a mark has a painted shape")

    def test_the_printed_stack_is_light_whatever_the_page_theme_and_the_computer_prefer(self):
        # row 767: the PDF is light only. Every colour that is drawn in the stack is the same in the print of a dark computer as in a light one
        # (the published file carries no data-theme, and the print block sets color-scheme: light), whole stack, not just the body.
        probe = """(() => { const out = []; for (const el of document.querySelectorAll('#main, #main *')) { const cs = getComputedStyle(el);
          if (!el.getBoundingClientRect().width) continue; out.push([el.tagName + '.' + el.className, cs.backgroundColor, cs.color, cs.borderTopColor].join('|')); }
          return JSON.stringify(out); })()"""
        for width in (1400, 900):
            seen = {}
            for scheme in ("light", "dark"):
                with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                    sid = open_page(cdp, self.path.as_uri(), width, scheme)
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.tab')", sid)))
                    cdp.call("Emulation.setEmulatedMedia", {"media": "print", "features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
                    cdp.js("document.documentElement.dataset.theme = 'dark'" if scheme == "dark" else "0", sid)      # even a page that was given the dark theme prints light
                    cdp.js("window.dispatchEvent(new Event('beforeprint'))", sid)
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.print-tab')", sid)))
                    time.sleep(0.6)
                    self.assertEqual(cdp.js("getComputedStyle(document.body).backgroundColor", sid), "rgb(255, 255, 255)")
                    seen[scheme] = json.loads(cdp.js(probe, sid))
            self.assertTrue(seen["light"], "something was drawn")
            self.assertEqual(seen["dark"], seen["light"], f"the dark print has the colours of the light print at {width}")

    def test_the_print_leaves_off_the_empty_use_case_lines_and_their_headings(self):
        # row 767: the print opens every use case, so the screen's closed cards showed 'No next steps are shared...' blocks on paper. The
        # lines (and the heading above each) are left off the paper; no word is added or changed.
        for width, scheme in VARIANTS:
            with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                sid = open_page(cdp, self.path.as_uri(), width, scheme)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.tab')", sid)))
                self.printed(cdp, sid)
                time.sleep(0.4)
                got = json.loads(cdp.js("""JSON.stringify({ none: document.querySelectorAll('.print-tab .ucp-none').length,
                  shown: [...document.querySelectorAll('.print-tab .ucp-none')].filter(e => e.getBoundingClientRect().height > 0).length,
                  heads: [...document.querySelectorAll('.print-tab .ucp-body h2')].filter(h => h.nextElementSibling && h.nextElementSibling.matches('.ucp-none') && h.getBoundingClientRect().height > 0).length,
                  kept: (() => { const b = document.querySelector('.print-tab .ucp-body'); if (!b) return -1; const h = document.createElement('h2'); h.textContent = 'Probe heading';
                    const u = document.createElement('ul'); u.innerHTML = '<li>Probe step</li>'; b.append(h, u); return h.getBoundingClientRect().height > 0 ? 1 : 0; })(),
                  text: document.getElementById('main').innerText })""", sid))
                self.assertGreater(got["none"], 0, "the demo use case has no steps and no milestones")
                self.assertEqual(got["shown"], 0, "no empty-list line on the paper")
                self.assertEqual(got["heads"], 0, "no heading left with nothing under it")
                self.assertNotIn("No next steps are shared", got["text"])
                self.assertEqual(got["kept"], 1, "a heading with a list under it is still printed (the rule hides only the empty lines)")
                cdp.js("window.dispatchEvent(new Event('afterprint'))", sid)
                self.assertTrue(wait(lambda: cdp.js("!document.querySelector('.print-tab')", sid)))

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
