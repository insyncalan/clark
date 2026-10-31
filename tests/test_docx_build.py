"""#48: the Word report built from a report's published rows (src/clark/docx_build.py). Design: docs/handoff/design-48-word.md.

Run: python3 dev/run_tests.py test_docx_build
The rows are the #39 plant (tests/fixtures/publish-plant.json, project PUB, all made up), passed through publish.select() as the
published file's rows are. No database, no browser, no Word: every part is read back as a zip, parsed as XML and searched, and the
text is read back with docx_read. What is asserted: the same rows give the same bytes; every part is well formed and listed; what
select() dropped is in no part, in four spellings; a field select() did not keep is never written even if a row carries it; rich
text goes through the sanitiser; a value is only ever text in the XML.
"""
import copy
import io
import re
import time
import unittest
import xml.dom.minidom
import zipfile
from unittest import mock

from _paths import ROOT   # noqa: F401  (puts src/ on the path)

import _publish_fixture as fx
from clark import docx_build, docx_read, look, platform, publish
from clark.docx_build import WordError

SENSITIVE_WORDS = r"(?i)traceback|exception|\bxml\b|\bzip\b|errno|\bAPI\b"
# A kept row's own text is shown instead of its client wording, or the other way round, never both (data-model.md): this row's
# description is replaced by its client message.
REPLACED = {"ZQ-KEEP-ACTION-1"}


def published(plant=None):
    return publish.select(fx.inputs(plant))


def parts(data):
    z = zipfile.ZipFile(io.BytesIO(data))
    return {i.filename: z.read(i.filename) for i in z.infolist()}


def every_text(data):
    return "\n".join(b.decode("utf-8") for b in parts(data).values())


def blocks(data):
    return docx_read.read(data, "report.docx").blocks


def headings(data):
    return [b["text"] for b in blocks(data) if b["kind"] == "heading" and b["level"] == 1]


def with_project(p, **fields):
    p = copy.deepcopy(p)
    p["data"]["project"].update(fields)
    return p


class Repeatable(unittest.TestCase):
    def test_the_same_rows_give_the_same_bytes(self):
        a = docx_build.build(published())
        b = docx_build.build(published())
        self.assertEqual(a, b)
        self.assertNotEqual(a, docx_build.build(with_project(published(), name="Another project")))

    def test_another_day_gives_another_file(self):
        p = published()
        q = copy.deepcopy(p)
        q["as_at"] = "2026-11-30"
        self.assertNotEqual(docx_build.build(p), docx_build.build(q))

    def test_the_zip_is_plain_and_the_same_on_every_machine(self):
        z = zipfile.ZipFile(io.BytesIO(docx_build.build(published())))
        names = [i.filename for i in z.infolist()]
        self.assertEqual(names[0], "[Content_Types].xml")
        self.assertEqual(len(names), len(set(names)))
        for i in z.infolist():
            self.assertTrue(i.filename.isascii() and "\\" not in i.filename and not i.filename.startswith("/"), i.filename)
            self.assertEqual((i.date_time, i.create_system, i.external_attr >> 16), ((1980, 1, 1, 0, 0, 0), 3, 0o644))
        self.assertIsNone(z.testzip())

    def test_nobody_is_named_in_the_file(self):
        core = parts(docx_build.build(published()))["docProps/core.xml"].decode("utf-8")
        self.assertIn("<dc:creator>clark</dc:creator>", core)
        self.assertIn("<cp:lastModifiedBy>clark</cp:lastModifiedBy>", core)
        self.assertIn("2026-10-28T00:00:00Z", core)


