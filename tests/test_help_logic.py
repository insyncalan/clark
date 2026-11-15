"""#82 (BRD 5.13, FR-120 to FR-124): Help's rules, src/clark/page/src/help/helpLogic.js, on the real source.

Run: python3 dev/run_tests.py test_help_logic
The page's own pure functions (bundled by the pinned esbuild with helpContent.json) run in headless Chrome, the page's real engine
(Python can not run JavaScript): the tab lists, the search across all three tabs, "open Help at a place", the keys list, the icon
legend and the links inside Help. The words themselves are tested in test_help_content.py. The browser part is required: it fails,
never skips, without Chrome (set CLARK_CHROME to its path).
"""
import json
import tempfile
import unittest
from pathlib import Path

from _help_shown import shown_content
from _paths import SRC

import esbuild  # noqa: E402  (dev/tools)
from test_server import CHROME, chrome  # noqa: E402  (the shared browser harness)

MODULE = SRC / "clark" / "page" / "src" / "help" / "helpLogic.js"
CONTENT = json.loads((MODULE.parent / "helpContent.json").read_text(encoding="utf-8"))
TASKS = CONTENT["howto"]["tasks"]
SECTIONS = CONTENT["reference"]["sections"]

# What the page shows today: the source without the entries held in helpLater.json (the default), read before anything else
# changes the held list. Compared with the Python copy in _help_shown.py, so the two cannot drift apart.
SHOWN = """(() => {
  const H = HL, idx = H.buildIndex();
  return { content: H.content, places: H.placeIds(), tabs: Object.fromEntries(H.TABS.map((t) => [t.key, H.tabList(t.key)])),
    index: idx.map((e) => e.id), links: H.linksIn(), keys: H.keysList(false).length, jobs: H.jobs().length,
    where: { held: H.placeOf("howto-find-work-items", "reference"), kept: H.placeOf("ref-keys", "start"), heldRef: H.placeOf("ref-milestone-peek", "start"), startPart: H.placeOf("start-jobs", "reference") },
    q: Object.fromEntries(["peek", "publish", "keys", "undo", "sneak", "ask clark", "movement", "diagnostics"].map((q) => [q, H.search(idx, q).map((x) => x.id)])) };
})()"""

PROBE = """(() => {
  const H = HL; H.useHeld({});          // these tests are of the logic on the whole source: nothing held
  const idx = H.buildIndex();
  const r = {};
  r.tabs = H.TABS.map((t) => [t.key, t.name]);
  r.lists = Object.fromEntries(H.TABS.map((t) => [t.key, H.tabList(t.key)]));
  r.noList = H.tabList("nothing");
  r.places = H.placeIds();
  r.where = {};
  for (const w of ["", undefined, null, 5, "start", "howto", "reference", "howto-publish-the-report", "ref-keys", "start-jobs", "ref-nothing", "howto-nothing", "nonsense"])
    r.where[String(w)] = H.placeOf(w, "reference");
  r.whereBadLast = H.placeOf("", "elsewhere");
  r.index = idx.map((e) => [e.tab, e.id, e.title]);
  r.byTitle = idx.map((e) => [e.id, H.search(idx, e.title).map((x) => x.id)]);
  r.q = {};
  for (const q of ["items", "publish", "PUBLISH", "publi", "milestone", "milestones", "swimlane", "undo", "zzzqq", "", "   ", "a", "the", "públish", "peek undo", "publish zzzqq", "ctrl", "excel"])
    r.q[q] = H.search(idx, q).map((x) => [x.tab, x.id, x.line, x.score]);
  r.view = {};
  for (const q of ["", "  ", "zzzqq", "a", "swimlane", "undo", "keys"]) r.view[q] = H.resultsView(idx, q);
  r.none = H.noResults("  <b>x</b> ");
  r.keys = H.keysList(false); r.keysMac = H.keysList(true);
  r.icons = H.iconLegend(); r.marks = H.milestoneMarks();
  r.links = H.linksIn(); r.go = [H.goLabel("work"), H.goLabel("settings#personal"), H.goLabel("nowhere")];
  r.plain = [H.plain("Press **Keep** or [[Mod+Enter]], then `x` in [Help](#ref-keys) or [Work](go:work)"), H.plain("[[Alt+Left]] [[Esc]] [[?]]", true), H.plain(null), H.plain("[[Mod+Enter]]", true)];
  r.jobs = H.jobs(); r.first = H.firstTen().length; r.loop = H.loopSteps().length;
  const one = (title, q) => H.search([{ tab: "howto", id: "t", title, tw: H.wordsOf(title), lw: [] }], q).length;
  r.stem = [one("The item", "items"), one("The entry", "entries"), one("The box", "boxes"), one("The items", "item"), one("The itch", "items"), one("An ox", "ox")];
  const long = "Open the board with the key, then drag a card to a new column and the status changes with it, and nothing else on the card moves; an Undo in the message puts it back to where it was";
  r.mark = { plain: H.markParts("Press the Keys to search", "keys"), two: H.markParts("Undo the change, then undo again", "undo change"), none: H.markParts("Nothing to find", "zzz"),
    stem: H.markParts("Three items and one entry", "items entries"), accent: H.markParts("Café menu", "cafe"), markup: H.markParts("<b>x</b> keys", "keys"),
    short: H.markParts("a b keys", "a"), empty: H.markParts("", "keys"), nul: H.markParts(null, "keys"), late: H.markParts(long, "undo"), early: H.markParts(long, "board") };
  r.dyn = H.buildIndex({ types: ["Zebra badge"] }).filter((e) => e.lines.includes("Zebra badge")).map((e) => e.id);
  return r;
})()"""


