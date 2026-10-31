"""#35: the page shell, its bundle and the design token layering. Rules: Done-when on the planning repo #35.

Run: python3 dev/run_tests.py test_page
Checks that need no browser: the build is repeatable and the committed page.html is what the sources give; the bundle takes
nothing from outside src/ and the vendored libraries; the page is one file with inline scripts only and loads nothing from
the internet; the token names agree. The browser checks (Test C, the real-browser CSP test against the real bundle, and the
page width) start headless Chrome and are required: they fail, never skip, without it.
"""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import ROOT, SRC, TOOLS

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import publish_public  # noqa: E402
import esbuild  # noqa: E402

from clark import page, server as sv  # noqa: E402
from test_server import Running, _Collect, chrome, wait  # noqa: E402  (the #33 browser harness, shared)

# The names a brand may set (the demo brand declares all of them). Taken out of the prototype's and a full brand's tokens.
CONTRACT = frozenset("""--brand-blue --brand-navy --brand-ink --brand-cyan --grey-50 --grey-100 --grey-200 --grey-300 --grey-500 --grey-700
--status-green --status-amber --status-red --status-blue --status-green-tint --status-amber-tint --status-red-tint
--status-green-text --status-amber-text --status-red-text --status-blue-text --text --text-muted --border --font --radius-sm
--radius --radius-lg --shadow --surface --heading --topbar --bg --black --text-on-brand --surface-muted --link --focus
--data-1 --data-2 --data-3 --data-4 --data-5 --data-6 --size-body --size-caption --size-small --size-h3 --size-h2 --size-h1
--size-display --leading --weight-light --weight-regular --weight-medium --weight-semibold --tracking-caps --space-1 --space-2
--space-3 --space-4 --space-5 --space-6 --space-7 --space-8 --max-width --radius-pill --stagger --ease-out --ease-enter
--ease-exit --ease-toggle --dur-instant --dur-state --dur-layout --dur-enter --image-cover --image-fade --profile-bg --profile-fg --profile-ring --profile-size
--pill-bg --pill-color --pill-fg --pill-glow --pill-glow-hover --bar-end --accent-line --font-head --font-label --art-home --art-home-height""".split())
TOKEN_NAME = re.compile(r"(--[a-z0-9-]+)\s*:")


def token_names(css):
    return set(TOKEN_NAME.findall(css))


