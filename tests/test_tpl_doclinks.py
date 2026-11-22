"""#96 G7, Documents and links (store type "doclinks"): the content's checker and its limits, hostile input, one save one step one
Undo, what the published file carries (a hidden or empty section is left out; a marker scan of the file), and the page: the
served View and the published file draw the same list, Edit adds and removes a link in one step each, and refuses a bad link
in words before anything is sent. The file part (Add a file) is tests/test_section_file_route.py.

Run: python3 dev/run_tests.py test_tpl_doclinks
Needs Chrome (the #33 harness): the page tests fail, never skip, without it. Fictional data only. Laptop widths 1400 and 900 px,
light and dark.
"""
import json
import re
import shutil
import tempfile
import time
import hashlib
import unittest
from pathlib import Path
from unittest import mock

from _demo import USER
from _paths import SRC
import _testpage
from clark import changes, page, publish, section_bodies, store as store_module, theme
from clark.section_kinds import base, doclinks
from test_changes import Api
from test_report_editor import EMPTY_BRANDING, Base as PageBase, Pg
from test_server import chrome

MARK = "Fictional marker kept out"        # planted where it must never reach a file
RULES = store_module.BODY_RULES
DESCRIPTION_LABEL = "Link description (required)"          # quoted from the ticket
EMPTY_STATE = "Nothing here yet. Add a file or a link."      # quoted from the ticket


def body(items, **more):
    return json.dumps({"v": 1, "items": items, **more})


def a_file(name="Plan v2.pdf", size=340 * 1024, **more):
    return {"kind": "file", "name": name, "rel": f"Report files/{name}", "bytes": size, **more}


def a_link(href="https://example.org/plan", label="The plan", **more):
    return {"kind": "link", "href": href, "label": label, **more}


def check(kind, text):
    return section_bodies.check(kind, text, RULES)


