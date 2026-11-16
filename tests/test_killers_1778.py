"""Killer for PR 1778 (row 1230): a milestone that is not for the client must not count in Configure's "of N" (dashRows keeps `r.clientVisible`).
Run inside tests/: PYTHONPATH=../src:../vendor:. python3 -m unittest test_killers_1778. Widths 1400 and 900 only.
"""
import unittest

import test_ms_configure_1230 as base
from _demo import USER
from test_glance_page import tearDownModule  # noqa: F401
from test_server import chrome


class Killers(base.Configure):
    def test_a_milestone_not_for_the_client_is_not_counted_in_configure(self):
        with self.store.step("dashboard", USER) as st:
            st.create("milestones", {"project": "ABC", "name": "Internal only", "baseline_date": "2030-09-01", "source": "demo", "client_visible": 0})
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                base.put_ms_view(self, None)
                p = self.show(cdp, width)
                p.until(f"!!document.querySelector('{base.ROWS}')", "milestones")
                self.edit(p)
                self.open_panel(p)
                self.assertEqual(p.js("document.querySelector('[data-uc-of]').textContent"), "of 7")


# keep only the new test from the inherited class
for _n in [n for n in dir(Killers) if n.startswith("test_") and n not in Killers.__dict__]:
    setattr(Killers, _n, None)

if __name__ == "__main__":
    unittest.main()
