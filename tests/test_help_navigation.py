"""#642 step 3, Navigation: the pure parts. The five jobs on Start here, the contents list, "What next" links and the history of places.

Run: python3 dev/run_tests.py test_help_navigation
Quick tier: no browser. The page's pure functions (helpLogic.js) are bundled by the pinned esbuild and run in node (skips with no node),
the same way test_help_guides.py does. The panel as drawn, the keys and the widths are in test_help_nav_page.py (a browser).

THE RULE for a job: it is shown only while the how-to entry it opens is shown (the held list, helpLater.json). A job whose entry is held
keeps its words held: it is in no list, no search, no link and not in the built page. The words of the five jobs are the signed
mockup's (docs/handoff/v1.0/mockups/help-start.html), except the fourth job's name: see TITLE_FOR_ARRANGE.
"""
import copy
import json
import unittest

from _help_shown import LATER, RAW, shown_content
from test_help_guides import FIXTURE, fixture_content, run_node
import build_page  # noqa: E402  (dev/tools, on the path through test_help_guides)

JOBS = ["add-a-work-item", "write-the-weekly-report", "add-a-section-from-a-template", "arrange-the-report", "publish-the-report"]
# The owner's decision (item-642.md section 8) names the fourth job "Move, hide and delete sections", and the signed mockup uses it. The
# never-delete rule (test_help_shown.NeverDelete: Help says Archive, and Delete only as the section button is labelled) refuses the word
# "delete" anywhere else in Help's words, so the job carries its entry's own title until the owner rules. Not loosened here.
TITLE_FOR_ARRANGE = "Arrange the report’s sections"
MOCKUP = {
    "add-a-work-item": ("Add a work item", "Put a new task on the plan and say who owns it."),
    "write-the-weekly-report": ("Write this week’s report", "Fill in the status, the highlights and the next steps."),
    "add-a-section-from-a-template": ("Add a section from a template", "Start a new section from a ready-made layout."),
    "arrange-the-report": (TITLE_FOR_ARRANGE, "Change the order of the report, or take parts out."),
    "publish-the-report": ("Publish to the client", "Check the report, then send the finished copy."),
}


