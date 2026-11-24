"""Row 1046 (v1.2), piece 2: the notices bell in the top bar, in a real browser against the real page. Chrome is required: these tests fail, never skip, without it.

Run: python3 dev/run_tests.py -j 1 test_bell_1046
Covers: no bell while nothing is unread; the bell sits left of search with the name "Notifications, N unread" and the badge (9+ past nine, the true
count in the name); a click opens a non-modal dialog (never by itself) with focus inside; severity shown as a word; Mark as read lowers the count; Mark all
as read empties the badge; Esc and Close give focus back to the bell; the empty state; an action goes to a place inside clark; the bar has no overlap
at 1400 and 900 px. Notices pushed here are made up. Only 1400 and 900 px are tested.
"""
import unittest

from clark import page, theme
import _testpage as testpage
import test_report_editor as tre
from test_inline_67 import size
from test_report_editor import Base
from test_server import chrome

MAKE = ("(function(n, sev){var out=[], d=new Date(); var iso=d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0');"
        "for (var i=0;i<n;i++) out.push({id:'n'+i, severity:sev[i % sev.length], title:'Notice '+i, body:'Body '+i, date:iso});"
        "return out;})")
SEV = "['info','warning','critical']"


def classic_html():
    return page.layer_theme(testpage.html(), theme.css("prototype-2.0"))