class Checker(unittest.TestCase):
    def refused(self, kind, text, words=None):
        with self.assertRaises(section_bodies.Bad) as e:
            check(kind, text)
        self.assertNotIn(MARK, str(e.exception), "a refusal never quotes the content")
        if words:
            self.assertEqual(str(e.exception), words)
        return str(e.exception)

    def test_a_good_list_is_stored_as_canonical_text_with_words_trimmed(self):
        got = check("doclinks", body([a_link(label="  The plan  "), a_file(label="")]))
        self.assertEqual(json.loads(got), {"v": 1, "items": [
            {"kind": "link", "href": "https://example.org/plan", "label": "The plan"},
            {"kind": "file", "name": "Plan v2.pdf", "rel": "Report files/Plan v2.pdf", "bytes": 340 * 1024, "label": ""}]})
        self.assertEqual(check("doclinks", got), got, "saving it again changes nothing")
        self.assertEqual(json.loads(check("doclinks", body([a_link(href="mailto:team@example.org", label="Team")])))["items"][0]["href"],
                         "mailto:team@example.org")
        self.assertEqual(check("doclinks", ""), "", "no content is no content")
        self.assertTrue(doclinks.READY)

    def test_only_https_and_mailto_links_with_nothing_hidden_in_them(self):
        for href in ("javascript:alert(1)", "JaVaScRiPt:alert(1)", "http://example.org", "data:text/html,x", "//example.org",
                     "relative/page.html", "Report files/Plan.pdf", "#top", "https://", "https:///x", "https://@example.org",
                     "https://user:" + "pass@example.org/", "https://.example.org", "https://example.org/a b", "https://example.org/\\x",
                     "mailto:", "ftp://example.org", "https://example.org/" + "a" * 2000, "", 7, None, True, ["https://example.org"]):
            with self.subTest(href=href):
                self.refused("doclinks", body([a_link(href=href)]))
        self.refused("doclinks", body([a_link(href="https://exa‮mple.org")]))      # a direction-changing character (generic wall)
        self.refused("doclinks", body([a_link(href="https://exa\tmple.org")]))

    def test_a_file_is_one_safe_name_in_report_files_with_a_true_size(self):
        bad = [dict(a_file(), rel="Report files/other.pdf"), dict(a_file(), rel="../Report files/Plan v2.pdf"),
               a_file(name="../secret.txt"), a_file(name="sub/a.pdf"), a_file(name="a\\b.pdf"), a_file(name="C:a.pdf"),
               a_file(name=".hidden"), a_file(name="trailing."), a_file(name="trailing "), a_file(name=" lead"), a_file(name=""),
               a_file(name="a" * 121), a_file(name='a"b.pdf'), a_file(name="a?.pdf"), a_file(name="a|b.pdf"),
               a_file(size=-1), a_file(size=True), a_file(size="12"), a_file(size=2 ** 41), a_file(size=None),
               {"kind": "file", "name": "a.pdf", "bytes": 1}, {"kind": "file", "rel": "Report files/a.pdf", "bytes": 1}]
        for item in bad:
            with self.subTest(item=item):
                self.refused("doclinks", body([item]))
        self.assertEqual(json.loads(check("doclinks", body([a_file(name="a#b (2).docx")])))["items"][0]["name"], "a#b (2).docx")

    def test_only_the_allowed_endings_are_taken_and_the_last_ending_decides(self):
        for name in ("a.pdf", "Plan.PDF", "a.Doc", "a.docx", "a.xls", "a.xlsx", "a.csv", "a.ppt", "a.pptx", "a.jpg", "a.JPEG", "a.png",
                     "a.txt", "report.exe.pdf", "a.b.TXT"):
            with self.subTest(name=name):
                self.assertEqual(json.loads(check("doclinks", body([a_file(name=name)])))["items"][0]["name"], name)
        for name in ("a.html", "a.htm", "a.svg", "a.zip", "a.exe", "a.js", "a.sh", "a.bat", "report.pdf.exe", "noending", "a.pdf ",
                     "a.pdfx", "pdf", "a.gif", "a.docm"):
            with self.subTest(name=name):
                self.refused("doclinks", body([a_file(name=name)]), f"{name}: {doclinks.BAD_FILE}" if name.endswith(" ") else doclinks.bad_type(name))

    def test_the_refusal_names_the_allowed_types_and_add_file_meets_the_same_rule(self):
        for word in ("PDF", "Word", "Excel", "PowerPoint", "JPG", "PNG", "TXT"):
            self.assertIn(word, doclinks.BAD_TYPE_TAIL)
        with self.assertRaises(section_bodies.Bad) as e:
            doclinks.add_file(None, {"name": "a.zip", "rel": "Report files/a.zip", "bytes": 1})
        self.assertEqual(str(e.exception), doclinks.bad_type("a.zip"))

    def test_the_first_bytes_must_match_the_ending(self):
        """Row 1194 (ruling 21-11): one function, doclinks.allowed_content, for the file window and the drop; the refusal is bad_type."""
        ok = doclinks.allowed_content
        self.assertEqual(ok("a.pdf", b"%PDF-1.4"), "a.pdf")
        self.assertEqual(ok("A.DOCX", b"PK\x03\x04"), "A.DOCX")
        self.assertEqual(ok("a.txt", "words".encode()), "a.txt")
        for name, head in (("a.pdf", b"PK\x03\x04"), ("a.png", b"%PDF-"), ("a.doc", b"PK\x03\x04"), ("a.csv", b"a\x00b"), ("a.pdf", b""), ("a.zip", b"PK\x03\x04")):
            with self.subTest(name=name, head=head), self.assertRaises(section_bodies.Bad) as e:
                ok(name, head)
            self.assertEqual(str(e.exception), doclinks.bad_type(name))

    def test_a_link_needs_a_description_a_file_does_not(self):
        for label in ("", "   "):
            with self.subTest(label=label):
                self.refused("doclinks", body([a_link(label=label)]), "Link 1: Enter a link description.")
        self.refused("doclinks", body([{"kind": "link", "href": "https://example.org/plan"}]), "Link 1: Enter a link description.")
        self.assertEqual(json.loads(check("doclinks", body([a_file(label="")])))["items"][0]["label"], "")

    def test_the_refusal_for_a_link_names_its_place_in_the_list(self):
        """Item 1194 (ruled 15-11): 'Link {n}: Enter a link description.', n counted from 1 over every entry, files included."""
        self.refused("doclinks", body([a_link(), a_link(label="")]), "Link 2: Enter a link description.")
        self.refused("doclinks", body([a_link(), a_file(), a_link(label="  ")]), "Link 3: Enter a link description.")

    def test_a_stored_entry_that_fails_the_check_is_named_in_the_refusal(self):
        """Item 1628 (ruled 16-11): a refusal that drops the whole section names the item: a file by its name, a link by its place (from 1)."""
        self.refused("doclinks", body([a_link(), a_link(href="http://example.org")]), "Link 2: " + doclinks.BAD_LINK)
        self.refused("doclinks", body([a_file(), a_link(label="x" * 500)]), "Link 2: " + doclinks.BAD_LABEL)
        self.refused("doclinks", body([a_link(), a_file(name="Plan v3.pdf", rel="Report files/other.pdf")]), "Plan v3.pdf: " + doclinks.BAD_FILE)
        self.refused("doclinks", body([a_file(label="x" * 500)]), "Plan v2.pdf: " + doclinks.BAD_LABEL)
        self.refused("doclinks", body([a_file(name="a.zip")]), doclinks.bad_type("a.zip"))      # already named: no second prefix
        self.refused("doclinks", body([a_link(label="")]), "Link 1: Enter a link description.")

    def test_the_refusal_for_a_file_names_the_file(self):
        """Item 1194 (ruled 15-11): '{file name}: That type of file can't be added. Use PDF, Word, Excel, PowerPoint, JPG, PNG or TXT.'"""
        tail = "That type of file can't be added. Use PDF, Word, Excel, PowerPoint, JPG, PNG or TXT."
        self.refused("doclinks", body([a_link(), a_file(name="Setup tool.zip")]), "Setup tool.zip: " + tail)
        with self.assertRaises(section_bodies.Bad) as e:
            doclinks.add_file(None, {"name": "run me.exe", "rel": "Report files/run me.exe", "bytes": 1})
        self.assertEqual(str(e.exception), "run me.exe: " + tail)

    def test_the_refusal_for_a_file_type_is_one_sentence_on_the_server_and_in_the_page(self):
        """Item 1628 (ruled 16-11): the page's BAD_TYPE (docLinksWords.js), doclinks.bad_type and the route's bad_type refusal are the same sentence."""
        from clark import section_files
        name = "run me.exe"
        words = (SRC / "clark" / "page" / "src" / "logic" / "docLinksWords.js").read_text(encoding="utf-8")
        page = re.search(r"export const BAD_TYPE = \(name\) => `([^`]*)`;", words).group(1).replace("${name}", name)
        route = section_files.MESSAGES["bad_type"].format(name=name)
        self.assertEqual(page, doclinks.bad_type(name))
        self.assertEqual(route, doclinks.bad_type(name))

    def test_a_name_with_nothing_before_its_ending_is_not_a_type_and_a_long_name_is_cut_in_the_refusal(self):
        """Mutation sweep (1194): ".pdf" has an ending but no name; a refusal quotes at most NAME_MAX characters of a file's name."""
        for name in (".pdf", "pdf", "."):
            with self.assertRaises(section_bodies.Bad, msg=name):
                doclinks.allowed_type(name)
        text = self.refused("doclinks", body([a_file(name="x" * 300 + ".pdf")]))
        self.assertEqual(text.split(": ")[0], "x" * doclinks.NAME_MAX, "the name in the refusal is cut at NAME_MAX")

    def test_the_shape_is_fixed_and_nothing_unknown_is_stored(self):
        self.refused("doclinks", json.dumps({"v": 2, "items": []}), doclinks.BAD_VERSION)
        self.refused("doclinks", json.dumps({"v": True, "items": []}), doclinks.BAD_VERSION)
        self.refused("doclinks", json.dumps({"items": []}))
        for extra in (json.dumps({"v": 1, "items": [], "script": MARK}), body([dict(a_link(), onclick=MARK)]),
                      body([dict(a_file(), href="https://example.org/" + MARK.replace(" ", "-"))])):
            self.assertNotIn(MARK.split()[1], check("doclinks", extra), "a field the section doesn't use is dropped, never stored")
        self.refused("doclinks", body([{"kind": "picture", "src": "x"}]), doclinks.BAD_KIND)
        self.refused("doclinks", body(["https://example.org"]), doclinks.BAD_KIND)
        self.refused("doclinks", json.dumps({"v": 1, "items": {"0": a_link()}}))
        self.refused("doclinks", json.dumps([a_link()]))
        self.refused("doclinks", body([a_link(label=MARK * 10)]), "Link 1: " + doclinks.BAD_LABEL)
        self.refused("doclinks", body([a_link(label=12)]), "Link 1: " + doclinks.BAD_LABEL)

    def test_at_most_twenty_entries_and_the_limit_fits_the_change_route(self):
        self.assertEqual(len(json.loads(check("doclinks", body([a_link()] * 20)))["items"]), 20)
        self.refused("doclinks", body([a_link()] * 21), doclinks.TOO_MANY)
        self.refused("doclinks", body([a_link(href="https://example.org/" + "p" * 1900, label="w" * 120)] * 20), section_bodies.TOO_BIG)
        self.assertLessEqual(doclinks.LIMIT + 8 * 1024, 72 * 1024, "a full section is sent through /api/change")

    def test_add_file_puts_the_server_s_entry_at_the_end_and_refuses_a_full_list(self):
        value = json.loads(check("doclinks", body([a_link()])))
        got = doclinks.add_file(value, {"name": "Budget.xlsx", "rel": "Report files/Budget.xlsx", "bytes": 10})
        self.assertEqual(got["items"][-1], {"kind": "file", "name": "Budget.xlsx", "rel": "Report files/Budget.xlsx", "bytes": 10, "label": ""})
        self.assertEqual(doclinks.add_file(None, {"name": "a.pdf", "rel": "Report files/a.pdf", "bytes": 1})["items"][0]["name"], "a.pdf")
        with self.assertRaises(section_bodies.Bad):
            doclinks.add_file({"v": 1, "items": [a_link()] * 20}, {"name": "a.pdf", "rel": "Report files/a.pdf", "bytes": 1})
        with self.assertRaises(section_bodies.Bad):
            doclinks.add_file(None, {"name": "../a.pdf", "rel": "Report files/../a.pdf", "bytes": 1})

    def test_published_picks_the_fields_and_leaves_an_empty_list_out(self):
        ctx = base.Context({}, "2030-01-15")
        value = json.loads(check("doclinks", body([a_link(), a_file()])))
        self.assertEqual(section_bodies.published("doclinks", value, ctx), {"content": {"items": value["items"]}})
        self.assertIsNone(section_bodies.published("doclinks", {"v": 1, "items": []}, ctx))


