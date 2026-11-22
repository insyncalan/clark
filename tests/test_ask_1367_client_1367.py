"""Row 1367 (AP4, DoD4): what a client gets does not change when ask clark reads the whole project, and ask clark is never on a read-only or client page.

Run: python3 dev/run_tests.py test_ask_1367_client_1367
The Word export and the published ("To client") file are built from publish.select(), which ask clark's wider read never touches; these tests
build both before and after an ask read of the same project and compare. Fictional data only (the publish plant). Chrome at 1400 and 900 px,
light and dark, for the page test.
"""
import copy
import io
import tempfile
import unittest
import zipfile
from unittest import mock

from _paths import SRC  # noqa: F401

import _publish_fixture as plant
from clark import ask_data, docx_build, page, publish
from test_milestones_page import EMPTY_BRANDING
from test_server import Running, chrome, wait
from test_milestones_page import page_target, FIXED_DATE, for_url

AS_AT = "2026-11-17"
HIDDEN = ("ZQ-FLAG-OFF-ACTION", "ZQ-HIDDEN-ACTION", "ZQ-ARCHIVED-ACTION", "ZQ-FLAG-OFF-MILESTONE", "ZQ-HIDDEN-MILESTONE", "ZQ-FLAG-OFF-RISK", "ZQ-GHOST-WORKSTREAM")


def given():
    g = plant.inputs()
    g["as_at"] = AS_AT
    return g


def ask_reads(g):
    with mock.patch.object(publish, "read_inputs", return_value=g):
        return ask_data.project_data(object(), "PUB", "tell me about everything, hidden items too", as_at=AS_AT)


def word_parts(published):
    with zipfile.ZipFile(io.BytesIO(docx_build.build(published))) as z:
        return {n: z.read(n) for n in z.namelist()}


def client_file(published):
    return publish.render(published, page.page_html(EMPTY_BRANDING, view=True), AS_AT, published["data"]["project"]["name"])


class WhatAClientGets(unittest.TestCase):
    def test_the_word_export_is_the_same_with_and_without_ask_reading_hidden_rows(self):
        untouched = word_parts(publish.select(given()))
        g = given()
        read = ask_reads(g)
        self.assertIn("ZQ-HIDDEN-ACTION", "\n".join(p.text for p in read.passages), "ask clark did read the hidden rows, or this test proves nothing")
        after = word_parts(publish.select(g))
        self.assertEqual(sorted(after), sorted(untouched))
        for name in untouched:
            self.assertEqual(after[name], untouched[name], f"{name} is the same bytes after an ask read")
        body = untouched["word/document.xml"].decode("utf-8")
        for marker in HIDDEN:
            self.assertNotIn(marker, body, f"{marker} is not in the Word export")

    def test_to_client_mode_output_is_unchanged(self):
        untouched = client_file(publish.select(given()))
        g = given()
        ask_reads(g)
        after = client_file(publish.select(g))
        self.assertEqual(after, untouched, "the file that goes to the client is the same text after an ask read")
        for marker in HIDDEN:
            self.assertNotIn(marker, untouched, f"{marker} is not in the client's file")

    def test_the_ask_read_does_not_change_the_rows_it_was_given(self):
        before, g = copy.deepcopy(given()["data"]), given()
        ask_reads(g)
        self.assertEqual(g["data"], before, "reading for ask clark leaves every row as it was")


class NoAskOnAReadOnlyOrClientPage(unittest.TestCase):
    def test_ask_clark_is_absent_from_a_read_only_and_a_client_page_at_1400_and_900(self):
        text = client_file(publish.select(given()))
        self.assertIn('data-mode="view"', text)
        for width in (1400, 900):
            for mode in ("light", "dark"):
                with self.subTest(width=width, mode=mode), chrome() as cdp:
                    s = Running(data_for=lambda code: {}, projects=lambda archived=False: [], page_html=lambda: text)
                    self.addCleanup(s.close)
                    sid = page_target(cdp)
                    cdp.call("Page.enable", {}, sid)
                    cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
                    cdp.call("Page.navigate", {"url": for_url(f"http://127.0.0.1:{s.port}/")}, sid)
                    self.assertTrue(wait(lambda: cdp.js("document.readyState === 'complete' && !!document.querySelector('.top, header, main, body > *')", sid)), "the client page drew")
                    cdp.js(f"document.documentElement.dataset.theme = '{mode}'", sid)
                    import time
                    time.sleep(1.0)      # the page's scripts have run and nothing was added after
                    g = cdp.js("({btn: !!document.querySelector('#ask-btn, .tb-ask'), panel: !!document.querySelector('#ask-panel, .ask-panel'), mode: document.documentElement.dataset.mode, words: /ask clark/i.test(document.body.innerText)})", sid)
                    self.assertEqual(g["mode"], "view", g)
                    self.assertFalse(g["btn"], f"no ask button on the client page at {width} {mode}")
                    self.assertFalse(g["panel"], "no ask panel")
                    self.assertFalse(g["words"], "the words ask clark are not on the page")


if __name__ == "__main__":
    unittest.main()
