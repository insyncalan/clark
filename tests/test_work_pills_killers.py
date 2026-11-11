"""Row 1059 mutation killers: the pills the published file keeps (visible), and the Help wording.
Widths 1400 and 900 only.

Run: python3 dev/run_tests.py test_work_pills_killers
"""
import json
import unittest

from _paths import ROOT, SRC  # noqa: F401
import test_client_page_filters as _pub  # noqa: E402
import test_filter_line_page as _line  # noqa: E402
from test_server import chrome, wait  # noqa: E402

HELP = SRC / "clark" / "page" / "src" / "help" / "helpContent.json"


class PublishedPills(_pub.ClientPageFilters):
    def test_the_published_file_still_draws_both_sets_of_pills_at_1400_and_900_px(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.go(cdp, width, "light")
                seen = cdp.js("""[...document.querySelectorAll('.wbar [data-type], .wbar [data-show]')].map(b => { const r = b.getBoundingClientRect();
                    return [b.dataset.type || b.dataset.show, r.width > 0 && r.height > 0]; })""", sid)
                self.assertEqual([k for k, _ in seen], ["all", "action", "risk", "decision", "open", "closed", "all"])
                self.assertTrue(all(v for _, v in seen), f"all drawn: {seen}")


for _name in dir(_pub.ClientPageFilters):
    if _name.startswith("test_") and _name not in PublishedPills.__dict__:
        setattr(PublishedPills, _name, None)


class AppBar(_line.Line):
    def test_the_app_draws_no_bar_at_all_now_that_the_archived_pill_is_gone_at_1400_and_900_px(self):
        s = self.serve()
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.load(cdp, s.port, width=width)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.fline-wrap')", sid)), "the filter line is there")
                self.assertEqual(cdp.js("document.querySelectorAll('#work .wbar, #showArchived, .arch-pill').length", sid), 0)


for _name in dir(_line.Line):
    if _name.startswith("test_") and _name not in AppBar.__dict__:
        setattr(AppBar, _name, None)


class HelpWords(unittest.TestCase):
    def test_help_names_the_line_words_and_not_the_pills(self):
        text = HELP.read_text(encoding="utf-8")
        for need in ("On the filter line, write type: to pick the type, and is:open or is:closed (or status:Open or status:Closed) to pick open or closed items.",
                     "Type is:open or is:closed on the filter line to say which items to list.",
                     "From the top: the saved views with the **Table** and **Board** icons"):
            self.assertIn(need, text)
        for gone in ("The first switch picks the type", "The second picks **Open**", "Choose **Open**, **Closed** or **All**",
                     "the type switch; **Open**", "the type switch;"):
            self.assertNotIn(gone, text)
        json.loads(text)


if __name__ == "__main__":
    unittest.main()
