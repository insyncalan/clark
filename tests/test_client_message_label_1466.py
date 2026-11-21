"""Row 1466 (the points the first PR left open): the details panel label on the live page in View and Edit, the Client visible line kept in View and Edit
with one click and Undo, a published file with no eye and no client-visibility words anywhere (light and dark), and no gap row left in a published peek.
Run: CLARK_CHROME=/usr/local/bin/creaite-chrome python3 dev/run_tests.py test_client_message_label_1466
"""
import re
import tempfile
import unittest
from pathlib import Path

import test_peek_ruled_1077 as base  # noqa: E402
import test_publish as tp  # noqa: E402
from test_server import chrome, wait  # noqa: E402

DECISION, MILESTONE, RISK = "TUL-D-013", "TUL-M-002", "TUL-007"
LABELS = "[...document.querySelectorAll('#peek .pk-fields dt')].map(d => d.textContent.trim())"
PEEK_TEXT = "document.querySelector('#peek').innerText"
EYES = "document.querySelectorAll('svg[data-icn=eye], svg[data-icn=eyeoff]').length"
CLIENT_WORDS = r"(?i)client (not )?visible|shown to the client|hidden from the client"


def published():
    _plant, _pub, text = tp.made()
    folder = Path(tempfile.mkdtemp(prefix="clark-1466b-"))
    path = folder / "report.html"
    path.write_text(text, encoding="utf-8")
    return folder, path


class Live(base.Peeks):
    def test_the_details_panel_label_is_client_message_in_view_and_edit(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.dashboard_in_view(cdp, width, self.store, self.code)
                seen = {}
                for mode in ("View", "Edit"):
                    if mode == "Edit":
                        self.to_edit(cdp, sid)
                    for ref, kind in ((DECISION, "item"), (MILESTONE, "milestone")):
                        self.open_peek(cdp, sid, ref, kind)
                        labels = cdp.js(LABELS, sid)
                        self.assertNotIn("Client wording", labels, (mode, ref))
                        self.assertNotRegex(cdp.js(PEEK_TEXT, sid), r"(?i)client wording")
                        seen[(mode, ref)] = labels
                self.assertIn("Client Message", seen[("View", MILESTONE)])
                self.assertIn("Client Message", seen[("Edit", MILESTONE)])
                self.assertIn("Client Message", seen[("Edit", DECISION)])

    def test_view_and_edit_keep_the_client_visible_line_with_one_click_and_undo(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.dashboard_in_view(cdp, width, self.store, self.code)
                self.open_peek(cdp, sid, RISK, "item")
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek [data-pk-client-read]')", sid)), "View: the status line")
                self.assertRegex(cdp.js("document.querySelector('#peek [data-pk-client-read]').textContent", sid), r"Client (not )?visible")
                self.assertEqual(cdp.js("document.querySelectorAll('#peek [data-pk-client]').length", sid), 0, "View: not a control")
                self.to_edit(cdp, sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek [data-pk-client]')", sid)), "Edit: the control")
                before = cdp.js("document.querySelector('#peek [data-pk-client]').getAttribute('aria-pressed')", sid)
                cdp.js("document.querySelector('#peek [data-pk-client]').click()", sid)
                self.assertTrue(wait(lambda: cdp.js("document.querySelector('#peek [data-pk-client]').getAttribute('aria-pressed')", sid) != before), "one click changes it")
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.toast [data-undo]')", sid)), "the toast offers Undo")
                cdp.js("document.querySelector('.toast [data-undo]').click()", sid)
                self.assertTrue(wait(lambda: cdp.js("document.querySelector('#peek [data-pk-client]').getAttribute('aria-pressed')", sid) == before), "Undo puts it back")


class Published(unittest.TestCase):
    def setUp(self):
        self.folder, self.path = published()
        self.addCleanup(lambda: __import__("shutil").rmtree(str(self.folder), ignore_errors=True))

    def scheme(self, cdp, sid, scheme):
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)

    def test_no_eye_and_no_client_visibility_words_anywhere_light_and_dark(self):
        pages = ("", "#dashboard&p=PUB", "#work&p=PUB", "#work&p=PUB&item=PUB-A-001", "#work&p=PUB&item=PUB-001", "#work&p=PUB&item=PUB-D-001",
                 "#dashboard&p=PUB&ms=PUB-M-001", "#usecases&p=PUB&uc=1.1")
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                with chrome() as cdp:
                    sid = tp.opened(cdp, self.path.as_uri(), width)
                    self.scheme(cdp, sid, scheme)
                    self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.ready", sid) == "1"))
                    for hash_ in pages:
                        with self.subTest(width=width, scheme=scheme, page=hash_):
                            cdp.js(f"location.hash = {hash_!r}", sid)
                            self.assertTrue(wait(lambda: cdp.js("document.body.innerText.length > 20", sid)))
                            if cdp.js("!!document.querySelector('#peek [data-pk-details]')", sid) and cdp.js("document.querySelector('#peek [data-pk-details]').getAttribute('aria-expanded')", sid) != "true":
                                cdp.js("document.querySelector('#peek [data-pk-details]').click()", sid)
                            self.assertEqual(cdp.js(EYES, sid), 0, "no eye icon in the file")
                            self.assertNotRegex(cdp.js("document.body.innerText", sid), CLIENT_WORDS)
                            self.assertNotRegex(cdp.js("document.body.innerText", sid), r"(?i)client wording")

    def test_a_published_peek_leaves_no_empty_row_where_the_line_was(self):
        rows = ("[...document.querySelectorAll('#peek .pk-fields > *')].filter(e => !e.textContent.trim() && !e.querySelector('svg, input, button')).length",
                "[...document.querySelectorAll('#peek .pk-fields .pk-row')].filter(e => !e.querySelector('dt') && !e.textContent.trim()).length")
        for width in (1400, 900):
            for hash_ in ("#work&p=PUB&item=PUB-A-001", "#work&p=PUB&item=PUB-001", "#work&p=PUB&item=PUB-D-001", "#dashboard&p=PUB&ms=PUB-M-001"):
                with self.subTest(width=width, page=hash_), chrome() as cdp:
                    sid = tp.opened(cdp, self.path.as_uri() + hash_, width)
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek .pk-fields dt')", sid)))
                    if cdp.js("!!document.querySelector('#peek [data-pk-details]')", sid) and cdp.js("document.querySelector('#peek [data-pk-details]').getAttribute('aria-expanded')", sid) != "true":
                        cdp.js("document.querySelector('#peek [data-pk-details]').click()", sid)
                    for js in rows:
                        self.assertEqual(cdp.js(js, sid), 0)
                    self.assertEqual(cdp.js("document.querySelectorAll('#peek [data-pk-client-row]').length", sid), 0)
                    labels = cdp.js(LABELS, sid)
                    self.assertTrue(all(labels), labels)
                    self.assertEqual(len(labels), len(set(labels)), labels)
                    self.assertFalse(any(re.search(r"(?i)client visible", l) for l in labels))


if __name__ == "__main__":
    unittest.main()
