"""#45 page side: the At a glance tiles, Project health, the use case summary and the section styles, in a real browser.

Run: python3 dev/run_tests.py test_glance_page
The page is the committed one, served by a real server whose change and undo routes are the real clark.changes over a real store
in a temporary folder (fictional data). Laptop widths only: 1400 and 900 px, light and dark. The published tests open the finished
file from file:// and check what is in its bytes. The clock needs no fixing: every planted due date is in 2020.
"""
import json
import re
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from _demo import USER
from _paths import ROOT, SRC
from test_report_editor import ALT, EMPTY_BRANDING, Base, Pg, tearDownModule  # noqa: F401
from test_server import chrome, wait

from clark import page, publish

LONG = "2020-01-01"


def plant(self):
    """Overdue actions (one Sensitive, one client-off), a High risk, a pending decision and two use cases, in project ABC."""
    d = self.demo
    uc = d.use_case
    with self.store.step("dashboard", USER) as st:
        self.uc2 = st.create("use_cases", {"project": "ABC", "title": "Payment runs", "status": "Flag", "ref": "1.2",
                                           "headline": "One supplier file still fails", "standing": "<p>Two of three files load.</p>", "source": "demo"})
        st.update("use_cases", uc, {"ref": "1.1", "headline": "Matching is live", "standing": "<p>Live for two suppliers.</p>"})
    self.a_open = d.action(description="Chase the supplier file", owner="Pat Demo", due_date=LONG, use_case=uc)
    self.a_secret = d.action(description="ZQ-sensitive step", owner="Sam Demo", due_date=LONG, use_case=uc)
    self.a_off = d.action(description="ZQ-client-off step", owner="Lee Demo", due_date=LONG, use_case=uc, client_visible=0)
    self.a_later = d.action(description="Plan the second wave", owner="Pat Demo", due_date="2099-01-01", use_case=self.uc2)
    with self.store.step("dashboard", USER) as st:
        st.create("raid", {"project": "ABC", "type": "Risk", "description": "Key person leaves", "raised": "2026-10-01", "source": "demo",
                           "impact": "High", "likelihood": "High", "owner": "Pat Demo"})
        st.create("decisions", {"project": "ABC", "decision": "Use the shared drive", "source": "demo", "status": "Pending", "needed_by": "2020-02-01"})
    self.store.con.execute("INSERT OR IGNORE INTO item_labels (item_id, label) VALUES (?, 'Sensitive')", (self.a_secret,))
    self.store.con.commit()


class Setup(Base):
    def setUp(self):
        super().setUp()
        plant(self)

    def show(self, cdp, width=1400, dark=False, hash_="#dashboard&p=ABC", settings=False):
        p = Pg.at(self, cdp, self.s.port, hash_)
        cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, p.sid)      # a headless page is otherwise not focused, so blur() fires nothing
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        if dark:
            p.js("document.documentElement.dataset.theme = 'dark'")
        if settings:
            return p
        p.ready()
        p.until("!!document.querySelector('.glance')", "the tiles drew")
        return p

    def tiles(self, p):
        return p.js("[...document.querySelectorAll('.glance > .tcell')].map(e => e.dataset.tile)")

    def rows(self):
        return {r["tile"]: r for r in self.store.read("glance_tiles", "ABC")}

    def project(self):
        return self.store.read("projects", ref="ABC")

    def undo(self, p):
        p.js("document.querySelector('[data-undo]').click()")
        p.until("document.querySelector('.toast-text') && document.querySelector('.toast-text').textContent.length > 0 && !document.querySelector('[data-undo]')", "undone")


