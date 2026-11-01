"""#39: publish one HTML report, Local, boxed layout (src/clark/publish.py). Rules: Done-when on the planning repo #39, spec-39.

Run: python3 dev/run_tests.py test_publish
One fictional project, PUB (tests/fixtures/publish-plant.json, loaded by tests/_publish_fixture.py), has rows that must
reach the file and rows that must not. A dropped row is searched for in the file's bytes as typed, HTML-escaped,
JSON-escaped and lower-cased, never by a field name (the page's own code says "internal_note"). Most tests need no database
and no browser. The browser tests (Test C) open the finished file from file:// with no server at all, and are required: they
fail, never skip, without Chrome.
The database tests use a real clark store (src/clark/schema.sql) with the plant put in by raw SQL (_publish_fixture.build_db);
publishing logs through Store.log_publication, and Store.publish_inputs does the reading.
"""
import ast
import base64
import errno
import hashlib
import http.server
import json
import re
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from _paths import ROOT, SRC, TOOLS

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402

import _publish_fixture as fx  # noqa: E402
from clark import page, platform, publish, store as store_module  # noqa: E402
from clark.store import open_store  # noqa: E402
from clark.publish import PublishError  # noqa: E402
from clark.server import csp_hashes  # noqa: E402
from _growth import assert_growth  # noqa: E402
from test_server import _Pipe, chrome, wait as _wait  # noqa: E402  (the #33 browser harness, shared)


def _icon_href(name, mime):
    return f"data:{mime};base64," + base64.b64encode((ROOT / "src" / "clark" / "page" / "assets" / name).read_bytes()).decode("ascii")


ICON_HREF = _icon_href("clark-icon.svg", "image/svg+xml")       # clark's own pinned pictures (#73)
ICON_LINK = f'<link rel="icon" type="image/svg+xml" href="{ICON_HREF}">'
TOUCH_LINK = f'<link rel="apple-touch-icon" type="image/png" href="{_icon_href("clark-icon-180.png", "image/png")}">'


def wait(check, seconds=30):
    """The harness's wait with a longer default (30 s, not 15): one browser test failed once under heavy load with five solo
    runs passing, and a slow machine should be slow, not red (#39 review LOW)."""
    return _wait(check, seconds)

EMPTY_BRANDING = tempfile.mkdtemp(prefix="clark-no-brand-")     # so a brand on this laptop never changes a test


def tearDownModule():
    Path(EMPTY_BRANDING).rmdir()


def made(mutate=None, branding=EMPTY_BRANDING):
    """(plant, published, file text) for the plant as it is, or after `mutate(plant)`."""
    plant = fx.load()
    if mutate:
        mutate(plant)
    pub = publish.select(fx.inputs(plant))
    text = publish.render(pub, page.page_html(branding), plant["as_at"], pub["data"]["project"]["name"])
    return plant, pub, text


def block(text):
    """The parsed clark-data block of a file."""
    m = re.search(r'<script type="application/json" id="clark-data">(.*?)</script>', text, re.S)
    return json.loads(m.group(1))


