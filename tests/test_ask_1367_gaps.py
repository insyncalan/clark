"""Row 1367 follow-up: the workstreams reader, the link fields by name, a Draft that quotes a hidden item, and the note in the panel.

Run: python3 dev/run_tests.py test_ask_1367_gaps
Fictional data only (the publish plant). Classic only; the Cards pins are not touched.
"""
import json
import re
import unittest

from _paths import SRC  # noqa: F401

import _testpage as testpage
from _real_server import real_server
import test_ask_1367 as base
from clark import ask, ask_data, page, publish, theme as themes, to_client
from test_ask_panel import Stub
from test_report_editor import Base
from test_server import chrome

read, text_of, add_row = base.read, base.text_of, base.add_row

HIDDEN = ("ZQ-HIDDEN-ACTION", "ZQ-FLAG-OFF-MILESTONE")


class Workstreams(unittest.TestCase):
    def test_workstreams_are_a_kind_with_words_a_label_and_a_title_field(self):
        self.assertIn("workstreams", ask_data.KIND_ORDER)
        self.assertEqual(ask_data.KIND_WORDS["workstreams"], "workstreams")
        self.assertEqual(ask_data.LABELS["workstreams"], "report: workstreams")
        self.assertEqual(ask_data.TITLE["workstreams"], "name")
        self.assertEqual(ask_data.SHOWN["workstreams"], ("status", "created"))

    def test_a_workstream_is_read_with_its_id_name_and_status(self):
        line = [x for x in text_of(read("workstreams?")[0]).split("\n") if "PUB-W-001" in x][0]
        self.assertEqual(line, "PUB-W-001 Delivery | status: Active | created: 01-09-2026")

    def test_a_workstream_is_read_whatever_the_report_shows(self):
        def hide_all(given):
            given["sections"] = [{**s, "hidden": 1} for s in publish.DEFAULT_SECTIONS]
        self.assertIn("PUB-W-001", text_of(read("workstreams?", edit=hide_all)[0]))

    def test_an_archived_workstream_and_another_projects_are_not_read(self):
        def more(given):
            add_row(given, "workstreams", id="PUB-W-901", name="ZQ-ARCHIVED-WS", archived=1)
            add_row(given, "workstreams", id="OTH-W-900", project="OTH", name="ZQ-OTHER-WS")
        text = text_of(read(edit=more)[0])
        self.assertNotIn("ZQ-ARCHIVED-WS", text)
        self.assertNotIn("ZQ-OTHER-WS", text)

    def test_a_closed_workstream_is_read_with_its_status(self):
        def closed(given):
            add_row(given, "workstreams", id="PUB-W-902", name="ZQ-CLOSED-WS", status="Closed")
        self.assertIn("PUB-W-902 ZQ-CLOSED-WS | status: Closed", text_of(read(edit=closed)[0]))

    def test_workstreams_are_counted_and_cut_like_the_other_kinds(self):
        got, _ = read()
        self.assertIn(("workstreams", 2, 2), got.counts)
        self.assertEqual(ask_data.left_out_lines([("workstreams", 1, 3)]),
                         ["Sent 1 of 3 workstreams (the closest to your question); 2 were left out."])
        self.assertEqual(ask_data.partial_lines([("workstreams", 1, 3)]), ["workstreams: 1 of 3 rows sent"])

    def test_the_lead_and_the_other_working_columns_are_never_read(self):
        text = text_of(read()[0])
        for marker in ("ZQ-WS-LEAD", "ZQ-WS-KEYWORDS", "ZQ-WS-ALIASES", "ZQ-SOURCE-PATH"):
            self.assertNotIn(marker, text)

    def test_a_workstream_is_a_fact_for_the_claims_check_with_no_state(self):
        got, _ = read()
        self.assertEqual(got.facts["PUB-W-001"], {"title": "Delivery", "owner": "", "state": []})

    def test_the_published_file_carries_the_same_workstreams_as_before(self):
        published = publish.select(read()[1])["data"]["workstreams"]
        self.assertEqual([w["id"] for w in published], ["PUB-W-001"])


