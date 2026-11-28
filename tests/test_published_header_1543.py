"""Row 1543 PR 1: the published header's pages group sits where the editor's does (same right edge, same line), and the room the
editor's right-hand buttons use is reserved, so the pages do not move between the two. In a real browser, light and dark, 1400 px,
and the 1200 and 1100 px edge checks (the 900 px bar: AP7 below). Fictional data.

Run: python3 dev/run_tests.py test_published_header_1543        (needs Chrome; run only while the machine's load is under 70)
"""
import base64
import json
from unittest import mock

import _backdrop_pics as pics
import test_glance_page as glance
from clark import publish
from clark import store as store_module
from _demo import USER
from _new_page import reload_to_new_page
from test_published_one_bar import HIDE, colour, ratio
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome
from _classic_page import classic

# The pages group and the bar: the group's gaps to the bar's right and bottom edges, each tab's left edge, and the right-hand group's box.
PROBE = """(() => {
  const bar = document.querySelector('header.top'), tabs = bar.querySelector('.tabs'), b = bar.getBoundingClientRect(), t = tabs.getBoundingClientRect();
  const q = (n) => Math.round(n * 100) / 100, end = bar.querySelector('.cm-wrap, .hdr-end'), e = end ? end.getBoundingClientRect() : null;
  const list = [...tabs.querySelectorAll('[role=tab]')].map((x) => x.getBoundingClientRect());
  return {gapRight: q(b.right - t.right), gapBottom: q(b.bottom - t.bottom), n: list.length, lefts: list.map((r) => q(r.left)), lastRight: q(list[list.length - 1].right),
    endRight: e ? q(b.right - e.right) : null, wide: document.documentElement.scrollWidth <= innerWidth};
})()"""
WIDTHS = ((1400, False), (1400, True), (1200, False), (1100, False))