class Tiles(Setup):
    def test_view_shows_three_tiles_with_the_numbers_and_decisions_hidden_by_default(self):
        with chrome() as cdp:
            p = self.show(cdp)
            self.assertEqual(self.tiles(p), ["health", "overdue", "risks"], "Decisions needed is hidden until shown")
            self.assertEqual(p.js("document.querySelector('[data-fig=overdue] .v').textContent"), "3")
            self.assertEqual(p.js("document.querySelector('[data-fig=risks] .v').textContent"), "1")
            self.assertEqual(p.js("document.querySelector('[data-fig=health] .pill').textContent"), "On track")
            self.assertEqual(p.js("document.querySelectorAll('.milestone-tile, [data-fig=milestones], [data-fig=next]').length"), 0)

    def test_health_is_two_tile_widths_at_1400_and_900_in_light_and_dark(self):
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark), chrome() as cdp:
                    p = self.show(cdp, width, dark)
                    box = lambda t: p.js(f"(() => {{ const r = document.querySelector('[data-tile={t}]').getBoundingClientRect(); return [r.left, r.width]; }})()")
                    health, overdue = box("health"), box("overdue")
                    gap = p.js("parseFloat(getComputedStyle(document.querySelector('.glance')).columnGap)")
                    self.assertAlmostEqual(health[1], 2 * overdue[1] + gap, delta=1.5)
                    self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"), "no sideways scroll")

    def test_text_contrast_is_at_least_4_5_to_1_in_light_and_dark(self):
        script = """(() => {
          const rgb = (c) => c.match(/[\\d.]+/g).slice(0, 3).map(Number);
          const lum = ([r, g, b]) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
          const ratio = (a, b) => { const x = lum(rgb(a)), y = lum(rgb(b)); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
          const out = [];
          for (const sel of ['[data-fig=overdue] .k', '[data-fig=overdue] .v', '[data-fig=overdue] .dd', '[data-fig=overdue] .tw', '[data-fig=health] .hreason', '[data-fig=health] .pill', '.ucstrip', '.ucbar .uctitle', '.ucbar .uchead', '.ucbar .ucsteps']) {
            const el = document.querySelector(sel); if (!el) { out.push([sel, 0]); continue; }
            let bg = el, back = 'rgba(0, 0, 0, 0)';
            while (bg && /rgba\\(.*, 0\\)|transparent/.test(back)) { back = getComputedStyle(bg).backgroundColor; bg = bg.parentElement; }
            out.push([sel, ratio(getComputedStyle(el).color, back)]);
          }
          return out;
        })()"""
        for dark in (False, True):
            with self.subTest(dark=dark), chrome() as cdp:
                p = self.show(cdp, 1400, dark)
                for sel, r in p.js(script):
                    if sel == "[data-fig=health] .hreason":
                        continue                       # no reason written yet: nothing drawn
                    self.assertGreaterEqual(r, 4.5, f"{sel} in {'dark' if dark else 'light'}")

    def test_a_tile_opens_the_work_items_it_counts(self):
        with chrome() as cdp:
            p = self.show(cdp)
            p.js("document.querySelector('[data-fig=overdue]').click()")
            p.until("location.hash.startsWith('#work&p=ABC&f=')", "Work items opened")
            p.until("document.querySelectorAll('#work tbody tr[data-id]').length === 3", "the list holds the three it counted")

    def test_the_outline_is_drawn_on_the_bottom_left_and_fades(self):
        with chrome() as cdp:
            p = self.show(cdp)
            got = p.js("(() => { const e = getComputedStyle(document.querySelector('[data-fig=overdue]'), '::after'); return [e.borderTopWidth, e.maskImage || e.webkitMaskImage, e.borderTopColor]; })()")
            self.assertEqual(got[0], "2px")
            self.assertIn("45deg", got[1], "the mask runs from the bottom-left corner")
            self.assertNotEqual(got[2], "rgba(0, 0, 0, 0)", "an overdue tile has its red outline")
            bg = p.js("getComputedStyle(document.querySelector('[data-fig=overdue]')).backgroundColor")
            self.assertEqual(bg, p.js("getComputedStyle(document.querySelector('[data-fig=risks]')).backgroundColor"), "tiles are neutral, whatever the colour")


