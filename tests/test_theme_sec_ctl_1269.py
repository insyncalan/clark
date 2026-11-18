"""Row 1269: the Edit-mode section control (.sec-ctl) against the Classic section's 2px gutter rule and 20px padding, as Chrome lays it out.

Run: python3 dev/run_tests.py test_theme_sec_ctl_1269
Real Dashboard in Edit, over the fictional demo data, at 1400 and 900 only, in Classic (the Theme layered) and in Cards (no Theme).
Measured: getBoundingClientRect of every .sec-ctl against its .sec, the section's border box edge, its content edge (border plus padding)
and its heading box. The control must not overlap the heading or any text box in its section, and must stay inside the viewport.
Fails, never skips, without Chrome. The numbers are printed as a table.
"""
import json
import unittest

import test_glance_page as g
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome

from clark import page

NAME = "prototype-2.0"
SIZES = (1400, 900)
THEMES = (("classic", NAME), ("cards", None))
DENSITIES = ("compact", "comfortable")      # the standard (One card) and Comfortable, the one where the Classic gutter rule is drawn
TABLE = []

MEASURE = """(() => {
  const R = (e) => { const b = e.getBoundingClientRect(); return { l: b.left, t: b.top, r: b.right, b: b.bottom }; };
  const hit = (a, b) => a.l < b.r - 0.01 && a.r > b.l + 0.01 && a.t < b.b - 0.01 && a.b > b.t + 0.01;
  const out = [];
  for (const sec of document.querySelectorAll('#report .secs > .sec')) {
    const ctl = sec.querySelector(':scope > .sec-ctl'); if (!ctl) continue;
    const cs = getComputedStyle(sec), s = R(sec), c = R(ctl);
    if (c.r - c.l === 0 || s.r - s.l === 0) continue;
    const bl = parseFloat(cs.borderLeftWidth) || 0, pl = parseFloat(cs.paddingLeft) || 0;
    const content = s.l + bl + pl;
    const texts = [];       // every element of the section, outside the control, that holds text of its own
    for (const e of sec.querySelectorAll('*')) {
      if (ctl.contains(e)) continue;
      const own = [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
      if (own) { const q = R(e); if (q.r > q.l && q.b > q.t) texts.push(q); }
    }
    const head = sec.querySelector('.sec-head'), h = head ? R(head) : null;
    const rule = { l: s.l, t: s.t, r: s.l + bl, b: s.b };      // the left border line as a thin box
    out.push({ id: sec.dataset.id, right: sec.classList.contains('slot-right'), c, s, content, bl, pl, h,
      overHead: h ? hit(c, h) : false, overText: texts.filter((q) => hit(c, q)).length, texts: texts.length,
      overRule: bl > 0 && hit(c, rule), borderColour: cs.borderLeftColor,
      inView: c.l >= 0 && c.r <= innerWidth, scroll: document.documentElement.scrollWidth <= innerWidth,
      left_of_content: c.r <= content + 0.01 });
  }
  return JSON.stringify(out);
})()"""


class SecCtl(g.Setup):
    def setUp(self):
        super().setUp()
        self.s.httpd.page_html = lambda: page.page_html(branding=page.NO_BRAND, theme=self.theme)

    def measure(self, width, theme, density):
        self.theme = theme
        with chrome() as cdp:
            p = self.show(cdp, width=width, standard=True)
            p.js("document.documentElement.dataset.density = %r" % density)
            p.edit()
            return json.loads(p.js(MEASURE))

    def test_the_control_clears_the_gutter_rule_the_padding_and_the_text_at_1400_and_900(self):
        for name, theme in THEMES:
            for width, density in ((w, d) for w in SIZES for d in DENSITIES):
                with self.subTest(theme=name, width=width, density=density):
                    secs = self.measure(width, theme, density)
                    self.assertGreater(len(secs), 5, "the demo dashboard has many sections")
                    for d in secs:
                        where = f"{name} {density} {width} {d['id']}"
                        self.assertFalse(d["overHead"], f"{where}: the control overlaps the heading box")
                        self.assertEqual(d["overText"], 0, f"{where}: the control overlaps text")
                        self.assertFalse(d["overRule"], f"{where}: the control overlaps the section's left rule")
                        self.assertTrue(d["left_of_content"], f"{where}: the control ends before the section's content starts")
                        self.assertTrue(d["inView"], f"{where}: the control is inside the viewport")
                        self.assertTrue(d["scroll"], f"{where}: no sideways scroll")
                        TABLE.append((width, name, density, d))
        print()
        print("width theme   density     rule/pad ctl.left ctl.right sec.left content.left rule.l-r      overlap(rule/head/text)")
        seen = set()
        for width, name, density, d in TABLE:
            key = (width, name, density, d["right"])
            if key in seen:
                continue
            seen.add(key)
            c, s = d["c"], d["s"]
            print("%5d %-8s %-11s %g/%g %8.1f %9.1f %8.1f %12.1f %6.1f-%-6.1f %s/%s/%s (%s%s)" % (
                width, name, density, d["bl"], d["pl"], c["l"], c["r"], s["l"], d["content"], s["l"], s["l"] + d["bl"],
                "yes" if d["overRule"] else "no", "yes" if d["overHead"] else "no", "yes" if d["overText"] else "no",
                d["id"], " slot-right" if d["right"] else ""))