class Header1543(glance.Published):
    def editor_bar(self, cdp, width, dark):
        p = self.show(cdp, width, dark)
        p.until("!!document.querySelector('header.top .tab')", "the editor's bar drew")
        return p.js(PROBE)

    def published_bar(self, width, dark, three=False):
        if three:      # a use case the client may not see: the file has no Use cases page
            self.store.con.execute("UPDATE use_cases SET client_visible = 0 WHERE project = 'ABC'")
            self.store.con.commit()
        path = self.publish()
        with chrome() as cdp:
            p = self.draw(cdp, path, width, dark)
            p.until("!!document.querySelector('header.top-file .tab')", "the published bar drew")
            return p.js(PROBE)

    def test_published_header_pages_same_right_edge_as_editor(self):
        for width, dark in WIDTHS:
            with self.subTest(width=width, dark=dark):
                with chrome() as cdp:
                    e = self.editor_bar(cdp, width, dark)
                f = self.published_bar(width, dark)
                self.assertEqual(f["n"], e["n"], "both bars show the same pages")
                self.assertAlmostEqual(f["gapRight"], e["gapRight"], delta=0.05, msg=f"published pages end {f['gapRight']} px from the bar's right edge, the editor's {e['gapRight']}")
                self.assertAlmostEqual(f["gapBottom"], e["gapBottom"], delta=0.05, msg=f"published pages end {f['gapBottom']} px above the bar's bottom, the editor's {e['gapBottom']}")
                for a, b in zip(f["lefts"], e["lefts"]):
                    self.assertAlmostEqual(a, b, delta=1.5, msg=f"the pages sit {f['lefts']} in the file, {e['lefts']} in the editor")
                self.assertTrue(f["wide"], "no sideways scroll")

    def test_published_header_pages_right_aligned_three_or_four(self):
        cases = ((1400, False), (1400, True), (1100, False))
        fours = {c: self.published_bar(*c) for c in cases}
        for width, dark in cases:
            with self.subTest(width=width, dark=dark):
                four = fours[(width, dark)]
                self.assertEqual(four["n"], 4)
                three = self.published_bar(width, dark, three=True)
                self.assertEqual(three["n"], 3, "a report with no Use cases page has three pages")
                self.assertEqual(three["gapRight"], four["gapRight"], "the pages group still ends at the same right edge")
                self.assertEqual(three["lastRight"], four["lastRight"], "its last page has not moved")
                self.assertEqual(three["endRight"], four["endRight"], "nothing to the right of the pages moved")
                self.assertGreater(three["lefts"][0], four["lefts"][0], "the group is shorter on its left")

    def probe_file(self, js, width, dark):
        path = self.publish()
        with chrome() as cdp:
            p = self.draw(cdp, path, width, dark)
            p.until("!!document.querySelector('header.top-file .tab')", "the published bar drew")
            return p.js(js)

    def test_published_header_no_as_at(self):
        head_js = """(() => ({head: document.querySelector('header.top').textContent,
          boxes: document.querySelectorAll('header.top .asat, header.top .asat-wrap, header.top button.asat, header.top input[type=date]').length}))()"""
        for width, dark in ((1400, False), (1400, True), (900, False), (900, True)):
            with self.subTest(width=width, dark=dark):
                path = self.publish()
                with chrome() as cdp:
                    p = self.draw(cdp, path, width, dark)
                    p.until("!!document.querySelector('header.top-file .tab')", "the published bar drew")
                    got = p.js(head_js)
                    p.js("document.querySelector('.cm-badge').click()")
                    p.until("!!document.querySelector('[role=menu]') && document.querySelector('[role=menu]').textContent.trim().length > 0", "the profile menu opened")
                    menu = p.js("document.querySelector('[role=menu]').textContent")
                self.assertGreater(len(menu.strip()), 0, "control: the menu was read after it drew")
                self.assertNotRegex(got["head"], r"(?i)as at", "no As at in the header")
                self.assertNotRegex(menu, r"(?i)as at", "no As at in the profile menu either")
                self.assertEqual(got["boxes"], 0)
                self.assertIn("Weekly report", got["head"], "the line under the project name stays (this fixture has no week ending date; the date text is unchanged)")

    def test_published_header_switcher_and_profile_sizes(self):
        """AP5, at 1400 and at 900, light and dark: the switcher is a bare icon (no fill, no border), the profile circle is filled with the brand cyan."""
        js = """(() => { const r = (s) => { const b = document.querySelector(s).getBoundingClientRect(); return [Math.round(b.width), Math.round(b.height), Math.round(document.querySelector("header.top").getBoundingClientRect().right - b.right)]; };
          const c = document.createElement('i'); c.style.background = 'var(--brand-cyan)'; document.body.appendChild(c);
          const cs = (s) => getComputedStyle(document.querySelector(s)), cyan = getComputedStyle(c).backgroundColor, t = cs('.cm-theme');
          return {theme: r('.cm-theme'), badge: r('.cm-badge'), cyan: cyan, badgeFill: cs('.cm-badge').backgroundColor, themeFill: t.backgroundColor,
                  themeBorder: parseFloat(t.borderTopWidth) + parseFloat(t.borderLeftWidth)}; })()"""
        for width, dark in ((1400, False), (1400, True), (900, False), (900, True)):
            with self.subTest(width=width, dark=dark):
                got = self.probe_file(js, width, dark)
                self.assertEqual(got["theme"][:2], [32, 32], "the light and dark button is 32 px (ticket AP5; 38 px is the editor's search button width)")
                self.assertEqual(got["badge"][:2], [32, 32], "the profile circle is 32 px")
                self.assertEqual(got["badgeFill"], got["cyan"], "the profile circle is filled with the brand cyan")
                self.assertIn(got["themeFill"], ("rgba(0, 0, 0, 0)", "transparent"), "the switcher is a bare icon: no fill")
                self.assertEqual(got["themeBorder"], 0, "the switcher has no border")
                if width == 1400:
                    self.assertEqual(got["badge"][2], 28, "the circle ends 28 px from the bar's right edge, as the editor's")

    def test_published_header_no_edit_controls(self):
        js = """(() => { const h = document.querySelector('header.top');
          return {n: h.querySelectorAll('.tb-ask, .tb-act:not(#pub-search-btn), .hdr-end, .bell, [aria-label="Ask clark"], [aria-label="Client visible"]').length,      // row 1543 AP8: the search button is the one .tb-act a published header has
                  btns: [...h.querySelectorAll('button')].map((b) => b.className).sort()}; })()"""
        for width, dark in ((1400, False), (1400, True), (900, False), (900, True)):
            with self.subTest(width=width, dark=dark):
                got = self.probe_file(js, width, dark)
                self.assertEqual(got["n"], 0, f"no editor control in the published header: {got['btns']}")

    # ---- Row 1543 part 1: the search (AP8, AP9, AP12). The read only panel, the keys and the size check are part 2. ----
    def plant_search(self):
        """Words the file holds (a client message, a section) and words only the team has (a client-off row, a hidden row, a hidden section, a team note)."""
        self.plant_more_work()
        with self.store.step("dashboard", USER) as st:
            st.update("actions", self.a_open, {"client_message": "ZQ-client-words about the bank"})
            st.create("actions", {"project": "ABC", "description": "Visible step", "owner": "Kim Demo", "raised": "2026-10-01", "source": "demo", "due_date": "2099-01-01",
                                  "latest_update": "ZQ-team-note-text"})
            st.create("report_sections", {"project": "ABC", "sort_order": 50, "type": "text", "title": "Supplier notes", "body": "<p>ZQ-section-words rollout</p>"})
            st.create("report_sections", {"project": "ABC", "sort_order": 51, "type": "text", "title": "Team plan", "body": "<p>ZQ-hidden-section-words</p>", "hidden": 1})
        return self.publish()

    def search(self, p, q):
        """Type `q` in the open box and return the result rows as [label, page] once the list is the one for `q`."""
        p.js(f"(() => {{ const i = document.getElementById('report-search-q'); i.value = {json.dumps(q)}; i.dispatchEvent(new Event('input', {{bubbles: true}})); }})()")
        p.until(f"document.querySelector('.rs-list').dataset.for === {json.dumps(q)}", f"the results for {q!r} drew")
        return p.js("[...document.querySelectorAll('.rs-row')].map((b) => [b.querySelector('.rs-label').textContent, b.dataset.kind])")

    def open_box(self, p):
        """Wide: the search button. At 900 px and narrower the bar has no button (as the editor's): the first entry of the report menu opens the same box. Clicks only."""
        p.until("!!document.getElementById('client-menu-btn')", "the bar drew")
        if p.js("innerWidth <= 900"):
            p.js("document.getElementById('client-menu-btn').click()")
            p.until("!!document.querySelector('#client-menu [data-row=search]')", "the menu has the search entry")
            p.js("document.querySelector('#client-menu [data-row=search]').click()")
        else:
            p.until("!!document.getElementById('pub-search-btn')", "the button drew")
            p.js("document.getElementById('pub-search-btn').click()")
        p.until("!!document.querySelector('dialog#report-search[open]') && document.activeElement === document.getElementById('report-search-q')", "the search box opened with focus in it")

    def test_published_search_button_same_as_editor(self):
        edit_js = """(() => { const b = document.getElementById('pal-btn'), r = b.getBoundingClientRect(), c = getComputedStyle(b), t = document.querySelector('header.top .tabs').getBoundingClientRect();
          return {w: Math.round(r.width), h: Math.round(r.height), border: c.borderTopWidth + c.borderTopStyle, radius: c.borderTopLeftRadius, fromTabs: Math.round((r.left - t.right) * 10) / 10}; })()"""
        pub_js = """(() => { const b = document.getElementById('pub-search-btn'), r = b.getBoundingClientRect(), c = getComputedStyle(b), t = document.querySelector('header.top .tabs').getBoundingClientRect(), w = document.querySelector('.cm-wrap').getBoundingClientRect();
          return {w: Math.round(r.width), h: Math.round(r.height), border: c.borderTopWidth + c.borderTopStyle, radius: c.borderTopLeftRadius, name: b.getAttribute('aria-label'), tip: b.title,
                  fromTabs: Math.round((r.left - t.right) * 10) / 10, beforeSwitcher: r.right <= w.left, gap: Math.round(w.left - r.right), endRight: Math.round(document.querySelector('header.top').getBoundingClientRect().right - w.right), inBar: r.top >= 0 && r.bottom <= document.querySelector('header.top').getBoundingClientRect().bottom,
                  count: document.querySelectorAll('#pub-search-btn').length, wide: document.documentElement.scrollWidth <= innerWidth}; })()"""
        with chrome() as cdp:
            p = self.show(cdp, 1400, False)
            p.until("!!document.getElementById('pal-btn')", "the editor's search button drew")
            ed = p.js(edit_js)
        self.assertEqual((ed["w"], ed["h"]), (38, 28), "control: the editor's button is 38 by 28")
        for width, dark in ((1400, False), (1400, True)):
            with self.subTest(width=width, dark=dark):
                got = self.probe_file(pub_js, width, dark)
                self.assertEqual(got["count"], 1)
                self.assertEqual((got["w"], got["h"]), (38, 28), "38 px wide by 28 px high")
                self.assertEqual((got["border"], got["radius"]), (ed["border"], ed["radius"]), "the editor's border and corners")
                self.assertEqual((got["name"], got["tip"]), ("Go to or do", "Go to or do (Ctrl or Cmd + K)"), "the editor's name and tooltip")
                self.assertTrue(got["beforeSwitcher"] and got["inBar"] and got["wide"], f"the button is in the bar, left of the switcher, with no sideways scroll: {got}")
                self.assertAlmostEqual(got["fromTabs"], ed["fromTabs"], delta=0.6, msg="it sits where the editor's search button does, 22 px after the pages")

    def test_published_search_is_the_first_menu_entry_at_900_and_not_in_the_bar(self):
        """PM ruling (row 1543, as the editor's SearchButton.jsx:8 and ProfileMenu.jsx:113, item 1177): at 900 px and narrower the bar has no search button; "Go to or do" is the first entry of the report menu and opens the same box. At 1400 the button is there and the menu has no such entry. Clicks only."""
        path = self.plant_search()
        menu_js = """(() => [...document.querySelectorAll('#client-menu [role=menuitem]')].map((x) => x.textContent.trim()).slice(0, 2))()"""
        for width, dark in ((1400, False), (1400, True), (901, False), (900, False), (900, True)):      # 901 is the first width with the button (the editor's breakpoint is max-width 900)
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                p = self.draw(cdp, path, width, dark)
                p.until("!!document.getElementById('client-menu-btn')", "the bar drew")
                bar = p.js("document.querySelector('header.top-file').innerHTML.includes('Go to or do')")      # read before the menu opens (the menu panel sits inside the bar)
                p.js("document.getElementById('client-menu-btn').click()")
                p.until("!!document.querySelector('#client-menu [role=menuitem]')", "the menu opened")
                first = p.js(menu_js)
                if width == 900:
                    self.assertEqual((p.js("!!document.getElementById('pub-search-btn')"), bar), (False, False), "no search button, and no 'Go to or do' word, in the bar")
                    self.assertEqual(first[0], "Go to or do", f"it is the first menu entry: {first}")
                    p.js("document.querySelector('#client-menu [data-row=search]').click()")
                    p.until("!!document.querySelector('dialog#report-search[open]') && document.activeElement === document.getElementById('report-search-q')", "the entry opens the search box")
                    self.assertEqual(p.js("document.querySelectorAll('dialog#report-search').length"), 1, "the one box")
                else:
                    self.assertEqual(p.js("!!document.getElementById('pub-search-btn')"), True, "the button is in the bar")
                    self.assertNotIn("Go to or do", first, "the menu has no such entry when the button is there")

    def test_published_search_box_placeholder_and_open(self):
        path = self.plant_search()
        for width, dark in ((1400, False), (1400, True), (900, False), (900, True)):
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                p = self.draw(cdp, path, width, dark)
                p.until("!!document.getElementById('client-menu-btn')", "the bar drew")
                self.assertEqual(p.js("!!document.querySelector('dialog#report-search')"), False, "no box until the button is pressed")
                self.open_box(p)
                got = p.js("""(() => { const d = document.getElementById('report-search'), r = d.getBoundingClientRect(), i = document.getElementById('report-search-q');
                  return {ph: i.placeholder, inView: r.left >= 0 && r.right <= innerWidth && r.top >= 0 && r.bottom <= innerHeight, wide: document.documentElement.scrollWidth <= innerWidth, rows: document.querySelectorAll('.rs-row').length,
                          none: !document.querySelector('.rs-none').hidden, expanded: (document.getElementById('pub-search-btn') || {getAttribute: () => 'true'}).getAttribute('aria-expanded')}; })()""")
                self.assertEqual(got["ph"], "Search this report")
                self.assertTrue(got["inView"] and got["wide"], f"the box fits the window: {got}")
                self.assertEqual((got["rows"], got["none"], got["expanded"]), (0, False, "true"), "an empty box lists nothing and says nothing")
                self.assertEqual(self.search(p, "zzzz-nothing"), [])
                self.assertEqual(p.js("document.querySelector('.rs-none').hidden"), False, "nothing found says so")
                self.assertEqual(p.js("document.querySelector('.rs-none').textContent"), "Nothing matches.")
                p.js("document.querySelector('dialog#report-search').dispatchEvent(new Event('cancel', {cancelable: true}))")
                if width == 900:
                    p.until("!document.querySelector('dialog#report-search')", "closing takes the box away")
                else:
                    p.until("!document.querySelector('dialog#report-search') && document.activeElement === document.getElementById('pub-search-btn')", "closing puts focus back on the button")

    def plant_added_page(self):
        """An added page shown to the client with one text section (publish.py client_pages), then the file."""
        from clark import changes
        sections = json.dumps([{"id": "s1", "type": "text", "title": "Added page head", "body": "<p>ZQ-added-page-words</p>"}])
        status, body = changes.make_change(self.store.path, [], USER)({"project": "ABC", "kind": "added_pages", "op": "new", "values": {"name": "Plans page", "starter": "blank", "sections": sections, "client": 1, "sort_order": 1}})
        self.assertEqual(status, 200, body)
        return self.publish()

    def test_search_finds_exactly_the_added_page_words_the_published_file_draws(self):
        """Search follows what is drawn. Whatever the page draws of the added page's words (none, or all) is exactly what the search finds: a word found but not drawn, or drawn but not found, fails."""
        path = self.plant_added_page()
        text = path.read_text(encoding="utf-8")
        self.assertIn("ZQ-added-page-words", text, "the file does carry the page")
        words = ("ZQ-added-page-words", "Added page head")
        for width, dark in ((1400, False), (1400, True), (900, False), (900, True)):
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                p = self.draw(cdp, path, width, dark)
                p.until("!!document.querySelector('header.top-file .tab')", "the bar drew")
                p.js("location.hash = '#page:ABC-PG-001'")
                p.until("location.hash === '#page:ABC-PG-001'", "the address changed")
                drawn = {w for w in words if p.js(f"document.body.innerText.includes({json.dumps(w)})")}
                self.open_box(p)
                found = {w for w in words if self.search(p, w)}
                self.assertEqual(found, drawn, f"the words the search finds are the words the page draws (found {sorted(found)}, drawn {sorted(drawn)})")

    def test_published_search_only_what_the_file_holds(self):
        path = self.plant_search()
        wants = (("Chase the supplier", "Chase the supplier file", "work"), ("Pat Demo", "Chase the supplier file", "work"), ("ZQ-client-words", "Chase the supplier file", "work"),
                 ("Key person", "Key person leaves", "work"), ("shared drive", "Use the shared drive", "work"), ("Pilot live", "Pilot live", "milestones"),
                 ("Payment runs", "1.2 Payment runs", "usecases"), ("ZQ-section-words", "Supplier notes", "dashboard"))
        for width, dark in ((1400, False), (1400, True), (900, False), (900, True)):
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                p = self.draw(cdp, path, width, dark)
                self.open_box(p)
                for q, label, page in wants:
                    self.assertIn([label, page], self.search(p, q), f"{q!r} finds {label!r}")
                self.assertEqual(self.search(p, self.a_open)[0], ["Chase the supplier file", "work"], "a work item by its ID, first (the section that lists it follows)")
                self.assertEqual(self.search(p, "ZQ-team-note-text"), [], "a team note is not searched")

    def test_published_search_opens_the_page_of_a_result(self):
        path = self.plant_search()
        with chrome() as cdp:
            p = self.draw(cdp, path, 1400, False)
            self.open_box(p)
            self.search(p, "Pilot live")
            p.js("document.querySelector('.rs-row').click()")
            p.until("!document.querySelector('dialog#report-search') && location.hash.startsWith('#milestones')", "the result's page opened and the box closed")

    # ---- Row 1543 part 2 (AP11): the keys. Real key events (Input.dispatchKeyEvent), widths 1400 and 900, light and dark. ----
    def press(self, p, key, code, vk, modifiers=0, text=None):
        for kind in ("keyDown", "keyUp"):
            args = {"type": kind, "key": key, "code": code, "windowsVirtualKeyCode": vk, "modifiers": modifiers}
            if text and kind == "keyDown":
                args["text"] = text
            p.cdp.call("Input.dispatchKeyEvent", args, p.sid)

    def test_published_search_keyboard(self):
        """AP11: Ctrl or Cmd + K opens the box (and the page stops the browser's own use of the keys); a plain k, with Alt or with Shift, does not; Esc closes it;
        Up and Down walk the results (the ends wrap) and Enter opens the chosen one."""
        path = self.plant_search()
        CTRL, META, ALT, SHIFT = 2, 4, 1, 8
        for width, dark in ((1400, False), (1400, True), (900, False), (900, True)):
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                p = self.draw(cdp, path, width, dark)
                p.until("!!document.getElementById('client-menu-btn')", "the bar drew")
                p.js("window.__seen = []; window.addEventListener('keydown', (e) => window.__seen.push([e.key, e.defaultPrevented]))")
                box = "!!document.querySelector('dialog#report-search[open]')"
                for mods in (ALT | CTRL, SHIFT | CTRL, 0):
                    self.press(p, "k", "KeyK", 75, mods, text="k" if not mods else None)
                    self.assertEqual(p.js(box), False, f"K with modifiers {mods} does not open the box")
                self.press(p, "k", "KeyK", 75, CTRL)
                p.until(box + " && document.activeElement === document.getElementById('report-search-q')", "Ctrl + K opens the box with focus in it")
                self.assertEqual(p.js("window.__seen.filter((s) => s[0] === 'k').map((s) => s[1])"), [False, False, False, True], "only Ctrl + K is taken from the browser")
                self.press(p, "Escape", "Escape", 27)
                p.until("!document.querySelector('dialog#report-search')", "Esc closes the box")
                self.press(p, "k", "KeyK", 75, META)
                p.until(box, "Cmd + K opens the box")
                self.press(p, "k", "KeyK", 75, 0, text="k")
                self.assertEqual(p.js("document.getElementById('report-search-q').value"), "k", "a plain k typed in the box is a letter and the box stays")
                self.assertEqual(p.js(box), True)
                rows = self.search(p, "ZQ")
                self.assertGreaterEqual(len(rows), 3, f"control: several results to walk: {rows}")
                n = len(rows)
                p.until("document.querySelector('.rs-row').hasAttribute('data-active')", "the first result is chosen")
                at = lambda want: p.until(f"[...document.querySelectorAll('.rs-row')].findIndex((b) => b.hasAttribute('data-active')) === {want}", f"the chosen result is {want}")
                for i in range(n + 1):
                    self.press(p, "ArrowDown", "ArrowDown", 40)
                    at((i + 1) % n)      # Down walks the results and wraps from the last to the first
                self.press(p, "ArrowUp", "ArrowUp", 38)
                at(0)      # Up goes back one
                self.press(p, "ArrowUp", "ArrowUp", 38)
                at(n - 1)      # Up from the first wraps to the last
                self.press(p, "ArrowUp", "ArrowUp", 38)
                at(n - 2)
                self.press(p, "ArrowDown", "ArrowDown", 40)
                at(n - 1)
                want = p.js(f"document.querySelectorAll('.rs-row')[{n - 1}].dataset.kind")
                self.assertNotEqual(want, p.js("document.querySelector('.rs-row').dataset.kind"), "control: the last result is on another page than the first, so opening the first would show")
                self.press(p, "Enter", "Enter", 13)
                p.until(f"!document.querySelector('dialog#report-search') && location.hash.startsWith('#' + {json.dumps(want)})", "Enter opens the page of the chosen result and closes the box")

    def test_published_search_hidden_item_not_found(self):
        path = self.plant_search()
        text = path.read_text(encoding="utf-8")
        team_only = ("ZQ-client-off step", "ZQ-client-off risk", "ZQ-hidden risk", "ZQ-client-off decision", "ZQ-hidden decision", "ZQ-hidden-section-words", "ZQ-team-note-text", "Team plan")
        for words in team_only:
            self.assertNotIn(words, text, f"control: {words!r} is not in the file at all")
        for width, dark in ((1400, False), (1400, True), (900, False), (900, True)):
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                p = self.draw(cdp, path, width, dark)
                self.open_box(p)
                self.assertEqual(len(self.search(p, "ZQ-section-words")), 1, "control: the box finds what the file holds")
                for words in team_only + ("ZQ-hidden", "ZQ-client-off", "ZQ-team"):
                    self.assertEqual(self.search(p, words), [], f"{words!r} (team only) returns 0 results")
                self.assertEqual(p.js("document.querySelector('.rs-none').hidden"), False)


