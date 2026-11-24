"""Row 1256 (PR B): a Risk's and an Issue's Details are drawn like an Action's (approved mockups peek-risk and peek-issue), and keep the Use case row:
Workstream, Milestone, Use case, Raised (read only, with its hint), then the Client visible line. Modelled on test_peek_action_1181.
Run: CLARK_CHROME=/usr/local/bin/creaite-chrome python3 dev/run_tests.py test_peek_details_1256
Demo project, Edit mode: TUL-007 is a risk, TUL-010 an issue.
"""
import unittest

from _paths import ROOT

import test_peek_latest  # noqa: E402
from test_work_filters import click  # noqa: E402
from test_server import wait  # noqa: E402
from test_peek_action_1181 import ROWS_JS  # noqa: E402
from test_server import chrome  # noqa: E402

RISK, ISSUE = "TUL-007", "TUL-010"


class Details(test_peek_latest.Browser):
    def open_details(self, cdp, sid):
        if cdp.js("document.querySelector('[data-pk-details]').getAttribute('aria-expanded')", sid) != "true":
            click(cdp, sid, "[data-pk-details]")
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-pk-details-rows]')", sid)))

    def test_risk_and_issue_rows_are_workstream_milestone_use_case_raised_then_client_visible(self):
        for ref in (RISK, ISSUE):
            for width in (1400, 900):
                with self.subTest(ref=ref, width=width), chrome() as cdp:
                    sent, sid = self.load(cdp, width, ref)
                    self.open_details(cdp, sid)
                    rows = cdp.js(ROWS_JS, sid)
                    for gone in ("Type", "Client Message", "Last reviewed"):
                        self.assertNotIn(gone, rows, f"{gone} is not a row here")
                    self.assertEqual(rows[:4], ["Workstream", "Milestone", "Use case", "Raised"], rows)
                    client = cdp.js("(() => { const c = document.querySelector('[data-pk-details-rows] [data-pk-client-row]'); const r = [...document.querySelectorAll('[data-pk-details-rows] .pk-row')]; return c ? r.indexOf(c) : -1; })()", sid)
                    self.assertEqual(client, 4, "the Client visible line follows Raised")

    def test_raised_is_read_only_with_its_hint(self):
        for ref in (RISK, ISSUE):
            with self.subTest(ref=ref), chrome() as cdp:
                sent, sid = self.load(cdp, 1400, ref)
                self.open_details(cdp, sid)
                row = cdp.js("(() => { const d = [...document.querySelectorAll('[data-pk-details-rows] .pk-row')].find(r => /^Raised/.test(r.querySelector('dt').textContent.trim()));"
                             " return d ? { text: d.innerText.replace(/\\s+/g, ' '), controls: d.querySelectorAll('button, input, [contenteditable=true]').length } : null; })()", sid)
                self.assertIsNotNone(row, "a Raised row")
                self.assertIn("set when it was raised", row["text"])
                self.assertEqual(row["controls"], 0, "read only")


class Source(unittest.TestCase):
    def test_peek_draws_the_action_body_for_risks_and_issues(self):
        src = (ROOT / "src/clark/page/src/components/Peek.jsx").read_text(encoding="utf-8")
        self.assertIn('row.kind === "risk" || row.kind === "issue"', src)


if __name__ == "__main__":
    unittest.main()