class Plant(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plant, cls.pub, cls.text = made()

    def assertAbsent(self, *keys):
        for key in keys:
            marker = self.plant["markers"][key]
            for spelling in fx.spellings(marker) + [marker.split()[0]]:
                self.assertNotIn(spelling, self.text, f"{key}: {spelling!r} is in the file")
            self.assertNotIn(marker.lower(), self.text.lower(), key)
            if re.fullmatch(r"PUB-[A-Z0-9-]+", key):
                self.assertNotIn(key, self.text, f"the id {key} is in the file")


class Dropped(Plant):
    def test_flag_off_rows_absent_from_bytes(self):
        self.assertAbsent("PUB-A-010", "PUB-002", "PUB-D-002", "PUB-M-003", "PUB-U-002")

    def test_report_hidden_rows_absent(self):
        self.assertAbsent("PUB-A-011", "PUB-M-004")

    def test_sensitive_and_any_exclude_label_rows_absent(self):
        # Sensitive; a label whose behaviour is exclude (Commercial); a label whose default choice is exclude (Embargoed);
        # and the same name in capitals.
        self.assertAbsent("PUB-A-012", "PUB-A-013", "PUB-A-014", "PUB-A-015", "PUB-U-003")

        def customer_excludes(plant):
            plant["label_rules"][-1]["behaviour"] = "exclude"
        _, pub, text = made(customer_excludes)
        self.assertEqual([a["id"] for a in pub["data"]["actions"]], ["PUB-A-002"], "a rule added later drops its rows too")
        self.assertNotIn("ZQ-KEEP-ACTION-1", text)

        def no_rules(plant):
            plant["label_rules"] = []
        _, pub, _ = made(no_rules)
        ids = [a["id"] for a in pub["data"]["actions"]]
        self.assertNotIn("PUB-A-012", ids, "Sensitive is dropped even if the database has no rule for it")
        self.assertNotIn("PUB-A-015", ids, "and whatever its capitals")
        self.assertIn("PUB-A-013", ids, "a label with no exclude rule drops nothing")

    def test_archived_absent_even_if_data_for_sent_it(self):
        self.assertEqual(self.plant["data"]["actions"][-1]["archived"], 1, "the plant sends the archived row")
        self.assertAbsent("PUB-A-016")

    def test_internal_note_movement_source_never_copied(self):
        self.assertAbsent("internal_note", "source", "response_action", "reasoning", "options", "workstream_lead", "workstream_keywords",
                          "workstream_aliases", "comment", "change_log_old", "change_log_note")
        for m in self.pub["data"]["milestones"]:
            self.assertFalse({"internal_note", "movement", "source", "client_visible", "archived", "state_set"} & set(m))

    def test_project_folders_absent(self):
        self.assertAbsent("publish_local", "publish_client")

    def test_hidden_section_body_absent(self):
        self.assertAbsent("hidden_section_body", "hidden_section_title")
        self.assertNotIn("s-commercial", [s["id"] for s in self.pub["sections"]])

    def test_a_pair_of_any_two_types_keeps_its_row_in_the_file(self):
        def pair(plant):
            by = {x["id"]: x for x in plant["sections"]}
            by["s-glance"]["beside"] = 1                                  # glance beside use cases: neither is text
            by["s-raid"]["beside"] = 1                                    # raid beside actions
        _, pub, text = made(pair)
        flags = {x["id"]: x["beside"] for x in pub["sections"]}
        self.assertEqual((flags["s-glance"], flags["s-usecases"], flags["s-raid"], flags["s-actions"]), (1, 0, 1, 0))
        self.assertEqual({x["id"]: x["beside"] for x in block(text)["sections"]}, flags)

    def test_a_hidden_half_never_pairs_its_partner_with_a_neighbour(self):
        def hidden_half(plant):
            by = {x["id"]: x for x in plant["sections"]}
            by["s-notes"]["beside"] = 1                                   # notes beside the hidden commercial section
            by["s-commercial"]["beside"] = 1                              # a stray flag on the hidden half: it must not reach the file
        _, pub, text = made(hidden_half)
        flags = {x["id"]: x["beside"] for x in pub["sections"]}
        self.assertEqual((flags["s-notes"], flags["s-raid"]), (0, 0))      # notes alone; raid is not pulled in beside notes
        self.assertNotIn("s-commercial", flags)
        self.assertNotIn("ZQ-HIDDEN-SECTION-TITLE", text)

    def test_a_hidden_second_half_leaves_the_first_alone_and_the_next_section_free(self):
        def hidden_second(plant):
            by = {x["id"]: x for x in plant["sections"]}
            by["s-milestones"]["beside"] = 1
            by["s-notes"]["hidden"] = 1                                   # the partner of milestones
            by["s-commercial"]["hidden"] = 0
        _, pub, _ = made(hidden_second)
        flags = {x["id"]: x["beside"] for x in pub["sections"]}
        self.assertEqual(flags["s-milestones"], 0)
        self.assertEqual(sum(flags.values()), 0)

    def test_hidden_kind_drops_rows_and_tab(self):
        def hide(*types):
            def go(plant):
                for s in plant["sections"]:
                    s["hidden"] = 1 if s["type"] in types else s["hidden"]
            return go
        _, pub, text = made(hide("actions"))
        self.assertEqual((pub["data"]["actions"], pub["tabs"]), ([], ["dashboard", "work", "milestones", "usecases"]),
                         "raid and decisions still need the Work items tab")
        self.assertNotIn("ZQ-KEEP-ACTION-1", text)
        self.assertNotIn("PUB-A-001", text, "nor its id, in a link or a label")
        self.assertEqual((pub["data"]["links"], pub["data"]["labels"]), ([], {}))
        _, pub, text = made(hide("actions", "raid", "decisions"))
        self.assertEqual(pub["tabs"], ["dashboard", "milestones", "usecases"])
        self.assertNotIn("ZQ-KEEP-RISK-1", text)
        self.assertNotIn("ZQ-KEEP-DECISION-1", text)
        _, pub, text = made(hide("milestones"))
        self.assertEqual((pub["data"]["milestones"], pub["tabs"]), ([], ["dashboard", "work", "usecases"]))
        self.assertNotIn("ZQ-KEEP-MILESTONE-1", text)
        self.assertIsNone(next(a for a in pub["data"]["actions"] if a["id"] == "PUB-A-001")["milestone"])
        _, pub, text = made(hide("usecases"))
        self.assertEqual(pub["data"]["use_cases"], [])
        self.assertNotIn("ZQ-KEEP-USECASE-1", text)
        self.assertNotIn("usecases", pub["tabs"])
        _, pub, _ = made(hide("current"))
        self.assertEqual(pub["data"]["project"]["current_state"], "", "a hidden Current state section is dropped with its text")

    def test_every_marker_absent_in_four_spellings(self):
        for key in self.plant["markers"]:
            self.assertAbsent(key)
        for dropped in self.plant["dropped"]:
            self.assertNotIn(dropped, self.text, dropped)

    def test_no_forbidden_keys_and_only_kept_ids(self):
        payload = block(self.text)
        allowed = {t: set(f) for t, f in publish.PUBLISH_FIELDS.items()}
        allowed["milestones"] |= {"state", "state_word", "slip_days", "original_date"}
        forbidden = {"internal_note", "movement", "source", "client_visible", "archived", "updated_at", "publish_local",
                     "publish_client", "active", "lead", "keywords", "aliases", "comments", "applies", "change_log",
                     "item_events", "publications", "saved_views", "source_folders", "state_set", "reasoning", "options",
                     "response_action"}
        ids = set()
        for table, rows in payload["data"].items():
            if table == "project":
                self.assertLessEqual(set(rows), allowed["projects"])
            elif table == "labels":
                ids |= set(rows)
            elif table == "use_case_pages":                  # ids only, and only of rows already in the file (test_publish_usecases)
                for row in rows:
                    self.assertEqual(set(row), {"id", "next_steps", "milestones"})
            else:
                for row in rows:
                    self.assertLessEqual(set(row), allowed.get(table, set()), f"{table}: {sorted(set(row))}")
                    ids |= {row[k] for k in ("id", "from_item", "to_item", "milestone", "use_case", "replaces")
                            if row.get(k)}

        def keys(node):
            if isinstance(node, dict):
                for k, v in node.items():
                    yield k
                    yield from keys(v)
            elif isinstance(node, list):
                for v in node:
                    yield from keys(v)
        self.assertEqual(forbidden & {k for k in keys(payload) if k not in payload["data"].get("labels", {})}, set())
        self.assertLessEqual(ids, set(self.plant["kept"]), "an id that isn't kept is in the file")
        self.assertEqual(ids, set(self.plant["kept"]), "and every kept id is")

    def test_links_labels_workstreams_follow_kept_rows(self):
        d = self.pub["data"]
        self.assertEqual(d["links"], [{"from_item": "PUB-A-001", "to_item": "PUB-A-002", "kind": "blocks"}])
        self.assertEqual(d["labels"], {"PUB-A-001": ["Customer"]})
        self.assertEqual([w["name"] for w in d["workstreams"]], ["Delivery"], "Ghost is used only by dropped rows")
        self.assertEqual(set(d["workstreams"][0]), {"id", "name", "status"})
        self.assertAbsent("PUB-W-002")

    def test_dangling_references_become_null(self):
        d = self.pub["data"]
        a1, a2 = (next(a for a in d["actions"] if a["id"] == i) for i in ("PUB-A-001", "PUB-A-002"))
        self.assertEqual((a1["milestone"], a1["use_case"]), ("PUB-M-001", "PUB-U-001"), "a kept target stays")
        self.assertEqual((a2["milestone"], a2["use_case"]), (None, None), "a hidden milestone and a flag-off use case")
        self.assertIsNone(next(x for x in d["decisions"] if x["id"] == "PUB-D-003")["replaces"])

    def test_counts_use_kept_rows_only(self):
        d = self.pub["data"]
        self.assertEqual([len(d[k]) for k in ("actions", "raid", "decisions", "milestones", "use_cases")], [2, 1, 2, 2, 1])
        got = block(self.text)["data"]
        self.assertEqual([len(got[k]) for k in ("actions", "raid", "decisions", "milestones", "use_cases")], [2, 1, 2, 2, 1])

    def test_kept_rows_present(self):                     # the controls: the file isn't empty, so absence means something
        for key, marker in self.plant["kept_markers"].items():
            self.assertIn(marker, self.text, key)
        for kept in self.plant["kept"]:
            self.assertIn(kept, self.text, kept)
        self.assertEqual([s["type"] for s in self.pub["sections"]],
                         ["current", "glance", "usecases", "milestones", "text", "raid", "actions", "decisions"])

    def test_json_block_cannot_close_or_leak(self):
        def hostile(plant):
            plant["data"]["actions"][0]["client_message"] = "</script><script>zq=1</script><!--   & <b>"
        _, _, text = made(hostile)
        m = re.search(r'<script type="application/json" id="clark-data">(.*?)</script>', text, re.S)
        self.assertEqual(len(csp_hashes(text)["script"]), 1, "the data can't start a script")
        self.assertNotRegex(m.group(1), r"[<>&  ]", "nothing in the block can be read as markup")
        self.assertIn("</script><script>zq=1</script><!--   & <b>", block(text)["data"]["actions"][0]["client_message"],
                      "and it still reads back exactly")
        self.assertEqual(block(text)["data"]["project"]["name"], 'Bridge & "Harbour" <Programme>')

    def test_rich_text_is_cleaned(self):
        current = self.pub["data"]["project"]["current_state"]
        for bad in ("<script", "window.zq", "<img", "x.invalid", "onclick", "javascript:", "<iframe", "style="):
            self.assertNotIn(bad, current)
        self.assertIn("ZQ-KEEP-CURRENT", current)
        self.assertIn('<a href="https://example.org/ok" rel="noopener noreferrer">good link</a>', current)
        self.assertIn("<a rel=", current, "a link that isn't allowed keeps its words and loses its address")
        self.assertEqual(self.pub["data"]["use_cases"][0]["standing"], "<p>ZQ-KEEP-STANDING</p>")
        body = next(s["body"] for s in self.pub["sections"] if s["type"] == "text")
        self.assertIn("ZQ-KEEP-TEXT-SECTION", body)
        self.assertNotIn("x.invalid", body)
        self.assertIn('<img src="data:image/png;base64,iVBORw0KGgo=" alt="dot">', body, "an embedded image stays")

    def test_clean_html_cases(self):
        clean = publish.clean_html
        self.assertEqual(clean(""), "")
        self.assertEqual(clean(None), "")
        self.assertEqual(clean("<p>a <b>b</b></p>"), "<p>a <b>b</b></p>")
        self.assertEqual(clean("<p>one<b>two"), "<p>one<b>two</b></p>", "an open tag is closed")
        self.assertEqual(clean("a</b>b"), "ab", "a stray end tag goes")
        self.assertEqual(clean("<SCRIPT>zq()</SCRIPT>x"), "x")
        self.assertEqual(clean("<script>a<script>b</script>c</script>d"), "cd", "a script ends at its first end tag, as in a browser; "
                         "what follows is text, escaped")
        self.assertEqual(clean("<svg><script>a</script><circle/></svg>x"), "x")
        self.assertEqual(clean("<form action=x><input name=a>say</form>y"), "y")
        self.assertEqual(clean("<link rel=stylesheet href=https://x.invalid/a.css><meta http-equiv=refresh>t"), "t")
        self.assertEqual(clean("<p style='color:red' onclick='x()' class=c>t</p>"), "<p>t</p>")
        self.assertEqual(clean("&lt;script&gt;alert(1)&lt;/script&gt;"), "&lt;script&gt;alert(1)&lt;/script&gt;",
                         "text that looks like markup stays text")
        for href in ("javascript:zq()", " JaVaScRiPt:zq()", "jav&#x09;ascript:zq()", "data:text/html,x", "//x.invalid/a",
                     "/relative", "http://x.invalid/a", "vbscript:x", ""):
            self.assertEqual(clean(f'<a href="{href}">t</a>'), '<a rel="noopener noreferrer">t</a>', href)
        for href in ("https://example.org/a?b=1&c=2", "mailto:a@example.org", "#next"):
            self.assertIn(f'href="{href.replace("&", "&amp;")}"', clean(f'<a href="{href}">t</a>'))
        self.assertEqual(clean('<img src="https://x.invalid/a.png">t'), "t")
        self.assertEqual(clean('<img src="data:image/svg+xml;base64,AAAA">t'), "t", "svg can carry script")
        self.assertEqual(clean('<img src="data:text/html;base64,AAAA">t'), "t")
        self.assertEqual(clean('<img srcset="https://x.invalid/a.png 2x" src="data:image/gif;base64,R0lG">'),
                         '<img src="data:image/gif;base64,R0lG">')
        self.assertEqual(clean('<td colspan="2" rowspan="x">t</td>'), '<td colspan="2">t</td>')


class TheFile(Plant):
    def test_no_outside_address_in_attributes_css_or_srcs(self):
        self.assertEqual(publish.outside_addresses(self.text), [])        # the rules live in publish.py, so #43 runs them on the copy

    def test_clarks_icon_links_are_not_outside_addresses_but_other_links_are(self):
        icon, touch = ICON_LINK, TOUCH_LINK
        self.assertEqual(publish.outside_addresses(f"<head>{icon}{touch}</head>"), [])
        for bad in ('<link rel="icon" href="https://x.invalid/i.png">', '<link rel="icon" href="data:text/html;base64,AAAA">',
                    '<link rel="stylesheet" href="data:image/png;base64,AAAA">', '<link rel="icon" href="i.png">',
                    '<link rel="preload" href="data:image/png;base64,AAAA">'):
            self.assertIn("a <link> tag", publish.outside_addresses(bad), bad)

    def test_a_genuine_pages_three_icon_links_are_accepted(self):
        links = "".join(re.findall(r"<link\b[^>]*>", page.PAGE.read_text(encoding="utf-8")))
        self.assertEqual(len(re.findall(r"<link\b", links)), 3)
        self.assertEqual(publish.outside_addresses(f"<head>{links}</head>"), [])

    def test_a_genuine_link_written_any_other_way_is_refused(self):
        # was: reversed order, single quotes and no space were accepted; the scan now takes only the exact string the build writes
        for bad in (f'<link href="{ICON_HREF}" type="image/svg+xml" rel="icon">', f"<link href='{ICON_HREF}'rel='icon'>",
                    f"<link rel='icon' type='image/svg+xml' href='{ICON_HREF}'>", ICON_LINK.replace("<link", "<LINK"),
                    ICON_LINK.replace("rel=", "REL="), ICON_LINK.replace(">", " >"), ICON_LINK.replace(">", "/>"),
                    ICON_LINK.replace(">", " />"), f'<link rel="icon" href="{ICON_HREF}">'):
            self.assertIn("a <link> tag", publish.outside_addresses(f"<head>{bad}</head>"), bad[:60])
        self.assertEqual(publish.outside_addresses(f"<head>{ICON_LINK}</head>"), [])

    def test_data_in_the_spacing_of_a_genuine_icon_link_is_refused(self):
        bits = "".join(" " if b == "0" else "\t" for b in format(int.from_bytes(b"ZQ-SECRET-ROW-TEXT", "big"), "b"))
        for gap in (bits, " " * 1_000_000, "\u2000" * 300_000, "\u00a0", "\u3000", "\u200a", "\t", "\n", "\x0c", "  ", "/", " / ", "//"):
            for bad in (ICON_LINK.replace("<link rel", "<link" + gap + "rel"), ICON_LINK.replace('" type', '"' + gap + "type"),
                        ICON_LINK.replace('" href', '"' + gap + "href"), ICON_LINK.replace("rel=", "rel" + gap + "="),
                        ICON_LINK.replace("=\"icon", "=" + gap + '"icon'), ICON_LINK.replace('">', '"' + gap + ">")):
                self.assertIn("a <link> tag", publish.outside_addresses(f"<head>{bad}</head>"), repr(gap[:20]))
        self.assertIn("a <link> tag", publish.outside_addresses(ICON_LINK.replace("<link", "<link/", 1)))
        self.assertIn("a <link> tag", publish.outside_addresses(ICON_LINK.replace("<link ", "<link\u2000", 1)))

    def test_a_genuine_icon_link_is_accepted_wherever_it_stands_and_any_other_link_is_refused_there(self):
        # the rule asserted: every <link in the text is checked, wherever it is (comment, script, template, textarea,
        # noscript; a CDATA section is refused whole since #112 H1); the exact genuine string passes anywhere (it carries no payload), anything else is refused anywhere
        bad = '<link rel="stylesheet" href="data:text/css;base64,QUJD">'
        for wrap in ("<!-- {} -->", "<script>var a = '{}';</script>", "<template>{}</template>",
                     "<textarea>{}</textarea>", "<noscript>{}</noscript>"):
            self.assertEqual(publish.outside_addresses(wrap.format(ICON_LINK)), [], wrap)
            self.assertIn("a <link> tag", publish.outside_addresses(wrap.format(bad)), wrap)
            self.assertIn("a <link> tag", publish.outside_addresses(wrap.format(ICON_LINK.replace(">", " >"))), wrap)
            self.assertIn("a <link> tag", publish.outside_addresses(wrap.format(ICON_LINK.replace("<link", "<link\t"))), wrap)

    def test_a_large_hidden_payload_in_an_icon_link_is_refused(self):
        blob = base64.b64encode(b"\x00" * 300_000).decode("ascii")
        leak = base64.b64encode(b"ZQ-SECRET-ROW-TEXT").decode("ascii")
        for href in (f"data:image/png;base64,{blob}", f"data:image/png;base64,{leak}", f"data:image/svg+xml;base64,{leak}"):
            self.assertIn("a <link> tag", publish.outside_addresses(f'<link rel="icon" href="{href}">'), href[:40])

    def test_an_icon_link_that_repeats_an_attribute_is_refused(self):
        for bad in ('<link rel="stylesheet" href="data:text/css;base64,QUJD" rel="icon" href="data:image/png;base64,AAAA">',
                    f'<link rel="stylesheet" REL="icon" href="{ICON_HREF}">',
                    f'<link rel="icon" href="{ICON_HREF}" href="data:text/css;base64,QUJD">',
                    f"<link rel='stylesheet'rel='icon' href='{ICON_HREF}'>"):
            self.assertIn("a <link> tag", publish.outside_addresses(bad), bad[:60])

    def test_an_icon_link_with_an_extra_attribute_is_refused(self):
        for extra in ('onload="alert(1)"', "onload='alert(1)'", 'ONLOAD="x()"', 'crossorigin="anonymous"', 'media="all"', "disabled"):
            for bad in (f'<link rel="icon" href="{ICON_HREF}" {extra}>', f'<link {extra} rel="icon" href="{ICON_HREF}">'):
                self.assertIn("a <link> tag", publish.outside_addresses(bad), bad[:80])

    def test_an_icon_link_that_is_not_one_of_the_pinned_pictures_is_refused(self):
        png_not_pinned = "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\nnot clark's icon").decode("ascii")
        svg_not_pinned = "data:image/svg+xml;base64," + base64.b64encode(b"<svg onload='alert(1)'/>").decode("ascii")
        for href in (png_not_pinned, svg_not_pinned, "data:image/png;base64,AAAA", ICON_HREF + "AAAA", ICON_HREF.replace("base64,", "base64, ")):
            self.assertIn("a <link> tag", publish.outside_addresses(f'<link rel="icon" href="{href}">'), href[:40])

    def test_a_fourth_icon_link_is_refused(self):
        three = "".join(re.findall(r"<link\b[^>]*>", page.PAGE.read_text(encoding="utf-8")))
        self.assertEqual(publish.outside_addresses(f"<head>{three}</head>"), [])
        self.assertIn("a <link> tag", publish.outside_addresses(f"<head>{three}{ICON_LINK}</head>"))

    def test_the_same_icon_link_twice_or_three_times_is_refused_but_one_alone_is_fine(self):
        for link in (ICON_LINK, TOUCH_LINK):
            self.assertEqual(publish.outside_addresses(f"<head>{link}</head>"), [])
            for n in (2, 3):
                self.assertIn("a <link> tag", publish.outside_addresses(f"<head>{link * n}</head>"), n)

    def test_free_text_in_type_or_sizes_of_an_icon_link_is_refused(self):
        for attr in ('type="ZQ-SECRET-ROW-TEXT"', 'type="url(//x)"', 'type="image/png"', 'type="image/svg+xml;x"', 'type=""',
                     'sizes="ZQ-SECRET-ROW-TEXT"', 'sizes="32x32"', 'sizes=""', f'sizes="{"x" * 1_000_000}"', 'type="image/svg+xml\nZQ"',
                     'sizes="any\nZQ-SECRET-ROW-TEXT"'):
            bad = f'<link rel="icon" href="{ICON_HREF}" {attr}>'
            self.assertIn("a <link> tag", publish.outside_addresses(bad), attr[:40])
        self.assertEqual(publish.outside_addresses(ICON_LINK), [])
        self.assertIn("a <link> tag", publish.outside_addresses(f'<link rel="icon" href="{ICON_HREF}">'), "type is part of the tag")

    def test_an_icon_links_type_href_mime_and_rel_must_pair_up_with_its_picture(self):
        png = _icon_href("clark-icon-32.png", "image/png")
        touch = _icon_href("clark-icon-180.png", "image/png")
        for bad in (f'<link rel="icon" type="image/png" href="{ICON_HREF}">',                    # svg picture, png type
                    f'<link rel="icon" type="image/svg+xml" href="{png}">',                      # png picture, svg type
                    f'<link rel="icon" href="data:image/png;base64,{ICON_HREF.split(",")[1]}">',       # svg bytes under a png mime
                    f'<link rel="icon" href="data:image/svg+xml;base64,{png.split(",")[1]}">',         # png bytes under an svg mime
                    f'<link rel="apple-touch-icon" href="{ICON_HREF}">', f'<link rel="icon" href="{touch}">',
                    f'<link rel="apple-touch-icon" href="{png}">'):
            self.assertIn("a <link> tag", publish.outside_addresses(bad), bad[:70])

    def test_an_icon_links_base64_must_be_in_its_one_canonical_spelling(self):
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
        for name, mime, rel in (("clark-icon.svg", "image/svg+xml", "icon"), ("clark-icon-32.png", "image/png", "icon"),
                                ("clark-icon-180.png", "image/png", "apple-touch-icon")):
            payload = _icon_href(name, mime).split(",", 1)[1]
            body = payload.rstrip("=")
            if body == payload:
                continue                                    # no padding, so no spare bits to flip
            siblings = [c for c in alphabet if c != body[-1] and base64.b64decode(body[:-1] + c + "=" * (len(payload) - len(body)))
                        == base64.b64decode(payload)]
            self.assertTrue(siblings, name)
            self.assertEqual(publish.outside_addresses(page.icon_link(rel, mime, payload)), [], name)
            for c in siblings:
                bad = page.icon_link(rel, mime, body[:-1] + c + "=" * (len(payload) - len(body)))
                self.assertIn("a <link> tag", publish.outside_addresses(bad), name)

    def test_other_ways_of_writing_a_link_do_not_get_past_the_scan(self):
        for bad in ('<LINK rel="stylesheet" href="data:text/css;base64,QUJD">', '<link rel=icon href=data:image/png;base64,AAAA>',
                    '<link rel="icon" href="data:image/png;base64,AAAA', f'<link rel="icon" href="{ICON_HREF}"',
                    f'<link rel="ICON" href="{ICON_HREF}">', f'<link rel="icon" href="DATA:image/png;base64,AAAA">',
                    f'<link rel="icon shortcut" href="{ICON_HREF}">', f'<link rel="icon" href="&#100;ata:{ICON_HREF[5:]}">'):
            self.assertIn("a <link> tag", publish.outside_addresses(bad), bad[:60])

    def test_an_outside_icon_and_a_data_stylesheet_or_preload_are_refused(self):
        for bad in ('<link rel="icon" href="https://x.invalid/i.png">', '<link rel="icon" href="//x.invalid/i.png">',
                    '<link rel="apple-touch-icon" href="http://x.invalid/i.png" type="image/png">',
                    '<link rel="stylesheet" href="data:text/css;base64,QUJD">', '<link rel="preload" href="data:image/png;base64,AAAA" as="image">',
                    f'<link rel="stylesheet" href="{ICON_HREF}">', f'<link rel="preload" href="{ICON_HREF}">'):
            self.assertIn("a <link> tag", publish.outside_addresses(bad), bad[:60])

    def test_the_address_scan_finds_each_kind(self):
        for bad in ('<link rel="stylesheet" href="a.css">', '<script src="a.js"></script>', '<img src="https://x.invalid/a.png">',
                    '<meta http-equiv="refresh" content="0">', "<style>@import 'a.css';</style>", "<style>a{background:url(a.png)}</style>",
                    '<a href="//x.invalid/">x</a>', "fonts.googleapis.com"):
            self.assertTrue(publish.outside_addresses("<body>" + bad + "</body>"), bad)
        self.assertEqual(publish.outside_addresses('<style>a{background:url(data:image/png;base64,AA)}</style><a href="#x">x</a>'), [])
        # the data block is left out only where the builder puts it, straight before the last </body>
        self.assertEqual(publish.outside_addresses('<body><script type="application/json" id="clark-data">{"u":"https://x.invalid"}</script>\n</body>'), [])
        self.assertTrue(publish.outside_addresses('<script type="application/json" id="clark-data"><link rel="stylesheet" href="a.css"></script>'),
                        "the same opener anywhere else is page markup")

    def test_a_fake_data_block_hides_nothing_from_the_scan(self):
        real = publish.data_block({"data": {"u": "x"}, "sections": [], "tabs": []}, "2026-10-28")
        opener = '<script type="application/json" id="clark-data">'
        tail = f"{real}\n</body></html>"
        self.assertEqual(publish.outside_addresses(f"<body>{tail}"), [])
        for bad, what in (('<link rel="stylesheet" href="a.css">', "a <link> tag"),
                          ('<script src="a.js"></script>', "a script loaded by address"),
                          ('<img src="https://x.invalid/a.png">', "an attribute that names an outside address")):
            for fake in (f"{opener}{bad}</script>", f"{opener}{{}}</script>{bad}", f"{opener}x{bad}", f"{opener}{bad}"):
                self.assertIn(what, publish.outside_addresses(f"<body>{fake}{tail}"), fake)       # a fake opener before the real block
                self.assertIn(what, publish.outside_addresses(f"<body>{fake}</body>{tail}"), fake)
                self.assertIn(what, publish.outside_addresses(f"<body>{tail}{fake}"), fake)       # and one after it
            self.assertIn(what, publish.outside_addresses(f"<body>{opener}x</script>\n{bad}\n</body>"), "a fake that sits at the end")
        self.assertIn("a <link> tag", publish.outside_addresses(f'<body>{opener}<link rel="stylesheet" href="a.css">'
                                                                f'</script>\n</body>'), "not even in the last place")
        two = f"<body>{real}\n{real}\n</body>"
        self.assertEqual(publish.without_data_block(two), f"<body>{real}\n</body>", "only the one before the last </body> is cut")

    def test_a_hostile_tokens_css_can_neither_end_the_style_nor_hide_a_link(self):
        opener = '<script type="application/json" id="clark-data">'
        css = f':root {{ --x: 1; }}</STYLE>{opener}</script><link rel="stylesheet" href="https://x.invalid/a.css"><script src="b.js"></script>'
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        (Path(tmp.name) / "tokens.css").write_text(css, encoding="utf-8")
        _, _, text = made(branding=tmp.name)
        self.assertEqual(len(re.findall(r"(?i)<style\b", text)), 2, "the brand's text stayed inside its own style element")
        self.assertEqual(len(re.findall(r"(?i)<script\b", text)), 2, "and gave the page no script of its own")
        self.assertEqual(len(csp_hashes(text)["script"]), 1, "so the policy covers only the page's own script")
        self.assertIn("a <link> tag", publish.outside_addresses(text), "and what it names is still seen by the scan")

    def test_the_scan_reads_style_text_in_any_letter_case(self):
        for bad in ("<STYLE>@IMPORT 'a.css';</STYLE>", "<Style>a{background:URL(a.png)}</sTyLe >", "<style>@Import url(a.css)</style>"):
            self.assertTrue(publish.outside_addresses("<body>" + bad + "</body>"), bad)
        self.assertEqual(publish.outside_addresses("<STYLE>a{background:URL(DATA:image/png;base64,AA)}</STYLE>"), [])

    def test_the_style_scan_is_linear_on_endless_end_tag_lookalikes(self):
        # #106: the old lazy regex took 3.2 s on 40,000 of these (and minutes at the 5 MB limit). The old check was a wall-clock limit (1 s
        # for 40,000); it is now the growth from 40,000 to 160,000 repeats in CPU time (growth_ratio, as in test_publish_public).
        for name, make in (("end tags with no >", lambda n: "<style>" + "</style " * n), ("starts with no >", lambda n: "<style " * n),
                           ("starts and ends", lambda n: "<style>" + "</style x>" * n), ("starts alone", lambda n: "<style>" * n)):
            assert_growth(self, lambda size, make=make: publish.outside_addresses(make(size)), 40000, name)

    def test_style_dash_x_is_not_an_end_tag(self):
        self.assertEqual(publish.style_texts("<style>a{}</style-x>b{}</style>"), ["a{}</style-x>b{}"])
        self.assertIn("a stylesheet that imports another", publish.outside_addresses("<style>a{}</style-x>@import 'a.css';</style>"))
        self.assertEqual(publish.style_texts("<style-x>a{}</style>"), [], "nor is <style-x> a start tag")

    def test_the_style_end_tag_is_read_as_a_browser_reads_it(self):
        for end in ("</style>", "</style >", "</style/>", "</style\t>", "</style\n>", "</style\r\n>", "</style\f>", "</STYLE\r\n  x='1'>"):
            self.assertEqual(publish.style_texts(f"<style>a{{}}{end}b{{}}"), ["a{}"], repr(end))
        self.assertIn("a stylesheet that imports another", publish.outside_addresses("<style>@import 'a.css';</style\r\n>"))
        self.assertEqual(publish.style_texts("<style>a{}</style\x00>b{}</style>"), ["a{}</style\x00>b{}"], "a NUL makes it another tag")
        self.assertEqual(publish.style_texts("<style>a{}</style"), ["a{}</style"], "no end tag: the style runs to the end")
        self.assertIn("a stylesheet that imports another", publish.outside_addresses("<style>@import 'a.css';"))
        self.assertEqual(publish.style_texts("<style>a{}</style>x<style>b{}</style>"), ["a{}", "b{}"])

    def test_long_s_and_kelvin_sign_are_not_s_and_k_in_a_tag(self):
        # re.IGNORECASE on a str pattern lets U+017F match s and U+212A match k; a browser does not, so the scan is ASCII only.
        self.assertEqual(publish.style_texts("<\u017ftyle>@import 'a.css';</\u017ftyle>"), [])
        self.assertEqual(publish.outside_addresses("<\u017ftyle>@import 'a.css';</\u017ftyle>"), [])
        self.assertEqual(publish.style_texts("<style>a{}</\u017ftyle>@import 'a.css';</style>"), ["a{}</\u017ftyle>@import 'a.css';"])
        self.assertIn("a stylesheet that imports another", publish.outside_addresses("<style>a{}</\u017ftyle>@import 'a.css';</style>"))
        self.assertEqual(publish.outside_addresses(ICON_LINK.replace("<link", "<lin\u212a", 1)), [], "not a link tag at all")
        self.assertIn("a <link> tag", publish.outside_addresses("<LINK rel=stylesheet href=a.css>"))

    def test_font_or_import_url_in_brand_is_refused(self):
        def brand(css):
            tmp = tempfile.TemporaryDirectory()
            self.addCleanup(tmp.cleanup)
            (Path(tmp.name) / "tokens.css").write_text(css, encoding="utf-8")
            return tmp.name
        for css in ("@font-face { font-family: X; src: url(https://fonts.invalid/f.woff2); }",
                    '@font-face { src: url("//fonts.invalid/f.woff2") }', "@import 'https://fonts.invalid/a.css';",
                    "@IMPORT url(a.css);", ":root { --x: URL( 'f.woff2' ); }"):
            with self.assertRaisesRegex(PublishError, "embed the font in tokens.css"):
                made(branding=brand(css))
        _, _, text = made(branding=brand("@font-face { font-family: X; src: url(data:font/woff2;base64,AAAA); }"))
        self.assertIn("data:font/woff2", text, "an embedded font is fine")
        self.assertEqual(len(csp_hashes(text)["style"]), 2, "and its block is covered by the policy")

    def test_one_script_one_data_block_no_boot_token(self):
        text = self.text
        self.assertEqual(len(re.findall(r"<script\b", text)), 2)
        self.assertEqual(len(re.findall(r'<script type="application/json" id="clark-data">', text)), 1)
        self.assertEqual(len(re.findall(r"<script>", text)), 1, "the page's own script")
        self.assertNotRegex(text, r'<script[^>]*id="clark-boot"')
        self.assertNotRegex(text, r"<script[^>]*\bsrc=")
        self.assertIn('<html lang="en-GB" data-mode="view">', text)
        self.assertIn("<title>Bridge &amp; &quot;Harbour&quot; &lt;Programme&gt;</title>", text)
        self.assertEqual(text.count("<title>"), 1)
        self.assertLess(text.index('id="clark-data"'), text.rindex("</body>"))
        payload = block(text)
        self.assertEqual((payload["v"], payload["as_at"], payload["tabs"]), (1, "2026-10-28", ["dashboard", "work", "milestones", "usecases"]))
        with self.assertRaisesRegex(PublishError, "token"):
            publish.render(self.pub, page.page_html(EMPTY_BRANDING).replace("</body>", '<script type="application/json" '
                           'id="clark-boot">{}</script></body>'), "2026-10-28", "x")
        with self.assertRaisesRegex(PublishError, "changed shape"):
            publish.render(self.pub, "<html></html>", "2026-10-28", "x")

    def test_csp_meta_first_and_hashes_match_finished_bytes(self):
        text = self.text
        m = re.search(r'<meta http-equiv="Content-Security-Policy" content="([^"]*)">', text)
        self.assertEqual(text.count("Content-Security-Policy"), 1)
        self.assertEqual(text.split("<head>")[1][:22 + len(m.group(0))],
                         '<meta charset="utf-8">' + m.group(0), "straight after <meta charset>, before anything else")
        h = csp_hashes(text)
        policy = dict(d.strip().split(" ", 1) for d in m.group(1).split(";"))
        self.assertEqual(policy["script-src"].split(), h["script"])
        self.assertEqual(policy["style-src-elem"].split(), h["style"])
        self.assertEqual((len(h["script"]), len(h["style"])), (1, 1), "the page's script, and its one style block")
        self.assertEqual(publish.csp_meta(text.replace(m.group(0), "")), m.group(0), "it is what the bytes without it give")
        _, _, other = made(lambda plant: plant["data"]["actions"][0].update(client_message="changed"))
        self.assertEqual(csp_hashes(other), h, "the data block is not hashed: it is never run")
        branded = tempfile.TemporaryDirectory()
        self.addCleanup(branded.cleanup)
        (Path(branded.name) / "tokens.css").write_text(":root { --brand-navy: #123456; }", encoding="utf-8")
        _, _, text2 = made(branding=branded.name)
        self.assertIn(csp_hashes(text2)["style"][1], text2, "a local brand's block is covered too")
        self.assertEqual(re.search(r'content="([^"]*)"', text2).group(1).count("sha256-"), 3)

    def test_csp_has_no_ignored_directives(self):
        policy = re.search(r'Content-Security-Policy" content="([^"]*)"', self.text).group(1)
        names = [d.strip().split(" ")[0] for d in policy.split(";")]
        for ignored in ("frame-ancestors", "report-uri", "report-to", "sandbox"):
            self.assertNotIn(ignored, names, "a <meta> policy ignores it with a console warning")
        for open_ in ("'self'", "'unsafe-inline'", "'unsafe-eval'", "http:", "https:", "*"):
            self.assertNotIn(open_, policy.split())
        for tight in ("default-src 'none'", "connect-src 'none'", "object-src 'none'", "base-uri 'none'", "form-action 'none'"):
            self.assertIn(tight, policy)

    def test_milestone_state_words_embedded(self):
        by = {m["id"]: m for m in block(self.text)["data"]["milestones"]}
        self.assertEqual((by["PUB-M-001"]["state"], by["PUB-M-001"]["state_word"]), ("At risk", "At risk"), "the user's own state")
        self.assertEqual((by["PUB-M-002"]["state"], by["PUB-M-002"]["state_word"], by["PUB-M-002"]["slip_days"]),
                         ("Slipped", "Expected later", 14))
        self.assertEqual(by["PUB-M-001"]["state_reason"], "ZQ-KEEP-STATE-REASON", "Q4: the visible why is published")
        self.assertEqual(by["PUB-M-001"]["original_date"], "2026-10-01", "the first agreed date, from change_log")
        self.assertEqual(by["PUB-M-002"]["original_date"], "2026-12-01", "no change: the current agreed date")
        _, pub, _ = made(lambda plant: plant["data"]["milestones"][0].update(state_set=0))
        late = pub["data"]["milestones"][0]
        self.assertEqual((late["state"], late["state_word"], late["slip_days"]), ("Overdue", "Late", 13))

        def later(plant):
            plant["as_at"] = "2027-01-01"
        _, pub, text = made(later)
        self.assertEqual(pub["data"]["milestones"][1]["state_word"], "Late", "worked out as at publish, not as at opening")
        self.assertEqual(block(text)["as_at"], "2027-01-01")

        def undone(plant):
            plant["undone"] = [1]
        _, pub, _ = made(undone)
        self.assertEqual(pub["data"]["milestones"][0]["original_date"], "2026-10-15", "an undone apply doesn't count")
        self.assertNotIn("change_log", self.text)

    def test_page_html_is_current(self):
        """Both built pages (#65): page.html, which clark serves, and page-view.html, the one a published file is made from."""
        self.assertEqual(page.PAGE.read_text(encoding="utf-8"), build_page.build(),
                         "src/clark/page/page.html is out of date: run python3 dev/tools/build_page.py")
        self.assertEqual(page.VIEW_PAGE.read_text(encoding="utf-8"), build_page.build(build_page.ENTRY_VIEW),
                         "src/clark/page/page-view.html is out of date: run python3 dev/tools/build_page.py")


