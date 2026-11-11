"""#130 point 1: Publish is in the profile menu and nowhere else on the page, and the circle's tooltip says so, in a real browser.

Run: python3 dev/run_tests.py test_publish_in_menu
Widths: 1400 and 900 (a laptop; the phone is a later issue). The keyboard routes to Publish (the command palette) are not buttons
and stay; this only pins that no second visible control carries the word. Chrome is required.
"""
import re
import unittest

from test_publish_dialog import Base, PAGE_SRC, WIDTHS
from test_server import chrome

TIP = "Your menu: Publish, Preview, Export, Settings"

# Every control a person can click on the page, outside the profile menu and the (closed) dialog, whose words or name mention Publish
# and that can be seen: it has a size and is not hidden. The last-published note is text, not a control, so it is not counted.
CONTROLS = """(function () {
  var found = [];
  [].forEach.call(document.querySelectorAll('button, a, [role=button], [role=menuitem], input[type=button], input[type=submit], [data-publish]'), function (e) {
    if (e.id === 'profile-btn' || e.closest('#profile-menu') || e.closest('#publish-dialog') || e.closest('dialog:not([open])')) return;
    var r = e.getBoundingClientRect(), s = getComputedStyle(e);
    if (!r.width || !r.height || s.visibility === 'hidden' || s.display === 'none') return;
    var words = [e.textContent, e.getAttribute('aria-label'), e.title, e.id].join(' ');
    if (/publish/i.test(words) && !/^(pub-note)$/.test(e.id)) found.push((e.id || e.tagName) + ': ' + words.trim());
  });
  return found;
})()"""


class PublishInMenu(Base):
    def test_C_the_circle_tooltip_is_the_exact_words(self):
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                p.width(w, 700)
                self.assertEqual(p.js("document.querySelector('#profile-btn').title"), TIP)
                self.assertEqual(p.js("document.querySelector('#profile-btn').getAttribute('aria-label')"), "Your menu")

    def test_C_publish_is_in_the_profile_menu(self):
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                p.width(w, 700)
                p.until("(() => { if (document.querySelector('#profile-menu')) return true; "
                        "if (Date.now() - (window.__menuTried || 0) > 1000) { window.__menuTried = Date.now(); document.querySelector('#profile-btn').click(); } "
                        "return !!document.querySelector('#profile-menu'); })()", "the menu opened")
                self.assertEqual(p.js("document.querySelectorAll('#profile-menu [data-kind=publish]').length"), 1, "one Publish entry")
                self.assertEqual(p.js("document.querySelector('#profile-menu [data-kind=publish]').textContent"), "Publish…")

    def test_C_no_other_publish_button_is_visible_in_the_bar_or_the_page(self):
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                p.width(w, 700)
                p.until("!!document.querySelector('#profile-btn')", "the page drew")
                self.assertEqual(p.js(CONTROLS), [], "no control outside the menu carries Publish")
                self.assertEqual(p.js("document.querySelectorAll('header.top button').length > 0"), True, "the bar is there, so the check looked at something")

    def test_C_the_source_has_one_publish_entry_and_no_publish_button(self):
        src = (PAGE_SRC / "edit" / "ProfileMenu.jsx").read_text(encoding="utf-8")
        self.assertEqual(len(re.findall(r'id: "publish"', src)), 1, "one entry in the menu")
        for f in PAGE_SRC.rglob("*.jsx"):
            if f.name in ("ProfileMenu.jsx", "Publish.jsx"):
                continue
            self.assertNotRegex(f.read_text(encoding="utf-8"), r">\s*Publish(…|\.\.\.)?\s*<", f"{f.name} has a Publish button")


if __name__ == "__main__":
    unittest.main()
