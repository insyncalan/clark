"""#130 enrichments: still loading placeholders on a first load, and a changed-row mark that survives reduced motion.

Run: python3 dev/run_tests.py test_enrichments
Part 1 needs no browser: the mark's text colours pass 4.5:1 in the light and dark tokens (computed from tokens.css); the
placeholder and the mark use no animation or transition; every component that marks a row also draws the word "Changed" (so a
table that is added later inherits the rule); the words are plain.
Part 2 runs the real page in headless Chrome (the harness's chrome(): keychain flags included) with `prefers-reduced-motion`
emulated, at 1400, 900 and 390 px wide: a change and an undo mark the changed section (tint, bar and the word), the mark goes at
the next click or key press or after 3 seconds (a clock the test winds by hand), Work items and Milestones rows take the same mark;
a slow answer shows the placeholder only after 150 ms, an instant one never shows it, a published file never does.
"""
import json
import re
import sys
import tempfile
import time
import unittest
from pathlib import Path

from _paths import SRC, TOOLS
import _publish_fixture as fx
import _testpage as testpage
import test_report_editor as tre
from test_page import DATA, navigate
from test_server import Running, chrome, wait

sys.path.insert(0, str(TOOLS))

from clark import page, publish

PAGE = SRC / "clark" / "page"
SRCDIR = PAGE / "src"
CSS = (PAGE / "shell.css").read_text(encoding="utf-8")
TOKENS = (SRC / "clark" / "brand" / "tokens.css").read_text(encoding="utf-8")
WIDTHS = (1400, 900, 390)
REDUCE = [{"name": "prefers-reduced-motion", "value": "reduce"}]


# ---- colour helpers, from the tokens -------------------------------------------------------------------------------------
def token_values(css, header):
    """{name: value} of the first block that starts with `header` (e.g. ':root {')."""
    block = css.split(header, 1)[1].split("\n}", 1)[0]
    return dict(re.findall(r"(--[a-z0-9-]+)\s*:\s*([^;]+);", block))


def resolve(name, values):
    v = values[name].strip()
    while v.startswith("var("):
        v = values[v[4:-1].strip()].strip()
    return v


def rgb(hexa):
    h = hexa.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def luminance(c):
    def f(v):
        v /= 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (f(x) for x in c)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def themes():
    light = token_values(TOKENS, ":root {")
    dark = dict(light)
    dark.update(token_values(TOKENS, ":root[data-theme=dark] {"))
    return {"light": light, "dark": dark}


def block_of(selector_start):
    """The text of the first CSS rule in shell.css whose selector starts with `selector_start`."""
    i = CSS.index(selector_start)
    return CSS[i:CSS.index("}", i) + 1]


class Tokens(unittest.TestCase):
    def test_the_mark_s_text_passes_4_5_to_1_on_its_tint_in_light_and_dark(self):
        for theme, values in themes().items():
            tint = rgb(resolve("--status-amber-tint", values))
            for fg in ("--status-amber-text", "--text", "--text-muted"):
                with self.subTest(theme=theme, fg=fg):
                    got = ratio(rgb(resolve(fg, values)), tint)
                    self.assertGreaterEqual(got, 4.5, f"{fg} on the changed tint in {theme}: {got:.2f}")

    def test_the_mark_uses_those_tokens_and_no_colour_of_its_own(self):
        rule = block_of(".tag.chg { flex")
        self.assertIn("var(--status-amber-text)", rule)
        self.assertIn("var(--status-amber-tint)", rule)
        for name in (".tag.chg { flex", ".sec.is-changed", "table.items tr.changed td", ".msl-row.changed"):
            self.assertNotRegex(block_of(name), r"#[0-9a-fA-F]{3,8}\b|rgb\(", name)


