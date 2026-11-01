"""Issue 130, point 2 (laptop widths): the section handle sits clear of the section's content and rests at about .75 where it sits in the card's padding, and the section is as wide in Edit as in View.

Run: python3 dev/run_tests.py test_section_handle
The real page and a real server over the fictional demo report (the same harness as tests/test_report_editor.py), in headless Chrome at
1400 px and 900 px, light and dark. By bounding boxes: the handle sits inside the frame, ends before the section's heading starts, and
at 900 px sits in the card's own left padding and rests at about .75; the section card's left edge and width are the same in View and Edit.
The browser parts are required: they fail, never skip, without Chrome (set CLARK_CHROME to its path).
"""
import time
import unittest

from test_report_editor import Base  # noqa: E402
from test_server import chrome  # noqa: E402

WIDTHS = (1400, 900)
GUTTER = 1304                      # px: the page is this wide or wider when the handle has the margin to itself

# Every section: its handle parts, its heading (View: .sec-h; Edit: the Title field) and the card's box.
MEASURE = r"""(() => {
  const box = (e) => { const r = e.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; };
  const out = [];
  document.querySelectorAll('.secs > .sec').forEach((s) => {
    const heads = [...s.querySelectorAll('.sec-h, .sec-title')].filter((h) => h.getBoundingClientRect().width > 0);
    const parts = [...s.querySelectorAll(':scope > .sec-ctl .handle, :scope > .sec-ctl .plus, :scope > .sec-ctl .eye')];
    const ctl = s.querySelector(':scope > .sec-ctl');
    out.push({ id: s.dataset.id, card: box(s), heads: heads.map(box), parts: parts.map(box), ctl: ctl ? box(ctl) : null,
               rest: ctl ? parseFloat(getComputedStyle(ctl).opacity) : null });
  });
  return out;
})()"""

SEATS = r"""(() => { const f = document.querySelector('.frame'); const r = f.getBoundingClientRect(); const cs = getComputedStyle(f);
  return [r.left + parseFloat(cs.paddingLeft), r.left]; })()"""     # [the frame's inner left edge, its outer left edge]


class SectionHandle(Base):
    def at(self, cdp, p, width, scheme):
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, p.sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        p.until(f"window.innerWidth === {width}", "resized")
        time.sleep(.3)                                                                          # let the new rules start their transition ...
        p.until("document.getAnimations().length === 0", "the opacity settled")                # ... and finish it
        return p.js(MEASURE)

    def test_the_handle_sits_in_the_padding_and_rests_at_about_three_quarters(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            # The first time in Edit, the first handle shows at full strength with its hint (#131); a key ends it, as for a person.
            p.until("!!document.querySelector('.sec-ctl.hint') || !!localStorage.getItem('clark.handleHint')", "the first-time hint")
            p.js("document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Shift'}))")
            p.until("!document.querySelector('.sec-ctl.hint')", "the hint has gone")
            for scheme in ("light", "dark"):
                for w in WIDTHS:
                    rows = self.at(cdp, p, w, scheme)
                    inner, outer = p.js(SEATS)
                    for r in rows:
                        where = f"{w} px, {scheme}, {r['id']}"
                        c = r["ctl"]
                        self.assertGreaterEqual(c[0], outer, f"{where}: the handle is inside the card's frame")
                        if w < GUTTER:
                            self.assertAlmostEqual(r["rest"], .75, delta=.05, msg=f"{where}: rests at about .75 below the gutter width")
                        # nothing of the section's own content, only its padding, is under the handle
                        self.assertLessEqual(c[2], r["heads"][0][0], f"{where}: the handle ends before the heading starts")
                        if w <= 900:
                            self.assertGreaterEqual(c[0], r["card"][0], f"{where}: in the card's own left padding")
                        else:
                            self.assertLessEqual(c[2], r["card"][0], f"{where}: in the margin beside the card")
                            self.assertGreaterEqual(c[0], inner - 28, f"{where}: and within the frame's padding")

    def test_the_section_card_is_as_wide_in_view_as_in_edit(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            for scheme in ("light", "dark"):
                for w in WIDTHS:
                    p.view()
                    in_view = {r["id"]: r["card"][::2] for r in self.at(cdp, p, w, scheme)}      # left and right edges
                    p.edit()
                    in_edit = {r["id"]: r["card"][::2] for r in p.js(MEASURE)}
                    self.assertEqual(in_edit, in_view, f"{w} px, {scheme}: the same left edge and width in View and Edit")


if __name__ == "__main__":
    unittest.main()