# Row 1543 AP4: what the published page shows for a day that has passed. Read from the drawn page: its text and the words in its labels, tips and titles,
# and the elements that carry the late look (red or amber late tags, the red milestone marks and the red sub-lines).
LATE_WORDS = r"(?i)\b(overdue|late|days? late|d late|yesterday)\b"
LATE_PROBE = """(() => {
  const keep = (e) => !e.closest('[data-fig]');      // the Dashboard's four tiles are not part of AP4's list (reported, not changed here)
  const text = [...document.querySelectorAll('main *')].filter((e) => keep(e) && e.children.length === 0).map((e) => e.textContent).join(' | ');
  const attrs = [...document.querySelectorAll('main [aria-label], main [title], main [data-tip]')].filter(keep)
    .map((e) => [e.getAttribute('aria-label'), e.getAttribute('title'), e.getAttribute('data-tip')].filter(Boolean).join(' ')).join(' | ');
  const bad = [...document.querySelectorAll('.late, .tp-late, .due-l.late, .msl-sub.late, .mst.c-red, .mv-mk.c-red, .node.c-red, .cal-ms.c-red, .mtk-chip .c-red, .tpl-dates-row.is-late')].filter(keep).map((e) => e.className);
  return {text, attrs, bad};
})()"""


class Late1543:      # the tests below are methods of Header1543 (mixed in at the end of the file)
    def plant_late(self):
        """An action 3 days ahead of the publish day (2026-10-28), a milestone whose agreed date has passed, and one slipped past its agreed date."""
        self.a_soon = self.demo.action(description="Book the review room", owner="Pat Demo", due_date="2026-10-31")
        with self.store.step("dashboard", USER) as st:
            gone = st.create("milestones", {"project": "ABC", "name": "Passed gate", "baseline_date": "2026-10-01", "forecast_date": "2026-10-05", "source": "demo"})
            slip = st.create("milestones", {"project": "ABC", "name": "Slipped gate", "baseline_date": "2026-12-01", "forecast_date": "2026-12-20", "source": "demo"})
            st.create("report_sections", {"project": "ABC", "type": "keydates", "title": "Key dates", "sort_order": 900,
                                          "body": store_module.check_section_body("keydates", json.dumps({"v": 1, "items": [{"milestone": gone}, {"milestone": slip}]}))})
        self.demo.plant_builtin_sections()

    def peek_due(self, p):
        """The peek of the action whose date has passed: the class of its Due date chip's icon and the chip's text (read from the board card's peek)."""
        p.js("document.querySelector('header.top [data-view=work]').click()")
        p.until("!!document.querySelector('[data-layout=board]')", "the board switch drew")
        p.js("document.querySelector('[data-layout=board]').click()")
        p.until("!!document.querySelector('#work-board article .bc-main')", "the board drew")
        p.js("[...document.querySelectorAll('#work-board article')].find((x) => x.textContent.includes('Chase the supplier file')).querySelector('.bc-main').click()")
        p.until("!!document.querySelector('[data-peek] [data-row=due] .pkc-ic')", "the peek's Due date chip drew")
        return p.js("(() => { const c = document.querySelector('[data-peek] [data-row=due]'); return {cls: c.querySelector('.pkc-ic').className, text: c.textContent, late: c.classList.contains('late')}; })()")

    def peek_ms(self, p, name):
        """The file's peek of a milestone, opened from the Milestones list: its text and the elements that carry a red or amber look."""
        p.js("document.querySelector('header.top [data-view=milestones]').click()")
        p.until("document.querySelectorAll('main .msl-row').length > 0", "the milestones drew")
        p.js("[...document.querySelectorAll('main .msl-row')].find((x) => x.textContent.includes('%s')).querySelector('.msl-cells').click()" % name)
        p.until("!!document.querySelector('[data-peek] [data-ms-head]')", f"the peek of {name} drew")
        return p.js("(() => { const e = document.querySelector('[data-peek]'); return {text: e.textContent, bad: [...e.querySelectorAll('.late, .c-red, .ic-r, .ic-a, .c-amber')].map((x) => x.className)}; })()")

    def pages(self, p):
        """The text, labels and late-look elements of each page the file has: Dashboard, Work items, Milestones."""
        out = {}
        for v in ("dashboard", "work", "milestones"):
            if p.js(f"!!document.querySelector('header.top [data-view={v}]')"):
                p.js(f"document.querySelector('header.top [data-view={v}]').click()")
                p.until(f"document.querySelector('header.top [data-view={v}]').getAttribute('aria-selected') === 'true' && document.querySelectorAll('main .sec, main tr[data-id], main .msl-row, main [data-ms]').length > 0", f"{v} drew")
                out[v] = p.js(LATE_PROBE)
                if v == "dashboard":
                    for key, title in (("soon", "Book the review room"), ("over", "Chase the supplier file")):
                        out[v][key] = p.js("(() => { const r = [...document.querySelectorAll('.wl-row')].find((x) => x.textContent.includes('%s')), e = r && r.querySelector('.ico-w'); return e ? e.className : 'NONE'; })()" % title)
        return out

    def test_published_report_never_highlights_late(self):
        self.plant_late()
        real = publish.read_inputs

        def with_board(*a, **k):      # the Work items board is how a file opens the peek (row 1533: the author's switch)
            inputs = real(*a, **k)
            inputs["data"]["project"]["show_board_client"] = 1
            return inputs
        with mock.patch.object(publish, "read_inputs", with_board):
            path = self.publish()
        for width, dark in ((1400, False), (1400, True), (900, False), (900, True)):
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                p = self.draw(cdp, path, width, dark)
                p.until("!!document.querySelector('header.top-file .tab')", "the published bar drew")
                seen = self.pages(p)
                self.assertGreaterEqual(len(seen), 3, f"control: the three pages were read, {sorted(seen)}")
                self.assertIn("Passed gate", seen["milestones"]["text"], "control: the milestone with a passed date is on the page")
                self.assertIn("Chase the supplier file", seen["work"]["text"] + seen["dashboard"]["text"], "control: the overdue action is on the page")
                for v, got in seen.items():
                    self.assertNotRegex(got["text"], LATE_WORDS, f"{v}: no late word in the text")
                    self.assertNotRegex(got["attrs"], LATE_WORDS, f"{v}: no late word in a label, tip or title")
                    self.assertEqual(got["bad"], [], f"{v}: no late look")
                peek = self.peek_due(p)
                self.assertNotRegex(peek["cls"], r"\bic-[ra]\b", f"the peek's Due date icon of the passed date has no red and no amber: {peek}")
                self.assertNotRegex(peek["text"], LATE_WORDS, "and the peek says no late word")
                for name in ("Passed gate", "Slipped gate"):
                    ms = self.peek_ms(p, name)
                    self.assertIn(name, ms["text"], "control: the milestone's own peek is open")
                    self.assertNotRegex(ms["text"], LATE_WORDS, f"{name}: no late word in the peek: {ms['text']}")
                    self.assertEqual(ms["bad"], [], f"{name}: no red or amber look in the peek")
                self.assertIn("Expected later", seen["milestones"]["text"], "'Expected later' stays, plain")
                self.assertRegex(seen["dashboard"]["soon"], r"\ba\b", "amber for 'due within 7 days' stays")
                self.assertNotRegex(seen["dashboard"]["over"], r"\b[ra]\b", "the action whose date has passed has no red and no amber")


