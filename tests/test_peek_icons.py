"""#78: the peek's coloured icons. Run: python3 dev/run_tests.py test_peek_icons

Part 1 is the tone rules (page/src/iconColours.js), run in node when node is on the machine. Part 2 reads the committed tokens and
the style rules: every icon colour is a design token (no colour is written anywhere else), and each is at least 3:1 on the peek's
background and on its Changed highlight in light and in dark. Part 3 is the page in a real browser at 1400 and 900 px, light and
dark: every item in the demo data is opened, each icon has its tone and sits beside its words, the colour on screen is the token's
colour, the icon reaches 3:1 and the words beside it 4.5:1, and every word shown is plain. The data is the demo data (fictional).
"""
import json
import re
import shutil
import subprocess
import unittest

from _paths import ROOT

import test_peek as tp  # noqa: E402
from test_dark_contrast import dark_blocks, ratio  # noqa: E402
from test_server import chrome, wait  # noqa: E402

SRC = ROOT / "src" / "clark" / "page" / "src"
SHELL = ROOT / "src" / "clark" / "page" / "shell.css"
TOKENS = ROOT / "src" / "clark" / "brand" / "tokens.css"
TONES = ("r", "a", "g", "b", "n")
ICON_TOKENS = {"r": "--icon-red", "a": "--icon-amber", "g": "--icon-green", "b": "--icon-blue", "n": "--icon-grey"}
ROW_ICON = {"status": "half", "priority": "bars", "due": "cal"}
SHELL_MARK = "/* The peek's coloured icons"


def hexes(block):
    out = {}
    for n, v in re.findall(r"(--[\w-]+):\s*(#[0-9A-Fa-f]{6}|#[0-9A-Fa-f]{3})(?![\w])", block):
        out[n] = ("#" + "".join(c * 2 for c in v[1:]) if len(v) == 4 else v).upper()
    return out


