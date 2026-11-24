"""Row 1466 AP1 (ticket correction of 23-11-2026): the row label is exactly "Client Message" (capital M, never "Client wording") in every place the
build draws the Client Message row, in View and Edit, at 1400 and 900, in the light and the dark theme. No new row is built: a place that draws no
Client Message row today (a decision in View, a work item in Edit) stays without it. The other acceptance points are in test_client_message_label_1466.
Run: CLARK_CHROME=/usr/local/bin/creaite-chrome python3 dev/run_tests.py test_client_message_1466
"""
import tempfile
import unittest
from pathlib import Path

import test_peek_ruled_1077 as base  # noqa: E402
import test_publish as tp  # noqa: E402
from clark import page  # noqa: E402
from test_server import chrome, wait  # noqa: E402

LABELS = "[...document.querySelectorAll('#peek .pk-fields dt')].map(d => d.textContent.trim())"
DARK = "document.documentElement.dataset.theme = 'dark'"


class Places(base.Peeks):
    def test_the_label_is_client_message_in_every_place_the_row_is_drawn(self):
        decision = self.store.read("decisions")[0]["id"]
        milestone = self.store.read("milestones")[0]["id"]
        drawn = (("view", milestone, "milestone"), ("edit", milestone, "milestone"), ("edit", decision, "item"))       # Peek.jsx:192 and :135, MilestonePeek.jsx:270
        none = (("view", decision, "item"), ("view", "TUL-A-001", "item"), ("edit", "TUL-A-001", "item"))                # no such row today
        for width in (1400, 900):
            for dark in (False, True):
                for mode, ref, kind in drawn + none:
                    with self.subTest(width=width, dark=dark, mode=mode, ref=ref), chrome() as cdp:
                        sid = self.dashboard_in_view(cdp, width, self.store, self.code)
                        if dark:
                            cdp.js(DARK, sid)
                        if mode == "edit":
                            self.to_edit(cdp, sid)
                        self.open_peek(cdp, sid, ref, kind)
                        labels = self.labels(cdp, sid)
                        if (mode, ref, kind) in drawn:
                            self.assertEqual([l for l in labels if l.lower() == "client message"], ["Client Message"], labels)
                        else:
                            self.assertEqual([l for l in labels if "client" in l.lower()], [], labels)
                        self.assertNotRegex(cdp.js("document.querySelector('#peek').innerText", sid), r"(?i)client wording")

    def test_a_published_file_says_client_message_in_the_work_item_peek(self):          # Peek.jsx:136 and :404
        _plant, _pub, text = tp.made()
        folder = Path(tempfile.mkdtemp(prefix="clark-1466-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(str(folder), ignore_errors=True))
        path = folder / "report.html"
        path.write_text(text, encoding="utf-8")
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark), chrome() as cdp:
                    sid = tp.opened(cdp, path.as_uri() + "#work&p=PUB&item=PUB-A-001", width)
                    if dark:
                        cdp.js(DARK, sid)
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek .pk-fields dt')", sid)), "the published peek drew")
                    labels = cdp.js(LABELS, sid)
                    self.assertEqual([l for l in labels if l.lower() == "client message"], ["Client Message"], labels)

    def test_the_row_editor_label_and_toasts_say_client_message_of(self):
        html = page.page_html(tp.EMPTY_BRANDING, view=False)
        for words in ("`Client Message of ${", "} changed.`", "} is back as it was.`"):
            with self.subTest(words=words):
                self.assertIn(words, html)
        self.assertNotIn("`Wording of ${", html)


if __name__ == "__main__":
    unittest.main()
