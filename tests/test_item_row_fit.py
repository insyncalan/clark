"""Row 1021 (review at 560 px): no part of a work-item row runs into its neighbour, and no page scrolls sideways, at any width.

Run: python3 dev/run_tests.py test_item_row_fit
The by-eye review failed PR 1178 at 560 px: on Open actions the date ran into the id, View and Edit, and the published page scrolled
sideways. The rule (#1022): no text overruns its neighbour and there is no sideways scroll at any width, 560 included. Every part of a row
(icon, status word, title, owner, date, priority, id, eye) is measured in a real browser at 900 and 1400 px, light and dark, in the
editor (Sneak peek and Edit) and in the published file. The ruling on the owner: the screen may show initials at 900 px and under; the
published file and the printed page always show the FULL name.
"""
import unittest

from test_item_one_line import Base, FITS, ROWS, width, Pg
from test_server import chrome, wait

WIDTHS = (900, 1400)
PRINT_WIDTH = 703        # an A4 page between its 12 mm side margins, as CSS px: what the print media rules see

# Every visible part of every row, its box, and the parts that are cut (text wider than its own box).
PARTS = r"""(() => { const out = [], bad = [];
 const vis = (e) => { const b = e.getBoundingClientRect(), c = getComputedStyle(e); return b.width > 2 && b.height > 2 && c.visibility !== 'hidden' && c.display !== 'none' && c.clip !== 'rect(0px, 0px, 0px, 0px)'; };
 const own = (e) => [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
 const part = (e) => e.matches('button,.ico,.av,.ico-w,.prio,.late,.cell-ce') || (own(e) && !e.closest('button,.ico,.av,.ico-w,.prio,.late,.cell-ce'));
 for (const r of document.querySelectorAll('.irows .wl-row')) {
  const leaves = [...r.querySelectorAll('*')].filter(e => vis(e) && part(e));
  for (let i = 0; i < leaves.length; i++) for (let j = i + 1; j < leaves.length; j++) { const a = leaves[i], b = leaves[j]; if (a.contains(b) || b.contains(a)) continue;
    const p = a.getBoundingClientRect(), q = b.getBoundingClientRect();
    if (Math.min(p.right, q.right) - Math.max(p.left, q.left) > 0.5 && Math.min(p.bottom, q.bottom) - Math.max(p.top, q.top) > 0.5) out.push(r.dataset.id + ': ' + (a.className || a.tagName) + ' [' + a.textContent.trim().slice(0, 14) + '] over ' + (b.className || b.tagName) + ' [' + b.textContent.trim().slice(0, 14) + ']'); }
  for (const e of r.querySelectorAll('.c-date, .c-id, .c-prio, .c-owner .nm, .ico-w')) if (vis(e) && e.scrollWidth > e.clientWidth + 1) bad.push(r.dataset.id + ': ' + e.className + ' is cut, ' + e.scrollWidth + ' > ' + e.clientWidth);
  const rb = r.getBoundingClientRect();
  for (const e of leaves) if (!e.matches('.cell-pick') && (e.getBoundingClientRect().right > rb.right + 1 || e.getBoundingClientRect().left < rb.left - 1)) bad.push(r.dataset.id + ': ' + (e.className || e.tagName) + ' sticks out of its row');
 } return {out, bad}; })()"""
OWNERS = r"""[...document.querySelectorAll('.irows .wl-row')].map(r => { const nm = r.querySelector('.c-owner .nm'), b = nm && nm.getBoundingClientRect(), c = nm && getComputedStyle(nm);
  return {id: r.dataset.id, text: nm ? nm.textContent.trim() : '', shown: !!nm && b.width > 3 && b.height > 3 && c.clip !== 'rect(0px, 0px, 0px, 0px)' && c.visibility !== 'hidden',
          whole: !!nm && nm.scrollWidth <= nm.clientWidth + 1 && nm.scrollHeight <= nm.clientHeight + 1}; })"""
SIDEWAYS = "document.documentElement.scrollWidth - document.documentElement.clientWidth"
NAMES = {"Sara Khan", "Omar Reid", "Mia Hale", "Steering group"}


def theme(p_js, dark):
    p_js(f"document.documentElement.setAttribute('data-theme', '{'dark' if dark else 'light'}')")


class Fit:
    def parts_ok(self, js, where):
        got = js(PARTS)
        self.assertEqual(got["out"], [], f"{where}: parts of a row overlap")
        self.assertEqual(got["bad"], [], f"{where}: text is cut or sticks out of its row")
        self.assertTrue(wait(lambda: js(SIDEWAYS) <= 0), f"{where}: the page scrolls sideways by {js(SIDEWAYS)} px")


class FitInTheEditor(Fit, Base):
    def test_no_overlap_and_no_sideways_scroll_in_view_and_edit_at_every_width_light_and_dark(self):
        with chrome() as cdp:
            p = Pg.at(self, cdp, self.served().port)
            p.ready()
            for mode in ("view", "edit"):
                if mode == "edit":
                    p.edit()
                for dark in (False, True):
                    theme(p.js, dark)
                    for w in WIDTHS:
                        width(cdp, p.sid, w)
                        self.parts_ok(p.js, f"{mode} {'dark' if dark else 'light'} {w}")

    def test_on_screen_at_900_and_under_the_owner_is_initials_and_above_it_is_the_name(self):
        with chrome() as cdp:
            p = Pg.at(self, cdp, self.served().port)
            p.ready()
            for w, name in ((1400, True), (900, False)):
                width(cdp, p.sid, w)
                for r in p.js(OWNERS):
                    self.assertEqual(r["shown"], name, f"{r['id']} at {w}")


class FitInThePublishedFile(Fit, Base):
    def load_app(self, cdp):
        path = self.published()
        tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cdp.call("Page.navigate", {"url": path.as_uri()}, sid)
        self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('.wl-row').length > 0", sid)))
        return sid

    def test_no_overlap_and_no_sideways_scroll_at_every_width_light_and_dark(self):
        with chrome() as cdp:
            sid = self.load_app(cdp)
            js = lambda e: cdp.js(e, sid)
            for dark in (False, True):
                theme(js, dark)
                for w in WIDTHS:
                    width(cdp, sid, w)
                    self.parts_ok(js, f"file {'dark' if dark else 'light'} {w}")

    def test_the_file_shows_the_full_owner_name_at_every_width(self):
        with chrome() as cdp:
            sid = self.load_app(cdp)
            for w in WIDTHS:
                width(cdp, sid, w)
                rows = cdp.js(OWNERS, sid)
                self.assertTrue(rows)
                for r in rows:
                    self.assertIn(r["text"], NAMES)
                    self.assertTrue(r["shown"] and r["whole"], f"{r['id']}: the whole name '{r['text']}' shows at {w}: {r}")

    def test_the_printed_page_shows_the_full_owner_name_and_fits(self):
        with chrome() as cdp:
            sid = self.load_app(cdp)
            width(cdp, sid, PRINT_WIDTH)
            cdp.call("Emulation.setEmulatedMedia", {"media": "print"}, sid)
            cdp.js("window.dispatchEvent(new Event('beforeprint'))", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.print-tab')", sid)))
            rows = cdp.js(OWNERS, sid)
            self.assertTrue(rows)
            for r in rows:
                self.assertTrue(r["shown"] and r["whole"], f"{r['id']}: the whole name shows on paper: {r}")
            self.parts_ok(lambda e: cdp.js(e, sid), "print")


if __name__ == "__main__":
    unittest.main()
