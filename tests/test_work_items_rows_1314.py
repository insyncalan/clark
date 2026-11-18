"""Row 1314 (rows part): the Priority tag in the Work items list rows is a round pill.

Run: python3 dev/run_tests.py test_work_items_rows_1314
"""
import json
import re
import unittest

from _paths import SRC
import test_tpl_workitems as T

SHELL_CSS = (SRC / "clark" / "page" / "shell.css").read_text(encoding="utf-8")


def last_rule(css, selector):
    found = re.findall(r"(?:^|\n)" + re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert found, selector
    return found[-1]


class SourceRules(unittest.TestCase):
    def test_the_last_priority_pill_rule_rounds_it_fully(self):
        self.assertIn("border-radius: var(--radius-pill)", last_rule(SHELL_CSS, ".wil-pr"))


class InThePage(T.InThePage):
    def test_the_priority_tag_is_a_pill_not_a_rectangle(self):
        ref = self.add({"mode": "all", "columns": ["id", "owner", "due", "priority"], "owner": ["Pat Demo", "Lee Demo"]})
        with T.chrome() as cdp:
            p = self.show(cdp, 1400)
            sec = f'[data-id="{ref}"]'
            p.edit()
            p.until(f"!!document.querySelector('{sec} .wil-table .wil-pr')", "drew")
            got = json.loads(p.js(f"JSON.stringify((() => {{ const e = document.querySelector('{sec} .wil-table .wil-pr'); const s = getComputedStyle(e); return [parseFloat(s.borderTopLeftRadius), e.getBoundingClientRect().height]; }})())"))
            self.assertGreaterEqual(got[0], got[1] / 2, got)


if __name__ == "__main__":
    unittest.main()
