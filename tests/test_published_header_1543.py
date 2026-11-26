"""Row 1543 PR 1: the published header's pages group sits where the editor's does (same right edge, same line), and the room the
editor's right-hand buttons use is reserved, so the pages do not move between the two. In a real browser, light and dark, 1400 px,
and the 1200 and 1100 px edge checks (the 900 px bar is a later part of the row). Fictional data.

Run: python3 dev/run_tests.py test_published_header_1543        (needs Chrome; run only while the machine's load is under 70)
"""
import json

import test_glance_page as glance
from _demo import USER
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome

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
        for width, dark in ((1400, False), (1400, True), (900, False), (900, True)):
            with self.subTest(width=width, dark=dark):
                got = self.probe_file(pub_js, width, dark)
                self.assertEqual(got["count"], 1)
                self.assertEqual((got["w"], got["h"]), (38, 28), "38 px wide by 28 px high")
                self.assertEqual((got["border"], got["radius"]), (ed["border"], ed["radius"]), "the editor's border and corners")
                self.assertEqual((got["name"], got["tip"]), ("Go to or do", "Go to or do (Ctrl or Cmd + K)"), "the editor's name and tooltip")
                self.assertTrue(got["beforeSwitcher"] and got["inBar"] and got["wide"], f"the button is in the bar, left of the switcher, with no sideways scroll: {got}")
                if width == 900:
                    self.assertLessEqual(got["gap"], 24, "at 900 px the button sits beside the switcher")
                    self.assertLessEqual(got["endRight"], 40, "and both are at the right of the bar")
                if width == 1400:
                    self.assertAlmostEqual(got["fromTabs"], ed["fromTabs"], delta=0.6, msg="it sits where the editor's search button does, 22 px after the pages")

    def test_published_search_box_placeholder_and_open(self):
        path = self.plant_search()
        for width, dark in ((1400, False), (1400, True), (900, False), (900, True)):
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                p = self.draw(cdp, path, width, dark)
                p.until("!!document.getElementById('pub-search-btn')", "the button drew")
                self.assertEqual(p.js("!!document.querySelector('dialog#report-search')"), False, "no box until the button is pressed")
                self.open_box(p)
                got = p.js("""(() => { const d = document.getElementById('report-search'), r = d.getBoundingClientRect(), i = document.getElementById('report-search-q');
                  return {ph: i.placeholder, inView: r.left >= 0 && r.right <= innerWidth && r.top >= 0 && r.bottom <= innerHeight, wide: document.documentElement.scrollWidth <= innerWidth, rows: document.querySelectorAll('.rs-row').length,
                          none: !document.querySelector('.rs-none').hidden, expanded: document.getElementById('pub-search-btn').getAttribute('aria-expanded')}; })()""")
                self.assertEqual(got["ph"], "Search this report")
                self.assertTrue(got["inView"] and got["wide"], f"the box fits the window: {got}")
                self.assertEqual((got["rows"], got["none"], got["expanded"]), (0, False, "true"), "an empty box lists nothing and says nothing")
                self.assertEqual(self.search(p, "zzzz-nothing"), [])
                self.assertEqual(p.js("document.querySelector('.rs-none').hidden"), False, "nothing found says so")
                self.assertEqual(p.js("document.querySelector('.rs-none').textContent"), "Nothing matches.")
                p.js("document.querySelector('dialog#report-search').dispatchEvent(new Event('cancel', {cancelable: true}))")
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


for _name in dir(glance.Published):      # the base class's own tests are run in its own file
    if _name.startswith("test") and _name not in Header1543.__dict__:
        setattr(Header1543, _name, None)