class WellFormed(unittest.TestCase):
    def setUp(self):
        self.parts = parts(docx_build.build(published()))

    def test_every_part_parses(self):
        for name, raw in self.parts.items():
            xml.dom.minidom.parseString(raw)
            self.assertNotIn(b"<!DOCTYPE", raw, name)
            self.assertNotIn(b"<!ENTITY", raw, name)

    def test_every_part_is_in_the_content_types(self):
        dom = xml.dom.minidom.parseString(self.parts["[Content_Types].xml"])
        overrides = {e.getAttribute("PartName") for e in dom.getElementsByTagName("Override")}
        defaults = {e.getAttribute("Extension") for e in dom.getElementsByTagName("Default")}
        for name in self.parts:
            if name != "[Content_Types].xml":
                self.assertTrue("/" + name in overrides or name.rsplit(".", 1)[-1] in defaults, name)
        for o in overrides:
            self.assertIn(o[1:], self.parts)

    def test_every_relationship_points_at_a_part_or_a_safe_address(self):
        for name in ("_rels/.rels", "word/_rels/document.xml.rels"):
            dom = xml.dom.minidom.parseString(self.parts[name])
            base = "word/" if name.startswith("word/") else ""
            for r in dom.getElementsByTagName("Relationship"):
                if r.getAttribute("TargetMode") == "External":
                    self.assertTrue(r.getAttribute("Target").startswith(("https://", "mailto:")))
                    self.assertTrue(r.getAttribute("Type").endswith("/hyperlink"))
                else:
                    self.assertIn(base + r.getAttribute("Target"), self.parts)

    def test_every_reference_in_the_document_is_a_relationship(self):
        p = with_project(published(), current_state='<p><a href="https://example.org/a">a</a> <a href="mailto:a@example.org">b</a></p>')
        both = parts(docx_build.build(p))
        ids = set(re.findall(r'<Relationship Id="(rId\d+)"', both["word/_rels/document.xml.rels"].decode()))
        used = set(re.findall(r'r:id="(rId\d+)"', both["word/document.xml"].decode()))
        self.assertTrue(used and used <= ids)
        self.assertEqual(len(ids), len(set(re.findall(r'<Relationship Id="(rId\d+)"', both["word/_rels/document.xml.rels"].decode()))))

    def test_the_list_numbers_used_are_in_the_numbering_part(self):
        p = with_project(published(), current_state="<ol><li>a</li></ol><p>x</p><ol><li>b</li><li>c</li></ol><ul><li>d</li></ul>")
        both = parts(docx_build.build(p))
        used = set(re.findall(r'<w:numId w:val="(\d+)"/>', both["word/document.xml"].decode()))
        have = set(re.findall(r'<w:num w:numId="(\d+)"', both["word/numbering.xml"].decode()))
        self.assertEqual(used, {"1", "2", "3"})
        self.assertTrue(used <= have)
        self.assertEqual(both["word/numbering.xml"].decode().count("<w:startOverride"), 2)       # each ordered list starts at 1


