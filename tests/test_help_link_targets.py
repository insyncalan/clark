"""Help links name Settings places that still exist after the Settings menu change (items 1024, 1087, 1248 to 1250).

Run: python3 dev/run_tests.py test_help_link_targets
Quick tier: reads files, starts no browser. Every go: link, every "go" and "page" field and every Settings path written in Help
words (Settings > Folder, Settings, Folder) must name a screen Help can open, a Settings page in the menu, or an anchor that
helpStore.js maps to one. The page the anchor opens must hold the heading that takes the focus.
"""
import json
import re
import unittest

from _paths import ROOT

PAGE = ROOT / "src" / "clark" / "page" / "src"
HELP = PAGE / "help"
STORE = (HELP / "helpStore.js").read_text(encoding="utf-8")
PAGES_JS = (PAGE / "edit" / "settingsPages.js").read_text(encoding="utf-8")
ROUTER = (PAGE / "router.js").read_text(encoding="utf-8")
SOURCES = ("helpContent.json", "helpHeld.json", "helpLater.json")

ANCHORS = dict(re.findall(r"(\w+): \"([\w-]+)\"", re.search(r"const SETTINGS_ANCHOR = \{(.*?)\};", STORE, re.S).group(1)))
SCREENS = set(re.search(r"LIVE_SCREENS = \[(.*?)\]", STORE, re.S).group(1).replace('"', "").replace(" ", "").split(","))
SCREENS |= set(re.search(r"export const SCREENS = \[(.*?)\]", (HELP / "helpLogic.js").read_text(encoding="utf-8"), re.S).group(1).replace('"', "").replace(" ", "").split(","))
SLUGS = re.search(r"SETTINGS_PAGES = \[(.*?)\]", ROUTER, re.S).group(1).replace('"', "").replace(" ", "").split(",")
# [slug, name, heading id] for each page of the menu (the "published" entry opens a page of its own, not a Settings page)
MENU = re.findall(r"\[\"([\w-]+)\", \"([^\"]+)\", \[[^\]]*\], \"([\w-]+)\"\]", PAGES_JS)
NAMES = [n for _, n, _ in MENU] + re.findall(r"\[\"([A-Z][\w ]+)\", \[\[", PAGES_JS)
SOURCE_TEXT = {n: (HELP / n).read_text(encoding="utf-8") for n in SOURCES}


def strings(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, list):
        for i in x:
            yield from strings(i)
    elif isinstance(x, dict):
        for i in x.values():
            yield from strings(i)


class HelpLinkTargets(unittest.TestCase):
    def test_the_menu_was_read(self):
        self.assertEqual(sorted(SLUGS), sorted(["projects", "people", "profile", "folder", "brand", "appearance", "reports", "backups", "export", "claude-ai", "logs", "version"]))
        self.assertIn("Folder", NAMES)
        self.assertIn("Publishing", NAMES)          # a group name, not a page
        self.assertTrue(ANCHORS and SCREENS)

    def test_every_anchor_maps_to_a_page_that_exists(self):
        for a, slug in ANCHORS.items():
            with self.subTest(anchor=a):
                self.assertIn(slug, SLUGS, "settings#%s opens a page the menu does not have" % a)
                head = [h for s, _, h in MENU if s == slug]
                self.assertTrue(head, "no menu entry for %s" % slug)
                self.assertTrue(any(('id="%s"' % head[0]) in f.read_text(encoding="utf-8") or ('"%s"' % head[0]) in f.read_text(encoding="utf-8")
                                    for f in (PAGE / "edit").glob("*.jsx")), "no heading %s on the page" % head[0])

    def test_every_help_link_target_exists(self):
        for name, text in SOURCE_TEXT.items():
            targets = set(re.findall(r"\]\(go:([^)]+)\)", text)) | set(re.findall(r"\"go\": \"([^\"]*)\"", text)) | set(re.findall(r"\"(settings#[\w-]*)\"", text))
            for t in sorted(targets - {""}):
                with self.subTest(file=name, target=t):
                    screen, _, anchor = t.partition("#")
                    self.assertIn(screen, SCREENS, "no such screen")
                    if screen == "settings" and anchor:
                        self.assertIn(anchor, ANCHORS, "settings#%s is not mapped in SETTINGS_ANCHOR, so the link opens Projects" % anchor)

    def test_no_link_names_a_removed_settings_anchor(self):
        for name, text in SOURCE_TEXT.items():
            for dead in ("settings#pubs", "settings#personal", "settings#data", "settings#publishing"):
                self.assertNotIn(dead, text, name)

    def test_settings_paths_in_help_words_name_a_menu_page(self):
        """Settings > Folder, Settings › Folder and Settings, Folder: the word after Settings is a page or a group of the menu."""
        say = re.compile(r"Settings\s*(?:›|>|,)\s*([A-Z][A-Za-z ]*)")
        for name in SOURCES:
            for s in strings(json.loads(SOURCE_TEXT[name])):
                for m in say.finditer(s):
                    with self.subTest(file=name, words=m.group(0)):
                        self.assertTrue(any(m.group(1).startswith(n) for n in NAMES), "Settings has no page or group called that")

    def test_the_page_words_name_a_menu_page(self):
        """The words the page itself shows (a link, a hint): same rule, read from the source of the page's own parts."""
        say = re.compile(r"[\"'`>]\s*(?:Set it in |In |the |)Settings(?:,| ›| >) ?([A-Z][A-Za-z ]*?)[\"'`<.]")
        seen = 0
        for f in (PAGE / "edit").rglob("*.js*"):
            for line in f.read_text(encoding="utf-8").splitlines():
                if line.lstrip().startswith("//"):
                    continue
                for m in say.finditer(line):
                    seen += 1
                    with self.subTest(file=f.name, words=m.group(0)):
                        self.assertTrue(any(m.group(1).startswith(n) for n in NAMES), "Settings has no page or group called that")
        self.assertTrue(seen)

    def test_the_folder_link_lands_on_an_element_that_exists(self):
        """The To client link opens Settings on Folder and focuses the card with this id; the id must be on the Folder page's card."""
        state = (PAGE / "edit" / "publishState.js").read_text(encoding="utf-8")
        self.assertIn('openSettings("folder")', state)
        self.assertIn('getElementById("publishing")', state)
        self.assertIn('id="publishing"', (PAGE / "edit" / "ClientFolder.jsx").read_text(encoding="utf-8"))
        folder = [t for s, _, _ in MENU if s == "folder" for t in re.findall(r"\[\"folder\", \"Folder\", \[([^\]]*)\]", PAGES_JS)]
        self.assertIn("ClientFolder", folder[0])

    def test_every_openSettings_call_names_a_page(self):
        for f in PAGE.rglob("*.js*"):
            for slug in re.findall(r"\bopenSettings\(\"([\w-]+)\"\)", f.read_text(encoding="utf-8")):
                with self.subTest(file=f.name, page=slug):
                    self.assertIn(slug, SLUGS)


if __name__ == "__main__":
    unittest.main()
