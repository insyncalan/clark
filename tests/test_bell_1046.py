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
                self.assertTrue(p.js("!!document.querySelector('#bell-btn')"), "the bell stays while its popup is open, even with nothing unread")
                self.assertEqual(p.js("document.querySelector('.bell-empty') ? 1 : 0"), 0, "the three notices stay listed, read")
                p.key("Escape", 0, "Escape", 27)
                p.until("!document.querySelector('#bell-pop')", "Esc closed the popup")
                p.until("!document.querySelector('#bell-btn')", "nothing unread: the bell is gone")

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
            p.until("location.hash.indexOf('#settings') === 0", "the action opened the Settings page")

    def test_the_badge_shows_for_one_and_for_many(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            self.push(p, 1)
            p.until("!!document.querySelector('#bell-btn')", "the bell is drawn")
            self.assertEqual(p.js("[...document.querySelectorAll('#bell-btn .bell-badge')].map(e => e.textContent)"), ["1"], "one unread: the badge shows 1")
            self.push(p, 2)
            p.until("document.querySelector('#bell-btn').getAttribute('aria-label') === 'Notifications, 2 unread'", "two unread")
            self.assertEqual(p.js("[...document.querySelectorAll('#bell-btn .bell-badge')].map(e => e.textContent)"), ["2"])

    def test_the_popup_closes_on_an_outside_click_and_stays_on_an_inside_one(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            self.push(p, 2)
            p.until("!!document.querySelector('#bell-btn')", "the bell is drawn")
            p.js("document.querySelector('#bell-btn').click()")
            p.until("!!document.querySelector('#bell-pop')", "the popup opened")
            p.js("document.querySelector('.bell-ttl').dispatchEvent(new MouseEvent('mousedown', {bubbles: true}))")
            p.js("new Promise(r => setTimeout(r, 200))")
            self.assertTrue(p.js("!!document.querySelector('#bell-pop')"), "a press inside leaves it open")
            p.until("(document.body.dispatchEvent(new MouseEvent('mousedown', {bubbles: true})), !document.querySelector('#bell-pop'))", "a press outside closed it")

    def test_the_date_is_day_month_year(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            p.js("window.clarkPage.pushNotices([{id:'d', severity:'info', title:'Dated', body:'', date:'2026-11-03'}])")
            p.until("!!document.querySelector('#bell-btn')", "the bell is drawn")
            p.js("document.querySelector('#bell-btn').click()")
            p.until("!!document.querySelector('.bell-date')", "the date shows")
            self.assertEqual(p.js("document.querySelector('.bell-date').textContent"), "03-11-2026")

    def test_the_popup_shadow_is_the_token_not_a_literal(self):
        import re
        from pathlib import Path
        css = (Path(__file__).resolve().parent.parent / "src/clark/themes/prototype-2.0/rules.css").read_text(encoding="utf-8")
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
