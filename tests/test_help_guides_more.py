"""#642 step 10, guides C: Hand an item over, Save a view, See the Dashboard as it stood on a past day, Back up and restore your data.

Run: python3 dev/run_tests.py test_help_guides_more
Quick tier: no browser. The page's pure functions run in node (skips with no node), as in test_help_guides.py.
The guides name only real controls: every bold name must be a string in the page's own source (test_help_shown's check), the words the
owner keeps out do not appear, there is no AI and no date written with slashes. None is a Start here job: all four sit under How do I...
Pictures are not declared here (the shots do not exist yet); the shots each step could use are listed in the report.
"""
import json
import re
import unittest

from _help_shown import LATER, RAW, shown_content
from test_help_guides import check_guides, run_node
from test_help_navigation import BANNED
from test_help_shown import AgainstThePage

IDS = ["hand-an-item-over", "save-a-view", "see-the-dashboard-as-at-a-day", "back-up-and-restore-your-data"]
GUIDES = {g["id"]: g for g in shown_content()["guides"] if g["id"] in IDS}


def words(g):
    return [g["t"], g["job"], g["result"]] + [s["d"] for s in g["steps"]]


class TheFourGuides(unittest.TestCase):
    def test_they_are_shown_with_five_to_eight_numbered_steps(self):
        self.assertEqual(list(GUIDES), IDS)
        for i, g in GUIDES.items():
            self.assertTrue(5 <= len(g["steps"]) <= 8, i)
            self.assertTrue(all(s["d"].strip() for s in g["steps"]), i)
        r = dict(run_node(RAW, "HL.guides().map((g) => [g.id, g.steps.map((s) => s.n)])"))
        for i, g in GUIDES.items():
            self.assertEqual(r[i], list(range(1, len(g["steps"]) + 1)), i)

    def test_each_has_a_result_line_and_shape_and_no_picture_yet(self):
        self.assertEqual(check_guides(RAW), [])
        for i, g in GUIDES.items():
            self.assertTrue(g["result"].strip(), i)
            self.assertTrue(g["job"].strip(), i)
            self.assertTrue(all("pic" not in s for s in g["steps"]), f"{i}: pictures are added by the pictures step")

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

    def test_every_bold_name_is_a_string_in_the_page_source(self):
        norm = lambda t: re.sub(r"[‘’]", "'", t)
        code = norm(AgainstThePage.HELPCODE)
        names = {b for g in GUIDES.values() for t in words(g) for b in re.findall(r"\*\*(.+?)\*\*", t)}
        self.assertTrue(names)
        self.assertEqual(sorted(b for b in names if norm(b).strip(" .,:;…") not in code), [])
        for b in names:
            pat = r"(?<![\w])" + re.escape(norm(b).strip(" .,:;…")) + r"(?![\w])"
            self.assertRegex(code, pat, b)

    def test_the_controls_the_steps_name_are_the_ones_the_page_has(self):
        """The control names, exactly as the page shows them (HandOver.jsx, Bulk.jsx, FilterLine.jsx, WeekPicker.jsx, weekPicker.js, asAt.js, Safety.jsx, safety.js)."""
        text = {i: " ".join(s["d"] for s in g["steps"]) for i, g in GUIDES.items()}
        for name in ("**Work items**", "**Hand over**", "**All**", "**None**", "**Hand over to**", "**Cancel**", "**Change**", "**Undo**"):
            self.assertIn(name, text["hand-an-item-over"], name)
        for name in ("**Work items**", "**+ New view**", "**Name for the new view**", "**Save**", "**Save changes**", "**Save as a new view…**",
                     "**Rename…**", "**New name for this view**", "**Archive**", "**Bring back**"):
            self.assertIn(name, text["save-a-view"], name)
        for name in ("**Dashboard**", "**Week ending**", "**Published weeks**", "**Dashboard as at a day…**", "**Published reports**",
                     "**Dashboard as at a day**", "**Show**", "**Back to now**"):
            self.assertIn(name, text["see-the-dashboard-as-at-a-day"], name)
        for name in ("**Settings**", "**Backups**", "**Preview**", "**Restore**", "**Close**", "**Put it back**", "**Cancel**"):
            self.assertIn(name, text["back-up-and-restore-your-data"], name)

    def test_the_words_the_owner_keeps_out_and_ai_and_slash_dates_are_absent(self):
        for i, g in GUIDES.items():
            for t in words(g):
                self.assertIsNone(re.search(BANNED, t), f"{i}: {re.search(BANNED, t)}")
                self.assertNotRegex(t, r"(?<!\d)\d{1,2}/\d{1,2}/\d{2,4}", i)
                self.assertNotRegex(t, r"\b\d{4}-\d{2}-\d{2}\b", i)
                self.assertNotRegex(t, r"(?i)\b(delete|deleted)\b", i)
                self.assertNotRegex(t, r"\bAI\b", i)

    def test_no_guide_promises_what_the_page_does_not_have(self):
        """Backups has no Undo for a restore (the way back is the Before a restore copy); saved views live in the browser, not on the server."""
        text = {i: " ".join(words(g)).lower() for i, g in GUIDES.items()}
        self.assertIn("no undo button for a restore", text["back-up-and-restore-your-data"])
        self.assertIn("kept in your browser", text["save-a-view"])
        self.assertNotIn("undo this restore", text["back-up-and-restore-your-data"])
        self.assertNotIn("handing over is offered in view", text["hand-an-item-over"])
        self.assertNotIn("in edit", text["hand-an-item-over"])      # row 824: handing over has no Edit gate, so no step sends you to Edit
        self.assertNotIn("not offered in view", text["hand-an-item-over"])


