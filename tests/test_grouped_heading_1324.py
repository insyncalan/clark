"""Row 1324 (Grouped view, Option A): the group name is a heading line on the page, as Chrome computes it, at 1400 and 900 px, light and dark.

Run: python3 dev/run_tests.py test_grouped_heading_1324
The approved mock-up is clark-plan mockups/1324-grouped-view-template/. Work items and Use cases, in the Cards look and in the Classic look: no tile (no border,
no corners, no fill, nothing that clips), the heading Montserrat 600 15 px in the heading colour with one 1 px hairline under it, 18 px above each group, the count
13 px and muted, the column names drawn once on top, the flat list ("Group by: Nothing") still a card, and the collapse button keeping a visible focus ring and
a contrast of at least 4.5 to 1. Published pages (a use case group and a Work items group) draw the same heading line. Behaviour is not changed here: the collapse
tests of the other files stay.
"""
import json
import shutil
import unittest
from unittest import mock

from _real_server import real_server
from clark import __main__ as launcher, page, server as sv, use_cases_read
from clark.store import open_store
from test_inline_edits import EMPTY_BRANDING, need_chrome, tearDownModule  # noqa: F401
from test_server import chrome, wait
from test_work_items import FIXED_DATE, load_demo, page_target

NAME = "prototype-2.0"
SIZES = (1400, 900)

# what a group draws, in the live page (the editor's Work items or Use cases): one list of facts per group
FACTS = r"""((scope, groupSel, headSel) => {
  const g = (e, k) => getComputedStyle(e)[k];
  const probe = document.createElement('i'); document.body.appendChild(probe);
  const col = (v) => { probe.style.color = 'var(' + v + ')'; return g(probe, 'color'); };
  const groups = [...document.querySelectorAll(scope + ' ' + groupSel)].map((w) => {
    const h = w.querySelector(headSel), b = w.querySelector('.grp-b'), gc = w.querySelector('.gc'), ch = w.querySelector('.grp-b .i, .grp-b svg');
    return { bw: g(w, 'borderTopWidth') + g(w, 'borderBottomWidth') + g(w, 'borderLeftWidth') + g(w, 'borderRightWidth'), radius: g(w, 'borderTopLeftRadius'), bg: g(w, 'backgroundColor'),
      ox: g(w, 'overflowX'), oy: g(w, 'overflowY'), mt: g(w, 'marginTop'),
      hBg: g(h, 'backgroundColor'), pad: [g(h, 'paddingTop'), g(h, 'paddingRight'), g(h, 'paddingBottom'), g(h, 'paddingLeft')].join(' '),
      hLine: g(h, 'borderBottomWidth') + ' ' + g(h, 'borderBottomStyle'), hTop: g(h, 'borderTopWidth'), hRadius: g(h, 'borderTopLeftRadius'),
      font: g(b, 'fontFamily'), fw: g(b, 'fontWeight'), fs: g(b, 'fontSize'), color: g(b, 'color'),
      gcSize: g(gc, 'fontSize'), gcColor: g(gc, 'color'), chColor: g(ch, 'color'), label: (w.querySelector('.gl') || {}).textContent };
  });
  return { groups, heading: col('--heading'), muted: col('--text-muted'), head: g(document.body, 'fontFamily'),
    fit: document.documentElement.scrollWidth <= window.innerWidth };
})"""

RATIO = r"""((sels) => {
  const rgb = (c) => c.match(/[\d.]+/g).slice(0, 3).map(Number);
  const lum = ([r, g, b]) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const ratio = (a, b) => { const x = lum(rgb(a)), y = lum(rgb(b)); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  return sels.map((sel) => { const el = document.querySelector(sel); let bg = el, back = 'rgba(0, 0, 0, 0)';
    while (bg && /rgba\(.*, 0\)|transparent/.test(back)) { back = getComputedStyle(bg).backgroundColor; bg = bg.parentElement; }
    return [sel, ratio(getComputedStyle(el).color, back)]; });
})"""