class LinkFieldsByName(unittest.TestCase):
    def line(self, kind, **fields):
        def put(given):
            add_row(given, kind, id="PUB-Z-901", **fields)
        return [x for x in text_of(read(edit=put)[0]).split("\n") if "PUB-Z-901" in x][0]

    def test_the_link_fields_are_pinned_by_name(self):
        self.assertEqual([k for k, f in ask_data.SHOWN.items() if "milestone" in f], ["actions", "raid"])
        self.assertEqual([k for k, f in ask_data.SHOWN.items() if "use_case" in f], ["actions", "raid", "decisions"])

    def test_an_action_line_names_its_milestone_and_use_case(self):
        line = self.line("actions", description="ZQ-LINKED", milestone="PUB-M-001", use_case="PUB-U-001")
        self.assertIn("milestone: PUB-M-001", line)
        self.assertIn("use case: PUB-U-001", line)

    def test_a_risk_line_names_its_milestone_and_use_case(self):
        line = self.line("raid", description="ZQ-LINKED", milestone="PUB-M-001", use_case="PUB-U-001")
        self.assertIn("milestone: PUB-M-001", line)
        self.assertIn("use case: PUB-U-001", line)

    def test_a_decision_line_names_its_use_case_and_has_no_milestone_field(self):
        line = self.line("decisions", decision="ZQ-LINKED", use_case="PUB-U-001", milestone="PUB-M-001")
        self.assertIn("use case: PUB-U-001", line)
        self.assertNotIn("milestone:", line)

    def test_no_link_means_no_field(self):
        line = self.line("actions", description="ZQ-LINKED")
        self.assertNotIn("milestone:", line)
        self.assertNotIn("use case:", line)


class TeamOnlyAndCurrentState(unittest.TestCase):
    def test_no_team_only_column_is_a_shown_field_of_any_kind(self):
        from clark import store
        for kind, fields in ask_data.SHOWN.items():
            self.assertEqual(set(fields) & store.NEVER_PUBLISH, set(), kind)

    def test_team_only_fields_are_not_read(self):
        def put(given):
            for kind, title in (("actions", "description"), ("raid", "description"), ("decisions", "decision"), ("milestones", "name")):
                add_row(given, kind, id="PUB-T-9" + kind[:2], **{title: "ZQ-TEAM-ROW", "internal_note": "ZQ-TEAM-NOTE",
                        "reasoning": "ZQ-TEAM-REASON", "options": "ZQ-TEAM-OPTIONS", "response_action": "ZQ-TEAM-RESPONSE",
                        "movement": "ZQ-TEAM-MOVE"})
        text = text_of(read(edit=put)[0])
        self.assertIn("ZQ-TEAM-ROW", text)
        for marker in ("NOTE", "REASON", "OPTIONS", "RESPONSE", "MOVE"):
            self.assertNotIn("ZQ-TEAM-" + marker, text)

    def test_a_hidden_current_state_section_does_not_change_what_is_read(self):
        def hide(given):
            given["sections"] = [{**s, "hidden": 1} if s.get("type") == "current" else s for s in given["sections"]]
        self.assertIn("ZQ-KEEP-CURRENT", text_of(read(edit=hide)[0]))
        self.assertIn("ZQ-KEEP-CURRENT", text_of(read()[0]))

    def test_the_current_state_text_is_read_without_markup(self):
        def put(given):
            given["data"]["project"]["current_state"] = '<b>ZQ-BOLD</b><script>ZQ-SCRIPT()</script> <a href="http://x.invalid">ZQ-LINK</a>'
        text = text_of(read(edit=put)[0])
        self.assertIn("ZQ-BOLD", text)
        self.assertIn("ZQ-LINK", text)
        for bad in ("<b>", "<script", "<a ", "href", "ZQ-SCRIPT"):
            self.assertNotIn(bad, text)


