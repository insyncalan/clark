"""#96 G7, Documents and links (store type "doclinks"): the content's checker and its limits, hostile input, one save one step one
Undo, what the published file carries (a hidden or empty section is left out; a marker scan of the file), and the page: the
served View and the published file draw the same list, Edit adds and removes a link in one step each, and refuses a bad link
in words before anything is sent. The file part (Add a file) is tests/test_section_file_route.py.

Run: python3 dev/run_tests.py test_tpl_doclinks
Needs Chrome (the #33 harness): the page tests fail, never skip, without it. Fictional data only. Laptop widths 1400 and 900 px,
light and dark.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from _demo import USER
from _paths import SRC
from clark import changes, publish, section_bodies, store as store_module
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
                self.refused("doclinks", body([a_file(name=name)]), doclinks.BAD_FILE if name.endswith(" ") else doclinks.bad_type(name))

    def test_the_refusal_names_the_allowed_types_and_add_file_meets_the_same_rule(self):
        for word in ("PDF", "Word", "Excel", "PowerPoint", "JPG", "PNG", "TXT"):
            self.assertIn(word, doclinks.BAD_TYPE_TAIL)
        with self.assertRaises(section_bodies.Bad) as e:
            doclinks.add_file(None, {"name": "a.zip", "rel": "Report files/a.zip", "bytes": 1})
        self.assertEqual(str(e.exception), doclinks.bad_type("a.zip"))

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

    def test_the_refusal_for_a_file_names_the_file(self):
        """Item 1194 (ruled 15-11): '{file name}: That type of file can't be added. Use PDF, Word, Excel, PowerPoint, JPG, PNG or TXT.'"""
        tail = "That type of file can't be added. Use PDF, Word, Excel, PowerPoint, JPG, PNG or TXT."
        self.refused("doclinks", body([a_link(), a_file(name="Setup tool.zip")]), "Setup tool.zip: " + tail)
        with self.assertRaises(section_bodies.Bad) as e:
            doclinks.add_file(None, {"name": "run me.exe", "rel": "Report files/run me.exe", "bytes": 1})
        self.assertEqual(str(e.exception), "run me.exe: " + tail)

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
        self.refused("doclinks", body([a_link(label=MARK * 10)]), doclinks.BAD_LABEL)
        self.refused("doclinks", body([a_link(label=12)]), doclinks.BAD_LABEL)

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
        self.assertEqual(got["message"], doclinks.BAD_LINK)
        self.assertNotIn(MARK, json.dumps(got))
        self.assertEqual(self.snapshot(), before)

    def stored(self, ref, text):
        """Put `text` in the section's body as an older clark, or a hand edit, could have left it (no checker in the way)."""
        self.s.con.execute("UPDATE report_sections SET body = ? WHERE id = ?", (text, ref))
        self.s.con.commit()
        self.assertEqual(self.s.read("report_sections", ref=ref)["body"], text)

    def test_stored_content_the_new_rules_refuse_drops_the_section_and_refuses_every_save_PINNED_BEHAVIOUR(self):
        """Item 1194 made a link description required and a file ending allowed. Content stored BEFORE that (a link with no words, a
        file ending in .zip) no longer checks, so: publish leaves the whole section out (never repaired, never half drawn) and a
        save that still carries that entry is refused in the plain words. Removing the old entry (or giving it words) makes the
        section saveable and published again. This pins the behaviour; there is no fallback that keeps old entries."""
        for name, old, words in (("link with no words", a_link(label=""), "Link 2: Enter a link description."),
                                 ("file with an ending that is not allowed", a_file(name="old.zip"), "old.zip: " + doclinks.BAD_TYPE_TAIL)):
            with self.subTest(old=name):
                ref = self.make("Fictional old " + name)
                self.stored(ref, body([a_link(), old]))
                built = publish.build(self.s, "ABC", now="2030-01-15")
                self.assertNotIn(ref, {s["id"] for s in built["published"]["sections"]}, "the whole section is left out, the good link too")
                before = self.snapshot()
                status, got = self.save(ref, body([a_link(), old, a_link(href="https://example.org/new", label="New")]))
                self.assertEqual((status, got["message"]), (400, words))
                self.assertEqual(self.snapshot(), before, "a refused save writes nothing")
                status, got = self.save(ref, body([a_link()]))
                self.assertEqual(status, 200, got)
                built = publish.build(self.s, "ABC", now="2030-01-15")
                self.assertEqual([i["href"] for i in next(s for s in built["published"]["sections"] if s["id"] == ref)["content"]["items"]],
                                 ["https://example.org/plan"], "once the old entry is gone the section is published again")

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
                ["URL", "The plan", "SPAN", None],
                ["MAIL", "Team", "SPAN", None],
                ["PDF", "Plan v2.pdf", "SPAN", None]], "in the editor's View a name stays plain text")
            self.assertEqual(p.js(f"[...document.querySelectorAll('[data-id={json.dumps(ref)}] .tpl-dl-i a.tpl-act')].map(a => a.getAttribute('aria-label') + ' ' + a.getAttribute('href'))"),
                             ["Open The plan https://example.org/plan", "Open Team mailto:team@example.org"], "a link gets Open only")
            self.assertFalse(p.js(f"!!document.querySelector('[data-id={json.dumps(empty)}]')"), "an empty list is left out of View")
            self.assertEqual(p.js(f"document.querySelectorAll('[data-id={json.dumps(ref)}] input, [data-id={json.dumps(ref)}] button').length"), 0,
                             "View is read only")

    def test_edit_adds_a_link_in_one_step_and_undo_takes_it_back(self):
        ref = self.add([a_link()])
        sel = f"[data-id={json.dumps(ref)}]"
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            p.until(f"!!document.querySelector('{sel} [data-open-link]')", "the Edit part drew")
            p.js(f"document.querySelector('{sel} [data-open-link]').click()")
            p.until(f"!!document.querySelector('{sel} [data-add-link]')", "the add-link box opened")
            self.assertEqual(p.js(f"[...document.querySelectorAll('{sel} [data-add-link] label')].map(l => l.textContent)"),
                             ["Link", DESCRIPTION_LABEL])
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
            p.until(f"!!document.querySelector('{sel} [data-open-link]')", "the Edit part drew")
            self.assertEqual(p.js(f"document.querySelector('{sel} .tpl-empty').textContent"), EMPTY_STATE)
            p.js(f"document.querySelector('{sel} [data-open-link]').click()")
            p.until(f"!!document.querySelector('{sel} [data-add-link]')", "the add-link box opened")
            sent = len(self.sent)
            self.set_value(p, f"{sel} [data-add-link] input[type=text]", "https://example.org/ok", 0)
            p.js(f"document.querySelector('{sel} [data-add-link] button[type=submit]').click()")
            p.until(f"!!document.querySelector('{sel} .tpl-problem')", "the missing description is refused")
            self.assertEqual(p.js(f"document.querySelector('{sel} .tpl-problem').textContent"), "Link 1: Enter a link description.")
            for bad in ("javascript:alert(1)", "http://example.org", "example.org"):
                self.set_value(p, f"{sel} [data-add-link] input[type=text]", bad, 0)
                p.js(f"document.querySelector('{sel} [data-add-link] button[type=submit]').click()")
                p.until(f"!!document.querySelector('{sel} .tpl-problem')", "the refusal is shown")
                self.assertEqual(p.js(f"document.querySelector('{sel} .tpl-problem').textContent"), doclinks.BAD_LINK)
            self.assertEqual(len(self.sent), sent, "nothing was sent")
            self.assertEqual(p.js(f"document.querySelector('{sel} .tpl-problem').getAttribute('role')"), "alert")
            p.js(f"document.querySelector('{sel} [data-add-file]').focus()")
            self.assertTrue(p.js("document.activeElement.hasAttribute('data-add-file')"), "Add a file takes focus from the keyboard")

    def test_edit_refusal_for_the_add_link_box_counts_files_too(self):
        """Item 1194: with one link and one file listed the box says 'Link 3: ...' (n counts files too), not always 'Link 1: ...'."""
        ref = self.add([a_link(), a_file()])
        sel = f"[data-id={json.dumps(ref)}]"
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            p.until(f"!!document.querySelector('{sel} [data-open-link]')", "the Edit part drew")
            p.js(f"document.querySelector('{sel} [data-open-link]').click()")
            p.until(f"!!document.querySelector('{sel} [data-add-link]')", "the add-link box opened")
            sent = len(self.sent)
            self.set_value(p, f"{sel} [data-add-link] input[type=text]", "https://example.org/ok", 0)
            p.js(f"document.querySelector('{sel} [data-add-link] button[type=submit]').click()")
            p.until(f"!!document.querySelector('{sel} [data-add-link] .tpl-problem')", "the missing description is refused")
            self.assertEqual(p.js(f"document.querySelector('{sel} [data-add-link] .tpl-problem').textContent"), "Link 3: Enter a link description.")
            self.assertEqual(len(self.sent), sent, "nothing was sent")

    def test_edit_renames_in_place_and_moves_rows_one_step_each(self):
        ref = self.add([a_link(), a_file()])
        sel = f"[data-id={json.dumps(ref)}]"
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            p.until(f"document.querySelectorAll('{sel} .tpl-dl-i').length === 2", "the rows drew")
            self.assertEqual(p.js(f"[...document.querySelectorAll('{sel} .tpl-dl-i')].map(li => li.querySelector('[data-up]').disabled + ':' + li.querySelector('[data-down]').disabled)"),
                             ["true:false", "false:true"], "move is disabled at the ends")
            p.js(f"document.querySelectorAll('{sel} [data-down]')[0].click()")
            p.until(f"document.querySelector('{sel} .tpl-dl-i .tpl-badge').textContent === 'PDF'", "the file moved up")
            self.assertEqual([i["kind"] for i in json.loads(self.store.read("report_sections", ref=ref)["body"])["items"]], ["file", "link"])
            self.assertEqual(p.js(f"document.querySelectorAll('{sel} [data-rename]').length"), 0, "no Rename button: the name is the box")
            RenameTest.type(p, sel, "Signed plan", "Enter", 0)
            p.until("document.querySelector('.toast') && document.querySelector('.toast').textContent.includes('Name saved')", "the name was saved")
            self.assertEqual(json.loads(self.store.read("report_sections", ref=ref)["body"])["items"][0]["label"], "Signed plan")
            self.assertEqual(json.loads(self.store.read("report_sections", ref=ref)["body"])["items"][0]["name"], "Plan v2.pdf")
            RenameTest.type(p, sel, "Other", "Escape", 0)
            p.until(f"document.querySelector('{sel} input[data-rename-input]').value === 'Signed plan'", "Esc put the name back")
            self.assertEqual(json.loads(self.store.read("report_sections", ref=ref)["body"])["items"][0]["label"], "Signed plan", "Esc changes nothing")
            RenameTest.type(p, sel, "", "Enter", 1)
            p.until(f"document.querySelectorAll('{sel} input[data-rename-input]')[1].value === 'The plan'", "an empty name goes back")
            self.assertEqual(json.loads(self.store.read("report_sections", ref=ref)["body"])["items"][1]["label"], "The plan", "an empty name reverts")

    @staticmethod
    def set_value(p, selector, value, index=0):
        p.js(f"(() => {{ const el = document.querySelectorAll({json.dumps(selector)})[{index}]; el.focus(); el.value = {json.dumps(value)};"
             " el.dispatchEvent(new Event('input', {bubbles: true})); })()")


