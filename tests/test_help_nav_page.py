"""#642 step 3, Navigation: the Help panel as drawn, in a real browser (follows test_help_panel.py).

Run: python3 dev/run_tests.py test_help_nav_page
Headless Chrome through the shared harness, the real page with fictional demo data, at 1400 and 900 px, in the light and the dark theme.
Covers (1) the jobs on Start here as large links, held ones never shown or linked, (2) the contents list that stays in view with the
current entry marked, (3) "What next" links (on a page built with a fixture guide: none is shipped yet), (4) the way back to the previous
place beside Back, (5) the keyboard: search, the contents list and the entry by Tab and the arrow keys.
The pure parts (the held rule, the history, the next list) are in test_help_navigation.py.
"""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import TOOLS  # noqa: F401  (puts dev/tools on the path)
import _testpage as testpage
from _help_shown import RAW, shown_content
from test_report_editor import Base
from test_help_navigation import MOCKUP
import build_page  # noqa: E402

TOPBAR = 56
HELD_PLACES = ("howto-find-work-items", "howto-import-and-export", "howto-improve-wording-with-ai", "ref-peek")     # still held: never shown, never linked
SIZES = (1400, 900)
THEMES = ("light", "dark")


def set_size(cdp, p, w):
    cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)


def set_theme(cdp, p, scheme):
    cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, p.sid)