class Still(unittest.TestCase):
    """The placeholder and the mark do not move, so reduced motion has nothing to switch off."""

    def test_no_animation_or_transition_in_the_placeholder_or_the_mark(self):
        added = CSS[CSS.index("Loading placeholder:"):CSS.index("Motion:")]
        for word in ("animation", "transition", "@keyframes", "transform"):
            self.assertNotIn(word, added)

    def test_the_mark_has_a_bar_and_a_word_as_well_as_a_tint(self):
        """Not by colour alone: every rule that tints a changed row also sets an inset bar, and every component that marks a row
        draws the word. A table added later inherits the rule when it uses isChanged and WORD."""
        added = CSS[CSS.index("Changed rows:"):CSS.index("Motion:")]
        tints = re.findall(r"([^{}]+)\{[^}]*background: var\(--status-amber-tint\)[^}]*\}", added)
        self.assertGreaterEqual(len(tints), 4)
        for rule in re.findall(r"[^{}]+\{[^}]*\}", added.split("@media (forced-colors")[0]):
            if "var(--status-amber-tint)" in rule and ".tag.chg" not in rule and "td {" not in rule:
                self.assertIn("inset 4px 0 0", rule, rule)
        self.assertRegex(added, r"tr\.changed td:first-child \{ box-shadow: inset 4px 0 0")
        for path in SRCDIR.rglob("*.jsx"):
            text = path.read_text(encoding="utf-8")
            if "isChanged(" in text and path.name != "changed.js":
                with self.subTest(path.name):
                    self.assertIn("{WORD}", text)
                    self.assertIn('class="tag chg"', text)

    def test_the_words_are_plain(self):
        changed = (SRCDIR / "stores" / "changed.js").read_text(encoding="utf-8")
        views = (SRCDIR / "components" / "Views.jsx").read_text(encoding="utf-8")
        self.assertIn('export const WORD = "Changed";', changed)
        self.assertIn("<h1 class=\"sr\">Loading</h1>", views)
        self.assertIn("Opening {project.value}.", views)
        banned = re.compile(r"\b(sweep|proposal|stage|apply|applied|vault|live server|extract|refused|valid|invalid|tracker)\b", re.I)
        shown = re.findall(r'<(?:h1|p|span)[^>]*>([^<{]+)', views) + [re.search(r'WORD = "([^"]+)"', changed).group(1)]
        for text in shown:
            self.assertIsNone(banned.search(text), text)
        self.assertFalse(re.match(r"\s*clark\b", "Changed"))

    def test_the_wait_is_150_ms_and_a_published_file_skips_it(self):
        views = (SRCDIR / "components" / "Views.jsx").read_text(encoding="utf-8")
        self.assertIn("export const SKELETON_AFTER_MS = 150;", views)
        loading = views[views.index("function Loading()"):views.index("export function Milestones")]
        self.assertIn("if (isFile()) return undefined;", loading)
        self.assertIn("setLate(true); skeleton.value = view.value; }, SKELETON_AFTER_MS)", loading)
        app = (SRCDIR / "components" / "App.jsx").read_text(encoding="utf-8")
        self.assertIn('aria-busy={status.value === "loading" && !isFile() ? "true" : undefined}', app)

    def test_the_two_built_pages_are_current(self):
        import build_page
        self.assertEqual(page.PAGE.read_text(encoding="utf-8"), build_page.build())