class TheFiveJobs(unittest.TestCase):
    def test_the_source_holds_the_five_jobs_in_the_owners_order_with_the_mockups_words(self):
        self.assertEqual([j[0] for j in RAW["start"]["jobs"]], JOBS)
        for j in RAW["start"]["jobs"]:
            self.assertEqual((j[1], j[2]), MOCKUP[j[0]], j[0])
        self.assertEqual((RAW["start"]["text"]["undo_lead"], RAW["start"]["text"]["undo_link"]), ("Made a mistake?", "Undo the last change"))
        self.assertNotIn("excel", json.dumps(RAW["start"]["jobs"]).lower(), "bringing in an Excel workbook is not a start page job")

    def test_only_the_jobs_with_a_shown_entry_are_shown_and_the_rest_are_held(self):
        shown = shown_content()
        ids = {t["id"] for t in shown["howto"]["tasks"]}
        self.assertEqual([j[0] for j in shown["start"]["jobs"]], [j for j in JOBS if j in ids])
        self.assertEqual([j[0] for j in shown["start"]["jobs"]], ["add-a-section-from-a-template", "arrange-the-report"])
        held = [j for j in JOBS if j in LATER["howto"]]
        self.assertEqual(held, ["add-a-work-item", "write-the-weekly-report", "publish-the-report"])
        self.assertTrue(set(held).isdisjoint(j[0] for j in shown["start"]["jobs"]))

    def test_the_undo_link_is_held_with_its_entry(self):
        self.assertIn("undo-a-mistake", LATER["howto"])
        s = shown_content()["start"]
        self.assertEqual((s["undo"], s["text"]["undo_lead"], s["text"]["undo_link"]), ("", "", ""))

    def test_a_job_whose_entry_is_released_shows_with_its_words(self):
        """Mutation check: with nothing held all five and the Undo link appear, in the owner's order (the rule bites both ways)."""
        s = shown_content(RAW, {})["start"]
        self.assertEqual([j[0] for j in s["jobs"]], JOBS)
        self.assertEqual((s["undo"], s["text"]["undo_link"]), ("undo-a-mistake", "Undo the last change"))
        one = {"howto": {"publish-the-report": "later"}}
        self.assertEqual([j[0] for j in shown_content(RAW, one)["start"]["jobs"]], JOBS[:4])

    def test_a_held_job_leaves_no_word_and_no_link_in_the_shown_content(self):
        text = json.dumps(shown_content(), ensure_ascii=False)
        for i in ("add-a-work-item", "write-the-weekly-report", "publish-the-report"):
            self.assertNotIn(MOCKUP[i][1], text, f"the held job {i} shows its description")
            self.assertNotIn(f"howto-{i}", text)
        self.assertNotIn("Made a mistake?", text)
        self.assertNotIn("Undo the last change", text)

    def test_the_built_page_has_no_held_job_words(self):
        built = build_page.help_content_path(True).read_text(encoding="utf-8")
        for i in ("add-a-work-item", "write-the-weekly-report", "publish-the-report"):
            self.assertNotIn(MOCKUP[i][1], built, i)
        self.assertNotIn("Undo the last change", built)
        self.assertIn(MOCKUP["arrange-the-report"][1], built)
        self.assertEqual([j[0] for j in json.loads(built)["start"]["jobs"]], ["add-a-section-from-a-template", "arrange-the-report"])

    def test_the_browsers_copy_and_the_python_copy_agree_on_the_jobs(self):
        r = run_node(RAW, "(() => ({ shown: HL.content.start.jobs.map((j) => j[0]), undo: HL.undoLink(), list: HL.jobs().map((j) => j.place) }))()")
        self.assertEqual(r["shown"], ["add-a-section-from-a-template", "arrange-the-report"])
        self.assertEqual(r["list"], ["howto-add-a-section-from-a-template", "howto-arrange-the-report"])
        self.assertIsNone(r["undo"])
        r = run_node(RAW, "(() => { HL.useHeld({}); return { shown: HL.content.start.jobs.map((j) => j[0]), undo: HL.undoLink() }; })()")
        self.assertEqual(r["shown"], JOBS)
        self.assertEqual(r["undo"], {"lead": "Made a mistake?", "link": "Undo the last change", "place": "howto-undo-a-mistake"})

    def test_a_held_job_is_not_in_the_search_the_places_or_the_contents_list(self):
        r = run_node(RAW, "(() => { const i = HL.buildIndex(); return { places: HL.placeIds(), words: HL.search(i, 'highlights').filter((x) => x.id === 'start-jobs').length, list: HL.tabList('start')[0].entries.map((e) => e.place),"
                     " where: HL.placeOf('howto-add-a-work-item', 'start') }; })()")
        self.assertEqual(r["words"], 0)
        self.assertNotIn("howto-add-a-work-item", r["places"])
        self.assertNotIn("howto-add-a-work-item", r["list"])
        self.assertEqual(r["list"], ["start-jobs", "howto-add-a-section-from-a-template", "howto-arrange-the-report"])
        self.assertFalse(r["where"]["known"])

    def test_the_jobs_part_is_searchable_by_a_shown_jobs_words(self):
        r = run_node(RAW, "(() => HL.search(HL.buildIndex(), 'ready-made').map((x) => x.id))()")
        self.assertEqual(r[0], "start-jobs")