class Nav(Base):
    def in_help(self, cdp, tab=None):
        p = self.visit(cdp)
        p.js("try { localStorage.removeItem('clark.helpTab'); } catch (e) {}")
        from test_help_panel import full_help_from_menu   # "?" opens the context peek now; the profile menu's Help is the full Help
        full_help_from_menu(p, "Help opened from the profile menu")
        if tab:
            p.js(f"document.querySelector('#hpTab-{tab}').click()")
            p.until(f"document.querySelector('#hpTab-{tab}').getAttribute('aria-selected') === 'true' && !!document.querySelector('.hp-idx a')", f"the {tab} tab")
        return p

    # ---------- (1) the jobs ----------
    def test_start_here_shows_the_five_jobs_as_large_links_and_never_a_held_place(self):
        from test_server import chrome
        with chrome() as cdp:
            p = self.in_help(cdp)
            shown = [j for j in shown_content()["start"]["jobs"]]
            self.assertEqual(len(shown), 5)
            for w in SIZES:
                set_size(cdp, p, w)
                self.assertEqual(p.js("!!document.querySelector('#hp-later')"), False)
                self.assertEqual(p.js("[...document.querySelectorAll('.hp-job')].map(a => [a.querySelector('b').textContent, a.querySelector('span').textContent])"),
                                 [[j[1], j[2]] for j in shown], f"{w}: the shown jobs, in the owner's order, with the mockup's words")
                big = p.js("[...document.querySelectorAll('.hp-job')].map(a => { const r = a.getBoundingClientRect(); return [r.height, r.width, parseFloat(getComputedStyle(a.querySelector('b')).fontSize), a.tagName] })")
                for h, wd, size, tag in big:
                    self.assertGreaterEqual(h, 56, f"{w}: a large link")      # the mockup's job card is about 70 px tall
                    self.assertGreater(wd, 400)
                    self.assertGreaterEqual(size, 18)
                    self.assertEqual(tag, "A")
                self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"), f"{w}: no sideways scroll")
            self.assertEqual(p.js("document.querySelector('.hp-start-jobs h2').textContent"), "Start here")
            self.assertEqual(p.js("document.querySelector('.hp-start-jobs .hp-lead').textContent"), "Pick a job and follow the steps. Each one is short.")
            self.assertEqual(p.js("document.querySelector('.hp-jobs-h').textContent"), "The five jobs")
            self.assertEqual(p.js("document.querySelector('.hp-undo').textContent"), "Made a mistake? Undo the last change")
            self.assertEqual(p.js("document.querySelector('.hp-undo a').dataset.hlink"), "howto-undo-a-mistake")
            self.assertEqual(p.js("getComputedStyle(document.querySelector('.hp-undo')).fontSize !== getComputedStyle(document.querySelector('.hp-job b')).fontSize"), True, "a small link beside the jobs")
            for held in HELD_PLACES:
                self.assertEqual(p.js(f"document.querySelector('[data-hlink=\"{held}\"], [data-hnext=\"{held}\"]')"), None, f"{held} is held: no link to it")
            self.assertNotIn("Excel", p.js("document.querySelector('.hp-start-jobs').textContent"))
            for scheme in THEMES:
                set_theme(cdp, p, scheme)
                for w in SIZES:
                    set_size(cdp, p, w)
                    self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"), f"{scheme} {w}")

    def test_a_job_opens_its_entry_and_every_link_on_start_here_has_a_place(self):
        from test_server import chrome
        with chrome() as cdp:
            p = self.in_help(cdp)
            places = p.js("[...document.querySelectorAll('#hpPane [data-hlink]')].map(a => a.dataset.hlink)")
            self.assertTrue(places)
            for place in places:
                p.js(f"window.clarkPage.help.open({json.dumps(place)})")
                p.until(f"!!document.querySelector('#hp-{place}.hp-found')", f"{place} exists and opens")
            p.js("document.querySelector('#hpTab-start').click()")
            p.until("!!document.querySelector('.hp-job')", "back on Start here")
            p.js("document.querySelector('.hp-job[data-hlink=guide-add-a-section-from-a-template]').click()")
            p.until("!!document.querySelector('#hp-guide-add-a-section-from-a-template.hp-found') && document.querySelector('#hpTab-howto').getAttribute('aria-selected') === 'true'", "the job opened its entry under How do I…")

    # ---------- (2) the contents list ----------
    def test_the_contents_list_stays_in_view_and_marks_where_you_are(self):
        from test_server import chrome
        with chrome() as cdp:
            p = self.in_help(cdp, "howto")
            for scheme in THEMES:
                set_theme(cdp, p, scheme)
                for w in SIZES:
                    set_size(cdp, p, w)
                    p.js("window.scrollTo(0, 0)")
                    p.until("window.scrollY === 0", "at the top")
                    self.assertEqual(p.js("getComputedStyle(document.querySelector('.hp-idx')).position"), "sticky")
                    p.js("window.scrollTo(0, document.documentElement.scrollHeight)")
                    p.until("window.scrollY > 1500", f"{scheme} {w}: scrolled far down")
                    r = p.js("(function(){var r=document.querySelector('.hp-idx').getBoundingClientRect(); return [r.top, r.bottom, innerHeight, r.right <= document.querySelector('.hp-task').getBoundingClientRect().left]})()")
                    self.assertGreaterEqual(r[0], 0, f"{scheme} {w}: the list is not scrolled off the top")
                    self.assertLessEqual(r[0], TOPBAR + 20, f"{scheme} {w}: it stays under the top bar")
                    self.assertGreater(r[1], 200, f"{scheme} {w}: and has height to show")
                    self.assertTrue(r[3], f"{scheme} {w}: beside the entries, not over them")
                    self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"), f"{scheme} {w}: no sideways scroll")
                    self.assertTrue(p.js("var cur=document.querySelector('.hp-idx a[aria-current]'); !!cur && cur.getBoundingClientRect().height > 0"), f"{scheme} {w}: one link is marked")
                    self.assertEqual(p.js("document.querySelectorAll('.hp-idx a[aria-current]').length"), 1)
            # the mark is drawn in tokens: a different background and an edge, in both themes
            for scheme in THEMES:
                set_theme(cdp, p, scheme)
                self.assertNotEqual(p.js("getComputedStyle(document.querySelector('.hp-idx a.cur')).backgroundColor"), p.js("getComputedStyle(document.querySelector('.hp-idx a:not(.cur)')).backgroundColor"), scheme)
                self.assertEqual(p.js("getComputedStyle(document.querySelector('.hp-idx a.cur')).borderLeftWidth"), "3px")

    def test_the_marked_link_follows_a_click_and_the_scroll(self):
        from test_server import chrome
        with chrome() as cdp:
            p = self.in_help(cdp, "howto")
            ids = p.js("[...document.querySelectorAll('.hp-idx a')].map(a => a.dataset.hlink)")
            self.assertEqual(p.js("document.querySelector('.hp-idx a[aria-current]').dataset.hlink"), ids[0], "opens at the first entry")
            target = ids[5]
            p.js(f"document.querySelector('.hp-idx a[data-hlink={target}]').click()")
            p.until(f"document.querySelector('.hp-idx a[aria-current]').dataset.hlink === {json.dumps(target)}", "a click marks its link")
            p.until(f"!!document.querySelector('#hp-{target}.hp-found')", "and opens its entry")
            p.js("window.scrollTo(0, 0)")
            p.until(f"document.querySelector('.hp-idx a[aria-current]').dataset.hlink === {json.dumps(ids[0])}", "scrolling to the top marks the first entry again")
            p.js("window.scrollTo(0, document.documentElement.scrollHeight)")
            p.until(f"document.querySelector('.hp-idx a[aria-current]').dataset.hlink !== {json.dumps(ids[0])}", "scrolling down moves the mark")

    def test_the_last_entry_is_marked_at_the_foot_of_each_tab(self):
        """Issue 793: at the foot of the page the last contents entry is the marked one, as the entry on screen."""
        from test_server import chrome
        with chrome() as cdp:
            p = self.in_help(cdp)
            for tab in ("start", "howto", "reference"):
                p.js(f"document.querySelector('#hpTab-{tab}').click()")
                p.until(f"document.querySelector('#hpTab-{tab}').getAttribute('aria-selected') === 'true' && !!document.querySelector('.hp-idx a')", f"the {tab} tab")
                for w in SIZES:
                    for scheme in THEMES:
                        set_size(cdp, p, w)
                        set_theme(cdp, p, scheme)
                        p.js("window.scrollTo(0, 0)")
                        p.until("window.scrollY === 0", "at the top")
                        p.js("window.scrollTo(0, document.documentElement.scrollHeight)")
                        p.until("window.scrollY > 500", "scrolled down")
                        p.until("(() => { const l = [...document.querySelectorAll('.hp-idx a')]; return l.length > 0 && l[l.length - 1].getAttribute('aria-current') === 'true'; })()",
                                f"{tab} {scheme} {w}: the last contents entry is marked at the foot")

    def test_start_here_has_its_contents_list_with_the_jobs(self):
        from test_server import chrome
        with chrome() as cdp:
            p = self.in_help(cdp)
            self.assertEqual(p.js("[...document.querySelectorAll('.hp-idx a')].map(a => a.textContent)"),
                             ["Start here"] + [j[1] for j in shown_content()["start"]["jobs"]] + [x["t"] for x in shown_content()["howto"]["tasks"] if x["id"] not in [j[0] for j in shown_content()["start"]["jobs"] if len(j) < 5]] + [shown_content()["start"]["text"]["where_title"], shown_content()["start"]["text"]["rules_title"]])   # a job that opens a guide leaves its how-to entry in the list
            self.assertEqual(p.js("document.querySelector('.hp-idx a[aria-current]').textContent"), "Start here")
            self.assertEqual(p.js("getComputedStyle(document.querySelector('.hp-idx')).position"), "sticky")

    def test_search_sits_top_right_on_the_title_row_and_back_rides_the_tab_row(self):
        from test_server import chrome
        with chrome() as cdp:
            p = self.in_help(cdp)
            self.assertTrue(p.js("var h=document.querySelector('.hp-head h1').getBoundingClientRect(), s=document.querySelector('.hp-search').getBoundingClientRect(); s.top < h.bottom && s.left > h.right && Math.abs(s.right - document.querySelector('.hp-head').getBoundingClientRect().right) < 2"), "search at the top right of the title row")
            self.assertTrue(p.js("var t=document.querySelector('.hp-tabs').getBoundingClientRect(), b=document.querySelector('#hpBack').getBoundingClientRect(); b.left > t.right - 1 && Math.abs((b.top + b.bottom) / 2 - (t.top + t.bottom) / 2) < 20"), "Back on the tab row")
            self.assertEqual(p.js("document.querySelector('#hpBack').textContent"), "Back")

    # ---------- (4) the way back ----------
    def test_a_way_back_to_the_previous_place_sits_beside_back(self):
        from test_server import chrome
        with chrome() as cdp:
            p = self.in_help(cdp)
            self.assertEqual(p.js("document.querySelector('#hpPrev')"), None, "nowhere to go back to yet")
            p.js("document.querySelector('.hp-job[data-hlink=guide-add-a-section-from-a-template]').click()")
            p.until("!!document.querySelector('#hp-guide-add-a-section-from-a-template.hp-found')", "the job opened")
            self.assertEqual(p.js("document.querySelector('#hpPrev').textContent"), "Back to Start here")
            self.assertTrue(p.js("var a=document.querySelector('#hpBack').getBoundingClientRect(), b=document.querySelector('#hpPrev').getBoundingClientRect(); b.left >= a.right - 1 && Math.abs(a.top - b.top) < 8"), "beside Back, on its row")
            self.assertEqual(p.js("document.querySelector('#hpBack').textContent"), "Back", "Back still means Back")
            ids = p.js("[...document.querySelectorAll('.hp-idx a')].map(a => a.dataset.hlink)")
            p.js(f"document.querySelector('.hp-idx a[data-hlink={ids[2]}]').click()")
            p.until(f"!!document.querySelector('#hp-{ids[2]}.hp-found')", "a second place")
            self.assertEqual(p.js("document.querySelector('#hpPrev').textContent"), "Back to Add a section from a template")
            p.js("document.querySelector('#hpPrev').click()")
            p.until("!!document.querySelector('#hp-guide-add-a-section-from-a-template.hp-found')", "the way back opened the place before")
            self.assertEqual(p.js("document.querySelector('.hp-idx a[aria-current]').dataset.hlink"), "guide-add-a-section-from-a-template")
            self.assertEqual(p.js("document.querySelector('#hpPrev').textContent"), "Back to Start here", "and the one before that is next")
            p.js("document.querySelector('#hpPrev').click()")
            p.until("document.querySelector('#hpTab-start').getAttribute('aria-selected') === 'true' && !!document.querySelector('.hp-job')", "back on Start here")
            self.assertEqual(p.js("document.querySelector('#hpPrev')"), None, "the history is used up")
            self.assertEqual(p.js("!!document.querySelector('#help')"), True, "and Help is still open")

    def test_the_way_back_has_room_at_900_and_in_both_themes_and_back_still_closes_help(self):
        from test_server import chrome
        with chrome() as cdp:
            p = self.in_help(cdp)
            p.js("document.querySelector('.hp-job[data-hlink=guide-add-a-section-from-a-template]').click()")
            p.until("!!document.querySelector('#hpPrev')", "a way back")
            for scheme in THEMES:
                set_theme(cdp, p, scheme)
                for w in SIZES:
                    set_size(cdp, p, w)
                    self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"), f"{scheme} {w}: no sideways scroll")
                    self.assertTrue(p.js("var b=document.querySelector('#hpPrev').getBoundingClientRect(); b.right <= innerWidth && b.left >= 0 && b.height >= 30"), f"{scheme} {w}: in view")
            p.js("document.querySelector('#hpBack').click()")
            p.until("!document.querySelector('#help') && !!document.querySelector('#report')", "Back closes Help, as before")
            from test_help_panel import full_help_from_menu   # "?" opens the context peek now; the profile menu's Help is the full Help
            full_help_from_menu(p, "reopened")
            self.assertEqual(p.js("document.querySelector('#hpPrev')"), None, "a fresh visit starts a fresh history")

    def test_a_tab_change_is_a_place_you_can_go_back_from(self):
        from test_server import chrome
        with chrome() as cdp:
            p = self.in_help(cdp)
            p.js("document.querySelector('#hpTab-reference').click()")
            p.until("document.querySelector('#hpTab-reference').getAttribute('aria-selected') === 'true'", "Reference")
            self.assertEqual(p.js("document.querySelector('#hpPrev').textContent"), "Back to Start here")
            p.js("document.querySelector('#hpPrev').click()")
            p.until("document.querySelector('#hpTab-start').getAttribute('aria-selected') === 'true'", "back on Start here")

    # ---------- (5) the keyboard ----------
    def test_the_contents_list_works_with_the_arrow_keys_and_opens_an_entry(self):
        from test_server import chrome
        with chrome() as cdp:
            p = self.in_help(cdp, "howto")
            ids = p.js("[...document.querySelectorAll('.hp-idx a')].map(a => a.dataset.hlink)")
            self.assertEqual(p.js("[...document.querySelectorAll('.hp-idx a')].filter(a => a.tabIndex === 0).length"), 1, "the list is one stop for Tab")
            p.js("document.querySelector('.hp-idx a[tabindex=\"0\"]').focus()")
            active = "document.activeElement.dataset.hlink"
            p.key("ArrowDown", code="ArrowDown", vk=40)
            self.assertEqual(p.js(active), ids[1])
            p.key("ArrowDown", code="ArrowDown", vk=40)
            p.key("ArrowUp", code="ArrowUp", vk=38)
            self.assertEqual(p.js(active), ids[1])
            p.key("End", code="End", vk=35)
            self.assertEqual(p.js(active), ids[-1])
            p.key("ArrowDown", code="ArrowDown", vk=40)
            self.assertEqual(p.js(active), ids[-1], "stops at the end")
            p.key("Home", code="Home", vk=36)
            self.assertEqual(p.js(active), ids[0])
            p.key("ArrowDown", code="ArrowDown", vk=40)
            p.key("ArrowRight", code="ArrowRight", vk=39)
            p.until(f"document.activeElement.dataset.k === {json.dumps(ids[1])}", "Right opened the entry and moved the focus into it")
            self.assertEqual(p.js("document.activeElement.tabIndex"), 0, "the entry is a stop for Tab")
            self.assertEqual(p.js("document.querySelector('.hp-idx a[aria-current]').dataset.hlink"), ids[1])
            p.key("ArrowLeft", code="ArrowLeft", vk=37)
            self.assertEqual(p.js(active), ids[1], "Left goes back to the entry's link")
            self.assertEqual(p.js("!!document.querySelector('#help')"), True)

    def test_search_the_contents_list_and_the_entry_are_in_tab_order(self):
        from test_server import chrome
        with chrome() as cdp:
            p = self.in_help(cdp, "howto")
            tabbable = p.js("""(function(){
              var sel='a[href],button,input,[tabindex]', out=[];
              document.querySelectorAll('#help '+sel.split(',').join(', #help ')).forEach(function(e){ if (e.tabIndex >= 0 && e.getClientRects().length) out.push(e); });
              var q=document.querySelector('#hpQ'), tab=document.querySelector('#hpTab-howto'), rail=document.querySelector('.hp-idx a[tabindex="0"]'), entry=document.querySelector('#hpPane [data-k][tabindex="0"]');
              return [q,tab,rail,entry].map(function(e){ return out.indexOf(e); });
            })()""")
            self.assertTrue(all(i >= 0 for i in tabbable), f"each is reachable by Tab: {tabbable}")
            self.assertEqual(tabbable, sorted(tabbable), "in the order: search, tabs, contents list, entry")
            self.assertEqual(p.js("document.querySelectorAll('#hpPane [data-k][tabindex=\"0\"]').length"), 1, "one entry is a stop; the rest are reached from the list")
            # and a real Tab press moves along it
            p.js("document.querySelector('#hpQ').focus()")
            order = []
            for _ in range(5):
                p.key("Tab", code="Tab", vk=9)
                order.append(p.js("document.activeElement.closest('.hp-idx') ? 'rail' : (document.activeElement.dataset.k ? 'entry' : document.activeElement.id)"))
            self.assertEqual(order, ["hpTab-howto", "hpBack", "hpPrev", "rail", "entry"], "Tab from the search box: the tabs, the Back buttons at the end of their row, the contents list, then the entry")

    def test_down_from_the_search_box_goes_to_the_contents_list(self):
        from test_server import chrome
        with chrome() as cdp:
            p = self.in_help(cdp, "howto")
            p.js("document.querySelector('#hpQ').focus()")
            p.key("ArrowDown", code="ArrowDown", vk=40)
            self.assertTrue(p.js("!!document.activeElement.closest('.hp-idx')"))
            p.js("document.querySelector('#hpQ').focus()")
            p.type("keys")
            p.until("document.querySelectorAll('#hpRes a.hp-r').length > 0", "results")
            p.js("document.querySelector('#hpQ').focus()")
            p.key("ArrowDown", code="ArrowDown", vk=40)
            self.assertTrue(p.js("document.activeElement.classList.contains('hp-r')"), "with results, Down still goes to the first result")

    def test_the_focus_is_visible_in_both_themes(self):
        from test_server import chrome
        with chrome() as cdp:
            p = self.in_help(cdp, "howto")
            for scheme in THEMES:
                set_theme(cdp, p, scheme)
                p.key("Tab", code="Tab", vk=9)          # a key press makes :focus-visible apply
                p.js("document.querySelector('.hp-idx a[tabindex=\"0\"]').focus()")
                self.assertNotEqual(p.js("getComputedStyle(document.activeElement).outlineStyle"), "none", f"{scheme}: the link shows where the focus is")
                p.js("document.querySelector('#hpPane [data-k][tabindex=\"0\"]').focus()")
                self.assertNotEqual(p.js("getComputedStyle(document.activeElement).outlineStyle"), "none", f"{scheme}: and the entry")