class DraftQuotingAHiddenItem(unittest.TestCase):
    def test_a_file_that_quotes_a_hidden_item_is_stopped_by_the_client_check(self):
        given = read()[1]
        given["sections"] = list(given["sections"]) + [
            {"project": "PUB", "id": "s-draft", "type": "text", "title": "Draft", "body": "<p>Quoting ZQ-HIDDEN-ACTION here.</p>",
             "beside": 0, "hidden": 0, "sort_order": 99}]
        file = json.dumps(publish.select(given)).encode("utf-8")
        self.assertEqual(to_client.check_copy(file, markers=HIDDEN), ["text that was meant to be left out"])

    def test_the_same_file_without_the_quote_passes_the_check(self):
        file = json.dumps(publish.select(read()[1])).encode("utf-8")
        self.assertEqual(to_client.check_copy(file, markers=HIDDEN), [])

    def test_reading_a_hidden_item_does_not_put_it_in_a_selection_for_the_client(self):
        got, given = read()
        self.assertIn("ZQ-HIDDEN-ACTION", text_of(got))
        self.assertNotIn("ZQ-HIDDEN-ACTION", json.dumps(publish.select(given)))


class Classic(Base):
    THEME = "prototype-2.0"
    LINE = ask_data.left_out_lines([("milestones", 20, 47)])[0]

    def setUp(self):
        super().setUp()
        self.stub = Stub()
        self.s.close()
        css = themes.css(self.THEME)
        self.s = real_server(self.store.path, self.store.data_for, page_html=lambda: page.layer_theme(testpage.html(), css), seam=self.seam)
        self.addCleanup(self.s.close)
        self.s.httpd.ask = self.stub

    def at(self, p, width):
        p.cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)


class DraftSheet(Classic):
    DRAFT = {"html": "<p>Quoting ZQ-HIDDEN-ACTION for the summary.</p>", "title": "Summary", "sec": ""}
    SECTIONS = "document.querySelector('.secs').innerText"

    def test_a_draft_quoting_a_hidden_item_is_not_in_the_report_until_it_is_added_by_choice(self):
        stub = self.stub
        original = stub.ask

        def ask(body):
            status, out = original(body)
            if out.get("ok"):
                out["draft"] = dict(self.DRAFT)
            return status, out
        stub.ask = ask
        with chrome() as cdp:
            p = self.visit(cdp)
            p.js("document.querySelector('[data-mode=edit]').click()")
            p.key("/", code="Slash", vk=191)
            p.until("!document.querySelector('#ask-send').disabled", "ready")
            p.js("document.querySelector('#ask-box').focus()")
            p.type("Summarise")
            p.js("document.querySelector('#ask-send').click()")
            p.until("!!document.querySelector('#ask-draft')", "the draft opened")
            self.assertNotIn("ZQ-HIDDEN-ACTION", p.js(self.SECTIONS), "the draft is not in the report")
            p.js("document.querySelector('#ask-draft-add').click()")
            self.assertNotIn("ZQ-HIDDEN-ACTION", p.js(self.SECTIONS), "opening the menu is not approval")
            p.js("document.querySelector('#ask-draft-menu [data-kind=add]').click()")
            p.until(f"{self.SECTIONS}.includes('ZQ-HIDDEN-ACTION')", "added only after the choice")


class NoteInThePanel(Classic):
    def test_the_note_reads_plainly_at_1400_and_900_in_light_and_dark(self):
        self.stub.notes = [self.LINE]
        probe = """(function(){
          const rgb = (c) => c.match(/[\\d.]+/g).slice(0, 3).map(Number), lum = (c) => { const [r, g, b] = rgb(c).map((v) => { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); }); return .2126 * r + .7152 * g + .0722 * b; };
          const n = document.querySelector('[data-ask-notes]'); let bg = n, bgc = 'rgba(0, 0, 0, 0)';
          while (bg && /rgba\\(0, 0, 0, 0\\)|transparent/.test(bgc)) { bgc = getComputedStyle(bg).backgroundColor; bg = bg.parentElement; }
          const l1 = lum(getComputedStyle(n).color), l2 = lum(bgc), panel = document.querySelector('#ask-panel');
          return {text: n.textContent, ratio: (Math.max(l1, l2) + .05) / (Math.min(l1, l2) + .05), fits: n.scrollWidth <= n.clientWidth && panel.scrollWidth <= panel.clientWidth,
                  inside: n.getBoundingClientRect().right <= panel.getBoundingClientRect().right};
        })()"""
        with chrome() as cdp:
            p = self.visit(cdp)
            p.key("/", code="Slash", vk=191)
            p.until("!document.querySelector('#ask-send').disabled", "ready")
            p.js("document.querySelector('#ask-box').focus()")
            p.type("Which milestones are late?")
            p.js("document.querySelector('#ask-send').click()")
            p.until("!!document.querySelector('[data-ask-notes]')", "the note")
            for width in (1400, 900):
                self.at(p, width)
                for scheme in ("light", "dark"):
                    p.js(f"document.documentElement.dataset.theme = '{scheme}'")
                    r = p.js(probe)
                    where = f"{width} {scheme}"
                    self.assertEqual(r["text"], self.LINE, where)
                    self.assertGreaterEqual(r["ratio"], 4.5, f"{where} {r}")
                    self.assertTrue(r["fits"] and r["inside"], where)

    def test_the_note_is_in_plain_british_english(self):
        american = re.compile(r"\b(color|organiz|analyz|center|favor|gray|program\b)", re.I)
        for line in ask_data.left_out_lines([(k, 1, 3) for k in ask_data.KIND_ORDER]):
            self.assertIsNone(american.search(line), line)
            self.assertRegex(line, r"^Sent \d+ of \d+ [a-z ]+ \(the closest to your question\); \d+ (was|were) left out\.$")


