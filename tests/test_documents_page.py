"""#74 Supporting documents on the page: Edit adds, edits, leaves out and adds back a document link, one step each with Undo from the
toast, by mouse and keyboard; View and the published file draw only the visible ones, as links with their kind, date and site name,
at 1400 and 900 px, light and dark, with no sideways scroll and nothing to type in.

Run: python3 dev/run_tests.py test_documents_page
Needs Chrome (the #33 harness): these tests fail, never skip, without it. Fictional data only (example.com).
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from _demo import USER
from clark import publish
from test_documents_published import check_in_file
from test_report_editor import EMPTY_BRANDING, Base as PageBase, Pg
from test_server import chrome

WIDTHS = ((1400, False), (900, True), (900, False), (1400, True))


class Page(PageBase):
    def docs_section(self):
        return next(r["id"] for r in self.store.read("report_sections", "ABC") if r["type"] == "docs")

    def add_doc(self, title, url, kind="Minutes", date="2030-01-10"):
        status, body = self.real_change({"project": "ABC", "kind": "documents", "op": "new", "place": "report",
                                         "values": {"title": title, "kind": kind, "url": url, "date": date}})
        self.assertEqual(status, 200, msg=f"adding the document should give status 200; it gave {status} {body}")
        return body["ref"]

    def hide(self, ref):
        status, body = self.real_change({"project": "ABC", "kind": "report_hidden", "op": "new", "id": ref, "place": "eye"})
        self.assertEqual(status, 200, msg=f"hiding the document should give status 200; it gave {status} {body}")

    def rows(self, p, sel):
        return p.js(f"[...document.querySelectorAll('{sel} .docs-list .tpl-dl-i')].map(li => [li.querySelector('.tpl-badge').textContent, "
                    "li.querySelector('.tpl-name').textContent, li.querySelector('.tpl-facts').textContent])")

    def view_rows(self, p, sel):
        """What a reader sees of each document in View and in a published file: title, the line under it, the open icon."""
        return p.js(f"[...document.querySelectorAll('{sel} .docs-list .tpl-dl-i')].map(li => [li.querySelector('.tpl-name').textContent, "
                    "li.querySelector('.tpl-facts').textContent, li.querySelector('a.docs-open').getAttribute('aria-label'), "
                    "li.querySelector('a.docs-open').getAttribute('href'), li.querySelector('a.docs-open').target, li.querySelector('a.docs-open').rel, "
                    "li.querySelector('a.docs-open svg').getAttribute('aria-hidden'), li.querySelectorAll('a').length])")

    @staticmethod
    def set_value(p, selector, value):
        p.js(f"(() => {{ const el = document.querySelector({json.dumps(selector)}); el.focus(); el.value = {json.dumps(value)};"
             " el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true})); })()")


class InEdit(Page):
    def test_add_edit_leave_out_and_add_back_each_with_undo(self):
        sec = f"[data-id={json.dumps(self.docs_section())}]"
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            p.until(f"!!document.querySelector('{sec} .docs-edit')", "the documents part drew")
            self.assertIn("No documents yet", p.js(f"document.querySelector('{sec} .tpl-empty').textContent"),
                          msg="with no document the part says 'No documents yet'")
            p.js(f"[...document.querySelectorAll('{sec} button')].find(b => b.textContent === 'Add a document link').click()")
            p.until(f"!!document.querySelector('{sec} .docs-form')", "the form opened")
            p.until("document.activeElement && document.activeElement.id === 'doc-new-title'", "the title box takes the focus")
            self.set_value(p, "#doc-new-title", "Steering minutes")
            self.set_value(p, "#doc-new-kind", "Minutes")
            self.set_value(p, "#doc-new-url", "javascript:alert(1)")
            p.js(f"document.querySelector('{sec} .docs-form button[type=submit]').click()")
            p.until("(document.querySelector('.toast-text') || {}).textContent === \"That link can't be used. It must start with https://, http:// or mailto:\"",
                    "the link rule's own words")
            self.assertEqual(self.store.read("documents", "ABC"), [], msg="nothing was saved")
            self.set_value(p, "#doc-new-url", "https://example.com/minutes")
            self.set_value(p, "#doc-new-date", "31-02-2030")
            p.js(f"document.querySelector('{sec} .docs-form button[type=submit]').click()")
            p.until(f"(document.querySelector('{sec} .tpl-problem') || {{}}).textContent === 'Write the date as DD-MM-YYYY (day, month, year), or leave it empty.'",
                    "a day that is not real is said in words, before anything is sent")
            self.set_value(p, "#doc-new-date", "10-01-2030")
            p.js(f"document.querySelector('{sec} .docs-form button[type=submit]').click()")
            p.until(f"document.querySelectorAll('{sec} .docs-list .tpl-dl-i').length === 1", "the new document is drawn")
            self.assertEqual(self.rows(p, sec), [["Minutes", "Steering minutes", "10-01-2030 · example.com"]],
                             msg="the new document is drawn with its kind, title, and the date and site under it")
            p.saved()
            p.js("document.querySelector('[data-undo]').click()")
            p.until(f"document.querySelectorAll('{sec} .docs-list .tpl-dl-i').length === 0", "Undo took the add back")
            self.assertEqual(self.store.read("documents", "ABC"), [], msg="after Undo no document is stored")
            p.clear_toast()

            ref = self.add_doc("Board pack", "https://example.com/board", kind="Report")
            p.reload()
            p.edit()
            p.until(f"document.querySelectorAll('{sec} .docs-list .tpl-dl-i').length === 1", "the document is drawn")
            p.js(f"document.querySelector('{sec} button[aria-label=\"Edit Board pack\"]').click()")
            p.until(f"!!document.querySelector('#doc-{ref}-title')", "the edit form opened")
            self.set_value(p, f"#doc-{ref}-title", "Board pack, signed")
            p.js(f"document.querySelector('{sec} .docs-form button[type=submit]').click()")
            p.until(f"document.querySelector('{sec} .docs-list .tpl-name').textContent === 'Board pack, signed'", "the edit is drawn")
            p.saved()
            self.assertEqual(self.store.read("documents", ref=f"ABC|{ref}")["title"], "Board pack, signed", msg="the edited title is stored")
            p.js("document.querySelector('[data-undo]').click()")
            p.until(f"document.querySelector('{sec} .docs-list .tpl-name').textContent === 'Board pack'", "Undo put the title back")
            p.clear_toast()

            p.js(f"document.querySelector('{sec} button[aria-label=\"Leave Board pack out of the published page\"]').click()")
            p.until(f"document.querySelectorAll('{sec} .docs-list .tpl-dl-i').length === 0", "left out")
            p.until(f"(document.querySelector('{sec} .docs-left summary') || {{}}).textContent === 'Add back a document (1)'", "listed to add back")
            self.assertEqual([r["item_id"] for r in self.store.read("report_hidden", "ABC")], [ref], msg="leaving the document out records it as hidden")
            p.saved()
            p.js("document.querySelector('[data-undo]').click()")
            p.until(f"document.querySelectorAll('{sec} .docs-list .tpl-dl-i').length === 1", "Undo showed it again")
            p.clear_toast()
            self.hide(ref)
            p.reload()
            p.edit()
            p.until(f"!!document.querySelector('{sec} .docs-left')", "the add back list")
            p.js(f"document.querySelector('{sec} .docs-left').open = true")
            p.js(f"document.querySelector('{sec} button[aria-label=\"Add Board pack back to the published page\"]').click()")
            p.until(f"document.querySelectorAll('{sec} .docs-list .tpl-dl-i').length === 1", "added back")
            self.assertEqual(self.store.read("report_hidden", "ABC"), [], msg="adding the document back leaves nothing hidden")

    def test_keyboard_esc_closes_the_form_and_gives_the_focus_back_at_both_widths(self):
        sec = f"[data-id={json.dumps(self.docs_section())}]"
        self.add_doc("Plan of record", "https://example.com/plan", kind="Plan")
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            for width, dark in WIDTHS:
                with self.subTest(width=width, dark=dark):
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                    p.js(f"document.documentElement.dataset.theme = '{'dark' if dark else 'light'}'")
                    p.until(f"!!document.querySelector('{sec} .docs-edit')", "the documents part drew")
                    p.js(f"document.querySelector('{sec} button[aria-label=\"Edit Plan of record\"]').focus()")
                    for kind in ("keyDown", "keyUp"):          # Enter on the focused button, as a person presses it
                        cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13,
                                                            **({"text": "\r"} if kind == "keyDown" else {})}, p.sid)
                    p.until("document.activeElement && document.activeElement.id.endsWith('-title')", "the form opened with the focus in it")
                    p.key("Escape", vk=27)
                    p.until(f"!document.querySelector('{sec} .docs-form')", "Esc closed it")
                    p.until("document.activeElement && document.activeElement.getAttribute('aria-label') === 'Edit Plan of record'", "the focus went back")
                    self.assertLessEqual(p.js("document.documentElement.scrollWidth"), width, msg="no sideways scroll")
                    small = p.js(f"[...document.querySelectorAll('{sec} .docs-edit button, {sec} .docs-edit summary')]"
                                 ".map(b => b.getBoundingClientRect()).filter(r => r.height && (r.height < 24 || r.width < 24)).length")
                    self.assertEqual(small, 0, msg="every control is at least 24 px")


class Archive(Page):
    """#455: Archive on a document in Edit takes it off the list (one step, Undo in the toast, no question first, as the prototype);
    "Archived (n)" under the list brings it back with Restore (also with Undo); a published file never carries an archived one."""

    def archived(self, ref):
        return self.store.read("documents", ref=f"ABC|{ref}")["archived"]

    def toast_is(self, p, words):
        p.until(f"(document.querySelector('.toast-text') || {{}}).textContent === {json.dumps(words)}", f"the toast says {words!r}")

    def test_archive_undo_and_restore_at_both_widths_light_and_dark(self):
        sec = f"[data-id={json.dumps(self.docs_section())}]"
        keep = self.add_doc("Steering minutes", "https://example.com/minutes")
        refs = [self.add_doc(f"Board pack {i}", f"https://example.com/board-{i}", kind="Report") for i in range(len(WIDTHS))]
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            for i, ((width, dark), ref) in enumerate(zip(WIDTHS, refs)):
                title = f"Board pack {i}"          # each round leaves its document archived (the last Undo), so the count grows by one
                row = f"[...document.querySelectorAll('{sec} .docs-arch li')].find(li => li.querySelector('.tpl-name').textContent === {json.dumps(title)})"
                with self.subTest(width=width, dark=dark):
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                    p.js(f"document.documentElement.dataset.theme = '{'dark' if dark else 'light'}'")
                    p.until(f"!!document.querySelector('{sec} button[aria-label={json.dumps('Archive ' + title)}]')", "the Archive button is drawn")
                    names = f"[...document.querySelectorAll('{sec} .docs-list .tpl-name')].map(n => n.textContent)"
                    p.js(f"document.querySelector('{sec} button[aria-label={json.dumps('Archive ' + title)}]').click()")
                    self.toast_is(p, f"Archived {title}. It's out of the list and the published page.")
                    p.saved()
                    p.until(f"!{names}.includes({json.dumps(title)})", "the archived document left the list")
                    self.assertEqual(self.archived(ref), 1, msg="Archive sets the document's archived flag; nothing is deleted")
                    p.js("document.querySelector('[data-undo]').click()")
                    p.until(f"{names}.includes({json.dumps(title)})", "Undo put the document back in the list")
                    self.assertEqual(self.archived(ref), 0, msg="after Undo the document is live again")
                    p.clear_toast()

                    p.js(f"document.querySelector('{sec} button[aria-label={json.dumps('Archive ' + title)}]').click()")
                    p.saved()
                    p.until(f"!!document.querySelector('{sec} .docs-arch')", "the Archived list is drawn")
                    p.clear_toast()
                    p.until(f"document.querySelector('{sec} .docs-arch summary').textContent === 'Archived ({i + 1})'", "the Archived count")
                    p.js(f"document.querySelector('{sec} .docs-arch').open = true")
                    self.assertEqual(p.js(f"{row}.querySelector('.docs-arch-text').textContent"),
                                     f"{title} Archived · Report · 10-01-2030", msg="an archived row says its title, Archived, kind and date")
                    self.assertLessEqual(p.js("document.documentElement.scrollWidth"), width, msg="no sideways scroll")
                    small = p.js(f"[...document.querySelectorAll('{sec} .docs-edit button, {sec} .docs-edit summary')]"
                                 ".map(b => b.getBoundingClientRect()).filter(r => r.height && (r.height < 24 || r.width < 24)).length")
                    self.assertEqual(small, 0, msg="every control is at least 24 px")
                    colour = p.js(f"getComputedStyle({row}.querySelector('.tpl-name')).color")
                    back = p.js("getComputedStyle(document.body).backgroundColor")
                    self.assertNotEqual(colour, back, msg="the archived row's text can be read on the page's background")
                    p.js(f"document.querySelector('{sec} button[aria-label={json.dumps('Restore ' + title)}]').click()")
                    self.toast_is(p, f"Restored {title}. It's back in the list.")
                    p.saved()
                    p.until(f"{names}.includes({json.dumps(title)}) && !{row}", "Restore put it back and it left the Archived list")
                    self.assertEqual(self.archived(ref), 0, msg="Restore clears the archived flag")
                    p.js("document.querySelector('[data-undo]').click()")
                    p.until(f"!{names}.includes({json.dumps(title)}) && !!{row}", "Undo of Restore archived it again")
                    self.assertEqual(self.archived(ref), 1, msg="Undo of Restore archives the document again")
                    p.clear_toast()
            self.assertEqual(self.archived(keep), 0, msg="the other document was never touched")
            p.view()
            p.until(f"!!document.querySelector('{sec} .docs-list')", "View drew the list")
            self.assertEqual(p.js(f"[...document.querySelectorAll('{sec} .docs-list .tpl-name')].map(n => n.textContent)"), ["Steering minutes"],
                             msg="View lists only the live document")
            self.assertFalse(p.js(f"!!document.querySelector('{sec} .docs-arch')"), msg="View has no Archived list")

    def test_the_published_file_omits_an_archived_document(self):
        self.add_doc("Steering minutes", "https://example.com/minutes")
        gone = self.add_doc("Fictional archived paper", "https://example.com/archived-paper")
        status, body = self.real_change({"project": "ABC", "kind": "documents", "op": "archive", "id": f"ABC|{gone}", "place": "report"})
        self.assertEqual(status, 200, msg=f"archiving the document should give status 200; it gave {status} {body}")
        out = tempfile.mkdtemp(prefix="clark-455-")
        self.addCleanup(shutil.rmtree, out, ignore_errors=True)
        text = Path(publish.publish(self.store, "ABC", out, by_user=USER, now="2030-01-15", branding=EMPTY_BRANDING)["path"]).read_text(encoding="utf-8")
        check_in_file(self, text, "Steering minutes", True, "the live document is in the published file")
        check_in_file(self, text, "Fictional archived paper", False, "an archived document is not in the published file")
        check_in_file(self, text, "example.com/archived-paper", False, "an archived document's link is not in the published file")


class InView(Page):
    def test_view_draws_only_visible_documents_as_links_and_nothing_to_type_in(self):
        sec = f"[data-id={json.dumps(self.docs_section())}]"
        self.add_doc("Steering minutes", "https://example.com/minutes")
        self.add_doc("Team inbox", "mailto:pmo@example.com", kind="Other", date="")
        self.hide(self.add_doc("Fictional hidden paper", "https://example.com/hidden"))
        with chrome() as cdp:
            p = self.visit(cdp)
            p.until(f"!!document.querySelector('{sec} .docs-list')", "the list drew")
            got = p.js(f"[...document.querySelectorAll('{sec} .docs-list .tpl-name')].map(a => [a.textContent, a.getAttribute('href'), a.target, a.rel])")
            self.assertEqual(got, [["Steering minutes", "https://example.com/minutes", "_blank", "noopener noreferrer"],
                                   ["Team inbox", "mailto:pmo@example.com", "", "noopener noreferrer"]],
                             msg="View lists only the two visible documents, as links that open in a new tab (an email link opens none)")
            # the prototype's row: "Kind · date" under the title (no date, no stray " · "), and an icon link named "Open {title}"
            self.assertEqual(self.view_rows(p, sec),
                             [["Steering minutes", "Minutes · 10-01-2030", "Open Steering minutes", "https://example.com/minutes", "_blank", "noopener noreferrer", "true", 2],
                              ["Team inbox", "Other", "Open Team inbox", "mailto:pmo@example.com", "", "noopener noreferrer", "true", 2]],
                             msg="View: the icon is named, decorative inside, opens like the title; an email link opens no new tab")
            self.assertNotIn("Fictional hidden paper", p.js("document.body.textContent"), msg="View does not show the document that was left out")
            self.assertEqual(p.js(f"document.querySelectorAll('{sec} input, {sec} button, {sec} select, {sec} form').length"), 0,
                             msg="View has nothing to type in or press in the documents part")


class InTheFile(Page):
    def test_the_file_draws_the_visible_documents_at_both_widths_light_and_dark(self):
        sec = f"[data-id={json.dumps(self.docs_section())}]"
        self.add_doc("<b>Steering</b> minutes", "https://example.com/minutes")
        self.add_doc("Team inbox", "mailto:pmo@example.com", kind="Other", date="")
        self.hide(self.add_doc("Fictional hidden paper", "https://example.com/hidden"))
        out = tempfile.mkdtemp(prefix="clark-74-")
        self.addCleanup(shutil.rmtree, out, ignore_errors=True)
        path = Path(publish.publish(self.store, "ABC", out, by_user=USER, now="2030-01-15", branding=EMPTY_BRANDING)["path"])
        check_in_file(self, path.read_text(encoding="utf-8"), "Fictional hidden paper", False, "a document that was left out is not in the published file")
        for width, dark in WIDTHS:
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
                sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1000, "deviceScaleFactor": 1, "mobile": False}, sid)
                cdp.call("Page.navigate", {"url": path.as_uri()}, sid)
                p = Pg(self, cdp, sid)
                p.until("document.documentElement.dataset.ready === '1' && !!document.querySelector('h1')", "the file drew")
                if dark:
                    p.js("document.documentElement.dataset.theme = 'dark'")
                p.until(f"!!document.querySelector('{sec} .docs-list')", "the list is in the file")
                self.assertEqual(self.view_rows(p, sec),
                                 [["<b>Steering</b> minutes", "Minutes · 10-01-2030", "Open <b>Steering</b> minutes", "https://example.com/minutes",
                                   "_blank", "noopener noreferrer", "true", 2],
                                  ["Team inbox", "Other", "Open Team inbox", "mailto:pmo@example.com", "", "noopener noreferrer", "true", 2]],
                                 msg="a title is text, the line is Kind · date (no date, no stray ' · '), the icon is named Open {title}, an email opens no new tab")
                self.assertEqual(p.js(f"document.querySelector('{sec} a').getAttribute('href')"), "https://example.com/minutes",
                                 msg="the first link in the documents part opens the first document")
                self.assertEqual(p.js(f"document.querySelectorAll('{sec} input, {sec} button, {sec} select, {sec} form').length"), 0,
                                 msg="the file has nothing to type in or press in the documents part")
                self.assertLessEqual(p.js("document.documentElement.scrollWidth"), width, msg="no sideways scroll")


if __name__ == "__main__":
    unittest.main()
