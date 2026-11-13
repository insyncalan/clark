"""#642 steps 8 and 9, guides B: Bring in an Excel workbook, Send the workbook out, Publish to the client.

Run: python3 dev/run_tests.py test_help_guides_excel_publish
Quick tier: no browser. The page's pure functions run in node (skips with no node), as in test_help_guides.py.
The guides name only real controls: every bold name must be a string in the page's own source (test_help_shown's check), the words the
owner keeps out do not appear, there is no AI and no date written with slashes. Excel is not a Start here job; the Publish job opens
its guide. The pictures its steps draw are checked in test_help_guide_pictures.
"""
import json
import re
import unittest

from _help_shown import LATER, RAW, shown_content
from test_help_guides import check_guides, run_node
from test_help_navigation import BANNED
from test_help_shown import AgainstThePage

IDS = ["bring-in-an-excel-workbook", "send-the-workbook-out", "publish-to-the-client"]
STEPS = {"bring-in-an-excel-workbook": 8, "send-the-workbook-out": 7, "publish-to-the-client": 8}
GUIDES = {g["id"]: g for g in shown_content()["guides"] if g["id"] in IDS}      # the two guides of guides A are checked in test_help_guides


def words(g):
    return [g["t"], g["job"], g["result"]] + [s["d"] for s in g["steps"]]


class TheThreeGuides(unittest.TestCase):
    def test_they_are_shown_in_order_with_five_to_eight_numbered_steps(self):
        self.assertEqual(list(GUIDES), IDS)
        for i, g in GUIDES.items():
            self.assertEqual(len(g["steps"]), STEPS[i], i)
            self.assertTrue(5 <= len(g["steps"]) <= 8, i)
            self.assertTrue(all(s["d"].strip() for s in g["steps"]), i)
        r = run_node(RAW, "HL.guides().map((g) => [g.id, g.steps.map((s) => s.n)])")
        for i, nums in r:
            if i in STEPS:
                self.assertEqual(nums, list(range(1, STEPS[i] + 1)), i)

    def test_each_has_a_result_line_and_shape(self):
        self.assertEqual(check_guides(RAW), [])
        for i, g in GUIDES.items():
            self.assertTrue(g["result"].strip(), i)
            self.assertTrue(g["job"].strip(), i)

    def test_every_next_link_goes_to_a_shown_place_and_never_to_a_held_one(self):
        r = run_node(RAW, "(() => { const o = {}; for (const g of HL.guides()) o[g.id] = [g.next, HL.nextLinks(g.id), HL.nextOf(g.next).map((n) => n.place)]; return o; })()")
        held = {"howto-" + i for i in LATER["howto"]} | {"ref-" + i for i in LATER["reference"]} | {"guide-" + i for i in LATER.get("guides", {})}
        for i in IDS:
            given, links, shown = r[i]
            self.assertTrue(given, i)
            self.assertEqual(given, shown, f"{i}: every next place is shown")
            self.assertTrue(all(n["known"] and n["title"] for n in links), i)
            self.assertEqual(set(given) & held, set(), f"{i} links to a held place")
            self.assertNotIn("guide-" + i, given, "a guide does not point at itself")

    def test_a_guide_whose_link_is_held_loses_that_link_only(self):
        r = run_node(RAW, "(() => { HL.useHeld({ howto: { 'save-as-a-pdf': 'later' } }); return HL.nextOf(HL.guide('publish-to-the-client').next).map((n) => n.place); })()")
        self.assertNotIn("howto-save-as-a-pdf", r)
        self.assertIn("howto-word-in-and-out", r)

    def test_every_bold_name_is_a_string_in_the_page_source(self):
        norm = lambda t: re.sub(r"[‘’]", "'", t)
        code = norm(AgainstThePage.HELPCODE)
        names = {b for g in GUIDES.values() for t in words(g) for b in re.findall(r"\*\*(.+?)\*\*", t)}
        self.assertTrue(names)
        self.assertEqual(sorted(b for b in names if norm(b).strip(" .,:;…") not in code), [])
        # a whole-word check as well, for the longer names, so a name is not found only as a part of another word
        for b in names:
            pat = r"(?<![\w])" + re.escape(norm(b).strip(" .,:;…")) + r"(?![\w])"
            self.assertRegex(code, pat, b)

    def test_the_controls_the_steps_name_are_the_ones_the_page_has(self):
        """The control names, exactly as the page shows them (ImportWorkbook.jsx, Data.jsx, Publish.jsx, dataCard.js, ProfileMenu.jsx)."""
        text = {i: " ".join(s["d"] for s in g["steps"]) for i, g in GUIDES.items()}
        for name in ("**Settings**", "**Data**", "**Export workbook**", "**Import workbook**", "**Import from Excel**", "**Get the template**",
                     "**Choose a file**", "**Check the import**", "**Import anyway**", "**Undo this import**", "**Close**"):
            self.assertIn(name, text["bring-in-an-excel-workbook"], name)
        for name in ("**Export to Excel**", "**Export workbook**", "**Import workbook**", "**Work items**", "**Data**"):
            self.assertIn(name, text["send-the-workbook-out"], name)
        for name in ("**Preview the page in a new tab**", "**Publish…**", "**Publish the report**", "**Local**", "**To client**", "**Also a PDF**",
                     "**Also a Word document**", "**Cancel**", "**Publish locally**", "**Publish and send to the client**", "**Add a number**",
                     "**Rename it**", "**Overwrite the existing file**"):
            self.assertIn(name, text["publish-to-the-client"], name)

    def test_the_words_the_owner_keeps_out_and_ai_and_slash_dates_are_absent(self):
        for i, g in GUIDES.items():
            for t in words(g):
                self.assertIsNone(re.search(BANNED, t), f"{i}: {re.search(BANNED, t)}")
                self.assertNotRegex(t, r"(?<!\d)\d{1,2}/\d{1,2}/\d{2,4}", i)
                self.assertNotRegex(t, r"\b\d{4}-\d{2}-\d{2}\b", i)
                self.assertNotRegex(t, r"(?i)\b(delete|deleted)\b", i)

    def test_no_guide_names_a_control_that_is_not_built(self):
        """Work items has no import icon on this tree (only the export icon, in View): the Excel in guide must not say it has."""
        every = " ".join(" ".join(words(g)) for g in GUIDES.values()).lower()
        self.assertNotIn("import icon", every)
        self.assertNotIn("up-arrow", every)
        self.assertNotRegex(every, r"\bcsv\b")


