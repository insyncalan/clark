"""#82 (BRD 5.13, FR-120 to FR-124): the Help panel in a real browser, against the real page and routes.

Run: python3 dev/run_tests.py test_help_panel
Headless Chrome through the shared harness (the keychain flags are in it); the page is the real one with fictional demo data.
Only what the page has is shown (src/clark/page/src/help/helpLater.json holds the rest back), so the tabs are checked against
that. Covers: "?" opens Help outside a field and not inside one, Esc returns to the page left, the three tabs, search across all three
tabs, a result opens in place, a link inside Help and a link to a screen, window.clarkPage.help.open to a place (and an unknown
place), and that the published page has no Help. What waits for other items: the profile-menu entry (#64), Publish, Preview and
ask clark links (drawn as plain words until those exist).
"""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

from _paths import SRC, TOOLS  # noqa: F401  (puts src/ on the path)
from _new_page import reload_to_new_page
from test_report_editor import ALT, Base, Pg  # noqa: F401
from clark import page
from _help_shown import shown_content

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402


def keys_in_help(p):
    return p.js("document.querySelector('#help') ? 1 : 0")


def full_help_from_menu(p, what="Help opened from the profile menu"):
    """The profile menu's Help entry opens the context peek like "?" (row 896); this goes one click further, to the FULL Help (on the tab used last)."""
    p.cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, p.sid)   # a click with no key press before it leaves the page unfocused
    p.js("document.querySelector('#profile-btn').click()")
    p.until("!!document.querySelector('#profile-menu')", "profile menu")
    p.js("[...document.querySelectorAll('#profile-menu [role=menuitem]')].find(e => e.textContent === 'Help').click()")
    p.until("!!document.querySelector('#help') || !!document.querySelector('#help-peek')", what)
    if p.js("!!document.querySelector('#help-peek')"):          # row 896: the entry opens the peek; the full Help is its foot link, which opens on the entry the text names
        last = p.js("localStorage.getItem('clark.helpTab') || 'start'")
        p.js("document.querySelector('#help-peek [data-hpk-full]').click()")
        p.until("!!document.querySelector('#hpTab-%s')" % last, what)
        p.js("window.clarkPage.help.open(%r)" % last)      # the tab used last, which these tests are about (open() starts a fresh history)
    p.until("!!document.querySelector('#help') && !document.querySelector('#profile-menu')", what)


def full_help_from_key(p, what="Help opened from ? and the foot link"):
    """"?" opens the peek; its foot link opens the full Help. The peek hands focus back first, so Help's Back returns to what had it."""
    p.key("?", code="Slash", vk=191)
    p.until("!!document.querySelector('#help-peek')", "the peek opened on ?")
    p.js("document.querySelector('#help-peek [data-hpk-full]').click()")
    p.until("!!document.querySelector('#help')", what)