LOOK = """(() => [...document.querySelectorAll('#report .secs > .sec')].map((e) => { const c = getComputedStyle(e), r = e.getBoundingClientRect();
  return { id: e.dataset.id, w: r.width, odd: e.matches(':nth-child(odd):not(.is-hidden):not(.drag-slot)'), bl: c.borderLeftWidth, bs: c.borderLeftStyle,
    pl: c.paddingLeft, bt: c.borderTopWidth, bg: c.backgroundColor, col: c.borderLeftColor }; }).filter((d) => d.w > 0))()"""


class Gutter(g.Setup):
    """The Classic gutter (2px rule, 20px padding) on the even sections in both densities; the odd ones keep the panel and no rule (row 1311)."""

    def setUp(self):
        super().setUp()
        self.s.httpd.page_html = lambda: page.page_html(branding=page.NO_BRAND, theme=self.theme)

    def look(self, width, density, mode, scheme="light", print_=False, theme=NAME):
        self.theme = theme
        with chrome() as cdp:
            p = self.show(cdp, width=width, standard=True)
            p.js("document.documentElement.dataset.density = %r; document.documentElement.dataset.theme = %r" % (density, scheme))
            if mode == "edit":
                p.edit()
            if print_:
                cdp.call("Emulation.setEmulatedMedia", {"media": "print"}, p.sid)
            import time
            time.sleep(0.4)
            return p.js(LOOK)

    def test_even_sections_have_the_two_pixel_rule_and_twenty_pixels_odd_ones_have_none_in_both_densities(self):
        # the padding is 20 except where the page's own layout rules, which name #report or .slot-right and so outrank the Theme, set it:
        # Edit in Comfortable is 32 at both widths (room for the control inside the section), Edit in Compact at 900 is 0 (the control is in
        # the frame's padding), and the right half of a pair in Compact is 24 (the gap between the halves)
        for width in SIZES:
            for density in DENSITIES:
                for mode in ("edit", "view"):
                    with self.subTest(width=width, density=density, mode=mode):
                        rows = self.look(width, density, mode)
                        self.assertGreater(len(rows), 5)
                        pad = 20
                        if mode == "edit":
                            pad = 32 if density == "comfortable" else (0 if width == 900 else 20)
                        evens = [d for d in rows if not d["odd"]]
                        odds = [d for d in rows if d["odd"]]
                        self.assertTrue(evens and odds)
                        for d in evens:
                            self.assertEqual((d["bl"], d["bs"], d["bt"]), ("2px", "solid", "0px"), f"{d['id']} even: the rule, no top line")
                            half = density == "compact" and width == 1400
                            want = 24 if half and d["id"] == "ABC-S-006" else pad
                            self.assertEqual(d["pl"], "%dpx" % want, f"{d['id']} even padding")
                        for d in odds:
                            self.assertEqual(d["bl"], "0px", f"{d['id']} odd: no rule")
                            self.assertNotEqual(d["bg"], "rgba(0, 0, 0, 0)", f"{d['id']} odd keeps its panel")
                            self.assertEqual(d["bt"], "0px", d["id"])

    def test_the_rule_is_blue_in_edit_and_the_gutter_colour_in_view_in_light_and_dark(self):
        for scheme in ("light", "dark"):
            edit = self.look(1400, "compact", "edit", scheme)
            view = self.look(1400, "compact", "view", scheme)
            self.assertEqual(len({d["col"] for d in edit if not d["odd"]}), 1)
            self.assertNotEqual(edit[1]["col"], view[1]["col"], scheme + ": Edit is the brand blue, View the quiet gutter colour")
            self.assertTrue(all(d["bl"] == "2px" for d in view if not d["odd"]), scheme)

    def test_print_has_no_rule_and_no_padding_in_both_densities(self):
        for density in DENSITIES:
            for mode in ("view",):      # print is the View page; Edit's own padding rules are not print rules
                for d in self.look(1400, density, mode, print_=True):
                    self.assertEqual(d["bl"], "0px", f"{density} {mode} {d['id']}")
                    self.assertIn(d["pl"], ("0px", "24px") if d["id"] == "ABC-S-006" else ("0px",), f"{density} {mode} {d['id']}")      # 24: the pair gap, not the gutter


    def test_hover_and_focus_blend_the_brand_into_the_rule_in_both_densities(self):
        probe = "(() => { const e = document.querySelectorAll('#report .secs > .sec')[%d]; return getComputedStyle(e).borderLeftColor; })()"
        for density in DENSITIES:
            with self.subTest(density=density):
                self.theme = NAME
                with chrome() as cdp:
                    p = self.show(cdp, width=1400, standard=True)
                    p.js("document.documentElement.dataset.density = %r" % density)
                    import time
                    time.sleep(0.4)
                    rest = p.js(probe % 1)
                    want = p.js("""(() => { const q = document.createElement('i'); q.style.borderLeft = '2px solid color-mix(in srgb, var(--brand-blue) 35%, var(--gutter-rule))';
                        document.body.appendChild(q); const c = getComputedStyle(q).borderLeftColor; q.remove(); return c; })()""")
                    x, y = p.js("(() => { const r = document.querySelectorAll('#report .secs > .sec')[1].getBoundingClientRect(); return [r.left + 60, r.top + Math.min(r.height / 2, 40)]; })()")
                    cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y}, p.sid)
                    time.sleep(0.5)
                    self.assertTrue(p.js("document.querySelectorAll('#report .secs > .sec')[1].matches(':hover')"))
                    self.assertEqual(p.js(probe % 1), want, "hover blends 35% brand into the rule")
                    cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": 1, "y": 1}, p.sid)
                    time.sleep(0.5)
                    p.js("(() => { const e = document.querySelectorAll('#report .secs > .sec')[1]; const b = document.createElement('button'); e.appendChild(b); b.focus(); })()")
                    time.sleep(0.5)
                    self.assertEqual(p.js(probe % 1), want, "focus inside blends it too")
                    self.assertNotEqual(want, rest)


    def test_the_rule_fades_over_two_tenths_of_a_second_and_the_html_view_rule_and_its_print_reset_hold(self):
        for density in DENSITIES:
            with self.subTest(density=density):
                self.theme = NAME
                with chrome() as cdp:
                    p = self.show(cdp, width=1400, standard=True)
                    p.js("document.documentElement.dataset.density = %r; document.documentElement.dataset.mode = 'view'" % density)
                    got = p.js("(() => { const c = getComputedStyle(document.querySelectorAll('#report .secs > .sec')[1]); return [c.transitionDuration, c.borderLeftWidth, c.paddingLeft]; })()")
                    self.assertEqual(got[:2], ["0.2s", "2px"])
                    self.assertEqual(got[2], "20px", "the published page's rule: 20px")
                    cdp.call("Emulation.setEmulatedMedia", {"media": "print"}, p.sid)
                    got = p.js("(() => { const c = getComputedStyle(document.querySelectorAll('#report .secs > .sec')[1]); return [c.borderLeftWidth, c.paddingLeft]; })()")
                    self.assertEqual(got, ["0px", "0px"], "print: no rule, no padding")


class CardsUntouched(unittest.TestCase):
    def test_the_cards_page_has_none_of_the_raised_selectors_and_keeps_its_style_blocks(self):
        import hashlib, re
        cards = page.page_html(branding=page.NO_BRAND, theme=None)
        self.assertNotIn(".sec.sec.sec", cards)
        # the whole-page hash moves whenever another row changes the script bundle, so the proof is the style blocks (same pin as test_work_items_mockup_1195)
        blocks = [hashlib.md5(b.encode()).hexdigest() for b in re.findall(r"<style[^>]*>(.*?)</style>", cards, re.S)]
        self.assertEqual(blocks, ["7195b3107c3b5022f3b40ad1dfbbe484"])


if __name__ == "__main__":
    unittest.main()