# Row 1543 AP4, additions (WO-M22710): no Overdue actions tile, no Late Gantt status, no Overdue in the Word copy of a published file.
class More1543:
    def plant_gantt(self):
        """A line whose end passed (2026-10-10, publish day 2026-10-28) and one still running, with the Gantt tab on for the client."""
        with self.store.step("dashboard", USER) as st:
            st.update("projects", "ABC", {"show_gantt_client": 1, "show_gantt_editor": 1, "gantt_hidden_columns": ""})
            st.create("report_sections", {"project": "ABC", "type": "gantttable", "title": "Plan table", "sort_order": 950, "body": "", "beside": 0, "hidden": 0})
            for n, (name, a, b) in enumerate((("Passed task", "2026-10-01", "2026-10-10"), ("Running task", "2026-10-20", "2026-12-20")), 1):
                st.create("gantt_lines", {"project": "ABC", "type": "task", "name": name, "start": a, "end": b, "pct": 20, "show": 1, "sort_order": 1024 * n})

    def test_published_file_has_no_overdue_actions_tile_and_editor_keeps_it(self):
        self.demo.plant_builtin_sections()
        with self.store.step("dashboard", USER) as st:      # the built-in At a glance section (a new project starts with the template one)
            for row in self.store.read("report_sections", "ABC"):
                if row["type"] == "glancetemplate":
                    st.cancel("report_sections", row["id"])
                    st.create("report_sections", {"project": "ABC", "type": "glance", "title": "At a glance", "sort_order": row["sort_order"]})
        self.demo.action(description="Chase the supplier file", owner="Pat Demo", due_date="2026-10-01")
        path = self.publish()
        for width, dark in ((1400, False), (1400, True), (900, False), (900, True)):
            with self.subTest(width=width, dark=dark):
                with chrome() as cdp:
                    e = self.show(cdp, width, dark)
                    e.until("!!document.querySelector('[data-fig=overdue]')", "the editor draws the Overdue actions tile")
                    self.assertIn("Overdue actions", e.js("document.querySelector('[data-fig=overdue]').textContent"))
                with chrome() as cdp:
                    p = self.draw(cdp, path, width, dark)
                    p.until("!!document.querySelector('[data-fig=health]')", "the file's tiles drew")
                    got = p.js("""(() => { const g = document.querySelector('[data-glance]'); const r = (e) => e.getBoundingClientRect();
                      return {text: g.textContent, over: g.querySelectorAll('[data-fig=overdue]').length, keys: [...g.querySelectorAll('[data-fig]')].map((e) => e.dataset.fig),
                              boxes: [...g.querySelectorAll('[data-fig]')].map((e) => [Math.round(r(e).width), Math.round(r(e).height)]), wide: document.documentElement.scrollWidth <= innerWidth}; })()""")
                    self.assertEqual(got["over"], 0, "no Overdue actions tile in the file")
                    self.assertNotIn("Overdue actions", got["text"])
                    self.assertIn("risks", got["keys"], "control: the other tiles are still drawn")
                    self.assertTrue(all(w > 40 and h > 20 for w, h in got["boxes"]), f"every remaining tile has a box: {got['boxes']}")
                    self.assertTrue(got["wide"], "no sideways scroll")

    def test_published_gantt_has_no_late_word_and_the_editor_keeps_it(self):
        self.plant_gantt()
        path = self.publish()
        probe = """(() => { const m = document.querySelector('main') || document.body;
          const lab = [...m.querySelectorAll('[aria-label], [title]')].map((e) => (e.getAttribute('aria-label') || '') + ' ' + (e.getAttribute('title') || '')).join(' | ');
          return {text: m.innerText, lab, bars: m.querySelectorAll('[aria-label*="Passed task"]').length}; })()"""
        pick = "(() => { const b = document.querySelector('[aria-label*=\"Passed task\"]'); if (b) b.dispatchEvent(new MouseEvent('click', {bubbles: true})); return !!b; })()"
        for width, dark in ((1400, False), (1400, True), (900, False), (900, True)):
            with self.subTest(width=width, dark=dark):
                with chrome() as cdp:
                    p = self.draw(cdp, path, width, dark)
                    p.until("!!document.querySelector('header.top-file [data-view=gantt]')", "the file has the Gantt tab")
                    p.js("document.querySelector('header.top-file [data-view=gantt]').click()")
                    p.until("document.body.innerText.includes('Passed task')", "the Gantt drew")
                    p.js(pick)
                    got = p.js(probe)
                    p.js("document.querySelector('header.top-file [data-view=dashboard]').click()")
                    p.until("document.body.innerText.includes('Passed task')", "the Gantt table section drew on the Dashboard")
                    table = p.js(probe)
                    self.assertNotRegex(table["text"], r"\bLate\b", "no Late word in the Gantt table's Status column")
                    self.assertGreater(got["bars"], 0, "control: the passed line's bar is drawn")
                    self.assertNotRegex(got["text"], r"\bLate\b", "no Late word on the published Gantt")
                    self.assertNotRegex(got["lab"], r"\bLate\b", "no Late word in a Gantt label")
                    self.assertNotRegex(got["text"], LATE_WORDS)
                with chrome() as cdp:
                    e = self.show(cdp, width, dark)
                    e.until("!!document.querySelector('header.top [data-view=gantt]')", "the editor has the Gantt tab")
                    e.js("document.querySelector('header.top [data-view=gantt]').click()")
                    e.until("document.body.innerText.includes('Passed task')", "the editor's Gantt drew")
                    e.js(pick)
                    self.assertRegex(e.js(probe)["lab"], r"\bLate\b", "the editor's Gantt still says Late")

    def test_client_word_copy_never_says_overdue(self):
        import copy
        from clark import docx_build
        from test_docx_graphics import NS, parts
        import xml.etree.ElementTree as ET
        self.plant_gantt()
        self.demo.action(description="Chase the supplier file", owner="Pat Demo", due_date="2026-10-01")
        self.demo.action(description="Urgent late step", owner="Pat Demo", due_date="2026-10-02", priority="Urgent")
        self.plant_late()
        built = publish.build(self.store, "ABC", now="2026-10-28")["published"]
        built = copy.deepcopy(built)
        if not any(x["type"] == "gantt" for x in built["sections"]):
            built["sections"] = list(built["sections"]) + [{"id": "gantt-1", "type": "gantt", "title": "Gantt", "beside": 0}]
        text = docx_build.build(built)
        doc = ET.fromstring(parts(text)["word/document.xml"])
        said = " | ".join("".join(t.text or "" for t in p.iter("{%s}t" % NS["w"])) for p in doc.iter("{%s}p" % NS["w"]))
        self.assertIn("Chase the supplier file", said, "control: the overdue action is in the copy")
        self.assertIn("Passed task", said, "control: the Gantt is in the copy")
        self.assertIn("Passed gate", said, "control: the passed milestone is in the copy")
        self.assertNotRegex(said, r"(?i)overdue", "the client's Word copy says no Overdue")

    def test_client_word_copy_has_no_late_word_and_no_late_colour(self):
        """Row 1543 AP4b (rule 1543-ap4b-0827): the Word copy of a published file says no overdue, no late, no N days late in its text or
        its picture alt text, and draws no late red: not in a run colour, not in a cell fill, not in a milestone or Gantt picture (the Gantt's red Today
        line is the one red mark, a line, not a late signal)."""
        import copy
        import re
        import xml.etree.ElementTree as ET
        from clark import docx_build, docx_graphics
        from test_docx_graphics import NS, parts, read_png
        self.plant_gantt()
        a_old = self.demo.action(description="Chase the supplier file", owner="Pat Demo", due_date="2026-10-01")
        a_urg = self.demo.action(description="Urgent passed step", owner="Pat Demo", due_date="2026-10-02", priority="Urgent")
        a_yes = self.demo.action(description="Due yesterday step", owner="Pat Demo", due_date="2026-10-27")
        a_five = self.demo.action(description="Due five days ago step", owner="Pat Demo", due_date="2026-10-23")
        self.plant_late()
        built = copy.deepcopy(publish.build(self.store, "ABC", now="2026-10-28")["published"])
        built["sections"] = [x for x in built["sections"] if x["type"] != "gantt"] + [
            {"id": "gantt-1", "type": "gantt", "title": "Gantt", "beside": 0},
            {"id": "wi-1", "type": "workitems", "title": "Work items", "beside": 0, "columns": ["id", "due", "status"], "items": [a_yes, a_five, a_old, a_urg]}]
        text = docx_build.build(built)
        files = parts(text)
        doc = ET.fromstring(files["word/document.xml"])
        said = " | ".join("".join(t.text or "" for t in p.iter("{%s}t" % NS["w"])) for p in doc.iter("{%s}p" % NS["w"]))
        alts = " | ".join(d.get("descr") or "" for d in doc.iter("{%s}docPr" % NS["wp"]))
        for word in ("Chase the supplier file", "Urgent passed step", "Due yesterday step", "Passed task", "Passed gate", "Slipped gate"):
            self.assertIn(word, said, f"control: {word} is in the copy")
        for row in (a_old, a_urg, a_yes, a_five):
            self.assertIn(row, said, f"control: the work item {row} is listed")
        self.assertNotRegex(said.replace("Due yesterday step", ""), r"(?i)yesterday", "a passed due date has no relative word, Yesterday included")
        due_cells = {"".join(t.text or "" for t in c.iter("{%s}t" % NS["w"])) for c in doc.iter("{%s}tc" % NS["w"])}
        self.assertIn("27-10-2026", due_cells, "the item due yesterday has its due cell as the plain date alone")
        self.assertNotIn("27-10-2026 Yesterday", said)
        self.assertIn("23-10-2026", said, "control: the date from five days ago is shown, as a date alone")
        self.assertIn("Open", said, "the accepted word for a passed action")
        self.assertTrue(alts, "control: the pictures have alt text")
        for where, got in (("text", said), ("alt text", alts)):
            self.assertNotRegex(got, r"(?i)overdue", f"no overdue in the {where}")
            self.assertNotRegex(got, r"(?i)\blate\b", f"no late in the {where}")
            self.assertNotRegex(got, r"(?i)days late", f"no N days late in the {where}")
        colours = {e.get("{%s}val" % NS["w"]) for e in doc.iter("{%s}color" % NS["w"])} | {e.get("{%s}fill" % NS["w"]) for e in doc.iter("{%s}shd" % NS["w"])}
        red = docx_build.palette(None)["tone-red-text"]
        self.assertTrue(colours - {None}, "control: the copy has colours")
        red_runs = {"".join(t.text or "" for t in r.iter("{%s}t" % NS["w"])) for r in doc.iter("{%s}r" % NS["w"])
                    if any(c.get("{%s}val" % NS["w"]) == red for c in r.iter("{%s}color" % NS["w"]))}
        self.assertTrue(red_runs <= {"1", "Red"}, f"red text is only the High risks tile's count and the risk's Red rating (not lateness); no date, state or word of a late item: {red_runs}")
        self.assertTrue(red_runs, "control: the red the copy does use is found by this check")
        status_red = docx_graphics.tokens(docx_build.palette(None))["status-red"]
        pngs = [n for n in files if n.startswith("word/media/") and n.endswith(".png")]
        self.assertGreaterEqual(len(pngs), 2, "control: the plan and the Gantt pictures are in the copy")
        for n in pngs:
            w, h, palette, rows = read_png(files[n])
            if status_red in palette:
                at = palette.index(status_red)
                cols = {x for row in rows for x, v in enumerate(row) if v == at}
                self.assertLessEqual(len(cols), 2, f"{n}: red is only the Gantt's Today line, two pixels wide")


