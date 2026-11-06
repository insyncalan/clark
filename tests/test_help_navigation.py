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
# The owner named the fourth job "Move, hide and delete sections" (item-642.md section 8, the signed mockups). It is used for the job, the contents
# list and the entry title; the never-delete test allows exactly that signed string (test_help_shown.SIGNED_DELETE).
TITLE_FOR_ARRANGE = "Move, hide and delete sections"
MOCKUP = {
    "add-a-work-item": ("Add a work item", "Put a new task on the plan and say who owns it."),
    "write-the-weekly-report": ("Write this week’s report", "Fill in the status, the highlights and the next steps."),
    "add-a-section-from-a-template": ("Add a section from a template", "Start a new section from a ready-made layout."),
    "arrange-the-report": (TITLE_FOR_ARRANGE, "Change the order of the report, or take parts out."),
    "publish-the-report": ("Publish to the client", "Check the report, then send the finished copy."),
}


GUIDE_JOBS = ["add-a-section-from-a-template", "arrange-the-report", "publish-the-report"]      # the jobs that open a guide (#642 guides A) rather than a how-to entry
JOB_PLACES = {i: ("guide-" if i in GUIDE_JOBS else "howto-") + ("publish-to-the-client" if i == "publish-the-report" else i) for i in ["add-a-work-item", "write-the-weekly-report", "add-a-section-from-a-template", "arrange-the-report", "publish-the-report", "undo-a-mistake"]}
ENTRIES = ["add-a-work-item", "write-the-weekly-report", "publish-the-report", "undo-a-mistake"]     # written for step 3, shown now
# Words the owner keeps out of what a person reads (and AI, which is not in this release).
BANNED = r"(?i)\b(apply|applied|applies|applying|staged|staging|proposal|proposals|sweep|tracker|vault|extract|extracted|extracts|AI)\b|Draft with|Claude"


