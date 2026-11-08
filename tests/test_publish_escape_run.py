"""#871: a run of backslash escapes is read in one step by check_brand's style reading, with the same result as one at a time.

Run: python3 dev/run_tests.py test_publish_escape_run
The reference is the one-at-a-time reading (the old pattern, and the backslash walk cut to one escape per step); random style
text made of the awkward characters must read the same, and a long run must cost a few steps, not one per escape.
"""
import random
import re
import unittest

from _paths import ROOT, SRC  # noqa: F401

from clark import publish  # noqa: E402

OLD_ESCAPE = re.compile(r"\\(?:([0-9A-Fa-f]{1,6})(?:\r\n|[ \t\n\r\f])?|(\r\n|[\n\r\f])|(.))", re.S)
ONE_PAIR = re.compile(r"\\.?", re.S)
ALPHABET = ["\\", "\\", "\\", '"', "'", "a", "6", "2", "5", " ", "/", "*", "(", ")", "u", "r", "l", "\n", "\r\n", "7", "c"]


def old_escape(m):
    if m.group(1):
        n = int(m.group(1), 16)
        c = chr(n) if 0 < n <= 0x10FFFF and not 0xD800 <= n <= 0xDFFF else "\ufffd"
        return m.group(0) if c in publish._NOT_DECODED else c
    if m.group(2):
        return "\\\n"
    return m.group(0) if m.group(3) in publish._NOT_DECODED else m.group(3)


def merged(starts, ends):
    out = []
    for s, e in zip(starts, ends):
        if out and out[-1][1] >= s:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return out


class Counting:
    def __init__(self, pattern):
        self.pattern, self.calls = pattern, 0

    def match(self, *args):
        self.calls += 1
        return self.pattern.match(*args)


class EscapeRunTests(unittest.TestCase):
    def texts(self, n=3000):
        rng = random.Random(871)
        for _ in range(n):
            yield "".join(rng.choice(ALPHABET) for _ in range(rng.randint(0, 40)))

    def test_css_plain_reads_as_one_at_a_time(self):
        for text in self.texts():
            for gap in (" ", ""):
                typed = publish._without_comments(text, gap)
                self.assertEqual(publish.css_plain(text, gap), OLD_ESCAPE.sub(old_escape, typed), repr(text))

    def test_comment_walk_reads_as_one_at_a_time(self):
        for text in self.texts():
            for gap in (" ", ""):
                fast = publish._without_comments(text, gap)
                saved = publish._BACKSLASH_RUN
                publish._BACKSLASH_RUN = ONE_PAIR
                try:
                    slow = publish._without_comments(text, gap)
                finally:
                    publish._BACKSLASH_RUN = saved
                self.assertEqual(fast, slow, repr(text))

    def test_escape_places_cover_the_same_text(self):
        for text in self.texts():
            plain = publish.css_plain(text)
            typed = publish._without_comments(text)
            starts, ends, shift = [], [], 0
            for m in OLD_ESCAPE.finditer(typed):
                put = len(old_escape(m))
                starts.append(m.start() + shift)
                ends.append(m.start() + shift + put)
                shift += put - (m.end() - m.start())
            want = None if len(typed) + shift != len(plain) else (starts, ends)
            got = publish._escape_places(text, plain)
            if want is None:
                self.assertIsNone(got, repr(text))
            else:
                self.assertEqual(merged(*got), merged(*want), repr(text))

    def test_a_long_run_costs_a_few_steps(self):
        css = "<style>" + "\\\\" * 100000 + "</style>"
        counter = Counting(publish._BACKSLASH_RUN)
        saved = publish._BACKSLASH_RUN
        publish._BACKSLASH_RUN = counter
        try:
            publish.check_brand(css)
        finally:
            publish._BACKSLASH_RUN = saved
        self.assertGreater(counter.calls, 0)
        self.assertLess(counter.calls, 20)

    def test_hostile_text_is_still_refused(self):
        for bad in ("\\\\\\\\ @\\69mport url(x)", '\\"\\"\\\\ background:\\75rl(http://x.test/a.png)'):
            with self.assertRaises(publish.PublishError):
                publish.check_brand("<style>.a{b:%s}</style>" % bad)


if __name__ == "__main__":
    unittest.main()