class Health(Setup):
    def test_a_pick_with_no_reason_asks_for_one_and_saves_both_together_with_one_undo(self):
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            before = self.project()
            self.assertIsNone(before["health_reason"])
            p.js("document.querySelector('#health-pill').click()")
            p.until("!!document.querySelector('#health-menu')", "the pick menu opened (not a cycle)")
            self.assertEqual(p.js("[...document.querySelectorAll('#health-menu [role=menuitemradio]')].map(b => b.textContent)"), ["On track", "At risk", "Off track"])
            self.assertEqual(p.js("[...document.querySelectorAll('#health-menu [role=menuitemradio]')].map(b => b.getAttribute('aria-checked'))"), ["true", "false", "false"],
                             "the one in use is marked checked")
            self.assertEqual(p.js("[...document.querySelectorAll('#health-menu .hpill')].map(b => b.className.replace('hpill ', ''))"), ["g", "a", "r"], "each word is a coloured pill")
            self.assertEqual(p.js("document.querySelectorAll('#health-menu svg[data-icn=check]').length"), 1, "one check mark shape, on the one in use")
            p.js("document.querySelector('#health-menu [data-kind=\"At risk\"]').click()")
            p.until("document.activeElement && document.activeElement.hasAttribute('data-reason')", "the reason box took focus")
            time.sleep(0.4)
            self.assertEqual(self.project()["health"], "On track", "nothing is saved before the reason is written")
            p.type("Test environment is late")
            p.js("document.activeElement.blur()")
            p.saved()
            now = self.project()
            self.assertEqual((now["health"], now["health_reason"]), ("At risk", "Test environment is late"))
            self.assertEqual(p.js("document.querySelector('[data-fig=health] .pill').textContent"), "At risk")
            self.undo(p)
            now = self.project()
            self.assertEqual((now["health"], now["health_reason"]), ("On track", None), "Undo put the health and the reason back together")
            self.assertEqual(p.js("document.querySelector('[data-fig=health] .pill').textContent"), "On track")

    def test_the_menu_keys_and_the_filled_pill(self):
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            fill = p.js("(() => { const b = getComputedStyle(document.querySelector('#health-pill')); return [b.textTransform, b.borderTopLeftRadius, b.backgroundColor, document.querySelectorAll('#health-pill svg').length]; })()")
            self.assertEqual(fill[0], "uppercase")
            self.assertEqual(fill[1], "4px", "a block, not a round pill")
            self.assertNotEqual(fill[2], "rgba(0, 0, 0, 0)", "the pill is filled")
            self.assertEqual(fill[3], 0, "no chevron")
            p.js("document.querySelector('#health-pill').focus()")
            p.js("document.querySelector('#health-pill').dispatchEvent(new KeyboardEvent('keydown', {key: 'ArrowDown', bubbles: true}))")
            p.until("!!document.querySelector('#health-menu')", "Down opened the menu")
            p.js("document.activeElement.dispatchEvent(new KeyboardEvent('keydown', {key: 'ArrowDown', bubbles: true}))")
            self.assertEqual(p.js("document.activeElement.getAttribute('data-kind')"), "At risk", "Down moves to the next pill")
            p.js("document.activeElement.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))")
            p.until("!document.querySelector('#health-menu')", "Esc closed the menu")
            self.assertEqual(p.js("document.activeElement.id"), "health-pill", "focus went back to the pill")

    def test_a_pick_leaving_the_box_empty_changes_nothing(self):
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            p.js("document.querySelector('#health-pill').click()")
            p.until("!!document.querySelector('#health-menu')", "menu")
            p.js("document.querySelector('#health-menu [data-kind=\"Off track\"]').click()")
            p.until("document.activeElement && document.activeElement.hasAttribute('data-reason')", "focus")
            time.sleep(0.4)                                    # the menu has closed; the box keeps focus
            self.assertTrue(p.js("document.activeElement.hasAttribute('data-reason')"))
            p.js("document.activeElement.blur()")
            wait(lambda: "needs a reason" in p.toast(), 3)
            self.assertIn("needs a reason", p.toast())
            self.assertEqual(self.project()["health"], "On track")

    def test_a_pick_keeps_the_reason_as_it_stands_and_undo_still_works(self):
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            p.js("document.querySelector('[data-reason]').focus()")
            p.type("Waiting on the test environment")
            p.js("document.activeElement.blur()")
            p.saved()
            self.assertEqual(self.project()["health_reason"], "Waiting on the test environment")
            p.clear_toast()
            p.js("document.querySelector('#health-pill').click()")
            p.until("!!document.querySelector('#health-menu')", "menu")
            p.js("document.querySelector('#health-menu [data-kind=\"Off track\"]').click()")
            p.saved()
            self.assertEqual((self.project()["health"], self.project()["health_reason"]), ("Off track", "Waiting on the test environment"))
            self.assertIn("Check that the reason still fits", p.toast())
            self.undo(p)
            self.assertEqual(self.project()["health"], "On track", "a pick that kept the reason can be undone")

    def test_the_reason_is_free_multi_line_text_edited_in_place(self):
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            self.assertEqual(p.js("document.querySelector('[data-reason]').tagName"), "TEXTAREA")
            p.js("document.querySelector('[data-reason]').focus()")
            p.type("First line\nSecond line")
            p.js("document.activeElement.blur()")
            p.saved()
            self.assertEqual(self.project()["health_reason"], "First line\nSecond line")
            p.view()
            self.assertEqual(p.js("document.querySelector('[data-fig=health] .hreason').textContent"), "First line\nSecond line")
            self.assertEqual(p.js("document.querySelectorAll('[data-fig=health] textarea, [data-fig=health] button').length"), 0, "View has no control on health")


