"""#71: the files that make clark a Chrome app (src/clark/appfiles.py, src/clark/app/): the manifest and its icons, the service
worker, the offline page, the data mark and /health's answer to it. All pure: nothing is served here (the routes are not wired
yet: docs/handoff/design-71-launcher.md). tests/test_app_browser.py runs the same files in headless Chrome.

Run: python3 dev/run_tests.py test_app_files
"""
import json
import re
import struct
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT, SRC

from clark import appfiles as af
from clark import server as sv

TOKENS = (SRC / "clark" / "brand" / "tokens.css").read_text(encoding="utf-8")
ROUTES = ["/manifest.webmanifest", "/sw.js", "/offline", "/app/icon-192.png", "/app/icon-512.png", "/app/icon-maskable-512.png"]


def png_size(data):
    """(width, height) from a PNG's header."""
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    return struct.unpack(">II", data[16:24])


def token(name):
    """The value of `--name` in the demo tokens (the first block), upper-cased."""
    return re.search(r"--" + name + r":\s*(#[0-9A-Fa-f]{3,6})", TOKENS).group(1).upper()


class Manifest(unittest.TestCase):
    def setUp(self):
        self.m = af.manifest()

    def test_name_window_and_scope(self):
        m = self.m
        self.assertEqual((m["name"], m["short_name"]), ("clark", "clark"))
        self.assertEqual((m["id"], m["start_url"], m["scope"]), ("/", "/", "/"))
        self.assertEqual(m["display"], "standalone")
        self.assertEqual(m["lang"], "en-GB")

    def test_the_colours_are_clarks_tokens(self):
        self.assertEqual(self.m["theme_color"].upper(), token("brand-navy"), "the top bar's colour")
        self.assertEqual(self.m["background_color"].upper(), token("grey-50"), "the page's background")

    def test_three_icons_192_512_and_maskable_whose_sizes_match_their_files(self):
        icons = self.m["icons"]
        self.assertEqual([(i["sizes"], i["purpose"]) for i in icons], [("192x192", "any"), ("512x512", "any"), ("512x512", "maskable")])
        for icon, (route, name, px, _) in zip(icons, af.ICONS):
            self.assertEqual(icon["type"], "image/png")
            self.assertEqual(icon["src"].split("?")[0], route)
            self.assertEqual(png_size(af.icon_bytes(name)), (px, px), name)

    def test_the_icons_are_the_73_files_byte_for_byte(self):
        files = af.open_files()
        for route, name, _, _ in af.ICONS:
            self.assertEqual(files[route][0], (SRC / "clark" / "page" / "assets" / name).read_bytes())

    def test_a_new_icon_gets_a_new_address(self):
        v = af.icon_stamp()
        self.assertRegex(v, r"^[0-9a-f]{8}$")
        self.assertTrue(all(i["src"].endswith(f"?v={v}") for i in self.m["icons"]))
        self.assertNotEqual(af.manifest("abcd1234")["icons"][0]["src"], self.m["icons"][0]["src"])

    def test_the_bytes_are_this_manifest_and_nothing_from_outside(self):
        text = af.manifest_json().decode("utf-8")
        self.assertEqual(json.loads(text), self.m)
        self.assertNotRegex(text, r"https?:|//")

    def test_the_manifest_has_no_token_and_no_data(self):
        self.assertNotIn(sv.TOKEN, af.manifest_json().decode("utf-8"))
        self.assertEqual(set(self.m), {"name", "short_name", "description", "lang", "id", "start_url", "scope", "display",
                                       "background_color", "theme_color", "icons"})


class OpenFiles(unittest.TestCase):
    """The whole list of what the server may answer without the token."""

    def test_exactly_these_routes(self):
        self.assertEqual(sorted(af.open_files()), sorted(ROUTES))

    def test_each_is_fixed_bytes_of_the_right_type_and_holds_no_token(self):
        for route, (body, ctype, extra) in af.open_files().items():
            self.assertIsInstance(body, bytes, route)
            self.assertNotIn(sv.TOKEN.encode(), body, route)
            self.assertEqual(ctype, {"/manifest.webmanifest": "application/manifest+json", "/sw.js": "text/javascript",
                                     "/offline": "text/html"}.get(route, "image/png"), route)
            self.assertEqual(set(extra), {"Content-Security-Policy"} if route == "/sw.js" else set(), route)

    def test_the_worker_script_may_fetch_from_clark_only_and_load_nothing_else(self):
        self.assertEqual(af.open_files()["/sw.js"][2], {"Content-Security-Policy": "default-src 'none'; connect-src 'self'"})

    def test_a_second_call_gives_the_same_bytes(self):
        self.assertEqual(af.open_files(), af.open_files())


