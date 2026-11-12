"""Every place Help sends a person to still exists (queue item 9, after the Settings menu change).

Run: python3 dev/run_tests.py test_help_links_exist
Quick tier: reads files, starts no browser (the built page.html is read as text).

Checked, with the exact dead target and the Help entry that names it:
  1. a go link (inline "(go:...)", an entry's "go", a start job's screen, a start "where" screen) names a screen Help can open, and a
     Settings anchor ("settings#x") is one the Settings screen has;
  2. an entry's `page` list names such screens and anchors;
  3. "Settings > Name" and "Settings, Name" in Help (and in held Help) name a Settings page or card that exists;
  4. every Settings page or card heading id is in the built page.html, and the router has the view Help calls "Published reports";
  5. no code (comments included) names a Settings anchor that does not exist.
Two shapes of Settings are read from the source: one page at a time (edit/settingsPages.js, router.SETTINGS_PAGES, helpStore's
SETTINGS_ANCHOR) and the earlier list of cards (CARDS in components/Views.jsx).
"""
import json
import re
import unittest

from _paths import ROOT

PAGE_SRC = ROOT / "src" / "clark" / "page" / "src"
HELP = PAGE_SRC / "help"
FILES = ("helpContent.json", "helpLater.json", "helpHeld.json")


def read(path):
    return path.read_text(encoding="utf-8")


def list_of(src, name):
    m = re.search(r"export const %s = \[(.*?)\]" % name, src, re.S)
    return re.findall(r'"([^"]+)"', m.group(1)) if m else []


LOGIC = read(HELP / "helpLogic.js")
STORE = read(HELP / "helpStore.js")
VIEWS_JSX = read(PAGE_SRC / "components" / "Views.jsx")
ROUTER = read(PAGE_SRC / "router.js")
SCREENS = set(list_of(LOGIC, "SCREENS"))
LIVE = set(list_of(STORE, "LIVE_SCREENS"))
VIEWS = set(list_of(ROUTER, "VIEWS"))
SETTINGS_PAGES = list_of(ROUTER, "SETTINGS_PAGES")
PAGES_JS = PAGE_SRC / "edit" / "settingsPages.js"
RAW = {f: json.loads(read(HELP / f)) for f in FILES if (HELP / f).exists()}


def context_cards():
    ctx = [c for c in RAW["helpContent.json"].get("context", []) if c.get("page") == "settings"]
    return [k for c in ctx for k in c.get("cards", [])]


if PAGES_JS.exists():
    # one Settings page at a time: [group, [[key, name, tools, heading id], ...]]
    ENTRIES = re.findall(r'\["([\w-]+)", "([^"]+)", \[[^\]]*\], "([\w-]+)"\]', read(PAGES_JS))
    NAMES = {n for _, n, _ in ENTRIES}
    HEADS = {h for k, _, h in ENTRIES if k != "published"}     # Published reports is a page of its own, not a Settings page: no heading is moved to
    am = re.search(r"const SETTINGS_ANCHOR = \{(.*?)\}", STORE, re.S)
    ANCHORS = dict(re.findall(r"(\w+): \"([\w-]+)\"", am.group(1))) if am else {}     # anchor -> Settings page key
else:
    # the list of cards: [component, chip name, heading id]
    CARDS = re.findall(r'\["(\w+)", "([^"]*)", "([\w-]+)"\]', re.search(r"const CARDS = \[(.*?)\];", VIEWS_JSX, re.S).group(1))
    NAMES = {n for _, n, _ in CARDS if n} | {k["title"] for k in context_cards()}
    # "AI" is a card of its own inside Asking (edit/AiSettings.jsx, heading "AI"): Help names it as Settings > AI
    if "<h2>AI</h2>" in read(PAGE_SRC / "edit" / "AiSettings.jsx"):
        NAMES.add("AI")
    HEADS = {h for _, _, h in CARDS}
    ANCHORS = {k["card"]: k["card"] for k in context_cards()}
# words that follow "Settings," in a list of the profile circle's menu, not as a Settings page
MENU_WORDS = {"Appearance", "Help", "Publish", "Preview"}


def where(top, ctx):
    return ctx or top


def walk(o, top, ctx, path=()):
    """Yield (entry label, path, key or index, string) for every string; the label is the nearest entry with an id and a title."""
    if isinstance(o, dict):
        if "id" in o and ("t" in o or "title" in o):
            ctx = "%s %s \"%s\"" % (top, o["id"], o.get("t") or o.get("title"))
        for k, v in o.items():
            yield from walk(v, top, ctx, path + (k,))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from walk(v, top, ctx, path + (i,))
    elif isinstance(o, str):
        yield (ctx or top, path, o)


