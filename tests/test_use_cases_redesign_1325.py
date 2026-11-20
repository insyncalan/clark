"""Row 1325 KILLERS: killers written first, red on main: the Use cases page redesigned to the approved mock-up (mockups/1325-use-cases-template/approved.html on the planning board).

Run: python3 dev/run_tests.py test_use_cases_redesign_1325
Chrome required (fails, never skips). 1400 and 900 px, light mode, under Classic (the prototype-2.0 theme layer) only. Owner ruling 19-11: Classic only, layered; Cards is a
production setting and every Cards look change needs the owner's word, so Cards must look as it does on main (CardsAsOnMain below pins it). Dark mode is not asserted (the mock-up did not draw it; open question on the row).
Owner words (18-11-2026 18:34 Dubai): "1325 use cases fully approved, lock Status, Commitment replaces grey line".
Every check is a computed style, a measured position or the page's own text in Chrome, not a source grep.
Contract the build must meet (the names are the Work items names, so the build can share the Work items CSS):
  R1  `#usecases table.items`, ONE `thead tr.colh`, headers Use case / Where it stands / Status / Owner / Next steps / Milestone and a last cell
      holding the Columns button; rows `tbody tr[data-uc]` with td.c-item (.t title, .meta2 grey line "UC 1.1 · Committed"), td.c-where,
      td.c-status (.pill), td.c-owner (.av and .on), td.c-steps (.stp text, .prg bar with an inner i), td.c-ms (Milestone), td.c-eye (.weye);
      head, tabs with counts, `.fline` filter box, `.fline-tail` with the List/Board pair and the Group by / Sort by labelled buttons (icon buttons until Row 1316 follow-up).
  R2  a use case hidden from the client: `tr.off`, all row text #667391, pill unfilled with a ring, grey avatar, crossed-out eye.
  R3  `button[aria-label=Columns]` in the last th; its menu `.cols-menu` of role=menuitemcheckbox rows; Use case and Status locked.
  R4  grouped by Status: one heading button per group, one column header, shut group hides its rows (the heading look is the grouped-heading row's).
"""
import hashlib
import json
import re
import unittest

from clark import page, theme
from _demo import USER
from _new_page import reload_to_new_page
from _real_server import real_server
import _testpage as testpage
from test_report_editor import EMPTY_BRANDING, Base, Pg, tearDownModule  # noqa: F401
from test_server import chrome
from test_use_cases_list import plant

GREY = "rgb(102, 115, 145)"        # #667391, 4.74:1 on white
NAMES = ["Use case", "Where it stands", "Status", "Owner", "Next steps", "Milestone"]
HIDE_AT_900 = ["Milestone"]
ROWS = '#usecases table.items tbody tr[data-uc]'

