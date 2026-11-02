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
from test_report_editor import EMPTY_BRANDING, Base as PageBase, Pg
from test_server import chrome

WIDTHS = ((1400, False), (900, True), (900, False), (1400, True))


class Page(PageBase):
    def docs_section(self):
        return next(r["id"] for r in self.store.read("report_sections", "ABC") if r["type"] == "docs")

    def add_doc(self, title, url, kind="Minutes", date="2030-01-10"):
        status, body = self.real_change({"project": "ABC", "kind": "documents", "op": "new", "place": "report",
                                         "values": {"title": title, "kind": kind, "url": url, "date": date}})
        self.assertEqual(status, 200, body)
        return body["ref"]

    def hide(self, ref):
        status, body = self.real_change({"project": "ABC", "kind": "report_hidden", "op": "new", "id": ref, "place": "eye"})
        self.assertEqual(status, 200, body)

    def rows(self, p, sel):
        return p.js(f"[...document.querySelectorAll('{sel} .docs-list .tpl-dl-i')].map(li => [li.querySelector('.tpl-badge').textContent, "
                    "li.querySelector('.tpl-name').textContent, li.querySelector('.tpl-facts').textContent])")

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
            self.assertIn("No documents yet", p.js(f"document.querySelector('{sec} .tpl-empty').textContent"))
            p.js(f"[...document.querySelectorAll('{sec} button')].find(b => b.textContent === 'Add a document link').click()")
            p.until(f"!!document.querySelector('{sec} .docs-form')", "the form opened")
            p.until("document.activeElement && document.activeElement.id === 'doc-new-title'", "the title box takes the focus")
            self.set_value(p, "#doc-new-title", "Steering minutes")
            self.set_value(p, "#doc-new-kind", "Minutes")
            self.set_value(p, "#doc-new-url", "javascript:alert(1)")
            p.js(f"document.querySelector('{sec} .docs-form button[type=submit]').click()")
            p.until("(document.querySelector('.toast-text') || {}).textContent === \"That link can't be used. It must start with https://, http:// or mailto:\"",
                    "the link rule's own words")
            self.assertEqual(self.store.read("documents", "ABC"), [], "nothing was saved")
            self.set_value(p, "#doc-new-url", "https://example.com/minutes")
            self.set_value(p, "#doc-new-date", "2030-01-10")
            p.js(f"document.querySelector('{sec} .docs-form button[type=submit]').click()")
            p.until(f"document.querySelectorAll('{sec} .docs-list .tpl-dl-i').length === 1", "the new document is drawn")
            self.assertEqual(self.rows(p, sec), [["Minutes", "Steering minutes", "10-01-2030 · example.com"]])
            p.saved()
            p.js("document.querySelector('[data-undo]').click()")
            p.until(f"document.querySelectorAll('{sec} .docs-list .tpl-dl-i').length === 0", "Undo took the add back")
            self.assertEqual(self.store.read("documents", "ABC"), [])
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
            self.assertEqual(self.store.read("documents", ref=f"ABC|{ref}")["title"], "Board pack, signed")
            p.js("document.querySelector('[data-undo]').click()")
            p.until(f"document.querySelector('{sec} .docs-list .tpl-name').textContent === 'Board pack'", "Undo put the title back")
            p.clear_toast()

            p.js(f"document.querySelector('{sec} button[aria-label=\"Leave Board pack out of the published page\"]').click()")
            p.until(f"document.querySelectorAll('{sec} .docs-list .tpl-dl-i').length === 0", "left out")
            p.until(f"(document.querySelector('{sec} .docs-left summary') || {{}}).textContent === 'Add back a document (1)'", "listed to add back")
            self.assertEqual([r["item_id"] for r in self.store.read("report_hidden", "ABC")], [ref])
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
            self.assertEqual(self.store.read("report_hidden", "ABC"), [])

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
                    self.assertLessEqual(p.js("document.documentElement.scrollWidth"), width, "no sideways scroll")
                    small = p.js(f"[...document.querySelectorAll('{sec} .docs-edit button, {sec} .docs-edit summary')]"
                                 ".map(b => b.getBoundingClientRect()).filter(r => r.height && (r.height < 24 || r.width < 24)).length")
                    self.assertEqual(small, 0, "every control is at least 24 px")


class InView(Page):
    def test_view_draws_only_visible_documents_as_links_and_nothing_to_type_in(self):
        sec = f"[data-id={json.dumps(self.docs_section())}]"
        self.add_doc("Steering minutes", "https://example.com/minutes")
        self.add_doc("Team inbox", "mailto:pmo@example.com", kind="Other", date="")
        self.hide(self.add_doc("Fictional hidden paper", "https://example.com/hidden"))
        with chrome() as cdp:
            p = self.visit(cdp)
            p.until(f"!!document.querySelector('{sec} .docs-list')", "the list drew")
            got = p.js(f"[...document.querySelectorAll('{sec} .docs-list a')].map(a => [a.textContent, a.getAttribute('href'), a.target, a.rel])")
            self.assertEqual(got, [["Steering minutes", "https://example.com/minutes", "_blank", "noopener noreferrer"],
                                   ["Team inbox", "mailto:pmo@example.com", "", "noopener noreferrer"]])
            self.assertNotIn("Fictional hidden paper", p.js("document.body.textContent"))
            self.assertEqual(p.js(f"document.querySelectorAll('{sec} input, {sec} button, {sec} select, {sec} form').length"), 0)


class InTheFile(Page):
    def test_the_file_draws_the_visible_documents_at_both_widths_light_and_dark(self):
        sec = f"[data-id={json.dumps(self.docs_section())}]"
        self.add_doc("<b>Steering</b> minutes", "https://example.com/minutes")
        self.hide(self.add_doc("Fictional hidden paper", "https://example.com/hidden"))
        out = tempfile.mkdtemp(prefix="clark-74-")
        self.addCleanup(shutil.rmtree, out, ignore_errors=True)
        path = Path(publish.publish(self.store, "ABC", out, by_user=USER, now="2030-01-15", branding=EMPTY_BRANDING)["path"])
        self.assertNotIn("Fictional hidden paper", path.read_text(encoding="utf-8"))
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
                self.assertEqual(self.rows(p, sec), [["Minutes", "<b>Steering</b> minutes", "10-01-2030 · example.com"]], "a title is text")
                self.assertEqual(p.js(f"document.querySelector('{sec} a').getAttribute('href')"), "https://example.com/minutes")
                self.assertEqual(p.js(f"document.querySelectorAll('{sec} input, {sec} button, {sec} select, {sec} form').length"), 0)
                self.assertLessEqual(p.js("document.documentElement.scrollWidth"), width, "no sideways scroll")


if __name__ == "__main__":
    unittest.main()
