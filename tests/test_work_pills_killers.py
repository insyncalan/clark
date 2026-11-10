"""Row 1059 mutation killers: the pills the published file keeps (visible), and the Help wording.
Widths 1400 and 900 only.

Run: python3 dev/run_tests.py test_work_pills_killers
"""
import json
import unittest

from _paths import ROOT, SRC  # noqa: F401
import test_client_page_filters as _pub  # noqa: E402
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


class HelpWords(unittest.TestCase):
    def test_help_names_the_line_words_and_not_the_pills(self):
        text = HELP.read_text(encoding="utf-8")
        for need in ("type:action, type:risk or type:decision, and is:closed or is:open.",
                     "Type is:closed in the filter line to list the closed ones.",
                     "From the top: the saved views with the **Table** and **Board** icons"):
            self.assertIn(need, text)
        for gone in ("The first switch picks the type", "The second picks **Open**", "Choose **Open**, **Closed** or **All**",
                     "the type switch; **Open**", "the type switch;"):
            self.assertNotIn(gone, text)
        json.loads(text)


if __name__ == "__main__":
    unittest.main()