STRUCT = """(() => {
  const q = (s, r) => (r || document).querySelector(s), qa = (s, r) => [...(r || document).querySelectorAll(s)];
  const vis = (e) => { if (!e) return false; const r = e.getBoundingClientRect(), s = getComputedStyle(e); return r.width > 1 && r.height > 1 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const o = {};
  o.table = !!q('#usecases table.items');
  o.oldList = qa('#usecases .ucl-list, #usecases .ucl-cols, #usecases .ucl-row').length;
  o.heads = qa('#usecases table.items tr.colh').length;
  const ths = qa('#usecases table.items thead tr.colh th');
  o.th = ths.map((t) => [t.textContent.trim(), vis(t), Math.round(t.getBoundingClientRect().left), Math.round(t.getBoundingClientRect().width), t.className]);
  o.cols = !!q('#usecases table.items thead tr.colh th:last-child button[aria-label="Columns"]');
  o.h1 = (q('#usecases h1') || {}).textContent;
  o.tabs = qa('#usecases .vtab').map((b) => [b.textContent.replace(/\\d+$/, '').trim(), (q('em.num', b) || {}).textContent]);
  o.fline = !!q('#usecases .fline input') && !!q('#usecases .fline .fcount');
  o.lsw = qa('#usecases .fline-tail .seg.lsw button').map((b) => b.getAttribute('aria-label'));
  o.icons = qa('#usecases .fline-tail button[aria-label^="Group by"], #usecases .fline-tail button[aria-label^="Sort by"]').length;
  o.rows = qa('#usecases table.items tbody tr[data-uc]').map((r) => {
    const c = (k) => q('td.c-' + k, r);
    const col = (k) => { const e = c(k); return e ? [Math.round(e.getBoundingClientRect().left), vis(e)] : null; };
    const cs = getComputedStyle(c('item') || r);
    const prg = q('.prg', r), inner = prg && q('i', prg);
    const av = q('.av', r), on = q('.on', r);
    return { ref: (q('.meta2', r) || {}).textContent, title: (q('.t', r) || {}).textContent, where: (c('where') || {}).textContent,
      pill: (q('td.c-status .pill', r) || {}).textContent, av: av && av.textContent.trim(), avBox: av && [av.getBoundingClientRect().width, getComputedStyle(av).borderRadius],
      onVis: vis(on), onText: on && on.textContent.trim(), stp: (q('.stp', r) || {}).textContent,
      prgH: prg && prg.getBoundingClientRect().height, prgFill: prg && inner ? inner.getBoundingClientRect().width / prg.getBoundingClientRect().width : null,
      ms: (c('ms') || {}).textContent, msVis: vis(c('ms')), eye: !!q('td.c-eye .weye', r),
      left: ['item', 'where', 'status', 'owner', 'steps', 'ms'].map((k) => col(k)),
      rule: [cs.borderBottomWidth, cs.borderBottomStyle, cs.borderTopWidth, cs.borderLeftWidth], off: r.classList.contains('off'), uc: r.dataset.uc };
  });
  o.noScroll = document.documentElement.scrollWidth <= innerWidth;
  return o; })()"""

LOOK = """((root) => {
  const q = (s) => document.querySelector(s);
  const pick = (e, ks) => e ? ks.map((k) => getComputedStyle(e)[k]) : null;
  const T = ['fontSize', 'fontWeight', 'color', 'textTransform', 'letterSpacing', 'paddingTop', 'paddingBottom', 'paddingLeft', 'borderBottomWidth', 'borderBottomStyle', 'borderBottomColor', 'backgroundColor'];
  const av = q(root + ' tbody tr:not(.off) .av');
  const sec = q(root), b = getComputedStyle(sec, '::before');
  return { th: pick(q(root + ' thead tr.colh th.c-owner'), T), td: pick(q(root + ' tbody td.c-owner'), T),
    av: av ? [av.getBoundingClientRect().width, av.getBoundingClientRect().height, getComputedStyle(av).borderRadius, getComputedStyle(av).fontSize] : null,
    vtab: pick(q(root + ' .vtab'), ['fontSize', 'fontWeight', 'color', 'paddingTop', 'paddingLeft', 'borderBottomWidth', 'borderBottomColor']),
    fline: pick(q(root + ' .fline'), ['borderBottomWidth', 'borderBottomStyle', 'borderBottomColor', 'borderTopWidth', 'borderRadius', 'height']),
    gutter: [...pick(sec, ['borderLeftWidth', 'boxShadow', 'paddingLeft']), b.content, b.width, b.backgroundColor] }; })"""