def code_of(text):
    """A script without its comments (a comment may name an item number such as #42)."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return "\n".join(re.sub(r"(?<!:)//.*", "", line) for line in text.splitlines())


def refs(block):
    return dict(re.findall(r"(--[\w-]+):\s*var\((--[\w-]+)\)\s*;", block))


def token_modes():
    """[(mode, {token: '#RRGGBB'})]: light, then each dark block, with every var() chain followed to its colour."""
    css = TOKENS.read_text(encoding="utf-8")
    light_css = css.split("/* dark mode")[0]
    blocks = re.findall(r":root\[data-theme=(?:dark|auto)\]\s*\{(.*?)\n\s*\}", css, re.S)
    out = []
    for label, texts in [("light", [light_css])] + [("dark", [light_css, b]) for b in blocks]:
        colours, links = {}, {}
        for t in texts:
            colours.update(hexes(t))
            links.update(refs(t))
        for _ in range(5):
            for name, target in links.items():
                if target in colours:
                    colours[name] = colours[target]
        out.append((label, colours))
    return out


def icon_definitions():
    css = TOKENS.read_text(encoding="utf-8")
    return dict(re.findall(r"(--icon-[\w-]+):\s*(.*?);", css))


class ToneRules(unittest.TestCase):
    def run_js(self, body):
        node = shutil.which("node")
        if not node:
            self.skipTest("no node")
        code = f'import * as I from "{(SRC / "iconColours.js").as_uri()}"; {body}'
        done = subprocess.run([node, "--input-type=module", "-e", code], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def test_priority_urgent_red_high_amber_medium_blue_low_and_none_grey(self):
        out = self.run_js('console.log(JSON.stringify(["Urgent", "High", "Medium", "Low", null, "", "Odd"].map(I.priorityTone)))')
        self.assertEqual(out, ["r", "a", "b", "n", "n", "n", "n"])

    def test_the_date_is_red_late_amber_within_a_week_blue_later_and_grey_with_none(self):
        today = "2026-10-28"
        act = lambda due, status="Open": {"kind": "action", "status": status, "due_date": due}
        cases = [(act("2026-10-27"), "r"), (act("2026-10-28"), "a"), (act("2026-11-04"), "a"), (act("2026-11-05"), "b"),
                 (act(None), "n"), (act("not a day"), "n"), (act("2026-10-01", "Closed"), "b"), (act("2026-10-01", "Cancelled"), "b"),
                 ({"kind": "risk", "status": "Open", "due_date": "2026-10-20"}, "r"),
                 ({"kind": "decision", "status": "Pending", "needed_by": "2026-10-30"}, "a"),
                 ({"kind": "decision", "status": "Pending", "needed_by": "2026-10-01"}, "r"),
                 ({"kind": "decision", "status": "Made", "date": "2026-10-01"}, "b")]
        out = self.run_js(f"const C = {json.dumps([c for c, _ in cases])}; console.log(JSON.stringify(C.map((r) => I.dateTone(r, {json.dumps(today)}))))")
        self.assertEqual(out, [want for _, want in cases])

    def test_the_status_takes_the_pills_own_tone_and_an_unknown_tone_is_grey(self):
        today = "2026-10-28"
        rows = [{"kind": "action", "status": "Open", "due_date": "2026-10-20"}, {"kind": "action", "status": "Delayed", "due_date": None},
                {"kind": "risk", "status": "Open", "priority": "High"}, {"kind": "decision", "status": "Made"},
                {"kind": "issue", "status": "Closed", "priority": "High"}]
        out = self.run_js(f"console.log(JSON.stringify([{json.dumps(rows)}.map((r) => I.statusTone(r, {json.dumps(today)})), "
                          f"[\"r\", \"x\", undefined].map(I.iconClass)]))")
        self.assertEqual(out, [["r", "a", "r", "g", "n"], ["ic-r", "ic-n", "ic-n"]])


class TokensOnly(unittest.TestCase):
    def test_each_icon_colour_is_one_committed_token_and_nothing_else(self):
        defs = icon_definitions()
        self.assertEqual(sorted(defs), sorted(ICON_TOKENS.values()))
        css = TOKENS.read_text(encoding="utf-8")
        for name, value in defs.items():
            m = re.fullmatch(r"var\((--[\w-]+)\)", value.strip())
            self.assertIsNotNone(m, f"{name} is a colour written out: {value}")
            self.assertRegex(css, rf"(?m)[\s{{;]{re.escape(m.group(1))}:", f"{name} names {m.group(1)}, which tokens.css does not set")
            self.assertFalse(m.group(1).startswith("--icon"), name)

    def test_the_style_rules_take_icon_colours_from_icon_tokens_only(self):
        css = SHELL.read_text(encoding="utf-8")
        self.assertIn(SHELL_MARK, css)
        mine = css[css.index(SHELL_MARK):]
        self.assertNotRegex(mine, r"#[0-9a-fA-F]{3,8}\b")
        self.assertNotRegex(mine, r"\b(rgb|rgba|hsl|hsla|oklch|color-mix)\(")
        for tone, token in ICON_TOKENS.items():
            self.assertRegex(mine, rf"\.ic-{tone} \{{ color: var\({token}\); \}}")
        colours = re.findall(r"(?<![\w-])color:\s*([^;}]+)", mine)
        self.assertEqual(len(colours), 5, colours)
        self.assertTrue(all(c.strip().startswith("var(--icon-") for c in colours), colours)

    def test_no_script_or_component_writes_a_colour(self):
        for name in ("iconColours.js", "components/Peek.jsx", "components/Icon.jsx"):
            text = code_of((SRC / name).read_text(encoding="utf-8"))
            self.assertNotRegex(text, r"#[0-9a-fA-F]{3,8}\b", name)
            self.assertNotRegex(text, r"\b(rgb|rgba|hsl|hsla)\(", name)
        self.assertNotRegex(code_of((SRC / "components" / "Peek.jsx").read_text(encoding="utf-8")), r"style=\{?[\"`][^\"`]*color", "no inline colour")

    def test_the_icon_shapes_are_plain_and_take_the_text_colour_of_their_tone(self):
        icons = (SRC / "components" / "Icon.jsx").read_text(encoding="utf-8")
        for name in ROW_ICON.values():
            line = next((x for x in icons.splitlines() if x.strip().startswith(f"{name}:")), None)
            self.assertIsNotNone(line, name)
            self.assertNotRegex(line, r"#[0-9a-fA-F]{3,8}|rgb|stroke=|style=", name)
            self.assertNotIn("fill=\"", line.replace('fill="currentColor"', ""), "a fill is the current colour or none")

    def test_the_tokens_and_rules_are_in_both_built_pages_and_the_published_one_gains_no_route(self):
        for name in ("page.html", "page-view.html"):
            text = (ROOT / "src" / "clark" / "page" / name).read_text(encoding="utf-8")
            for token in ICON_TOKENS.values():
                self.assertIn(token, text, (name, token))
            self.assertIn(".ic-r", text, name)
        view = (ROOT / "src" / "clark" / "page" / "page-view.html").read_text(encoding="utf-8")
        for word in ("/api/sneak", "/api/change", "clarkPage", "Sneak peek"):
            self.assertNotIn(word, view)


class Contrast(unittest.TestCase):
    # the peek's background, and the highlight a row takes for a moment after a change
    BACKGROUNDS = ("--surface", "--flash")

    def test_every_icon_is_at_least_3_to_1_on_the_peek_and_its_highlight_in_light_and_dark(self):
        modes = token_modes()
        self.assertEqual([m for m, _ in modes], ["light", "dark", "dark"], "light, data-theme=dark and data-theme=auto")
        for mode, tokens in modes:
            for tone, token in ICON_TOKENS.items():
                for bg in self.BACKGROUNDS:
                    with self.subTest(mode=mode, icon=token, on=bg):
                        self.assertGreaterEqual(ratio(tokens[token], tokens[bg]), 3.0, f"{mode}: {token} {tokens[token]} on {bg} {tokens[bg]}")

    def test_the_words_beside_the_icons_are_at_least_4_5_to_1_in_light_and_dark(self):
        pairs = [("--text", "--surface"), ("--text-muted", "--surface"), ("--status-red-text", "--surface"),
                 ("--status-green-text", "--status-green-tint"), ("--status-amber-text", "--status-amber-tint"),
                 ("--status-red-text", "--status-red-tint"), ("--status-blue-text", "--brand-blue-tint"), ("--grey-700", "--grey-100")]
        for mode, tokens in token_modes():
            for fg, bg in pairs:
                with self.subTest(mode=mode, fg=fg, bg=bg):
                    self.assertGreaterEqual(ratio(tokens[fg], tokens[bg]), 4.5, f"{mode}: {fg} on {bg}")

    def test_the_check_can_fail(self):
        """The plain amber (the first thing to try) is 2.2:1 on white: the ratio code says so, so a weak token would be caught."""
        light = dict(token_modes())["light"]
        self.assertLess(ratio(light["--status-amber"], light["--surface"]), 3.0)
        self.assertLess(ratio(light["--grey-500"], light["--flash"]), 3.0)


def rgb_hex(text):
    nums = [int(float(x)) for x in re.findall(r"[\d.]+", text)[:3]]
    return "#%02X%02X%02X" % tuple(nums)


READ = """(() => {
  const probe = (css) => { const e = document.createElement('i'); e.style.cssText = css; document.body.appendChild(e); const v = getComputedStyle(e); const out = [v.color, v.backgroundColor]; e.remove(); return out; };
  const peek = document.querySelector('#peek'); if (!peek) return null;
  const tokens = {}; for (const n of ['--icon-red', '--icon-amber', '--icon-green', '--icon-blue', '--icon-grey', '--surface', '--flash']) tokens[n] = probe('color:var(' + n + ');background:var(' + n + ')')[0];
  const rows = {};
  for (const key of ['status', 'priority', 'due']) {
    const dd = peek.querySelector('[data-row=' + key + '] dd'); if (!dd) continue;
    const val = dd.querySelector('.pk-val'), tone = val.querySelector('span[class^=ic-]'), svg = tone.querySelector('svg');
    const word = (val.querySelector('.pill') || val), late = dd.querySelector('.due-l');
    const wordBg = val.querySelector('.pill') ? getComputedStyle(word).backgroundColor : getComputedStyle(peek).backgroundColor;
    rows[key] = { cls: tone.className, icon: svg.dataset.icn, hidden: svg.getAttribute('aria-hidden'), color: getComputedStyle(tone).color,
      words: val.textContent.trim(), wordColor: getComputedStyle(word).color, wordBg, pill: (val.querySelector('.pill') || {}).className || '',
      under: late ? late.textContent.trim() : '', underColor: late ? getComputedStyle(late).color : '', label: dd.getAttribute('aria-label') };
  }
  return { id: peek.dataset.peek, rows, tokens, bg: getComputedStyle(peek).backgroundColor };
})()"""

PLAIN_STATUS = {"Open", "Overdue", "Due soon", "Delayed", "Red", "Amber", "Green", "Not rated", "Closed", "Cancelled", "Made", "Withdrawn", "Pending"}
PLAIN_PRIORITY = {"Urgent", "High", "Medium", "Low", "—"}
DATE = re.compile(r"\d{2}-\d{2}-\d{4}|—")
UNDER = re.compile(r"Today|Tomorrow|Yesterday|\d+ days? late|In \d+ days?")
JARGON = re.compile(r"\b(tone|token|ic-|icon|undefined|null|NaN|var\(|css|hex|rgb)\b|--", re.I)


def days(a, b):
    from datetime import date
    return (date.fromisoformat(a) - date.fromisoformat(b)).days


def expected_date_tone(kind, status, iso, today="2026-10-28"):
    if not iso:
        return "n"
    if status in ("Closed", "Cancelled", "Made", "Withdrawn"):
        return "b"
    n = days(iso, today)
    return "r" if n < 0 else "a" if n <= 7 else "b"


class IconsBrowser(unittest.TestCase):
    setUpClass = tp.Browser.__dict__["setUpClass"]
    tearDownClass = tp.Browser.__dict__["tearDownClass"]
    load_page = tp.Browser.load_page

    def items(self):
        """(id, kind, status, priority, date) for every item the demo project has, from the data the page reads."""
        out = []
        for r in self.data["actions"]:
            out.append((r["id"], "action", r["status"], r["priority"], r["due_date"]))
        for r in self.data["raid"]:
            out.append((r["id"], str(r["type"]).lower(), r["status"], r["priority"], r["due_date"]))
        for r in self.data["decisions"]:
            out.append((r["id"], "decision", r["status"], None, r["needed_by"] if r["status"] == "Pending" else r["date"]))
        return out

    def read(self, cdp, sid, item):
        cdp.js(f"location.hash = '#work&p={self.code}&item={item}'", sid)
        self.assertTrue(wait(lambda: cdp.js("(() => { const p = document.querySelector('#peek'); return !!p && p.dataset.peek === " + json.dumps(item) + " && !!p.querySelector('.pk-val'); })()", sid)), item)
        return cdp.js(READ, sid)

    def check_item(self, got, item, theme):
        iid, kind, status, priority, due = item
        rows, tokens = got["rows"], got["tokens"]
        want = {"status": rows["status"]["pill"].split()[-1],
                "priority": {"Urgent": "r", "High": "a", "Medium": "b"}.get(priority, "n"),
                "due": expected_date_tone(kind, status, due)}
        self.assertEqual(set(rows), {"status", "due"} | ({"priority"} if kind != "decision" else set()), f"{iid}: a decision has no priority row")
        surface = rgb_hex(got["bg"])
        for key, row in rows.items():
            where = f"{iid} {key} ({theme})"
            self.assertEqual(row["cls"], f"ic-{want[key]}", where)
            self.assertEqual(row["icon"], ROW_ICON[key], where)
            self.assertEqual(row["hidden"], "true", f"{where}: the icon is hidden from a screen reader; the words carry it")
            self.assertEqual(rgb_hex(row["color"]), rgb_hex(tokens[ICON_TOKENS[want[key]]]), f"{where}: the colour on screen is the token's")
            self.assertGreaterEqual(ratio(rgb_hex(row["color"]), surface), 3.0, f"{where}: icon on the peek")
            self.assertGreaterEqual(ratio(rgb_hex(row["color"]), rgb_hex(tokens["--flash"])), 3.0, f"{where}: icon on its highlight")
            self.assertGreaterEqual(ratio(rgb_hex(row["wordColor"]), rgb_hex(row["wordBg"])), 4.5, f"{where}: the words")
            if row["under"]:
                self.assertGreaterEqual(ratio(rgb_hex(row["underColor"]), surface), 4.5, f"{where}: the words under the date")
            # never colour alone: the icon sits beside a written word, and its shape is the row's own
            self.assertTrue(row["words"], where)
        self.assertEqual(rows["status"]["words"], rows["status"]["words"].strip())
        self.assertIn(rows["status"]["words"], PLAIN_STATUS, iid)
        if "priority" in rows:
            self.assertIn(rows["priority"]["words"], PLAIN_PRIORITY, iid)
            if priority:
                self.assertEqual(rows["priority"]["words"], priority, "the priority is written, not only coloured")
        self.assertRegex(rows["due"]["words"], DATE, iid)
        if want["due"] == "r":
            self.assertRegex(rows["due"]["under"], r"late", f"{iid}: a red date says it is late")
        if want["due"] == "a":
            self.assertRegex(rows["due"]["under"], r"Today|Tomorrow|In \d+ days?", f"{iid}: an amber date says how soon")
        for row in rows.values():
            for text in (row["words"], row["under"]):
                self.assertNotRegex(text, JARGON, f"{iid}: {text!r}")
        if rows["due"]["under"]:
            self.assertRegex(rows["due"]["under"], UNDER, iid)

    def test_the_data_has_every_tone_to_check(self):
        """The check below is only as good as the data: the demo items must reach more than one tone in each row."""
        items = self.items()
        self.assertGreater(len(items), 10)
        self.assertGreaterEqual(len({expected_date_tone(i[1], i[2], i[4]) for i in items}), 3, "dates reach red, amber, blue or grey")
        self.assertGreaterEqual(len({i[3] for i in items if i[1] != "decision"}), 3, "more than two priorities")

    def test_every_item_shows_its_icons_in_their_tones_with_its_words_light_and_dark_at_both_widths(self):
        items = self.items()
        tones = {"status": set(), "priority": set(), "due": set()}
        for width in (1400, 900):
            with chrome() as cdp:
                s, sid = self.load_page(cdp, width)
                for theme in ("light", "dark"):
                    cdp.js(f"document.documentElement.dataset.theme = {json.dumps(theme)}", sid)
                    for item in items:
                        with self.subTest(width=width, theme=theme, item=item[0]):
                            got = self.read(cdp, sid, item[0])
                            self.check_item(got, item, theme)
                            for key, row in got["rows"].items():
                                tones[key].add(row["cls"])
                    if theme == "dark":
                        light_amber = got["tokens"]["--icon-amber"]
                self.assertNotEqual(light_amber, "", "dark tokens read")
        self.assertGreaterEqual(len(tones["status"]), 3, tones)
        self.assertGreaterEqual(len(tones["due"]), 3, tones)
        self.assertGreaterEqual(len(tones["priority"]), 3, tones)

    def test_the_colour_changes_with_the_theme_and_the_icon_is_not_the_only_thing_that_changes(self):
        """Dark is a real second look (the same icon takes a different colour), and each row keeps its own shape and its words."""
        late = next(i for i in self.items() if i[1] != "decision" and i[2] not in ("Closed", "Cancelled") and i[4] and days(i[4], "2026-10-28") < 0)
        with chrome() as cdp:
            s, sid = self.load_page(cdp, 1400)
            cdp.js("document.documentElement.dataset.theme = 'light'", sid)
            a = self.read(cdp, sid, late[0])
            cdp.js("document.documentElement.dataset.theme = 'dark'", sid)
            b = self.read(cdp, sid, late[0])
        self.assertNotEqual(a["rows"]["due"]["color"], b["rows"]["due"]["color"])
        self.assertEqual(a["rows"]["due"]["icon"], b["rows"]["due"]["icon"])
        self.assertEqual({r["icon"] for r in a["rows"].values()}, set(ROW_ICON.values()), "three different shapes, not one shape in three colours")
        self.assertRegex(a["rows"]["due"]["under"], "late")

    def test_a_milestone_peek_is_unchanged(self):
        """Only the work item's status, priority and date carry icons; a milestone's fields are the words they were."""
        text = (SRC / "components" / "Peek.jsx").read_text(encoding="utf-8")
        body = text[text.index("function MilestoneFields"):text.index("// The edge you drag")]
        self.assertNotIn("Toned", body)


class PlainWords(unittest.TestCase):
    """Every string the icons add, read from the source: there are none to hide, and none that sounds like code."""

    def test_the_icon_code_adds_no_visible_word(self):
        text = (SRC / "iconColours.js").read_text(encoding="utf-8")
        code = code_of(text)
        strings = set(re.findall(r'"([^"]*)"', code)) - {"./workItems.js"}
        allowed = set(TONES) | {"Urgent", "High", "Medium", "Low"}
        for s in strings:
            self.assertTrue(s in allowed, f"{s!r} would be a word nobody planned")

    def test_the_peek_adds_no_title_or_label_of_its_own_to_an_icon(self):
        text = (SRC / "components" / "Peek.jsx").read_text(encoding="utf-8")
        start = text.index("function Toned")
        toned = text[start:text.index("\n", start)]
        for attr in ("title=", "aria-label=", "alt="):
            self.assertNotIn(attr, toned, "the words beside the icon say it; a second name would be read twice")
        self.assertIn("children", toned)


if __name__ == "__main__":
    unittest.main()