class EditTiles(Setup):
    def test_hide_with_the_eye_leaves_it_out_of_view_and_undo_brings_it_back(self):
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            self.assertEqual(self.tiles(p), ["health", "overdue", "risks", "decisions"], "Edit draws the hidden Decisions tile too")
            self.assertEqual(p.js("document.querySelector('[data-tile=decisions]').classList.contains('is-hidden')"), True)
            p.js("document.querySelector('[data-tile=risks] [data-tile-eye]').click()")
            p.saved()
            self.assertEqual(self.rows()["risks"]["hidden"], 1)
            p.view()
            self.assertEqual(self.tiles(p), ["health", "overdue"], "hidden is absent in View, not dimmed")
            p.edit()
            self.undo(p)
            self.assertEqual(self.rows()["risks"]["hidden"], 0)

    def test_project_health_has_no_eye_because_the_published_file_always_carries_it(self):
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            self.assertEqual(p.js("document.querySelectorAll('[data-tile=health] [data-tile-eye]').length"), 0, "no eye on Project health")
            self.assertGreater(p.js("document.querySelectorAll('[data-tile=overdue] [data-tile-eye]').length"), 0, "the other tiles keep theirs")
            self.assertEqual(p.js("document.querySelector('[data-tile=health]').classList.contains('is-hidden')"), False)
            p.view()
            self.assertEqual(self.tiles(p)[0], "health")

    def test_a_hidden_tiles_text_is_at_least_4_5_to_1_in_edit_at_1400_and_900_in_light_and_dark(self):
        script = """(() => {
          const rgb = (c) => c.match(/[\\d.]+/g).slice(0, 3).map(Number);
          const lum = ([r, g, b]) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
          const ratio = (a, b) => { const x = lum(rgb(a)), y = lum(rgb(b)); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
          const out = [];
          if (!document.querySelector('[data-tile=decisions].is-hidden')) return [['hidden tile missing', 0]];
          for (const sel of ['.k', '.v', '.dd', '.tw', '.thid']) {
            const el = document.querySelector('[data-tile=decisions] ' + sel); if (!el) { out.push([sel, 0]); continue; }
            let bg = el, back = 'rgba(0, 0, 0, 0)', op = 1;
            for (let e = el; e; e = e.parentElement) op *= parseFloat(getComputedStyle(e).opacity);
            while (bg && /rgba\\(.*, 0\\)|transparent/.test(back)) { back = getComputedStyle(bg).backgroundColor; bg = bg.parentElement; }
            out.push([sel, op < 1 ? 0 : ratio(getComputedStyle(el).color, back)]);
          }
          return out;
        })()"""
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark), chrome() as cdp:
                    p = self.show(cdp, width, dark)
                    p.edit()
                    p.until("!!document.querySelector('[data-tile=decisions].is-hidden')", "the hidden tile drew")
                    for sel, r in p.js(script):
                        self.assertGreaterEqual(r, 4.5, f"hidden Decisions {sel} (a ratio of 0 means missing or dimmed by opacity)")
                    self.assertEqual(p.js("getComputedStyle(document.querySelector('[data-tile=decisions] .fig')).borderTopStyle"), "dashed")

    def test_decisions_needed_can_be_shown(self):
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            p.js("document.querySelector('[data-tile=decisions] [data-tile-eye]').click()")
            p.saved()
            p.view()
            self.assertEqual(self.tiles(p), ["health", "overdue", "risks", "decisions"])
            self.assertEqual(p.js("document.querySelector('[data-fig=decisions] .v').textContent"), "1")

    def test_alt_and_the_arrows_move_a_tile_one_step_with_one_undo(self):
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            p.js("document.querySelector('[data-tile=overdue] [data-tile-grip]').focus()")
            p.key("ArrowRight", ALT, code="ArrowRight", vk=39)
            p.saved()
            p.until("JSON.stringify([...document.querySelectorAll('.glance > .tcell')].map(e => e.dataset.tile)) === JSON.stringify(['health','risks','overdue','decisions'])", "moved")
            order = sorted(self.rows().values(), key=lambda r: r["sort_order"])
            self.assertEqual([r["tile"] for r in order], ["health", "risks", "overdue", "decisions"])
            self.undo(p)
            self.assertEqual(self.tiles(p), ["health", "overdue", "risks", "decisions"])

    def test_dragging_a_tile_moves_it(self):
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            gx, gy, _ = p.box("[data-tile=risks] [data-tile-grip]")
            tx, ty, _ = p.box("[data-tile=health]")
            p.mouse("mousePressed", gx, gy, 1)
            for step in range(1, 9):
                p.mouse("mouseMoved", gx + (tx - 120 - gx) * step / 8, gy + (ty - gy) * step / 8, 1)
            p.mouse("mouseReleased", tx - 120, ty, 0)
            p.saved()
            self.assertEqual(self.tiles(p)[:2], ["risks", "health"])

    def test_right_click_sets_the_outline_colour_and_undo_puts_it_back(self):
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            p.js("document.querySelector('[data-tile=overdue]').dispatchEvent(new MouseEvent('contextmenu', {bubbles: true, cancelable: true}))")
            p.until("!!document.querySelector('.tilemenu')", "the colour menu")
            self.assertEqual(p.js("[...document.querySelectorAll('.tilemenu [role^=menuitem]')].map(b => b.textContent.replace('✓ ', ''))"),
                             ["Automatic", "Green", "Amber", "Red", "No colour"])
            p.js("document.querySelector('.tilemenu [data-outline=G]').click()")
            p.saved()
            self.assertEqual(self.rows()["overdue"]["outline"], "G")
            self.assertTrue(p.js("document.querySelector('[data-fig=overdue]').classList.contains('rag-g')"))
            self.undo(p)
            self.assertEqual(self.rows()["overdue"]["outline"], "")

    def test_view_has_no_tile_control(self):
        with chrome() as cdp:
            p = self.show(cdp)
            self.assertEqual(p.js("document.querySelectorAll('[data-tile-grip], [data-tile-eye], [data-reason], #health-pill, .tilemenu').length"), 0)
            p.js("document.querySelector('[data-tile=overdue]').dispatchEvent(new MouseEvent('contextmenu', {bubbles: true, cancelable: true}))")
            self.assertEqual(p.js("document.querySelectorAll('.tilemenu').length"), 0)