class Build(unittest.TestCase):
    def test_the_build_is_repeatable_and_the_committed_page_is_current(self):
        first, second = build_page.build(), build_page.build()
        self.assertEqual(first, second, "the same sources must give the same bytes")
        self.assertEqual(page.PAGE.read_text(encoding="utf-8"), first,
                         "src/clark/page/page.html is out of date: run python3 dev/tools/build_page.py")
        view = build_page.build(build_page.ENTRY_VIEW)
        self.assertEqual(view, build_page.build(build_page.ENTRY_VIEW))
        self.assertEqual(page.VIEW_PAGE.read_text(encoding="utf-8"), view,
                         "src/clark/page/page-view.html is out of date: run python3 dev/tools/build_page.py")

    def test_the_bundle_takes_nothing_from_outside_src_and_the_vendored_folders(self):
        with tempfile.TemporaryDirectory() as tmp:
            meta = Path(tmp) / "meta.json"
            done = esbuild.run(["--bundle", "--format=iife", "--tsconfig-raw={}", *build_page.preact_flags(), "main.jsx",
                                f"--outfile={Path(tmp) / 'p.js'}", f"--metafile={meta}"],
                               cwd=build_page.SRC, capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            inputs = json.loads(meta.read_text(encoding="utf-8"))["inputs"]
        allowed = (build_page.SRC.resolve(), build_page.VENDOR.resolve(), build_page.VENDOR_TIPTAP.resolve())     # the editor (#66)
        paths = {i: (build_page.SRC / i).resolve() for i in inputs}
        outside = [i for i, p in paths.items() if not any(a == p or a in p.parents for a in allowed)]
        self.assertEqual(outside, [])
        self.assertTrue(any("preact" in i for i in inputs) and any("signals" in i for i in inputs))

    def test_every_library_name_is_mapped_to_its_vendored_file(self):
        flags = build_page.preact_flags()
        for spec in ("preact", "preact/hooks", "preact/jsx-runtime", "@preact/signals", "@preact/signals-core"):
            alias = next(f for f in flags if f.startswith(f"--alias:{spec}="))
            self.assertTrue(Path(alias.split("=", 1)[1]).is_file(), alias)


class OneFile(unittest.TestCase):
    def setUp(self):
        self.html = page.PAGE.read_text(encoding="utf-8")

    def test_inline_scripts_only_and_nothing_from_the_internet(self):
        self.assertEqual(len(re.findall(r"<script\b", self.html)), 1)
        self.assertNotRegex(self.html, r"<script[^>]*\bsrc=")
        self.assertEqual(re.findall(r"<link\b[^>]*>", self.html),                  # only clark's icon, as data: (#73)
                         re.findall(r'<link rel="(?:icon|apple-touch-icon)" type="image/[a-z+]+" href="data:image/[a-z+]+;base64,[A-Za-z0-9+/=]+">',
                                    self.html))
        self.assertEqual(len(re.findall(r"<link\b", self.html)), 3)
        self.assertNotRegex(self.html, r"""(?i)\b(src|href|action|poster|data)\s*=\s*["']?(https?:)?//""")
        self.assertNotRegex(self.html, r"(?i)url\(\s*[\"']?(https?:)?//|@import")
        self.assertNotIn("fonts.googleapis", self.html)

    def test_the_built_page_has_no_comment_and_names_no_person(self):
        """A source comment can name a person and a date (one did, from the dark-mode tokens); a built file that leaves the
        machine must carry none: no HTML comment, no CSS comment, and none of the team's names anywhere but inside a data: URI."""
        self.assertNotIn("<!--", self.html)
        for block in re.findall(r"<style[^>]*>(.*?)</style>", self.html, re.S):
            self.assertNotIn("/*", block)
            self.assertNotIn("*/", block)
        text = re.sub(r"data:[^\"')\s]+", "", self.html)               # the font and icons are base64: leave them out
        listed = publish_public.PEOPLE_ANY_CASE + publish_public.PEOPLE_CAPITALISED      # the tool holds them, not this file
        names = re.findall(r"\b(" + "|".join(listed) + r")\b", text)
        self.assertEqual(names, [], "a name in the built page")
        self.assertNotRegex(text, r"\b\d\d-\d\d-20\d\d\b", "a date in the built page (a comment's date)")

    def test_a_local_brands_comments_are_stripped_before_they_are_layered(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "tokens.css").write_text(
                "/* made by Jane Example, 01-01-2026 */\n:root { --brand-navy: #123456; } /* and this */\n/* never closed", encoding="utf-8")
            html = page.page_html(tmp)
        self.assertIn("--brand-navy: #123456", html)
        for text in ("Jane Example", "01-01-2026", "and this", "never closed", "/*", "*/"):
            self.assertNotIn(text, html.split('id="brand-local"', 1)[1].split("</style>", 1)[0])

    def test_strip_css_comments(self):
        for css, want in (("a{} /* x */ b{}", "a{}  b{}"), ("/* x */", ""), ("a{}/**/b{}", "a{}b{}"),
                          ("a{}/* x\ny */b{}", "a{}b{}"), ("a{} /* never closed", "a{} "), ("a{}", "a{}"),
                          ("/* a */ /* b */c{}", " c{}")):
            self.assertEqual(page.strip_css_comments(css), want, css)

    def test_the_server_policy_lists_this_page_and_its_two_blocks(self):
        with tempfile.TemporaryDirectory() as none:                  # no local brand, whatever this laptop has
            hashes = sv.csp_hashes(sv.with_boot(page.page_html(none)))
        self.assertEqual((len(hashes["script"]), len(hashes["style"])), (1, 1))
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "tokens.css").write_text(":root { --brand-navy: #123456; }", encoding="utf-8")
            layered = sv.csp_hashes(sv.with_boot(page.page_html(tmp)))
        self.assertEqual((len(layered["script"]), len(layered["style"])), (1, 2))

    def test_the_demo_brand_is_fictional_and_names_every_token_the_page_uses(self):
        demo = token_names((ROOT / "src" / "clark" / "brand" / "tokens.css").read_text(encoding="utf-8"))
        css = (SRC / "clark" / "page" / "shell.css").read_text(encoding="utf-8")
        used = set(re.findall(r"var\((--[a-z0-9-]+)", css))
        self.assertEqual(sorted(used - demo), [])
        self.assertNotRegex(css, r"#[0-9a-fA-F]{3,8}\b", "the shell takes its colours from tokens, never a hard-coded one")