def targets(raw, top):
    """(entry, kind, target) for each go link and page name in one source file."""
    out = []
    for label, path, s in walk(raw, top, ""):
        last = path[-1] if path else None
        for m in re.finditer(r"\]\(go:([^)]+)\)", s):
            out.append((label, "go", m.group(1)))
        if last == "go" and s:
            out.append((label, "go", s))
        if len(path) >= 3 and path[:2] == ("start", "jobs") and last == 3 and s:
            out.append((label, "go", s))
        if len(path) >= 3 and path[:2] == ("start", "where") and last == 2 and s:
            out.append((label, "go", s))
        if "page" in path and isinstance(last, int) and path[-2] == "page":
            out.append((label, "page", s))
    return out


def names_in(s):
    """The word run after "Settings >" or "Settings," : the longest Settings name there, else the capitalised run."""
    found = []
    for m in re.finditer(r"Settings (›|,) ?(?=[A-Z])", s):
        rest = s[m.end():]
        hit = [n for n in NAMES if re.match(re.escape(n) + r"(?![\w])", rest)]
        if hit:
            continue
        run = re.match(r"[A-Z][\w]*(?: (?:and|[A-Z][\w]*))*", rest).group(0)
        if m.group(1) == "," and run.split(" ")[0] in MENU_WORDS:
            continue
        found.append(run)
    return found


class HelpLinksExist(unittest.TestCase):
    def dead(self):
        bad = []
        for f, raw in RAW.items():
            top = f.replace(".json", "")
            for label, kind, t in targets(raw, top):
                screen, _, anchor = t.partition("#")
                if kind == "go" and screen not in SCREENS:
                    bad.append("%s: %s names the screen %r, which Help cannot open (SCREENS)" % (label, t, screen))
                elif kind == "page" and screen not in LIVE:
                    bad.append("%s: page list names %r, not a screen (LIVE_SCREENS)" % (label, screen))
                elif anchor and screen == "settings" and anchor not in ANCHORS:
                    bad.append("%s: dead Settings anchor %s (%s has: %s)" % (label, t, "helpStore SETTINGS_ANCHOR" if PAGES_JS.exists() else "the Settings cards", ", ".join(sorted(ANCHORS))))
        return bad

    def test_go_links_and_page_lists_exist(self):
        self.assertGreater(sum(len(targets(r, f)) for f, r in RAW.items()), 40)       # measured 47 on main: the floor is a little less
        self.assertEqual(self.dead(), [])

    def test_settings_names_in_help_exist(self):
        bad = []
        for f, raw in RAW.items():
            for label, _, s in walk(raw, f.replace(".json", ""), ""):
                for run in names_in(s):
                    bad.append("%s: names Settings > %r, but Settings has: %s" % (label, run, ", ".join(sorted(NAMES))))
        self.assertGreater(sum(1 for f, r in RAW.items() for _, _, s in walk(r, f, "") if "Settings ›" in s), 10)
        self.assertEqual(bad, [])

    def test_every_settings_heading_is_in_the_built_page(self):
        page = read(ROOT / "src" / "clark" / "page" / "page.html")
        self.assertGreater(len(HEADS), 8)
        self.assertEqual(sorted(h for h in HEADS if not re.search(r'id[=:]\s*"%s"' % re.escape(h), page)), [])

    def test_the_published_reports_view_exists_when_help_names_it(self):
        text = json.dumps(RAW["helpContent.json"], ensure_ascii=False)
        self.assertIn("Profile circle › Published reports", text, "the check below is only worth anything while Help names the view")
        if "Profile circle › Published reports" in text:
            self.assertIn("published", VIEWS, "Help says the profile circle opens Published reports, but router.VIEWS has no such view")

    def test_the_settings_pages_agree_with_each_other(self):
        if not PAGES_JS.exists():
            self.skipTest("this tree has the list of cards, not one page at a time")
        keys = [k for k, _, _ in ENTRIES if k != "published"]
        self.assertEqual(sorted(SETTINGS_PAGES), sorted(keys), "router.SETTINGS_PAGES and settingsPages.js name different pages")
        for a, page in ANCHORS.items():
            self.assertIn(page, SETTINGS_PAGES, "helpStore SETTINGS_ANCHOR %s opens %s, which is not a Settings page" % (a, page))
        titles = {k["title"] for k in context_cards()} - {"Quit"}
        self.assertEqual(sorted(titles - NAMES), [], "Settings peek card titles that the menu does not name")

    def test_no_code_names_a_settings_anchor_that_is_not_there(self):
        bad = []
        for f in sorted(PAGE_SRC.rglob("*")):
            if f.suffix not in (".js", ".jsx") or not f.is_file():
                continue
            for m in re.finditer(r"settings#([\w-]+)", read(f)):
                if m.group(1) not in ANCHORS:
                    bad.append("%s names settings#%s, which Settings does not have (has: %s)" % (f.relative_to(ROOT), m.group(1), ", ".join(sorted(ANCHORS))))
            for m in re.finditer(r"#settings&s=([\w-]+)", read(f)):
                if SETTINGS_PAGES and m.group(1) not in SETTINGS_PAGES:
                    bad.append("%s names #settings&s=%s, not in router.SETTINGS_PAGES" % (f.relative_to(ROOT), m.group(1)))
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
