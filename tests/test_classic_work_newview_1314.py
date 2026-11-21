"""Row 1314 (Work items + New view, Classic only): the button is the brand blue, as on the Use cases page. The shared shell rule stays grey for Cards.

Run: python3 dev/run_tests.py test_classic_work_newview_1314
Chrome at 1400 and 900 px, light and dark (fictional data). Page words: none new.
"""
import re
import tempfile
import unittest

from clark import page, theme
from _paths import SRC
from _real_server import real_server
from test_server import chrome
from test_work_board_page import Base

SHELL = (SRC / "clark" / "page" / "shell.css").read_text(encoding="utf-8")
RULES = (SRC / "clark" / "themes" / "prototype-2.0" / "rules.css").read_text(encoding="utf-8")


def rules(css, selector):
    out = []
    for sel, body in re.findall(r"(?m)^([^{}@/\n][^{}\n]*)\{([^}]*)\}", re.sub(r"/\*.*?\*/", "", css, flags=re.S)):
        if selector in [s.strip() for s in sel.split(",")]:
            out.append(body)
    return " ".join(out)


PROBE = """(() => { const tok = (v) => { const i = document.createElement('i'); i.style.color = v; document.body.appendChild(i); const c = getComputedStyle(i).color; i.remove(); return c; };
  const n = document.querySelector('#work .vnew');
  return { vnew: n && getComputedStyle(n).color, brand: tok('var(--brand-blue)'), muted: tok('var(--text-muted)') }; })()"""


class Static(unittest.TestCase):
    def test_new_view_is_brand_in_classic_and_hover_stays(self):
        self.assertIn("color: var(--brand-blue)", rules(RULES, "#work .vnew"))
        self.assertIn("color: var(--brand-blue)", rules(RULES, "#work .vnew:hover"))
        self.assertIn("var(--text-muted)", rules(SHELL, ".vnew"), "the shared button is still grey (Cards)")

    def test_cards_stylesheet_has_none_of_it(self):
        self.assertNotIn("#work .vnew", SHELL)


class Browser(Base):
    def setUp(self):
        super().setUp()
        self.s.close()
        css = theme.css("prototype-2.0")
        self.s = real_server(self.store.path, self.store.data_for,
                             page_html=lambda: page.layer_theme(page.page_html(tempfile.mkdtemp()), css), seam=lambda real, which: real)
        self.addCleanup(self.s.close)

    def test_at_1400_and_900_in_light_and_dark(self):
        for scheme in ("light", "dark"):
            for width in (1400, 900):
                with self.subTest(scheme=scheme, width=width), chrome() as cdp:
                    sid = self.visit(cdp, width=width)
                    cdp.js("document.documentElement.dataset.theme = %r" % scheme, sid)
                    got = cdp.js(PROBE, sid)
                    self.assertIsNotNone(got["vnew"], "the + New view button is on the page")
                    self.assertEqual(got["vnew"], got["brand"], f"{scheme} {width}: + New view is --brand-blue")
                    self.assertNotEqual(got["vnew"], got["muted"])


if __name__ == "__main__":
    unittest.main()
