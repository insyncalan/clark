"""#1111: a published file's work item peek draws the Latest update and the Client wording the file already carries, read only, and
only when there is some (no new published data). Real publish.select/render and headless Chrome.
Run: python3 dev/run_tests.py test_peek_latest_wording_1111
"""
import json
import tempfile
import unittest
from pathlib import Path

import _publish_fixture as fx
from clark import page, publish  # noqa: E402
from test_server import chrome, wait  # noqa: E402
import test_publish as tp  # noqa: E402

LABELS = "[...document.querySelectorAll('#peek .pk-fields dt')].map(d => d.textContent.trim())"
CONTROLS = "button, input, textarea, select, [contenteditable], [role=textbox], [role=combobox]"


class PublishedPeek(unittest.TestCase):
    def setUp(self):
        plant = fx.load()
        for a in plant["data"]["actions"]:
            if a["id"] == "PUB-A-001":
                a["latest_update"] = "<p>Plan <em>agreed</em> ZQ-KEEP-LATEST</p>"
        for key in ("risks", "decisions"):                  # a stray latest_update on a non-action must not be drawn
            for r in plant["data"].get(key, [])[:1]:
                r["latest_update"] = "<p>ZQ-NOT-FOR-THIS-KIND</p>"
                self.other = r["id"]
        pub = publish.select(fx.inputs(plant))
        text = publish.render(pub, page.page_html(tp.EMPTY_BRANDING, view=True), plant["as_at"], pub["data"]["project"]["name"])
        folder = Path(tempfile.mkdtemp(prefix="clark-1111-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(str(folder), ignore_errors=True))
        self.path = folder / "report.html"
        self.path.write_text(text, encoding="utf-8")

    def labels(self, item, width=1400):
        with chrome() as cdp:
            sid = tp.opened(cdp, self.path.as_uri() + "#work&p=PUB&item=" + item, width)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek .pk-fields')", sid)), "the peek drew")
            got = cdp.js(LABELS, sid)
            return got, cdp.js("document.querySelector('#peek .pk-body').innerText", sid), cdp.js(
                f"[...document.querySelector('#peek .pk-body').querySelectorAll({json.dumps(CONTROLS)})].length", sid), cdp.js(
                "document.querySelectorAll('#peek [data-ms-row=latest_update] em').length", sid)

    def test_an_action_with_both_shows_both_read_only(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                labels, body, controls, em = self.labels("PUB-A-001", width)
                self.assertIn("Client wording", labels)
                self.assertIn("Latest update", labels)
                self.assertIn("ZQ-KEEP-MESSAGE-1", body)
                self.assertIn("Plan agreed ZQ-KEEP-LATEST", body)
                self.assertEqual(em, 1, "the update is drawn as the editor draws it")
                self.assertEqual(controls, 0, "read only")

    def test_an_action_with_neither_shows_neither(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                labels, _body, _controls, _em = self.labels("PUB-A-002", width)
                self.assertNotIn("Client wording", labels)
                self.assertNotIn("Latest update", labels)

    def test_a_risk_or_decision_never_shows_a_latest_update(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                labels, body, _controls, _em = self.labels(self.other, width)
                self.assertNotIn("Latest update", labels)
                self.assertNotIn("ZQ-NOT-FOR-THIS-KIND", body)


if __name__ == "__main__":
    unittest.main()
