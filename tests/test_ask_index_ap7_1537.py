"""Row 1537 AP7: the people and contract warning (ticket 1365) and the Used line (ticket 1292) still show unchanged on an answer built from index passages,
at 1400 and 900 px, light and dark. Chrome, the real page, the real AskService with a real index (ask_index.Indexer) and the real folder route; only the
model is a stub provider. Light and dark are the computer's colour scheme, as test_ask_settings sets it. Made-up names only.

Run: python3 dev/run_tests.py test_ask_index_ap7_1537
"""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401

import test_ask_about_1292 as t1292
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome, wait

from clark import ask, ask_folders, ask_index, ask_service, reach

WIDTHS = (1400, 900)
SCHEMES = ("light", "dark")
PASSAGE = "The zebrafish tank is cleaned on Tuesdays."
HOLDS = "This folder holds Payroll. Passages from it may go to Claude, which Anthropic runs, and they can contain personal information. Send passages from this folder to Claude?"


class IndexAnswer(t1292.Classic):
    def setUp(self):
        super().setUp()
        patch = mock.patch.object(reach.platform, "system", return_value=reach.platform.MAC)
        patch.start()
        self.addCleanup(patch.stop)
        self.box = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.box, True)
        self.notes, self.flagged = self.box / "notes", self.box / "lib"
        for d in (self.notes, self.flagged / "Payroll"):
            d.mkdir(parents=True)
        (self.notes / "tank.txt").write_text(PASSAGE, encoding="utf-8")
        (self.flagged / "Payroll" / "pay.txt").write_text("Pay runs monthly.", encoding="utf-8")
        data = self.store.path.parent
        self.provider = ask.StubProvider(reply="")
        self.service = ask_service.AskService(self.store.path, self.provider, [], data_dir=data)
        self.indexer = ask_index.Indexer(data)
        self.addCleanup(self.indexer.shutdown)
        self.service.indexer = self.indexer
        self.s.httpd.ask = self.service
        self.s.httpd.ask_folders = ask_folders.AskFolders(self.store.path, [], data_dir=data, home=self.box, by_user=lambda: "tester", indexer=self.indexer)
        for folder in (self.notes, self.flagged):
            status, _, raw = self.s.api("POST", "/api/ask-folders", json.dumps({"project": "ABC", "action": "add", "path": str(folder)}).encode())
            self.assertEqual((status, json.loads(raw).get("ok")), (200, True), raw)
        self.assertTrue(self.indexer.wait_idle(20))
        self.assertTrue(self.indexer.current("ABC", [str(self.notes)]), "the index is complete for the readable folder")

    def item_id(self, p):
        return p.js("document.querySelector('.wil-table tr[data-id]').dataset.id")

    def size(self, cdp, p, width, scheme):
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, p.sid)

    def test_the_used_line_shows_unchanged_on_an_answer_built_from_index_passages(self):
        for width in WIDTHS:
            for scheme in SCHEMES:
                with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                    p = self.visit(cdp)
                    self.size(cdp, p, width, scheme)
                    p.edit()
                    ident = self.item_id(p)
                    self.provider.reply = f"{ident} is late. The tank is cleaned on Tuesdays."
                    p.key("/", code="Slash", vk=191)
                    p.until("!document.querySelector('#ask-send') || !document.querySelector('#ask-send').disabled", "ready")
                    sent, direct = len(self.provider.sent), []
                    real = ask_service.ask_passages.folder_data
                    with mock.patch.object(ask_service.ask_passages, "folder_data", lambda *a, **k: direct.append(1) or real(*a, **k)):
                        self.ask(p, "when is the zebrafish tank cleaned")
                        p.until("!!document.querySelector('[data-ask-used]')", "the Used line drew")
                    self.assertEqual(len(self.provider.sent), sent + 1)
                    self.assertIn(PASSAGE, self.provider.sent[-1], "the passage was sent")
                    self.assertIn("tank.txt", self.provider.sent[-1])
                    self.assertEqual(direct, [], "the passage came from the index, the direct folder read was not used")
                    self.assertEqual(p.js("document.querySelector('[data-ask-used]').textContent.replace(/\\s+/g, ' ').trim()"), f"Used: 1 {ident}")
                    self.assertTrue(p.js("(() => { const r = document.querySelector('[data-ask-used]').getBoundingClientRect(); return r.width > 0 && r.right <= document.querySelector('#ask-panel').getBoundingClientRect().right + 1; })()"), "the line sits inside the panel")
                    self.assertTrue(p.js("document.documentElement.scrollWidth <= innerWidth"), "nothing overflows sideways")

    def test_the_people_and_contract_warning_shows_unchanged_while_the_answer_path_is_the_index(self):
        for width in WIDTHS:
            for scheme in SCHEMES:
                with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                    p = self.visit(cdp)
                    self.size(cdp, p, width, scheme)
                    p.js("location.hash = '#settings&p=ABC&s=claude'")
                    p.until("!!document.querySelector('[data-ask-warn]')", "the warning drew")
                    self.assertEqual(p.js("document.querySelectorAll('[data-ask-warn]').length"), 1)
                    flat = p.js("document.querySelector('[data-ask-warn]').innerText").replace("\n", " ")
                    self.assertIn(HOLDS, " ".join(flat.split()))
                    self.assertIn("Left out of ask clark.", flat)
                    self.assertEqual(p.js("[...document.querySelectorAll('[data-ask-warn] button')].map(b => b.innerText)"), ["Accept", "Decline", "Leave these subfolders out"], "the folder is a subfolder, so the third button shows")
                    self.assertTrue(p.js("(() => { const r = document.querySelector('[data-ask-warn]').getBoundingClientRect(); return r.width > 0 && r.right <= innerWidth; })()"), "inside the window")
                    self.assertTrue(p.js("document.documentElement.scrollWidth <= innerWidth"), "nothing overflows sideways")
                    self.assertEqual(self.s.httpd.ask_folders.all_folders("ABC"), [str(self.notes)], "the flagged folder is left out of the index, the other one is read")
                    self.assertTrue(self.indexer.current("ABC", [str(self.notes)]))
                    self.assertIs(self.service.indexer, self.indexer, "the answer path is the index")


if __name__ == "__main__":
    unittest.main()
