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
from clark import docx_build, docx_read, glance, look, platform, publish
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
    return "\n".join(b.decode("utf-8", "replace") for b in parts(data).values())      # a picture part is bytes: it is searched too, as text


def blocks(data):
    return docx_read.read(data, "report.docx").blocks


def headings(data):
    return [b["text"] for b in blocks(data) if b["kind"] == "heading" and b["level"] == 1]


def with_project(p, **fields):
    p = copy.deepcopy(p)
    p["data"]["project"].update(fields)
    return p


class HostileValues(unittest.TestCase):
    """A stored value that is not text (a list, a dict) in a field that picks a colour must not break the Word build (an unhashable
    value in a dict or set lookup raised TypeError): it just has no colour. The risks are LINKED to a use case and open, so the
    use-case strip (glance.use_case_strip, worst colour, pill_of, colour_of_priority) is reached as well as the table cells."""
    def plant(self, bad):
        plant = fx.load()
        data = plant["data"]
        for row in data["raid"]:
            row["priority"] = bad
            row["use_case"] = data["use_cases"][0]["id"]
            row["status"] = "Open"
        for row in data["actions"]:
            row["priority"] = bad
            row["use_case"] = data["use_cases"][0]["id"]
        for row in data["decisions"]:
            row["status"] = bad
        return plant

    def test_a_priority_or_status_that_is_not_text_builds_with_no_colour(self):
        for bad in (["High"], {"a": 1}):
            with self.subTest(bad=bad):
                data = docx_build.build(published(self.plant(bad)))
                self.assertTrue(data.startswith(b"PK"))

    def test_a_priority_that_is_not_text_is_not_rated_on_a_linked_risk(self):
        for bad in (["High"], {"a": 1}):
            with self.subTest(bad=bad):
                plant = self.plant(bad)
                d = plant["data"]
                rows = glance.use_case_strip(d["use_cases"], glance.work_rows(d), "2026-10-28")["rows"]
                linked = [r for r in rows if r["id"] == plant["data"]["use_cases"][0]["id"]]
                self.assertTrue(linked)
                self.assertIsNone(linked[0]["worst"])
                self.assertIsNone(glance.colour_of_priority(bad))


class HostileHealthAndStatus(unittest.TestCase):
    """Row 1035: a project's health or a use case's status that is a list or dict (an unhashable key in a colour lookup raised
    TypeError) builds with no colour, with a use case linked to open work."""
    def plant(self, bad):
        plant = fx.load()
        data = plant["data"]
        data["project"]["health"] = bad
        for uc in data["use_cases"]:
            uc["status"] = bad
        for row in data["raid"]:
            row["use_case"] = data["use_cases"][0]["id"]
            row["status"] = "Open"
        return plant

    def test_a_health_or_use_case_status_that_is_not_text_builds(self):
        for bad in (["On track"], {"a": 1}):
            with self.subTest(bad=bad):
                self.assertTrue(docx_build.build(published(self.plant(bad))).startswith(b"PK"))

    def test_the_pill_and_the_strip_give_no_colour(self):
        for bad in (["On track"], {"a": 1}):
            with self.subTest(bad=bad):
                pill = glance.health_pill(bad)
                self.assertIsNone(pill["colour"])
                self.assertEqual(pill["words"], "Not set")
                d = self.plant(bad)["data"]
                rows = glance.use_case_strip(d["use_cases"], glance.work_rows(d), "2026-10-28")["rows"]
                self.assertTrue(rows)
                self.assertEqual([r["colour"] for r in rows], [None] * len(rows))      # no colour at all, not a grey one


