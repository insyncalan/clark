"""#642 step 2 and #645 step 1: the shape of Help's guides, and the page key on entries (helpContent.json, helpLogic.js).

Run: python3 dev/run_tests.py test_help_guides
Quick tier: no browser. The page's own pure functions are bundled by the pinned esbuild and run in node (the tests skip when node
is not on the machine). The shipped source holds the two guides of #642 guides A (add a section from a template; move, hide and delete sections).
The fixture guide below exists only here, added in memory to a copy of the real source and bundled in its place, so the loader, the
search and the shape rules are tested without depending on any shipped wording.
The words of the entries are tested in test_help_content.py, the held list in test_help_shown.py.
"""
import copy
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _help_shown import LATER, RAW, shown_content
from _paths import SRC

import esbuild  # noqa: E402  (dev/tools)
import build_page  # noqa: E402  (dev/tools)

HELP = SRC / "clark" / "page" / "src" / "help"
MODULE = HELP / "helpLogic.js"
LIVE_SCREENS = json.loads(re.search(r"LIVE_SCREENS = (\[.*?\]);", (HELP / "helpStore.js").read_text(encoding="utf-8")).group(1))

SHOWN_TASKS = [t["id"] for t in shown_content()["howto"]["tasks"]]     # what is not held: a link may only point at these

# A fixture guide (test only): two numbered steps, one with a picture, a result line, links to a how-to entry and a reference section.
FIXTURE = {
    "id": "fixture-guide", "t": "Fixture guide", "job": "Check that a wombat can read it.",
    "steps": [{"d": "Open the **Zebra** screen.", "pic": "pic-one"}, {"d": "Press `Quokka` twice."}],
    "result": "A numbat arrives.", "next": ["howto-" + SHOWN_TASKS[0], "ref-keys"],
}


def check_guides(content):
    """What is wrong with the guides of a content object, as a list of sentences (empty: the shape holds)."""
    bad, declared = [], [p["id"] for p in content.get("pictures", [])]
    places = {"start-" + p for p in ("top", "loop", "first", "jobs", "where", "rules", "foot")}
    places |= {"howto-" + t["id"] for t in content["howto"]["tasks"]} | {"ref-" + s["id"] for s in content["reference"]["sections"]}
    places |= {"guide-" + g["id"] for g in content.get("guides", [])}
    if len(declared) != len(set(declared)):
        bad.append("a picture id is declared more than once")
    ids = [g["id"] for g in content.get("guides", [])]
    if len(ids) != len(set(ids)):
        bad.append("a guide id is used more than once")
    for g in content.get("guides", []):
        for k in ("id", "t", "job", "result"):
            if not str(g.get(k, "")).strip():
                bad.append(f"{g.get('id')}: no {k}")
        if not g.get("steps"):
            bad.append(f"{g.get('id')}: no numbered steps")
        for n, s in enumerate(g.get("steps", []), 1):
            if not str(s.get("d", "")).strip():
                bad.append(f"{g.get('id')}: step {n} has no text")
            if s.get("pic") and s["pic"] not in declared:
                bad.append(f"{g.get('id')}: step {n} shows the undeclared picture {s['pic']}")
        if not g.get("next"):
            bad.append(f"{g.get('id')}: no next links")
        for p in g.get("next", []):
            if p not in places:
                bad.append(f"{g.get('id')}: the next link {p} is not a place")
    return bad


def fixture_content():
    c = copy.deepcopy(RAW)
    c["guides"] = [copy.deepcopy(FIXTURE)]
    c["pictures"] = [{"id": "pic-one", "alt": "The Zebra screen"}]
    return c