# Row 1543 AP4 (slice 6, review ruling 'no late days on any client surface'): the published Work items page has no Overdue group and no Overdue
# Due-filter option; an open item whose date has passed is in the group "Earlier" and is still drawn. The editor keeps both.
class Overdue1543:
    def plant_overdue_item(self):
        self.demo.action(description="Chase the supplier file", owner="Pat Demo", due_date="2026-10-01")

    def published_work(self, cdp, path, width, dark):
        p = self.draw(cdp, path, width, dark)
        p.until("!!document.querySelector('header.top-file .tab')", "the published bar drew")
        p.js("document.querySelector('header.top-file [data-view=work]').click()")
        p.until("!!document.querySelector('#work-list') && !!document.querySelector('#group-by')", "the published Work items drew")
        return p

    def test_published_work_items_have_no_overdue_group_or_filter_option(self):
        self.plant_overdue_item()
        path = self.publish()
        for width, dark in ((1400, False), (1400, True), (900, False), (900, True)):
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                p = self.published_work(cdp, path, width, dark)
                p.js("document.querySelector('[data-show=all]') && document.querySelector('[data-show=all]').click()")
                p.js("document.querySelector('#group-by').click()")
                p.until("!!document.querySelector('[role=menuitem][data-kind=due]')", "the Group by menu opened")
                p.js("document.querySelector('[role=menuitem][data-kind=due]').click()")
                p.until("[...document.querySelectorAll('tr.grp th')].some((t) => /Earlier/.test(t.textContent))", "the Due groups drew, the passed date in Earlier")
                heads = p.js("[...document.querySelectorAll('tr.grp th')].map((t) => t.textContent)")
                self.assertTrue(any(h.startswith("Earlier") for h in heads), f"the open item whose date passed is in Earlier: {heads}")
                self.assertGreater(p.js("document.querySelectorAll('#work tr[data-id]').length"), 0, "control: the rows are drawn")
                self.assertTrue(p.js("document.querySelector('#work').textContent.includes('Chase the supplier file')"), "control: the item is still drawn")
                p.js("document.querySelector('[data-fb=due]').click()")
                p.until("!!document.querySelector('#fbox-due input')", "the Due filter opened")
                menu = p.js("document.querySelector('#fbox-due').textContent")
                self.assertIn("Due in 7 days", menu, "control: the Due filter offers its options")
                self.assertEqual(p.js("document.querySelectorAll('#fbox-due input[value=overdue]').length"), 0, "no Overdue option")
                self.assertNotRegex(menu, r"(?i)overdue")
                self.assertNotRegex(p.js("document.querySelector('#work').textContent"), r"(?i)overdue", "no Overdue text anywhere on the Work items page")

    def test_published_remembered_overdue_filter_is_no_filter(self):
        self.plant_overdue_item()
        path = self.publish()
        keep = "localStorage.setItem('clark.work.ABC', JSON.stringify({v: 1, type: 'all', mode: 'all', filters: {due: ['overdue']}, not: {}, group: 'workstream'}))"
        for width, dark in ((1400, False), (900, True)):
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                p = self.draw(cdp, path, width, dark)
                p.until("!!document.querySelector('header.top-file .tab')", "the published bar drew")
                p.js(keep)
                p.js("location.hash = '#work'")
                reload_to_new_page(p.js, "!!document.querySelector('#work-list') && document.querySelectorAll('#work tr[data-id]').length > 0", "the Work items drew with the remembered choice")
                self.assertEqual(p.js("document.querySelectorAll('[data-chip=due]').length"), 0, "no Due chip")
                self.assertTrue(p.js("document.querySelector('#work').textContent.includes('Chase the supplier file')"), "the item is drawn: the choice is no filter")
                self.assertNotRegex(p.js("document.querySelector('#work').textContent"), r"(?i)overdue")

    def test_editor_work_items_keep_the_overdue_group(self):
        self.plant_overdue_item()
        for width, dark in ((1400, False), (1400, True), (900, False), (900, True)):
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                p = self.show(cdp, width, dark, hash_="#work&p=ABC", settings=True)      # settings=True: the page is not waited for as a Dashboard
                p.until("document.documentElement.dataset.ready === '1'", "the editor opened")
                p.js("localStorage.setItem('clark.work.v1', JSON.stringify({ABC: {view: 'table', group: 'due', lane: null, collapsed: []}}))")
                reload_to_new_page(p.js, "document.documentElement.dataset.ready === '1' && !!document.querySelector('tbody[data-group]')", "the editor's Work items drew")
                if dark:
                    p.js("document.documentElement.dataset.theme = 'dark'")
                p.until("[...document.querySelectorAll('tbody[data-group]')].some((t) => t.dataset.group === 'overdue')", "the Overdue group drew")
                # the editor's Due filter (filters.js options) still lists Overdue: pinned in test_work_filters (labels Overdue, Due in 7 days, No date, Later), run with this file
                self.assertIn("Overdue", p.js("[...document.querySelectorAll('thead[data-group]')].map((t) => t.textContent).join('|')"), "the Overdue group is drawn with its heading")


