"""Prototype parity A-D12: the use case summary in Edit has a status button on each row, the name and headline edited in place,
and the opened row's "Where it stands" written, all through the existing change route and Undo.

Run: python3 dev/run_tests.py test_uc_edit_parity
Same harness and fictional data as test_glance_page. Laptop widths only: 1400 and 900 px, light and dark.
"""
import unittest

from test_glance_page import Published, Setup, tearDownModule  # noqa: F401
from test_server import chrome
from _paths import SRC

STATUS = "document.querySelector('[data-uc=\"%s\"] [data-uc-status]')"
FIELD = "document.querySelector('[data-uc=\"%s\"] [data-uc-field=%s]')"


class Editing(Setup):
    def show_edit(self, cdp, width=1400, dark=False):
        p = self.show(cdp, width, dark)
        p.edit()
        p.until("document.querySelectorAll('[data-uc-status]').length === 2", "the status buttons drew")
        return p

    def uc(self, ref):
        return self.store.read("use_cases", ref=ref)

    def set_text(self, p, ref, field, text, ending="Enter"):
        p.js("(function(){var el=%s; el.focus(); el.value=%r;})()" % (FIELD % (ref, field), text))
        p.key(ending, code=ending, vk=13 if ending == "Enter" else 27)

    def test_view_has_no_status_button_and_edit_has_one_on_each_row(self):
        with chrome() as cdp:
            p = self.show(cdp)
            self.assertEqual(p.js("document.querySelectorAll('[data-uc-status], [data-uc-field]').length"), 0)
            p.edit()
            p.until("document.querySelectorAll('[data-uc-status]').length === 2", "buttons")
            self.assertEqual(p.js("[...document.querySelectorAll('[data-uc-status]')].map(e => e.getAttribute('aria-label'))"),
                             ["Status: On track. Change", "Status: Flag. Change"])
            self.assertEqual(p.js("document.querySelectorAll('[data-uc-field=title]').length"), 2)
            self.assertEqual(p.js("document.querySelectorAll('[data-uc-field=headline]').length"), 2)
            p.view()
            self.assertEqual(p.js("document.querySelectorAll('[data-uc-status], [data-uc-field]').length"), 0, "View takes them away again")

    def test_the_status_is_changed_from_the_button_and_undone(self):
        uc = self.demo.use_case
        with chrome() as cdp:
            p = self.show_edit(cdp)
            p.js(STATUS % uc + ".click()")
            p.until("!!document.querySelector('[role=menuitemradio]')", "the menu opened")
            self.assertEqual(p.js("[...document.querySelectorAll('[role=menuitemradio]')].map(e => e.dataset.value)"), ["On track", "Flag", "High risk"])
            p.js("document.querySelector('[role=menuitemradio][data-value=\"High risk\"]').click()")
            p.saved()
            self.assertEqual(self.uc(uc)["status"], "High risk")
            p.until("document.querySelector('[data-uc-status]').textContent.indexOf('High risk') >= 0", "the button says it")
            self.assertEqual(p.js("document.activeElement === " + STATUS % uc), True, "focus is back on the button")
            self.assertIn("High risk", p.toast())
            self.undo(p)
            self.assertEqual(self.uc(uc)["status"], "On track")

    def test_the_status_menu_works_from_the_keyboard_and_esc_changes_nothing(self):
        uc = self.demo.use_case
        with chrome() as cdp:
            p = self.show_edit(cdp)
            p.js(STATUS % uc + ".focus()")
            p.key("Enter", code="Enter", vk=13)           # a focused button takes Enter as a click
            p.js(STATUS % uc + ".click()")
            p.until("!!document.querySelector('[role=menuitemradio]')", "menu")
            self.assertEqual(p.js("document.activeElement.dataset.value"), "On track", "focus starts on the current status")
            p.key("Escape", code="Escape", vk=27)
            p.until("!document.querySelector('[role=menuitemradio]')", "closed")
            self.assertEqual(self.uc(uc)["status"], "On track")
            self.assertEqual(p.js("document.activeElement === " + STATUS % uc), True)

    def test_the_name_and_headline_are_saved_when_left_and_undone(self):
        uc = self.demo.use_case
        with chrome() as cdp:
            p = self.show_edit(cdp)
            self.set_text(p, uc, "title", "Supplier matching")
            p.saved()
            self.assertEqual(self.uc(uc)["title"], "Supplier matching")
            self.assertIn("Supplier matching", p.toast())
            self.undo(p)
            self.assertNotEqual(self.uc(uc)["title"], "Supplier matching")
            self.set_text(p, uc, "headline", "Matching is live for all")
            p.saved()
            self.assertEqual(self.uc(uc)["headline"], "Matching is live for all")

    def test_a_blank_name_is_refused_in_plain_words_and_esc_puts_the_text_back(self):
        uc = self.demo.use_case
        with chrome() as cdp:
            p = self.show_edit(cdp)
            was = self.uc(uc)["title"]
            self.set_text(p, uc, "title", "   ")
            p.until("!!document.querySelector('.toast-text')", "a message")
            self.assertIn("needs a name", p.toast())
            self.assertEqual(self.uc(uc)["title"], was)
            self.assertEqual(p.js(FIELD % (uc, "title") + ".value"), was, "the old name is back")
            self.set_text(p, uc, "title", "Something else", ending="Escape")
            self.assertEqual(p.js(FIELD % (uc, "title") + ".value"), was)
            self.assertEqual(self.uc(uc)["title"], was)

    def test_the_opened_row_is_editable(self):
        uc = self.demo.use_case
        with chrome() as cdp:
            p = self.show_edit(cdp)
            p.js("document.querySelector('[data-uc=\"%s\"] [data-uc-open]').click()" % uc)
            p.until("!!document.querySelector('.ucdetail [data-rich=standing]')", "the text can be edited")
            self.assertEqual(p.js("document.querySelector('[data-uc-open]').getAttribute('aria-expanded')"), "true")
            p.js("document.querySelector('.ucdetail [data-rich=standing]').click()")
            p.until("!!document.querySelector('.ucdetail [contenteditable=true]')", "the editor opened")
            p.js("document.querySelector('.ucdetail [contenteditable=true]').focus()")
            p.type(" Third supplier next.")
            p.key("Enter", modifiers=2 | 4, code="Enter", vk=13)           # Ctrl/Cmd+Enter saves
            p.saved()
            self.assertIn("Third supplier next.", self.uc(uc)["standing"])
            self.assertIn("Live for two suppliers.", self.uc(uc)["standing"])
            self.undo(p)
            self.assertNotIn("Third supplier next.", self.uc(uc)["standing"])

    def test_widths_contrast_and_one_live_region(self):
        script = """(() => {
          const rgb = (c) => c.match(/[\\d.]+/g).slice(0, 3).map(Number);
          const lum = ([r, g, b]) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
          const ratio = (a, b) => { const x = lum(rgb(a)), y = lum(rgb(b)); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
          const out = [];
          for (const sel of ['[data-uc-status]', '[data-uc-field=title]', '[data-uc-field=headline]', '[data-uc-open]']) {
            const el = document.querySelector(sel); if (!el) { out.push([sel, 0]); continue; }
            let bg = el, back = 'rgba(0, 0, 0, 0)';
            while (bg && /rgba\\(.*, 0\\)|transparent/.test(back)) { back = getComputedStyle(bg).backgroundColor; bg = bg.parentElement; }
            out.push([sel, ratio(getComputedStyle(el).color, back)]);
          }
          return out;
        })()"""
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark), chrome() as cdp:
                    p = self.show_edit(cdp, width, dark)
                    for sel, r in p.js(script):
                        self.assertGreaterEqual(r, 4.5, sel)
                    self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"), "no sideways scroll")
                    self.assertEqual(p.js("document.querySelectorAll('[aria-live]').length"), 1, "one polite live region")
                    self.assertEqual(p.js("document.querySelector('[aria-live]').getAttribute('aria-live')"), "polite")
                    box = p.js("(() => { const r = document.querySelector('[data-uc-status]').getBoundingClientRect(); return [r.left, r.right]; })()")
                    self.assertLessEqual(box[1], width)


class PublishedFile(Published):
    def test_the_file_and_the_view_page_hold_none_of_the_edit_parts(self):
        text = self.publish().read_text(encoding="utf-8")
        view = (SRC / "clark" / "page" / "page-view.html").read_text(encoding="utf-8")
        for t in (text, view):
            for part in ("data-uc-status", "data-uc-field", "data-uc-open", "ucedit-text", "ucstatus", "ucbar-edit", "/api/change"):
                self.assertNotIn(part, t, part)


if __name__ == "__main__":
    unittest.main()