class OnlyThePublishedRows(unittest.TestCase):
    def setUp(self):
        self.plant = fx.load()
        self.data = docx_build.build(published(self.plant))
        self.everything = every_text(self.data)

    def test_what_select_dropped_is_in_no_part(self):
        for where, marker in self.plant["markers"].items():
            for spelling in fx.spellings(marker):
                self.assertNotIn(spelling, self.everything, f"{where}: {spelling!r}")

    def test_what_select_kept_is_in_the_file(self):
        for where, marker in self.plant["kept_markers"].items():
            if marker not in REPLACED:
                self.assertIn(marker, self.everything, where)

    def test_a_field_select_did_not_keep_is_never_written(self):
        p = published(self.plant)
        for k in ("milestones", "actions", "raid", "decisions", "use_cases", "workstreams"):
            for row in p["data"][k]:
                row.update(internal_note="ZQ-X-NOTE", source="ZQ-X-SOURCE", reasoning="ZQ-X-REASON", options="ZQ-X-OPTIONS",
                           response_action="ZQ-X-RESPONSE", movement="ZQ-X-MOVE", publish_client="ZQ-X-FOLDER",
                           by_user="ZQ-X-USER", extra_field="ZQ-X-EXTRA", archived=0, client_visible=1)
        p["data"]["project"].update(publish_local="ZQ-X-LOCAL", publish_client="ZQ-X-CLIENT", internal_note="ZQ-X-PROJECT")
        p["data"]["labels"] = {"PUB-A-001": ["ZQ-X-LABEL"]}
        p["data"]["links"] = [{"from_item": "PUB-A-001", "to_item": "PUB-A-002", "kind": "ZQ-X-LINK"}]
        p["data"]["comments"] = [{"body": "ZQ-X-COMMENT"}]
        p["sections"][0]["internal"] = "ZQ-X-SECTION"
        self.assertNotIn("ZQ-X-", every_text(docx_build.build(p)))

    def test_a_row_that_is_not_in_the_rows_is_not_in_the_file(self):
        p = published(self.plant)
        p["data"]["actions"] = [a for a in p["data"]["actions"] if a["id"] != "PUB-A-002"]
        self.assertNotIn("PUB-A-002", every_text(docx_build.build(p)))
        self.assertNotIn("ZQ-KEEP-ACTION-2", every_text(docx_build.build(p)))

    def test_a_section_that_is_not_shown_is_not_in_the_file(self):
        p = published(self.plant)
        p["sections"] = [s for s in p["sections"] if s["type"] in ("current", "glance")]
        text = every_text(docx_build.build(p))
        for needle in ("Actions", "Decisions", "Risks and issues", "Milestones", "Use cases", "Overdue actions", "High risks"):
            self.assertNotIn(needle, text)
        self.assertIn("Current state", text)

    def test_boxed_is_the_only_layout(self):
        base = docx_build.build(published(self.plant))
        for layout in ("boxed", "spine", "cover", "something else", None, ""):
            p = published(self.plant)
            p["data"]["project"]["layout"] = layout
            self.assertEqual(docx_build.build(p), base, layout)

    def test_hidden_flag_off_archived_and_sensitive_rows_are_each_absent(self):
        by_word = {w: m for w, m in self.plant["markers"].items() if w.startswith("PUB-")}
        for needle in ("HIDDEN", "FLAG-OFF", "ARCHIVED", "SENSITIVE"):
            found = [m for m in by_word.values() if needle in m]
            self.assertTrue(found, needle)
            for m in found:
                self.assertNotIn(m, self.everything)
        self.assertNotIn(self.plant["markers"]["hidden_section_title"], self.everything)

    def test_every_part_is_utf_8_and_other_alphabets_survive(self):
        p = published(self.plant)
        p["data"]["actions"][0]["client_message"] = ""
        p["data"]["actions"][0]["description"] = "Zażółć gęślą jaźń \u4e2d\u6587 \u0645\u0631\u062d\u0628\u0627"
        data = docx_build.build(p)
        for name, raw in parts(data).items():
            raw.decode("utf-8")
            self.assertTrue(raw.startswith(b"<?xml") is False or b'encoding="UTF-8"' in raw[:80], name)
        self.assertIn("Zażółć gęślą jaźń \u4e2d\u6587 \u0645\u0631\u062d\u0628\u0627", every_text(data))

    def test_a_cancelled_milestone_is_left_out(self):
        p = published(self.plant)
        p["data"]["milestones"][0]["status"] = "Cancelled"
        text = every_text(docx_build.build(p))
        self.assertNotIn("ZQ-KEEP-MILESTONE-1", text)
        self.assertIn("ZQ-KEEP-MILESTONE-2", text)


