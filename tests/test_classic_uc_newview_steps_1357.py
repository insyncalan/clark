"""Row 1357 items 3 and 7 (Use cases page, Classic only): the + New view button is the brand colour (it was grey), and the Next steps text in the
list is 13 px (it was 14 px). The shared shell rule keeps its 14 px: the dashboard bars and the published list use it too.

Run: python3 dev/run_tests.py test_classic_uc_newview_steps_1357
Chrome at 1400 and 900 px, light and dark (fictional data). Page words: none new.
"""
import re
import unittest

from _paths import SRC
from test_server import chrome

import test_use_cases_list as ucl

PAGE = SRC / "clark" / "page"
SHELL = (PAGE / "shell.css").read_text(encoding="utf-8")
RULES = (SRC / "clark" / "themes" / "prototype-2.0" / "rules.css").read_text(encoding="utf-8")


def rules(css, selector):
    out = []
    for sel, body in re.findall(r"(?m)^([^{}@/\n][^{}\n]*)\{([^}]*)\}", re.sub(r"/\*.*?\*/", "", css, flags=re.S)):
        if selector in [s.strip() for s in sel.split(",")]:
            out.append(body)
    return " ".join(out)


PROBE = """(() => { const g = (s, p) => getComputedStyle(document.querySelector(s))[p];
  const tok = (v) => { const i = document.createElement('i'); i.style.color = v; document.body.appendChild(i); const c = getComputedStyle(i).color; i.remove(); return c; };
  const steps = [...document.querySelectorAll('#usecases .ucl-table .ucsteps')];
  return { vnew: g('#ucl-viewNew', 'color'), brand: tok('var(--brand-blue)'), muted: tok('var(--text-muted)'),
    steps: steps.map((e) => getComputedStyle(e).fontSize), badge: [...document.querySelectorAll('#usecases .ucl-table .ucsteps .ucn-b')].map((e) => getComputedStyle(e).fontSize),
    caption: (() => { const i = document.createElement('i'); i.style.fontSize = 'var(--size-caption)'; document.body.appendChild(i); const c = getComputedStyle(i).fontSize; i.remove(); return c; })() }; })()"""


class Static(unittest.TestCase):
    def test_new_view_is_brand_in_classic_and_hover_stays(self):
        self.assertIn("color: var(--brand-blue)", rules(RULES, "#usecases .vnew"))
        self.assertIn("color: var(--brand-blue)", rules(RULES, "#usecases .vnew:hover"))
        self.assertIn("var(--text-muted)", rules(SHELL, ".vnew"), "the shared button is still grey (Work items and Cards)")

    def test_next_steps_13px_is_classic_only(self):
        self.assertIn("font-size: var(--size-caption)", rules(RULES, ".ucl-table .ucsteps"))
        self.assertIn("font-size: var(--size-small)", rules(SHELL, ".ucsteps"), "the shared rule keeps 14 px (dashboard and published list)")


class App(ucl.Setup):
    THEME = "prototype-2.0"

    def test_at_1400_and_900_in_light_and_dark(self):
        for scheme in ("light", "dark"):
            for width in (1400, 900):
                with self.subTest(scheme=scheme, width=width), chrome() as cdp:
                    p = self.show(cdp, width=width, dark=scheme == "dark")
                    got = p.js(PROBE)
                    self.assertEqual(got["vnew"], got["brand"], f"{scheme} {width}: + New view is --brand-blue")
                    self.assertNotEqual(got["vnew"], got["muted"])
                    self.assertEqual(got["caption"], "13px")
                    self.assertTrue(got["steps"], "the sample has rows")
                    self.assertEqual(got["steps"], ["13px"] * len(got["steps"]), f"{scheme} {width}: Next steps text 13 px")
                    self.assertEqual(set(got["badge"]) <= {"13px"}, True, f"{scheme} {width}: the count badge is 13 px as before")


if __name__ == "__main__":
    unittest.main()
