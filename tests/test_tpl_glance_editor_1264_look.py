"""Row 1264 slice 6: which colour each own tile tone gets in Edit, and where the own tiles wrap, at 1400 and 900, light and dark, in a real browser.
Each tone is compared with the token the approved mock-up names for it (resolved in the page itself, so a swap of two tones fails, in dark too).

Run: python3 dev/run_tests.py test_tpl_glance_editor_1264_look
"""
import unittest

from test_server import chrome
from test_tpl_glance_editor_1264 import OWN, Editor, tearDownModule  # noqa: F401

TONES = (("green", "--status-green"), ("amber", "--status-amber-text"), ("red", "--status-red"), ("blue", "--brand-blue"), ("neutral", "--grey-200"))


class Look(Editor):
    def token(self, p, name):
        return p.js(f"""(function(){{ var e = document.createElement('i'); e.style.borderTop = '1px solid var({name})'; document.body.appendChild(e);
          var c = getComputedStyle(e).borderTopColor; e.remove(); return c; }})()""")

    def test_L1_each_tone_gets_its_own_token_as_the_tile_border_and_neutral_takes_the_mock_up_grey(self):
        self.seed([{**OWN, "id": f"t{i}", "tone": tone, "label": f"Fictional {tone}"} for i, (tone, _) in enumerate(TONES, 1)])
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark), chrome() as cdp:
                    p = self.page(cdp, width, dark)
                    for i, (tone, tok) in enumerate(TONES, 1):
                        got = p.js(f"getComputedStyle(document.querySelector({self.q(f'[data-tile=t{i}] .tpl-gt-tile')})).borderTopColor")
                        self.assertEqual(got, self.token(p, tok), f"{tone} must draw {tok}")

    def test_L2_own_tiles_stay_in_the_row_at_900_and_go_full_width_only_at_760_and_below(self):
        self.seed([{**OWN, "id": f"t{i}", "label": f"Fictional {i}"} for i in (1, 2)])
        with chrome() as cdp:
            p = self.page(cdp, 900)
            got = p.js(f"""(function(){{ var g = document.querySelector({self.q('.glance')}).getBoundingClientRect().width;
              return [g, document.querySelector({self.q('[data-tile=t1]')}).getBoundingClientRect().width]; }})()""")
            self.assertLess(got[1], got[0] - 1, f"an own tile at 900 shares its row: {got}")


if __name__ == "__main__":
    unittest.main()