class SearchFindsThem(unittest.TestCase):
    def test_a_search_finds_each_guide_by_its_title_and_by_a_word_in_a_step(self):
        probes = {"bring-in-an-excel-workbook": ("bring in an excel workbook", "get the template"),
                  "send-the-workbook-out": ("send the workbook out", "cover sheet"),
                  "publish-to-the-client": ("publish to the client", "placeholder title")}
        for gid, (title, step_word) in probes.items():
            r = run_node(RAW, "(() => { const idx = HL.buildIndex(); const f = (q) => HL.search(idx, q).map((x) => x.id); return [f(%s), f(%s)]; })()"
                         % (json.dumps(title), json.dumps(step_word)))
            self.assertIn("guide-" + gid, r[0], f"{title} finds the guide")
            self.assertIn("guide-" + gid, r[1], f"{step_word} finds the guide")

    def test_a_step_is_found_at_its_own_line(self):
        r = run_node(RAW, "(() => { const idx = HL.buildIndex(); return HL.search(idx, 'macro workbook').filter((x) => x.id === 'guide-bring-in-an-excel-workbook').map((x) => x.line); })()")
        self.assertEqual(r, [3])           # line 0 is the job, so the third step is line 3
        r = run_node(RAW, "(() => { const idx = HL.buildIndex(); return HL.search(idx, 'next publication gets').filter((x) => x.id === 'guide-publish-to-the-client').map((x) => x.line); })()")
        self.assertEqual(r, [9])           # eight steps, then the result line

    def test_a_held_guide_leaves_the_search(self):
        r = run_node(RAW, "(() => { HL.useHeld({ guides: { 'send-the-workbook-out': 'later' } }); const idx = HL.buildIndex();"
                     " return { found: HL.search(idx, 'cover sheet').map((x) => x.id), ids: HL.guides().map((g) => g.id), next: HL.nextOf(['guide-send-the-workbook-out']) }; })()")
        self.assertNotIn("guide-send-the-workbook-out", r["found"])
        self.assertNotIn("send-the-workbook-out", r["ids"])
        self.assertEqual(r["next"], [])


