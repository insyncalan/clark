"""#926, the Gantt tab and the project setting, page side: the tab appears only when the setting says so, carries the project's own name, routes like
the other pages (address, Back and Forward), stays in view in the tab row at 1400 and 900 px, and is renamed in Edit (click the label, Enter or
click away saves, Esc cancels, Undo toast); Settings > Gantt has the two ticks and the Tab name. Fictional data.

Run: python3 dev/run_tests.py test_gantt_tab
The source checks (the wire format in one place, the fixed lists, the words) need no browser. The page is mounted on a bare page with the shell
styles (tests/fixtures/gantt_tab_demo.jsx, a stand-in for the server), by the same route as test_gantt_table.py. Chrome is required for the
second half: those tests fail, never skip, without it.
"""
import contextlib
import json
import re
import sys
import tempfile
import unittest
from _editor_checks import for_url
from pathlib import Path

from _paths import ROOT, SRC, TOOLS

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402

from test_server import Running, chrome, wait  # noqa: E402

PAGE_SRC = SRC / "clark" / "page" / "src"
DEMO = ROOT / "tests" / "fixtures" / "gantt_tab_demo.jsx"
_PAGE = {}


def read(*parts):
    return (PAGE_SRC.joinpath(*parts)).read_text(encoding="utf-8")


def lit(x):
    return json.dumps(x)


