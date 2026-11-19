"""Row 1311: the Dashboard keeps .band on every other visible section without a reload (the wiring in Dashboard.jsx, not the pure function).

Run: python3 dev/run_tests.py test_band_wiring_1311

Real dashboard (the test fixture: a summary, three full sections, one pair), served by the test server, at 1400 and 900 px. Three wires, each with its own check:
- on render: bands are on when the sections first draw (nothing else has touched a class yet);
- on a class change: a section hidden by toggling is-hidden (no re-render) re-bands the rest, and shown again puts them back;
- on hashchange: a change the observer cannot see (data-type, not class) is picked up when location.hash changes.
"""
import json
import unittest

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


SUMMARY = "[...document.querySelectorAll('.secs > .sec')].flatMap((e, i) => e.dataset.type === 'current' ? [i] : [])"
RIGHT = "[...document.querySelectorAll('.secs > .sec')].flatMap((e, i) => e.classList.contains('slot-right') ? [i] : [])"


class BandWiring(Base):
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

    def test_a_hash_change_re_bands(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                n, right = len(p.js(BANDED)), p.js(RIGHT)
                # data-type is not a class: the observer does not see it. Only the hashchange listener can pick it up.
                p.js("document.querySelectorAll('.secs > .sec')[0].dataset.type = 'current'")
                p.js("location.hash = location.hash + '&x=1'")
                want = expect([True] * n, p.js(SUMMARY), right)
                p.until(f"JSON.stringify({BANDED}) === JSON.stringify({json.dumps(want)})", "the hashchange re-banded")


if __name__ == "__main__":
    unittest.main()
