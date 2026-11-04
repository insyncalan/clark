"""#642 step 2 and #645 step 1: the shape of Help's guides, and the page key on entries (helpContent.json, helpLogic.js).

Run: python3 dev/run_tests.py test_help_guides
Quick tier: no browser. The page's own pure functions are bundled by the pinned esbuild and run in node (the tests skip when node
is not on the machine). The shipped source holds NO guide yet: the fixture guide below exists only here, added in memory to a copy
of the real source and bundled in its place, so the loader, the search and the shape rules are tested without any visible wording.
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
        done = subprocess.run([node, "-e", code], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout)


class ShippedSource(unittest.TestCase):
    def test_the_three_guides_are_shipped_and_hold_the_shape(self):
        """#642 steps 8 and 9: Excel in, Excel out and Publish to the client. No picture is declared here (the pictures live on another branch)."""
        self.assertEqual([g["id"] for g in RAW["guides"]], ["bring-in-an-excel-workbook", "send-the-workbook-out", "publish-to-the-client"])
        self.assertEqual(RAW["pictures"], [])
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
        old.pop("guides"), old.pop("pictures")
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

    def test_the_shipped_index_holds_one_entry_for_each_guide_and_no_picture(self):
        r = run_node(RAW, "(() => ({ guides: HL.guides().map((g) => g.id), pics: HL.pictureIds(), idx: HL.buildIndex().filter((e) => e.id.startsWith('guide-')).length }))()")
        self.assertEqual(r, {"guides": [g["id"] for g in RAW["guides"]], "pics": [], "idx": 3})


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

    def test_the_context_for_each_screen_today_is_recorded(self):
        """INFORMATION, not a rule: how many entries have context for each screen (and Settings card) today. It does not fail on a zero, only on a
        change from these numbers; the step that writes the context text adds the rule that every screen has some (#645 section 8)."""
        shown = shown_content()
        counts = {s: 0 for s in LIVE_SCREENS}
        cards = {}
        for kind, key in (("howto", "tasks"), ("reference", "sections")):
            for e in shown[kind][key]:
                for s in {p.split("#")[0] for p in e.get("page", [])}:
                    counts[s] += 1
                for p in e.get("page", []):
                    if "#" in p:
                        cards[p] = cards.get(p, 0) + 1
        print("\nHelp context per screen:", ", ".join(f"{s}={n}" for s, n in counts.items()), "| cards:", cards or "none")
        # The counts recorded when the key was added; the step that writes the context text raises them (and adds the rule that
        # none is zero), so it changes these numbers with it.
        self.assertEqual(counts, {"dashboard": 1, "dashboard+edit": 9, "work": 2, "milestones": 1, "settings": 2})      # measured on the tree with the four entries released (was 0, 8, 1, 1, 2)
        self.assertEqual(cards, {"settings#pubs": 1})

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


def matches(e, page, screen):
    return any(p == page or (p.split("#")[0] == screen and (page == screen or p == screen)) for p in e.get("page", []))


if __name__ == "__main__":
    unittest.main()