class HostileColourLookups(unittest.TestCase):
    """Row 1035 follow-up: the priority and status cells in the Word tables (docx_build colour_for lookups) take a stored list
    or dict without an unhashable-key error and give it no colour."""
    def test_a_priority_state_or_status_that_is_not_text_builds(self):
        for bad in (["High"], {"a": 1}):
            with self.subTest(bad=bad):
                plant = fx.load()
                data = plant["data"]
                for table, fields in (("actions", ("priority", "status")), ("raid", ("priority", "status")),
                                      ("decisions", ("status",))):
                    for row in data.get(table, []):
                        for f in fields:
                            row[f] = bad
                self.assertTrue(docx_build.build(published(plant)).startswith(b"PK"))


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
            if name.startswith("word/media/"):
                self.assertTrue(name.endswith(".png") and raw.startswith(b"\x89PNG\r\n\x1a\n"), name)      # a picture: tests/test_docx_graphics.py reads it
                continue
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
            if name.startswith("word/media/"):
                continue                                                     # a picture is bytes, checked in tests/test_docx_graphics.py
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

    def test_a_milestones_client_wording_is_rich_and_reads_as_plain_words_in_word(self):
        # Item 1078: the client wording is stored as the editor's HTML; the Word copy must show its words, never the tags.
        p = copy.deepcopy(self.p)
        p["data"]["milestones"][0].update(client_message="<p>ZQ-RICH-WORDS <strong>bold</strong> &amp; more</p>")
        text = every_text(docx_build.build(p))
        self.assertIn("ZQ-RICH-WORDS", text)
        self.assertIn("bold", text)
        self.assertNotIn("&lt;p&gt;", text)
        self.assertNotIn("&lt;strong&gt;", text)

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
        self.assertIn(docx_build.TOKENS["tone-amber-tint"], doc)

    def test_status_words_travel_with_their_colour(self):
        for b in self.blocks:
            if b["kind"] == "table" and b["rows"][0][0] == "ID" and "Priority" in b["rows"][0]:
                col = b["rows"][0].index("Priority")
                self.assertTrue(all(r[col] in ("Urgent", "High", "Medium", "Low") for r in b["rows"][1:]))

    def test_an_open_row_past_its_date_says_overdue_and_a_closed_one_is_not_listed(self):
        p = copy.deepcopy(self.p)
        p["as_at"] = "2026-12-31"
        p["data"]["actions"][0]["status"] = "Closed"

        def due_cells(q):
            table = next(b["rows"] for b in blocks(docx_build.build(q)) if b["kind"] == "table" and b["rows"][0][:2] == ["ID", "Action"])
            return {r[0]: r[4] for r in table[1:]}

        got = due_cells(p)
        self.assertEqual(got["PUB-A-002"], "06-11-2026 (overdue)")
        self.assertNotIn("PUB-A-001", got)      # row 837: a closed action is not listed at all
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
            if not name.startswith("word/media/"):
                xml.dom.minidom.parseString(raw)
        doc = both["word/document.xml"].decode("utf-8")
        self.assertNotIn("</w:t></w:r></w:p><w:p><w:r><w:t>INJECTED", doc)
        self.assertEqual(blocks(data)[0]["text"], '</w:t></w:r></w:p><w:p><w:r><w:t>INJECTED & "quoted" end')
        self.assertFalse(re.search("[\x00-\x08\x0b\x0c\x0e-\x1f]", doc))

    def test_a_text_of_two_hundred_thousand_characters_builds(self):
        started = time.process_time()
        data = docx_build.build(with_project(published(), current_state="<p>" + "word " * 39_998 + "</p>"))
        self.assertLess(time.process_time() - started, 60)  # CPU time, so a loaded machine does not count against it; a generous ceiling that a real blow-up still fails
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
        started = time.process_time()
        data = docx_build.build(p)
        self.assertLess(time.process_time() - started, 120)  # CPU time, so a loaded machine does not count against it; a generous ceiling that a real blow-up still fails
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
        pictures = parts(docx_build.build(published()))["word/document.xml"].decode("utf-8").count("<w:drawing>")
        self.assertEqual(pictures, 2)                                            # the Health bar and the milestone plan
        self.assertEqual(notes, ["The web address of 1 link was not read; the words stay."])             # clark's own 2 pictures are not counted


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


# Row 769: the Word copy's tables. The narrowest each column may be, in twentieths of a point, so that an ID, a date, a status
# word or "Commitment" is never broken across two lines (nine-point text and 80-twip cell margins on each side).
MIN_COL = {"ID": 1150, "Ref": 700, "Type": 1150, "Owner": 1100, "Priority": 900, "Due": 1050, "Status": 1050, "Agreed": 1050,
           "Forecast": 1050, "State": 1050, "Slip": 900, "Commitment": 1300, "Impact / likelihood": 1000, "Made by": 1300,
           "Date": 1700, "Work items": 1000}
W_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