def bundle(content, tmp):
    src = Path(tmp) / "content.json"
    src.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")
    out = Path(tmp) / "hl.js"
    done = esbuild.run(["--bundle", "--format=iife", "--global-name=HL", f"--alias:clark-help-content={src}", str(MODULE), f"--outfile={out}"],
                       capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return out.read_text(encoding="utf-8")


def run_node(content, probe):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    with tempfile.TemporaryDirectory() as tmp:
        code = bundle(content, tmp) + ";\nconsole.log(JSON.stringify(" + probe + "));"
        script = Path(tmp) / "probe.js"      # the bundle holds all of helpContent.json: a file, never one argument (Linux allows 128 KB for one)
        script.write_text(code, encoding="utf-8")
        done = subprocess.run([node, str(script)], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout)


class ShippedSource(unittest.TestCase):
    def test_no_command_line_argument_carries_the_help_content(self):
        """Linux allows one command-line argument only 128 KB: the node probes (here and in test_help_peek_logic) must pass the bundle as a file."""
        import test_help_peek_logic as pl
        from unittest import mock
        seen = []
        real = subprocess.run
        def spy(cmd, *a, **k):
            seen.extend(len(x.encode("utf-8")) for x in cmd)
            return real(cmd, *a, **k)
        with mock.patch.object(subprocess, "run", spy):
            run_node(RAW, "1")
            pl.run_node("1")
        self.assertTrue(seen)
        self.assertLess(max(seen), 100 * 1024, "an argument built from the Help content is too long for Linux")
        with tempfile.TemporaryDirectory() as tmp:
            self.assertGreater(len(bundle(RAW, tmp).encode("utf-8")), 100 * 1024, "the bundle is past the limit, so passing it as an argument would fail: this check bites")

    def test_the_nine_guides_are_shipped_and_hold_the_shape(self):
        """#642 guides A, B and C together: the pictures its steps draw are checked in test_help_guide_pictures."""
        self.assertEqual([g["id"] for g in RAW["guides"]], ["add-a-section-from-a-template", "arrange-the-report", "bring-in-an-excel-workbook", "send-the-workbook-out", "publish-to-the-client", "hand-an-item-over", "save-a-view", "see-the-dashboard-as-at-a-day", "back-up-and-restore-your-data"])
        self.assertEqual([len(g["steps"]) for g in RAW["guides"]][:5], [6, 7, 8, 7, 8])
        self.assertEqual(check_guides(RAW), [])

    def test_the_held_list_names_no_guide_that_does_not_exist(self):
        self.assertEqual(set(LATER.get("guides", {})) - {g["id"] for g in RAW["guides"]}, set())
        self.assertEqual(shown_content()["guides"], RAW["guides"])


class GuideShape(unittest.TestCase):
    def test_the_fixture_guide_has_the_shape(self):
        self.assertEqual(check_guides(fixture_content()), [])

    def test_the_rules_find_each_fault(self):
        def broken(**change):
            c = fixture_content()
            c["guides"][0].update(change)
            return check_guides(c)
        self.assertTrue(any("no numbered steps" in b for b in broken(steps=[])))
        self.assertTrue(any("no result" in b for b in broken(result="")))
        self.assertTrue(any("no next links" in b for b in broken(next=[])))
        self.assertTrue(any("is not a place" in b for b in broken(next=["howto-nothing-here"])))
        self.assertTrue(any("undeclared picture" in b for b in broken(steps=[{"d": "x", "pic": "pic-two"}])))
        c = fixture_content()
        c["pictures"].append({"id": "pic-one", "alt": "again"})
        self.assertTrue(any("declared more than once" in b for b in check_guides(c)))

    def test_the_loader_numbers_the_steps_and_lists_the_pictures(self):
        r = run_node(fixture_content(), "(() => ({ all: HL.guides().map((g) => g.id), g: HL.guide('fixture-guide'), none: HL.guide('nope'),"
                     " pics: HL.pictureIds(), next: HL.nextLinks('fixture-guide'), nextNone: HL.nextLinks('nope'), places: HL.placeIds(),"
                     " where: HL.placeOf('guide-fixture-guide', 'start'), badWhere: HL.placeOf('guide-nope', 'start') }))()")
        self.assertEqual(r["all"], ["fixture-guide"])
        self.assertEqual(r["g"]["place"], "guide-fixture-guide")
        self.assertEqual([(s["n"], s["pic"], s["text"]) for s in r["g"]["steps"]],
                         [(1, "pic-one", "Open the Zebra screen."), (2, None, "Press Quokka twice.")])
        self.assertEqual(r["g"]["result"], "A numbat arrives.")
        self.assertIsNone(r["none"])
        self.assertEqual(r["pics"], ["pic-one"])
        self.assertEqual([(n["place"], n["known"]) for n in r["next"]],
                         [("howto-" + SHOWN_TASKS[0], True), ("ref-keys", True)])
        self.assertEqual(r["next"][0]["title"], next(t["t"] for t in RAW["howto"]["tasks"] if t["id"] == SHOWN_TASKS[0]))
        self.assertEqual(r["nextNone"], [])
        self.assertIn("guide-fixture-guide", r["places"])
        self.assertEqual(r["where"], {"tab": "howto", "target": "guide-fixture-guide", "known": True})
        self.assertEqual(r["badWhere"]["known"], False)

    def test_the_index_finds_a_guide_its_steps_and_its_result(self):
        r = run_node(fixture_content(), "(() => { const idx = HL.buildIndex(); const f = (q) => HL.search(idx, q).map((x) => [x.id, x.line]);"
                     " return { zebra: f('zebra'), quokka: f('quokka'), title: f('fixture guide'), job: f('wombat'), result: f('numbat'),"
                     " lines: idx.find((e) => e.id === 'guide-fixture-guide').lines }; })()")
        self.assertEqual(r["zebra"], [["guide-fixture-guide", 1]])                    # step 1 is line 1 (line 0 is the job)
        self.assertEqual(r["quokka"], [["guide-fixture-guide", 2]])
        self.assertEqual(r["title"][0][0], "guide-fixture-guide")
        self.assertEqual(r["job"][0], ["guide-fixture-guide", 0])
        self.assertEqual(r["result"], [["guide-fixture-guide", 3]])
        self.assertEqual(r["lines"][1], "1. Open the Zebra screen.")

    def test_a_held_guide_leaves_the_search_the_places_and_the_context(self):
        c = fixture_content()
        c["guides"][0]["page"] = ["work"]
        r = run_node(c, "(() => { HL.useHeld({ guides: { 'fixture-guide': 'later' } }); const idx = HL.buildIndex();"
                     " return { guides: HL.guides().length, found: HL.search(idx, 'zebra').length, places: HL.placeIds().filter((p) => p.startsWith('guide-')),"
                     " ctx: HL.contextFor('work').filter((e) => e.id === 'fixture-guide').length }; })()")
        self.assertEqual(r, {"guides": 0, "found": 0, "places": [], "ctx": 0})
        self.assertEqual(shown_content(c, {"guides": {"fixture-guide": "later"}})["guides"], [])

    def test_the_index_is_what_it_was_without_guides_pictures_and_page_keys(self):
        """The new keys add nothing to what is searched: the source without them gives the identical index, held list or not."""
        old = copy.deepcopy(RAW)
        old["guides"], old["pictures"] = [], []
        for e in old["howto"]["tasks"] + old["reference"]["sections"]:
            e.pop("page", None)
        raw = copy.deepcopy(RAW)
        raw["guides"] = []                 # the shipped guides add their own entries to the index; what else is searched is unchanged
        probe = "(() => { const a = HL.buildIndex(); HL.useHeld({}); return { shown: a, all: HL.buildIndex() }; })()"
        self.assertEqual(run_node(old, probe), run_node(raw, probe))
        self.assertTrue(run_node(raw, probe)["all"])

    def test_the_built_page_has_no_held_guide(self):
        """The built Help (held entries left out of the file the page is bundled from) holds no guide id, place or word of a held guide."""
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / "help"
            fake.mkdir()
            (fake / "helpContent.json").write_text(json.dumps(fixture_content(), ensure_ascii=False), encoding="utf-8")
            (fake / "helpLater.json").write_text(json.dumps({"guides": {"fixture-guide": "later"}}), encoding="utf-8")
            was = build_page.HELP, build_page.SHOWN_DIR
            build_page.HELP, build_page.SHOWN_DIR = fake, fake / "shown"
            try:
                built = build_page.help_content_path(True)
            finally:
                build_page.HELP, build_page.SHOWN_DIR = was
            text = built.read_text(encoding="utf-8")
            self.assertNotIn("fixture-guide", text)
            self.assertNotIn("wombat", text)
            self.assertEqual(json.loads(text)["guides"], [])
            r = run_node(json.loads(text), "({ guides: HL.guides().length, places: HL.placeIds().filter((p) => p.startsWith('guide-')),"
                         " found: HL.search(HL.buildIndex(), 'zebra').length })")
            self.assertEqual(r, {"guides": 0, "places": [], "found": 0})



SHIPPED = [g for g in shown_content()["guides"] if g["id"] in ("add-a-section-from-a-template", "arrange-the-report")]      # the two guides of #642 guides A (the others: test_help_guides_excel_publish)
HELD_PLACES = {"howto-" + i for i in LATER.get("howto", {})} | {"ref-" + i for i in LATER.get("reference", {})} \
    | {"guide-" + i for i in LATER.get("guides", {})} | {"start-" + i for i in LATER.get("start", {})}


class ShippedGuides(unittest.TestCase):
    """The guides as shipped (#642 guides A, B and C): their shape, their links, the names they use and that search finds them."""

    def test_each_guide_has_five_to_eight_numbered_steps_a_result_and_next_links(self):
        self.assertEqual(len(SHIPPED), 2)
        for g in SHIPPED:
            self.assertTrue(5 <= len(g["steps"]) <= 8, g["id"])
            self.assertTrue(g["job"].strip() and g["result"].strip() and g["next"], g["id"])
        r = run_node(RAW, "HL.guides().map((g) => [g.id, g.steps.map((s) => s.n), HL.nextLinks(g.id).map((n) => n.known)])")
        for gid, numbers, known in r:
            self.assertEqual(numbers, list(range(1, len(numbers) + 1)), gid)
            self.assertTrue(known and all(known), f"{gid}: a next link goes nowhere")

    def test_every_next_link_is_a_shown_place_and_a_held_place_is_never_linked(self):
        shown = {"howto-" + t["id"] for t in shown_content()["howto"]["tasks"]} | {"ref-" + s["id"] for s in shown_content()["reference"]["sections"]} \
            | {"guide-" + g["id"] for g in SHIPPED}
        self.assertTrue(HELD_PLACES)
        for g in SHIPPED:
            for p in g["next"]:
                self.assertIn(p, shown, f"{g['id']}: {p}")
                self.assertNotIn(p, HELD_PLACES, f"{g['id']}: {p} is held")
            self.assertNotIn(("guide-" + g["id"]), g["next"], "a guide does not link to itself")
        # and the page itself, with a held list that holds everything the guides link to, shows none of those links
        held = {"howto": {"publish-the-report": "later", "undo-a-mistake": "later"}, "reference": {"section-templates": "later"}, "guides": {"arrange-the-report": "later"}}
        r = run_node(RAW, "(() => { HL.useHeld(%s); return HL.guides().map((g) => [g.id, HL.nextOf(g.next).map((n) => n.place)]); })()" % json.dumps(held))
        self.assertEqual([x for x in r if x[0] in ("add-a-section-from-a-template", "arrange-the-report")], [["add-a-section-from-a-template", []]])

    def test_the_two_start_jobs_open_the_guides_and_the_how_to_entries_stay_reachable(self):
        r = run_node(RAW, "(() => ({ jobs: HL.jobs().map((j) => [j.id, j.place]), howto: HL.tabList('howto').flatMap((g) => g.entries.map((e) => e.place)),"
                     " more: HL.tabList('start').filter((g) => g.group === 'Also under How do I...').flatMap((g) => g.entries.map((e) => e.place)) }))()")
        places = dict(r["jobs"])
        self.assertEqual(places["add-a-section-from-a-template"], "guide-add-a-section-from-a-template")
        self.assertEqual(places["arrange-the-report"], "guide-arrange-the-report")
        for i in ("add-a-section-from-a-template", "arrange-the-report"):
            self.assertIn("howto-" + i, r["howto"])
            self.assertIn("howto-" + i, r["more"])
        # a job whose guide is held opens its how-to entry instead
        r = run_node(RAW, "(() => { HL.useHeld({ guides: { 'arrange-the-report': 'later' } }); return HL.jobs().map((j) => [j.id, j.place]); })()")
        self.assertEqual(dict(r)["arrange-the-report"], "howto-arrange-the-report")
        self.assertEqual(dict(r)["add-a-section-from-a-template"], "guide-add-a-section-from-a-template")

    def test_the_words_the_guides_use_for_the_templates_are_the_templates_names(self):
        templates = (SRC / "clark" / "page" / "src" / "logic" / "templates.js").read_text(encoding="utf-8")
        text = " ".join(s["d"] for g in SHIPPED for s in g["steps"])
        for name in re.findall(r"\*\*(Key figures, four|Callout|Text and pictures|Figures|Work items|Files and links|People and dates|Notes)\*\*", text):
            self.assertIn(f'"{name}"', templates, name)

    def test_search_finds_each_guide_and_its_steps(self):
        probes = {"add-a-section-from-a-template": [("place you choose", 0), ("search templates", 3), ("where it goes", 5), ("cancel", 6), ("empty section", 7)],
                  "arrange-the-report": [("drag its move button", 2), ("full width", 5), ("eye mark", 6), ("removes the section", 7), ("gone from view", 8)]}
        for gid, rows in probes.items():
            for word, line in rows:
                r = run_node(RAW, "(() => HL.search(HL.buildIndex(), %s).filter((x) => x.id === 'guide-%s').map((x) => x.line))()" % (json.dumps(word), gid))
                self.assertIn(line, r, f"{gid}: '{word}' should find line {line}, found {r}")
        r = run_node(RAW, "(() => ['Add a section from a template', 'Move, hide and delete sections'].map((q) => HL.search(HL.buildIndex(), q).slice(0, 2).map((x) => x.id)))()")
        self.assertEqual([sorted(x) for x in r], [["guide-add-a-section-from-a-template", "howto-add-a-section-from-a-template"], ["guide-arrange-the-report", "howto-arrange-the-report"]])      # the guide and the how-to entry of the same name

    def test_the_shipped_index_holds_one_entry_for_each_guide(self):
        r = run_node(RAW, "(() => ({ guides: HL.guides().map((g) => g.id), idx: HL.buildIndex().filter((e) => e.id.startsWith('guide-')).length }))()")
        self.assertEqual(r, {"guides": [g["id"] for g in RAW["guides"]], "idx": 9})


def page_values(content):
    for kind, key in (("howto", "tasks"), ("reference", "sections")):
        for e in content[kind][key]:
            for p in e.get("page", []):
                yield kind, e["id"], p


class PageKey(unittest.TestCase):
    def test_every_page_value_is_a_live_screen_or_one_of_its_settings_cards(self):
        seen = 0
        for kind, i, p in page_values(RAW):
            screen, _, card = p.partition("#")
            self.assertIn(screen, LIVE_SCREENS, f"{kind} {i}: {p}")
            if card:
                self.assertEqual(screen, "settings", f"{kind} {i}: only Settings has cards")
                self.assertRegex(card, r"^[a-z][a-z-]*$")
            seen += 1
        self.assertGreater(seen, 0)

    def test_a_page_list_is_a_list_of_distinct_values(self):
        for e in RAW["howto"]["tasks"] + RAW["reference"]["sections"]:
            if "page" in e:
                self.assertIsInstance(e["page"], list)
                self.assertTrue(e["page"], f"{e['id']}: an empty page list")
                self.assertEqual(len(e["page"]), len(set(e["page"])), e["id"])

    def test_a_how_to_entry_names_the_screen_its_go_field_names(self):
        for t in RAW["howto"]["tasks"]:
            go = t.get("go", "")
            if go.split("#")[0] in LIVE_SCREENS:
                self.assertEqual(t.get("page"), [go], t["id"])
            else:
                self.assertNotIn("page", t, f"{t['id']}: go is {go!r}, not a screen Help can open")

    def test_context_for_agrees_with_the_source_on_every_screen_and_card_and_never_returns_a_held_entry(self):
        cards = sorted({p for _, _, p in page_values(RAW) if "#" in p})
        probe = "(() => { const o = {}; for (const p of %s) o[p] = HL.contextFor(p).map((e) => e.place); return o; })()" % json.dumps(LIVE_SCREENS + cards + ["publish", "nothing", ""])
        r = run_node(RAW, probe)
        shown = shown_content()
        held = {"howto-" + i for i in LATER.get("howto", {})} | {"ref-" + i for i in LATER.get("reference", {})}
        self.assertTrue(held)
        for page, places in r.items():
            screen = page.split("#")[0]
            want = [("howto-" + t["id"]) for t in shown["howto"]["tasks"] if matches(t, page, screen)] + \
                   [("ref-" + s["id"]) for s in shown["reference"]["sections"] if matches(s, page, screen)]
            self.assertEqual(places, want, page)
            self.assertEqual(set(places) & held, set(), f"{page} returns a held entry")
        self.assertEqual((r["publish"], r["nothing"], r[""]), ([], [], []))

    def test_context_for_leaves_out_an_entry_held_later_and_keeps_a_stable_order(self):
        c = copy.deepcopy(RAW)
        for e in c["howto"]["tasks"]:
            if e["id"] in SHOWN_TASKS[:2]:
                e["page"] = ["work"]
        r = run_node(c, "(() => { const a = HL.contextFor('work').map((e) => e.place); HL.useHeld({ howto: { '" + SHOWN_TASKS[0] + "': 'later' } });"
                     " return { a, b: HL.contextFor('work').map((e) => e.place), again: HL.contextFor('work').map((e) => e.place) }; })()")
        self.assertIn("howto-" + SHOWN_TASKS[0], r["a"])
        self.assertNotIn("howto-" + SHOWN_TASKS[0], r["b"])
        self.assertEqual(r["b"], r["again"])
        order = [t["id"] for t in c["howto"]["tasks"]]
        ids = [p[len("howto-"):] for p in r["a"] if p.startswith("howto-")]
        self.assertEqual(ids, sorted(ids, key=order.index))


# The Settings cards on the page, by the part that draws each (components/Views.jsx, Settings): the visible title of the card.
# A part the page adds that is not here fails the rule below, so the new card's line is written with it.
# Asking is left out on purpose: it is the ask clark switch, and Help holds every entry about ask clark (helpLater.json).
SETTINGS_PARTS = {"ClientFolder": "Publishing", "PublishedReports": "Published reports", "Personal": "Personal", "ReviewDays": "Freshness", "GanttSetting": "Gantt",
                  "Diagnostics": "Logs and diagnostics", "Safety": "Backups", "People": "People", "Projects": "Projects", "Data": "Data", "Update": "Version and updates"}
SETTINGS_LEFT_OUT = {"AskSettings"}
PAGE_SRC = HELP.parent
WORDS_NOT_USED = re.compile(r"\b(apply|applied|staged|proposal|sweep|tracker|vault|extract)\b", re.I)


def settings_parts():
    code = (PAGE_SRC / "components" / "Views.jsx").read_text(encoding="utf-8")
    body = code[code.index("export function Settings"):]
    body = body[:body.index("\n}\n")]
    return set(re.findall(r"\{(\w+) \? <\1 />", body))


class ContextText(unittest.TestCase):
    """#645 step 2: the words the peek shows for each screen. A rule, not a count: a screen with no text fails (#645 section 8)."""
    CTX = {c["page"]: c for c in RAW["context"]}

    @classmethod
    def shown_places(cls):
        s = shown_content()
        return {"howto-" + t["id"] for t in s["howto"]["tasks"]} | {"ref-" + t["id"] for t in s["reference"]["sections"]}

    def test_every_screen_has_context_text(self):
        self.assertEqual(sorted(self.CTX), sorted(LIVE_SCREENS), "every screen of LIVE_SCREENS needs its text, and no other screen has one")
        self.assertEqual(len(RAW["context"]), len(LIVE_SCREENS))
        for page, c in self.CTX.items():
            self.assertTrue(c["title"].strip() and "\n" not in c["title"], page)
            self.assertGreaterEqual(len(c["s"]), 2, f"{page}: at least two sentences")
            self.assertLessEqual(len(c["s"]), 5, f"{page}: at most five sentences")
            for line in c["s"]:
                self.assertTrue(line.strip().endswith("."), f"{page}: {line!r} is not a sentence")
                self.assertLess(len(line), 160, f"{page}: {line!r} is not short")
            self.assertIn(c["full"], self.shown_places(), f"{page}: full is a held or unknown place")

    def test_the_settings_text_has_a_line_for_every_settings_card_on_the_page(self):
        found = settings_parts()
        self.assertTrue(found, "the page's own list of Settings cards was not read")
        unknown = found - set(SETTINGS_PARTS) - SETTINGS_LEFT_OUT
        self.assertEqual(unknown, set(), "the page has a Settings card with no title here: add it to SETTINGS_PARTS and write its line")
        titles = {k["title"]: k for k in self.CTX["settings"]["cards"]}
        want = {SETTINGS_PARTS[p] for p in found if p in SETTINGS_PARTS}
        self.assertEqual(set(titles), want)
        for t, k in titles.items():
            self.assertTrue(k["line"].strip().endswith("."), t)
            self.assertLess(len(k["line"]), 110, f"{t}: one short line")
        ids = [k["card"] for k in self.CTX["settings"]["cards"]]
        self.assertEqual(len(ids), len(set(ids)))
        for page, c in self.CTX.items():
            if page != "settings":
                self.assertNotIn("cards", c, page)

    def test_each_card_title_is_a_title_the_page_shows(self):
        names = ("ClientFolder.jsx", "Personal.jsx", "ReviewDays.jsx", "GanttSetting.jsx", "Diagnostics.jsx", "People.jsx", "Safety.jsx", "PublishedReports.jsx", "Projects.jsx", "Data.jsx")
        code = " ".join((PAGE_SRC / "edit" / f).read_text(encoding="utf-8") for f in names)
        code += " " + (PAGE_SRC / "logic" / "safety.js").read_text(encoding="utf-8") + (PAGE_SRC / "logic" / "update.js").read_text(encoding="utf-8") + (PAGE_SRC / "logic" / "pastReports.js").read_text(encoding="utf-8")
        for title in SETTINGS_PARTS.values():
            self.assertIn(title, code, title)

    def test_the_bold_names_are_on_the_page(self):
        code = "\n".join(f.read_text(encoding="utf-8") for f in PAGE_SRC.rglob("*.js*") if f.parent != HELP).replace("’", "'")
        gone = sorted({b for c in RAW["context"] for ln in c["s"] for b in re.findall(r"\*\*(.+?)\*\*", ln)
                       if not re.search(r"(?<![\w])" + re.escape(b.strip(" .,:;")) + r"(?![\w])", code)})
        self.assertEqual(gone, [], "context text names a control the page does not have")

    def test_the_words_follow_the_house_rules(self):
        every = []
        for c in RAW["context"]:
            every += [c["title"]] + c["s"] + [k["title"] + " " + k["line"] for k in c.get("cards", [])]
        for t in every:
            self.assertIsNone(WORDS_NOT_USED.search(t), t)
            self.assertIsNone(re.search(r"\bask clark\b", t), f"{t!r}: ask clark is not named in the context text")
            self.assertNotRegex(t, r"^clark\b")
            self.assertNotRegex(t, r"\d{4}-\d{2}-\d{2}")

    def test_context_text_reaches_the_peek_by_screen_and_never_targets_a_held_place(self):
        pages = LIVE_SCREENS + ["settings#pubs", "publish", "", "nothing"]
        probe = ("(() => { const o = {}; for (const p of %s) { const t = HL.contextText(p); o[p] = t && { title: t.title, full: t.full, "
                 "fullTitle: t.fullTitle, cards: t.cards.length, plain: t.lines.join(' ') }; } return o; })()") % json.dumps(pages)
        r = run_node(RAW, probe)
        for s in LIVE_SCREENS:
            self.assertEqual(r[s]["title"], self.CTX[s]["title"])
            self.assertEqual(r[s]["full"], self.CTX[s]["full"])
            self.assertTrue(r[s]["fullTitle"])
            self.assertNotIn("**", r[s]["plain"])
        self.assertEqual(r["settings"]["cards"], len(self.CTX["settings"]["cards"]))
        self.assertEqual(r["work"]["cards"], 0)
        self.assertEqual(r["settings#pubs"]["title"], "Settings")
        self.assertEqual((r["publish"], r[""], r["nothing"]), (None, None, None))
        # A place held later is never a target: the text then has no link rather than a link to a part that is not built.
        full = self.CTX["work"]["full"]
        h = run_node(RAW, "(() => { HL.useHeld({ reference: { '" + full[4:] + "': 'later' } }); const t = HL.contextText('work'); return { full: t.full, fullTitle: t.fullTitle }; })()")
        self.assertEqual(h, {"full": None, "fullTitle": None})


def matches(e, page, screen):
    return any(p == page or (p.split("#")[0] == screen and (page == screen or p == screen)) for p in e.get("page", []))


if __name__ == "__main__":
    unittest.main()