class Panel(Base):
    def in_help(self, cdp):
        p = self.visit(cdp)
        full_help_from_menu(p)
        return p

    def test_question_mark_opens_and_esc_returns(self):
        from test_server import chrome
        with chrome() as cdp:
            p = self.visit(cdp)
            before = p.js("location.hash")
            self.assertEqual(p.js("document.querySelector('#help') === null"), True)
            p.key("?", code="Slash", vk=191)
            p.until("!!document.querySelector('#help-peek')", "? opened the peek (the Dashboard has context text)")
            self.assertEqual(p.js("document.querySelector('#help') === null"), True, "the peek is not the full Help")
            p.key("Escape", code="Escape", vk=27)
            p.until("!document.querySelector('#help-peek') && !document.querySelector('.peek.leaving')", "Esc closed the peek")
            full_help_from_menu(p)
            self.assertEqual(p.js("document.querySelector('#report') === null"), True, "Help is in place of the page")
            self.assertEqual(p.js("location.hash"), before, "opening Help does not move the address")
            p.key("Escape", code="Escape", vk=27)
            p.until("!document.querySelector('#help') && !!document.querySelector('#report')", "Esc returned to the page")

    def test_question_mark_in_a_field_is_just_a_character(self):
        from test_server import chrome
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            p.js("var el=document.querySelector('[data-id] [data-title]'); el.focus()")
            p.key("?", code="Slash", vk=191)
            self.assertEqual(p.js("document.querySelector('#help') === null"), True, "no Help while typing in a title")

    def test_three_tabs_and_what_each_shows_today(self):
        """Only what the page has is shown (helpLater.json): Start here and How do I… say so, Reference has the keys."""
        from test_server import chrome
        with chrome() as cdp:
            p = self.in_help(cdp)
            self.assertEqual(p.js("[...document.querySelectorAll('.hp-tabs [role=tab]')].map(b => b.textContent)"), ["Start here", "How do I…", "Reference"])
            self.assertEqual(p.js("document.querySelectorAll('.hp-first li').length"), 0, "no held entry on Start here")
            # row 903: the hero card and The loop (five steps, the last a Your call step) sit above the jobs
            self.assertEqual(p.js("document.querySelectorAll('.hp-hero h2').length"), 1, "the hero card")
            self.assertEqual(p.js("document.querySelectorAll('.hp-steps li').length"), 5, "the loop has five steps")
            self.assertEqual(p.js("document.querySelectorAll('.hp-steps li.gate').length"), 1, "one Your call step")
            self.assertEqual(p.js("var h=document.querySelector('.hp-hero'),l=document.querySelector('.hp-loop'),j=document.querySelector('.hp-start-jobs');"
                                  "!!(h.compareDocumentPosition(l) & 4) && !!(l.compareDocumentPosition(j) & 4)"), True, "hero, loop, then the jobs")
            self.assertEqual(p.js("document.querySelectorAll('.hp-job').length"), len(shown_content()["start"]["jobs"]), "the jobs whose entries are shown (#642 step 3)")
            self.assertFalse(p.js("!!document.querySelector('#hp-later')"))
            p.js("document.querySelector('#hpTab-howto').click()")
            p.until("document.querySelectorAll('.hp-task').length > 0", "How do I… has the tasks the page can do")
            self.assertEqual(p.js("document.querySelectorAll('.hp-task').length"), len(shown_content()["howto"]["tasks"]) + len(shown_content()["guides"]), "the entries and the guides")
            self.assertEqual(p.js("!!document.querySelector('#hp-later')"), False)
            p.js("document.querySelector('#hpTab-reference').click()")
            p.until("document.querySelectorAll('.hp-ref').length > 0", "Reference drew")
            self.assertEqual(p.js("document.querySelectorAll('.hp-ref').length"), len(shown_content()["reference"]["sections"]))
            self.assertEqual(p.js("document.querySelector('#hp-ref-keys .hp-keys tbody').children.length"), len(shown_content()["reference"]["keys"]))
            self.assertEqual(p.js("document.querySelector('#hp-ref-keys .hp-keys').textContent.indexOf('Mod+J')"), -1)      # #721: Sneak peek is shown now; the page has no Mod+J key
            self.assertEqual(p.js("document.querySelector('.hp-idx') && document.querySelectorAll('.hp-idx a').length"), len(shown_content()["reference"]["sections"]))

    def test_search_finds_what_is_shown_and_opens_in_place_and_not_what_is_held(self):
        from test_server import chrome
        with chrome() as cdp:
            p = self.in_help(cdp)
            p.js("var q=document.querySelector('#hpQ'); q.focus()")
            p.type("shortcuts")
            p.until("document.querySelectorAll('#hpRes a.hp-r').length > 0", "results")
            self.assertEqual(p.js("[...document.querySelectorAll('#hpRes .hp-resg h3')].map(h => h.textContent)"), ["Reference"])
            p.js("document.querySelector('#hpRes a.hp-r').click()")
            p.until("!document.querySelector('#hpRes') && !!document.querySelector('.hp-found')", "the result opened in place and flashed")
            for word in ("hdmi",):                              # "publish" and "peek" are in entries that say so (a row left out is not on the published page); test_help_logic pins those results exactly
                p.js("var q=document.querySelector('#hpQ'); q.value=''; q.focus()")
                p.type(word)
                p.until("!!document.querySelector('.hp-none')", f"a held word ({word}) finds nothing")
            self.assertIn("Nothing in Help for", p.js("document.querySelector('.hp-none b').textContent"))

    def test_a_search_for_movement_or_diagnostics_finds_its_entry_and_opens_it(self):
        """Row 65: these two words found nothing; each now finds the entries about it, and a result opens in place."""
        from test_server import chrome
        with chrome() as cdp:
            p = self.in_help(cdp)
            for word, first, where in (("movement", "Milestones and Movement", "ref-milestones-page"), ("diagnostics", "Diagnostics and logs", "ref-diagnostics")):
                p.js("var q=document.querySelector('#hpQ'); q.value=''; q.focus()")
                p.type(word)
                p.until("document.querySelectorAll('#hpRes a.hp-r').length > 0", f"results for {word}")
                self.assertIn(first, p.js("[...document.querySelectorAll('#hpRes a.hp-r')].map(a => a.textContent).join(' | ')"))
                self.assertEqual(p.js("!!document.querySelector('.hp-none')"), False)
                p.js("[...document.querySelectorAll('#hpRes a.hp-r')].find(a => a.textContent.indexOf(" + json.dumps(first) + ") >= 0).click()")
                p.until("!document.querySelector('#hpRes') && !!document.querySelector('#hp-%s.hp-found')" % where, f"{word}: the result opened in place and flashed")
                p.js("var q=document.querySelector('#hpQ'); q.value=''; q.focus()")
            self.assertEqual(p.js("document.querySelector('#hp-ref-diagnostics').textContent.indexOf('Copy diagnostics') >= 0"), True)

    def test_a_contents_link_opens_its_place_and_a_held_place_is_not_one(self):
        from test_server import chrome
        with chrome() as cdp:
            p = self.in_help(cdp)
            p.js("document.querySelector('#hpTab-reference').click()")
            p.until("!!document.querySelector('.hp-idx a')", "the contents list")
            p.js("document.querySelector('.hp-idx a[data-hlink=ref-keys]').click()")
            p.until("!!document.querySelector('#hp-ref-keys.hp-found')", "a contents link opens its place and flashes it")
            self.assertEqual(p.js("document.querySelector('[data-hlink=ref-peek], [data-hlink=ref-publishing], [data-hlink=howto-publish-the-report]')"), None)
            self.assertTrue(p.js("location.hash.indexOf('#dashboard') === 0"), "the page left is the Dashboard")

    def test_focus_goes_back_to_what_had_it_when_help_closes(self):                     # MEDIUM
        from test_server import chrome
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            p.js("var h=document.querySelector('.secs .sec[data-id] [data-drag]'); window.__id=h.closest('.sec').dataset.id; h.focus()")
            full_help_from_key(p, "Help opened from a section's handle")
            p.key("Escape", code="Escape", vk=27)
            p.until("!document.querySelector('#help') && document.activeElement && document.activeElement.hasAttribute('data-drag')", "Esc put focus back on the handle")
            self.assertEqual(p.js("document.activeElement.closest('.sec').dataset.id"), p.js("window.__id"))
            # Esc does the same from a part of the top bar, which is a part of the top bar is the same element still
            p.js("document.querySelector('.mode[data-mode=view]').focus()")
            full_help_from_key(p, "Help opened from the View button")
            p.key("Escape", code="Escape", vk=27)
            p.until("!document.querySelector('#help') && document.activeElement && document.activeElement.dataset.mode === 'view'", "Esc put focus back on View")

    def test_the_top_bar_has_no_help_button_and_help_has_no_back_button(self):
        """Row 899: the top bar has no "?" button. Help is reached by the ? key, the palette and the profile menu; Help has no Back button
        (row 779): Esc puts the person where they were. Both widths."""
        from test_server import chrome
        with chrome() as cdp:
            p = self.visit(cdp)
            for w in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                self.assertEqual(p.js("document.querySelector('#help-btn')"), None, f"{w}: no Help button in the top bar")
                self.assertTrue(p.js("var b=document.querySelector('#profile-btn').getBoundingClientRect(); b.right<=innerWidth"), f"{w}: the profile circle is in view")
                # The ? key opens the context peek on a screen with text (the Dashboard has some); the profile menu's Help is the full Help.
                p.key("?", code="Slash", vk=191)
                p.until("!!document.querySelector('#help-peek')", f"{w}: the ? key opened the peek")
                self.assertEqual(p.js("document.querySelector('#help')"), None, f"{w}: the key does not open the full Help here")
                p.key("?", code="Slash", vk=191)
                p.until("!document.querySelector('#help-peek') && !document.querySelector('.peek.leaving')", f"{w}: the ? key closed the peek")
                p.js("document.querySelector('#profile-btn').focus()")
                full_help_from_menu(p, f"{w}: the profile menu's Help opened Help")
                self.assertEqual(p.js("document.querySelector('#hpBack')"), None, "no Back button: Esc leaves Help (prototype help.js:725)")
                self.assertEqual(p.js("document.querySelector('#hpClose')"), None, "no Close Help button any more")
                self.assertIn("Esc takes you where you were", p.js("document.querySelector('.hp-head p').textContent"))
                self.assertNotIn("Back", p.js("document.querySelector('.hp-head p').textContent"), "the line names no Back that is not there")
                p.until("document.getAnimations().length === 0", f"{w}: settled before measuring")
                self.assertTrue(p.js("var s=document.querySelector('.hp-search').getBoundingClientRect(), h=document.querySelector('.hp-head h1').getBoundingClientRect(); s.left > h.right && s.top < h.bottom + 40 && s.right <= innerWidth"), f"{w}: search at the top right, level with the title")
                self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"), f"{w}: no sideways scroll")
                p.key("Escape", code="Escape", vk=27)
                p.until("!document.querySelector('#help') && !!document.querySelector('#report') && document.activeElement.id === 'profile-btn'", f"{w}: Esc returned to the page and the profile button that opened Help")

    def test_help_is_a_page_of_cards_with_a_search_icon_and_a_key_chip(self):
        """C-H6 and C-H7: no outer frame; the search box has its icon and a "/" chip that goes while the box is used; the Reference
        tab has its contents rail beside cards. Light and dark."""
        from test_server import chrome
        with chrome() as cdp:
            p = self.in_help(cdp)
            for scheme in ("light", "dark"):
                cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, p.sid)
                self.assertEqual(p.js("document.querySelector('#help').classList.contains('frame')"), False, "Help is not drawn as one bordered panel")
                self.assertEqual(p.js("getComputedStyle(document.querySelector('#help')).borderTopWidth"), "0px")
                self.assertEqual(p.js("!!document.querySelector('.hp-search > svg[data-icn=search]')"), True, "the search icon")
                p.js("document.querySelector('#hpQ').blur()")      # full Help opens with the focus in the box; the chip shows once it is left
                self.assertEqual(p.js("(function(){var k=document.querySelector('#hpQk');return [k.textContent,k.getAttribute('aria-label'),getComputedStyle(k).display]})()"),
                                 ["/", "Press slash to search", "block"], "the key chip shows while the box is empty and not in use")
                p.js("document.querySelector('#hpTab-reference').click()")
                p.until("!!document.querySelector('.hp-two .hp-idx')", "the contents rail")
                self.assertEqual(p.js("(function(){var r=document.querySelector('.hp-idx').getBoundingClientRect(), c=document.querySelector('.hp-ref').getBoundingClientRect();"
                                      "return [getComputedStyle(document.querySelector('.hp-idx')).position, r.right <= c.left, getComputedStyle(document.querySelector('.hp-ref')).borderTopWidth]})()"),
                                 ["sticky", True, "1px"], "the rail beside the cards, each card with its own edge")
            p.js("var q=document.querySelector('#hpQ'); q.focus()")
            self.assertEqual(p.js("getComputedStyle(document.querySelector('#hpQk')).display"), "none", "the chip goes while the box has the focus")
            p.type("keys")
            p.until("!!document.querySelector('#hpRes a.hp-r')", "results")
            p.js("document.querySelector('#hpTab-start').focus()")
            self.assertEqual(p.js("getComputedStyle(document.querySelector('#hpQk')).display"), "none", "and while it has a word in it")

    def test_a_result_marks_the_matched_word(self):
        """C-H9: the matched word is marked in the title and in the line, as text; the mark is the prototype's flash colour."""
        from test_server import chrome
        with chrome() as cdp:
            p = self.in_help(cdp)
            p.js("var q=document.querySelector('#hpQ'); q.focus()")
            p.type("shortcuts")
            p.until("document.querySelectorAll('#hpRes a.hp-r').length > 0", "results")
            marks = p.js("[...document.querySelectorAll('#hpRes a.hp-r mark')].map(m => m.textContent.toLowerCase())")
            self.assertTrue(marks and all(m.startswith("shortcut") for m in marks), marks)
            self.assertEqual(p.js("document.querySelectorAll('#hpRes a.hp-r .hp-rl mark').length > 0 || document.querySelectorAll('#hpRes a.hp-r .hp-rt mark').length > 0"), True)
            self.assertNotEqual(p.js("getComputedStyle(document.querySelector('#hpRes mark')).backgroundColor"), "rgba(0, 0, 0, 0)", "the mark has a background")
            self.assertEqual(p.js("document.querySelector('#hpRes a.hp-r').textContent.indexOf('<')"), -1)
            p.js("var q=document.querySelector('#hpQ'); q.value=''; q.focus()")
            p.type("<b>x</b>")
            p.until("!!document.querySelector('.hp-none')", "nothing found")
            self.assertEqual(p.js("document.querySelectorAll('#hpRes b, #hpRes mark').length"), 1, "only the empty-result line's own bold; what was typed is text")

    def test_esc_clears_the_search_from_a_result_or_a_tab_then_closes(self):            # MEDIUM
        from test_server import chrome
        with chrome() as cdp:
            p = self.in_help(cdp)
            for where in ("result", "tab"):
                p.js("var q=document.querySelector('#hpQ'); q.focus()")
                p.type("keys")
                p.until("document.querySelectorAll('#hpRes a.hp-r').length > 0", "results")
                p.js("(%s).focus()" % ("document.querySelector('#hpRes a.hp-r')" if where == "result" else "document.querySelector('#hpTab-start')"))
                self.assertNotEqual(p.js("document.activeElement.id"), "hpQ")
                p.key("Escape", code="Escape", vk=27)
                p.until("!document.querySelector('#hpRes') && document.querySelector('#hpQ').value === ''", f"Esc on a {where} cleared the search")
                self.assertTrue(p.js("!!document.querySelector('#help')"), "and Help stayed open")
            p.key("Escape", code="Escape", vk=27)
            p.until("!document.querySelector('#help')", "a second Esc closes Help")

    def test_open_help_at_a_place(self):
        from test_server import chrome
        with chrome() as cdp:
            p = self.visit(cdp)
            p.js("window.clarkPage.help.open('ref-keys')")
            p.until("!!document.querySelector('#hp-ref-keys.hp-found')", "opened at the keys")
            self.assertEqual(p.js("document.querySelector('#hpTab-reference').getAttribute('aria-selected')"), "true")
            p.js("window.clarkPage.help.close()")
            p.until("!document.querySelector('#help')", "closed")
            p.js("window.clarkPage.help.open('howto-nothing-here')")
            p.until("!!document.querySelector('#help')", "an unknown place still opens Help")
            self.assertEqual(p.js("document.querySelector('.hp-found')"), None, "and flashes nothing")

    def test_the_tab_used_last_is_remembered_and_a_new_page_closes_help(self):
        from test_server import chrome
        with chrome() as cdp:
            p = self.in_help(cdp)
            p.js("document.querySelector('#hpTab-howto').click()")
            p.js("window.clarkPage.help.close()")
            p.js("window.clarkPage.help.open()")
            p.until("document.querySelector('#hpTab-howto') && document.querySelector('#hpTab-howto').getAttribute('aria-selected') === 'true'", "opened on the tab used last")
            reload_to_new_page(p.js)
            p.until("!!window.clarkPage && !!document.querySelector('#report')", "reloaded")
            full_help_from_menu(p)
            p.until("!!document.querySelector('#hpTab-howto') && document.querySelector('#hpTab-howto').getAttribute('aria-selected') === 'true'", "a reload still opens on the tab used last")
            p.js("window.clarkPage.show('work')")
            p.until("!document.querySelector('#help')", "going to another page closes Help")