# Row 1543 AP4d (PM ruling rom-rul-1543-ap4d-0920): on a published file the Milestones timeline keeps the slip (the ghost ring, the dashed line,
# "+N days", the Slipped diamond) and loses its red; the editor draws them red as before.
TIMELINE_PROBE = """(() => {
  const root = document.querySelector('.mv') || document.querySelector('[data-ms]').parentElement;
  const probe = document.createElement('i'); document.body.appendChild(probe);
  const tok = (n) => { probe.style.color = `var(${n})`; return getComputedStyle(probe).color; };
  const red = [tok('--status-red'), tok('--status-red-text')], amber = [tok('--status-amber'), tok('--status-amber-text')];
  const hsl = (c) => { const m = c.match(/[\\d.]+/g); if (!m || m.length < 3 || (m.length > 3 && +m[3] === 0)) return null; const [r, g, b] = m.slice(0, 3).map((x) => x / 255);
    const hi = Math.max(r, g, b), lo = Math.min(r, g, b), d = hi - lo, l = (hi + lo) / 2; if (!d) return {h: 0, s: 0};
    const s = d / (1 - Math.abs(2 * l - 1)); let h = hi === r ? ((g - b) / d) % 6 : hi === g ? (b - r) / d + 2 : (r - g) / d + 4; h = (h * 60 + 360) % 360; return {h, s}; };
  const bad = (c) => { if (red.includes(c) || amber.includes(c)) return 'token'; const x = hsl(c); if (!x || x.s <= 0.25) return ''; return (x.h >= 345 || x.h <= 15) ? 'red hue' : (x.h >= 30 && x.h <= 50) ? 'amber hue' : ''; };
  const sets = {
    slip: [[...root.querySelectorAll('[data-slip]')], ['color']],
    conn: [[...root.querySelectorAll('.mv-conn')], ['borderTopColor']],
    ghost: [[...root.querySelectorAll('.mv-ghost')], ['borderTopColor', 'borderLeftColor']],
    diamond: [[...root.querySelectorAll('.mv-mk svg path')].filter((e) => /M10 2\\.5l7\\.5/.test(e.getAttribute('d') || '')), ['stroke']],
    legend: [[...document.querySelectorAll('.mlg-ghost')], ['borderTopColor']],
    cal: [[...document.querySelectorAll('.cal-ms.ghost')], ['borderTopColor', 'color']],
  };
  const out = {hits: [], n: {}, red: 0, slips: [...root.querySelectorAll('[data-slip]')].map((e) => e.textContent), widths: [...root.querySelectorAll('.mv-ghost, .mv-conn')].map((e) => e.getBoundingClientRect().width),
               slipText: sets.slip[0].length ? getComputedStyle(sets.slip[0][0]).color : null, redText: red[1], redStroke: red[0], diamondStroke: sets.diamond[0].length ? getComputedStyle(sets.diamond[0][0]).stroke : null};
  for (const [k, [els, props]] of Object.entries(sets)) { out.n[k] = els.length;
    for (const e of els) { const c = getComputedStyle(e); for (const p of props) { const v = c[p], w = bad(v); if (w) out.hits.push(k + ' ' + p + ' ' + v + ' ' + w); if (red.includes(v)) out.red++; } } }
  return out;
})()"""