OFFLOOK = """(() => {
  const lum = ([r, g, b]) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const rgb = (c) => c.match(/[\\d.]+/g).slice(0, 3).map(Number);
  const out = {};
  for (const r of document.querySelectorAll('#usecases table.items tbody tr[data-uc]')) {
    const q = (s) => r.querySelector(s), cs = (e) => getComputedStyle(e);
    const text = ['.t', '.where', '.meta2', '.on', '.stp', '.mslab'].map((s) => q(s)).filter(Boolean).map((e) => [e.className || e.tagName, cs(e).color]);
    const pill = q('td.c-status .pill'), av = q('.av'), eye = q('td.c-eye .weye');
    const white = 'rgb(255, 255, 255)';
    out[r.dataset.uc] = { off: r.classList.contains('off'), text, textBg: cs(r).backgroundColor,
      pill: pill && [cs(pill).backgroundColor, cs(pill).boxShadow, cs(pill).borderTopWidth, cs(pill).color, pill.getBoundingClientRect().height > 8, cs(pill).display],
      av: av && [cs(av).backgroundColor, cs(av).color], eye: eye && [cs(eye).color, eye.querySelector('svg') ? eye.querySelector('svg').innerHTML : '', eye.getAttribute('aria-pressed'), eye.title, eye.getBoundingClientRect().width > 8],
      rowH: r.getBoundingClientRect().height, op: cs(r).opacity,
      ratio: (() => { const a = lum(rgb(GREY)) + 0.05, b = lum([255, 255, 255]) + 0.05; return Math.max(a, b) / Math.min(a, b); })() };
  }
  return out; })()""".replace("GREY", json.dumps(GREY))

MENU = """(() => [...document.querySelectorAll('.cols-menu [role=menuitemcheckbox]')].map((b) => [b.textContent.replace(/\\s+/g, ' ').trim(), b.getAttribute('aria-checked'), b.getAttribute('aria-disabled')]))()"""

GROUPS = """(() => [...document.querySelectorAll('#usecases .grp-b')].map((b) => {
  const th = b.closest('th') || b, g = getComputedStyle(b), gl = b.querySelector('.gl'), gc = b.querySelector('.gc'), t = getComputedStyle(th);
  const chain = []; for (let e = b.parentElement; e && e.id !== 'usecases'; e = e.parentElement) { const s = getComputedStyle(e); chain.push([e.tagName, s.borderTopWidth, s.borderLeftWidth, s.borderTopLeftRadius, s.boxShadow]); }
  return { gl: gl && gl.textContent, gc: gc && gc.textContent, exp: b.getAttribute('aria-expanded'), inTr: !!b.closest('tr.grp'), chev: !!b.querySelector('.gch svg'),
    font: [g.fontWeight, g.fontSize], th: [t.backgroundColor, t.borderTopWidth, t.borderLeftWidth, t.borderBottomWidth, t.borderBottomStyle, t.borderTopLeftRadius],
    chain }; }))()"""