class Source(unittest.TestCase):
    """No browser: how the page is put together."""

    def test_the_wire_format_is_written_in_one_place(self):
        names = ("show_gantt_editor", "show_gantt_client", "gantt_tab_name")
        for f in PAGE_SRC.rglob("*.js*"):
            if f.parent.name == "help" or f.name in ("ganttTab.js", "helpContent.json"):
                continue
            text = f.read_text(encoding="utf-8")
            for n in names:
                self.assertNotIn(n, text, f"{f.relative_to(PAGE_SRC)} spells {n}: only gantt/ganttTab.js may")
        one = read("gantt", "ganttTab.js")
        for n in names:
            self.assertIn(n, one)

    def test_the_view_is_routed_like_the_others(self):
        self.assertIn('"usecases", "gantt", "settings", "published"]', read("router.js"))
        self.assertIn("get gantt()", read("stores", "report.js"))
        self.assertIn("gantt: GanttView", read("components", "App.jsx"))       # the page joined to its data (GanttView mounts GanttPage with a host)
        self.assertIn('from "../gantt/components/GanttView.jsx"', read("components", "App.jsx"))

    def test_the_setting_is_saved_like_the_freshness_days(self):
        change = read("gantt", "ganttTab.js")
        self.assertIn('kind: "projects", op: "update"', change)
        for part in ("GanttSetting", "GanttTabName"):
            self.assertIn(part, read("edit", "index.js"))
        self.assertIn("requestFor(", read("edit", "GanttSetting.jsx"))
        self.assertIn("requestFor(", read("edit", "GanttTabName.jsx"))

    def test_the_new_words_are_on_the_page(self):
        card = read("edit", "GanttSetting.jsx")
        for words in ("Show the Gantt to me", "Show the Gantt to the client", "Tab name"):
            self.assertIn(words, card)

    def test_colours_are_tokens(self):
        for f in ("edit/GanttSetting.jsx", "edit/GanttTabName.jsx", "gantt/components/GanttPage.jsx", "gantt/ganttTab.js"):
            code = re.sub(r"//[^\n]*", "", read(*f.split("/")))      # the issue numbers in the header comments are not colours
            self.assertIsNone(re.search(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b", code), f)
        css = (PAGE_SRC.parent / "shell.css").read_text(encoding="utf-8")
        for rule in re.findall(r"^\.(?:top \.tab-name|fld-tick)[^\n]*$", css, re.M):
            self.assertIsNone(re.search(r"#[0-9a-fA-F]{3,8}\b", rule), rule)


def page_html():
    if "html" not in _PAGE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "t.js"
            done = esbuild.run(["--bundle", "--format=iife", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(DEMO), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            script = out.read_text(encoding="utf-8").replace("</script", "<\\/script")
        css = (build_page.TOKENS.read_text(encoding="utf-8") + (build_page.PAGE / "shell.css").read_text(encoding="utf-8")).replace("</style", "<\\/style")
        _PAGE["html"] = ('<!doctype html>\n<html lang="en-GB" data-theme="auto"><head><meta charset="utf-8">'
                         '<meta name="viewport" content="width=device-width, initial-scale=1"><title>t</title>'
                         f'<style>\n{css}</style></head>\n<body><div id="root"></div>\n<script>{script}</script>\n</body></html>\n')
    return _PAGE["html"]


class Tab(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack = contextlib.ExitStack()
        cls.server = Running(page_html=page_html)
        cls.stack.callback(cls.server.close)
        cls.cdp = cls.stack.enter_context(chrome())
        tid = next(t["targetId"] for t in cls.cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        cls.sid = cls.cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cls.cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, cls.sid)

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    def load(self, over=None, edit=False, width=1400):
        self.cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
        self.cdp.call("Page.navigate", {"url": for_url(f"http://127.0.0.1:{self.server.port}/#dashboard&p=DEMO")}, self.sid)
        self.assertTrue(wait(lambda: self.cdp.js("!!(window.G && window.G.mount)", self.sid)), "the test bundle ran")
        self.go(f"G.mount({lit(over or {})}, {lit(edit)})")

    def js(self, expr):
        return self.cdp.js(expr, self.sid)

    def go(self, expr):
        self.js(f"(function(){{ {expr}; }})()")
        self.cdp.call("Runtime.evaluate", {"expression": "new Promise(r => setTimeout(r, 150))", "awaitPromise": True}, self.sid)

    def state(self):
        return json.loads(self.js("JSON.stringify(G.state())"))

    def labels(self):
        return self.state()["tabs"]

    # ── the tab follows the setting ──

    def test_no_gantt_tab_while_the_setting_is_off(self):
        self.load()
        self.assertEqual(self.labels(), ["Dashboard", "Work items", "Milestones", "Use cases"])

    def test_the_editor_tick_adds_the_tab_with_the_project_name_for_it(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                self.load({"show_gantt_editor": 1}, width=width)
                self.assertEqual(self.labels(), ["Dashboard", "Work items", "Milestones", "Use cases", "Gantt"])
                self.go("G.set({ gantt_tab_name: 'Plan' })")
                self.assertIn("Plan", self.labels())

    def test_the_client_tick_alone_adds_nothing_to_the_editor(self):
        self.load({"show_gantt_client": 1})
        self.assertNotIn("Gantt", self.labels())

    def test_the_tab_opens_the_page_and_goes_in_the_address(self):
        self.load({"show_gantt_editor": 1})
        self.go("document.querySelector('.top .tab[data-view=gantt]').click()")
        s = self.state()
        self.assertEqual((s["view"], s["hash"]), ("gantt", "#gantt&p=DEMO"))
        self.assertEqual(self.js("document.querySelector('.top .tab[aria-selected=true]').dataset.view"), "gantt")
        self.assertTrue(self.js("!!document.querySelector('#gantt-page')"), "the Gantt page itself is open (the joined page, no longer a one-word stand-in)")

    def test_back_and_forward_step_through_the_gantt_page(self):
        self.load({"show_gantt_editor": 1})
        self.go("document.querySelector('.top .tab[data-view=gantt]').click()")
        self.go("history.back()")
        self.assertEqual(self.state()["view"], "dashboard")
        self.go("history.forward()")
        self.assertEqual(self.state()["view"], "gantt")

    def test_an_address_for_the_gantt_with_the_setting_off_opens_the_first_tab(self):
        self.load()
        self.go("location.hash = '#gantt&p=DEMO'")
        self.assertEqual(self.state()["view"], "dashboard")

    def test_the_open_tab_is_in_view_at_1400_and_900(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                self.load({"show_gantt_editor": 1, "gantt_tab_name": "Programme plan"}, width=width)
                self.go("document.querySelector('.top .tab[data-view=gantt]').click()")
                box = json.loads(self.js("""JSON.stringify((function(){
                    var t = document.querySelector('.top .tab[aria-selected=true]').getBoundingClientRect(), n = document.querySelector('.top .tabs').getBoundingClientRect();
                    return { left: t.left >= n.left - 1, right: t.right <= n.right + 1, page: document.documentElement.scrollWidth <= window.innerWidth };
                })())"""))
                self.assertEqual(box, {"left": True, "right": True, "page": True})

    # ── the name, in Edit ──

    def test_the_name_is_a_box_after_a_click_in_edit_and_enter_saves_with_an_undo(self):
        self.load({"show_gantt_editor": 1}, edit=True)
        self.go("document.querySelector('.top .tab[data-view=gantt]').click()")      # opens the page
        self.go("document.querySelector('.top .tab[data-view=gantt]').click()")      # the label of the open tab: the box
        self.assertTrue(self.js("!!document.querySelector('[data-gantt-tab-name]')"))
        self.go("var b = document.querySelector('[data-gantt-tab-name]'); b.value = 'Roadmap'; b.dispatchEvent(new Event('input', {bubbles: true}))")
        self.go("document.querySelector('[data-gantt-tab-name]').dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true}))")
        self.assertTrue(wait(lambda: "Roadmap" in self.labels()), "the tab shows the new name")
        self.assertEqual(self.js("G.sent.length"), 1)
        self.assertEqual(json.loads(self.js("JSON.stringify(G.sent[0].changes)")), {"gantt_tab_name": "Roadmap"})
        self.assertIn("Undo", self.js("document.body.innerText"))

    def test_escape_cancels_and_an_empty_name_is_refused(self):
        self.load({"show_gantt_editor": 1}, edit=True)
        self.go("document.querySelector('.top .tab[data-view=gantt]').click()")
        self.go("document.querySelector('.top .tab[data-view=gantt]').click()")
        self.go("var b = document.querySelector('[data-gantt-tab-name]'); b.value = 'Other'; b.dispatchEvent(new Event('input', {bubbles: true}))")
        self.go("document.querySelector('[data-gantt-tab-name]').dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))")
        self.assertEqual((self.js("G.sent.length"), self.js("!!document.querySelector('[data-gantt-tab-name]')")), (0, False))
        self.go("document.querySelector('.top .tab[data-view=gantt]').click()")
        self.go("var b = document.querySelector('[data-gantt-tab-name]'); b.value = '   '; b.dispatchEvent(new Event('input', {bubbles: true}))")
        self.go("document.querySelector('[data-gantt-tab-name]').dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true}))")
        self.assertEqual(self.js("G.sent.length"), 0, "nothing was sent")
        self.assertIn("Give the tab a name of 1 to 30 characters. Nothing was changed.", self.js("document.body.innerText"))

    def test_the_label_is_not_a_box_in_view(self):
        self.load({"show_gantt_editor": 1}, edit=False)
        self.go("document.querySelector('.top .tab[data-view=gantt]').click()")
        self.go("document.querySelector('.top .tab[data-view=gantt]').click()")
        self.assertFalse(self.js("!!document.querySelector('[data-gantt-tab-name]')"))

    # ── Settings > Gantt ──

    def test_settings_has_the_two_ticks_and_the_name_and_each_is_saved_alone(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                self.load(edit=True, width=width)
                self.go("location.hash = '#settings&p=DEMO'")
                text = self.js("document.querySelector('#gantt-setting').innerText")
                for words in ("Gantt", "Show the Gantt to me", "Show the Gantt to the client", "Tab name"):
                    self.assertIn(words, text)
                self.go("document.getElementById('gantt-editor').click()")
                self.assertEqual(json.loads(self.js("JSON.stringify(G.sent[0].changes)")), {"show_gantt_editor": 1})
                self.go("document.getElementById('gantt-client').click()")
                self.assertEqual(json.loads(self.js("JSON.stringify(G.sent[1].changes)")), {"show_gantt_client": 1})
                self.assertIn("Gantt", self.labels(), "the editor tab follows the tick")
                self.go("var b = document.getElementById('gantt-name'); b.focus(); b.value = 'Delivery plan'; b.dispatchEvent(new Event('input', {bubbles: true}))")
                self.go("document.getElementById('gantt-name').blur()")      # a separate step, as a person does it: the typed text is drawn before the box is left
                self.assertEqual(json.loads(self.js("JSON.stringify(G.sent[2].changes)")), {"gantt_tab_name": "Delivery plan"})
                self.assertIn("Delivery plan", self.labels())


if __name__ == "__main__":
    unittest.main()