class RenameTest:
    """Typing into the one open rename box and pressing a key."""
    @staticmethod
    def type(p, sel, value, key, index=0):
        p.js(f"(() => {{ const el = document.querySelectorAll({json.dumps(sel + ' input[data-rename-input]')})[{index}]; el.focus(); el.value = {json.dumps(value)};"
             " el.dispatchEvent(new Event('input', {bubbles: true}));"
             f" el.dispatchEvent(new KeyboardEvent('keydown', {{key: {json.dumps(key)}, bubbles: true}})); }})()")


class Saved(Api):
    def make(self, title="Fictional documents", **more):
        return self.ok("new", values={"type": "doclinks", "title": title}, after=None, **more)["ref"]

    def save(self, ref, text):
        return self.change(self.req(changes.UPDATE, id=ref, changes={"body": text}, place="report"))

    def test_one_save_is_one_step_and_one_undo_puts_the_list_back(self):
        ref = self.make()
        status, first = self.save(ref, body([a_link()]))
        self.assertEqual(status, 200, first)
        status, second = self.save(ref, body([a_link(), a_link(href="https://example.org/two", label="Two")]))
        self.assertEqual(status, 200, second)
        self.assertNotEqual(first["apply_id"], second["apply_id"])
        rows = self.s.con.execute("SELECT field FROM change_log WHERE apply_id = ? AND field != 'updated_at'", (second["apply_id"],)).fetchall()
        self.assertEqual([r["field"] for r in rows], ["body"], "one field in one step")
        status, _ = self.undone(second["apply_id"])
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(self.s.read("report_sections", ref=ref)["body"])["items"], [a_link()])

    def test_a_refused_save_writes_nothing_and_says_why_without_quoting(self):
        ref = self.make()
        before = self.snapshot()
        status, got = self.save(ref, body([a_link(href="javascript:" + MARK)]))
        self.assertEqual(status, 400)
        self.assertEqual(got["message"], "Link 1: " + doclinks.BAD_LINK)
        self.assertNotIn(MARK, json.dumps(got))
        self.assertEqual(self.snapshot(), before)

    def stored(self, ref, text):
        """Put `text` in the section's body as an older clark, or a hand edit, could have left it (no checker in the way)."""
        self.s.con.execute("UPDATE report_sections SET body = ? WHERE id = ?", (text, ref))
        self.s.con.commit()
        self.assertEqual(self.s.read("report_sections", ref=ref)["body"], text)

    def test_stored_content_the_new_rules_refuse_is_kept_on_a_save_and_left_out_of_the_file_OPTION_A(self):
        """Item 1194 made a link description required and a file ending allowed. Content stored BEFORE that (a link with no words, a
        file ending in .zip) no longer checks. This test used to pin that every save was refused while such an entry was held (the
        whole section was locked until the editor removed it). It is changed to option A, because a report with one old entry could
        not be saved at all, not even to fix another line: a save keeps an entry the section already holds when it comes back
        unchanged; a changed or new entry meets every rule; publish reads the section's own stored text too, so the section is still
        published with the old entry in it (finding of 21-11: dropping it silently was refused)."""
        for name, old, fixed, words in (
                ("link with no words", a_link(label=""), a_link(label="Words now"), "Link 2: Enter a link description."),
                ("file with an ending that is not allowed", a_file(name="old.zip"), a_file(name="old.exe"), "old.exe: " + doclinks.BAD_TYPE_TAIL)):
            with self.subTest(old=name):
                ref = self.make("Fictional old " + name)
                self.stored(ref, body([a_link(), old]))
                built = publish.build(self.s, "ABC", now="2030-01-15")
                self.assertEqual(len(next(s for s in built["published"]["sections"] if s["id"] == ref)["content"]["items"]), 2, "publish keeps the old entry with the good link")
                new = a_link(href="https://example.org/new", label="New")
                status, got = self.save(ref, body([a_link(), old, new]))
                self.assertEqual(status, 200, got)
                self.assertEqual(json.loads(self.s.read("report_sections", ref=ref)["body"])["items"][1]["name" if old["kind"] == "file" else "href"],
                                 old.get("name") or old["href"], "the old entry is stored as it was")
                self.assertEqual(len(json.loads(self.s.read("report_sections", ref=ref)["body"])["items"]), 3)
                built = publish.build(self.s, "ABC", now="2030-01-15")
                self.assertEqual(len(next(s for s in built["published"]["sections"] if s["id"] == ref)["content"]["items"]), 3, "still published after a save that kept the old entry")
                before = self.snapshot()
                changed = dict(old, **({"name": "old.exe", "rel": "Report files/old.exe"} if old["kind"] == "file" else {"href": "https://example.org/other"}))
                status, got = self.save(ref, body([a_link(), changed]))
                self.assertEqual((status, got["message"]), (400, words), "a changed old entry meets every rule")
                bad_new = a_link(href="https://example.org/brand-new", label="")
                status, got = self.save(ref, body([a_link(), old, bad_new]))
                self.assertEqual((status, got["message"]), (400, "Link 3: Enter a link description."), "a new bad entry is refused")
                self.assertEqual(self.snapshot(), before, "a refused save writes nothing")
                status, got = self.save(ref, body([a_link()]))
                self.assertEqual(status, 200, got)
                built = publish.build(self.s, "ABC", now="2030-01-15")
                self.assertEqual([i["href"] for i in next(s for s in built["published"]["sections"] if s["id"] == ref)["content"]["items"]],
                                 ["https://example.org/plan"], "once the old entry is gone the section is published again")

    def test_a_section_saved_with_a_no_description_link_still_publishes(self):
        ref = self.make("Fictional saved before 1194 link")
        self.stored(ref, body([a_link(), a_link(href="https://example.org/old", label="")]))
        built = publish.build(self.s, "ABC", now="2030-01-15")
        items = next(s for s in built["published"]["sections"] if s["id"] == ref)["content"]["items"]
        self.assertEqual([i["href"] for i in items], ["https://example.org/plan", "https://example.org/old"])

    def test_a_section_saved_with_a_file_of_an_unlisted_ending_still_publishes(self):
        ref = self.make("Fictional saved before 1194 file")
        self.stored(ref, body([a_link(), a_file(name="old.zip")]))
        built = publish.build(self.s, "ABC", now="2030-01-15")
        items = next(s for s in built["published"]["sections"] if s["id"] == ref)["content"]["items"]
        self.assertEqual(len(items), 2)
        self.assertEqual(items[1]["name"], "old.zip")

    def test_publish_still_refuses_what_was_never_stored_that_way(self):
        """The relaxation is the stored text's own entries only: a body that is bad in another way is still left out."""
        ref = self.make("Fictional bad body")
        self.stored(ref, '{"v": 1, "items": [{"kind": "link", "href": "javascript:alert(1)", "label": "x"}]}')
        built = publish.build(self.s, "ABC", now="2030-01-15")
        self.assertNotIn(ref, {s["id"] for s in built["published"]["sections"]})

    def test_a_stored_body_that_cannot_be_read_does_not_stop_a_good_save(self):
        """Mutation sweep (1194): what the section holds is only a place to keep old entries; if it cannot be read, the new content is checked on its own."""
        ref = self.make("Fictional unreadable")
        self.stored(ref, "this is not json")
        status, got = self.save(ref, body([a_link()]))
        self.assertEqual(status, 200, got)
        self.assertEqual(json.loads(self.s.read("report_sections", ref=ref)["body"])["items"], [a_link()])

    def test_undo_of_a_delete_puts_back_a_section_with_an_old_entry(self):
        """Mutation sweep (1194): a section deleted with an old entry (a link with no words) comes back whole by Undo."""
        ref = self.make("Fictional deleted old")
        before = section_bodies.canonical({"v": 1, "items": [a_link(), a_link(label="")]})
        self.stored(ref, before)
        status, gone = self.change(self.req("delete", id=ref))
        self.assertEqual(status, 200, gone)
        status, back = self.undone(gone["apply_id"])
        self.assertEqual(status, 200, back)
        self.assertEqual(self.s.read("report_sections", ref=ref)["body"], before)

    def test_undo_of_a_save_puts_back_an_old_entry_the_new_rules_refuse(self):
        """Row 1194, the Undo defect: a body stored before item 1194 holds a link with no words; a save drops that link; Undo of the
        save must put the stored text back whole (200, body equal), as it does for any other section, not refuse its own old entry."""
        for name, old in (("link with no words", a_link(label="")), ("file with an ending that is not allowed", a_file(name="old.zip", label=""))):
            with self.subTest(old=name):
                ref = self.make("Fictional undo " + name)
                before = section_bodies.canonical({"v": 1, "items": [a_link(), old]})      # as clark stores a body: its canonical text
                self.stored(ref, before)
                status, got = self.save(ref, body([a_link()]))
                self.assertEqual(status, 200, got)
                status, undone = self.undone(got["apply_id"])
                self.assertEqual(status, 200, undone)
                self.assertEqual(undone.get("skipped") or [], [], "nothing is left out of the put back")
                self.assertEqual(self.s.read("report_sections", ref=ref)["body"], before)

    def test_undo_waives_only_the_entries_the_log_holds_and_the_section_still_publishes(self):
        ref = self.make("Fictional undo strict")
        old = a_link(label="")
        before = body([a_link(), old])
        self.stored(ref, before)
        status, got = self.save(ref, body([a_link()]))
        self.assertEqual(status, 200, got)
        status, _ = self.undone(got["apply_id"])
        self.assertEqual(status, 200)
        built = publish.build(self.s, "ABC", now="2030-01-15")
        self.assertEqual(len(next(s for s in built["published"]["sections"] if s["id"] == ref)["content"]["items"]), 2, "the section still publishes after the Undo")
        status, got = self.save(ref, body([a_link(), dict(old, href="https://example.org/other")]))
        self.assertEqual((status, got["message"]), (400, "Link 2: Enter a link description."), "a changed entry after the Undo meets every rule")
        status, got = self.save(ref, body([a_link(), old, a_link(href="https://example.org/n", label="")]))
        self.assertEqual((status, got["message"]), (400, "Link 3: Enter a link description."), "a new bad entry after the Undo is refused")

    def test_a_stored_entry_sent_back_with_only_its_description_changed_is_a_new_entry(self):
        """Mutation sweep (1194, S1): the description is part of what makes an entry 'the same one'; change or blank it and the entry meets every rule."""
        ref = self.make("Fictional description change")
        old = a_file(name="old.zip", label="Old words")
        self.stored(ref, section_bodies.canonical({"v": 1, "items": [a_link(), old]}))
        before = self.snapshot()
        for label in ("New words", ""):
            with self.subTest(label=label):
                status, got = self.save(ref, body([a_link(), dict(old, label=label)]))
                self.assertEqual(status, 400, got)
                self.assertEqual(got["message"], "old.zip: " + doclinks.BAD_TYPE_TAIL)
        self.assertEqual(self.snapshot(), before)
        status, got = self.save(ref, body([a_link(), old]))
        self.assertEqual(status, 200, got)

    def test_the_undoing_marker_never_stays_in_the_change_set(self):
        """Mutation sweep (1194, S2): the marker rides in `changed` for the checker only; it never reaches what the store does next."""
        ref = self.make("Fictional marker")
        row = dict(self.s.con.execute("SELECT * FROM report_sections WHERE id = ?", (ref,)).fetchone())
        row["body"] = body([a_link()])
        changed = {"body", store_module.UNDOING}
        store_module._section_rules(self.s.con, "report_sections", row, changed)
        self.assertNotIn(store_module.UNDOING, changed)

    def test_the_store_waives_old_entries_only_for_an_undo(self):
        """At the store's own door (no request check before it): a write of a body with a new entry that fails the rules is refused;
        the same text put back by an Undo (revert) is kept; an Undo still refuses a text that cannot be read at all."""
        ref = self.make("Fictional store door")
        old = body([a_link(), a_link(label="")])
        current = dict(self.s.con.execute("SELECT * FROM report_sections WHERE id = ?", (ref,)).fetchone())
        for revert, text, ok in ((False, old, False), (True, old, True), (True, "{not json", False), (False, body([a_link()]), True)):
            with self.subTest(revert=revert, text=text[:12]):
                if ok:
                    store_module._merged_row(self.s.con, "report_sections", current, {"body": text}, revert=revert)
                else:
                    with self.assertRaises(store_module.Invalid):
                        store_module._merged_row(self.s.con, "report_sections", current, {"body": text}, revert=revert)

    def test_the_file_carries_the_list_and_a_hidden_or_empty_section_is_left_out(self):
        shown = self.make("Fictional papers")
        self.save(shown, body([a_link(), a_file()]))
        hidden = self.make("Fictional hidden papers")
        self.save(hidden, body([a_link(label=MARK)]))
        self.ok(changes.UPDATE, id=hidden, changes={"hidden": 1})
        empty = self.make("Fictional empty papers")
        self.save(empty, body([]))
        never = self.make("Fictional never filled")
        built = publish.build(self.s, "ABC", now="2030-01-15")
        sections = {s["id"]: s for s in built["published"]["sections"]}
        self.assertEqual(sections[shown]["content"]["items"][0]["href"], "https://example.org/plan")
        self.assertEqual(sections[shown]["content"]["items"][1]["rel"], "Report files/Plan v2.pdf")
        for ref in (hidden, empty, never):
            self.assertNotIn(ref, sections)
        text = built["body"].decode("utf-8")
        self.assertNotIn(MARK, text)
        for title in ("Fictional hidden papers", "Fictional empty papers", "Fictional never filled"):
            self.assertNotIn(title, text)
        self.assertNotIn("body", sections[shown], "the stored text is never in the file")


