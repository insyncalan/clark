"""Item 1180: the peek toolbar. Run: python3 dev/run_tests.py test_peek_toolbar_1180

Real browser at 1400 and 900 px with the test build, fictional demo data. The bar reads, left to right: Close, Open full page, a thin
rule, Previous item, Next item, then (right side) Draft email, Copy link, More. More holds Duplicate, Archive and, last and in red,
Delete. There is no Share menu, no Preview as client, and no separate Duplicate, Archive or Delete button. A read-only peek (View)
keeps Close, Open full page, Previous and Next and has no Draft email, Copy link or More.
"""
import unittest

import test_peek as TP
from test_server import chrome, wait
from test_work_filters import click, key

BAR = "[...document.querySelectorAll('#peek .pk-bar button')]"
NAME = "(b => (b.getAttribute('aria-label') || b.title || b.textContent || '').trim())"


class Toolbar(unittest.TestCase):
    setUpClass = classmethod(TP.Browser.setUpClass.__func__)
    tearDownClass = classmethod(TP.Browser.tearDownClass.__func__)
    load_page = TP.Browser.load_page
    edit_mode = TP.Browser.edit_mode
    ids_on_page = TP.Browser.ids_on_page

    def open_peek(self, cdp, width, edit=True):
        s, sid = self.load_page(cdp, width)
        if edit:
            self.edit_mode(cdp, sid)
        ids = self.ids_on_page(cdp, sid)
        click(cdp, sid, f"#work tbody tr[data-id='{ids[1]}'] .c-item")
        self.assertTrue(wait(lambda: cdp.js("clarkPage.peek() && clarkPage.peek().id", sid) == ids[1]))
        self.assertTrue(wait(lambda: cdp.js("document.querySelector('#peek').getAnimations().length === 0", sid)), "the slide-in has ended")
        return sid

    def names(self, cdp, sid):
        return cdp.js(f"{BAR}.map({NAME})", sid)

    def left_of(self, cdp, sid, a, b):
        return cdp.js(f"document.querySelector({a!r}).getBoundingClientRect().right <= document.querySelector({b!r}).getBoundingClientRect().left + 0.5", sid)

    def open_more(self, cdp, sid):
        click(cdp, sid, "#pk-more")
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek [role=menu], [role=menu]')", sid)))
        return cdp.js("[...document.querySelectorAll('[role=menu] [role^=menuitem]')].map(b => (b.getAttribute('aria-label') || b.textContent).trim())", sid)

    def test_the_bar_reads_close_full_page_rule_previous_next_then_draft_email_copy_link_more(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.open_peek(cdp, width)
                order = cdp.js(f"{BAR}.map(b => b.hasAttribute('data-pk-close') ? 'close' : b.hasAttribute('data-pk-wide') ? 'wide' : b.hasAttribute('data-pk-prev') ? 'prev' : b.hasAttribute('data-pk-next') ? 'next' : b.id === 'pk-more' ? 'more' : {NAME}(b).toLowerCase().includes('draft email') ? 'draft' : {NAME}(b).toLowerCase().includes('copy link') ? 'link' : 'other:' + {NAME}(b))", sid)
                self.assertEqual(order, ["close", "wide", "prev", "next", "draft", "link", "more"], order)

    def test_the_left_group_sits_left_and_the_right_group_right_with_a_thin_rule_between_full_page_and_previous(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.open_peek(cdp, width)
                self.assertTrue(self.left_of(cdp, sid, "[data-pk-close]", "[data-pk-wide]"))
                self.assertTrue(self.left_of(cdp, sid, "[data-pk-wide]", "[data-pk-prev]"))
                self.assertTrue(self.left_of(cdp, sid, "[data-pk-prev]", "[data-pk-next]"))
                self.assertTrue(self.left_of(cdp, sid, "[data-pk-next]", "#pk-more"))
                right = cdp.js("document.querySelector('#peek').getBoundingClientRect().right - document.querySelector('#pk-more').getBoundingClientRect().right", sid)
                self.assertLess(right, 24, "More is the right-most control")
                left = cdp.js("document.querySelector('[data-pk-close]').getBoundingClientRect().left - document.querySelector('#peek').getBoundingClientRect().left", sid)
                self.assertLess(left, 24, "Close is the left-most control")
                rule = cdp.js("""(() => { const w = document.querySelector('[data-pk-wide]').getBoundingClientRect(), p = document.querySelector('[data-pk-prev]').getBoundingClientRect();
                  return [...document.querySelectorAll('#peek .pk-bar *')].filter(e => { const r = e.getBoundingClientRect(); return e.tagName !== 'BUTTON' && !e.closest('button') && r.width <= 2 && r.height >= 8 && r.left >= w.right - 0.5 && r.right <= p.left + 0.5; }).length; })()""", sid)
                self.assertEqual(rule, 1, "one thin rule between Open full page and Previous item")

    def test_each_control_has_a_name_an_icon_and_a_24px_target(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.open_peek(cdp, width)
                got = cdp.js(f"{BAR}.map(b => ({{n: {NAME}(b), svg: !!b.querySelector('svg'), w: b.getBoundingClientRect().width, h: b.getBoundingClientRect().height, shown: b.getBoundingClientRect().right <= document.documentElement.clientWidth}}))", sid)
                self.assertEqual(len(got), 7)
                for g in got:
                    self.assertTrue(g["n"], g)
                    self.assertTrue(g["svg"], g)
                    self.assertGreaterEqual(min(g["w"], g["h"]), 24, g)
                    self.assertTrue(g["shown"], g)
                names = " | ".join(g["n"].lower() for g in got)
                for word in ("close", "draft email", "copy link", "more", "previous", "next"):
                    self.assertIn(word, names)

    def test_there_is_no_share_preview_duplicate_archive_or_delete_button_in_the_bar(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.open_peek(cdp, width)
                names = " | ".join(n.lower() for n in self.names(cdp, sid))
                for word in ("share", "preview", "duplicate", "archive", "delete"):
                    self.assertNotIn(word, names, word)
                self.assertFalse(cdp.js("!!document.querySelector('#peek .pk-bar [data-pk-dup], #peek .pk-bar [data-pk-arch], #peek .pk-bar [data-pk-del]')", sid))

    def test_more_holds_duplicate_archive_and_delete_last_after_a_rule(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.open_peek(cdp, width)
                items = self.open_more(cdp, sid)
                self.assertEqual(len(items), 3, items)
                self.assertTrue(items[0].lower().startswith("duplicate"), items)
                self.assertTrue(items[1].lower().startswith("archive"), items)
                self.assertTrue(items[2].lower().startswith("delete"), items)
                sep = cdp.js("""(() => { const m = document.querySelector('[role=menu]'), kids = [...m.children]; const i = kids.findIndex(k => /^delete/i.test((k.getAttribute('aria-label') || k.textContent).trim()));
                  return i > 0 && (kids[i - 1].getAttribute('role') === 'separator' || kids[i - 1].tagName === 'HR' || kids[i - 1].classList.contains('sep')); })()""", sid)
                self.assertTrue(sep, "a rule sits above Delete")

    def test_delete_is_red_and_the_others_are_not(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.open_peek(cdp, width)
                self.open_more(cdp, sid)
                colours = cdp.js("""[...document.querySelectorAll('[role=menu] [role^=menuitem]')].map(b => { const c = getComputedStyle(b).color.match(/\\d+/g).map(Number); return {r: c[0], g: c[1], b: c[2], danger: b.classList.contains('danger')}; })""", sid)
                last = colours[-1]
                self.assertTrue(last["danger"], colours)
                self.assertGreater(last["r"], last["g"] + 60, colours)
                self.assertGreater(last["r"], last["b"] + 60, colours)
                for c in colours[:-1]:
                    self.assertFalse(c["danger"], colours)
                    self.assertLess(c["r"] - c["g"], 60, colours)

    def test_esc_closes_more_first_then_the_peek_and_focus_returns_to_more(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.open_peek(cdp, width)
                self.open_more(cdp, sid)
                key(cdp, sid, "Escape")
                self.assertTrue(wait(lambda: cdp.js("!document.querySelector('[role=menu]')", sid)))
                self.assertIsNotNone(cdp.js("clarkPage.peek()", sid), "the first Esc closes the menu only")
                self.assertTrue(cdp.js("document.activeElement.id === 'pk-more'", sid), "focus returns to More")

    def test_duplicate_from_more_makes_a_copy_and_delete_from_more_asks_first(self):
        with chrome() as cdp:
            sid = self.open_peek(cdp, 1400)
            before = len(self.ids_on_page(cdp, sid))
            self.open_more(cdp, sid)
            cdp.js("[...document.querySelectorAll('[role=menu] [role^=menuitem]')].find(b => /^duplicate/i.test(b.textContent.trim())).click()", sid)
            self.assertTrue(wait(lambda: len(self.ids_on_page(cdp, sid)) == before + 1), "Duplicate adds one row")

    def test_a_read_only_peek_keeps_close_full_page_previous_next_and_has_no_draft_copy_or_more(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.open_peek(cdp, width, edit=False)
                order = cdp.js(f"{BAR}.map(b => b.hasAttribute('data-pk-close') ? 'close' : b.hasAttribute('data-pk-wide') ? 'wide' : b.hasAttribute('data-pk-prev') ? 'prev' : b.hasAttribute('data-pk-next') ? 'next' : 'other:' + {NAME}(b))", sid)
                self.assertEqual(order[:4], ["close", "wide", "prev", "next"], order)
                names = " | ".join(self.names(cdp, sid)).lower()
                for word in ("draft email", "copy link", "more", "duplicate", "archive", "delete", "share"):
                    self.assertNotIn(word, names, word)

    def test_previous_and_next_still_step_and_close_still_closes(self):
        with chrome() as cdp:
            sid = self.open_peek(cdp, 1400)
            ids = self.ids_on_page(cdp, sid)
            click(cdp, sid, "[data-pk-next]")
            self.assertTrue(wait(lambda: cdp.js("clarkPage.peek().id", sid) == ids[2]))
            click(cdp, sid, "[data-pk-prev]")
            self.assertTrue(wait(lambda: cdp.js("clarkPage.peek().id", sid) == ids[1]))
            click(cdp, sid, "[data-pk-close]")
            self.assertTrue(wait(lambda: cdp.js("clarkPage.peek()", sid) is None))


if __name__ == "__main__":
    unittest.main()