class WhatNext(unittest.TestCase):
    def test_a_next_list_gives_shown_places_with_their_titles_in_order_once_each(self):
        first = "howto-" + next(t["id"] for t in shown_content()["howto"]["tasks"])
        r = run_node(RAW, "(() => HL.nextOf([%s, 'ref-keys', %s, 'howto-add-a-work-item', 'howto-nothing', 5, null]))()" % (json.dumps(first), json.dumps(first)))
        self.assertEqual([n["place"] for n in r], [first, "ref-keys"])
        self.assertTrue(all(n["title"] for n in r))

    def test_a_held_place_is_never_a_what_next_link(self):
        held = ["howto-" + i for i in LATER["howto"]] + ["ref-" + i for i in LATER["reference"]]
        self.assertTrue(held)
        r = run_node(RAW, "HL.nextOf(%s)" % json.dumps(held + ["start-top"]))
        self.assertEqual(r, [])

    def test_no_next_list_gives_nothing(self):
        r = run_node(RAW, "[HL.nextOf(undefined), HL.nextOf([]), HL.nextOf('ref-keys'), HL.nextOf({})]")
        self.assertEqual(r, [[], [], [], []])

    def test_a_guide_next_agrees_with_the_guides_own_links(self):
        c = fixture_content()
        r = run_node(c, "(() => ({ a: HL.nextOf(HL.guide('fixture-guide').next), b: HL.nextLinks('fixture-guide') }))()")
        self.assertEqual([(n["place"], n["title"]) for n in r["a"]], [(n["place"], n["title"]) for n in r["b"] if n["known"]])

    def test_a_guide_joins_the_how_to_contents_list_without_a_heading(self):
        r = run_node(fixture_content(), "(() => { const l = HL.tabList('howto'); return { last: l[l.length - 1], n: l.length }; })()")
        self.assertEqual(r["last"], {"group": "", "entries": [{"id": "fixture-guide", "title": "Fixture guide", "place": "guide-fixture-guide"}]})
        self.assertEqual(r["n"], len(shown_content()["howto"]["groups"]) + 1)
        r = run_node(RAW, "HL.tabList('howto').filter((g) => !g.group).length")
        self.assertEqual(r, 0, "no guide shipped: no unnamed group")

    def test_a_held_guide_is_in_no_list_and_no_next(self):
        c = copy.deepcopy(fixture_content())
        r = run_node(c, "(() => { HL.useHeld({ guides: { 'fixture-guide': 'later' } }); return { l: HL.tabList('howto').filter((g) => !g.group).length, n: HL.nextOf(['guide-fixture-guide']) }; })()")
        self.assertEqual(r, {"l": 0, "n": []})
        self.assertEqual(FIXTURE["id"], "fixture-guide")


class History(unittest.TestCase):
    """The small history of places (helpLogic.js trailVisit, trailBack, firstPlace) behind the way back beside Back."""
    def run_trail(self, probe):
        return run_node(RAW, probe)

    def test_a_visit_adds_the_place_left_and_never_the_same_twice_in_a_row(self):
        r = self.run_trail("(() => { let t = []; t = HL.trailVisit(t, 'a', 'b'); t = HL.trailVisit(t, 'b', 'c'); const x = t.slice(); t = HL.trailVisit(t, 'c', 'c');"
                           " t = HL.trailVisit(t, 'b', 'd'); return { x, t }; })()")
        self.assertEqual(r["x"], ["a", "b"])
        self.assertEqual(r["t"], ["a", "b"], "moving to the place you are at changes nothing, and b is already the latest")

    def test_back_gives_the_latest_place_and_a_shorter_history(self):
        r = self.run_trail("(() => { const t = ['a', 'b', 'c']; const one = HL.trailBack(t); const two = HL.trailBack(one.trail); return { t, one, two, none: HL.trailBack([]), bad: HL.trailBack(null) }; })()")
        self.assertEqual(r["t"], ["a", "b", "c"], "the history given is not changed")
        self.assertEqual(r["one"], {"place": "c", "trail": ["a", "b"]})
        self.assertEqual(r["two"], {"place": "b", "trail": ["a"]})
        self.assertEqual(r["none"], {"place": None, "trail": []})
        self.assertEqual(r["bad"], {"place": None, "trail": []})

    def test_nothing_is_added_from_nowhere_and_the_history_is_capped(self):
        r = self.run_trail("(() => { let t = []; t = HL.trailVisit(t, null, 'a'); t = HL.trailVisit(t, '', 'a'); const empty = t.slice();"
                           " for (let i = 0; i < 50; i++) t = HL.trailVisit(t, 'p' + i, 'p' + (i + 1)); return { empty, n: t.length, cap: HL.TRAIL_MAX, last: t[t.length - 1], first: t[0] }; })()")
        self.assertEqual(r["empty"], [])
        # 20: the cap is a choice (a reader keeps a handful of places in mind), not a measurement
        self.assertEqual((r["cap"], r["n"], r["last"], r["first"]), (20, 20, "p49", "p30"))

    def test_a_tab_opens_at_its_first_entry(self):
        r = self.run_trail("({ start: HL.firstPlace('start'), howto: HL.firstPlace('howto'), reference: HL.firstPlace('reference'), none: HL.firstPlace('nothing') })")
        self.assertEqual(r["start"], "start-jobs")
        self.assertEqual(r["howto"], "howto-" + shown_content()["howto"]["tasks"][0]["id"])
        self.assertEqual(r["reference"], "ref-" + shown_content()["reference"]["sections"][0]["id"])
        self.assertIsNone(r["none"])


if __name__ == "__main__":
    unittest.main()