class WhatIsInIt(unittest.TestCase):
    def setUp(self):
        self.p = published()
        self.data = docx_build.build(self.p)
        self.blocks = blocks(self.data)

    def test_the_sections_come_in_the_published_order(self):
        self.assertEqual(headings(self.data)[1:], [s["title"] for s in self.p["sections"]])

    def test_the_order_follows_the_rows_it_is_given(self):
        p = copy.deepcopy(self.p)
        p["sections"].reverse()
        got = headings(docx_build.build(p))[1:]
        self.assertEqual(got, [s["title"] for s in p["sections"]])

    def test_a_section_keeps_its_own_title(self):
        p = copy.deepcopy(self.p)
        p["sections"][0]["title"] = "Where we are"
        self.assertIn("Where we are", headings(docx_build.build(p)))

    def test_the_title_block(self):
        self.assertEqual(self.blocks[0], {"kind": "heading", "level": 1, "text": 'Bridge & "Harbour" <Programme>'})
        self.assertEqual(self.blocks[1]["text"], "Week ending 23-10-2026")
        rows = self.blocks[2]["rows"]
        self.assertIn(["Project code", "PUB"], rows)
        self.assertIn(["Client", "Example Client"], rows)
        self.assertIn(["As at", "28-10-2026"], rows)

    def test_no_week_ending_says_as_at(self):
        self.assertEqual(blocks(docx_build.build(with_project(self.p, week_ending=None)))[1]["text"], "As at 28-10-2026")

    def test_a_table_for_each_kind(self):
        heads = [b["rows"][0] for b in self.blocks if b["kind"] == "table" and b["rows"][0][0] in ("ID", "Ref")]
        self.assertEqual([h[1] for h in heads], ["Use case", "Milestone", "Type", "Action", "Decision"])

    def test_client_wording_replaces_the_rows_own_text(self):
        text = every_text(self.data)
        self.assertIn("ZQ-KEEP-MESSAGE-1", text)
        self.assertNotIn("ZQ-KEEP-ACTION-1", text)            # PUB-A-001 has client wording
        self.assertIn("ZQ-KEEP-ACTION-2", text)               # PUB-A-002 has none: its own text shows
        self.assertIn("Latest update: ZQ-KEEP-UPDATE-1", text)

    def test_milestones_use_the_clients_words(self):
        text = every_text(self.data)
        self.assertIn("Expected later", text)
        self.assertNotIn("Slipped", text)
        self.assertIn("+13 days", text)
        self.assertIn("Reason: ZQ-KEEP-STATE-REASON", text)

    def test_an_achieved_milestone_says_when(self):
        p = copy.deepcopy(self.p)
        p["data"]["milestones"][0].update(status="Done", actual_date="2026-10-14", state="Achieved", state_word="Achieved")
        text = every_text(docx_build.build(p))
        self.assertIn("Achieved 14-10-2026", text)

    def test_dates_read_dd_mm_yyyy_and_are_never_stored_dates(self):
        both = parts(self.data)
        words = (both["word/document.xml"] + both["word/footer1.xml"]).decode("utf-8")
        self.assertIn("23-10-2026", words)
        self.assertIn("06-11-2026", words)
        self.assertIn("as at 28-10-2026", words)
        self.assertFalse(re.search(r"\d{4}-\d\d-\d\d", words))

    def test_health_is_words_and_a_colour(self):
        doc = parts(self.data)["word/document.xml"].decode("utf-8")
        self.assertIn("Project health: ", doc)
        self.assertIn("At risk", doc)
        self.assertIn("ZQ-HEALTH-REASON", doc)
        self.assertIn(docx_build.TOKENS["status-amber-tint"], doc)

    def test_status_words_travel_with_their_colour(self):
        for b in self.blocks:
            if b["kind"] == "table" and b["rows"][0][0] == "ID" and "Priority" in b["rows"][0]:
                col = b["rows"][0].index("Priority")
                self.assertTrue(all(r[col] in ("Urgent", "High", "Medium", "Low") for r in b["rows"][1:]))

    def test_an_open_row_past_its_date_says_overdue_and_a_closed_one_does_not(self):
        p = copy.deepcopy(self.p)
        p["as_at"] = "2026-12-31"
        p["data"]["actions"][0]["status"] = "Closed"

        def due_cells(q):
            table = next(b["rows"] for b in blocks(docx_build.build(q)) if b["kind"] == "table" and b["rows"][0][:2] == ["ID", "Action"])
            return {r[0]: r[4] for r in table[1:]}

        got = due_cells(p)
        self.assertEqual(got["PUB-A-002"], "06-11-2026 (overdue)")
        self.assertEqual(got["PUB-A-001"], "06-11-2026")
        self.assertEqual(due_cells(self.p)["PUB-A-002"], "06-11-2026")

    def test_a_table_with_no_rows_says_none_recorded(self):
        p = copy.deepcopy(self.p)
        p["data"]["actions"] = []
        text = every_text(docx_build.build(p))
        self.assertIn("None recorded.", text)

    def test_an_empty_current_state_or_text_section_is_left_out(self):
        p = with_project(self.p, current_state="")
        for s in p["sections"]:
            if s["type"] == "text":
                s["body"] = ""
        got = headings(docx_build.build(p))
        self.assertNotIn("Current state", got)
        self.assertNotIn("Programme notes", got)

    def test_the_tiles_count_only_what_is_published(self):
        text = every_text(self.data)
        self.assertIn("Overdue actions", text)
        self.assertIn("of 2 open actions", text)
        self.assertIn("High risks and issues", text)
        self.assertNotIn("Decisions needed", text)             # hidden by default, as on the page

    def test_use_cases_show_their_linked_items(self):
        text = every_text(self.data)
        self.assertIn("1 use case", text)
        self.assertIn("Linked work items: PUB-A-001", text)

    def test_a_footer_has_the_page_number_and_no_line_starts_with_the_product_name(self):
        footer = parts(self.data)["word/footer1.xml"].decode("utf-8")
        self.assertIn("PAGE", footer)
        self.assertIn("NUMPAGES", footer)
        for b in self.blocks:
            for line in ([b["text"]] if "text" in b else [c for r in b["rows"] for c in r]):
                self.assertFalse(line.startswith("clark"), line)

    def test_a_work_row_with_nothing_missing_builds(self):
        p = copy.deepcopy(self.p)
        for k in ("milestones", "actions", "raid", "decisions", "use_cases"):
            p["data"][k] = [{f: None for f in row} for row in p["data"][k]]
        docx_build.build(p)