def fixture_content():
    """The whole source with a guide and a few next lists (none ships yet): one next list names a shown place, a held place and the guide."""
    c = copy.deepcopy(RAW)
    c["guides"] = [{"id": "fixture-guide", "t": "Fixture guide", "job": "Check that a wombat can read it.",
                    "steps": [{"d": "Open the **Zebra** screen."}, {"d": "Press `Quokka` twice."}], "result": "A numbat arrives.",
                    "next": ["howto-arrange-the-report", "howto-find-work-items", "ref-keys", "howto-nothing-here"]}]
    for t in c["howto"]["tasks"]:
        if t["id"] == "set-the-health":
            t["next"] = ["guide-fixture-guide", "howto-find-work-items"]
    return c


class WhatNextPage(Base):
    """A page built with a fixture guide (the real source ships none): the same panel, drawn with `next` lists."""
    html = None

    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "helpContent.json"
            path.write_text(json.dumps(fixture_content(), ensure_ascii=False), encoding="utf-8")
            with mock.patch.object(build_page, "help_content_path", lambda held=True: path):
                cls.html = build_page.build("main-test.jsx")

    def setUp(self):
        patch = mock.patch.object(testpage, "html", lambda branding=None: self.html)
        patch.start()
        self.addCleanup(patch.stop)
        super().setUp()

    def open_at(self, cdp, place):
        p = self.visit(cdp)
        p.js(f"window.clarkPage.help.open({json.dumps(place)})")
        p.until(f"!!document.querySelector('#hp-{place}')", f"opened at {place}")
        return p

    def test_a_guide_ends_with_what_next_links_to_shown_places_only(self):
        from test_server import chrome
        with chrome() as cdp:
            p = self.open_at(cdp, "guide-fixture-guide")
            self.assertEqual(p.js("document.querySelector('#hp-guide-fixture-guide .hp-next h4').textContent"), "What next")
            self.assertEqual(p.js("[...document.querySelectorAll('#hp-guide-fixture-guide .hp-next a')].map(a => [a.dataset.hnext, a.textContent])"),
                             [["howto-arrange-the-report", "Move, hide and delete sections"], ["ref-keys", next(s["t"] for s in RAW["reference"]["sections"] if s["id"] == "keys")]],
                             "the held place and the place that does not exist are left out; the order is the guide's")
            self.assertEqual(p.js("document.querySelector('#hp-guide-fixture-guide .hp-next').parentElement === document.querySelector('#hp-guide-fixture-guide')"), True)
            self.assertEqual(p.js("document.querySelector('#hp-guide-fixture-guide').lastElementChild.className"), "hp-next", "at the end of the entry")
            self.assertEqual(p.js("!!document.querySelector('#hp-guide-fixture-guide ol li')"), True)
            self.assertIn("A numbat arrives.", p.js("document.querySelector('#hp-guide-fixture-guide .hp-note').textContent"))

    def test_a_what_next_link_opens_its_place_and_the_way_back_returns(self):
        from test_server import chrome
        with chrome() as cdp:
            p = self.open_at(cdp, "guide-fixture-guide")
            p.js("document.querySelector('#hp-guide-fixture-guide .hp-next a[data-hnext=ref-keys]').click()")
            p.until("!!document.querySelector('#hp-ref-keys.hp-found') && document.querySelector('#hpTab-reference').getAttribute('aria-selected') === 'true'", "the link opened the place under its tab")
            self.assertEqual(p.js("document.querySelector('.hp-idx a[aria-current]').dataset.hlink"), "ref-keys")
            self.assertEqual(p.js("document.querySelector('#hpPrev').textContent"), "Back to Fixture guide")
            p.js("document.querySelector('#hpPrev').click()")
            p.until("!!document.querySelector('#hp-guide-fixture-guide.hp-found')", "back at the guide")

    def test_an_entry_with_a_next_list_shows_it_and_one_without_shows_none(self):
        from test_server import chrome
        with chrome() as cdp:
            p = self.open_at(cdp, "howto-set-the-health")
            self.assertEqual(p.js("[...document.querySelectorAll('#hp-howto-set-the-health .hp-next a')].map(a => a.dataset.hnext)"), ["guide-fixture-guide"],
                             "the held entry in its list is not linked")
            self.assertEqual(p.js("document.querySelectorAll('#hpPane .hp-next').length"), 6, "the four written entries, this one and the guide: no other entry has a next list")
            self.assertEqual(p.js("document.querySelectorAll('.hp-task:not(#hp-howto-set-the-health):not(.hp-guide):not(#hp-howto-add-a-work-item):not(#hp-howto-write-the-weekly-report):not(#hp-howto-publish-the-report):not(#hp-howto-undo-a-mistake) .hp-next').length"), 0)

    def test_what_next_in_both_themes_and_widths(self):
        from test_server import chrome
        with chrome() as cdp:
            p = self.open_at(cdp, "guide-fixture-guide")
            for scheme in THEMES:
                set_theme(cdp, p, scheme)
                for w in SIZES:
                    set_size(cdp, p, w)
                    self.assertTrue(p.js("var r=document.querySelector('#hp-guide-fixture-guide .hp-next a').getBoundingClientRect(); r.right <= innerWidth && r.width > 20"), f"{scheme} {w}")
                    self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"), f"{scheme} {w}: no sideways scroll")
                    self.assertNotEqual(p.js("getComputedStyle(document.querySelector('#hp-guide-fixture-guide .hp-next a')).color"),
                                        p.js("getComputedStyle(document.querySelector('#help')).backgroundColor"), f"{scheme}: the link can be read")

    def test_the_guide_has_its_place_in_the_contents_list_and_a_search_finds_it(self):
        from test_server import chrome
        with chrome() as cdp:
            p = self.open_at(cdp, "guide-fixture-guide")
            self.assertEqual(p.js("document.querySelector('.hp-idx a[data-hlink=guide-fixture-guide]').textContent"), "Fixture guide")
            self.assertEqual(p.js("document.querySelector('.hp-idx a[aria-current]').dataset.hlink"), "guide-fixture-guide")
            p.js("document.querySelector('#hpQ').focus()")
            p.type("zebra")
            p.until("document.querySelectorAll('#hpRes a.hp-r').length > 0", "results")
            self.assertEqual(p.js("document.querySelector('#hpRes a.hp-r').dataset.hit"), "guide-fixture-guide")


if __name__ == "__main__":
    unittest.main()