CONTENT_LONG = ("Open the board with the key, then drag a card to a new column and the status changes with it, and nothing else on the card "
                "moves; an Undo in the message puts it back to where it was")


def bundled():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "hl.js"
        done = esbuild.run(["--bundle", "--format=iife", "--global-name=HL", f"--alias:clark-help-content={MODULE.parent / 'helpContent.json'}",
                            str(MODULE), f"--outfile={out}"],
                           capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        return out.read_text(encoding="utf-8")


def page_target(cdp):
    tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
    return cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]


_CACHE = {}


def probes():
    """Both probes, run once in the one browser (the shown content first: the whole-source probe changes the held list)."""
    if not _CACHE:
        assert Path(CHROME).is_file(), f"Chrome is needed for the required browser tests: set CLARK_CHROME ({CHROME!r})"
        with chrome() as cdp:
            sid = page_target(cdp)
            code = bundled()
            for name, probe in (("shown", SHOWN), ("all", PROBE)):
                res = cdp.call("Runtime.evaluate", {"expression": code + ";\n" + probe, "returnByValue": True}, sid)
                assert "exceptionDetails" not in res, res
                _CACHE[name] = res["result"]["value"]
    return _CACHE


class Logic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = probes()["all"]

    def ids(self, q):
        return [x[1] for x in self.r["q"][q]]

    # ---- the tab lists ----
    def test_three_tabs_in_order(self):
        self.assertEqual(self.r["tabs"], [["start", "Start here"], ["howto", "How do I…"], ["reference", "Reference"]])

    def test_how_do_i_lists_every_task_under_its_group(self):
        lst = self.r["lists"]["howto"]
        self.assertEqual([g["group"] for g in lst], CONTENT["howto"]["groups"] + [""])      # the guides: one run with no heading, at the end
        self.assertEqual(sum(len(g["entries"]) for g in lst[:-1]), len(TASKS))
        self.assertEqual(sum(len(g["entries"]) for g in lst[:-1]), 37)   # item 1158 took out one task; was 38 with the People entry (#454), Run clark with Docker and the AI card task (#446)
        self.assertEqual([e["place"] for e in lst[-1]["entries"]], ["guide-add-a-section-from-a-template", "guide-arrange-the-report", "guide-bring-in-an-excel-workbook", "guide-send-the-workbook-out", "guide-publish-to-the-client", "guide-hand-an-item-over", "guide-save-a-view", "guide-see-the-dashboard-as-at-a-day", "guide-back-up-and-restore-your-data", "guide-the-brand-kit-guide"])
        first = lst[0]["entries"][0]
        self.assertEqual(first, {"id": TASKS[0]["id"], "title": TASKS[0]["t"], "place": "howto-" + TASKS[0]["id"]})

    def test_reference_lists_every_section_under_its_group(self):
        lst = self.r["lists"]["reference"]
        self.assertEqual([g["group"] for g in lst], CONTENT["reference"]["groups"])
        self.assertEqual(sum(len(g["entries"]) for g in lst), 35)   # item 1158 took out Needs from you; was 36 with the People entry (#454) and the Feedback entry (#1069)
        self.assertTrue(all(e["place"].startswith("ref-") for g in lst for e in g["entries"]))

    def test_start_here_lists_its_seven_parts_and_an_unknown_tab_lists_nothing(self):
        """The seven parts in order; the jobs part is followed by the group of the five jobs (each opens its how-to entry) and the group of the other how-to entries."""
        groups = self.r["lists"]["start"]
        jobs = ["howto-add-a-work-item", "howto-write-the-weekly-report", "guide-add-a-section-from-a-template", "guide-arrange-the-report", "guide-publish-to-the-client"]      # three jobs open a guide (#642 guides A and B)
        self.assertEqual([g["group"] for g in groups], ["Start here", "The five jobs", "Also under How do I...", "Start here"], "parts in a row that share a heading are one group, headed once")
        self.assertEqual([e["place"] for e in groups[0]["entries"]], ["start-" + p for p in ("top", "loop", "first", "jobs")])
        self.assertEqual([e["place"] for e in groups[3]["entries"]], ["start-" + p for p in ("where", "rules", "foot")])
        self.assertEqual([e["place"] for e in groups[1]["entries"]], jobs)
        self.assertEqual(sorted(e["place"] for e in groups[2]["entries"]), sorted("howto-" + x["id"] for x in TASKS if "howto-" + x["id"] not in jobs))      # the how-to entries of the guide jobs are here
        self.assertEqual(self.r["noList"], [])

    def test_the_jobs_and_steps_of_start_here(self):
        self.assertEqual(len(self.r["jobs"]), 5)
        self.assertTrue(all(j["place"] == ("guide-" if j["id"] in ("add-a-section-from-a-template", "arrange-the-report", "publish-the-report") else "howto-") + ("publish-to-the-client" if j["id"] == "publish-the-report" else j["id"]) for j in self.r["jobs"]))
        self.assertEqual((self.r["first"], self.r["loop"]), (5, 5))

    # ---- open Help at a place ----
    def test_open_at_a_place(self):
        w = self.r["where"]
        self.assertEqual(w["howto-publish-the-report"], {"tab": "howto", "target": "howto-publish-the-report", "known": True})
        self.assertEqual(w["ref-keys"], {"tab": "reference", "target": "ref-keys", "known": True})
        self.assertEqual(w["start-jobs"], {"tab": "start", "target": "start-jobs", "known": True})
        for tab in ("start", "howto", "reference"):
            self.assertEqual(w[tab], {"tab": tab, "target": None, "known": True})

    def test_open_with_nothing_opens_the_tab_used_last(self):
        for k in ("", "undefined", "null"):
            self.assertEqual(self.r["where"][k], {"tab": "reference", "target": None, "known": True})
        self.assertEqual(self.r["whereBadLast"], {"tab": "start", "target": None, "known": True})

    def test_a_place_that_does_not_exist_opens_its_tab_or_the_last_one_and_says_so(self):
        w = self.r["where"]
        self.assertEqual(w["ref-nothing"], {"tab": "reference", "target": None, "known": False})
        self.assertEqual(w["howto-nothing"], {"tab": "howto", "target": None, "known": False})
        self.assertEqual(w["nonsense"], {"tab": "reference", "target": None, "known": False})
        self.assertEqual(w["5"], {"tab": "reference", "target": None, "known": True})   # not text: as nothing

    def test_every_place_is_unique_and_the_count_is_right(self):
        p = self.r["places"]
        self.assertEqual(len(p), len(set(p)))
        self.assertEqual(len(p), 7 + 37 + 35 + 10)   # with the People entries (#454), the AI card task (#446) and the ten guides (#642 guides A, B and C)

    # ---- search ----
    def test_search_finds_every_entry_by_its_title(self):
        for place, found in self.r["byTitle"]:
            with self.subTest(place):
                self.assertIn(place, found)

    def test_a_title_match_ranks_above_a_text_match_and_a_task_above_a_section_on_a_tie(self):
        res = self.r["q"]["publish"]
        self.assertEqual(res[0][1], "howto-publish-the-report")
        scores = [x[3] for x in res]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertGreater(len(res), 5)

    def test_titles_that_match_come_before_text_that_matches(self):
        titles = {i: t for _, i, t in self.r["index"]}
        res = self.r["q"]["undo"]
        flags = ["undo" in titles[x[1]].lower() for x in res]
        self.assertTrue(flags[0] and any(flags))
        self.assertEqual(flags, sorted(flags, reverse=True))     # every title match before every text-only match

    def test_a_plural_finds_the_singular(self):
        self.assertIn("howto-add-a-work-item", self.ids("items"))

    def test_a_plural_in_all_three_forms_finds_the_singular_and_not_the_other_way_round(self):
        self.assertEqual(self.r["stem"], [1, 1, 1, 1, 0, 1])    # items->item, entries->entry, boxes->box; "item" finds "items"; "items" not "itch"

    def test_matching_ignores_capitals_and_accents_and_plurals_start_from_the_word(self):
        self.assertEqual(self.r["q"]["publish"], self.r["q"]["PUBLISH"])
        self.assertEqual(set(self.ids("milestone")), set(self.ids("milestones")))
        self.assertIn("ref-milestone-states", self.ids("milestone"))
        self.assertIn("howto-publish-the-report", self.ids("publi"))    # part of a word finds the word
        self.assertEqual(self.ids("públish"), self.ids("publish"))

    def test_every_word_must_be_found_and_short_words_are_ignored(self):
        both = set(self.ids("peek undo"))
        self.assertTrue(both)
        self.assertLess(len(both), len(self.ids("undo")))
        self.assertEqual(self.ids("publish zzzqq"), [])
        self.assertEqual(self.ids("a"), [])

    def test_search_reaches_all_three_tabs(self):
        tabs = {x[0] for x in self.r["q"]["undo"]}
        self.assertEqual(tabs, {"start", "howto", "reference"})
        keys = [x for x in self.r["q"]["ctrl"] if x[1] == "ref-keys"]
        self.assertTrue(keys)

    def test_a_result_says_which_line_matched(self):
        for _, place, line, _ in self.r["q"]["swimlane"] + self.r["q"]["excel"]:
            self.assertGreaterEqual(line, -1, place)

    def test_nothing_asked_nothing_found(self):
        for q in ("", "   ", "a"):
            self.assertEqual(self.r["q"].get(q, []), [])
        self.assertEqual(self.r["view"][""]["kind"], "none-asked")
        self.assertEqual(self.r["view"]["  "]["kind"], "none-asked")

    def test_no_results_message_is_plain_and_points_to_the_tabs(self):
        v = self.r["view"]["zzzqq"]
        self.assertEqual((v["kind"], v["count"], v["groups"]), ("empty", 0, []))
        self.assertEqual(v["title"], "Nothing in Help for “zzzqq”")
        self.assertEqual(v["hint"], "Try another word, or look through the tabs.")
        self.assertEqual(self.r["view"]["a"]["hint"], "Type at least two letters.")       # a one-letter search says what to do
        self.assertEqual(self.r["none"]["title"], "Nothing in Help for “<b>x</b>”")      # text, trimmed; the panel escapes it

    def test_results_are_grouped_how_do_i_first_then_reference_then_start_here_with_a_count(self):
        v = self.r["view"]["undo"]
        self.assertEqual([g["tab"] for g in v["groups"]], ["howto", "reference", "start"])
        self.assertEqual([g["name"] for g in v["groups"]], ["How do I…", "Reference", "Start here"])
        self.assertEqual(v["count"], sum(len(g["results"]) for g in v["groups"]))
        self.assertEqual(v["line"], f"{v['count']} results for “undo”")
        one = self.r["view"]["keys"]
        self.assertIn(one["line"], (f"{one['count']} results for “keys”", "1 result for “keys”"))

    def test_a_part_the_page_fills_in_is_searched_when_the_page_gives_its_lines(self):
        self.assertEqual(self.r["dyn"], ["ref-icons"])

    # ---- the keys and the icons ----
    def test_a_result_marks_the_words_that_matched(self):
        """C-H9: the prototype marks the matched word in a title and a line (help.js `mark`), as text parts, never markup."""
        m = self.r["mark"]
        join = lambda parts: "".join(p["t"] for p in parts)
        hits = lambda parts: [p["t"] for p in parts if p["hit"]]
        self.assertEqual(m["plain"], [{"t": "Press the ", "hit": False}, {"t": "Keys", "hit": True}, {"t": " to search", "hit": False}])
        self.assertEqual(hits(m["two"]), ["Undo", "change", "undo"], "every word of the search is marked, in the line's own capitals")
        self.assertEqual(m["none"], [{"t": "Nothing to find", "hit": False}])
        self.assertEqual(hits(m["stem"]), ["items", "entry"], "a plural finds the singular and the other way round")
        self.assertEqual(hits(m["accent"]), ["Café"], "accents are ignored in matching, kept in the words")
        self.assertEqual(join(m["markup"]), "<b>x</b> keys", "the text is kept as it is; the page draws it as text")
        self.assertEqual(hits(m["short"]), [], "a one-letter word is not searched for")
        self.assertEqual((m["empty"], m["nul"]), ([], []))
        self.assertEqual(join(m["early"]), CONTENT_LONG, "a match near the start keeps the whole line")
        self.assertEqual(m["late"][0], {"t": "…", "hit": False}, "a match late in a long line starts a little before it, with an ellipsis")
        self.assertTrue(hits(m["late"]) == ["Undo"] and join(m["late"][1:]) in CONTENT_LONG)

    def test_keys_list(self):
        keys, mac = self.r["keys"], self.r["keysMac"]
        self.assertEqual(len(keys), 35)      # the Up and Alt+/ rows are gone (the page binds neither); Mod+J is back (askPanelState.js binds it)
        self.assertEqual(len(mac), 35)
        self.assertEqual([k for k in keys if k["keys"] in ("Up",) and ("ask clark" in k["does"] or "Sneak" in k["does"])], [])
        self.assertEqual([k["keys"] for k in keys if "ask clark" in k["does"] and "J" in k["keys"]], ["Ctrl+J"])
        self.assertEqual([k["keys"] for k in mac if "ask clark" in k["does"] and "J" in k["keys"]], ["⌘+J"])
        self.assertTrue(all("[[" not in k["keys"] + k["does"] and "**" not in k["does"] for k in keys))
        self.assertTrue(any(k["keys"] == "?" for k in keys))

    def test_icon_legend(self):
        icons = self.r["icons"]
        self.assertEqual(len(icons), 29)      # row 1077: the Draft entry is out with the Draft chip; # #721: the top-bar "ask clark" chat row is out until the ask button is on the page
        self.assertEqual(len({i["icon"] for i in icons}), 29)
        self.assertTrue(all(i["title"] and i["does"] and i["where"] for i in icons))
        self.assertIn("eyeoff", [i["icon"] for i in icons])

    def test_milestone_marks(self):
        states = [m["state"] for m in self.r["marks"]]
        self.assertEqual(states[:5], ["Achieved", "On track", "At risk", "Slipped", "Overdue"])
        self.assertEqual(states[-2:], ["Expected", "Today"])
        self.assertTrue(all(m["means"] for m in self.r["marks"]))

    # ---- links inside Help ----
    def test_every_link_inside_help_finds_its_place_and_every_screen_exists(self):
        links = self.r["links"]
        self.assertGreater(len(links["inside"]), 17)   # measured 18 on this tree (24 with the prototype's twelve jobs): the measured count less one
        self.assertEqual(sorted(set(links["inside"]) - set(self.r["places"])), [])
        screens = {"dashboard", "dashboard+edit", "work", "milestones", "settings", "publish", "preview", "ask"}
        self.assertEqual(sorted(s for s in links["screens"] if s.split("#")[0] not in screens), [])
        self.assertGreater(len(links["screens"]), 3)

    def test_go_labels(self):
        self.assertEqual(self.r["go"], ["Open Work items", "Open Settings", "Open it"])

    def test_plain_takes_the_markup_off(self):
        self.assertEqual(self.r["plain"][0], "Press Keep or Ctrl+Enter, then x in Help or Work")
        self.assertEqual(self.r["plain"][1], "Alt+← Esc ?")
        self.assertEqual(self.r["plain"][2], "")
        self.assertEqual(self.r["plain"][3], "⌘+Enter")