class RichText(unittest.TestCase):
    def render(self, html):
        data = docx_build.build(with_project(published(), current_state=html))
        return data, parts(data)

    def test_hostile_text_never_reaches_the_file(self):
        data, both = self.render(
            '<script>alert(1)</script><p onclick="steal()">hi <b style="x">there</b></p><a href="javascript:alert(2)">bad</a>'
            '<img src="x" onerror="boom()"><style>p{color:red}</style><iframe src="https://evil.invalid"></iframe>'
            '<a href="data:text/html,x">data</a><a href=" jav&#9;ascript:alert(3)">tab</a><object data="x"></object>')
        everything = every_text(data)
        for needle in ("alert", "javascript", "onclick", "onerror", "steal", "boom", "evil.invalid", "<img", "data:text", "iframe",
                       "color:red"):
            self.assertNotIn(needle, everything)
        self.assertNotIn("Hyperlink", both["word/document.xml"].decode().split("<w:body>")[1])
        self.assertIn("hi", everything)

    def test_only_https_and_mailto_become_links(self):
        data, both = self.render('<p><a href="https://example.org/x?a=1&amp;b=2">one</a> <a href="http://example.org/plain">two</a> '
                                 '<a href="mailto:a@example.org">three</a> <a href="#top">four</a></p>')
        rels = both["word/_rels/document.xml.rels"].decode("utf-8")
        self.assertIn('Target="https://example.org/x?a=1&amp;b=2"', rels)
        self.assertIn('Target="mailto:a@example.org"', rels)
        self.assertNotIn("http://example.org", rels)
        self.assertEqual(rels.count('TargetMode="External"'), 2)
        text = " ".join(b.get("text", "") for b in blocks(data))
        self.assertIn("two", text)
        self.assertIn("four", text)

    def test_the_same_link_is_one_relationship(self):
        _, both = self.render('<p><a href="https://example.org/a">x</a> <a href="https://example.org/a">y</a></p>')
        self.assertEqual(both["word/_rels/document.xml.rels"].decode().count('TargetMode="External"'), 1)

    def test_formatting_headings_lists_quotes_and_rules_map(self):
        data, both = self.render(
            "<h1>Big</h1><h2>Medium</h2><h3>Small</h3><p><strong>b</strong><em>i</em><s>s</s>"
            "<strong><em>both</em></strong></p><ul><li>one<ul><li>deep<ul><li>deeper</li></ul></li></ul></li><li>two</li></ul>"
            "<ol><li>first</li><li>second</li></ol><blockquote><p>quoted</p></blockquote><hr><p>line<br>break</p>"
            '<ul><li><input type="checkbox" checked disabled> done</li><li><input type="checkbox" disabled> to do</li></ul>')
        doc = both["word/document.xml"].decode("utf-8")
        for style in ("Heading2", "Heading3", "Heading4", "Quote", "ListParagraph"):
            self.assertIn(f'<w:pStyle w:val="{style}"/>', doc)
        for tag in ("<w:b/>", "<w:i/>", "<w:strike/>", "<w:br/>", "<w:pBdr>"):
            self.assertIn(tag, doc)
        items = [b["text"] for b in blocks(data) if b["kind"] == "list_item"]
        self.assertIn("\u2611 done", items)
        self.assertIn("\u2610 to do", items)
        got = [b for b in blocks(data) if b["kind"] in ("list_item", "heading")]
        mine = [(b["kind"], b.get("level"), b.get("ordered"), b["text"]) for b in got if b["text"] in
                ("Big", "Medium", "Small", "one", "deep", "deeper", "two", "first", "second")]
        self.assertEqual(mine, [("heading", 2, None, "Big"), ("heading", 3, None, "Medium"), ("heading", 4, None, "Small"),
                                ("list_item", 0, False, "one"), ("list_item", 1, False, "deep"), ("list_item", 2, False, "deeper"),
                                ("list_item", 0, False, "two"), ("list_item", 0, True, "first"), ("list_item", 0, True, "second")])

    def test_lists_deeper_than_three_levels_stay_at_three(self):
        _, both = self.render("<ul><li>a<ul><li>b<ul><li>c<ul><li>d<ul><li>e</li></ul></li></ul></li></ul></li></ul></li></ul>")
        levels = {int(x) for x in re.findall(r'<w:ilvl w:val="(\d+)"/>', both["word/document.xml"].decode())}
        self.assertEqual(levels, {0, 1, 2})

    def test_a_value_is_only_text_in_the_xml(self):
        nasty = '</w:t></w:r></w:p><w:p><w:r><w:t>INJECTED & "quoted" \x00\x0b\ud800 end'
        p = with_project(published(), name=nasty, sponsor=nasty, current_state=f"<p>{nasty.replace('<', '&lt;')}</p>")
        p["data"]["actions"][0]["description"] = nasty
        p["data"]["actions"][0]["client_message"] = ""
        data = docx_build.build(p)
        both = parts(data)
        for name, raw in both.items():
            xml.dom.minidom.parseString(raw)
        doc = both["word/document.xml"].decode("utf-8")
        self.assertNotIn("</w:t></w:r></w:p><w:p><w:r><w:t>INJECTED", doc)
        self.assertEqual(blocks(data)[0]["text"], '</w:t></w:r></w:p><w:p><w:r><w:t>INJECTED & "quoted" end')
        self.assertFalse(re.search("[\x00-\x08\x0b\x0c\x0e-\x1f]", doc))

    def test_a_text_of_two_hundred_thousand_characters_builds(self):
        started = time.time()
        data = docx_build.build(with_project(published(), current_state="<p>" + "word " * 39_998 + "</p>"))
        self.assertLess(time.time() - started, 10)
        self.assertGreater(len(data), 1000)

    def test_a_text_that_is_too_long_is_refused_in_words(self):
        with self.assertRaises(WordError) as caught:
            docx_build.build(with_project(published(), current_state="<p>" + "x" * 200_001 + "</p>"))
        self.assertIn("too long", str(caught.exception))
        self.assertNotRegex(str(caught.exception), SENSITIVE_WORDS)

    def test_rich_text_in_a_use_case_and_a_text_section_goes_through_the_sanitiser_too(self):
        p = published()
        p["data"]["use_cases"][0]["standing"] = '<p>ok</p><script>alert("ZQ-STANDING")</script>'
        for s in p["sections"]:
            if s["type"] == "text":
                s["body"] = '<p>fine</p><iframe src="https://evil.invalid">ZQ-BODY</iframe>'
        text = every_text(docx_build.build(p))
        self.assertNotIn("ZQ-STANDING", text)
        self.assertNotIn("ZQ-BODY", text)
        self.assertIn("fine", text)