# the focus ring of the collapse button must be inside every ancestor that clips: [clipped?, ring style, ring width]
RING = r"""((sel) => { const b = document.querySelector(sel); b.focus();
  const s = getComputedStyle(b), grow = parseFloat(s.outlineWidth) + Math.max(0, parseFloat(s.outlineOffset)), r = b.getBoundingClientRect();
  let clipped = false;
  for (let a = b.parentElement; a && a !== document.documentElement; a = a.parentElement) {
    const c = getComputedStyle(a);
    if (/(hidden|auto|scroll|clip)/.test(c.overflowX + c.overflowY)) { const q = a.getBoundingClientRect();
      if (r.left - grow < q.left - 0.5 || r.top - grow < q.top - 0.5 || r.right + grow > q.right + 0.5 || r.bottom + grow > q.bottom + 0.5) clipped = true; }
  }
  return { clipped, style: s.outlineStyle, width: s.outlineWidth, focused: document.activeElement === b }; })"""


def contrast_ok(rows, least=4.5):
    return [r for r in rows if r[1] < least]


class Live(unittest.TestCase):
    """The real page over a real server and the demo data (fictional)."""

    def setUp(self):
        need_chrome()
        self.store, self.folder, _ = load_demo()
        self.addCleanup(shutil.rmtree, str(self.folder), True)
        self.addCleanup(self.store.close)
        self.path = self.folder / "clark.db"
        self.theme = None
        self.s = real_server(self.path, self.read, projects=lambda archived=False: [{"code": "TUL", "name": "Tulip"}],
                             page_html=lambda: page.page_html(EMPTY_BRANDING, theme=self.theme))
        self.s.httpd.use_cases = use_cases_read.make_read(self.read, lambda code: set(), launcher.use_case_history(mock.Mock(path=self.path)))
        self.addCleanup(self.s.close)
        quiet = mock.patch.object(sv.LOG, "disabled", True)
        quiet.start()
        self.addCleanup(quiet.stop)

    def read(self, code, archived="hide"):
        st = open_store(self.path, onedrive_roots=[])
        try:
            return st.data_for(code, archived=archived)
        finally:
            st.close()

    def open(self, cdp, where, width, scheme, theme):
        self.theme = theme
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        if getattr(self, "keep", None):
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": self.keep}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1000, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.s.port}/{where}"}, sid)
        return sid

    def work(self, cdp, width, scheme, theme):
        sid = self.open(cdp, "#work&p=TUL&f=mode:all", width, scheme, theme)
        self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('#work tbody tr[data-id]').length > 0", sid), 20), "Work items drew")
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-cell]')", sid)), "the pickers are on")
        return sid

    def cases(self, cdp, width, scheme, theme, group="status"):
        self.keep = "try { localStorage.setItem('clark.ucPage', JSON.stringify({TUL: {group: %s}})); } catch (e) {}" % json.dumps(group)
        sid = self.open(cdp, "#usecases&p=TUL", width, scheme, theme)
        self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('#usecases .ucl-row[data-uc]').length > 0", sid), 20), "the list drew")
        return sid

    def facts(self, cdp, sid, scope, group, head):
        return json.loads(cdp.js("JSON.stringify(%s(%s, %s, %s))" % (FACTS, json.dumps(scope), json.dumps(group), json.dumps(head)), sid))

    def line(self, tag, f, heading_color, muted):
        """The Option A heading line of every group in the facts read (K-a and K-c)."""
        self.assertTrue(f["groups"], tag + ": groups are drawn")
        for n, w in enumerate(f["groups"]):
            t = f"{tag} group {n} {w['label']}"
            self.assertEqual(w["bw"], "0px0px0px0px", t + ": no border (no tile)")
            self.assertEqual(w["radius"], "0px", t + ": no rounded corners")
            self.assertEqual(w["bg"], "rgba(0, 0, 0, 0)", t + ": no fill on the group")
            self.assertEqual((w["ox"], w["oy"]), ("visible", "visible"), t + ": nothing clips the heading or its focus ring")
            self.assertEqual(w["mt"], "18px", t + ": 18 px of space above the group")
            self.assertEqual(w["hBg"], "rgba(0, 0, 0, 0)", t + ": no band behind the heading")
            self.assertEqual(w["hRadius"], "0px", t + ": no corners on the heading")
            self.assertEqual(w["hTop"], "0px", t + ": no line above the heading")
            self.assertEqual(w["hLine"], "1px solid", t + ": one 1 px hairline under the heading")
            pt, pr, pb, pl = w["pad"].split()
            self.assertEqual((pt, pb, pl), ("0px", "6px", "0px"), t + ": padding 0 0 6px")
            self.assertIn("Montserrat", w["font"], t + ": the heading face")
            self.assertEqual((w["fw"], w["fs"]), ("600", "15px"), t + ": 600 and 15 px")
            self.assertEqual(w["color"], heading_color, t + ": the heading colour")
            self.assertEqual(w["gcSize"], "13px", t + ": the count is 13 px")
            self.assertEqual(w["gcColor"], muted, t + ": the count is muted")
            self.assertEqual(w["chColor"], muted, t + ": the chevron is muted")
        self.assertTrue(f["fit"], tag + ": nothing sideways")

    # ---- K-a, K-b: Work items ----
    def test_work_items_groups_are_heading_lines_not_tiles(self):
        for scheme in ("light", "dark"):
            for width in SIZES:
                for theme in (None, NAME):
                    with self.subTest(scheme=scheme, width=width, theme=theme), chrome() as cdp:
                        sid = self.work(cdp, width, scheme, theme)
                        f = self.facts(cdp, sid, "#work", ".wgroup:has(table.grouped)", "tr.grp th")
                        self.line(f"work {theme} {scheme} {width}", f, f["heading"], f["muted"])

    def test_work_items_column_names_once_on_top_and_the_columns_line_up(self):
        for width in SIZES:
            for theme in (None, NAME):
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    sid = self.work(cdp, width, "light", theme)
                    got = json.loads(cdp.js("""(() => {
                      const hs = [...document.querySelectorAll('#work tr.colh')], first = document.querySelector('#work tbody tr[data-id]');
                      const heads = hs.length ? [...hs[0].querySelectorAll('th')] : [];
                      const gs = [...document.querySelectorAll('#work .wgroup:has(table.grouped)')];
                      const leftsOf = (cells) => cells.map((c) => Math.round(c.getBoundingClientRect().left));
                      const rows = gs.map((w) => { const r = w.querySelector('tbody tr[data-id]'); return r ? leftsOf([...r.children]) : null; }).filter(Boolean);
                      const top = hs.length && gs.length ? hs[0].getBoundingClientRect().bottom <= gs[0].getBoundingClientRect().top + 1 : false;
                      return JSON.stringify({ colh: hs.length, inGroup: document.querySelectorAll('#work .wgroup tr.colh').length, groups: gs.length, heads: leftsOf(heads), rows, top,
                        grips: hs.length ? hs[0].querySelectorAll('[data-cgrip]').length : 0, ths: heads.length, pickers: document.querySelectorAll('#work .cols-btn:not(.cols-kbd)').length,
                        kbd: document.querySelectorAll('#work .cols-btn.cols-kbd').length, tabs: [...document.querySelectorAll('#work table.items *')].filter(e => e.tabIndex >= 0 && !e.disabled && !e.closest('tr.grp')).length }); })()""", sid))
                    tag = f"{theme} {width}"
                    self.assertEqual(got["colh"], 1, tag + ": the column names are drawn once")
                    self.assertEqual(got["inGroup"], 0, tag + ": none inside a group")
                    self.assertGreater(got["groups"], 1, tag + ": several groups")
                    self.assertTrue(got["top"], tag + ": the one header is above the first group")
                    self.assertEqual(got["grips"], got["ths"], tag + ": a resize handle on every column")
                    self.assertEqual(got["pickers"], 1, tag + ": one column picker")
                    self.assertEqual(got["kbd"], 1, tag + ": one keyboard way into the picker")
                    self.assertGreater(len(got["rows"]), 1)
                    for n, r in enumerate(got["rows"]):
                        self.assertEqual(r, got["heads"][:len(r)] if len(r) <= len(got["heads"]) else None, f"{tag}: group {n} rows start where the header columns start")

    def test_work_items_flat_list_keeps_its_card_and_extra_columns_still_scroll(self):
        with chrome() as cdp:
            sid = self.work(cdp, 1400, "light", None)
            cdp.js("document.querySelector('#viewMenu').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.ddmenu [data-kind=\"group:nothing\"]')", sid)))
            cdp.js("document.querySelector('.ddmenu [data-kind=\"group:nothing\"]').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("!document.querySelector('tr.grp')", sid)))
            card = json.loads(cdp.js("JSON.stringify((() => { const s = getComputedStyle(document.querySelector('#work .wgroup')); return [s.borderTopWidth, s.borderTopLeftRadius, s.overflowX, s.overflowY]; })())", sid))
            self.assertEqual(card[0], "1px", "the flat list is still a bordered card")
            self.assertNotEqual(card[1], "0px", "with rounded corners")
            self.assertIn(card[2], ("hidden", "auto"))
            # a Work items table with an extra column (row 1195) still scrolls sideways inside its box
            cdp.js("(() => { const d = document.createElement('div'); d.className = 'wgroup'; d.id = 'probe'; d.innerHTML = '<table class=\"items\"><tbody><tr><td class=\"c-x\">x</td></tr></tbody></table>'; document.body.appendChild(d); })()", sid)
            self.assertEqual(cdp.js("getComputedStyle(document.querySelector('#probe')).overflowX", sid), "auto")

    # ---- K-e: the control ----
    def test_the_collapse_button_keeps_a_focus_ring_that_is_not_clipped_and_every_text_is_4_5_to_1(self):
        for scheme in ("light", "dark"):
            for width in SIZES:
                for theme in (None, NAME):
                    with self.subTest(scheme=scheme, width=width, theme=theme), chrome() as cdp:
                        sid = self.work(cdp, width, scheme, theme)
                        ring = json.loads(cdp.js("JSON.stringify(%s('#work .wgroup .grp-b'))" % RING, sid))
                        self.assertEqual((ring["clipped"], ring["style"], ring["width"], ring["focused"]), (False, "solid", "2px", True), f"work {scheme} {width} {theme}")
                        low = contrast_ok(json.loads(cdp.js("JSON.stringify(%s(['#work .grp-b .gl', '#work .grp-b .gc']))" % RATIO, sid)))
                        self.assertEqual(low, [], f"work heading and count contrast {scheme} {width} {theme}")
                        # hover: the heading takes the brand colour, still 4.5 to 1
                        x, y = json.loads(cdp.js("(() => { const r = document.querySelector('#work .grp-b .gl').getBoundingClientRect(); return JSON.stringify([r.left + r.width / 2, r.top + r.height / 2]); })()", sid))
                        cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y}, sid)
                        self.assertTrue(wait(lambda: cdp.js("document.querySelector('#work .grp-b').matches(':hover')", sid)))
                        hov = cdp.js("getComputedStyle(document.querySelector('#work .grp-b')).color", sid)
                        rest = cdp.js("(() => { const p = document.createElement('i'); document.body.appendChild(p); p.style.color = 'var(--heading)'; return getComputedStyle(p).color; })()", sid)
                        self.assertNotEqual(hov, rest, f"{scheme} {width} {theme}: hover changes the heading colour")
                        low = contrast_ok(json.loads(cdp.js("JSON.stringify(%s(['#work .grp-b']))" % RATIO, sid)))
                        self.assertEqual(low, [], f"work hovered heading contrast {scheme} {width} {theme}")

    # ---- K-c: the Use cases editor list ----
    def test_use_cases_groups_are_heading_lines_with_one_column_header(self):
        for scheme in ("light", "dark"):
            for width in SIZES:
                for theme in (None, NAME):
                    with self.subTest(scheme=scheme, width=width, theme=theme), chrome() as cdp:
                        sid = self.cases(cdp, width, scheme, theme)
                        f = self.facts(cdp, sid, "#usecases", ".ucl-group", ".ucl-grp")
                        tag = f"cases {theme} {scheme} {width}"
                        self.line(tag, f, f["heading"], f["muted"])
                        got = json.loads(cdp.js("""JSON.stringify((() => { const g = (e, k) => getComputedStyle(e)[k], box = document.querySelector('#usecases .ucl-box'), cols = [...document.querySelectorAll('#usecases .ucl-cols')];
                          const lasts = [...document.querySelectorAll('#usecases .ucl-group .ucl-list > li:last-child .ucl-row, #usecases .ucl-group .ucl-list > .ucl-row:last-child')];
                          const rows = [...document.querySelectorAll('#usecases .ucl-group .ucl-row')];
                          return { box: [g(box, 'borderTopWidth'), g(box, 'borderTopLeftRadius'), g(box, 'backgroundColor'), g(box, 'overflowX')], cols: cols.length, colsBg: g(cols[0], 'backgroundColor'),
                            colsAbove: cols[0].getBoundingClientRect().bottom <= document.querySelector('#usecases .ucl-group').getBoundingClientRect().top + 1, colsCase: g(cols[0], 'textTransform'),
                            lasts: lasts.map((e) => g(e, 'borderBottomWidth')), lastCount: lasts.length, groups: document.querySelectorAll('#usecases .ucl-group').length,
                            rowPadL: [...new Set(rows.map((e) => g(e, 'paddingLeft')))], colsPadL: g(cols[0], 'paddingLeft') }; })())""", sid))
                        self.assertEqual(got["box"], ["0px", "0px", "rgba(0, 0, 0, 0)", "visible"], tag + ": the list box is not a tile")
                        self.assertEqual(got["cols"], 1, tag + ": the column header is drawn once")
                        self.assertEqual(got["colsBg"], "rgba(0, 0, 0, 0)", tag + ": no grey strip behind the column header")
                        self.assertEqual(got["colsCase"], "none", tag + ": the column header is not in capitals")
                        self.assertTrue(got["colsAbove"], tag + ": on top of the first group")
                        self.assertEqual(got["lastCount"], got["groups"], tag + ": a last row in every group")
                        self.assertEqual(set(got["lasts"]), {"1px"}, tag + ": the last row of a group keeps its bottom hairline")
                        self.assertEqual(got["rowPadL"], [got["colsPadL"]], tag + ": the rows and the column header start at the same place")

    def test_use_cases_flat_list_keeps_its_card_under_classic(self):
        with chrome() as cdp:
            sid = self.cases(cdp, 1400, "light", NAME, group="nothing")
            box = json.loads(cdp.js("JSON.stringify((() => { const s = getComputedStyle(document.querySelector('#usecases .ucl-box')); return [s.borderTopWidth, s.borderTopLeftRadius, s.overflowX]; })())", sid))
            self.assertEqual((box[0], box[2]), ("1px", "hidden"), "the flat Classic list is still the framed card")
            self.assertNotEqual(box[1], "0px")

    def test_use_cases_collapse_button_focus_ring_and_contrast(self):
        for scheme in ("light", "dark"):
            for width in SIZES:
                for theme in (None, NAME):
                    with self.subTest(scheme=scheme, width=width, theme=theme), chrome() as cdp:
                        sid = self.cases(cdp, width, scheme, theme)
                        ring = json.loads(cdp.js("JSON.stringify(%s('#usecases .ucl-group .grp-b'))" % RING, sid))
                        self.assertEqual((ring["clipped"], ring["style"], ring["width"], ring["focused"]), (False, "solid", "2px", True), f"cases {scheme} {width} {theme}")
                        low = contrast_ok(json.loads(cdp.js("JSON.stringify(%s(['#usecases .grp-b .gl', '#usecases .grp-b .gc']))" % RATIO, sid)))
                        self.assertEqual(low, [], f"cases heading and count contrast {scheme} {width} {theme}")


