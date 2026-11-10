"""Row 1089: the brand kit guide opened in Help, in a real browser at 1400 and 900 px (follows test_help_nav_page.py).

Run: python3 dev/run_tests.py test_help_brand_kit_page
"""
import unittest

from _help_shown import shown_content
import test_help_nav_page as nav
from test_report_editor import Base

ID = "bring-in-a-brand-kit"


class BrandKitGuideInHelp(Base):
    in_help = nav.Nav.in_help

    def test_the_guide_opens_and_reads_the_same_at_1400_and_900(self):
        from test_server import chrome
        g = next(x for x in shown_content()["guides"] if x["id"] == ID)
        with chrome() as cdp:
            p = self.in_help(cdp)
            for w in nav.SIZES:
                nav.set_size(cdp, p, w)
                p.js("window.clarkPage.help.open('guide-%s')" % ID)
                p.until("!!document.querySelector('#hp-guide-%s.hp-found')" % ID, f"{w}: the guide opens")
                body = p.js("document.querySelector('#hp-guide-%s').textContent" % ID)
                for word in ("clark-brand.json", "50 files", "16 MB", "24 MB", "5 MB", "sha256", "one folder named by the brand’s id"):
                    self.assertIn(word, body, f"{w}: {word}")
                self.assertEqual(p.js("document.querySelectorAll('#hp-guide-%s li').length" % ID), len(g["steps"]), w)
                self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"), f"{w}: no sideways scroll")


if __name__ == "__main__":
    unittest.main()