ALLOWED_NOTE = ("Files you can add: PDF, Word (.doc .docx), Excel (.xls .xlsx .csv), PowerPoint (.ppt .pptx), JPG, PNG and TXT. Not allowed: "
                "HTML, SVG, ZIP and any program or script, because they can run code or hide what is inside. Links (to a SharePoint file, "
                "a web page or an email): https:// or mailto:.")       # UNRULED: the mockup's words, verbatim


class MockupLook(InThePage):
    """Item 1194: what the approved mockup shows, at 1400 and 900 px (page icon 41 px tall, icon buttons, name box in place, add-link box)."""

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
                                 ["DOC", "PNG", "TXT", "URL", "MAIL"], w)
                self.assertEqual(p.js(f"[...document.querySelectorAll('{sel} .tpl-badge')].map(e => !!e.querySelector('svg') && Math.round(e.getBoundingClientRect().height))"),
                                 [41] * 5, f"a page icon 41 px tall at {w}")
                self.assertEqual(p.js(f"[...document.querySelectorAll('{sel} a.tpl-act')].map(a => !!a.querySelector('svg') && a.textContent.trim() === '' && "
                                      "a.getBoundingClientRect().width >= 44 && a.getBoundingClientRect().height >= 44)"), [True] * 2,
                                 f"Open is a 44 px icon at {w} (links only: a file's Open and Download are drawn in the published file, see Published)")

    def test_edit_rows_have_icon_remove_a_name_box_notes_and_the_link_box_in_place(self):
        ref = self.add([a_file("Scope statement.docx", 88 * 1024), a_link()])
        sel = f"[data-id={json.dumps(ref)}]"
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            p.until(f"!!document.querySelector('{sel} [data-open-link]')", "the Edit part drew")
            for w in self.widths(p, cdp):
                self.assertEqual(p.js(f"[...document.querySelectorAll('{sel} .tpl-badge')].map(e => !!e.querySelector('svg') && Math.round(e.getBoundingClientRect().height))"),
                                 [41, 41], f"a page icon 41 px tall at {w}")
                self.assertEqual(p.js(f"[...document.querySelectorAll('{sel} .tpl-remove')].map(b => !!b.querySelector('svg') && b.textContent.trim() === '' && b.getAttribute('aria-label'))"),
                                 ["Remove Scope statement.docx", "Remove The plan"], w)
                self.assertEqual(p.js(f"[...document.querySelectorAll('{sel} input[data-rename-input]')].map(i => i.value)"), ["Scope statement.docx", "The plan"], w)
                self.assertEqual(p.js(f"document.querySelector('{sel} .tpl-allowed').textContent"), ALLOWED_NOTE, w)
                self.assertIn("Name: click to rename, Enter saves, Esc cancels.", p.js(f"document.querySelector('{sel} .tpl-hint').textContent"))
                p.js(f"document.querySelector('{sel} [data-open-link]').click()")
                p.until(f"!!document.querySelector('{sel} [data-add-link]')", "the add-link box opened")
                box = p.js(f"(() => {{ const f = document.querySelector('{sel} [data-add-link]'), r = f.getBoundingClientRect(), l = document.querySelector('{sel} .tpl-dl').getBoundingClientRect();"
                           " return [getComputedStyle(f).position, r.top < l.bottom && r.bottom > l.top, r.right <= innerWidth]; })()")
                self.assertEqual(box, ["absolute", True, True], f"the box floats over the list under its icon at {w}")
                p.js(f"document.querySelector('{sel} [data-add-link] button[type=submit]').click()")
                p.until(f"!!document.querySelector('{sel} [data-add-link] .tpl-problem')", "the refusal is inside the box")
                p.js(f"document.querySelector('{sel} [data-open-link]').click()")
                p.until(f"!document.querySelector('{sel} [data-add-link]')", "the box closed")

    # Measured against docs-mockup.html in the same Chrome (item 1194): the sizes and colours that need no wording and no ruling.
    PROBE = ("(() => { const sec = document.querySelector(%s), q = s => sec.querySelector(s), cs = (e, k) => getComputedStyle(e)[k], R = e => e.getBoundingClientRect();"
             " const li = q('.tpl-dl-i'), nm = q('.tpl-rename, .tpl-name'), fx = q('.tpl-facts'), up = q('[data-up]'), dn = q('[data-down]'), rm = q('.tpl-remove'), ic = [...sec.querySelectorAll('.tpl-icons > button')],"
             " al = q('.tpl-allowed'), hint = q('.tpl-hint'), head = sec.querySelector('.sec-head'), list = q('.tpl-dl'), svg = q('.tpl-badge svg text');"
             " const inset = nm.matches('input') ? 1 + parseFloat(cs(nm, 'paddingLeft')) : 0;"
             " return {row: [cs(li, 'borderTopLeftRadius'), cs(li, 'padding'), Math.round(R(li).height)], name: [cs(nm, 'fontSize'), cs(nm, 'fontWeight')],"
             " align: Math.round((R(nm).left + inset - R(fx).left) * 10) / 10, mark: [up, dn, rm].map(b => [cs(b, 'borderTopWidth'), cs(b, 'borderTopLeftRadius'), Math.round(R(b).width), Math.round(R(b).height), cs(b.querySelector('svg'), 'strokeWidth')]),"
             " off: cs(up, 'opacity'), head: ic.map(b => [cs(b, 'borderTopWidth'), cs(b.querySelector('svg'), 'strokeWidth'), cs(b, 'color'), cs(b, 'borderTopColor'), Math.round(R(b).top + R(b).height / 2 - (R(head).top + R(head).height / 2))]),"
             " gap: Math.round(R(list).top - R(ic[0]).top), allowed: [cs(al, 'fontSize'), cs(al, 'padding'), cs(al, 'borderTopLeftRadius')], hint: cs(hint, 'fontSize'), font: svg.getAttribute('font-family'), step: [Math.round(R(dn).left - R(up).left), Math.round(R(rm).left - R(dn).left)], facts: Math.round(R(fx).height * 10) / 10}; })()")

    def test_edit_matches_the_mockup_sizes_spacing_and_icon_colours(self):
        ref = self.add([a_file("Scope statement.docx", 88 * 1024), a_link()])
        sel = f"[data-id={json.dumps(ref)}]"
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            p.until(f"!!document.querySelector('{sel} [data-open-link]')", "the Edit part drew")
            for w in self.widths(p, cdp):
                got = p.js(self.PROBE % json.dumps(sel))
                self.assertEqual(got["row"], ["12px", "8px 10px 8px 14px", 62], f"row radius, padding and height at {w}")
                self.assertEqual(got["name"], ["16px", "500"], w)
                self.assertLessEqual(abs(got["align"]), 1, f"the name box's text lines up with the facts line at {w}")
                self.assertEqual(got["mark"], [["0px", "10px", 44, 44, "1.8px"]] * 3, f"move and remove: borderless 44 px icons, 1.8 stroke, at {w}")
                self.assertEqual(got["off"], "0.3", w)
                self.assertEqual(got["step"], [46, 46], f"the three icon buttons are 2 px apart at {w}")
                self.assertEqual(got["facts"], 16.9, f"the facts line is 13 px on a 1.3 line at {w}")
                self.assertEqual([h[:4] for h in got["head"]], [["1px", "1.8px", "rgb(14, 36, 48)", "rgb(217, 224, 239)"]] * 2, f"file and link icon buttons at {w}")
                self.assertLessEqual(max(abs(h[4]) for h in got["head"]), 2, f"the icon buttons sit on the title's line at {w}")
                self.assertIn(got["gap"], range(56, 61), f"the list starts 58 px under the icon buttons' top at {w}")
                self.assertEqual(got["allowed"], ["12.5px", "10px 14px", "12px"], w)
                self.assertEqual(got["hint"], "12px", w)
                self.assertTrue(got["font"].startswith("Inter"), "the label band uses the page font")

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

    def test_toasts_say_what_the_ticket_quotes(self):
        ref = self.add([a_file("Scope statement.docx", 88 * 1024)])
        sel = f"[data-id={json.dumps(ref)}]"
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            p.until(f"!!document.querySelector('{sel} [data-open-link]')", "the Edit part drew")
            p.js(f"document.querySelector('{sel} [data-open-link]').click()")
            p.until(f"!!document.querySelector('{sel} [data-add-link]')", "the box opened")
            InThePage.set_value(p, f"{sel} [data-add-link] input[type=text]", "https://example.org/b", 0)
            InThePage.set_value(p, f"{sel} [data-add-link] input[type=text]", "Budget", 1)
            p.js(f"document.querySelector('{sel} [data-add-link] button[type=submit]').click()")
            p.until("!!document.querySelector('.toast')", "a toast")
            self.assertEqual(p.js("document.querySelector('.toast').textContent").replace("Undo", "").replace("Close", "").strip(), "Link added")
            p.js(f"document.querySelectorAll('{sel} .tpl-remove')[0].click()")
            p.until("document.querySelector('.toast').textContent.includes('Removed')", "the remove toast")
            self.assertEqual(p.js("document.querySelector('.toast').textContent").replace("Undo", "").replace("Close", "").strip(), "Removed Scope statement.docx. The file stays in the client folder.")


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
                rel = p.js(f"document.querySelector('[data-id={json.dumps(ref)}] a.tpl-name').rel")
                self.assertEqual(rel, "noopener noreferrer")

    def test_the_published_page_carries_no_edit_part(self):
        view = (SRC / "clark" / "page" / "page-view.html").read_text(encoding="utf-8")
        for words in ("Add a file", "api/section-file", "tpl-form", "Choose the file", "Save card"):
            self.assertNotIn(words, view)


if __name__ == "__main__":
    unittest.main()