class WordTableWidths(unittest.TestCase):
    def setUp(self):
        import xml.etree.ElementTree as ET
        root = ET.fromstring(parts(docx_build.build(published()))["word/document.xml"])
        q = "{%s}" % W_NS["w"]
        self.tables = []
        for t in root.iter(q + "tbl"):
            grid = [int(g.get(q + "w")) for g in t.find("w:tblGrid", W_NS)]
            rows = t.findall("w:tr", W_NS)
            cells = [[int(c.find("w:tcPr/w:tcW", W_NS).get(q + "w")) for c in r.findall("w:tc", W_NS)] for r in rows]
            head = ["".join(x.text or "" for x in c.iter(q + "t")) for c in rows[0].findall("w:tc", W_NS)]
            self.tables.append({"grid": grid, "cells": cells, "head": head,
                                "total": int(t.find("w:tblPr/w:tblW", W_NS).get(q + "w")),
                                "repeat": rows[0].find("w:trPr/w:tblHeader", W_NS) is not None})

    def data_tables(self):
        return [t for t in self.tables if t["head"] and t["head"][0] in ("ID", "Ref")]

    def test_every_table_fits_the_text_width_and_the_cells_follow_the_grid(self):
        self.assertTrue(self.tables)
        self.assertLessEqual(docx_build.TEXT_W, docx_build.PAGE_W - 2 * docx_build.MARGIN)
        for t in self.tables:
            self.assertEqual(sum(t["grid"]), docx_build.TEXT_W)
            self.assertEqual(t["total"], docx_build.TEXT_W)
            for row in t["cells"]:
                self.assertEqual(row, t["grid"])

    def test_the_data_tables_have_a_repeating_header_row_of_the_expected_columns(self):
        self.assertEqual([t["head"][1] for t in self.data_tables()], ["Use case", "Milestone", "Type", "Action", "Decision"])
        for t in self.data_tables():
            self.assertTrue(t["repeat"])

    def test_no_data_column_is_narrower_than_its_longest_word(self):
        for t in self.data_tables():
            for name, w in zip(t["head"], t["grid"]):
                if name in MIN_COL:
                    self.assertGreaterEqual(w, MIN_COL[name], f"{t['head'][1]} table, column {name}")

    def test_open_actions_and_risks_columns_are_wide_enough_for_ids_dates_and_words(self):
        for second, names, wide in (("Action", ["ID", "Owner", "Priority", "Due", "Status"], "Action"),
                                    ("Type", ["ID", "Type", "Owner", "Priority", "Impact / likelihood", "Due", "Status"], "Item")):
            (t,) = [x for x in self.tables if x["head"][:2] == ["ID", second]]
            for name in names:
                self.assertGreaterEqual(t["grid"][t["head"].index(name)], MIN_COL[name], f"{second} table, {name}")
            self.assertGreaterEqual(t["grid"][t["head"].index(wide)], 1800)


# Row 837: the Word copy's Open actions and Risks and issues tables list only open items (the app's rule, glance.is_open).
class WordOpenItemsOnly(unittest.TestCase):
    def built(self):
        p = copy.deepcopy(published())
        d = p["data"]
        acts, raid = d["actions"], d["raid"]
        for status, n in (("Closed", 1), ("Cancelled", 2), ("Delayed", 3)):
            a = dict(acts[0], id=f"ZQ-ACT-{n}", status=status, client_message=f"Zq action {status}", description="")
            r = dict(raid[0], id=f"ZQ-RISK-{n}", status=status, client_message=f"Zq risk {status}", description="")
            acts.append(a)
            raid.append(r)
        raid.append(dict(raid[0], id="ZQ-ISSUE-9", type="Issue", status="Closed", client_message="Zq issue Closed", description=""))
        return p, every_text(docx_build.build(p))

    def tables_text(self, p):
        import xml.etree.ElementTree as ET
        root = ET.fromstring(parts(docx_build.build(p))["word/document.xml"])
        q = "{%s}" % W_NS["w"]
        out = ""
        for t in root.iter(q + "tbl"):
            rows = t.findall("w:tr", W_NS)
            head = ["".join(x.text or "" for x in c.iter(q + "t")) for c in rows[0].findall("w:tc", W_NS)]
            if head[:2] in (["ID", "Action"], ["ID", "Type"]):
                out += "".join(x.text or "" for x in t.iter(q + "t"))
        return out

    def test_a_closed_or_cancelled_action_or_risk_is_not_listed(self):
        p, _ = self.built()
        text = self.tables_text(p)
        for gone in ("ZQ-ACT-1", "ZQ-ACT-2", "ZQ-RISK-1", "ZQ-RISK-2", "ZQ-ISSUE-9", "Zq action Closed", "Zq risk Cancelled"):
            self.assertNotIn(gone, text)

    def test_open_ones_are_still_listed(self):
        p, _ = self.built()
        text = self.tables_text(p)
        for kept in ("ZQ-ACT-3", "ZQ-RISK-3", "PUB-A-001", "PUB-A-002", "PUB-001"):
            self.assertIn(kept, text)

    def test_the_tables_hold_only_the_open_rows(self):
        p, _ = self.built()
        import xml.etree.ElementTree as ET
        root = ET.fromstring(parts(docx_build.build(p))["word/document.xml"])
        q = "{%s}" % W_NS["w"]
        counts = {}
        for t in root.iter(q + "tbl"):
            rows = t.findall("w:tr", W_NS)
            head = ["".join(x.text or "" for x in c.iter(q + "t")) for c in rows[0].findall("w:tc", W_NS)]
            if head[:2] in (["ID", "Action"], ["ID", "Type"]):
                counts[head[1]] = len(rows) - 1
        self.assertEqual(counts, {"Action": 3, "Type": 2})

    def test_nothing_open_keeps_the_empty_state(self):
        p = copy.deepcopy(published())
        for k in ("actions", "raid"):
            for r in p["data"][k]:
                r["status"] = "Closed"
        data = docx_build.build(p)
        self.assertIn(docx_build.NONE, every_text(data))
        self.assertFalse([b for b in blocks(data) if b.get("kind") == "table" and "Action" in str(b)[:300]])


if __name__ == "__main__":
    unittest.main()