def bundle_with_signals(module, name):
    """One script that sets a global `name`, with the page's own library mapping (changed.js imports @preact/signals)."""
    import build_page
    import esbuild
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "m.js"
        done = esbuild.run(["--bundle", "--format=iife", f"--global-name={name}", *build_page.preact_flags(), str(module), f"--outfile={out}"],
                           capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        return out.read_text(encoding="utf-8")


class Rules(unittest.TestCase):
    """The mark's own rules (stores/changed.js), through the real module in Chrome, with a clock wound by hand."""

    def test_diff_mark_clear_and_the_timer(self):
        script = bundle_with_signals(SRCDIR / "stores" / "changed.js", "CH") + ";\n" + """(() => {
            const out = {}; let fire = null; const log = [];
            CH.useClock({ setTimeout: (f, ms) => { fire = f; log.push(ms); return 1; }, clearTimeout: () => { log.push("clear"); fire = null; } });
            out.diff = CH.diffIds([{ id: "A", v: 1 }, { id: "B", v: 1 }], [{ id: "A", v: 1 }, { id: "B", v: 2 }, { id: "C", v: 1 }]);
            out.diffNone = CH.diffIds([{ id: "A", v: 1 }], [{ id: "A", v: 1 }]);
            out.diffNull = CH.diffIds(null, [{ id: "A" }]);
            CH.markChanged(["A"]); out.marked = CH.changed.value.slice(); out.set = log.slice(); out.isA = CH.isChanged("A"); out.isB = CH.isChanged("B");
            fire(); out.afterTimer = CH.changed.value.slice();
            CH.markChanged(["A"]); CH.markChanged(["B"]); out.replaced = CH.changed.value.slice();
            document.dispatchEvent(new KeyboardEvent("keydown", { key: "Shift" })); out.shift = CH.changed.value.slice();
            document.dispatchEvent(new KeyboardEvent("keydown", { key: "a" })); out.key = CH.changed.value.slice();
            CH.markChanged(["A"]); document.dispatchEvent(new Event("pointerdown")); out.pointer = CH.changed.value.slice();
            CH.markChanged([]); out.empty = CH.changed.value.slice();
            out.show = CH.SHOW_MS; out.word = CH.WORD;
            return out; })()"""
        with chrome() as cdp:
            sid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
            sid = cdp.call("Target.attachToTarget", {"targetId": sid, "flatten": True})["sessionId"]
            res = cdp.call("Runtime.evaluate", {"expression": script, "returnByValue": True}, sid)
            self.assertNotIn("exceptionDetails", res, res)
            o = res["result"]["value"]
        self.assertEqual(o["diff"], ["B", "C"], "a changed row and a new one, not an equal one")
        self.assertEqual((o["diffNone"], o["diffNull"]), ([], ["A"]))
        self.assertEqual((o["marked"], o["isA"], o["isB"]), (["A"], True, False))
        self.assertEqual(o["set"][-1], 3000, "the mark is timed for 3 seconds")
        self.assertEqual(o["afterTimer"], [], "the timer clears it")
        self.assertEqual(o["replaced"], ["B"], "a later change replaces the earlier mark")
        self.assertEqual(o["shift"], ["B"], "holding a modifier is not an action")
        self.assertEqual((o["key"], o["pointer"], o["empty"]), ([], [], []))
        self.assertEqual((o["show"], o["word"]), (3000, "Changed"))


# ---- the real page --------------------------------------------------------------------------------------------------------
def probe(p, css):
    """The computed colour of `background: <css>` as the page resolves it."""
    return p.js(f"(function(){{var e=document.createElement('i');e.style.background={json.dumps(css)};document.body.appendChild(e);"
                "var c=getComputedStyle(e).backgroundColor;e.remove();return c;})()")


def parse_rgb(text):
    return tuple(int(float(x)) for x in re.findall(r"[\d.]+", text)[:3])


class Mark(tre.Base):
    def reduce_motion(self, p):
        p.cdp.call("Emulation.setEmulatedMedia", {"features": REDUCE}, p.sid)
        self.assertTrue(p.js("matchMedia('(prefers-reduced-motion: reduce)').matches"))

    def width(self, p, w):
        p.cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": w < 500}, p.sid)

    def sec(self, p, ref):
        return f"document.querySelector('[data-id=\"{ref}\"]')"

    def look(self, p, ref):
        return p.js("(function(){var s=%s,t=s.querySelector('.tag.chg'),cs=getComputedStyle(s),ts=t&&getComputedStyle(t);"
                    "var r=t&&t.getBoundingClientRect();"
                    "return {changed:s.classList.contains('is-changed'),word:t&&t.textContent,bg:cs.backgroundColor,shadow:cs.boxShadow,"
                    "anim:cs.animationName,trans:cs.transitionDuration,tanim:ts&&ts.animationName,color:ts&&ts.color,tbg:ts&&ts.backgroundColor,"
                    "size:ts&&parseFloat(ts.fontSize),inside:r&&r.left>=0&&r.right<=innerWidth&&r.width>0,"
                    "vis:r&&r.width>0&&r.height>0,scroll:document.documentElement.scrollWidth<=innerWidth,flag:s.dataset.changed};})()" % self.sec(p, ref))

    def test_a_change_marks_its_section_with_a_tint_a_bar_and_the_word_under_reduced_motion_at_three_widths(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            self.reduce_motion(p)
            p.edit()
            p.menu("ABC-S-002", "hide")
            p.until(self.sec(p, "ABC-S-002") + ".classList.contains('is-changed')", "the changed section is marked")
            tint = parse_rgb(probe(p, "var(--status-amber-tint)"))
            for w in WIDTHS:
                with self.subTest(width=w):
                    self.width(p, w)
                    p.until("document.documentElement.scrollWidth <= innerWidth", f"no sideways scroll at {w}")
                    got = self.look(p, "ABC-S-002")
                    self.assertEqual((got["changed"], got["word"], got["flag"]), (True, "Changed", "1"))
                    self.assertEqual(parse_rgb(got["bg"]), tint, "a static tint")
                    self.assertNotEqual(got["shadow"], "none", "a bar, not colour alone")
                    self.assertEqual((got["anim"], got["tanim"]), ("none", "none"), "nothing moves")
                    self.assertTrue(got["inside"] and got["vis"], "the word is visible and inside the window")
                    self.assertGreaterEqual(got["size"], 13)
                    self.assertGreaterEqual(ratio(parse_rgb(got["color"]), parse_rgb(got["tbg"])), 4.5, "the word's contrast as drawn")
                    self.assertTrue(got["scroll"])
                    self.assertTrue(set(p.js("[...document.querySelectorAll('.sec.is-changed')].map(e=>e.dataset.id)")) == {"ABC-S-002"},
                                    "only the changed section")
            self.width(p, 1400)
            self.assertEqual(p.js("document.querySelectorAll('.tag.chg').length"), 1)

    def test_it_goes_at_the_next_click_or_key_press_and_after_three_seconds(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            p.js("window.__timers = []; clarkPage.useClock({setTimeout: (f, ms) => { window.__timers.push([f, ms]); return window.__timers.length; },"
                 " clearTimeout: () => {}})")
            p.menu("ABC-S-002", "hide")
            p.until("!!document.querySelector('.tag.chg')", "marked")
            self.assertEqual(p.js("window.__timers[window.__timers.length - 1][1]"), 3000)
            p.js("window.__timers[window.__timers.length - 1][0]()")                       # the clock reaches 3 seconds
            p.until("!document.querySelector('.tag.chg') && !document.querySelector('.is-changed')", "gone after the timeout")
            p.clear_toast()
            p.menu("ABC-S-003", "hide")
            p.until("!!document.querySelector('.tag.chg')", "marked again")
            p.mouse("mousePressed", 700, 300, 1)
            p.mouse("mouseReleased", 700, 300)
            p.until("!document.querySelector('.tag.chg')", "gone at the next click")
            p.js("clarkPage.markChanged(['ABC-S-004'])")
            p.until("!!document.querySelector('[data-id=\"ABC-S-004\"] .tag.chg')", "marked by hand")
            p.key("x", code="KeyX", vk=88)
            p.until("!document.querySelector('.tag.chg')", "gone at the next key press")

    def test_undo_marks_the_section_it_put_back_and_a_new_change_replaces_the_mark(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            self.reduce_motion(p)
            p.edit()
            p.menu("ABC-S-003", "hide")
            p.saved()
            p.js("document.querySelector('[data-undo]').click()")
            p.until("!" + self.sec(p, "ABC-S-003") + ".classList.contains('is-hidden')", "undone")
            p.until(self.sec(p, "ABC-S-003") + ".classList.contains('is-changed')", "the restored section is marked")
            self.assertEqual(p.js("[...document.querySelectorAll('.is-changed')].map(e => e.dataset.id)"), ["ABC-S-003"])
            p.clear_toast()
            p.menu("ABC-S-005", "hide")
            p.until(self.sec(p, "ABC-S-005") + ".classList.contains('is-changed')", "the new change is marked")
            self.assertEqual(p.js("[...document.querySelectorAll('.is-changed')].map(e => e.dataset.id)"), ["ABC-S-005"], "the old mark went")

    def test_a_first_draw_and_a_reload_mark_nothing(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            self.assertEqual(p.js("document.querySelectorAll('.tag.chg, .is-changed, [data-changed]').length"), 0)


class OtherRows(unittest.TestCase):
    """Work items and Milestones take the same mark (nothing edits them yet, so the page's hook marks them)."""

    def test_rows_take_the_tint_the_bar_and_the_word_with_reduced_motion_at_three_widths(self):
        s = Running(data_for=DATA.get, page_html=lambda: testpage.html())
        self.addCleanup(s.close)
        with chrome() as cdp:
            for view, ids, sel in (("work", ["ABC-A-001"], "#work tbody tr[data-id=ABC-A-001]"),
                                   ("milestones", ["ABC-M-001"], "#milestones li[data-ms=ABC-M-001]")):
                for w in WIDTHS:
                    with self.subTest(view=view, width=w):
                        sid = navigate(cdp, s.port, f"#{view}&p=ABC")
                        pg = tre.Pg(self, cdp, sid)
                        cdp.call("Emulation.setEmulatedMedia", {"features": REDUCE}, sid)
                        cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": w < 500}, sid)
                        pg.until(f"!!document.querySelector({json.dumps(sel)})", "the row drew")
                        pg.js(f"clarkPage.markChanged({json.dumps(ids)})")
                        pg.until(f"!!document.querySelector({json.dumps(sel + ' .tag.chg')})", "the word")
                        got = pg.js("(function(){var r=document.querySelector(%s),c=r.closest('tr')?r.querySelector('td'):r,cs=getComputedStyle(c),"
                                    "t=r.querySelector('.tag.chg'),b=t.getBoundingClientRect();return {bg:cs.backgroundColor,shadow:cs.boxShadow,"
                                    "word:t.textContent,anim:cs.animationName,inside:b.left>=0&&b.right<=innerWidth&&b.width>0,"
                                    "scroll:document.documentElement.scrollWidth<=innerWidth,flag:r.dataset.changed};})()" % json.dumps(sel))
                        self.assertEqual((got["word"], got["flag"], got["anim"]), ("Changed", "1", "none"))
                        self.assertNotEqual(got["shadow"], "none")
                        self.assertNotEqual(parse_rgb(got["bg"]), (0, 0, 0))
                        self.assertTrue(got["inside"] and got["scroll"])
                        pg.js("clarkPage.markChanged([])")
                        pg.until("!document.querySelector('.tag.chg')", "cleared")


class Skeleton(tre.Base):
    watching = set()

    WATCH = """(function(){ window.__seen = {skel: null, busy: null, busyEver: false, skelEver: false};
      var t0 = performance.now();
      new MutationObserver(function(){
        var m = document.querySelector('main'), k = document.querySelector('.skel-frame');
        if (m && m.getAttribute('aria-busy') === 'true') { window.__seen.busyEver = true; if (window.__seen.busy === null) window.__seen.busy = performance.now() - t0; }
        if (k) { window.__seen.skelEver = true; if (window.__seen.skel === null) window.__seen.skel = performance.now() - t0; }
      }).observe(document, {childList: true, subtree: true, attributes: true}); })()"""

    def visit_with(self, cdp, port, hash_, width=1400, reduce=False):
        sid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        sid = cdp.call("Target.attachToTarget", {"targetId": sid, "flatten": True})["sessionId"]
        cdp.call("Page.enable", {}, sid)
        if sid not in self.watching:
            self.watching.add(sid)
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": self.WATCH}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": width < 500}, sid)
        if reduce:
            cdp.call("Emulation.setEmulatedMedia", {"features": REDUCE}, sid)
        cdp.call("Page.navigate", {"url": "about:blank"}, sid)          # a hash-only change would not reload the page
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{port}/{hash_}"}, sid)
        return tre.Pg(self, cdp, sid)

    def slow_server(self, seconds):
        gate = {"open": False}

        def data_for(code):
            end = time.time() + seconds
            while not gate["open"] and time.time() < end:
                time.sleep(0.02)
            return self.store.data_for(code)
        s = Running(data_for=data_for, page_html=lambda: testpage.html())
        self.addCleanup(s.close)
        return s, gate

    def test_a_slow_answer_shows_a_still_placeholder_after_150_ms_in_every_screen_width_and_motion_setting(self):
        s, gate = self.slow_server(30)
        with chrome() as cdp:
            for view in ("work", "milestones", "dashboard"):
                for w, reduce in ((1400, False), (900, True), (390, True)):
                    with self.subTest(view=view, width=w, reduce=reduce):
                        gate["open"] = False
                        p = self.visit_with(cdp, s.port, f"#{view}&p=ABC", w, reduce)
                        p.until("!!document.querySelector('.skel-frame')", "the placeholder appeared")
                        seen = p.js("window.__seen")
                        self.assertGreaterEqual(seen["skel"] - seen["busy"], 140, "not before about 150 ms of waiting")
                        self.assertEqual(p.js("document.querySelector('main').getAttribute('aria-busy')"), "true")
                        self.assertEqual(p.js("document.querySelector('.skel-frame .sr').textContent"), "Loading")
                        self.assertEqual(p.js("document.querySelector('.skel-body').getAttribute('aria-hidden')"), "true")
                        self.assertEqual(p.js("document.querySelector('.skel-body').textContent.trim()"), "", "the blocks carry no words")
                        looks = p.js("[...document.querySelectorAll('.skel')].filter(e => getComputedStyle(e).display !== 'none').map(e => { var c = getComputedStyle(e); "
                                     "return [c.animationName, c.transitionDuration, c.backgroundColor, e.getBoundingClientRect().height > 0]; })")
                        self.assertGreater(len(looks), 4)
                        for anim, trans, bg, drawn in looks:
                            self.assertEqual((anim, drawn), ("none", True))
                            self.assertEqual(trans, "0s")
                            self.assertNotEqual(bg, "rgba(0, 0, 0, 0)")
                        self.assertTrue(p.js("document.documentElement.scrollWidth <= innerWidth"), f"no sideways scroll at {w}")
                        gate["open"] = True
                        p.until("!document.querySelector('.skel-frame') && !!document.querySelector('main h1:not(.sr)')", "the screen replaced it")
                        self.assertIsNone(p.js("document.querySelector('main').getAttribute('aria-busy')"), "busy ends with the data")

    def test_an_instant_answer_never_flashes_a_placeholder(self):
        s = self.s
        with chrome() as cdp:
            for view in ("work", "milestones", "dashboard"):
                p = self.visit_with(cdp, s.port, f"#{view}&p=ABC")
                p.until("!!document.querySelector('main h1')", "the screen drew")
                time.sleep(0.4)
                seen = p.js("window.__seen")
                self.assertFalse(seen["skelEver"], f"{view}: a placeholder flashed")

    def test_a_published_file_never_has_a_loading_phase(self):
        plant = fx.load()
        pub = publish.select(fx.inputs(plant))
        served = page.page_html          # the published file is built from the served page; this test never calls the page hook
        text = publish.render(pub, served(tre.EMPTY_BRANDING), plant["as_at"], pub["data"]["project"]["name"])
        code = pub["data"]["project"]["code"]
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "report.html"
            f.write_text(text, encoding="utf-8")
            with chrome() as cdp:
                sid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
                sid = cdp.call("Target.attachToTarget", {"targetId": sid, "flatten": True})["sessionId"]
                cdp.call("Page.enable", {}, sid)
                cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": self.WATCH}, sid)
                cdp.call("Page.navigate", {"url": f"{f.as_uri()}#dashboard&p={code}"}, sid)
                p = tre.Pg(self, cdp, sid)
                p.until("!!document.querySelector('.sec')", "the published report drew")
                time.sleep(0.4)
                seen = p.js("window.__seen")
                self.assertEqual((seen["skelEver"], seen["busyEver"]), (False, False), "no placeholder and no busy flag in a file")


if __name__ == "__main__":
    unittest.main()