def code_of(js):
    """The script without its comments."""
    return re.sub(r"/\*.*?\*/|//[^\n]*", "", js, flags=re.S)


class ServiceWorker(unittest.TestCase):
    """The worker does one job: page loads only, falls back only to /offline, caches only /offline."""

    def setUp(self):
        self.js = af.service_worker().decode("utf-8")
        self.code = code_of(self.js)

    def test_it_listens_for_install_activate_and_fetch_only(self):
        self.assertEqual(re.findall(r'addEventListener\("(\w+)"', self.code), ["install", "activate", "fetch"])
        for other in ("push", "sync", "message", "periodicsync", "notificationclick", "importScripts"):
            self.assertNotIn(other, self.code)

    def test_it_handles_page_loads_only_and_falls_back_to_the_offline_page_only(self):
        self.assertIn('if (e.request.mode !== "navigate") return;', self.code)
        self.assertEqual(self.code.count("respondWith("), 1)
        self.assertIn('e.respondWith(fetch(e.request).catch(() => caches.match("/offline")));', self.code)

    def test_it_caches_one_page_in_one_cache_and_removes_any_other_cache(self):
        self.assertEqual(re.findall(r'const CACHE = "([^"]+)"', self.code), ["clark-offline-v1"])
        self.assertEqual(re.findall(r"\.(add|addAll|put)\(([^)]*)\)", self.code), [("add", '"/offline"')])
        self.assertIn("ks.filter(k => k !== CACHE).map(k => caches.delete(k))", self.code)

    def test_it_never_names_the_page_or_the_api_or_an_outside_address(self):
        for text in ('"/"', "'/'", "/api", "http:", "https:", "token", "Token"):
            self.assertNotIn(text, self.code)


class OfflinePage(unittest.TestCase):
    def setUp(self):
        self.page = af.offline_page().decode("utf-8")

    def test_it_says_clark_isnt_running_with_the_start_command_and_check_again(self):
        self.assertIn("<title>Not running</title>", self.page)
        self.assertIn("<h1>Start clark to use this window</h1>", self.page)
        self.assertIn("Double-click <b>clark.command</b> in your clark folder", self.page)
        self.assertIn("<code>./clark.command</code>", self.page)
        self.assertIn('<button type="button" id="again">Check again</button>', self.page)
        self.assertIn('"Still not running. Double-click clark.command, then check again."', self.page)
        self.assertNotIn("@LAUNCHER@", self.page)
        self.assertNotIn("@COMMAND@", self.page)

    def test_check_again_asks_health_then_goes_to_clark(self):
        self.assertIn('fetch("/health", {cache: "no-store"})', self.page)
        self.assertIn('location.replace("/")', self.page)

    def test_the_words_are_plain(self):
        text = re.sub(r"<style>.*?</style>|<script>.*?</script>|<[^>]+>", " ", self.page, flags=re.S)
        for word in ("server", "Server", "localhost", "port", "JSON", "Error", "Exception", "!", "Clark"):
            self.assertNotIn(word, text)

    def test_what_it_says_is_nothing_is_lost(self):
        self.assertIn("Nothing is lost: your data stays on this computer.", self.page)
        self.assertIn("A minute after the last window closes, clark stops by itself.", self.page)

    def test_the_launcher_name_is_escaped_and_nothing_else_is_put_in(self):
        page = af.offline_page('<b>x"&').decode("utf-8")
        self.assertIn("&lt;b&gt;x&quot;&amp;", page)
        self.assertNotIn("<b>x", page)

    def test_it_loads_nothing_and_names_no_address(self):
        self.assertNotRegex(self.page, r"https?:|src=|href=|@import|url\(|<link|<img|<iframe")

    def test_every_colour_is_one_of_clarks_tokens(self):
        known = {c.upper() for c in re.findall(r"--[\w-]+:\s*(#[0-9A-Fa-f]{3,6})\b", TOKENS)}
        used = {c.upper() for c in re.findall(r"#[0-9A-Fa-f]{3,6}\b", re.search(r"<style>(.*?)</style>", self.page, re.S).group(1))}
        self.assertTrue(used)
        self.assertEqual(used - known, set(), "a colour that is not in brand/tokens.css")

    def test_it_has_one_style_and_one_script_which_the_policy_hashes(self):
        h = sv.csp_hashes(self.page)
        self.assertEqual((len(h["style"]), len(h["script"])), (1, 1))
        policy = sv.csp_policy(af.offline_page())
        self.assertIn(h["script"][0], policy)
        self.assertIn(h["style"][0], policy)
        self.assertNotIn("unsafe-inline'", re.search(r"script-src ([^;]*)", policy).group(1))

    def test_it_is_not_the_page_it_has_no_boot_block(self):
        self.assertNotIn("clark-boot", self.page)


