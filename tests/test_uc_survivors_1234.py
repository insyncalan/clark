"""Row 1234: tests that kill the mutants the three row 1234 test files let live.

U2 (the row height measured from an open row), U3 (a wrong --ucrow-h after the first render, hidden by the resize that
the row height test fires), U5 (the Enter key no longer opens a bar), H1 (the dash loses its muted colour).

Run: python3 dev/run_tests.py test_uc_survivors_1234
Widths 1400 and 900 px only. Fictional data.
"""
import tempfile
import unittest

from test_commit_dash_1234 import ROW2
from test_commitment_page import Flags, tearDownModule  # noqa: F401
from test_server import chrome
import test_uc_rowh_1234 as rowh


class RowHeightAfterARowOpens(rowh.Browser):
    def test_the_box_stays_n_closed_rows_tall_after_the_first_row_opens(self):
        for width in (1400, 900):
            with self.subTest(width=width), tempfile.TemporaryDirectory() as tmp, rowh.chrome() as cdp:
                pub, text = rowh.made({"n": 3, "scroll": True, "tracker": "top"})
                sid = self.draw(cdp, text, tmp, width)
                closed = cdp.js("document.querySelector('.uc .ucrows > .ucrow').getBoundingClientRect().height", sid)
                cdp.js("document.querySelector('.uc .ucrows > .ucrow .ucbar').click()", sid)
                self.assertTrue(rowh.wait(lambda: cdp.js("!!document.querySelector('.uc .ucrows > .ucrow .ucdetail')", sid)))
                box = cdp.js("document.querySelector('.uc .ucrows').getBoundingClientRect().height", sid)
                self.assertAlmostEqual(box, 3 * closed, delta=1, msg=f"n=3 closed rows are {closed} px each, the box is {box}")


class Bar(Flags):
    def test_enter_and_space_on_a_bar_open_and_close_it(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                bar = "document.querySelector('.ucrow .ucbar')"
                for key, then in (("Enter", "true"), (" ", "false")):
                    p.js(f"{bar}.dispatchEvent(new KeyboardEvent('keydown', {{key: {key!r}, bubbles: true, cancelable: true}}))")
                    p.until(f"{bar}.getAttribute('aria-expanded') === '{then}'", f"{key!r} made aria-expanded {then}")

    def test_the_dash_is_in_the_muted_colour_not_the_title_colour(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                dash = p.js(f"getComputedStyle(document.querySelector('{ROW2} [data-commit-none]')).color")
                muted = p.js("getComputedStyle(document.querySelector('.ucrow .uchead, .uc .ucsteps')).color")
                title = p.js("getComputedStyle(document.querySelector('.ucrow .uctitle')).color")
                self.assertNotEqual(muted, title, "the check can tell muted from title")
                self.assertEqual(dash, muted)

    def test_the_open_count_is_a_pill_badge_dark_in_light_and_light_in_dark(self):
        """Row 1234-A: n>0 draws the digit as a 24px pill (radius 12px, caption size, medium weight) in --heading with --surface text, contrast >= 4.5 measured here; n=0 has no badge; the text stays the one string stepsWord(n)."""
        probe = """(() => {
          const rgb = (c) => c.match(/[\\d.]+/g).slice(0, 3).map(Number);
          const lum = ([r, g, b]) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
          const ratio = (a, b) => { const x = lum(rgb(a)), y = lum(rgb(b)); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
          const tok = (n) => { const e = document.createElement('i'); e.style.color = `var(${n})`; document.body.append(e); const c = getComputedStyle(e).color; e.remove(); return c; };
          const medium = (() => { const e = document.createElement('b'); e.style.fontWeight = 'var(--weight-medium)'; document.body.append(e); const w = getComputedStyle(e).fontWeight; e.remove(); return w; })();
          const all = [...document.querySelectorAll('.ucrow .ucsteps')];
          const withB = all.filter((e) => e.querySelector('.ucn-b')), without = all.filter((e) => !e.querySelector('.ucn-b'));
          const b = withB[0] && withB[0].querySelector('.ucn-b'), cs = b && getComputedStyle(b), r = b && b.getBoundingClientRect();
          return { text: all.map((e) => e.textContent), noBadgeText: without.map((e) => e.textContent), some: withB.length,
                   fill: cs && cs.backgroundColor, ink: cs && cs.color, heading: tok('--heading'), surface: tok('--surface'), ratio: cs && ratio(cs.color, cs.backgroundColor),
                   h: r && r.height, w: r && r.width, radius: cs && cs.borderTopLeftRadius, size: cs && cs.fontSize, weight: cs && cs.fontWeight, medium };
        })()"""
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark), chrome() as cdp:
                    p = self.show(cdp, width)
                    if dark:
                        p.js("document.documentElement.dataset.theme = 'dark'")
                    got = p.js(probe)
                    self.assertGreaterEqual(got["some"], 1, "a row with open steps has the badge")
                    self.assertTrue(all(__import__("re").fullmatch(r"\d+ next steps?|No open steps", t) for t in got["text"]), got["text"])
                    self.assertTrue(all(t == "No open steps" for t in got["noBadgeText"]), "n=0 is plain text, no badge")
                    self.assertEqual((got["fill"], got["ink"]), (got["heading"], got["surface"]))
                    self.assertGreaterEqual(got["ratio"], 4.5, f"digit contrast {got['ratio']} (measured in the browser)")
                    self.assertGreaterEqual(got["h"], 24)
                    self.assertGreaterEqual(got["w"], 24)
                    self.assertEqual((got["radius"], got["size"], got["weight"]), ("12px", "13px", got["medium"]))
                    self.assertEqual(got["heading"] != got["surface"], True)


if __name__ == "__main__":
    unittest.main()