class TheStartJobs(unittest.TestCase):
    def test_the_publish_job_opens_the_guide_and_the_other_jobs_open_their_entries(self):
        r = run_node(RAW, "HL.jobs().map((j) => [j.id, j.place])")
        self.assertEqual(dict(r)["publish-the-report"], "guide-publish-to-the-client")
        for i, place in r:
            if i not in ("publish-the-report", "add-a-section-from-a-template", "arrange-the-report"):      # the other two jobs open their own guides (guides A)
                self.assertEqual(place, "howto-" + i)
        job = next(j for j in RAW["start"]["jobs"] if j[0] == "publish-the-report")
        self.assertEqual((job[1], job[4]), ("Publish to the client", "publish-to-the-client"))
        self.assertEqual(GUIDES["publish-to-the-client"]["t"], job[1])

    def test_the_job_falls_back_to_its_how_to_entry_while_the_guide_is_held(self):
        r = run_node(RAW, "(() => { HL.useHeld({ guides: { 'publish-to-the-client': 'later' } }); return HL.jobs().find((j) => j.id === 'publish-the-report').place; })()")
        self.assertEqual(r, "howto-publish-the-report")

    def test_the_jobs_links_are_places_that_exist(self):
        r = run_node(RAW, "(() => { const known = new Set(HL.placeIds()); return HL.linksIn().inside.filter((p) => !known.has(p) && !p.startsWith('start-')); })()")
        self.assertEqual(r, [])

    def test_excel_is_not_on_the_start_page_but_both_guides_are_under_how_do_i(self):
        start = json.dumps(shown_content()["start"]).lower()
        self.assertNotIn("guide-bring-in", start)
        self.assertNotIn("guide-send-the", start)
        for j in shown_content()["start"]["jobs"]:
            self.assertNotIn("excel", " ".join(str(x) for x in j).lower())
        r = run_node(RAW, "(() => ({ start: HL.tabList('start').map((g) => g.entries.map((e) => e.place)).flat(), howto: HL.tabList('howto').map((g) => g.entries.map((e) => e.place)).flat() }))()")
        for i in ("guide-bring-in-an-excel-workbook", "guide-send-the-workbook-out"):
            self.assertNotIn(i, r["start"], "Excel is not a Start here job")
            self.assertIn(i, r["howto"], "it is reachable under How do I...")
        self.assertIn("guide-publish-to-the-client", r["start"])


class ImportExportPointAtSettings(unittest.TestCase):
    """Import and Export are on Settings > Data, not on Work items: the how-to goes there and no legend or step says otherwise."""

    def test_how_to_goes_to_settings_data_and_the_legend_drops_work_items(self):
        c = RAW
        howto = [h for h in c["howto"]["tasks"] if h.get("id") == "import-and-export"][0]
        self.assertEqual(howto["go"], "settings#data")
        self.assertEqual(howto["page"], ["settings#data"])
        rows = {r[0]: r for r in c["reference"]["icons"]}
        for k in ("dl", "ul"):
            self.assertEqual(rows[k][3], "Settings, the profile circle", k)
        blob = json.dumps(c)
        self.assertNotIn("ready for an import", blob)


if __name__ == "__main__":
    unittest.main()