class Bell(Base):
    def setUp(self):
        super().setUp()
        self.s.close()
        self.s = tre.real_server(self.store.path, self.store.data_for, page_html=classic_html, seam=self.seam)      # the bell is the Classic theme's; Cards draws none
        self.addCleanup(self.s.close)

    def at(self, cdp, width):
        p = self.visit(cdp)
        size(cdp, p, width, 700)
        p.until("!!document.querySelector('#profile-btn')", "the profile circle shows")
        p.until("!!window.clarkPage && !!window.clarkPage.pushNotices", "the test hook is there")
        return p

    def push(self, p, n):
        p.js(f"window.clarkPage.pushNotices({MAKE}({n}, {SEV}))")

    def test_no_bell_while_nothing_is_unread(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.at(cdp, width)
                p.js("new Promise(r => setTimeout(r, 300))")
                self.assertFalse(p.js("!!document.querySelector('#bell-btn')"))

    def test_the_bell_is_left_of_search_with_its_name_and_badge(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            self.push(p, 3)
            p.until("!!document.querySelector('#bell-btn')", "the bell is drawn")
            got = p.js("(function(){var b=document.querySelector('#bell-btn'), s=document.querySelector('#pal-btn');"
                       "return [b.getAttribute('aria-label'), b.querySelector('.bell-badge').textContent, b.getBoundingClientRect().right <= s.getBoundingClientRect().left, !!document.querySelector('#bell-pop')];})()")
            self.assertEqual(got, ["Notifications, 3 unread", "3", True, False], "drawn, left of search, and shut until clicked")
            self.push(p, 12)
            p.until("document.querySelector('#bell-btn .bell-badge').textContent === '9+'", "the badge caps at 9+")
            self.assertEqual(p.js("document.querySelector('#bell-btn').getAttribute('aria-label')"), "Notifications, 12 unread")

    def test_open_read_and_close(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.at(cdp, width)
                self.push(p, 3)
                p.until("!!document.querySelector('#bell-btn')", "the bell is drawn")
                p.js("document.querySelector('#bell-btn').click()")
                p.until("!!document.querySelector('#bell-pop')", "the popup opened")
                p.until("document.querySelector('#bell-pop').contains(document.activeElement)", "focus went into the popup")
                got = p.js("(function(){var d=document.querySelector('#bell-pop');return [d.getAttribute('role'), d.getAttribute('aria-modal'), d.contains(document.activeElement),"
                           "[...d.querySelectorAll('.bell-sev-w')].map(e => e.textContent), d.querySelectorAll('.bell-item').length, d.getBoundingClientRect().right <= document.documentElement.clientWidth];})()")
                self.assertEqual([got[0], got[1], got[2], sorted(got[3]), got[4], got[5]], ["dialog", None, True, ["Critical", "Info", "Warning"], 3, True])
                p.js("document.querySelector('.bell-one').click()")
                p.until("document.querySelector('#bell-btn').getAttribute('aria-label') === 'Notifications, 2 unread'", "one read")
                p.js("document.querySelector('#bell-all').click()")
                p.until("!document.querySelector('#bell-btn .bell-badge') && !document.querySelector('#bell-all')", "all read: no badge")
                self.assertEqual(p.js("document.querySelector('.bell-empty') ? 1 : 0"), 0, "the three notices stay listed, read")
                p.key("Escape", 0, "Escape", 27)
                p.until("!document.querySelector('#bell-pop')", "Esc closed the popup")
                p.until("document.activeElement && document.activeElement.id === 'bell-btn'", "focus is back on the bell, which stays while it has focus")
                p.js("document.activeElement.blur()")
                p.until("!document.querySelector('#bell-btn')", "nothing unread: the bell is gone once focus leaves it")

    def test_close_gives_focus_back_and_an_action_goes_inside_clark(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            p.js("window.clarkPage.pushNotices([{id:'a', severity:'info', title:'Upgrade available', body:'A newer clark is out.', date:" + MAKE + "(1, ['info'])[0].date, action:{label:'Open Settings', to:'/settings'}}])")
            p.until("!!document.querySelector('#bell-btn')", "the bell is drawn")
            p.js("document.querySelector('#bell-btn').click()")
            p.until("!!document.querySelector('#bell-pop')", "the popup opened")
            p.js("document.querySelector('#bell-close').click()")
            p.until("!document.querySelector('#bell-pop')", "Close closed it")
            p.until("document.activeElement && document.activeElement.id === 'bell-btn'", "focus came back to the bell")
            self.assertEqual(p.js("document.activeElement && document.activeElement.id"), "bell-btn")
            p.js("document.querySelector('#bell-btn').click()")
            p.until("!!document.querySelector('.bell-act')", "the action shows")
            self.assertEqual(p.js("document.querySelector('.bell-act').textContent"), "Open Settings")
            p.js("document.querySelector('.bell-act').click()")
            p.until("!document.querySelector('#bell-pop')", "the action closed the popup")

    def test_close_after_mark_all_as_read_keeps_focus_on_the_bell_until_it_leaves(self):
        """Row 1046: Mark all as read makes the count 0; Close or Esc must still put focus on the bell (it stays drawn until focus leaves)."""
        for how in ("close", "esc"):
            with self.subTest(how):
                with chrome() as cdp:
                    p = self.at(cdp, 1400)
                    p.js("window.clarkPage.pushNotices([{id:'a', severity:'info', title:'Upgrade available', body:'A newer clark is out.', date:" + MAKE + "(1, ['info'])[0].date}])")
                    p.until("!!document.querySelector('#bell-btn')", "the bell is drawn")
                    p.js("document.querySelector('#bell-btn').click()")
                    p.until("!!document.querySelector('#bell-pop')", "the popup opened")
                    p.js("document.querySelector('#bell-all').click()")
                    if how == "close":
                        p.js("document.querySelector('#bell-close').click()")
                    else:
                        p.js("document.querySelector('#bell-pop').dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))")
                    p.until("!document.querySelector('#bell-pop')", "the popup closed")
                    p.until("document.activeElement && document.activeElement.id === 'bell-btn'", "focus is on the bell")

    def test_the_popup_shadow_is_the_token_not_a_literal(self):
        import re
        from pathlib import Path
        css = (Path(__file__).resolve().parent.parent / "src/clark/themes/prototype-2.0/rules-2.css").read_text(encoding="utf-8")
        rule = re.search(r"^\.bell-pop \{[^}]*\}", css, re.M).group(0)
        self.assertIn("box-shadow: var(--shadow)", rule)
        self.assertNotIn("rgba", rule)

    def test_the_bar_has_no_overlap_with_the_bell(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.at(cdp, width)
                self.push(p, 12)
                p.until("!!document.querySelector('#bell-btn')", "the bell is drawn")
                got = p.js("(function(){var r=[...document.querySelectorAll('header.top *')].filter(e => ['BUTTON'].includes(e.tagName) && e.getClientRects().length).map(e => [e.id || e.className, e.getBoundingClientRect()]), bad=[];"
                           "for (var i=0;i<r.length;i++){ if (r[i][1].right > document.documentElement.clientWidth + 0.5) bad.push('past ' + r[i][0]);"
                           "for (var j=i+1;j<r.length;j++) if (r[i][1].left < r[j][1].right - 0.5 && r[j][1].left < r[i][1].right - 0.5 && r[i][1].top < r[j][1].bottom - 0.5 && r[j][1].top < r[i][1].bottom - 0.5) (r[i][0] === 'bell-btn' || r[j][0] === 'bell-btn') && bad.push(r[i][0] + ' over ' + r[j][0]);}"
                           "return bad;})()")
                self.assertEqual(got, [], f"at {width} px")


    def test_database_refreshed_toast_has_its_own_slot_and_the_look(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            p.until("!!window.clarkPage.refreshed", "the test hook is there")
            p.js("window.clarkPage.refreshed()")
            p.until("!!document.querySelector('.toast.refresh')", "the toast is drawn")
            got = p.js("(function(){var t=document.querySelector('.toast.refresh');"
                       "return [t.textContent.indexOf('Database refreshed') >= 0, !!t.querySelector('svg'), !!t.querySelector('[data-undo]'), !!t.querySelector('[data-dismiss]'),"
                       "t.querySelector('.toast-bar').getAttribute('style').indexOf('8000ms') >= 0, getComputedStyle(t).borderLeftWidth];})()")
            self.assertEqual(got, [True, True, False, True, True, "6px"], "words, icon, no Undo, Close, 8 s, teal edge")
            p.js("document.querySelector('.toast.refresh [data-dismiss]').click()")
            p.until("!document.querySelector('.toast.refresh')", "Close takes it away")


    def test_a_critical_notice_also_shows_a_banner_until_it_is_read(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            p.js("window.clarkPage.pushNotices([{id:'c1', severity:'critical', title:'Upgrade required', body:'Install 2.0.4 to carry on.', date:'2026-11-18'},"
                 "{id:'w1', severity:'warning', title:'A new version', body:'', date:'2026-11-18'}])")
            p.until("!!document.querySelector('#crit-banner')", "the banner is drawn")
            got = p.js("(function(){var b=document.querySelector('#crit-banner');return [b.getAttribute('role'), b.textContent.indexOf('Upgrade required.') === 0, document.querySelectorAll('#crit-banner').length];})()")
            self.assertEqual(got, ["alert", True, 1])
            p.js("document.querySelector('#crit-read').click()")
            p.until("!document.querySelector('#crit-banner')", "reading it takes the banner away")
            self.assertTrue(p.js("!!document.querySelector('#bell-btn')"), "the warning is still unread")

    def test_a_warning_alone_shows_no_banner(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            p.js("window.clarkPage.pushNotices([{id:'w1', severity:'warning', title:'A new version', body:'', date:'2026-11-18'}])")
            p.until("!!document.querySelector('#bell-btn')", "the bell is drawn")
            self.assertFalse(p.js("!!document.querySelector('#crit-banner')"))


class CardsDrawsNoBell(Base):
    def test_cards_draws_no_bell_and_no_wrapper_even_with_notices_pushed(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.visit(cdp)
                size(cdp, p, width, 700)
                p.until("!!document.querySelector('#profile-btn')", "the profile circle shows")
                p.until("!!window.clarkPage && !!window.clarkPage.pushNotices", "the test hook is there")
                p.js(f"window.clarkPage.pushNotices({MAKE}(3, {SEV}))")
                p.js("new Promise(r => setTimeout(r, 300))")
                self.assertEqual(p.js("[!!document.querySelector('#bell-btn'), !!document.querySelector('.bell-wrap'), !!document.querySelector('.tb-bell')]"), [False, False, False])


if __name__ == "__main__":
    unittest.main()