class TheFiveJobs(unittest.TestCase):
    def test_the_source_holds_the_five_jobs_in_the_owners_order_with_the_signed_words(self):
        self.assertEqual([j[0] for j in RAW["start"]["jobs"]], JOBS)
        for j in RAW["start"]["jobs"]:
            self.assertEqual((j[1], j[2]), MOCKUP[j[0]], j[0])
        self.assertEqual(RAW["start"]["jobs"][3][1], "Move, hide and delete sections", "the owner's name for the job")
        t = RAW["start"]["text"]
        self.assertEqual((t["undo_lead"], t["undo_link"]), ("Made a mistake?", "Undo the last change"))
        self.assertEqual((t["jobs_head"], t["jobs_lead"], t["jobs_title"], t["jobs_more"]),
                         ("Start here", "Pick a job and follow the steps. Each one is short.", "The five jobs", "Also under How do I..."))
        self.assertNotIn("excel", json.dumps(RAW["start"]["jobs"]).lower(), "bringing in an Excel workbook is not a start page job")

    def test_all_five_jobs_and_the_undo_link_are_shown(self):
        s = shown_content()["start"]
        self.assertEqual([j[0] for j in s["jobs"]], JOBS)
        self.assertEqual((s["undo"], s["text"]["undo_link"]), ("undo-a-mistake", "Undo the last change"))
        ids = {t["id"] for t in shown_content()["howto"]["tasks"]}
        self.assertTrue(all(j in ids for j in JOBS), "every job opens an entry that is shown")

    def test_the_fourth_jobs_entry_carries_the_owners_name(self):
        t = next(x for x in RAW["howto"]["tasks"] if x["id"] == "arrange-the-report")
        self.assertEqual(t["t"], "Move, hide and delete sections")

    def test_a_job_whose_entry_is_held_is_not_shown_and_its_words_go_with_it(self):
        """The rule bites: hold one entry and its job (and the Undo link, for undo) leave the shown content, with their words."""
        s = shown_content(RAW, {"howto": {"publish-the-report": "later", "undo-a-mistake": "later"}})["start"]
        self.assertEqual([j[0] for j in s["jobs"]], JOBS[:4])
        self.assertEqual((s["undo"], s["text"]["undo_lead"], s["text"]["undo_link"]), ("", "", ""))
        text = json.dumps(shown_content(RAW, {"howto": {"publish-the-report": "later", "undo-a-mistake": "later"}}), ensure_ascii=False)
        self.assertNotIn(MOCKUP["publish-the-report"][1], text)
        self.assertNotIn("Undo the last change", text)
        self.assertNotIn("howto-publish-the-report", json.dumps(s))
        every = shown_content(RAW, {"howto": {i: "later" for i in JOBS}})["start"]
        self.assertEqual(every["jobs"], [])

    def test_the_built_page_holds_a_held_job_out(self):
        built = build_page.help_content_path(True).read_text(encoding="utf-8")
        self.assertEqual([j[0] for j in json.loads(built)["start"]["jobs"]], JOBS)
        self.assertIn(MOCKUP["publish-the-report"][1], built)

    def test_the_browsers_copy_and_the_python_copy_agree_on_the_jobs(self):
        r = run_node(RAW, "(() => ({ shown: HL.content.start.jobs.map((j) => j[0]), undo: HL.undoLink(), list: HL.jobs().map((j) => j.place) }))()")
        self.assertEqual(r["shown"], JOBS)
        self.assertEqual(r["list"], [JOB_PLACES[i] for i in JOBS])
        self.assertEqual(r["undo"], {"lead": "Made a mistake?", "link": "Undo the last change", "place": "howto-undo-a-mistake"})
        r = run_node(RAW, "(() => { HL.useHeld({ howto: { 'publish-the-report': 'later' } }); return { shown: HL.content.start.jobs.map((j) => j[0]) }; })()")
        self.assertEqual(r["shown"], JOBS[:4])

    def test_the_contents_list_of_start_here_has_the_three_groups(self):
        r = run_node(RAW, "HL.tabList('start').map((g) => [g.group, g.entries.map((e) => e.place)])")
        self.assertEqual(r[:3], [["Start here", ["start-top"]], ["Start here", ["start-loop"]], ["Start here", ["start-jobs"]]], "the hero card and the loop come first (row 903)")
        r = r[2:]
        self.assertEqual(r[1], ["The five jobs", [JOB_PLACES[i] for i in JOBS]])
        self.assertEqual(r[2][0], "Also under How do I...")
        # the two jobs that open a guide leave their how-to entries here, so those stay reachable
        others = [t["id"] for t in shown_content()["howto"]["tasks"] if t["id"] not in JOBS or t["id"] in GUIDE_JOBS]
        self.assertEqual(r[2][1], ["howto-" + i for i in others], "the other shown how-to entries, in the source's order")
        self.assertEqual(r[3:], [["Start here", ["start-where"]], ["Start here", ["start-rules"]]], "where and rules are released with ask clark and Sneak peek (#721)")
        self.assertEqual(len(r), 5)

    def test_the_jobs_part_is_searchable_by_its_words(self):
        r = run_node(RAW, "(() => HL.search(HL.buildIndex(), 'ready-made').map((x) => x.id))()")
        self.assertEqual(r[0], "start-jobs")
        r = run_node(RAW, "(() => HL.search(HL.buildIndex(), 'delete sections').map((x) => x.id))()")
        self.assertIn("start-jobs", r)
        self.assertIn("howto-arrange-the-report", r)


class ContentsKeys(unittest.TestCase):
    def test_a_contents_group_is_keyed_by_its_place_in_the_list_not_its_name(self):
        """With more Start parts released, several groups share the name "Start here" (or have none, as guides do): a name as the key would clash."""
        names = [g["group"] for g in run_node(RAW, "(() => { HL.useHeld({}); return HL.tabList('start'); })()")]
        self.assertGreater(len(names) - len(set(names)), 0, "the whole source has groups with the same name")
        from _paths import SRC
        jsx = (SRC / "clark" / "page" / "src" / "help" / "Help.jsx").read_text(encoding="utf-8")
        self.assertIn("<div key={n}>", jsx)
        self.assertNotIn("g.group || n", jsx)