class Redesign:
    """The tests, run under the Classic theme layer (Cards is pinned unchanged in CardsAsOnMain)."""
    css = None

    def open_page(self, cdp, width, hash_="#usecases&p=ABC", ready=None):
        p = Pg.at(self, cdp, self.s.port, hash_)
        cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, p.sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1000, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        p.until(ready or "document.querySelectorAll('#usecases [data-uc]').length > 0", "the list drew")
        self.assertEqual(p.js("window.innerWidth"), width)
        return p

    def setUp(self):
        super().setUp()
        plant(self)
        with self.store.step("dashboard", USER) as st:
            st.update("use_cases", self.uc1, {"owner": "Pat Demo", "commitment": "Committed"})
            st.update("use_cases", self.uc2, {"owner": "Sam Demo"})
        self.s.close()
        html = testpage.html()
        if self.css:
            html = page.layer_theme(html, self.css)
        self.s = real_server(self.store.path, self.store.data_for, page_html=lambda: html, seam=self.seam)
        self.addCleanup(self.s.close)

    def widths(self):
        return (1400, 900)

    # R1 ---------------------------------------------------------------------------------------------------------------------------
    def test_r1_the_page_is_one_flat_table_like_work_items(self):
        for w in self.widths():
            with self.subTest(width=w), chrome() as cdp:
                p = self.open_page(cdp, w)
                g = p.js(STRUCT)
                self.assertTrue(g["table"], "a table.items, as Work items")
                self.assertEqual(g["oldList"], 0, "the old list (ul, its own column-name strip, li rows) is gone")
                self.assertEqual(g["heads"], 1, "one column header row")
                self.assertEqual([t[0] for t in g["th"][:6]], NAMES)
                self.assertEqual(len(g["th"]), 7, "six columns and the eye cell that holds the Columns button")
                self.assertTrue(g["cols"], "the Columns button is in the last header cell")
                self.assertEqual(g["h1"], "Use cases")
                self.assertEqual(g["tabs"], [["All use cases", "4"], ["On the dashboard", "2"], ["Committed", "1"], ["At risk", "2"]])
                self.assertTrue(g["fline"], "the filter box with its count")
                self.assertEqual(g["lsw"], ["List", "Board"], "the list/board pair")
                self.assertEqual(g["icons"], 2, "the Group by and Sort by buttons (labelled since Row 1316 follow-up)")
                self.assertEqual([r["ref"].split(" · ")[0] for r in g["rows"]], ["UC 1.1", "UC 1.2", "UC 1.10", "UC 2.1"])
                self.assertTrue(g["noScroll"])
                for i, r in enumerate(g["rows"]):
                    last = i == len(g["rows"]) - 1   # Row 1405: no line under the last row
                    self.assertEqual(r["rule"][:2], ["0px", "none"] if last else ["1px", "solid"], "a thin row rule under every row but the last: " + r["uc"])
                    self.assertTrue(r["eye"], "the eye is the last cell")
                    for k, hide in enumerate(NAMES):
                        left = r["left"][k]
                        if w == 900 and hide in HIDE_AT_900:
                            self.assertFalse(left[1], f"900: {hide} is not drawn")
                        else:
                            self.assertTrue(left[1], f"{hide} is drawn")
                            self.assertAlmostEqual(left[0], g["th"][k][2], delta=1, msg=f"{hide}: the cell sits under its header")
                one = g["rows"][0]
                self.assertEqual(one["title"], {r["ref"]: r for r in self.store.read("use_cases", "ABC")}["1.1"]["title"])
                self.assertEqual(one["ref"], "UC 1.1 · Committed", "the grey line: the id, then the commitment")
                self.assertEqual(g["rows"][1]["ref"], "UC 1.2", "no commitment, no dot")
                self.assertEqual(one["av"], "PD")
                self.assertEqual(g["rows"][3]["av"], None, "no owner, no avatar")
                self.assertEqual(one["stp"], "1 next step")
                self.assertEqual(one["prgH"], 0, "Row 1399: the prototype draws no progress bar under the next steps (it stays in the markup, not drawn)")
                if w == 1400:
                    self.assertTrue(one["onVis"] and one["onText"] == "Pat Demo", "1400: the owner's name beside the avatar")
                    self.assertTrue(one["msVis"] and (one["ms"] or "").strip(), "the milestone cell names the linked milestone")
                else:
                    self.assertFalse(one["onVis"], "900: the owner shows the avatar only")
                    self.assertTrue(one["avBox"][0] > 16, "900: the avatar is drawn")

    def test_r1_the_look_is_the_work_items_look_measured_on_both_pages(self):
        for w in self.widths():
            with self.subTest(width=w), chrome() as cdp:
                p = self.open_page(cdp, w)
                uc = p.js(LOOK + "('#usecases')")
                p.js("location.hash = '#work&p=ABC'")
                p.until("!!document.querySelector('#work table.items tbody tr')", "Work items drew")
                wk = p.js(LOOK + "('#work')")
                for k in ("av", "gutter"):   # Row 1399 and Row 1405: th, td and vtab are the prototype's on Use cases and no longer equal to Work items (pinned in test_use_cases_rows_1399 and test_use_cases_box_1405); not fline: Row 1316 ruled the Classic Use cases filter a boxed input (the prototype's), Work items keeps its line
                    self.assertIsNotNone(uc[k], k + ": drawn on Use cases")
                    if k == "vtab":   # row 1394: the Work items tab is the prototype's 15px, padding 9px 10px 8px, 3px underline (its own look); the weight, colours and side padding stay the same on both pages
                        keep = (1, 2, 4, 6)
                        self.assertEqual([uc[k][i] for i in keep], [wk[k][i] for i in keep], k + ": weight, colour, side padding and underline colour the same as Work items")
                        continue
                    self.assertEqual(uc[k], wk[k], k + ": the same as Work items, measured on both pages")

    # R2 ---------------------------------------------------------------------------------------------------------------------------
    def test_r2_a_row_hidden_from_the_client_is_greyed_whole_and_still_visible(self):
        for w in self.widths():
            with self.subTest(width=w), chrome() as cdp:
                p = self.open_page(cdp, w)
                g = p.js(OFFLOOK)
                on, off = [v for v in g.values() if not v["off"]], [v for v in g.values() if v["off"]]
                self.assertEqual((len(on), len(off)), (2, 2), "two rows on the dashboard, two hidden from the client")
                for v in off:
                    self.assertTrue(v["text"], "text to read")
                    self.assertEqual([c for _, c in v["text"] if c != GREY], [], "every text of the hidden row is #667391")
                    self.assertGreaterEqual(v["ratio"], 4.5)
                    self.assertGreater(v["rowH"], 30, "still visible")
                    self.assertEqual(v["op"], "1", "greyed by colour, not by opacity")
                    self.assertEqual(v["pill"][0], "rgba(0, 0, 0, 0)", "the status pill is unfilled")
                    self.assertTrue(v["pill"][1] != "none" or v["pill"][2] == "1px", "with a ring")
                    self.assertTrue(v["pill"][4], "and still drawn")
                    if v["av"]:
                        self.assertEqual(v["av"][0], GREY, "grey avatar")
                    self.assertEqual(v["eye"][0], GREY)
                    self.assertTrue(v["eye"][4])
                    self.assertEqual(v["eye"][2], "false")
                for v in on:
                    self.assertNotEqual(v["pill"][0], "rgba(0, 0, 0, 0)", "a row on the dashboard keeps its filled pill")
                    self.assertNotIn(GREY, [c for _, c in v["text"]][:1], "the title of a shown row is not greyed")
                self.assertNotEqual(on[0]["eye"][1], off[0]["eye"][1], "the hidden row's eye is drawn crossed out")

    # R3 ---------------------------------------------------------------------------------------------------------------------------
    def test_r3_the_column_chooser(self):
        for w in self.widths():
            with self.subTest(width=w), chrome() as cdp:
                p = self.open_page(cdp, w)
                self.assertEqual(p.js("(() => { const b = document.querySelector('#usecases thead th:last-child button[aria-label=Columns]'); const r = b.getBoundingClientRect(); const o = [...document.querySelectorAll('#usecases thead th')].map((t) => t.getBoundingClientRect().right); return [b.title, b.getAttribute('aria-haspopup'), b.getAttribute('aria-expanded'), r.right >= Math.max(...o) - 12, r.width >= 24]; })()"),
                                 ["Choose the columns", "menu", "false", True, True], "the Columns icon at the right end of the header row")
                p.js("document.querySelector('#usecases button[aria-label=Columns]').click()")
                p.until("document.querySelectorAll('.cols-menu [role=menuitemcheckbox]').length > 0", "the chooser opened")
                words = [m[0] for m in p.js(MENU)]
                self.assertEqual(len(words), 9, "nine rows: " + repr(words))
                self.assertEqual([w_.split(" ")[0] for w_ in words], ["Use", "Where", "Status", "Owner", "Next", "Milestone", "Commitment", "Release", "On"], "in the order of the columns, then the optional ones")
                for lab in ("Use case", "Status"):
                    m = next(m for m in p.js(MENU) if m[0].startswith(lab))
                    self.assertEqual((m[1], m[2]), ("true", "true"), lab + " is locked on")
                for lab in ("Commitment", "Release", "On the dashboard"):
                    m = next(m for m in p.js(MENU) if m[0].startswith(lab))
                    self.assertEqual(m[1], "false", lab + " is off to start")
                for lab in ("Where it stands", "Owner", "Next steps", "Milestone"):
                    m = next(m for m in p.js(MENU) if m[0].startswith(lab))
                    self.assertEqual((m[1], m[2]), ("true", None), lab + " is on and can be switched")
                p.js("[...document.querySelectorAll('.cols-menu [role=menuitemcheckbox]')].find((b) => b.textContent.startsWith('Status')).click()")
                self.assertEqual(p.js("[...document.querySelectorAll('#usecases thead th')].some((t) => t.textContent.trim() === 'Status')"), True, "a locked column cannot be switched off")
                p.js("[...document.querySelectorAll('.cols-menu [role=menuitemcheckbox]')].find((b) => b.textContent.startsWith('Owner')).click()")
                p.until("![...document.querySelectorAll('#usecases thead th')].some((t) => t.textContent.trim() === 'Owner' && t.getBoundingClientRect().width > 1)", "Owner switched off")
                p.js("[...document.querySelectorAll('.cols-menu [role=menuitemcheckbox]')].find((b) => b.textContent.startsWith('Owner')).click()")
                p.until("[...document.querySelectorAll('#usecases thead th')].some((t) => t.textContent.trim() === 'Owner' && t.getBoundingClientRect().width > 1)", "Owner back")

    def test_r3_commitment_replaces_the_commitment_text_in_the_grey_line(self):
        for w in self.widths():
            with self.subTest(width=w), chrome() as cdp:
                p = self.open_page(cdp, w)
                grey = "(() => document.querySelector('#usecases tr[data-uc] .meta2').textContent)()"
                self.assertEqual(p.js(grey), "UC 1.1 · Committed")
                p.js("document.querySelector('#usecases button[aria-label=Columns]').click()")
                p.until("document.querySelectorAll('.cols-menu [role=menuitemcheckbox]').length > 0", "the chooser opened")
                p.js("[...document.querySelectorAll('.cols-menu [role=menuitemcheckbox]')].find((b) => b.textContent.startsWith('Commitment')).click()")
                p.until("[...document.querySelectorAll('#usecases thead th')].some((t) => t.textContent.trim() === 'Commitment')", "the Commitment column is in the header")
                col = p.js("(() => { const t = [...document.querySelectorAll('#usecases thead th')].find((x) => x.textContent.trim() === 'Commitment'); const c = document.querySelector('#usecases tr[data-uc] td.c-cm'); return [t.getBoundingClientRect().width > 1, c && c.textContent.trim(), c && Math.round(c.getBoundingClientRect().left) === Math.round(t.getBoundingClientRect().left)]; })()")
                if w == 1400:
                    self.assertEqual(col, [True, "Committed", True], "the column shows the commitment")
                    self.assertEqual(p.js(grey), "UC 1.1", "and the grey line no longer repeats it (owner: Commitment replaces the grey line)")
                else:
                    self.assertFalse(col[0], "900: the Commitment column is not drawn")
                    self.assertEqual(p.js(grey), "UC 1.1 · Committed", "900: so the grey line keeps the commitment")
                reload_to_new_page(p.js, "document.querySelectorAll('#usecases [data-uc]').length > 0")
                self.assertEqual(p.js("[...document.querySelectorAll('#usecases thead th')].some((t) => t.textContent.trim() === 'Commitment')"), True, "saved for this table and project in this browser")

    # R4 ---------------------------------------------------------------------------------------------------------------------------
    def test_r4_grouped_list_keeps_its_headings_and_the_new_columns(self):
        """Grouped by Status the new table still draws one heading button per group, opens and shuts it, and keeps one column header on top.
        How the heading line itself is drawn (name, count, hairline, no tile) belongs to the grouped-heading row and is pinned in its own tests."""
        for w in self.widths():
            with self.subTest(width=w), chrome() as cdp:
                p = self.open_page(cdp, w, ready="true")
                p.js("localStorage.setItem('clark.ucPage', JSON.stringify({ABC: {line: '', tab: 'all', group: 'status', sort: 'status'}}))")
                reload_to_new_page(p.js, "document.querySelectorAll('#usecases .grp-b').length > 0", "grouped by Status")
                self.assertEqual(p.js("document.querySelectorAll('#usecases .grp-b').length"), 3, "one heading button per status group")
                self.assertEqual(p.js("document.querySelectorAll('#usecases tr.colh').length"), 1, "the column header is drawn once, on top")
                self.assertEqual(p.js("document.querySelectorAll('#usecases tr[data-uc]').length"), 4, "all four rows are drawn")
                p.js("document.querySelector('#usecases .grp-b').click()")
                p.until("document.querySelector('#usecases .grp-b').getAttribute('aria-expanded') === 'false'", "collapsed")
                self.assertEqual(p.js("document.querySelectorAll('#usecases tr[data-uc]').length"), 2, "a shut group hides its two rows")