class Timeline1543:
    def timeline(self, cdp, path, width, dark, edit=False):
        if edit:
            p = self.show(cdp, width, dark, hash_="#milestones&p=ABC", settings=True)
            p.until("document.querySelectorAll('.mv-mk').length > 0", "the editor's timeline drew")
        else:
            p = self.draw(cdp, path, width, dark)
            p.until("!!document.querySelector('header.top-file .tab')", "the published bar drew")
            p.js("document.querySelector('header.top-file [data-view=milestones]').click()")
            p.until("document.querySelectorAll('.mv-mk').length > 0", "the published timeline drew")
        p.until("document.getAnimations().every((a) => a.playState === 'finished')", "settled")
        return p

    def test_published_timeline_keeps_the_slip_and_drops_the_red(self):
        """PM rulings rom-rul-1543-ap4d-0920 and the scope ruling: no red and no amber computed colour on the slip text, dashed line, ghost ring,
        Slipped diamond (timeline), the legend's ghost ring and the calendar's ghost chip in a published file; each is still drawn; the editor stays red."""
        self.plant_late()
        path = self.publish()
        for width, dark in ((1400, False), (1400, True), (900, False), (900, True)):
            with self.subTest(width=width, dark=dark):
                with chrome() as cdp:
                    p = self.timeline(cdp, path, width, dark)
                    got = p.js(TIMELINE_PROBE)
                    p.js("[...document.querySelectorAll('button')].find((b) => /^\\s*Calendar\\s*$/.test(b.textContent)).click()")
                    p.until("document.querySelectorAll('.cal-ms.ghost').length > 0", "the calendar drew its ghost chip")
                    cal = p.js(TIMELINE_PROBE)
                    p.js("document.querySelector('header.top-file [data-view=dashboard]').click()")      # the Dashboard's own timeline section (the other label layout)
                    p.until("document.querySelectorAll('.mv-lab2').length > 0", "the Dashboard's timeline section drew")
                    dash = p.js(TIMELINE_PROBE)
                self.assertGreaterEqual(sum(got["n"][k] for k in ("slip", "conn", "ghost", "diamond")), 4, f"control: the elements were found {got['n']}")
                for k in ("slip", "conn", "ghost", "diamond"):
                    self.assertGreaterEqual(got["n"][k], 1, f"{k} is still drawn")
                self.assertEqual(got["n"]["slip"], got["n"]["ghost"], "one +N days for each ghost")
                self.assertEqual(got["n"]["conn"], got["n"]["ghost"], "one dashed line for each ghost")
                self.assertTrue(all(t.startswith("+") for t in got["slips"]), f"+N days is still said: {got['slips']}")
                self.assertTrue(all(w > 0 for w in got["widths"]), "the ghost and the line have a size")
                self.assertEqual(got["hits"], [], "no red or amber computed colour in the published timeline")
                self.assertGreaterEqual(dash["n"]["slip"], 1, "control: the Dashboard's timeline shows +N days")
                self.assertEqual(dash["hits"], [], "no red or amber on the Dashboard's timeline slip")
                self.assertGreaterEqual(cal["n"]["cal"], 1, "control: the calendar's ghost chip is drawn")
                self.assertEqual(cal["hits"], [], "no red or amber on the calendar's ghost chip")
                if got["n"]["legend"]:
                    self.assertEqual([h for h in got["hits"] if h.startswith("legend")], [], "no red on the legend's ghost ring")
                with chrome() as cdp:
                    e = self.timeline(cdp, None, width, dark, edit=True)
                    ed = e.js(TIMELINE_PROBE)
                    self.assertGreaterEqual(ed["n"]["ghost"], 1, "control: the editor draws the ghost")
                    self.assertGreaterEqual(ed["red"], 1, "the editor's timeline is still red")
                    self.assertEqual(ed["slipText"], ed["redText"], "the editor's +N days is the red text colour")
                    self.assertEqual(ed["diamondStroke"], ed["redStroke"], "the editor's Slipped diamond is red")

    def test_published_timeline_pictures(self):
        import base64
        import os
        out = os.environ.get("CLARK_SHOT_DIR")
        if not out:
            self.skipTest("CLARK_SHOT_DIR not set: the by-eye pictures are made on request")
        self.plant_late()
        path = self.publish()
        for width, dark in ((1400, False), (1400, True), (900, False), (900, True)):
            with chrome() as cdp:
                p = self.timeline(cdp, path, width, dark)
                p.js("document.querySelector('.mv') && document.querySelector('.mv').scrollIntoView()")
                data = cdp.call("Page.captureScreenshot", {"format": "png"}, p.sid)["data"]
                os.makedirs(out, exist_ok=True)
                with open(os.path.join(out, f"timeline-{width}{'-dark' if dark else ''}.png"), "wb") as f:
                    f.write(base64.b64decode(data))


for _cls in (Late1543, More1543, Overdue1543, Timeline1543):
    for _name in dir(_cls):
        if _name.startswith(("test", "plant_", "pages", "peek_", "published_work", "timeline")):
            setattr(Header1543, _name, getattr(_cls, _name))


NAME_PROBE = """(() => {
  const bar = document.querySelector('header.top'), n = bar.querySelector('#project-name'), b = bar.getBoundingClientRect(), r = n.getBoundingClientRect(), cs = getComputedStyle(n);
  const id = n.closest('.top-id, .hdr-id').getBoundingClientRect();
  return {name: n.textContent, barW: Math.round(b.width), barH: Math.round(b.height), nameW: Math.round(r.width), idW: Math.round(id.width), nameH: Math.round(r.height), lh: parseFloat(cs.lineHeight) || parseFloat(cs.fontSize) * 1.2,
    ws: cs.whiteSpace, tov: cs.textOverflow, ov: cs.overflow, cut: n.scrollWidth > n.clientWidth, title: n.getAttribute('title') || (n.firstElementChild && n.firstElementChild.getAttribute('title')) || ''};
})()"""
STRIP_PROBE = """(() => {
  const bar = document.querySelector('header.top'), tabs = bar.querySelector('.tabs'), b = bar.getBoundingClientRect(), t = tabs.getBoundingClientRect(), logo = bar.querySelector('.logo').getBoundingClientRect();
  const q = (n) => Math.round(n * 10) / 10, first = tabs.querySelector('[role=tab]').getBoundingClientRect(), cs = getComputedStyle(tabs);
  return {barH: q(b.height), tabsTop: q(t.top - b.top), tabsH: q(t.height), tabsLeft: q(t.left - b.left), tabsW: q(t.width), firstLeft: q(first.left - b.left), border: cs.borderTopWidth, logoTop: q(logo.top - b.top), logoLeft: q(logo.left - b.left), idLeft: q(bar.querySelector('.top-id, .hdr-id').getBoundingClientRect().left - b.left),
    search: bar.querySelectorAll('[aria-label="Go to or do"]').length, wide: document.documentElement.scrollWidth <= innerWidth};
})()"""


ROW_PROBE = """(() => {
  const bar = document.querySelector('header.top'), tabs = bar.querySelector('.tabs'), b = bar.getBoundingClientRect(), t = tabs.getBoundingClientRect(), cs = getComputedStyle(bar);
  const id = bar.querySelector('.top-id, .hdr-id').getBoundingClientRect(), q = (n) => Math.round(n * 10) / 10;
  return {barH: q(b.height), display: cs.display, wrap: cs.flexWrap, tabsTop: q(t.top - b.top), tabsH: q(t.height), border: getComputedStyle(tabs).borderTopWidth,
    inline: t.top >= b.top && t.bottom <= b.bottom && t.left >= id.right - 0.5 && id.top < t.bottom && id.bottom > t.top,
    search: bar.querySelectorAll('[aria-label="Go to or do"]').length, wide: document.documentElement.scrollWidth <= innerWidth};
})()"""