class RealStoreAndCount(unittest.TestCase):
    """Row 1367: what a real store gives (not planted inputs), and the request never refused for the project's own passages."""

    def test_a_workstreams_created_day_is_read_from_a_real_store(self):
        from _demo import DemoStore
        demo = DemoStore()
        try:
            demo.store.con.execute("UPDATE workstreams SET created = '2026-09-01' WHERE project = 'ABC'")
            got = ask_data.project_data(demo.store, "ABC", "workstreams?")
            self.assertIn("ABC-W-001 Build | status: Active | created: 01-09-2026", "\n".join(p.text for p in got.passages))
            self.assertNotIn("created", publish.PUBLISH_FIELDS["workstreams"], "the published file is unchanged")
            for w in publish.select(publish.read_inputs(demo.store, "ABC"))["data"]["workstreams"]:
                self.assertNotIn("created", w)
        finally:
            demo.close()

    def _many(self, n):
        def plant(given):
            given["data"]["actions"] = [{"id": f"PUB-A-{i:03d}", "project": "PUB", "archived": 0, "description": f"Action {i} " + "lorem ipsum " * 90,
                                         "status": "Open"} for i in range(n)]
        return read(edit=plant)[0]

    def test_a_project_of_100_passages_builds_a_request_and_counts_what_was_left_out(self):
        got = self._many(400)
        self.assertEqual(len(got.passages), ask.MAX_PASSAGES)
        self.assertGreater(got.left_out, 0)
        self.assertTrue(ask.build_request("what?", got.passages).text)

    def test_exactly_max_passages_are_all_kept_and_one_more_is_left_out(self):
        few = [ask.Passage("p", f"{i} " + "x" * 50) for i in range(ask.MAX_PASSAGES)]
        kept, left = ask_data.choose(few, "q", ask.BUDGET, ask.MAX_PASSAGES)
        self.assertEqual((len(kept), left), (ask.MAX_PASSAGES, 0))
        kept, left = ask_data.choose(few + [ask.Passage("p", "last")], "q", ask.BUDGET, ask.MAX_PASSAGES)
        self.assertEqual((len(kept), left), (ask.MAX_PASSAGES, 1))
        self.assertEqual(kept[0], few[0])

    def test_the_count_cut_says_it_with_the_existing_words(self):
        got = self._many(400)
        line = " ".join(ask_data.left_out_lines(got.counts))
        self.assertRegex(line, r"Sent \d+ of \d+ actions \(the closest to your question\); \d+ were left out\.")

    def test_the_project_share_is_a_whole_number_of_characters(self):
        from clark import ask_service
        self.assertIs(type(ask_service.PROJECT_SHARE), int)

    def test_the_kinds_are_kept_in_the_reading_order(self):
        self.assertEqual(ask_data.KIND_ORDER, ("milestones", "actions", "raid", "decisions", "use_cases", "workstreams"))

    def test_a_limit_of_zero_keeps_nothing(self):
        few = [ask.Passage("p", f"{i} x") for i in range(3)]
        kept, left = ask_data.choose(few, "q", ask.BUDGET, 0)
        self.assertEqual((kept, left), ((), 3))


if __name__ == "__main__":
    unittest.main()