class Brand(unittest.TestCase):
    def test_a_local_brand_is_laid_over_the_demo_colours(self):
        both = parts(docx_build.build(published(), colours={"brand-navy": "#112233"}))
        self.assertIn("112233", both["word/styles.xml"].decode())
        self.assertNotIn(docx_build.TOKENS["brand-navy"], both["word/styles.xml"].decode())

    def test_a_colour_that_is_not_six_hex_digits_is_ignored(self):
        bad = {"brand-navy": '"/><w:evil/>', "grey-700": "12345", "status-red-text": "GGGGGG", "no-such-token": "123456",
               "white": "#abcdef"}
        data = docx_build.build(published(), colours=bad)
        everything = every_text(data)
        self.assertNotIn("evil", everything)
        self.assertNotIn("123456", everything)
        self.assertIn("ABCDEF", everything)
        self.assertEqual(docx_build.palette(bad)["brand-navy"], docx_build.TOKENS["brand-navy"])


class FollowsTheLook(unittest.TestCase):
    def test_the_font_is_the_looks_office_font_in_every_run_style(self):
        styles = parts(docx_build.build(published()))["word/styles.xml"].decode()
        font = look.office_font()
        self.assertEqual(docx_build.FONT, font)
        names = set(re.findall(r'<w:rFonts [^>]*>', styles))
        names = {v for tag in names for v in re.findall(r'w:(?:ascii|hAnsi|eastAsia|cs)="([^"]*)"', tag)}
        self.assertEqual(names, {font}, "every font in the styles is the one the look names")

    def test_a_font_the_look_changes_is_the_font_the_file_uses(self):
        css = ":root { --font-office: Verdana; --font-email: Calibri, Arial, sans-serif; }"
        self.assertEqual(look.office_font(css), "Verdana")
        with mock.patch.object(docx_build, "FONT", look.office_font(css)):
            self.assertIn('w:ascii="Verdana"', parts(docx_build.build(published()))["word/styles.xml"].decode())

    def test_the_colours_are_the_looks_light_values(self):
        for name, hexa in docx_build.TOKENS.items():
            self.assertEqual(hexa, look.colour(name), name)


