"""Row 1479: the published use case page shows the Owner (the owner's ruling, 20-11-2026), names how each milestone is reached, never a Last change or
a History card, and a reference that already begins with UC is not given UC again.

Run: python3 dev/run_tests.py test_publish_uc_owner_1479
Same plant and file as test_publish_usecases. Laptop widths only: 1400 and 900 px.
"""
import tempfile
import unittest
from pathlib import Path

from test_publish import block, chrome, opened, wait
from test_publish_usecases import made, planted
import test_server  # noqa: F401  (this file drives Chrome: it is in the browser tier)

OWNER = "ZQ-OWNER-NAME"


def with_owner(plant):
    planted(plant)
    plant["data"]["use_cases"][0].update(owner=OWNER, ref="UC 1.1")
    plant["data"]["use_cases"][1].update(owner="ZQ-OWNER-OF-HIDDEN")      # its eye is off: it is not in the file


def js(cdp, sid, code):
    return cdp.js(code, sid)


class TheOwnerIsPublished(unittest.TestCase):
    def test_the_owner_of_a_shared_use_case_is_in_the_file_and_no_other(self):
        _, pub, text = made(with_owner)
        self.assertEqual([u["owner"] for u in pub["data"]["use_cases"]], [OWNER])
        self.assertNotIn("ZQ-OWNER-OF-HIDDEN", text)
        self.assertNotIn("updated_at", pub["data"]["use_cases"][0])


class ThePageShowsIt(unittest.TestCase):
    def test_owner_label_no_last_change_no_history_and_one_uc(self):
        _, pub, text = made(with_owner)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "r.html"
            path.write_text(text, encoding="utf-8")
            for width in (1400, 900):
                with self.subTest(width=width), chrome() as cdp:
                    sid = opened(cdp, path.as_uri())
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1000, "deviceScaleFactor": 1, "mobile": False}, sid)
                    self.assertTrue(wait(lambda: js(cdp, sid, "document.documentElement.dataset.ready") == "1"))
                    uid = pub["data"]["use_cases"][0]["id"]
                    js(cdp, sid, f"location.hash = '#usecases&p=PUB&uc={uid}'")
                    self.assertTrue(wait(lambda: js(cdp, sid, "!!document.querySelector('[data-ucf]')")))
                    labels = js(cdp, sid, "[...document.querySelectorAll('[data-ucf-details] dt')].map(e => e.textContent)")
                    self.assertEqual(labels[0], "Owner")
                    self.assertNotIn("Last change", labels)
                    self.assertEqual(js(cdp, sid, "document.querySelector('[data-uc-owner]').textContent"), OWNER)
                    self.assertEqual(js(cdp, sid, "document.querySelectorAll('[data-uc-owner] input, [data-uc-owner] textarea, [data-uc-owner] button').length"), 0)
                    hows = js(cdp, sid, "[...document.querySelectorAll('[data-ucf] [data-ms-how]')].map(e => e.textContent)")
                    self.assertTrue(hows and set(hows) == {"Through work items"}, hows)
                    page = js(cdp, sid, "document.querySelector('[data-ucf]').innerText")
                    for gone in ("HISTORY", "LAST CHANGE", "LINKED DIRECTLY MEANS", "CLICK THE TEXT", "ADD AN OWNER"):
                        self.assertNotIn(gone, page.upper())
                    self.assertNotIn("UC UC", js(cdp, sid, "document.querySelector('[data-ucf]').innerText + document.querySelector('.ucf-crumb').innerText"))
                    self.assertIn("UC 1.1", page)


class TheReferenceIsNotDoubled(unittest.TestCase):
    def test_refof_and_refbox_add_the_short_form_once(self):
        import json
        import subprocess
        from _paths import ROOT
        src = (ROOT / "src/clark/page/src/logic/useCasesList.js").read_text(encoding="utf-8")
        start = src.index("export const REF_PREFIX")
        end = src.index("/** The reference as it is read")
        body = src[start:end].replace("export const", "const")
        tail = src[end:src.index("/** The open next steps")].replace("export const", "const").replace("export function", "function")
        code = body + tail + ("\nconsole.log(JSON.stringify([refOf({ref: '1.1'}), refOf({ref: 'UC 1.1'}), refOf({ref: 'uc1.1'}), refOf({ref: 'UCLA 1'}), refOf({ref: ''}),"
                              " refBox('UC 1.1'), refBox('1.1'), refBox('')]));")
        out = subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True).stdout
        self.assertEqual(json.loads(out), ["UC 1.1", "UC 1.1", "UC 1.1", "UC UCLA 1", "", "UC 1.1", "UC 1.1", ""])
