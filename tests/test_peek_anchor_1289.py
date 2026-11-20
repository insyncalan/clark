"""Row 1289 (v1.3, the owner 17-11 "smooth peek is perfect"): every peek is flush to the right edge, top on the banner, bottom on the window bottom, and
slides in from the right in 0.5 s with cubic-bezier(.22,1,.36,1), translateX(100%) to 0. This reverses the card of row 1258 (test_peek_frame_1258).
Run: python3 dev/run_tests.py test_peek_anchor_1289   (reads the stylesheet only; the browser frames are listed in the status file)
"""
import re
import unittest

from _paths import ROOT

CSS = (ROOT / "src" / "clark" / "page" / "shell.css").read_text(encoding="utf-8")


def rule(selector):
    m = re.search(r"^" + re.escape(selector) + r" \{([^}]*)\}", CSS, re.M)
    assert m, selector
    return m.group(1)


class Anchor(unittest.TestCase):
    def test_the_frame_is_flush_square_and_has_no_gap(self):
        body = rule(".peek")
        for want in (r"position:\s*fixed", r"top:\s*var\(--topbar\)", r"right:\s*0[;\s]", r"bottom:\s*0[;\s]"):
            self.assertRegex(body, want)
        for no in ("border-radius", "margin"):
            self.assertNotIn(no, body)
        self.assertNotRegex(CSS, r"(?m)^\.peek[^{\n]*\{[^}]*(right:\s*16px|bottom:\s*16px|border-radius:\s*16px)")

    def test_the_tokens_and_the_keyframe(self):
        self.assertRegex(CSS, r":root \{ --peek-dur: 500ms; --peek-ease: cubic-bezier\(\.22, 1, \.36, 1\); \}")
        kf = re.search(r"@keyframes pk-in \{[^\n]*", CSS).group(0)
        self.assertIn("translateX(100%)", kf)
        self.assertNotIn("opacity", kf)

    def test_entry_uses_them_and_m_slide_is_untouched(self):
        self.assertRegex(CSS, r"\.peek:not\(\.leaving\) \{ animation: pk-in var\(--peek-dur\) var\(--peek-ease\) 1; \}")
        self.assertIn("@keyframes m-slide { from { opacity: 0; transform: translateX(24px); } }", CSS)

    def test_exit_stays_fast_and_reduced_motion_is_a_fade(self):
        self.assertRegex(CSS, r"\.peek\.leaving \{[^}]*pk-out var\(--dur-instant\)")
        self.assertRegex(CSS, r"prefers-reduced-motion: reduce\) \{ \.peek\.leaving \{ display: none; \} \.peek:not\(\.leaving\) \{ animation: pk-fade var\(--dur-instant\)")
        self.assertRegex(CSS, r"@keyframes pk-fade \{ from \{ opacity: 0; \} \}")

    def test_below_1000_the_peek_is_full_width_without_the_gap(self):
        self.assertRegex(CSS, r"@media \(max-width: 999px\) \{ \.peek:not\(\.hpk\) \{ width: 100% !important; \}")


if __name__ == "__main__":
    unittest.main()