class Refusals(unittest.TestCase):
    def test_rows_that_are_not_a_report_are_refused_in_words(self):
        good = published()
        for bad in ({}, None, {"data": {}, "sections": [], "as_at": "2026-10-28"}, {**good, "as_at": "28-10-2026"},
                    {**good, "as_at": None}, {**good, "sections": None}, {**good, "data": {**good["data"], "project": {}}}):
            with self.assertRaises(WordError) as caught:
                docx_build.build(bad)
            self.assertNotRegex(str(caught.exception), SENSITIVE_WORDS)

    def test_a_file_over_the_limit_is_refused_in_words(self):
        with mock.patch.object(docx_build, "MAX_BYTES", 1000):
            with self.assertRaises(WordError) as caught:
                docx_build.build(published())
        self.assertIn("MB", str(caught.exception))
        self.assertTrue(str(caught.exception).endswith("Leave out some sections or pictures and try again."), str(caught.exception))
        self.assertNotRegex(str(caught.exception), SENSITIVE_WORDS)

    def test_the_refusals_say_what_to_do_next(self):
        said = []
        for bad in ({}, {**published(), "as_at": "28-10-2026"}, {**published(), "data": {**published()["data"], "project": {}}}):
            with self.assertRaises(WordError) as caught:
                docx_build.build(bad)
            said.append(str(caught.exception))
        self.assertEqual(said[0], "The report could not be made: its rows are missing, or the report date is not a real day. "
                                  "Restart clark and try again.")
        self.assertEqual(said[2], "The report could not be made: there is no project to put in it. Restart clark and try again.")
        self.assertEqual(said[0], said[1])

    def test_a_big_report_builds_within_the_limit(self):
        p = published()
        base = p["data"]["actions"][0]
        p["data"]["actions"] = [dict(base, id=f"PUB-A-{n:04d}", description=f"Action number {n} with some words in it") for n in range(2000)]
        started = time.time()
        data = docx_build.build(p)
        self.assertLess(time.time() - started, 20)
        self.assertLess(len(data), docx_build.MAX_BYTES)
        self.assertIn("PUB-A-1999", every_text(data))