def make_db(testcase, mutate=None):
    tmp = tempfile.TemporaryDirectory()
    testcase.addCleanup(tmp.cleanup)
    plant = fx.load()
    if mutate:
        mutate(plant)
    return Path(tmp.name), fx.build_db(Path(tmp.name) / "clark.db", plant)


def store_of(testcase, db):
    """The real store over the plant's database file, closed when the test ends."""
    store = open_store(db, onedrive_roots=[])
    testcase.addCleanup(store.close)
    return store


class Making(unittest.TestCase):
    def setUp(self):
        self.tmp, self.db = make_db(self)
        self.store = store_of(self, self.db)
        self.out = self.tmp / "out"
        self.out.mkdir()

    def run_publish(self, **kw):
        kw.setdefault("now", "2026-10-28")
        kw.setdefault("branding", EMPTY_BRANDING)
        kw.setdefault("by_user", "Demo User")
        return publish.publish(self.store, "PUB", self.out, **kw)

    def test_the_database_gives_what_the_fixture_gives(self):
        from_db = publish.select(publish.read_inputs(self.store, "PUB", "2026-10-28"))
        self.assertEqual(from_db, publish.select(fx.inputs()))

    def test_an_archived_project_is_refused_and_nothing_is_written(self):
        with self.store.step("dashboard", "Demo User") as st:
            st.archive("projects", "PUB")
        with self.assertRaisesRegex(PublishError, "archived project can't be published.*Restore it first"):
            self.run_publish()
        self.assertEqual(list(self.out.iterdir()), [])
        self.assertEqual(self.store.con.execute("SELECT count(*) FROM publications").fetchone()[0], 0)

    def test_select_and_the_tile_figures_do_not_raise_for_an_archived_project(self):
        from clark import glance
        with self.store.step("dashboard", "Demo User") as st:
            st.archive("projects", "PUB")
        inputs = publish.read_inputs(self.store, "PUB", "2026-10-28")
        self.assertEqual(inputs["data"]["project"]["archived"], 1)
        shown = publish.select(inputs)
        self.assertEqual(shown["data"]["actions"], [])
        kept = glance.kept_rows(inputs["data"], "2026-10-28")           # as the page's tiles call it: no raise
        self.assertEqual(kept["rows"], [])

    def test_the_archived_flag_never_reaches_the_file(self):
        self.assertNotIn("archived", publish.select(publish.read_inputs(self.store, "PUB", "2026-10-28"))["data"]["project"])

    def test_a_live_project_still_publishes(self):
        self.assertTrue(Path(self.run_publish()["path"]).is_file())

    def test_name_is_safe_and_collision_needs_overwrite(self):
        self.assertEqual(publish.file_name("PUB", "2026-10-23", "2026-10-28"), "PUB-report-2026-10-23.html")
        self.assertEqual(publish.file_name("PUB", None, "2026-10-28"), "PUB-report-2026-10-28.html")
        self.assertEqual(publish.file_name("A:B", None, "2026-10-28"), "A-B-report-2026-10-28.html")
        with self.assertRaises(platform.PlatformError):
            publish.file_name("PUB", None, "2026-10-28", "/" + "x" * 300)
        first = self.run_publish()
        self.assertEqual(Path(first["path"]).name, "PUB-report-2026-10-23.html")
        with self.assertRaisesRegex(PublishError, "already in that folder"):
            self.run_publish()
        again = self.run_publish(overwrite=True)
        self.assertEqual(again["sha256"], first["sha256"], "the same data and date give the same bytes")
        self.assertEqual([p.name for p in self.out.iterdir()], ["PUB-report-2026-10-23.html"])
        with self.assertRaisesRegex(PublishError, "isn't there"):
            publish.publish(self.store, "PUB", self.tmp / "missing", by_user="Demo User", now="2026-10-28", branding=EMPTY_BRANDING)

    def test_write_is_atomic_and_hash_is_of_written_bytes(self):
        done = self.run_publish()
        body = Path(done["path"]).read_bytes()
        self.assertEqual((done["sha256"], done["bytes"]), (hashlib.sha256(body).hexdigest(), len(body)))
        self.assertEqual(body.decode("utf-8").count("\r"), 0, "no line end is changed on the way")
        self.assertEqual([p.name for p in self.out.iterdir()], ["PUB-report-2026-10-23.html"], "no temporary file is left")
        with mock.patch.object(platform, "replace_file", side_effect=OSError(errno.EIO, "disk error")):
            with self.assertRaisesRegex(PublishError, "Nothing was written"):
                self.run_publish(overwrite=True)
        self.assertEqual(Path(done["path"]).read_bytes(), body, "the old file is untouched when a replace fails")
        self.assertEqual([p.name for p in self.out.iterdir()], ["PUB-report-2026-10-23.html"])
        other = self.tmp / "other"
        other.mkdir()
        with mock.patch.object(platform, "replace_file", side_effect=OSError(errno.EIO, "disk error")):
            with self.assertRaises(PublishError):
                publish.publish(self.store, "PUB", other, by_user="Demo User", now="2026-10-28", branding=EMPTY_BRANDING)
        self.assertEqual(list(other.iterdir()), [], "nothing at all is left from a write that failed")

        def writes_something_else(dest, data, **kw):
            Path(dest).write_bytes(b"not the report")
        with mock.patch("clark.platform.write_file", writes_something_else):
            with self.assertRaisesRegex(PublishError, "not saved as it was made"):
                self.run_publish(overwrite=True)

    def test_the_size_message_says_what_to_do_next(self):
        with mock.patch.object(publish, "MAX_BYTES", 1000):
            with self.assertRaisesRegex(PublishError, "Remove or shrink the largest image or attachment, then publish again\\.$"):
                self.run_publish()

    def test_size_limit(self):
        with mock.patch.object(publish, "MAX_BYTES", 1000):
            with self.assertRaisesRegex(PublishError, "over the 0 MB limit"):
                self.run_publish()
        self.assertEqual(list(self.out.iterdir()), [])
        self.assertEqual(publish.MAX_BYTES, 5 * 1024 * 1024)
        self.assertLess(Path(self.run_publish()["path"]).stat().st_size, publish.MAX_BYTES)

    def publications(self):
        return [dict(r) for r in self.store.con.execute("SELECT * FROM publications ORDER BY seq")]

    def test_publish_logs_one_row_and_remembers_folder(self):
        self.planted_folder = self.store.read("projects", ref="PUB")["publish_local"]
        done = self.run_publish()
        rows = self.publications()
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["project"], rows[0]["local_path"], rows[0]["file_sha256"], rows[0]["by_user"],
                          rows[0]["week_ending"], rows[0]["checks"], rows[0]["word"], rows[0]["client_path"]),
                         ("PUB", done["path"], done["sha256"], "Demo User", "2026-10-23", "not needed", 0, None))
        self.assertEqual(done["seq"], rows[0]["seq"])
        self.assertEqual(set(done), {"path", "sha256", "bytes", "seq"})
        self.assertEqual(self.store.last_publish_folder("PUB"), str(self.out))
        self.assertEqual(self.store.read("projects", ref="PUB")["publish_local"], self.planted_folder,
                         "no write to the project row")
        self.assertEqual(hashlib.sha256(Path(done["path"]).read_bytes()).hexdigest(), rows[0]["file_sha256"])
        self.assertEqual(self.store.con.execute("SELECT count(*) FROM change_log WHERE tbl = 'publications'").fetchone()[0], 0)
        self.run_publish(overwrite=True)
        self.assertEqual(len(self.publications()), 2, "each publish is one row")

    def test_nothing_logged_if_write_fails(self):
        with mock.patch.object(platform, "replace_file", side_effect=OSError(errno.EIO, "disk error")):
            with self.assertRaises(PublishError):
                self.run_publish()
        self.assertEqual(self.publications(), [])
        self.assertEqual(list(self.out.iterdir()), [], "the reserved name is taken back when nothing real was written")

    def test_a_second_publish_at_once_cannot_take_the_same_name(self):
        first = self.run_publish()
        with self.assertRaisesRegex(PublishError, "already in that folder"):
            self.run_publish()
        self.assertEqual(Path(first["path"]).read_bytes()[:15], b"<!doctype html>")
        self.assertEqual(len(self.publications()), 1)

    def test_the_publish_date_must_be_a_date(self):
        for bad in ("tomorrow", "2026-13-01", "28-10-2026", "2026-10-28T10:00", "20261028", "2026-1-5"):
            with self.subTest(bad=bad), self.assertRaisesRegex(PublishError, "not a date"):
                self.run_publish(now=bad)

    def test_the_store_refuses_to_read_what_no_report_carries(self):
        fields = {t: tuple(f) for t, f in publish.PUBLISH_FIELDS.items() if t != "links"}
        for never in ("internal_note", "movement", "source", "reasoning", "options", "response_action", "publish_local"):
            table = {"internal_note": "milestones", "movement": "milestones", "source": "actions", "reasoning": "decisions",
                     "options": "decisions", "response_action": "raid", "publish_local": "projects"}[never]
            with self.subTest(never=never), self.assertRaisesRegex(store_module.Invalid, "never read for a published file"):
                self.store.publish_inputs("PUB", {**fields, table: fields[table] + (never,)})

    def test_a_publish_leaves_a_users_own_edit_of_the_folder_undoable(self):
        before = self.store.read("projects", ref="PUB")["publish_local"]
        step = self.store_step_folder("/Users/someone/Reports")
        self.run_publish()
        out = self.store.undo(step, "Demo User")
        self.assertEqual(out["skipped"], [], "a publication never touches the project row, so Undo has nothing to skip")
        self.assertEqual(self.store.read("projects", ref="PUB")["publish_local"], before)

    def store_step_folder(self, folder):
        with self.store.step("dashboard", "Demo User") as st:
            st.update("projects", "PUB", {"publish_local": folder})
        return self.store.con.execute("SELECT max(apply_id) FROM applies").fetchone()[0]

    def test_a_failed_record_after_a_good_write_says_the_file_was_saved(self):
        with mock.patch.object(self.store, "log_publication", side_effect=store_module.Invalid("clark's data is busy")):
            with self.assertRaisesRegex(PublishError, r"was saved in .*could not record it.*Publish again to record it"):
                self.run_publish()
        self.assertEqual(len(list(self.out.iterdir())), 1, "the good file is still there")

    def test_a_failed_record_never_shows_the_raw_exception_text(self):
        raw = "UNIQUE constraint failed: publications.seq [Errno 5] ZQ-RAW-TEXT"
        with mock.patch.object(self.store, "log_publication", side_effect=RuntimeError(raw)):
            with self.assertRaises(PublishError) as got:
                self.run_publish()
        message = str(got.exception)
        for fragment in ("ZQ-RAW-TEXT", "UNIQUE", "Errno", "constraint"):
            self.assertNotIn(fragment, message)
        self.assertIn("Publish again to record it", message, "the message gives the next step")

    def test_a_drive_root_has_a_plain_name_not_an_empty_quote(self):
        for root in ("/", "C:\\", "C:/"):
            self.assertEqual(platform.folder_name(root), "the top of the drive", root)
            self.assertEqual(platform.folder_phrase(root, True), "The top of the drive", root)
        self.assertEqual(platform.folder_phrase("/Users/demo/Reports"), "the folder “Reports”")
        self.assertEqual(platform.folder_phrase("/Users/demo/Reports/", True), "The folder “Reports”")
        self.assertNotIn("“”", platform.folder_phrase("/"))

    def test_a_link_to_another_projects_item_is_not_read_for_the_file(self):
        con = self.store.con
        con.execute("PRAGMA foreign_keys = OFF")
        con.execute("INSERT INTO projects (code, name) VALUES ('OTH', 'Another programme')")
        con.execute("INSERT INTO actions (id, project, description, raised, source) VALUES "
                    "('OTH-A-001', 'OTH', 'ZQ-OTHER-PROJECT-ACTION', '2026-10-01', 'demo')")
        con.execute("INSERT INTO links (from_item, to_item, kind, source) VALUES ('PUB-A-001', 'OTH-A-001', 'blocks', 'demo')")
        con.execute("INSERT INTO links (from_item, to_item, kind, source) VALUES ('OTH-A-001', 'PUB-A-002', 'blocks', 'demo')")
        con.execute("PRAGMA foreign_keys = ON")
        got = publish.read_inputs(self.store, "PUB", "2026-10-28")["data"]["links"]
        self.assertFalse([l for l in got if "OTH" in l["from_item"] or "OTH" in l["to_item"]], got)
        self.assertIn({"from_item": "PUB-A-001", "to_item": "PUB-A-002", "kind": "blocks"}, got, "a link inside the project stays")
        text = publish.render(publish.select(publish.read_inputs(self.store, "PUB", "2026-10-28")),
                              page.page_html(EMPTY_BRANDING), "2026-10-28", "t")
        self.assertNotIn("OTH-A-001", text)
        self.assertNotIn("ZQ-OTHER-PROJECT-ACTION", text)

    def test_movement_notes_never_reach_the_file(self):
        """#44's Movement choice and note live in milestones.internal_note, milestones.movement and in change_log rows (an
        internal_note change, and the note written with a rebaseline). None of it may feed a published file."""
        marker = "ZQ-MOVEMENT-NOTE"
        con = self.store.con
        con.execute("UPDATE milestones SET internal_note = ?, movement = 'rebaseline' WHERE id = 'PUB-M-001'", (marker,))
        con.execute("INSERT INTO applies (apply_id, by_user, device) VALUES (9001, 'Demo User', 'demo')")
        for field, value in (("internal_note", marker + "-LOG"), ("note", marker + "-REASON. Agreed with Sponsor. Decision PUB-D-001"),
                             ("movement", marker + "-CHOICE")):
            con.execute("INSERT INTO change_log (apply_id, tbl, item_id, field, old_value, new_value, op, via) "
                        "VALUES (9001, 'milestones', 'PUB-M-001', ?, NULL, ?, 'update', 'dashboard')", (field, value))
        done = self.run_publish()
        text = Path(done["path"]).read_text(encoding="utf-8")
        for planted in (marker, marker + "-LOG", marker + "-REASON", marker + "-CHOICE"):
            for spelling in fx.spellings(planted):
                self.assertNotIn(spelling, text, spelling)
        self.assertNotIn("rebaseline", {m.get("movement") for m in block(text)["data"]["milestones"]})
        for m in block(text)["data"]["milestones"]:
            self.assertFalse({"internal_note", "movement", "note"} & set(m), m)
        self.assertIn("PUB-M-001", text, "the milestone itself is published")

    def test_a_published_file_has_no_comment_even_with_a_brand_that_has_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "tokens.css").write_text("/* made by Jane Example, 01-01-2026 */\n:root { --brand-navy: #123456; }",
                                                  encoding="utf-8")
            done = self.run_publish(branding=tmp)
        text = Path(done["path"]).read_text(encoding="utf-8")
        self.assertIn("--brand-navy: #123456", text)
        self.assertNotIn("<!--", text)
        for style in re.findall(r"<style[^>]*>(.*?)</style>", text, re.S):
            self.assertNotIn("/*", style)
        for gone in ("Jane Example", "01-01-2026"):
            self.assertNotIn(gone, text)

    def test_a_published_file_is_the_view_only_page_with_no_route_that_changes_anything(self):      # #65
        text = Path(self.run_publish()["path"]).read_text(encoding="utf-8")
        editing = page.page_html(EMPTY_BRANDING)
        for route in ("/api/change", "/api/undo"):
            self.assertIn(route, editing, "the page the local server serves names the route, so this test can fail")
            self.assertNotIn(route, text)

    def test_a_publication_cannot_be_recorded_in_the_middle_of_a_step(self):
        with self.store.step("dashboard", "Demo User"):
            with self.assertRaisesRegex(store_module.Invalid, "middle of a step"):
                self.store.log_publication("PUB", self.out / "x.html", "2026-10-23", "a" * 64, "Demo User")
        self.assertEqual(self.publications(), [])

    def test_log_publication_refuses_bad_input(self):
        good = ("PUB", self.out / "x.html", "2026-10-23", "a" * 64, "Demo User")
        for bad, words in (((("NOPE",) + good[1:]), "isn't here"), ((good[:3] + ("xyz",) + good[4:]), "SHA-256"),
                           ((good[:4] + (" ",)), "who made it"), ((good[0], "x.html") + good[2:], "full path"),
                           ((good[:2] + ("not-a-date",) + good[3:]), "YYYY-MM-DD"), ((good[:2] + ("2026-02-30",) + good[3:]), "YYYY-MM-DD")):
            with self.subTest(words=words), self.assertRaisesRegex(store_module.Invalid, words):
                self.store.log_publication(*bad)
        self.assertEqual(self.publications(), [])

    def test_matches_data_for_shape(self):
        """The page cannot drift from the editor: a published row equals data_for's row on every field both have."""
        pub = publish.select(publish.read_inputs(self.store, "PUB", "2026-10-28"))["data"]
        editor = self.store.data_for("PUB")
        checked = 0
        for table in ("milestones", "actions", "raid", "decisions", "use_cases", "workstreams"):
            have = {r["id"]: r for r in editor[table]}
            for row in pub[table]:
                self.assertIn(row["id"], have, f"{row['id']} is published but not in the editor's data")
                shared = set(row) & set(have[row["id"]])
                self.assertTrue(shared)
                for field in shared:
                    if field in ("state", "state_word", "slip_days", "original_date"):     # worked out for the page, not stored
                        continue
                    if field in ("milestone", "use_case", "replaces") and row[field] is None:     # a reference to a dropped row
                        continue
                    if field in publish.RICH.get(table, ()):                                    # cleaned of script and handlers
                        continue
                    self.assertEqual(row[field], have[row["id"]][field], f"{row['id']}.{field}")
                    checked += 1
        self.assertGreater(checked, 50)

    def test_publish_opens_db_read_only(self):
        before = hashlib.sha256(self.db.read_bytes()).hexdigest()
        opened, sql = [], []
        real = sqlite3.connect

        def spy(*args, **kw):
            opened.append((args, kw))
            con = real(*args, **kw)
            con.set_trace_callback(sql.append)
            return con
        with mock.patch.object(store_module.sqlite3, "connect", spy):
            self.run_publish()
        self.assertEqual(len(opened), 1, "one connection")
        self.assertIn("mode=ro", opened[0][0][0])
        self.assertEqual(sum(s.strip().upper() == "BEGIN" for s in sql), 1, "one read transaction")
        asked = " ".join(sql)
        for column in ("internal_note", "movement", "reasoning", "options", "response_action", "publish_local", "keywords", "comments"):
            self.assertNotIn(column, asked, "a column the file never carries isn't even read")
        self.assertNotRegex(asked, r"\bsource\b")
        self.assertEqual(hashlib.sha256(self.db.read_bytes()).hexdigest(), before, "the database is not changed")
        ro = store_module.connect(self.db, readonly=True)
        with self.assertRaises(sqlite3.OperationalError):
            ro.execute("DELETE FROM actions")
        ro.close()

    def test_a_bad_code_or_a_missing_project_is_said_plainly(self):
        for code, words in (("pub", "capital letters"), ("NOPE", "no project with the code NOPE"), ("", "capital letters")):
            with self.assertRaisesRegex(PublishError, words):
                publish.read_inputs(self.store, code)
        with mock.patch.object(self.store, "publish_inputs", side_effect=sqlite3.DatabaseError("disk image is malformed")):
            with self.assertRaisesRegex(PublishError, "could not be read"):
                publish.read_inputs(self.store, "PUB")

    def test_without_report_sections_the_default_order_none_hidden(self):
        tmp, db = make_db(self, lambda plant: plant.update(sections=[]))
        pub = publish.select(publish.read_inputs(store_of(self, db), "PUB", "2026-10-28"))
        self.assertEqual([s["type"] for s in pub["sections"]],
                         ["current", "glance", "usecases", "milestones", "raid", "actions", "decisions"])
        self.assertEqual(pub["tabs"], ["dashboard", "work", "milestones", "usecases"])

    def test_the_module_never_reaches_the_servers_data_route_or_a_dialog(self):
        tree = ast.parse((SRC / "clark" / "publish.py").read_text(encoding="utf-8"))
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(tree)
                                                                           if isinstance(n, ast.Attribute)}
        self.assertNotIn("data_for", names)
        self.assertNotIn("choose_save_file", names)
        self.assertNotIn("choose_folder", names)
        imports = [(n.module, [a.name for a in n.names]) for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        self.assertIn(("clark.server", ["csp_hashes"]), imports)
        self.assertNotIn("server", [a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module == "clark"
                                    for a in n.names])
        self.assertNotIn("/api/data", (SRC / "clark" / "publish.py").read_text(encoding="utf-8"))


# ===== Test C: the finished file, in a real browser, from file:// with nothing listening =====
class Watching(_Pipe):
    """The test harness's pipe, keeping the events Chrome sends (it drops them, which a network test can't)."""

    def call(self, method, params=None, session=None):
        self.n += 1
        msg = {"id": self.n, "method": method, "params": params or {}}
        if session:
            msg["sessionId"] = session
        import os
        os.write(self.w, json.dumps(msg).encode() + b"\0")
        while True:
            while b"\0" not in self.buf:
                chunk = os.read(self.r, 1 << 16)
                if not chunk:
                    raise RuntimeError("Chrome closed the pipe")
                self.buf += chunk
            raw, self.buf = self.buf.split(b"\0", 1)
            m = json.loads(raw)
            if m.get("id") == self.n:
                if "error" in m:
                    raise RuntimeError(m["error"])
                return m["result"]
            if "method" in m:
                self.events = getattr(self, "events", []) + [m]


def opened(cdp, url, width=1400):
    """Attach to the page, watch the network and policy violations from the first byte, and open `url`."""
    cdp.__class__ = Watching
    cdp.events = []
    tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
    sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
    cdp.call("Network.enable", {}, sid)
    cdp.call("Page.enable", {}, sid)
    cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": "window.violations = [];"
             "document.addEventListener('securitypolicyviolation', function (e) { window.violations.push("
             "e.violatedDirective + ' ' + e.blockedURI); });"}, sid)
    cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
    cdp.call("Page.navigate", {"url": url}, sid)
    return sid