class UseCases(Setup):
    def test_the_strip_counts_and_the_status_words_line_up_at_1400_and_900(self):
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark), chrome() as cdp:
                    p = self.show(cdp, width, dark)
                    self.assertEqual(p.js("document.querySelector('.uctotal').textContent"), "2 use cases")
                    self.assertEqual(p.js("[...document.querySelectorAll('.ucn')].map(e => e.dataset.count + ':' + e.textContent.trim())"),
                                     ["On track:1 On track", "Flag:1 Flag"])
                    self.assertEqual(p.js("document.querySelectorAll('.meter i').length"), 2)
                    left = p.js("[...document.querySelectorAll('.ucrow [data-word]')].map(e => e.getBoundingClientRect().left)")
                    self.assertEqual(len(left), 2)
                    self.assertLessEqual(max(left) - min(left), 1, "the status words' left edges are equal within 1 px")
                    first = p.js("document.querySelector('.ucrow .ucbar').innerText.replace(/\\s+/g, ' ')")
                    for word in ("1.1", "Invoice matching", "Matching is live", "On track", "3 next steps"):
                        self.assertIn(word, first)

    def test_see_all_counts_only_the_open_items_and_opens_that_same_list(self):
        with self.store.step("dashboard", USER) as st:
            st.update("actions", self.a_open, {"status": "Closed"})
        with chrome() as cdp:
            p = self.show(cdp)
            p.js("document.querySelector('.ucrow .ucbar').click()")
            p.until("!!document.querySelector('[data-seeall]')", "the row opened")
            self.assertEqual(p.js("document.querySelector('[data-seeall]').textContent"), "See all 2 open work items", "the closed action is not counted")
            p.js("document.querySelector('[data-seeall]').click()")
            p.until("location.hash.startsWith('#work&p=ABC&f=')", "Work items opened")
            p.until("document.querySelectorAll('#work tbody tr[data-id]').length === 2", "the list holds the two the link counted")

    def test_a_row_opens_in_place_with_where_it_stands_the_next_steps_and_see_all(self):
        with chrome() as cdp:
            p = self.show(cdp)
            self.assertEqual(p.js("document.querySelectorAll('.ucdetail').length"), 0)
            p.js("document.querySelector('.ucrow .ucbar').click()")
            p.until("!!document.querySelector('.ucdetail')", "the row opened")
            text = p.js("document.querySelector('.ucdetail').innerText")
            self.assertIn("Live for two suppliers.", text)
            self.assertIn("Pat Demo: Chase the supplier file", text)
            self.assertIn("See all 3 open work items", text, "all three linked items are open")
            self.assertEqual(p.js("document.querySelector('.ucbar').getAttribute('aria-expanded')"), "true")
            p.js("document.querySelector('[data-seeall]').click()")
            p.until("location.hash.startsWith('#work&p=ABC&f=')", "Work items opened")
            p.until("document.querySelectorAll('#work tbody tr[data-id]').length === 3", "filtered to the use case")
            p.js("history.back()")
            p.until("!!document.querySelector('.ucrow')", "back on the Dashboard")