class ClassicPage(PageBase):
    """The page with the Classic theme layered (the look of item 1194 is Classic's; Cards keeps its old rows, see CardsUnchanged)."""

    def setUp(self):
        real = _testpage.html
        patch = mock.patch.object(_testpage, "html", lambda branding=None: page.layer_theme(real(branding), theme.css("prototype-2.0")))
        patch.start()
        self.addCleanup(patch.stop)
        super().setUp()


class ClassicView(ClassicPage):
    """Item 1194, the View in Classic: the same entries as before, drawn as the page-style rows. (The Edit tests of InThePage run on the Cards page until the Edit part follows.)"""

    def add(self, items, title="Fictional papers", kind="doclinks"):
        with self.store.step("dashboard", USER) as st:
            ref = st.create("report_sections", {"project": "ABC", "type": kind, "title": title, "sort_order": 999})
        if items is not None:
            with self.store.step("dashboard", USER) as st:
                st.update("report_sections", ref, {"body": store_module.check_section_body(kind, body(items))})
        return ref

    def entries(self, p, ref):
        return p.js(f"[...document.querySelectorAll('[data-id={json.dumps(ref)}] .tpl-dl-i')].map(li => "
                    "[li.querySelector('.tpl-badge').textContent, li.querySelector('.tpl-name').textContent, "
                    "li.querySelector('.tpl-name').tagName, li.querySelector('.tpl-name').getAttribute('href')])")

    def test_the_email_link_icon_is_an_envelope_with_an_at_badge_and_no_page(self):
        """Row 1194 round 3 (approved 18-11, pick D 'Envelope with @', the mock's 41 x 41 icon): a filled circle with '@' on an envelope, no page behind it."""
        ref = self.add([a_link(href="mailto:team@example.org", label="Team")])
        with chrome() as cdp:
            p = self.visit(cdp)
            p.until(f"!!document.querySelector('[data-id={json.dumps(ref)}] .tpl-dl')", "the list drew")
            got = p.js(f"(() => {{ const s = document.querySelector('[data-id={json.dumps(ref)}] .tpl-dl-i .tpl-badge svg'); const r = s.getBoundingClientRect();"
                       " return [s.getAttribute('viewBox'), !!s.querySelector('rect'), !!s.querySelector('circle'), s.querySelector('text').textContent, s.querySelectorAll('path').length, Math.round(r.width), Math.round(r.height)]; })()")
            self.assertEqual(got, ["0 0 41 41", True, True, "@", 1, 41, 41], "an envelope (rect + flap), a filled circle, '@', no page path, 41 x 41")
            self.assertEqual(p.js(f"(() => {{ const s = document.querySelector('[data-id={json.dumps(ref)}] .tpl-dl-i .tpl-badge svg'); return [s.getAttribute('role'), s.getAttribute('aria-label'), s.hasAttribute('aria-hidden'), Math.round(s.querySelector('text').getBoundingClientRect().height)]; }})()")[:3],
                             ["img", "Email link", False], "the icon keeps the accessible name 'Email link' (ruled 21-11)")
            self.assertEqual(p.js(f"parseFloat(document.querySelector('[data-id={json.dumps(ref)}] .tpl-dl-i .tpl-badge svg text').getAttribute('font-size')) * parseFloat(document.querySelector('[data-id={json.dumps(ref)}] .tpl-dl-i .tpl-badge svg text').getAttribute('transform').match(/scale\\(([0-9.]+)\\)/)[1])").__round__(1), 11.0,
                             "the mock's @ is 11 px (ruled 21-11): 13 px glyph scaled, as the badge labels are, so the 13 px floor test stays whole")

    def test_view_draws_the_list_and_an_empty_one_is_left_out(self):
        ref = self.add([a_link(), a_link(href="mailto:team@example.org", label="Team"), a_file()])
        empty = self.add([], "Fictional empty papers")
        with chrome() as cdp:
            p = self.visit(cdp)
            p.until(f"!!document.querySelector('[data-id={json.dumps(ref)}] .tpl-dl')", "the list drew")
            self.assertEqual(self.entries(p, ref), [
                ["URL", "The plan", "SPAN", None],
                ["@", "Team", "SPAN", None],
                ["PDF", "Plan v2.pdf", "SPAN", None]], "in the editor's View a name stays plain text")
            self.assertEqual(p.js(f"[...document.querySelectorAll('[data-id={json.dumps(ref)}] .tpl-dl-i a.tpl-act')].map(a => a.getAttribute('aria-label') + ' ' + a.getAttribute('href'))"),
                             ["Open The plan https://example.org/plan", "Open Team mailto:team@example.org"], "a link gets Open only")
            self.assertFalse(p.js(f"!!document.querySelector('[data-id={json.dumps(empty)}]')"), "an empty list is left out of View")
            self.assertEqual(p.js(f"document.querySelectorAll('[data-id={json.dumps(ref)}] input').length"), 0, "View is read only")
            self.assertEqual(p.js(f"[...document.querySelectorAll('[data-id={json.dumps(ref)}] button')].map(b => b.getAttribute('aria-label'))"),
                             ["Open Plan v2.pdf", "Download Plan v2.pdf"], "the only buttons are a file's Open and Download (row 1221)")

    STUB = """(() => { window.seen = []; window.opened = []; window.saved = [];
        const real = window.fetch.bind(window);
        window.fetch = (url, opts) => { if (String(url).startsWith('/api/section-file')) { window.seen.push([String(url), (opts && opts.headers && opts.headers['X-Clark-Token']) ? 'token' : 'no token']);
            return Promise.resolve(new Response(new Blob(['fictional bytes'], {type: 'application/pdf'}), {status: 200})); } return real(url, opts); };
        window.open = (u, t) => ({closed: false, close() { this.closed = true; }, set location(h) { window.opened.push(String(h).slice(0, 5)); }});   // the router points the tab with tab.location = url
        HTMLAnchorElement.prototype.click = function () { window.saved.push([this.download, this.href.slice(0, 5)]); }; })()"""

    def test_view_gives_a_file_row_open_and_download_that_read_through_clark(self):
        """Row 1221: in the editor's View a file row has Open and Download (44 px, named, at 1400 and 900), and each asks
        GET /api/section-file with the token, the project and the file's name; Open uses a new tab, Download the browser's save.
        A link row has neither (it has its own link)."""
        ref = self.add([a_file("Plan v2.pdf"), a_link()])
        sel = f"[data-id={json.dumps(ref)}]"
        with chrome() as cdp:
            p = self.visit(cdp)
            p.until(f"!!document.querySelector('{sel} .tpl-dl')", "the list drew")
            p.js(self.STUB)
            for w in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 1000, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                got = p.js(f"[...document.querySelectorAll('{sel} .tpl-dl-i')].map(li => [...li.querySelectorAll('button.tpl-act')].map(b => "
                           "[b.getAttribute('aria-label'), b.title, Math.round(b.getBoundingClientRect().height) >= 44]))")
                self.assertEqual(got, [[["Open Plan v2.pdf", "Open", True], ["Download Plan v2.pdf", "Download", True]], []], w)
                self.assertLessEqual(p.js("document.documentElement.scrollWidth"), w, "no sideways scroll")
            p.js(f"document.querySelectorAll('{sel} button.tpl-act')[0].click()")
            p.until("window.opened.length === 1", "Open opened the file in a new tab")
            p.js(f"document.querySelectorAll('{sel} button.tpl-act')[1].click()")
            p.until("window.saved.length === 1", "Download saved the file")
            self.assertEqual(p.js("window.seen"), [["/api/section-file?project=ABC&name=Plan%20v2.pdf", "token"],
                                                   ["/api/section-file?project=ABC&name=Plan%20v2.pdf&download=1", "token"]])
            self.assertEqual(p.js("window.saved"), [["Plan v2.pdf", "blob:"]])
            self.assertEqual(p.js("window.opened"), ["blob:"])

    def test_the_page_icon_colours_are_the_badge_tokens_not_literals(self):
        """Row 1194 read (colour literals): the drawn icon takes its colours from the --badge-* tokens, none is a hex literal."""
        src = (SRC / "clark" / "page" / "src" / "templates" / "docIcons.jsx").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"#[0-9A-Fa-f]{3,6}\b|rgba?\(", src), [], "no colour literal in docIcons.jsx")
        ref = self.add([a_file("Plan v2.pdf"), a_file("Notes.txt", 2048)])
        sel = f"[data-id={json.dumps(ref)}]"
        with chrome() as cdp:
            p = self.visit(cdp)
            p.until(f"!!document.querySelector('{sel} .tpl-dl')", "the list drew")
            got = p.js(f"[...document.querySelectorAll('{sel} .tpl-badge svg')].map(s => [getComputedStyle(s.querySelector('g[fill] path')).stroke, getComputedStyle([...s.querySelectorAll('path')].pop()).fill, getComputedStyle(s.querySelector('text')).fill])")
            want = p.js("(() => { const t = document.createElement('i'); document.body.append(t); const c = v => { t.style.color = v; return getComputedStyle(t).color; }; "
                        "const r = [[c('var(--badge-pdf)'), c('var(--badge-pdf)'), c('var(--white)')], [c('var(--badge-txt)'), c('var(--badge-txt)'), c('var(--white)')]]; t.remove(); return r; })()")
            self.assertEqual(got, want)