class Layering(unittest.TestCase):
    def test_a_local_brand_is_layered_over_the_demo_one_and_its_absence_changes_nothing(self):
        with tempfile.TemporaryDirectory() as empty:
            self.assertEqual(page.page_html(empty), page.PAGE.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "tokens.css").write_text(":root { --brand-navy: #123456; }", encoding="utf-8")
            html = page.page_html(tmp)
        self.assertLess(html.index('id="brand-demo"'), html.index('id="brand-local"'))
        self.assertIn("--brand-navy: #123456", html)

    def test_the_design_system_folder_counts_and_a_style_end_tag_can_not_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "design-system").mkdir()
            (Path(tmp) / "design-system" / "tokens.css").write_text("a{}</style><script>x</script>", encoding="utf-8")
            html = page.page_html(tmp)
        self.assertEqual(len(sv.csp_hashes(html)["script"]), 1, "the text inside the style block is never a script")
        self.assertIn("<\\/style", html)

    def test_a_style_end_tag_in_any_letter_case_a_comment_or_a_script_start_can_not_escape(self):
        for hostile in ("</STYLE>", "</Style >", "</style\t>", "</sTyLe/>", "<!--", "<SCRIPT>", "<script src=a.js>", "</STYLE\n>"):
            with tempfile.TemporaryDirectory() as tmp:
                (Path(tmp) / "tokens.css").write_text(f"a{{}}{hostile}<link rel=stylesheet href=//x.invalid/a.css>", encoding="utf-8")
                html = page.page_html(tmp)
            local = html.split('<style id="brand-local">', 1)[1]
            inside, rest = local.split("</style>\n</head>", 1)
            self.assertNotRegex(inside, r"(?i)<(/style|!--|script)", hostile)
            self.assertEqual(len(re.findall(r"(?i)</style", html)), 2, hostile)           # only the demo's and the local block's own
            self.assertEqual(len(re.findall(r"(?i)<style\b", html)), 2, hostile)
            self.assertIn("a{}<\\", inside, hostile)
            self.assertEqual(len(sv.csp_hashes(html)["script"]), 1, hostile)
        self.assertEqual(page.escape_style("p{color:red}"), "p{color:red}", "css with none of them is unchanged")

    def test_the_demo_declares_the_whole_token_contract(self):
        demo = token_names((ROOT / "src" / "clark" / "brand" / "tokens.css").read_text(encoding="utf-8"))
        self.assertEqual(sorted(CONTRACT - demo), [], "the demo brand is the contract: every name a brand may set is here")
        dark = re.search(r":root\[data-theme=dark\]\s*\{(.*?)\n\}", (ROOT / "src/clark/brand/tokens.css").read_text(encoding="utf-8"), re.S)
        self.assertTrue(dark and token_names(dark.group(1)) <= demo, "dark mode redraws only names the demo declares")

    def test_dark_mode_has_two_equal_copies_and_light_is_the_default(self):
        """#64a: data-theme=dark (chosen) and data-theme=auto (follow the computer, inside prefers-color-scheme) carry the same values; no attribute stays light."""
        css = (ROOT / "src" / "clark" / "brand" / "tokens.css").read_text(encoding="utf-8")
        dark = re.search(r":root\[data-theme=dark\]\s*\{(.*?)\n\}", css, re.S).group(1)
        auto = re.search(r"@media \(prefers-color-scheme: dark\)\s*\{\s*:root\[data-theme=auto\]\s*\{(.*?)\n  \}\s*\}", css, re.S).group(1)
        norm = lambda text: sorted(re.sub(r"\s+", " ", d).strip() for d in re.findall(r"--[a-z0-9-]+\s*:[^;]+;", text))
        self.assertEqual(norm(auto), norm(dark))
        self.assertTrue({"--surface", "--grey-50", "--brand-ink", "--heading", "--status-green-text", "--data-1", "--shadow"} <= token_names(dark))
        light = css[:css.index("/* dark mode")]
        self.assertNotIn("prefers-color-scheme", light, "with no data-theme the page is light until the user chooses")
        for name in ("--profile-bg", "--profile-fg", "--profile-ring", "--profile-size"):
            self.assertIn(name, light)

    def test_a_local_brand_on_this_laptop_uses_only_names_the_demo_declares(self):
        demo = token_names((ROOT / "src" / "clark" / "brand" / "tokens.css").read_text(encoding="utf-8"))
        local = ROOT / "system" / "branding" / "design-system" / "tokens.css"
        if local.is_file():                       # only on a laptop that has the user's own brand (git ignores it)
            self.assertEqual(sorted(token_names(local.read_text(encoding="utf-8")) - demo), [])

    def test_a_stray_tsconfig_in_a_parent_folder_does_not_change_the_bytes(self):
        stray = build_page.PAGE / "tsconfig.json"
        self.assertFalse(stray.exists())
        stray.write_text('{"compilerOptions": {"alwaysStrict": true}}', encoding="utf-8")
        try:
            self.assertEqual(build_page.build(), page.PAGE.read_text(encoding="utf-8"))
        finally:
            stray.unlink()