class TheNewEntries(unittest.TestCase):
    """The four entries written for step 3: add a work item, write this week's report, publish the report, undo a mistake."""
    def entry(self, i):
        return next(t for t in shown_content()["howto"]["tasks"] if t["id"] == i)

    def test_each_is_shown_and_has_a_group_title_where_and_three_to_six_numbered_steps(self):
        for i in ENTRIES:
            t = self.entry(i)
            self.assertTrue(t["g"] in shown_content()["howto"]["groups"], i)
            self.assertTrue(t["t"].strip() and t["w"].strip(), i)
            self.assertTrue(3 <= len(t["s"]) <= 6, f"{i}: {len(t['s'])} steps")
            self.assertTrue(all(s.strip() for s in t["s"]), i)
            self.assertNotIn(i, LATER["howto"], i)

    def test_each_has_a_next_list_that_points_at_shown_places_only(self):
        r = run_node(RAW, "(() => { const o = {}; for (const id of %s) { const t = HL.tasks().find((x) => x.id === id); o[id] = [t.next, HL.nextOf(t.next).map((n) => n.place)]; } return o; })()" % json.dumps(ENTRIES))
        for i in ENTRIES:
            given, shown = r[i]
            self.assertTrue(given, i)
            self.assertEqual(given, shown, f"{i}: every next place is a shown place")
            self.assertNotIn("howto-" + i, given, "an entry does not point at itself")

    def test_the_words_avoid_the_words_the_owner_keeps_out_and_say_nothing_of_ai(self):
        import re
        for i in ENTRIES:
            t = self.entry(i)
            text = " ".join([t["t"], t["w"]] + t["s"] + [t.get("n", "")])
            self.assertIsNone(re.search(BANNED, text), f"{i}: {re.search(BANNED, text)}")
            self.assertNotRegex(text, r"(?<!\d)\d{1,2}/\d{1,2}/\d{2,4}", i)    # dates are DD-MM-YYYY, never with slashes

    def test_the_steps_say_only_what_is_built(self):
        add, publish, write, undo = (self.entry(i) for i in ("add-a-work-item", "publish-the-report", "write-the-weekly-report", "undo-a-mistake"))
        self.assertIn("**Add item**", " ".join(add["s"]))
        self.assertIn("Also a PDF", " ".join(publish["s"]))
        self.assertIn("Also a Word document", " ".join(publish["s"]))
        self.assertIn("Publish locally", " ".join(publish["s"]))
        self.assertIn("Week ending", " ".join(write["s"]))
        self.assertIn("**Activity**", " ".join(undo["s"]))

    def test_a_search_finds_each_new_entry(self):
        probes = {"add-a-work-item": "placeholder", "write-the-weekly-report": "week ending", "publish-the-report": "preview", "undo-a-mistake": "activity"}
        for i, word in probes.items():
            r = run_node(RAW, "(() => HL.search(HL.buildIndex(), %s).map((x) => x.id))()" % json.dumps(word))
            self.assertIn("howto-" + i, r, f"{word} finds {i}")
        r = run_node(RAW, "(() => HL.search(HL.buildIndex(), 'Publish the report').map((x) => x.id))()")
        self.assertEqual(r[0], "howto-publish-the-report")

    def test_the_remaining_held_entries_stay_held(self):
        for i in ("improve-wording-with-ai", "find-work-items", "import-and-export", "update-a-milestone"):
            self.assertIn(i, LATER["howto"], i)
            self.assertNotIn(i, [t["id"] for t in shown_content()["howto"]["tasks"]])


class WhatNext(unittest.TestCase):
    def test_a_next_list_gives_shown_places_with_their_titles_in_order_once_each(self):
        first = "howto-" + next(t["id"] for t in shown_content()["howto"]["tasks"])
        r = run_node(RAW, "(() => HL.nextOf([%s, 'ref-keys', %s, 'howto-find-work-items', 'howto-nothing', 5, null]))()" % (json.dumps(first), json.dumps(first)))
        self.assertEqual([n["place"] for n in r], [first, "ref-keys"])
        self.assertTrue(all(n["title"] for n in r))

    def test_a_held_place_is_never_a_what_next_link(self):
        held = ["howto-" + i for i in LATER["howto"]] + ["ref-" + i for i in LATER["reference"]]
        self.assertTrue(held)
        r = run_node(RAW, "HL.nextOf(%s)" % json.dumps(held + ["start-first"]))
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
        r = run_node(RAW, "HL.tabList('howto').filter((g) => !g.group).map((g) => g.entries.map((e) => e.place))")
        self.assertEqual(r, [["guide-" + g["id"] for g in RAW["guides"]]], "the shipped guides are the one unnamed group")

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
        self.assertEqual(r["start"], "start-top")
        self.assertEqual(r["howto"], "howto-" + shown_content()["howto"]["tasks"][0]["id"])
        self.assertEqual(r["reference"], "ref-" + shown_content()["reference"]["sections"][0]["id"])
        self.assertIsNone(r["none"])


if __name__ == "__main__":
    unittest.main()
