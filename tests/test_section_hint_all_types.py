"""The first-time section handle hint shows whole for a top section of every type, at 1400 and 900 px, light and dark.

Run: python3 dev/run_tests.py test_section_hint_all_types

In a real browser, Edit mode, the Dashboard: for each of the section types, that type alone is the top section, and the hint beside its
handle is inside the window, at or below the top of its section, and not cut off by any box around it. No new words: the test reads no text.
"""
import json
import unittest

from _paths import ROOT

import test_peek as tp  # noqa: E402
from clark.store import SECTION_TYPES  # noqa: E402
from test_server import chrome, wait  # noqa: E402

BOXES = r"""(() => {
  const box = (e) => { const r = e.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; };
  const hint = document.querySelector('.sec-hint');
  if (!hint) return null;
  const h = box(hint), clipped = [];
  for (let p = hint.parentElement; p && p !== document.documentElement; p = p.parentElement) {
    const o = getComputedStyle(p);
    if (o.overflowX === 'visible' && o.overflowY === 'visible' && o.clipPath === 'none') continue;
    const b = box(p);
    if (h[0] < b[0] - 0.5 || h[1] < b[1] - 0.5 || h[2] > b[2] + 0.5 || h[3] > b[3] + 0.5) clipped.push(p.className || p.tagName);
  }
  const sec = hint.closest('.sec');
  const top = document.querySelector('.secs .sec');
  return { hint: h, sec: sec ? box(sec) : null, first: sec === top, clipped, width: document.documentElement.clientWidth, height: document.documentElement.clientHeight };
})()"""


class HintEverySection(unittest.TestCase):
    setUpClass = tp.Browser.__dict__["setUpClass"]
    tearDownClass = tp.Browser.__dict__["tearDownClass"]
    load_page = tp.Browser.load_page
    edit_mode = tp.Browser.edit_mode

    def top_is(self, kind):
        con = self.store.con
        first = con.execute("SELECT id FROM report_sections WHERE project=? ORDER BY sort_order LIMIT 1", (self.code,)).fetchone()[0]
        con.execute("UPDATE report_sections SET type=?, body='', beside=0, hidden=0 WHERE project=? AND id=?", (kind, self.code, first))
        con.commit()

    def test_the_hint_shows_whole_above_every_type(self):
        types = list(SECTION_TYPES)
        self.assertGreaterEqual(len(types), 30)
        saved = self.store.con.execute("SELECT id, type, body, beside, hidden FROM report_sections WHERE project=? ORDER BY sort_order", (self.code,)).fetchall()
        self.addCleanup(self.restore, saved)
        for kind in types:
            self.top_is(kind)
            for width in (1400, 900):
                with chrome() as cdp:
                    s, sid = self.load_page(cdp, width)
                    # The hint is meant to go after HINT_MS (4 s). This test measures where it sits, in two themes, one after the other: on a slow Mac
                    # (4 s is not enough for all of it) it went before the second read. Keep it for the whole test; its 4 s life is pinned elsewhere.
                    cdp.js("(() => { const t = window.setTimeout; window.setTimeout = (f, ms, ...a) => t(f, ms === 4000 ? 600000 : ms, ...a); })()", sid)
                    cdp.js("window.__sc = []; addEventListener('scroll', () => window.__sc.push([Math.round(performance.now()), scrollY]), true); window.__t0 = Math.round(performance.now())", sid)
                    self.edit_mode(cdp, sid)
                    cdp.js("document.querySelector('[data-view=dashboard]').click()", sid)
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.sec-hint')", sid)), f"the hint shows, {kind} {width}")
                    for theme in ("light", "dark"):
                        cdp.js(f"document.documentElement.dataset.theme = '{theme}'", sid)
                        self.settle(cdp, sid, f"{kind} {width} {theme}")
                        m = cdp.js(BOXES, sid)
                        where = f"{kind} {width} {theme}"
                        self.assertIsNotNone(m, where)
                        self.assertTrue(m["first"], f"the hint is on the top section, {where}")
                        self.assertGreaterEqual(m["hint"][0], 0, where)
                        self.assertLessEqual(m["hint"][2], m["width"], where)
                        self.assertGreaterEqual(m["hint"][1], 0, f"the hint is above the window, {where}: {m['hint']}")
                        self.assertGreaterEqual(m["hint"][1], m["sec"][1] - 0.5, f"the hint is above its section top, {where}: {m['hint']} {m['sec']}")
                        self.assertEqual(m["clipped"], [], f"the hint is cut off by {m['clipped']}, {where}")

    def settle(self, cdp, sid, where):
        """Wait (up to 10 s) for the page to be still: no scroll anchoring, scrolled to the top, the hint at the same place on two reads."""
        last = []
        seen = []

        def still():
            now = cdp.js("(document.documentElement.style.overflowAnchor === '' && scrollY === 0) ? JSON.stringify((() => { const h = document.querySelector('.sec-hint'); if (!h) return null; const r = h.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; })()) : null", sid)
            same = now is not None and now != "null" and last[:1] == [now]
            last[:] = [now]
            seen.append(now)
            return same
        ok = wait(still, 10)
        why = "" if ok else " | " + json.dumps({"reads": len(seen), "last": seen[-4:], "state": cdp.js("({anchor: document.documentElement.style.overflowAnchor, y: scrollY, hint: !!document.querySelector('.sec-hint'), anims: document.getAnimations().map(a => a.animationName || a.transitionProperty).slice(0, 6), motion: document.documentElement.dataset.motion || '', reduce: matchMedia('(prefers-reduced-motion: reduce)').matches, scrollH: document.documentElement.scrollHeight, innerH: innerHeight, hintH: (document.querySelector('.sec-hint') || {getBoundingClientRect: () => ({height: -1})}).getBoundingClientRect().height, scrolls: (window.__sc || []).slice(-8), t: Math.round(performance.now()) - (window.__t0 || 0), smooth: getComputedStyle(document.documentElement).scrollBehavior})", sid)})
        self.assertTrue(ok, f"the page settled, {where}" + why)

    def restore(self, saved):
        for i, t, b, be, hi in saved:
            self.store.con.execute("UPDATE report_sections SET type=?, body=?, beside=?, hidden=? WHERE project=? AND id=?", (t, b, be, hi, self.code, i))
        self.store.con.commit()


if __name__ == "__main__":
    unittest.main()
