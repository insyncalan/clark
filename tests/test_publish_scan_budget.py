"""#112: the leak scan has a budget, and going over it is a refusal (never a hang, never an exception that escapes, never a pass).

Run: python3 dev/run_tests.py test_publish_scan_budget
The scan counts its steps (publish.Work). A text that costs more than publish.SCAN_BUDGET is not read to the end: outside_addresses
returns one finding, check_brand and the publish step raise PublishError, and to_client.check_copy refuses. The real page costs
about 14,700 steps; the budget for the page's own length is kept at least 20 times that (it was 50 until the page grew).
"""
import unittest

from _paths import ROOT, SRC  # noqa: F401

from clark import publish, to_client  # noqa: E402
from test_publish import ICON_LINK, TOUCH_LINK  # noqa: E402,F401
from test_publish_scan_gaps import real  # noqa: E402

HEADROOM = 20


def measure(call, text):
    """The steps `call(text)` spends, counted on a Work that never stops."""
    box = []

    class Counting(publish.Work):
        def __init__(self, limit=None, size=0):
            super().__init__(10 ** 12)
            box.append(self)

    keep, publish.Work = publish.Work, Counting
    try:
        call(text)
    finally:
        publish.Work = keep
    return max(w.n for w in box)


# shapes that cost more than the budget (each far under the 5 MB a file may have)
# (the budget grows with the text, so only a shape that costs more than about one step per character is over it)
OVER = {
    "quote then tag starts": '<a b="' + "<a" * 300_000 + '">',
    "quote then tag starts, single quote": "<a b='" + "<a" * 500_000 + "'>",
    "quote then angle brackets": '<a b="' + "<" * 800_000 + '">',
}
# ordinary text that costs a lot of steps but only a few per character: it must pass
RULE = (".card-%d > .item:hover, .card-%d .label::after{background:#ffffff;color:rgb(10,20,30);margin:0 auto;padding:4px 8px;"
        "border:1px solid #cccccc;font:12px/1.4 sans-serif;transition:opacity .2s ease,transform .2s ease}\n")
BIG_CSS = "<style>" + "".join(RULE % (i, i) for i in range(6500)) + "</style>"
BIG_HTML = '<div class="a b"><span id="x">text</span><br></div>' * 60_000


class Budget(unittest.TestCase):
    def test_the_real_page_stays_far_under_the_budget(self):
        page = real()
        for name, call in (("outside_addresses", publish.outside_addresses), ("check_brand", publish.check_brand)):
            spent = measure(call, page)
            limit = publish.Work(size=len(page)).limit                      # the budget for a page this long
            self.assertLess(spent * HEADROOM, limit, f"{name} spends {spent} steps of {limit}")

    def test_the_three_icon_links_and_a_repeat_stay_under_the_budget(self):
        page = real()
        self.assertEqual(publish.outside_addresses(page), [])
        self.assertLess(measure(publish.has_other_links, page) * HEADROOM, publish.Work(size=len(page)).limit)

    def test_a_text_over_the_budget_is_a_finding_not_a_pass_or_an_exception(self):
        for name, text in OVER.items():
            with self.subTest(name):
                self.assertGreater(measure(publish.outside_addresses, text), publish.SCAN_BUDGET)      # it really is over
                found = publish.outside_addresses(text)
                self.assertEqual(found, [publish.TOO_BIG_FOUND])

    def test_check_copy_refuses_a_text_over_the_budget(self):
        for name, text in OVER.items():
            with self.subTest(name):
                found = to_client.check_copy(text.encode("utf-8"), markers=())
                self.assertIn(publish.TOO_BIG_FOUND, " ".join(map(str, found)))

    def test_check_brand_raises_publish_error_over_the_budget(self):
        keep = publish.SCAN_BUDGET, publish.SCAN_PER_CHAR
        publish.SCAN_BUDGET, publish.SCAN_PER_CHAR = 1000, 0                    # check_brand's own cost per character is low
        try:
            with self.assertRaises(publish.PublishError) as caught:
                publish.check_brand("<style>" + "a{b:url(data:x)}" * 5000 + "</style>")
        finally:
            publish.SCAN_BUDGET, publish.SCAN_PER_CHAR = keep
        self.assertIn("too long or too tangled", str(caught.exception))

    def test_a_lowered_budget_refuses_the_real_page(self):
        page = real()
        keep = publish.SCAN_BUDGET, publish.SCAN_PER_CHAR
        publish.SCAN_BUDGET, publish.SCAN_PER_CHAR = 100, 0
        try:
            self.assertEqual(publish.outside_addresses(page), [publish.TOO_BIG_FOUND])
            with self.assertRaises(publish.PublishError):
                publish.check_brand(page)
        finally:
            publish.SCAN_BUDGET, publish.SCAN_PER_CHAR = keep

    def test_a_large_ordinary_stylesheet_passes(self):
        self.assertGreater(len(BIG_CSS), 1_000_000)
        self.assertGreater(BIG_CSS.count("{"), 6000)
        self.assertGreater(measure(publish.outside_addresses, BIG_CSS), publish.SCAN_BUDGET)    # too dear for a flat budget
        self.assertEqual(publish.outside_addresses(BIG_CSS), [])
        publish.check_brand(BIG_CSS)                                                               # does not raise

    def test_a_large_tag_dense_page_passes(self):
        self.assertGreater(measure(publish.outside_addresses, BIG_HTML), publish.SCAN_BUDGET)
        self.assertEqual(publish.outside_addresses(BIG_HTML), [])

    def test_the_budget_has_a_ceiling_and_the_hostile_shapes_refuse_quickly(self):
        import time
        self.assertLessEqual(publish.Work(size=10 ** 9).limit, max(publish.SCAN_CEILING, publish.SCAN_BUDGET))
        for text in ('<a b="' + "<a" * 2_500_000 + '">', "<a b='" + "<a" * 1_000_000 + "'>",
                     '<a b="' + "<" * 5_000_000 + '">' + "x" * 300_000):
            started = time.process_time()
            self.assertEqual(publish.outside_addresses(text), [publish.TOO_BIG_FOUND])
            self.assertLess(time.process_time() - started, 5)

    def test_the_message_is_plain_words(self):
        msg = publish.TOO_BIG_FOUND
        self.assertFalse(msg.lower().startswith("clark"))
        for word in ("budget", "scan", "exception", "ScanTooBig", "Work"):
            self.assertNotIn(word, msg)

    def test_a_clean_text_under_the_budget_still_passes(self):
        self.assertEqual(publish.outside_addresses("<p>hello</p>" * 100), [])


if __name__ == "__main__":
    unittest.main()