class Counting(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.server.seen.append(self.path)
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

    def log_message(self, *a):
        pass


class RealBrowser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        db = fx.build_db(Path(cls.tmp.name) / "clark.db")
        cls.store = open_store(db, onedrive_roots=[])
        cls.addClassCleanup(cls.store.close)
        cls.done = publish.publish(cls.store, "PUB", cls.tmp.name, by_user="Demo User", now="2026-10-28", branding=EMPTY_BRANDING)
        cls.path = Path(cls.done["path"])
        cls.url = cls.path.as_uri()
        cls.plant = fx.load()
        cls.name = 'Bridge & "Harbour" <Programme>'

    def draw(self, cdp, hash_="", width=1400):
        sid = opened(cdp, self.url + hash_, width)
        self.assertTrue(wait(lambda: cdp.js("document.querySelector('h1') && document.documentElement.dataset.ready", sid) == "1"),
                        "the page drew from the file alone")
        return sid

    def test_C_file_opens_from_file_url_without_a_server(self):
        self.assertTrue(self.url.startswith("file:///"))
        with chrome() as cdp:
            sid = self.draw(cdp)
            self.assertEqual(cdp.js("location.protocol", sid), "file:")
            self.assertEqual(cdp.js("document.querySelector('h1').textContent", sid), self.name)
            self.assertEqual(cdp.js("document.title", sid), self.name)
            self.assertEqual(cdp.js("[...document.querySelectorAll('.tab')].map(t => t.dataset.view).join()", sid),
                             "dashboard,work,milestones,usecases", "four tabs and no Settings")
            self.assertEqual(cdp.js("document.querySelector('.asat').textContent", sid), "As at 28-10-2026")
            for view, h1 in (("work", "Work items"), ("milestones", "Milestones"), ("dashboard", self.name)):
                cdp.js(f"document.querySelector('[data-view={view}]').click()", sid)
                self.assertTrue(wait(lambda: cdp.js("document.querySelector('h1').textContent", sid) == h1), view)
            self.assertEqual(cdp.js("window.violations", sid), [], "the policy blocked nothing the page needed, "
                             "with no style-src-attr")

    def test_C_no_request_leaves_the_file(self):
        with chrome() as cdp:
            sid = self.draw(cdp)
            for view in ("work", "milestones"):
                cdp.js(f"document.querySelector('[data-view={view}]').click()", sid)
            time.sleep(1)
            cdp.js("1", sid)
        asked = [e["params"]["request"]["url"] for e in cdp.events if e.get("method") == "Network.requestWillBeSent"]
        self.assertEqual([u for u in asked if not u.startswith("data:")], [self.url], f"only the document: {asked}")

    def test_C_meta_csp_blocks_injected_script_and_fetch(self):
        listener = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Counting)
        listener.seen = []
        threading.Thread(target=listener.serve_forever, daemon=True).start()
        self.addCleanup(listener.server_close)
        self.addCleanup(listener.shutdown)
        out = f"http://127.0.0.1:{listener.server_port}"
        with chrome() as cdp:
            sid = self.draw(cdp)
            cdp.js("var s = document.createElement('script'); s.textContent = 'window.injected = 1'; "
                   "document.body.appendChild(s); var t = document.createElement('script'); "
                   f"t.src = '{out}/script.js'; document.body.appendChild(t);"
                   "window.fetched = 'pending'; fetch('" + out + "/fetch').then(function () { window.fetched = 'allowed'; }, "
                   "function (e) { window.fetched = 'blocked'; });"
                   f"var i = new Image(); i.src = '{out}/image.png'; var x = new XMLHttpRequest(); x.open('GET', '{out}/xhr'); "
                   "try { x.send(); } catch (e) {} document.body.insertAdjacentHTML('beforeend', "
                   "'<img src=\"data:,\" onerror=\"window.handler = 1\">');", sid)
            self.assertTrue(wait(lambda: cdp.js("window.fetched", sid) != "pending"))
            self.assertTrue(wait(lambda: len(cdp.js("window.violations", sid)) >= 5, 30), cdp.js("window.violations", sid))
            self.assertEqual(cdp.js("[window.injected === undefined, window.fetched, window.handler === undefined]", sid),
                             [True, "blocked", True])
            time.sleep(1)
        self.assertEqual(listener.seen, [], "nothing reached the local listener")

    def test_C_rendered_dom_has_no_markers_and_counts_match(self):
        with chrome() as cdp:
            sid = self.draw(cdp)
            tiles = cdp.js("[...document.querySelectorAll('.glance .fig')].map(n => n.dataset.fig)", sid)     # #45: the counts are the At a glance tiles
            cdp.js("document.querySelector('[data-view=work]').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#work')", sid)))
            cdp.js("document.querySelector('[data-show=all]').click()", sid)             # the list starts on Open (#64a); All lists every kept row
            self.assertTrue(wait(lambda: cdp.js("document.querySelector('[data-show=all]').getAttribute('aria-pressed')", sid) == "true"))
            work = cdp.js("document.querySelector('#work').textContent", sid)
            cdp.js("document.querySelector('[data-view=milestones]').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#milestones')", sid)))
            milestones = cdp.js("document.querySelector('#milestones').textContent", sid)
            dom = cdp.js("document.documentElement.outerHTML", sid)
        self.assertEqual(tiles, ["health", "overdue", "risks"], "the file draws the At a glance tiles; their numbers are checked in test_publish_glance")
        self.assertIn("5 items", work, "the list says how many it holds: the kept rows only")
        self.assertIn("ZQ-KEEP-MILESTONE-1", milestones)
        self.assertNotIn("ZQ-FLAG-OFF-MILESTONE", milestones)
        for key, marker in self.plant["markers"].items():
            self.assertNotIn(marker.lower(), dom.lower(), key)

    def test_kept_rows_present_in_dom(self):
        """#36 draws the Work items rows: every kept work item is on the page, no dropped one is (the controls for the absence
        tests: a page that drew nothing would pass those)."""
        work_ids = [i for i in self.plant["kept"] if re.fullmatch(r"PUB-(A-|D-)?\d{3}", i)]
        with chrome() as cdp:
            sid = self.draw(cdp)
            cdp.js("document.querySelector('[data-view=work]').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#work')", sid)))
            cdp.js("document.querySelector('[data-show=all]').click()", sid)             # the list starts on Open (#64a); All lists every kept row
            self.assertTrue(wait(lambda: cdp.js("document.querySelector('[data-show=all]').getAttribute('aria-pressed')", sid) == "true"))
            work = cdp.js("document.querySelector('#work').textContent", sid)
        self.assertEqual(len(work_ids), 5)
        for item in work_ids:
            self.assertIn(item, work, f"{item} is kept and must be on the page")
        for item in self.plant["dropped"]:
            self.assertNotIn(item, work, f"{item} is dropped and must not be on the page")

    def test_C_view_only_nothing_editable(self):
        with chrome() as cdp:
            sid = self.draw(cdp)
            # The milestone block (.msv) holds buttons that only change how the view is drawn: the Timeline / Calendar switch, zoom,
            # Today, the arrows, the scale, a quarter's month heading, Legend, "Show all" and Reset. Only these are allowed in a file;
            # any other button there (an eye, Export, Hold) is an Edit control and fails, as does every button outside the block.
            allow = "[data-msvb], [data-mv], [data-cal], [data-scale-b], [data-goto], [data-msall], [data-zreset], .mlg-b"
            found = cdp.js("({fields: document.querySelectorAll('input, textarea, select, form, [contenteditable]').length, "
                           "design: document.designMode, editable: document.body.isContentEditable, "
                           "buttons: [...document.querySelectorAll('button')].filter(b => !b.classList.contains('tab') && !b.closest('.msv') && !b.closest('.toc')).length, "
                           f"unlisted: [...document.querySelectorAll('.msv button')].filter(b => !b.matches({json.dumps(allow)})).map(b => b.className + ' ' + b.textContent).length, "
                           "settings: !!document.querySelector('[data-view=settings]'), mode: document.documentElement.dataset.mode})", sid)
        self.assertEqual(found, {"fields": 0, "design": "off", "editable": False, "buttons": 0, "unlisted": 0, "settings": False, "mode": "view"})

    def test_C_boxed_width_1232_at_1400_and_no_sideways_scroll_at_900(self):
        with chrome() as cdp:
            sid = self.draw(cdp)
            width = "Math.round(document.querySelector('.frame').getBoundingClientRect().width)"
            seen = {}
            for w in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
                for view in ("dashboard", "work", "milestones"):
                    cdp.js(f"document.querySelector('[data-view={view}]').click()", sid)
                    self.assertTrue(wait(lambda: cdp.js("document.documentElement.scrollWidth <= window.innerWidth", sid)),
                                    f"{view} at {w}px has no sideways scroll")
                    seen[(w, view)] = cdp.js(width, sid)
        self.assertEqual([seen[(1400, v)] for v in ("dashboard", "work", "milestones")], [1232, 1232, 1232],
                         "the page's 1280 px less its 24 px padding, as in the editor")

    def test_C_hash_navigation_works_on_file_url(self):
        with chrome() as cdp:
            sid = self.draw(cdp, "#milestones&p=PUB")
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#milestones')", sid)), "the address picks the view")
            cdp.js("document.querySelector('[data-view=work]').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("location.hash", sid) == "#work&p=PUB"))
            self.assertEqual(cdp.js("location.protocol + document.querySelectorAll('.tab[aria-selected=true]').length", sid), "file:1")
        with chrome() as cdp:
            sid = self.draw(cdp, "#settings&p=PUB")
            self.assertEqual(cdp.js("document.querySelector('h1').textContent", sid), self.name,
                             "a file has no Settings: the address falls back to the first view")
            self.assertEqual(cdp.js("document.querySelectorAll('.tab[aria-selected=true]')[0].dataset.view", sid), "dashboard")


if __name__ == "__main__":
    unittest.main()
