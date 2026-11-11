"""The top bar's profile circle (issue 732), in a real browser against the real page. Chrome is required: these tests fail,
never skip, without it.

Run: python3 dev/run_tests.py test_top_bar_avatar
The profile circle is filled aqua with a navy mark (the prototype's), in light and in dark; the top bar has no "?" Help button (row 899); the bar's items do not
overlap or run past the window at 1400 and 900 px with the bigger circle. Only 1400 and 900 px are tested.
"""
import unittest

from test_inline_67 import size
from test_report_editor import Base
from test_server import chrome

ITEMS = "[...document.querySelectorAll('header.top > *')].filter(e => e.getClientRects().length)"
TOKEN = ("function(t){ var e = document.createElement('i'); e.style.color = 'var(' + t + ')'; document.body.appendChild(e); "
         "var c = getComputedStyle(e).color; e.remove(); return c; }")


def lum(rgb):
    r, g, b = [int(x) for x in rgb[rgb.index("(") + 1:rgb.index(")")].replace("/", ",").split(",")[:3]]
    f = lambda v: (v / 255 / 12.92) if v / 255 <= 0.03928 else (((v / 255) + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


class Avatar(Base):
    def test_the_profile_circle_is_filled_aqua_with_a_navy_mark_in_light_and_dark(self):
        for theme in ("light", "dark"):
            with self.subTest(theme=theme), chrome() as cdp:
                p = self.visit(cdp)
                size(cdp, p, 1400, 700)
                p.js(f"document.documentElement.setAttribute('data-theme', '{theme}')")
                got = p.js("(function(){ var tok = " + TOKEN + ", b = document.querySelector('#profile-btn'), s = getComputedStyle(b);"
                           "return [s.backgroundColor, tok('--brand-cyan'), s.color, tok('--brand-navy'), s.borderRadius, b.getBoundingClientRect().width, "
                           "b.getBoundingClientRect().height, s.borderTopWidth];})()")
                self.assertEqual(got[0], got[1], "the fill is the aqua token")
                self.assertEqual(got[2], got[3], "the mark is the navy token")
                self.assertEqual(got[4:], ["50%", 34, 34, "2px"])
                a, b = sorted((lum(got[0]), lum(got[2])), reverse=True)
                self.assertGreaterEqual((a + 0.05) / (b + 0.05), 4.5, "navy on aqua reads clearly")

    def test_there_is_no_help_circle_beside_the_profile_circle(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            size(cdp, p, 1400, 700)
            self.assertEqual(p.js("document.querySelector('#help-btn')"), None)

    def test_the_bar_has_no_overlap_and_nothing_past_the_window_with_the_bigger_circle(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.visit(cdp)
                size(cdp, p, width, 700)
                got = p.js(f"(function(){{var r=[...{ITEMS}].map(e => [e.className || e.id, e.getBoundingClientRect()]), bad=[];"
                           "for (var i=0;i<r.length;i++){ if (r[i][1].right > document.documentElement.clientWidth + 0.5) bad.push('past ' + r[i][0]);"
                           "for (var j=i+1;j<r.length;j++) if (r[i][1].left < r[j][1].right - 0.5 && r[j][1].left < r[i][1].right - 0.5 && r[i][1].top < r[j][1].bottom - 0.5 && r[j][1].top < r[i][1].bottom - 0.5 && r[i][1].width && r[j][1].width) bad.push(r[i][0] + ' over ' + r[j][0]); }"
                           "return bad;})()")
                self.assertEqual(got, [], f"at {width} px")


if __name__ == "__main__":
    unittest.main()