# ---- K-d: published pages ----
import test_use_cases_list as T  # noqa: E402


class Published(T.Published):
    """The published file (the setup of test_use_cases_list.Published, without its tests)."""


for _n in [n for n in dir(Published) if n.startswith("test")]:
    setattr(Published, _n, None)


class PublishedHeading(Published):
    def test_a_published_use_case_group_and_a_published_work_items_group_are_heading_lines(self):
        path = self.publish()
        for scheme in ("light", "dark"):
            for width in SIZES:
                with self.subTest(scheme=scheme, width=width), chrome() as cdp:
                    p = self.draw(cdp, path, "#usecases&p=ABC")
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1000, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                    p.js("document.documentElement.dataset.theme = %s" % json.dumps(scheme))
                    p.js("document.querySelector('#ucp-group, [aria-label^=\"Group by\"]').click()")
                    p.until("!![...document.querySelectorAll('[role^=menuitem]')].find(e => e.textContent.trim() === 'Status')", "the menu")
                    p.js("[...document.querySelectorAll('[role^=menuitem]')].find(e => e.textContent.trim() === 'Status').click()")
                    p.until("document.querySelectorAll('.ucp-group').length >= 1", "grouped")
                    f = json.loads(p.js("JSON.stringify(%s('#usecases-file', '.ucp-group', '.ucp-grp'))" % FACTS))
                    # the published look is the Work items heading line: same rules as the live page
                    for n, w in enumerate(f["groups"]):
                        t = f"published cases {scheme} {width} group {n}"
                        self.assertEqual((w["bw"], w["radius"], w["bg"], w["ox"], w["oy"], w["mt"]), ("0px0px0px0px", "0px", "rgba(0, 0, 0, 0)", "visible", "visible", "18px"), t)
                        self.assertEqual((w["hBg"], w["hLine"], w["pad"].split()[2], w["fw"], w["fs"], w["gcSize"]), ("rgba(0, 0, 0, 0)", "1px solid", "6px", "600", "15px", "13px"), t)
                        self.assertIn("Montserrat", w["font"], t)
                        self.assertEqual((w["color"], w["gcColor"]), (f["heading"], f["muted"]), t)
                    self.assertTrue(f["groups"])
                    low = contrast_ok(json.loads(p.js("JSON.stringify(%s(['#usecases-file .grp-b .gl', '#usecases-file .grp-b .gc']))" % RATIO)))
                    self.assertEqual(low, [], f"published contrast {scheme} {width}")
                    p.js("[...document.querySelectorAll('.tabs .tab')].find(t => t.textContent === 'Work items').click()")
                    p.until("document.querySelectorAll('#work-list tbody tr[data-id], table.items tbody tr[data-id]').length > 0", "Work items")
                    got = json.loads(p.js("JSON.stringify({ colh: document.querySelectorAll('table.items tr.colh').length, tiles: [...document.querySelectorAll('.wgroup:has(table.grouped)')].map(w => getComputedStyle(w).borderTopWidth + getComputedStyle(w).borderTopLeftRadius) })"))
                    self.assertEqual(got["colh"], 1, f"published Work items: one column header {scheme} {width}")
                    self.assertTrue(got["tiles"] and set(got["tiles"]) == {"0px0px"}, f"published Work items: no tile {scheme} {width}: {got}")


if __name__ == "__main__":
    unittest.main()
