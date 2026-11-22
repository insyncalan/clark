"""Row 1311: the Dashboard keeps .band on every other visible section without a reload (the wiring in Dashboard.jsx, not the pure function).

Run: python3 dev/run_tests.py test_band_wiring_1311

Real dashboard (the test fixture: a summary, three full sections, one pair), served by the test server, at 1400 and 900 px. Three wires, each with its own check:
- on render: bands are on when the sections first draw (nothing else has touched a class yet);
- on a class change: a section hidden by toggling is-hidden (no re-render) re-bands the rest, and shown again puts them back;
- on a type change: a section that becomes the summary (data-type) is picked up; no address or history is touched.
"""
import json
import unittest

from clark import page
from test_report_editor import Base, tearDownModule  # noqa: F401
from test_server import chrome

BANDED = "[...document.querySelectorAll('.secs > .sec')].map(e => e.classList.contains('band'))"
SHOWN = "[...document.querySelectorAll('.secs > .sec')].map(e => !e.classList.contains('is-hidden'))"


def expect(shown, summary=(), right=()):
    """Banded flags per section, worked out here from the rule: hidden and summary ones skipped and not counted; the right half of a pair takes its left half's flag."""
    out, n = [], 0
    for i, s in enumerate(shown):
        if not s or i in summary:
            out.append(False)
        elif i in right:
            out.append(out[-1])
        else:
            out.append(n % 2 == 0)
            n += 1
    return out


SUMMARY = "[...document.querySelectorAll('.secs > .sec')].flatMap((e, i) => e.dataset.type === 'current' || (e.dataset.type === 'text' && ['Header', 'Current state'].includes(e.querySelector('.sec-h').textContent.trim())) ? [i] : [])"
RIGHT = "[...document.querySelectorAll('.secs > .sec')].flatMap((e, i) => e.classList.contains('slot-right') ? [i] : [])"


class BandWiring(Base):
    theme = "prototype-2.0"      # Classic: the bands are Classic only

    def setUp(self):
        super().setUp()
        self.s.close()
        from _real_server import real_server
        self.s = real_server(self.store.path, self.store.data_for, page_html=lambda: page.page_html(branding=page.NO_BRAND, theme=self.theme), seam=self.seam)
        self.addCleanup(self.s.close)

    def show(self, cdp, width):
        p = self.visit(cdp)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        p.until("document.querySelectorAll('.secs > .sec').length >= 4", "the sections drew")
        return p

    def test_bands_are_on_when_the_sections_first_draw(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                self.assertTrue(any(p.js(BANDED)), "some section is banded")
                self.assertEqual(p.js(BANDED), expect(p.js(SHOWN), p.js(SUMMARY), p.js(RIGHT)))

    def test_a_class_change_inside_secs_re_bands_without_a_reload(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                p.js("window.marker = 'same page'")
                before = p.js(BANDED)
                summary, right = p.js(SUMMARY), p.js(RIGHT)
                p.js("document.querySelectorAll('.secs > .sec')[2].classList.add('is-hidden')")
                p.until(f"JSON.stringify({BANDED}) === JSON.stringify({json.dumps(expect([i != 2 for i in range(len(before))], summary, right))})", "the band follows the hidden section")
                p.js("document.querySelectorAll('.secs > .sec')[2].classList.remove('is-hidden')")
                p.until(f"JSON.stringify({BANDED}) === JSON.stringify({json.dumps(before)})", "shown again, the bands are back")
                self.assertEqual(p.js("window.marker"), "same page", "no reload")

    def test_the_default_text_section_titled_current_state_is_the_summary(self):
        """ruling 19-11: the default summary is a TEXT section titled Current state (item 1188); it is never banded and does not count."""
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                n, right = len(p.js(BANDED)), p.js(RIGHT)
                p.js("(() => { const e = document.querySelectorAll('.secs > .sec')[0]; e.dataset.type = 'text'; e.querySelector('.sec-h').textContent = 'Current state'; })()")
                S = "[...document.querySelectorAll('.secs > .sec')].flatMap((e, i) => e.dataset.type === 'text' && e.querySelector('.sec-h').textContent.trim() === 'Current state' ? [i] : [])"
                self.assertEqual(p.js(S), [0])
                want = expect([True] * n, p.js(S), right)
                p.until(f"JSON.stringify({BANDED}) === JSON.stringify({json.dumps(want)})", "the Current state text section is left out of the bands")
                self.assertFalse(p.js("document.querySelectorAll('.secs > .sec')[0].classList.contains('band')"))

    def test_a_type_change_re_bands(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                n, right = len(p.js(BANDED)), p.js(RIGHT)
                p.js("document.querySelectorAll('.secs > .sec')[0].dataset.type = 'current'")
                want = expect([True] * n, p.js(SUMMARY), right)
                p.until(f"JSON.stringify({BANDED}) === JSON.stringify({json.dumps(want)})", "the type change re-banded")

class CardsKeepsItsDom(BandWiring):
    theme = None

    def test_the_default_text_section_titled_current_state_is_the_summary(self):
        self.skipTest("Cards is never banded (ruling 19-11)")

    def test_cards_is_never_banded(self):
        with chrome() as cdp:
            p = self.show(cdp, 1400)
            self.assertFalse(any(p.js(BANDED)), "Cards draws no band class")
            p.js("document.querySelectorAll('.secs > .sec')[2].classList.add('is-hidden')")
            self.assertFalse(any(p.js(BANDED)))

    test_bands_are_on_when_the_sections_first_draw = test_a_class_change_inside_secs_re_bands_without_a_reload = test_a_type_change_re_bands = None


if __name__ == "__main__":
    unittest.main()