class Styles(Setup):
    def test_each_section_style_applies_at_once_and_is_remembered(self):
        with chrome() as cdp:
            p = self.show(cdp, hash_="#settings&p=ABC", settings=True)
            p.until("!!document.querySelector('#personal')", "Personal")
            self.assertEqual(p.js("[...document.querySelectorAll('input[name=secstyle]')].map(i => i.value)"), ["slim", "roomy", "grey", "card"])
            self.assertEqual(p.js("document.querySelector('input[name=secstyle]:checked').value"), "slim", "Slim gaps is the default")
            for value in ("roomy", "grey", "card", "slim"):
                p.js(f"document.querySelector('input[name=secstyle][value={value}]').click()")
                p.until(f"document.documentElement.dataset.secstyle === '{value}'", f"{value} applied")
            p.js("document.querySelector('input[name=secstyle][value=grey]').click()")
            p.js("location.reload()")
            p.until("document.documentElement.dataset.secstyle === 'grey'", "remembered after a reload")
            gap = []
            for value in ("slim", "roomy"):
                p.js(f"document.documentElement.dataset.secstyle = '{value}'")
                p.js("location.hash = '#dashboard&p=ABC'")
                p.until("!!document.querySelector('.secs')", "dashboard")
                gap.append(p.js("parseFloat(getComputedStyle(document.querySelector('.secs')).rowGap)"))
            self.assertGreater(gap[1], gap[0], "Roomy gaps are roomier than Slim gaps")