def navigate(cdp, port, hash_=""):
    tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
    sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
    cdp.call("Emulation.setDeviceMetricsOverride", {"width": 1400, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
    cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{port}/{hash_}"}, sid)
    return sid


# One fictional project, in the shape Store.data_for(code) gives (#31); #35 doesn't need the store itself.
DATA = {"ABC": {"project": {"code": "ABC", "name": "Example Programme", "health": "On track", "client_name": None},
                "milestones": [{"id": "ABC-M-001", "name": "Pilot live"}], "workstreams": [], "use_cases": [], "links": [],
                "actions": [{"id": "ABC-A-001", "description": "Agree the cut-over plan"}], "raid": [], "decisions": [],
                "labels": {}}}


class RealBrowser(unittest.TestCase):
    def serve(self, branding):
        s = Running(data_for=DATA.get, page_html=lambda: page.page_html(branding))
        self.addCleanup(s.close)
        return s

    def test_C_the_override_wins_and_without_it_the_demo_value_shows(self):
        demo_navy = re.search(r"--brand-navy:\s*([^;]+);", (ROOT / "src/clark/brand/tokens.css").read_text(encoding="utf-8")).group(1)
        with tempfile.TemporaryDirectory() as empty, tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "tokens.css").write_text(":root { --brand-navy: #123456; }", encoding="utf-8")
            seen = {}
            for name, branding in (("demo", empty), ("override", tmp)):
                s = self.serve(branding)
                with chrome() as cdp:
                    sid = navigate(cdp, s.port, "#dashboard&p=ABC")
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.top')", sid)), "the page drew")
                    seen[name] = cdp.js("[getComputedStyle(document.documentElement).getPropertyValue('--brand-navy').trim(), "
                                        "getComputedStyle(document.querySelector('.top')).backgroundColor]", sid)
        self.assertEqual(seen["demo"][0], demo_navy)
        self.assertEqual(seen["override"], ["#123456", "rgb(18, 52, 86)"])
        self.assertNotEqual(seen["demo"][1], seen["override"][1])

    def test_the_real_bundle_runs_under_the_enforced_policy_and_injected_script_is_blocked(self):
        s = self.serve(tempfile.mkdtemp())
        blocked = []
        handler = _Collect(blocked)
        sv.LOG.addHandler(handler)
        sv.LOG.setLevel("INFO")
        self.addCleanup(sv.LOG.removeHandler, handler)
        with mock.patch.dict(sv.CSP_REPORTS, since=__import__("time").time(), n=0, dropped=0):
            with chrome() as cdp:
                sid = navigate(cdp, s.port, "#dashboard&p=ABC")
                self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.ready", sid) == "1"), "the bundle ran")
                self.assertTrue(wait(lambda: cdp.js("document.querySelector('h1') && document.querySelector('h1').textContent",
                                                    sid) == "Example Programme"), "the page read its data with the token")
                self.assertEqual(blocked, [], f"the real bundle needed nothing the policy blocks: {blocked}")
                cdp.js("var s = document.createElement('script'); s.textContent = 'window.injected = 1'; "
                       "document.body.appendChild(s);", sid)
                self.assertTrue(wait(lambda: len(blocked) >= 1, 10), "an injected inline script is reported")
                self.assertIs(cdp.js("window.injected === undefined", sid), True)

    def test_the_dashboard_is_as_wide_as_work_items_at_1400_and_nothing_overflows_at_900(self):
        s = self.serve(tempfile.mkdtemp())
        with chrome() as cdp:
            sid = navigate(cdp, s.port, "#dashboard&p=ABC")
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#report')", sid)))
            width = "Math.round(document.querySelector('.frame').getBoundingClientRect().width)"
            dashboard = cdp.js(width, sid)
            cdp.js("document.querySelector('[data-view=work]').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#work')", sid)))
            work = cdp.js(width, sid)
            self.assertEqual((dashboard, work), (1232, 1232), "the page's 1280 px less its 24 px padding, in both")
            for w in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
                for view in ("dashboard", "work", "milestones", "settings"):
                    cdp.js(f"document.querySelector('[data-view={view}]').click()", sid)
                    self.assertTrue(wait(lambda: cdp.js("document.documentElement.scrollWidth <= window.innerWidth", sid)),
                                    f"{view} at {w}px has no sideways scroll")

    def test_a_project_that_is_not_there_says_so_in_plain_words(self):
        s = self.serve(tempfile.mkdtemp())
        with chrome() as cdp:
            sid = navigate(cdp, s.port, "#dashboard&p=NOPE")
            self.assertTrue(wait(lambda: cdp.js("document.querySelector('h1') && document.querySelector('h1').textContent",
                                                sid) == "That project isn't here"))


if __name__ == "__main__":
    unittest.main()