class ClassicLook(ClassicView):
    """Item 1194: what the approved mockup shows in View, at 1400 and 900 px."""

    def widths(self, p, cdp):
        for w in (1400, 900):
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 1000, "deviceScaleFactor": 1, "mobile": False}, p.sid)
            yield w

    def test_view_rows_have_page_icons_type_words_and_icon_buttons(self):
        ref = self.add([a_file("Scope statement.docx", 88 * 1024), a_file("Site photo.png", 1126 * 1024), a_file("Notes.txt", 2048),
                        a_link("https://www.example.org/x", "some notes"), a_link("mailto:pmo@example.com", "Ask the PMO")])
        sel = f"[data-id={json.dumps(ref)}]"
        with chrome() as cdp:
            p = self.visit(cdp)
            p.until(f"!!document.querySelector('{sel} .tpl-dl')", "the list drew")
            for w in self.widths(p, cdp):
                self.assertEqual(p.js(f"[...document.querySelectorAll('{sel} .tpl-facts')].map(e => e.textContent)"),
                                 ["Word · 88 KB", "Image · 1.1 MB", "File · 2 KB", "Web link · example.org", "Email link · pmo@example.com"], w)
                self.assertEqual(p.js(f"[...document.querySelectorAll('{sel} .tpl-badge')].map(e => e.textContent)"),
                                 ["DOC", "PNG", "TXT", "URL", "@"], w)
                self.assertEqual(p.js(f"[...document.querySelectorAll('{sel} .tpl-badge')].map(e => !!e.querySelector('svg') && Math.round(e.getBoundingClientRect().height))"),
                                 [41] * 5, f"a page icon 41 px tall at {w}")
                self.assertEqual(p.js(f"[...document.querySelectorAll('{sel} a.tpl-act')].map(a => !!a.querySelector('svg') && a.textContent.trim() === '' && "
                                      "a.getBoundingClientRect().width >= 44 && a.getBoundingClientRect().height >= 44)"), [True] * 2,
                                 f"Open is a 44 px icon at {w} (links only: a file's Open and Download are drawn in the published file, see Published)")

    def test_view_rows_match_the_mockup_sizes_and_spacing(self):
        ref = self.add([a_link("https://www.example.org/x", "some notes"), a_link("mailto:pmo@example.com", "Ask the PMO")])
        sel = f"[data-id={json.dumps(ref)}]"
        with chrome() as cdp:
            p = self.visit(cdp)
            p.until(f"!!document.querySelector('{sel} .tpl-dl')", "the list drew")
            for w in self.widths(p, cdp):
                got = p.js(f"(() => {{ const li = document.querySelector('{sel} .tpl-dl-i'), n = li.querySelector('.tpl-name'), cs = (e, k) => getComputedStyle(e)[k];"
                           " return [cs(li, 'borderTopLeftRadius'), cs(li, 'padding'), Math.round(li.getBoundingClientRect().height), cs(n, 'fontSize'), cs(n, 'fontWeight')]; })()")
                self.assertEqual(got, ["12px", "8px 10px 8px 14px", 62, "16px", "500"], w)


