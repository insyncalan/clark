"""Row 1543 PR 1: the published header's pages group sits where the editor's does (same right edge, same line), and the room the
editor's right-hand buttons use is reserved, so the pages do not move between the two. In a real browser, light and dark, 1400 px,
and the 1200 and 1100 px edge checks (the 900 px bar is a later part of the row). Fictional data.

Run: python3 dev/run_tests.py test_published_header_1543        (needs Chrome; run only while the machine's load is under 70)
"""
import json
from unittest import mock

import test_glance_page as glance
from clark import publish
from clark import store as store_module
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
          return {n: h.querySelectorAll('.tb-ask, .tb-act, .hdr-end, .bell, [aria-label="Ask clark"], [aria-label="Client visible"]').length,
                  btns: [...h.querySelectorAll('button')].map((b) => b.className).sort()}; })()"""
        for width, dark in ((1400, False), (1400, True), (900, False), (900, True)):
            with self.subTest(width=width, dark=dark):
                got = self.probe_file(js, width, dark)
                self.assertEqual(got["n"], 0, f"no editor control in the published header: {got['btns']}")


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


for _cls in (Late1543, More1543):
    for _name in dir(_cls):
        if _name.startswith(("test", "plant_", "pages", "peek_")):
            setattr(Header1543, _name, getattr(_cls, _name))
for _name in dir(glance.Published):      # the base class's own tests are run in its own file
    if _name.startswith("test") and _name not in Header1543.__dict__:
        setattr(Header1543, _name, None)