def lum(hex_colour):
    """WCAG relative luminance of #RRGGBB (or #RGB)."""
    h = hex_colour.lstrip("#")
    h = "".join(c * 2 for c in h) if len(h) == 3 else h
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255
        out.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]


def contrast(a, b):
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def page_blocks(page):
    """(light, dark) as {--name: colour} read from the page's two variable blocks."""
    css = re.search(r"<style>(.*?)</style>", page, re.S).group(1)
    light = re.search(r":root\{([^}]*)\}", css).group(1)
    dark = re.search(r"prefers-color-scheme:dark\)\{:root\{([^}]*)\}", css).group(1)
    read = lambda block: dict(re.findall(r"(--[\w-]+):(#[0-9A-Fa-f]{3,6})", block))
    return read(light), read(dark)


def token_in(mode, name):
    """A token from brand/tokens.css: the light block, or the dark block over it. Read by the test's own patterns."""
    light = re.search(r"^:root \{(.*?)^\}", TOKENS, re.S | re.M).group(1)
    dark = re.search(r"^:root\[data-theme=dark\] \{(.*?)^\}", TOKENS, re.S | re.M).group(1)
    for block in ([dark, light] if mode == "dark" else [light]):
        m = re.search(re.escape(name) + r":\s*(#[0-9A-Fa-f]{3,6})\s*;", block)
        if m:
            return m.group(1).upper()
    raise AssertionError(name)


class OfflinePageColours(unittest.TestCase):
    """#142: the offline page takes its colours from brand/tokens.css when it is built."""

    def setUp(self):
        self.page = af.offline_page().decode("utf-8")
        self.light, self.dark = page_blocks(self.page)

    def test_no_placeholder_is_left(self):
        self.assertEqual(re.findall(r"@[A-Z_]+@", self.page), [])

    def test_the_two_blocks_hold_the_token_values_for_each_role(self):
        roles = {"--bg": "--grey-50", "--surface": "--surface", "--ink": "--brand-ink", "--muted": "--grey-700", "--line": "--grey-300"}
        for mode, block in (("light", self.light), ("dark", self.dark)):
            for var, tok in roles.items():
                self.assertEqual(block[var].upper(), token_in(mode, tok), f"{mode} {var} should be {tok}")
        self.assertEqual(self.light["--accent"].upper(), token_in("light", "--brand-blue"))
        self.assertEqual(self.light["--accent-ink"].upper(), token_in("light", "--text-on-brand"))

    def test_the_dark_button_keeps_the_light_blue_not_the_dark_brand_blue(self):
        self.assertNotIn("--accent", self.dark, "the dark block must not override the button fill")
        self.assertNotEqual(self.light["--accent"].upper(), token_in("dark", "--brand-blue"))

    def test_no_colour_sits_outside_the_two_variable_blocks(self):
        css = re.search(r"<style>(.*?)</style>", self.page, re.S).group(1)
        rest = re.sub(r":root\{[^}]*\}", "", css)
        self.assertEqual(re.findall(r"#[0-9A-Fa-f]{3,6}\b|rgba?\(|hsla?\(", rest), [])

    def test_text_contrast_is_at_least_4_5_in_both_modes(self):
        for mode, b in (("light", self.light), ("dark", self.dark)):
            fill = self.light["--accent"]  # the button is the same in both modes
            ink_on = (b["--ink"], b["--bg"], "ink on background")
            muted_on = (b["--muted"], b["--surface"], "muted on surface")
            btn = (self.light["--accent-ink"], fill, "button text on button fill")
            for fg, bg, what in (ink_on, muted_on, btn):
                self.assertGreaterEqual(contrast(fg, bg), 4.5, f"{mode}: {what} is {contrast(fg, bg):.2f}:1")

    def test_a_tokens_file_that_breaks_the_pattern_fails_clearly(self):
        no_dark = TOKENS.replace(":root[data-theme=dark]", ":root[data-x=dark]")
        with self.assertRaises((AttributeError, KeyError)):
            af.token_value(no_dark, "dark", "--grey-50")
        with self.assertRaises(KeyError):
            af.token_value(TOKENS, "light", "--no-such-token")