class Published(unittest.TestCase):
    def test_the_published_page_has_no_help(self):
        text = (Path(page.__file__).parent / "page-view.html").read_text(encoding="utf-8")
        text = re.sub(r"data:[a-z0-9/+.-]+;base64,[A-Za-z0-9+/=]+", "data:", text)          # a short word can turn up by chance inside the fonts' base64 data
        for word in ("Twelve jobs", "clark.helpTab", "Search Help", "hpQ", "Your first ten minutes", "help-btn"):
            self.assertNotIn(word, text)

    def test_the_published_build_takes_none_of_the_help_files(self):
        """A shared component that imports a Help module (its store, its logic, its words) bundles all of Help's words into the
        published file. The published entry's module graph must hold nothing from help/, whatever the words are."""
        with tempfile.TemporaryDirectory() as tmp:
            meta = Path(tmp) / "meta.json"
            done = esbuild.run(["--bundle", "--format=iife", "--tsconfig-raw={}", *build_page.preact_flags(), build_page.ENTRY_VIEW,
                                f"--outfile={Path(tmp) / 'p.js'}", f"--metafile={meta}"], cwd=build_page.SRC, capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            inputs = list(json.loads(meta.read_text(encoding="utf-8"))["inputs"])
        self.assertTrue(inputs)
        self.assertEqual([name for name in inputs if name.startswith("help/") or "/help/" in name], [])


if __name__ == "__main__":
    unittest.main()
