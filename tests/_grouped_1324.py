"""Shared by the two test files of row 1324 (the Option A heading line): the page over a real server, and what a group draws, read in Chrome."""
import json
import shutil
import unittest
from unittest import mock

from _real_server import real_server
from clark import __main__ as launcher, page, server as sv, use_cases_read
from clark.store import open_store
from test_inline_edits import EMPTY_BRANDING, need_chrome, tearDownModule  # noqa: F401
from test_server import chrome, wait  # noqa: F401
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
      gcSize: g(gc, 'fontSize'), gcColor: g(gc, 'color'), chColor: g(ch, 'color'), label: (w.querySelector('.gl') || {}).textContent,
      btn: [g(b, 'display'), g(b, 'alignItems'), g(b, 'columnGap'), g(b, 'paddingTop'), g(b, 'paddingBottom'), g(b, 'paddingLeft')].join(' '), chMt: g(ch, 'marginTop'),
      gcBox: [g(gc, 'marginLeft'), g(gc, 'paddingTop'), g(gc, 'whiteSpace')].join(' '),
      first: Math.round(h.getBoundingClientRect().left) - Math.round(w.getBoundingClientRect().left) };
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
  const s = getComputedStyle(b), grow = Math.max(0, parseFloat(s.outlineWidth) + parseFloat(s.outlineOffset)), r = b.getBoundingClientRect();
  let clipped = false;
  for (let a = b.parentElement; a && a !== document.documentElement; a = a.parentElement) {
    const c = getComputedStyle(a);
    if (/(hidden|auto|scroll|clip)/.test(c.overflowX + c.overflowY)) { const q = a.getBoundingClientRect();
      if (r.left - grow < q.left - 0.5 || r.top - grow < q.top - 0.5 || r.right + grow > q.right + 0.5 || r.bottom + grow > q.bottom + 0.5) clipped = true; }
  }
  return { clipped, style: s.outlineStyle, width: s.outlineWidth, focused: document.activeElement === b }; })"""


def contrast_ok(rows, least=4.5):
    return [r for r in rows if r[1] < least]



class LiveBase(unittest.TestCase):
    """The real page over a real server and the demo data (fictional); the tests are in test_grouped_heading_1324 and test_grouped_heading_1324_cases."""

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
            self.assertIn(w["btn"].split()[0], ("inline-flex", "flex"), t + ": a flex row (a flex item of the heading row is blockified)")
            self.assertEqual(" ".join(w["btn"].split()[1:]), "flex-start 8px 2px 2px 0px", t + ": the button is a flex row, top aligned, 8 px between chevron and name, padding 2 px 0")
            self.assertEqual((w["chMt"], w["gcBox"]), ("3px", "2px 2px nowrap"), t + ": the chevron 3 px down; the count 2 px from the name and never wrapped")
            self.assertEqual(w["first"], 0, t + ": the heading starts at the left edge of its group")
        self.assertTrue(f["fit"], tag + ": nothing sideways")

    # ---- K-a, K-b: Work items ----