class InThePage(PageBase):
    """The served View and the file draw the same entries; Edit adds and removes a link, one step each."""

    def add(self, items, title="Fictional papers", kind="doclinks"):
        with self.store.step("dashboard", USER) as st:
            ref = st.create("report_sections", {"project": "ABC", "type": kind, "title": title, "sort_order": 999})
        if items is not None:
            with self.store.step("dashboard", USER) as st:
                st.update("report_sections", ref, {"body": store_module.check_section_body(kind, body(items))})
        return ref

    def entries(self, p, ref):
        return p.js(f"[...document.querySelectorAll('[data-id={json.dumps(ref)}] .tpl-dl-i')].map(li => "
                    "[li.querySelector('.tpl-badge').textContent, li.querySelector('.tpl-name').textContent, "
                    "li.querySelector('.tpl-name').tagName, li.querySelector('.tpl-name').getAttribute('href')])")

    def test_view_draws_the_list_and_an_empty_one_is_left_out(self):
        ref = self.add([a_link(), a_link(href="mailto:team@example.org", label="Team"), a_file()])
        empty = self.add([], "Fictional empty papers")
        with chrome() as cdp:
            p = self.visit(cdp)
            p.until(f"!!document.querySelector('[data-id={json.dumps(ref)}] .tpl-dl')", "the list drew")
            self.assertEqual(self.entries(p, ref), [
                ["Link", "The plan", "A", "https://example.org/plan"],
                ["Link", "Team", "A", "mailto:team@example.org"],
                ["PDF", "Plan v2.pdf", "SPAN", None]], "the page clark serves names a file without linking it")
            self.assertFalse(p.js(f"!!document.querySelector('[data-id={json.dumps(empty)}]')"), "an empty list is left out of View")
            self.assertEqual(p.js(f"document.querySelectorAll('[data-id={json.dumps(ref)}] input').length"), 0, "View is read only")
            self.assertEqual(p.js(f"[...document.querySelectorAll('[data-id={json.dumps(ref)}] button')].map(b => b.getAttribute('aria-label'))"),
                             ["Open Plan v2.pdf", "Download Plan v2.pdf"], "the only buttons are a file's Open and Download (row 1221)")

    STUB = """(() => { window.seen = []; window.opened = []; window.saved = [];
        const real = window.fetch.bind(window);
        window.fetch = (url, opts) => { if (String(url).startsWith('/api/section-file')) { window.seen.push([String(url), (opts && opts.headers && opts.headers['X-Clark-Token']) ? 'token' : 'no token']);
            return Promise.resolve(new Response(new Blob(['fictional bytes'], {type: 'application/pdf'}), {status: 200})); } return real(url, opts); };
        window.open = (u, t) => ({closed: false, close() { this.closed = true; }, set location(h) { window.opened.push(String(h).slice(0, 5)); }});   // the router points the tab with tab.location = url
        HTMLAnchorElement.prototype.click = function () { window.saved.push([this.download, this.href.slice(0, 5)]); }; })()"""

    def test_view_gives_a_file_row_open_and_download_that_read_through_clark(self):
        """Row 1221: in the editor's View a file row has Open and Download (44 px, named, at 1400 and 900), and each asks
        GET /api/section-file with the token, the project and the file's name; Open uses a new tab, Download the browser's save.
        A link row has neither (it has its own link)."""
        ref = self.add([a_file("Plan v2.pdf"), a_link()])
        sel = f"[data-id={json.dumps(ref)}]"
        with chrome() as cdp:
            p = self.visit(cdp)
            p.until(f"!!document.querySelector('{sel} .tpl-dl')", "the list drew")
            p.js(self.STUB)
            for w in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 1000, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                got = p.js(f"[...document.querySelectorAll('{sel} .tpl-dl-i')].map(li => [...li.querySelectorAll('button.tpl-act')].map(b => "
                           "[b.getAttribute('aria-label'), b.textContent, Math.round(b.getBoundingClientRect().height) >= 44]))")
                self.assertEqual(got, [[["Open Plan v2.pdf", "Open", True], ["Download Plan v2.pdf", "Download", True]], []], w)
                self.assertLessEqual(p.js("document.documentElement.scrollWidth"), w, "no sideways scroll")
            p.js(f"document.querySelectorAll('{sel} button.tpl-act')[0].click()")
            p.until("window.opened.length === 1", "Open opened the file in a new tab")
            p.js(f"document.querySelectorAll('{sel} button.tpl-act')[1].click()")
            p.until("window.saved.length === 1", "Download saved the file")
            self.assertEqual(p.js("window.seen"), [["/api/section-file?project=ABC&name=Plan%20v2.pdf", "token"],
                                                   ["/api/section-file?project=ABC&name=Plan%20v2.pdf&download=1", "token"]])
            self.assertEqual(p.js("window.saved"), [["Plan v2.pdf", "blob:"]])
            self.assertEqual(p.js("window.opened"), ["blob:"])

    def test_edit_adds_a_link_in_one_step_and_undo_takes_it_back(self):
        ref = self.add([a_link()])
        sel = f"[data-id={json.dumps(ref)}]"
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            p.until(f"!!document.querySelector('{sel} [data-add-link]')", "the Edit part drew")
            self.set_value(p, f"{sel} [data-add-link] input[type=text]", "https://example.org/budget", 0)
            self.set_value(p, f"{sel} [data-add-link] input[type=text]", "Budget", 1)
            p.js(f"document.querySelector('{sel} [data-add-link] button[type=submit]').click()")
            p.until(f"document.querySelectorAll('{sel} .tpl-dl-i').length === 2", "the new link is drawn")
            stored = json.loads(self.store.read("report_sections", ref=ref)["body"])["items"]
            self.assertEqual(stored[-1], {"kind": "link", "href": "https://example.org/budget", "label": "Budget"})
            p.until("!!document.querySelector('[data-undo]')", "the toast offers Undo")
            p.js("document.querySelector('[data-undo]').click()")
            p.until(f"document.querySelectorAll('{sel} .tpl-dl-i').length === 1", "Undo took it back")
            self.assertEqual(json.loads(self.store.read("report_sections", ref=ref)["body"])["items"], [a_link()])
            p.js(f"document.querySelector('{sel} .tpl-remove').click()")
            p.until(f"document.querySelectorAll('{sel} .tpl-dl-i').length === 0", "Remove took it off")
            self.assertEqual(json.loads(self.store.read("report_sections", ref=ref)["body"])["items"], [])

    def test_edit_refuses_a_bad_link_in_words_and_sends_nothing(self):
        ref = self.add([])
        sel = f"[data-id={json.dumps(ref)}]"
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            p.until(f"!!document.querySelector('{sel} [data-add-link]')", "the Edit part drew")
            self.assertIn("stays out of the published page", p.js(f"document.querySelector('{sel} .tpl-empty').textContent"))
            sent = len(self.sent)
            for bad in ("javascript:alert(1)", "http://example.org", "example.org"):
                self.set_value(p, f"{sel} [data-add-link] input[type=text]", bad, 0)
                p.js(f"document.querySelector('{sel} [data-add-link] button[type=submit]').click()")
                p.until(f"!!document.querySelector('{sel} .tpl-problem')", "the refusal is shown")
                self.assertEqual(p.js(f"document.querySelector('{sel} .tpl-problem').textContent"), doclinks.BAD_LINK)
            self.assertEqual(len(self.sent), sent, "nothing was sent")
            self.assertEqual(p.js(f"document.querySelector('{sel} .tpl-problem').getAttribute('role')"), "alert")
            p.js(f"document.querySelector('{sel} [data-add-file]').focus()")
            self.assertTrue(p.js("document.activeElement.hasAttribute('data-add-file')"), "Add a file takes focus from the keyboard")

    @staticmethod
    def set_value(p, selector, value, index=0):
        p.js(f"(() => {{ const el = document.querySelectorAll({json.dumps(selector)})[{index}]; el.focus(); el.value = {json.dumps(value)};"
             " el.dispatchEvent(new Event('input', {bubbles: true})); })()")