class SearchFindsThem(unittest.TestCase):
    def test_a_search_finds_each_guide_by_its_title_and_by_a_word_in_a_step(self):
        probes = {"hand-an-item-over": ("hand an item over", "tick box"),
                  "save-a-view": ("save a view", "small arrow"),
                  "see-the-dashboard-as-at-a-day": ("past day", "back to now"),
                  "back-up-and-restore-your-data": ("back up and restore", "put it back")}
        for gid, (title, step_word) in probes.items():
            r = run_node(RAW, "(() => { const idx = HL.buildIndex(); const f = (q) => HL.search(idx, q).map((x) => x.id); return [f(%s), f(%s)]; })()"
                         % (json.dumps(title), json.dumps(step_word)))
            self.assertIn("guide-" + gid, r[0], f"{title} finds the guide")
            self.assertIn("guide-" + gid, r[1], f"{step_word} finds the guide")

    def test_a_step_is_found_at_its_own_line(self):
        r = run_node(RAW, "(() => { const idx = HL.buildIndex(); return HL.search(idx, 'rebuilt from the change history').filter((x) => x.id === 'guide-see-the-dashboard-as-at-a-day').map((x) => x.line); })()")
        self.assertEqual(r, [3])           # line 0 is the job, so the third step is line 3
        r = run_node(RAW, "(() => { const idx = HL.buildIndex(); return HL.search(idx, 'look at the backup again').filter((x) => x.id === 'guide-back-up-and-restore-your-data').map((x) => x.line); })()")
        self.assertEqual(r, [7])

    def test_a_held_guide_leaves_the_search(self):
        r = run_node(RAW, "(() => { HL.useHeld({ guides: { 'save-a-view': 'later' } }); const idx = HL.buildIndex();"
                     " return { found: HL.search(idx, 'small arrow').map((x) => x.id), ids: HL.guides().map((g) => g.id), next: HL.nextOf(['guide-save-a-view']) }; })()")
        self.assertNotIn("guide-save-a-view", r["found"])
        self.assertNotIn("save-a-view", r["ids"])
        self.assertEqual(r["next"], [])


class WhereTheyAre(unittest.TestCase):
    def test_none_is_a_start_here_job_and_all_four_are_under_how_do_i(self):
        start = json.dumps(shown_content()["start"]).lower()
        for i in IDS:
            self.assertNotIn("guide-" + i, start)
        r = run_node(RAW, "(() => ({ start: HL.tabList('start').map((g) => g.entries.map((e) => e.place)).flat(), howto: HL.tabList('howto').map((g) => g.entries.map((e) => e.place)).flat() }))()")
        for i in IDS:
            self.assertNotIn("guide-" + i, r["start"], "not a Start here job")
            self.assertIn("guide-" + i, r["howto"], "reachable under How do I...")

    def test_a_held_link_in_next_is_dropped_not_shown(self):
        r = run_node(RAW, "(() => { HL.useHeld({ howto: { 'find-work-items': 'later' } }); return HL.nextOf(HL.guide('save-a-view').next).map((n) => n.place); })()")
        self.assertNotIn("howto-find-work-items", r)
        self.assertIn("ref-work-items", r)


if __name__ == "__main__":
    unittest.main()