class CardsAsOnMain(Base):
    """Cards (the page with no Theme layer) still draws the Use cases list as origin/main (d526d17a3) does: the same style block, the same rendered
    DOM at 1400 and 900 (md5 of the #usecases section with the four use case ids folded to UC1..UC4, and of the open Group by menu), the old list
    markup and none of the new one. The md5 values were measured on a clean checkout of main with the same capture."""
    STYLE_MD5 = ["7195b3107c3b5022f3b40ad1dfbbe484"]
    LIST_MD5 = "a913dc96703a9e8cad0653b4a1c36db4"
    MENU_MD5 = "194c712b7ec600bda8708215bdd14f21"

    def test_the_cards_style_block_is_the_one_main_has(self):
        html = page.page_html(branding=page.NO_BRAND, theme=None)
        self.assertEqual([hashlib.md5(b.encode("utf-8")).hexdigest() for b in re.findall(r"<style[^>]*>(.*?)</style>", html, re.S)], self.STYLE_MD5)

    def test_the_cards_list_is_the_list_main_draws_at_1400_and_900(self):
        plant(self)
        self.s.close()
        html = testpage.html()
        self.s = real_server(self.store.path, self.store.data_for, page_html=lambda: html, seam=self.seam)
        self.addCleanup(self.s.close)
        ids = {self.uc1: "UC1", self.uc2: "UC2", self.uc3: "UC3", self.uc4: "UC4"}
        for w in (1400, 900):
            with self.subTest(width=w), chrome() as cdp:
                p = Pg.at(self, cdp, self.s.port, "#usecases&p=ABC")
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 1000, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                p.until("document.querySelectorAll('#usecases [data-uc]').length > 0", "the list drew")
                dom = p.js("document.querySelector('#usecases').outerHTML")
                for k, v in ids.items():
                    dom = dom.replace(k, v)
                self.assertEqual(hashlib.md5(dom.encode("utf-8")).hexdigest(), self.LIST_MD5, "the Cards Use cases DOM")
                self.assertEqual(p.js("[document.querySelectorAll('#usecases table.items').length, document.querySelectorAll('#usecases .ucl-box .ucl-cols').length, "
                                      "document.querySelectorAll('#usecases .ucl-list .ucl-row').length, document.querySelectorAll('#usecases .fline-tail .vicons').length, "
                                      "document.querySelectorAll('#usecases .ucl-tools #ucl-group, #usecases .ucl-tools #ucl-sort').length]"), [0, 1, 4, 0, 2],
                                 "the old list: no table, one column strip, four rows, no icon pair, Group by and Sort by beside Add use case")
                p.js("document.querySelector('#ucl-group').click()")
                p.until("!!document.querySelector('.ddmenu')", "the Group by menu")
                menu = re.sub(r'id="[^"]*"', "", p.js("document.querySelector('.ddmenu').outerHTML"))
                self.assertEqual(hashlib.md5(menu.encode("utf-8")).hexdigest(), self.MENU_MD5, "the Cards Group by menu")


class Classic(Redesign, Base):
    css = theme.css("prototype-2.0")


if __name__ == "__main__":
    unittest.main()