class Ap7:      # mixed into Header1543 below
    LONG_NAME = "A very long programme name that goes on and on and on for the whole line and beyond"

    def test_published_header_project_name_one_line(self):
        self.store.con.execute("UPDATE projects SET name = ? WHERE code = 'ABC'", (self.LONG_NAME,))
        self.store.con.commit()
        for width, dark in ((1400, False), (1400, True), (900, False), (900, True)):
            with self.subTest(width=width, dark=dark):
                got = self.probe_file(NAME_PROBE, width, dark)
                self.assertEqual(got["name"], self.LONG_NAME, "control: the long name is the one drawn")
                self.assertLess(got["nameH"], got["lh"] * 1.5, f"the name is one line ({got['nameH']} px high, a line is {got['lh']})")
                self.assertEqual((got["ws"], got["tov"], got["ov"]), ("nowrap", "ellipsis", "hidden"), "cut with an ellipsis")
                self.assertTrue(got["cut"], "the long name does not fit, so it is cut")
                self.assertLessEqual(got["idW"], got["barW"] * 0.5, "the name box stops at the editor's cap of half the bar (row 1305)")
                self.assertEqual(got["title"], self.LONG_NAME, "its tooltip still names it")

    def test_published_header_name_cap_is_the_editors(self):
        """A GUARD, not a proof of a change: the name box cap of the published bar is the editor header's, read from the computed style (the cap does not bind at 1400 or 900, so the width alone cannot show it). Both bars take the one rule `.hdr-id, .top-id { max-width: 50% }` (rules.css, row 1305), so this passes with the Row 1543 AP7 CSS reverted; the 900 px layout is pinned by test_published_header_900px_follows_editor."""
        probe = "(() => { const n = document.querySelector('header.top #project-name').closest('.top-id, .hdr-id'); const cs = getComputedStyle(n); return {cls: n.className, max: cs.maxWidth}; })()"
        classic(self)      # the editor in the Classic look, the one the file is drawn in
        for width, dark in ((1400, False), (900, False), (1400, True), (900, True)):
            with self.subTest(width=width, dark=dark):
                with chrome() as cdp:
                    p = self.show(cdp, width, dark)
                    p.until("!!document.querySelector('header.top .tab')", "the editor's bar drew")
                    e = p.js(probe)
                f = self.probe_file(probe, width, dark)
                self.assertIn("hdr-id", e["cls"], "control: the editor's name box")
                self.assertIn("top-id", f["cls"], "control: the file's name box")
                self.assertEqual(f["max"], e["max"], f"name cap: the file {f['max']}, the editor {e['max']}")
                self.assertEqual(e["max"], "50%", "the editor's code value (rules.css row 1305: .hdr-id, .top-id max-width 50%)")

    def test_published_header_900px_follows_editor(self):
        """AP7 (review ruling): at 900 px the published header follows the CLASSIC editor's bar (rules.css 900 px block: a flex row 103 px high, the pages inline in the same row, no strip and no line above the pages). The file is always Classic, so the editor here is Classic too. 1400 px: the file's bar is the editor's (85 px, flex, pages inline)."""
        classic(self)
        for width, high in ((900, 103), (1400, 85)):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark):
                    with chrome() as cdp:
                        p = self.show(cdp, width, dark)
                        p.until("!!document.querySelector('header.top .tab')", "the editor's bar drew")
                        e = p.js(ROW_PROBE)
                    f = self.probe_file(ROW_PROBE, width, dark)
                    for name, got in (("editor", e), ("file", f)):
                        self.assertAlmostEqual(got["barH"], high, delta=1, msg=f"the {name}'s bar is {got['barH']} px high, not {high}")
                        self.assertEqual(got["display"], "flex", f"the {name}'s bar is a flex row")
                        self.assertEqual(got["wrap"], "nowrap", f"the {name}'s bar does not wrap")
                        self.assertTrue(got["inline"], f"the {name}'s pages are inside the bar's box, in its one row: {got}")
                        self.assertEqual(got["border"], "0px", f"the {name}'s pages have no line above them (no strip)")
                    self.assertAlmostEqual(f["barH"], e["barH"], delta=1)
                    self.assertAlmostEqual(f["tabsTop"], e["tabsTop"], delta=1.5, msg=f"the pages' top: the file {f['tabsTop']}, the editor {e['tabsTop']}")
                    self.assertAlmostEqual(f["tabsH"], e["tabsH"], delta=1.5, msg=f"the pages' height: the file {f['tabsH']}, the editor {e['tabsH']}")
                    self.assertTrue(f["wide"], "no sideways scroll")
                    if width == 900:
                        self.assertEqual(f["search"], 0, "search is not drawn in the bar")
                        self.probe_menu(dark)

    def test_published_header_900px_every_page_label_keeps_4_5_to_1_over_the_picture(self):
        """AP7: at 900 px the pages sit in the bar's one row, over the cover picture; EVERY page label (selected or not) keeps 4.5 to 1 against the pixels drawn behind it, with a swirl and a bright picture in place, light and dark. The picture's fade at 900 px and narrower is what keeps it."""
        labels = """(() => [...document.querySelectorAll('header.top .tab')].map((t) => { const n = t.querySelector('.tab-label') || t, w = document.createTreeWalker(t, NodeFilter.SHOW_TEXT), out = [];
          for (let x; (x = w.nextNode());) { if (!x.textContent.trim()) continue; const rg = document.createRange(); rg.selectNodeContents(x);
            for (const r of rg.getClientRects()) if (r.width > 2) out.push({x: r.left, y: r.top, w: r.width, h: r.height}); }
          return {t: t.textContent.trim(), fg: getComputedStyle(t).color, rects: out}; }))()"""
        for dark in (False, True):
            for name, data in (("swirl", pics.swirl()), ("bright", pics.solid((60, 200, 230)))):
                with self.subTest(dark=dark, picture=name):
                    path = self.publish()
                    with chrome() as cdp:
                        p = self.draw(cdp, path, 900, dark)
                        p.until("!!document.querySelector('header.top-file .tab')", "the published bar drew")
                        p.js("document.documentElement.style.setProperty('--image-cover', %s)" % json.dumps("url(data:image/png;base64," + base64.b64encode(data).decode() + ")"))
                        p.until("document.getAnimations().every(a => a.playState === 'finished')", "settled")
                        items = p.js(labels)
                        p.js(HIDE)
                        shot = lambda: pics.decode(base64.b64decode(cdp.call("Page.captureScreenshot", {"format": "png"}, p.sid)["data"]))
                        w, h, rows = shot()      # as drawn: the picture with its fade
                        # positive control: the picture really reaches the labels' boxes. With the fade taken off (in the test only) the picture is drawn behind the labels; with no picture the same pixels are the plain bar. They must differ, so a blank background cannot pass.
                        p.js("document.querySelector('header.top').style.setProperty('--image-fade', 'linear-gradient(#000, #000)')")
                        _, _, full = shot()
                        p.js("document.querySelector('header.top').style.setProperty('--image-cover', 'none')")
                        _, _, plain = shot()
                    self.assertGreaterEqual(len(items), 3, "control: the page labels were read")
                    for it in items:
                        self.assertTrue(it["rects"], f"control: {it['t']!r} has a drawn label")
                        r, g, b, a = colour(it["fg"])
                        low, moved = 99.0, 0
                        for q in it["rects"]:
                            for y in range(int(q["y"]), min(h, int(q["y"] + q["h"]) + 1), 2):
                                for x in range(int(q["x"]), min(w, int(q["x"] + q["w"]) + 1), 2):
                                    bg = rows[y][x]
                                    moved += max(abs(i - j) for i, j in zip(full[y][x][:3], plain[y][x][:3])) > 8
                                    low = min(low, ratio([a * c + (1 - a) * k for c, k in zip((r, g, b), bg)], bg))
                        self.assertGreater(moved, 10, f"control: the picture would sit behind {it['t']!r} (without the fade), so the 4.5 to 1 is measured over a picture, not a blank bar")
                        self.assertGreaterEqual(low, 4.5, f"{it['t']!r} is {low:.2f}:1 over the picture")

    def probe_menu(self, dark):
        path = self.publish()
        with chrome() as cdp:
            p = self.draw(cdp, path, 900, dark)
            p.until("!!document.querySelector('header.top-file .tab')", "the published bar drew")
            p.js("document.querySelector('.cm-badge').click()")
            p.until("!!document.querySelector('[role=menu]') && document.querySelector('[role=menu]').textContent.trim().length > 0", "the profile menu opened")
            menu = p.js("document.querySelector('[role=menu]').textContent")
        for page in ("Dashboard", "Work items", "Milestones"):
            self.assertNotIn(page, menu, "the pages do not move into the profile menu")


for _cls in (Ap7,):
    for _name in dir(_cls):
        if _name.startswith(("test", "plant_", "pages", "probe_", "LONG")):
            setattr(Header1543, _name, getattr(_cls, _name))
for _name in dir(glance.Published):      # the base class's own tests are run in its own file
    if _name.startswith("test") and _name not in Header1543.__dict__:
        setattr(Header1543, _name, None)