class Published(Setup):
    def publish(self):
        self.out = tempfile.mkdtemp(prefix="clark-45-")
        self.addCleanup(shutil.rmtree, self.out, ignore_errors=True)
        done = publish.publish(self.store, "ABC", self.out, by_user=USER, now="2026-10-28", branding=EMPTY_BRANDING)
        return Path(done["path"])

    def draw(self, cdp, path, width=1400, dark=False):
        tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Page.navigate", {"url": path.as_uri()}, sid)
        p = Pg(self, cdp, sid)
        p.until("document.documentElement.dataset.ready === '1' && !!document.querySelector('h1')", "the file drew")
        if dark:
            p.js("document.documentElement.dataset.theme = 'dark'")
        return p

    def test_the_file_draws_both_sections_view_only_with_the_files_own_figures(self):
        path = self.publish()
        for width, dark in ((1400, False), (900, True)):
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                p = self.draw(cdp, path, width, dark)
                self.assertEqual(p.js("[...document.querySelectorAll('.glance > .tcell')].map(e => e.dataset.tile)"), ["health", "overdue", "risks"])
                self.assertEqual(p.js("document.querySelector('[data-fig=overdue] .v').textContent"), "1", "the client counts only what the file holds")
                self.assertEqual(p.js("document.querySelectorAll('.glance button, .glance textarea, .glance input, .uc textarea, .uc input').length"), 0)
                self.assertEqual(p.js("document.querySelectorAll('[data-tile-grip], [data-tile-eye], [data-reason], #health-pill').length"), 0)
                self.assertEqual(p.js("document.querySelector('.uctotal').textContent"), "2 use cases")
                health, overdue = (p.js(f"document.querySelector('[data-tile={t}]').getBoundingClientRect().width") for t in ("health", "overdue"))
                self.assertAlmostEqual(health, 2 * overdue + 12, delta=1.5)

    def test_a_use_case_lists_only_linked_items_that_are_client_flagged_and_not_hidden(self):
        path = self.publish()
        text = path.read_text(encoding="utf-8")
        for planted in ("ZQ-sensitive step", "ZQ-client-off step"):
            self.assertNotIn(planted, text, "a Sensitive or client-off item is not in the file at all")
        with chrome() as cdp:
            p = self.draw(cdp, path)
            p.js("document.querySelector('.ucrow .ucbar').click()")
            p.until("!!document.querySelector('.ucdetail')", "opened")
            shown = p.js("document.querySelector('.ucdetail').innerText")
            self.assertIn("Pat Demo: Chase the supplier file", shown)
            self.assertNotIn("ZQ-", shown)
            self.assertIn("See all 1 open work item", shown, "the one item the file keeps")
            self.assertNotIn("Sam Demo", shown)
            self.assertNotIn("Lee Demo", shown)

    def test_a_hidden_tile_and_a_hidden_use_case_are_absent(self):
        self.store.con.execute("UPDATE use_cases SET client_visible = 0 WHERE id = ?", (self.uc2,))
        self.store.con.commit()
        status, _ = self.real_change({"project": "ABC", "kind": "glance_tiles", "op": "update", "id": "risks", "changes": {"hidden": 1}})
        self.assertEqual(status, 200)
        path = self.publish()
        with chrome() as cdp:
            p = self.draw(cdp, path)
            self.assertEqual(p.js("[...document.querySelectorAll('.glance > .tcell')].map(e => e.dataset.tile)"), ["health", "overdue"], "absent, not dimmed")
            self.assertEqual(p.js("document.querySelector('.uctotal').textContent"), "1 use case")
            self.assertNotIn("Payment runs", p.js("document.body.innerText"))

    def test_the_file_takes_the_style_it_was_published_with(self):
        path = self.publish()
        raw = path.read_text(encoding="utf-8")
        marked = raw.replace('"v":1', '"style":"grey","v":1', 1)
        self.assertNotEqual(raw, marked)
        copy = path.with_name("styled.html")
        copy.write_text(marked, encoding="utf-8")
        with chrome() as cdp:
            p = self.draw(cdp, copy)
            self.assertEqual(p.js("document.documentElement.dataset.secstyle"), "grey")


class PublishedPage(unittest.TestCase):
    def test_page_view_html_holds_nothing_that_only_the_owner_has(self):
        text = (SRC / "clark" / "page" / "page-view.html").read_text(encoding="utf-8")
        for owner_only in ("data-tile-grip", "data-tile-eye", "data-reason", "health-pill", "/api/change", "Hide from the published report", "Section style", "Slim gaps"):
            self.assertNotIn(owner_only, text, owner_only)


if __name__ == "__main__":
    unittest.main()