class TheStartFilesNameNoOutsideAddress(unittest.TestCase):
    """Nothing in the launcher, the manifest, the worker or the offline page names an address outside this computer."""

    FILES = ("clark.command", "src/clark/launch.py", "src/clark/appfiles.py", "src/clark/idle.py", "src/clark/app/sw.js",
             "src/clark/app/offline.html")

    def test_only_127_0_0_1_is_ever_named(self):
        texts = {f: (ROOT / f).read_text(encoding="utf-8") for f in self.FILES}
        texts["manifest"] = af.manifest_json().decode("utf-8")
        for name, text in texts.items():
            for found in re.findall(r"(?:https?|wss?|ftp)://[^\s\"'<>)]*", text):
                self.assertTrue(found.startswith("http://127.0.0.1"), f"{name} names {found}")
            self.assertNotRegex(text, r"\b(curl|wget|pip|npm)\b", name)


class DataMark(unittest.TestCase):
    def test_it_is_sixteen_hex_characters_and_the_same_for_the_same_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a").mkdir()
            (Path(tmp) / "b").mkdir()
            a = af.data_mark(Path(tmp) / "a")
            self.assertRegex(a, r"^[0-9a-f]{16}$")
            self.assertEqual(a, af.data_mark(str(Path(tmp) / "a")))
            self.assertEqual(a, af.data_mark(Path(tmp) / "b" / ".." / "a"), "the folder's resolved path, not its spelling")
            self.assertNotEqual(a, af.data_mark(Path(tmp) / "b"))

    def test_it_does_not_hold_the_path(self):
        self.assertNotIn("tmp", af.data_mark("/tmp"))


class HealthAnswer(unittest.TestCase):
    def test_a_plain_call_gets_exactly_ok_true(self):
        self.assertEqual(af.health_answer(None, "abc"), {"ok": True})
        self.assertEqual(af.health_answer("", "abc"), {"ok": True})

    def test_the_launcher_s_mark_is_told_whether_it_is_the_same_data_folder(self):
        self.assertEqual(af.health_answer("abc", "abc"), {"ok": True, "this_data": True})
        self.assertEqual(af.health_answer("xyz", "abc"), {"ok": True, "this_data": False})


class TheCopiesAreRecorded(unittest.TestCase):
    """the reuse record: the new copies have their rows, and the live server still has exactly one."""

    def setUp(self):
        self.rows = [l for l in (ROOT / "docs" / "REUSE-FROM-CREAITE.md").read_text(encoding="utf-8").splitlines() if l.startswith("|")]

    def row(self, path):
        found = [r for r in self.rows if path in r]
        self.assertEqual(len(found), 1, path)
        return found[0]

    def test_launcher_worker_and_offline_page(self):
        self.assertIn("src/clark/launch.py", self.row("system/scripts/launch.py"))
        self.assertIn("src/clark/app/sw.js", self.row("system/templates/app/sw.js"))
        self.assertIn("src/clark/app/offline.html", self.row("system/templates/app/offline.html"))

    def test_exactly_one_live_server_row_and_it_names_the_new_files(self):
        found = [r for r in self.rows if "live_server.py" in r and "v2.6.9 `db5adb2`" in r]
        self.assertEqual(len(found), 1)
        for name in ("src/clark/appfiles.py", "src/clark/idle.py", "app_manifest", "vault_mark", "watch_for_close"):
            self.assertIn(name, found[0])


if __name__ == "__main__":
    unittest.main()