class FileName(unittest.TestCase):
    def test_the_name(self):
        self.assertEqual(docx_build.file_name("PUB", "2026-10-23", "2026-10-28"), "PUB-report-2026-10-23.docx")
        self.assertEqual(docx_build.file_name("PUB", None, "2026-10-28"), "PUB-report-2026-10-28.docx")
        self.assertEqual(docx_build.file_name("PUB", "2026-10-23", "2026-10-28"),
                         platform.safe_name("PUB-report-2026-10-23.docx"))

    def test_a_deep_folder_keeps_the_extension(self):
        name = docx_build.file_name("PUB", "2026-10-23", "2026-10-28", "/" + "/".join(["a" * 40] * 6))
        self.assertTrue(name.endswith(".docx"), name)


class RoundTrip(unittest.TestCase):
    def test_the_text_of_the_rows_reads_back(self):
        p = published()
        got = blocks(docx_build.build(p))
        flat = " ".join(c for b in got if b["kind"] == "table" for r in b["rows"] for c in r)
        for a in p["data"]["actions"]:
            self.assertIn(a["id"], flat)
        for d in p["data"]["decisions"]:
            self.assertIn(d["decision"], flat)
        for m in p["data"]["milestones"]:
            self.assertIn(m["name"], flat)
        self.assertEqual([b["text"] for b in got if b["kind"] == "heading" and b["level"] == 1][0], p["data"]["project"]["name"])

    def test_what_the_reader_says_it_did_not_read(self):
        notes = docx_read.read(docx_build.build(published()), "report.docx").notes
        self.assertEqual(notes, ["The web address of 1 link was not read; the words stay."])


class Source(unittest.TestCase):
    """NFR-9: nothing here may need a system, a network or the disk."""

    def test_the_modules_touch_neither_disk_nor_network_nor_a_process(self):
        for name in ("docx_build.py", "docx_read.py"):
            src = (ROOT / "src" / "clark" / name).read_text(encoding="utf-8")
            for word in (r"(?<![.\w])open\(", r"\bsocket\b", r"\burllib\b", r"\bsubprocess\b", r"os\.system", r"\bhttp\.client\b",
                         r"\bpathlib\b", r"\bos\.", r"\bsys\.", r"\bimport openpyxl", r"\bdatetime\.now", r"\btime\.time\b", r"\brandom\b"):
                self.assertFalse(re.search(word, src), f"{name}: {word}")
            for module in re.findall(r"^(?:import|from) (\w+)", src, re.M):
                self.assertIn(module, ("io", "re", "zipfile", "zlib", "unicodedata", "typing", "xml", "datetime", "clark"), f"{name}: {module}")

    def test_every_message_is_plain(self):
        for text in (docx_build.NONE,):
            self.assertNotRegex(text, SENSITIVE_WORDS)


if __name__ == "__main__":
    unittest.main()