class Shown(unittest.TestCase):
    """What the page shows: the held entries are out of every list, the search and the places."""
    @classmethod
    def setUpClass(cls):
        cls.shown = probes()["shown"]

    def test_the_browsers_copy_of_the_shown_content_is_the_python_copy(self):
        self.assertEqual(self.shown["content"], shown_content())

    def test_a_held_entry_is_in_no_list_no_place_and_no_search(self):
        s = self.shown
        SEC = ["start-top", "start-loop", "start-jobs", "start-where", "start-rules", "howto-write-the-weekly-report", "howto-set-the-health", "howto-check-the-report", "howto-publish-the-report", "howto-word-in-and-out", "howto-excel-file-layout", "howto-find-a-past-publication", "howto-save-as-a-pdf", "howto-add-a-work-item", "howto-use-the-board", "howto-change-an-item-in-the-peek", "howto-change-an-item-in-words", "howto-arrange-the-report", "howto-add-a-section-from-a-template", "howto-find-a-use-case", "howto-change-the-layout-and-look", "howto-handle-a-slipped-milestone", "howto-set-up-a-project", "howto-connect-claude-or-chatgpt", "howto-set-your-profile", "howto-add-people-details", "howto-undo-a-mistake", "howto-update-clark", "howto-start-check-and-restore-in-terminal", "howto-run-clark-with-docker", "ref-profile-circle", "ref-sections", "ref-section-templates", "ref-freshness", "ref-archive-restore", "ref-at-a-glance", "ref-layouts", "ref-work-items", "ref-milestones-page", "ref-ask-clark", "ref-peek", "ref-status-words", "ref-sneak-peek", "ref-milestone-states", "ref-publishing", "ref-published-reports", "ref-settings", "ref-people", "ref-updating-clark", "ref-diagnostics", "ref-feedback", "ref-dates-and-ids", "ref-using-help", "ref-keys"]
        GUIDES = ["guide-add-a-section-from-a-template", "guide-arrange-the-report", "guide-bring-in-an-excel-workbook", "guide-send-the-workbook-out", "guide-publish-to-the-client", "guide-hand-an-item-over", "guide-save-a-view", "guide-see-the-dashboard-as-at-a-day", "guide-back-up-and-restore-your-data", "guide-the-brand-kit-guide"]      # #642 guides A, B and C: after the how-to and reference places
        self.assertEqual(s["places"], SEC + GUIDES)
        jobs = [e["place"] for g in s["tabs"]["start"] if g["group"] == "The five jobs" for e in g["entries"]]
        self.assertEqual(jobs, ["howto-add-a-work-item", "howto-write-the-weekly-report", "guide-add-a-section-from-a-template", "guide-arrange-the-report", "guide-publish-to-the-client"], "Start here lists the five jobs, all shown")
        self.assertTrue(all(p in SEC + GUIDES for p in jobs), "and each is a shown place")
        self.assertEqual([e["place"] for g in s["tabs"]["howto"] for e in g["entries"]], SEC[5:30] + GUIDES)
        self.assertEqual([e["place"] for g in s["tabs"]["reference"] for e in g["entries"]],
                         ["ref-profile-circle", "ref-sections", "ref-section-templates", "ref-at-a-glance", "ref-layouts", "ref-work-items", "ref-milestones-page", "ref-ask-clark", "ref-freshness", "ref-archive-restore", "ref-peek", "ref-status-words", "ref-sneak-peek", "ref-milestone-states", "ref-publishing", "ref-published-reports", "ref-settings", "ref-people", "ref-updating-clark", "ref-diagnostics", "ref-feedback", "ref-dates-and-ids", "ref-using-help", "ref-keys"])      # by group: Screens, Working with items, Milestones, Publishing, Settings and data, Keys and icons
        self.assertEqual(s["index"], SEC + GUIDES)
        self.assertEqual((s["jobs"], s["links"]["inside"], s["links"]["screens"]), (5, ["howto-set-the-health", "howto-change-an-item-in-words", "ref-sneak-peek", "ref-section-templates", "ref-updating-clark", "howto-add-a-section-from-a-template", "ref-status-words", "howto-use-the-board", "howto-handle-a-slipped-milestone", "ref-diagnostics", "ref-people", "ref-feedback", "howto-add-a-work-item", "howto-write-the-weekly-report", "guide-add-a-section-from-a-template", "guide-arrange-the-report", "guide-publish-to-the-client", "howto-undo-a-mistake", "ref-keys"], ["settings#update", "work", "dashboard+edit", "publish", "ask", "settings#data", "settings", "milestones", "settings#profile", "settings#people", "dashboard"]))
        self.assertEqual(s["q"]["sneak"], ["howto-change-an-item-in-words", "ref-sneak-peek", "howto-change-an-item-in-the-peek", "start-where", "ref-keys"], "the Sneak peek entries, the keyline and the keys are found by a search for it")
        self.assertEqual(s["q"]["peek"], ["howto-change-an-item-in-the-peek", "howto-change-an-item-in-words", "ref-peek", "ref-sneak-peek", "howto-write-the-weekly-report", "howto-check-the-report", "howto-add-a-work-item", "howto-undo-a-mistake", "start-loop", "start-where", "ref-freshness", "ref-keys"])
        self.assertEqual(s["q"]["movement"][:2], ["ref-milestones-page", "howto-handle-a-slipped-milestone"], "a search for movement finds the Movement entries")
        self.assertEqual(s["q"]["diagnostics"][0], "ref-diagnostics", "a search for diagnostics finds the Diagnostics entry")
        self.assertEqual(s["q"]["publish"], ["howto-publish-the-report", "guide-publish-to-the-client", "start-top", "ref-publishing", "ref-published-reports", "howto-word-in-and-out", "howto-find-a-past-publication", "howto-save-as-a-pdf", "howto-add-a-work-item", "howto-arrange-the-report", "howto-change-the-layout-and-look", "howto-handle-a-slipped-milestone", "howto-set-up-a-project", "howto-update-clark", "guide-arrange-the-report", "guide-send-the-workbook-out", "guide-see-the-dashboard-as-at-a-day", "start-loop", "start-jobs", "start-where", "start-rules", "ref-profile-circle", "ref-archive-restore", "ref-layouts", "ref-work-items", "ref-milestones-page", "ref-peek", "ref-status-words", "ref-milestone-states", "ref-settings", "ref-updating-clark"],      # ref-peek: its Source line says a published file draws the name; howto-change-the-layout-and-look: its Spacing step says spacing is used on the published report
                         "the Published reports entries, then the entries that say what is or is not on the published page; only entries about Publish that are shown")
        self.assertEqual(s["q"]["keys"], ["ref-keys", "howto-use-the-board", "howto-find-a-use-case", "howto-change-the-layout-and-look", "howto-connect-claude-or-chatgpt", "guide-add-a-section-from-a-template", "guide-hand-an-item-over", "ref-section-templates", "ref-ask-clark", "ref-settings", "ref-using-help"])

    def test_opening_help_at_a_held_place_is_an_unknown_place_and_a_shown_one_still_opens(self):
        w = self.shown["where"]
        self.assertEqual(w["held"], {"tab": "howto", "target": None, "known": False})
        self.assertEqual(w["heldRef"], {"tab": "reference", "target": None, "known": False})
        self.assertEqual(w["startPart"], {"tab": "start", "target": "start-jobs", "known": True}, "the jobs part is shown now")
        self.assertEqual(w["kept"], {"tab": "reference", "target": "ref-keys", "known": True})

    def test_the_keys_that_are_shown_are_the_python_copy(self):
        self.assertEqual(self.shown["keys"], len(shown_content()["reference"]["keys"]))


if __name__ == "__main__":
    unittest.main()