class Published(PageBase):
    """The published file draws the list from its own data block: a file as a link relative to the report, a link to its page."""

    def test_the_file_draws_the_list_at_both_widths_light_and_dark(self):
        ref = InThePage.add(self, [a_link(), a_file(name="Plan v2#1.pdf", label="The plan, signed")])
        hidden = InThePage.add(self, [a_link(label=MARK)], "Fictional hidden papers")
        with self.store.step("dashboard", USER) as st:
            st.update("report_sections", hidden, {"hidden": 1})
        out = tempfile.mkdtemp(prefix="clark-96-g7-")
        self.addCleanup(shutil.rmtree, out, ignore_errors=True)
        done = publish.publish(self.store, "ABC", out, by_user=USER, now="2030-01-15", branding=EMPTY_BRANDING)
        path = Path(done["path"])
        text = path.read_text(encoding="utf-8")
        self.assertNotIn(MARK, text)
        self.assertNotIn("Fictional hidden papers", text)
        for width, dark in ((1400, False), (900, True), (900, False), (1400, True)):
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
                sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1000, "deviceScaleFactor": 1, "mobile": False}, sid)
                cdp.call("Page.navigate", {"url": path.as_uri()}, sid)
                p = Pg(self, cdp, sid)
                p.until("document.documentElement.dataset.ready === '1' && !!document.querySelector('h1')", "the file drew")
                if dark:
                    p.js("document.documentElement.dataset.theme = 'dark'")
                p.until(f"!!document.querySelector('[data-id={json.dumps(ref)}] .tpl-dl')", "the list is in the file")
                self.assertEqual(InThePage.entries(self, p, ref), [
                    ["URL", "The plan", "A", "https://example.org/plan"],
                    ["PDF", "The plan, signed", "A", "Report%20files/Plan%20v2%231.pdf"]])
                self.assertEqual(p.js(f"[...document.querySelectorAll('[data-id={json.dumps(ref)}] .tpl-facts')].map(e => e.textContent)"),
                                 ["Web link · example.org", "PDF · 340 KB"])
                self.assertEqual(p.js(f"[...document.querySelectorAll('[data-id={json.dumps(ref)}] .tpl-dl-i')].map(li => "
                                      "[...li.querySelectorAll('a.tpl-act')].map(a => a.getAttribute('aria-label') + ':' + a.hasAttribute('download') + ':' + a.target))"),
                                 [["Open The plan:false:_blank"], ["Open The plan, signed:false:_blank", "Download The plan, signed:true:"]], "Open on every row, Download on files only")
                self.assertEqual(p.js("document.querySelectorAll('.tpl-dl input, .tpl-dl button, .tpl-form').length"), 0)
                self.assertEqual(p.js("[...document.querySelectorAll('.tpl-dl a.tpl-act')].every(a => a.rel === 'noopener noreferrer' || a.hasAttribute('download'))"), True)
                self.assertFalse(p.js(f"!!document.querySelector('[data-id={json.dumps(hidden)}]')"))
                self.assertLessEqual(p.js("document.documentElement.scrollWidth"), width, "no sideways scroll")
                rels = p.js(f"[...document.querySelectorAll('[data-id={json.dumps(ref)}] a.tpl-name, [data-id={json.dumps(ref)}] a.tpl-act:not([download])')].map(a => a.className + ':' + a.target + ':' + a.rel)")
                self.assertEqual(rels, ["tpl-name:_blank:noopener noreferrer", "tpl-act:_blank:noopener noreferrer",
                                        "tpl-name:_blank:noopener noreferrer", "tpl-act:_blank:noopener noreferrer"],
                                 "row 1194 read (B1): each name link and each Open link opens a new tab with rel noopener noreferrer")

    def test_the_published_page_carries_no_edit_part(self):
        view = (SRC / "clark" / "page" / "page-view.html").read_text(encoding="utf-8")
        for words in ("Add a file", "api/section-file", "tpl-form", "Choose the file", "Save card"):
            self.assertNotIn(words, view)


if __name__ == "__main__":
    unittest.main()
