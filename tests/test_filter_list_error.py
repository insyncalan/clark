"""#954: on the Work items filter line the floating list of suggestions never covers the message line (the unknown-field error).

Run: python3 dev/run_tests.py test_filter_list_error
The real page and a real server over the fictional demo data, at 1400 and 900 px, light and dark. Typing `zzz:a ` (a field that does not exist, then a space so the list opens) makes the
line say so; with the suggestion list open too, the list's box must start at or below the bottom of the message's box, and the message must be on top
at its own centre (nothing else is drawn over it). With no message (`ow`, the start of a field name) the list still floats just under the line: it is
below the line's box and above where the message line would be, so the placement is unchanged. Chrome is required: these tests fail, never skip.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401  (puts src/ on the path)

from clark import page, server as sv  # noqa: E402
from clark.store import open_store  # noqa: E402
from test_server import CHROME, Running, chrome, wait  # noqa: E402
from test_work_filters import arm, set_line  # noqa: E402
from test_work_items import FIXED_DATE, load_demo, page_target  # noqa: E402

EMPTY_BRANDING = tempfile.mkdtemp(prefix="clark-no-brand-")
BOXES = r"""(() => {
  const box = (e) => { if (!e) return null; const r = e.getBoundingClientRect(); return {top: r.top, bottom: r.bottom, left: r.left, right: r.right, height: r.height}; };
  const msg = document.querySelector('#fline-msg'), list = document.querySelector('#fline-list'), line = document.querySelector('[data-fline]');
  let over = null;
  if (msg && msg.textContent.trim()) { const r = msg.getBoundingClientRect(); const at = document.elementFromPoint(r.left + 6, r.top + r.height / 2); over = !!at && (at === msg || msg.contains(at)); }
  return JSON.stringify({msg: box(msg), text: msg ? msg.textContent.trim() : '', list: box(list), line: box(line), options: document.querySelectorAll('#fline-list [role=option]').length, msgOnTop: over});
})()"""


def tearDownModule():
    shutil.rmtree(EMPTY_BRANDING, ignore_errors=True)


class ListAndError(unittest.TestCase):
    def setUp(self):
        assert Path(CHROME).is_file(), f"Google Chrome is needed for the required browser tests ({CHROME}); set CLARK_CHROME"
        self.store, self.folder, _ = load_demo()
        self.addCleanup(shutil.rmtree, str(self.folder), True)
        self.addCleanup(self.store.close)
        self.path = self.folder / "clark.db"
        self.s = Running(data_for=self.read, projects=lambda archived=False: [{"code": "TUL", "name": "Tulip"}], page_html=lambda: page.page_html(EMPTY_BRANDING))
        self.addCleanup(self.s.close)
        quiet = mock.patch.object(sv.LOG, "disabled", True)
        quiet.start()
        self.addCleanup(quiet.stop)

    def read(self, code, archived=None):
        st = open_store(self.path, onedrive_roots=[])
        try:
            return st.data_for(code)
        finally:
            st.close()

    def typed(self, cdp, width, theme, text, want_message):
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.s.port}/#work&p=TUL&f=mode:all"}, sid)
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#fline-input')", sid)), "the filter line drew")
        cdp.js(f"document.documentElement.dataset.theme = {json.dumps(theme)}", sid)
        set_line(cdp, sid, text)      # a real click and real typing, then the pause after which the list follows the box
        arm(cdp, sid)                 # row 931: and Space, which opens the list
        self.assertTrue(wait(lambda: bool(cdp.js("(document.querySelector('#fline-msg') || {}).textContent", sid)) == want_message), "the message line settled")
        self.assertTrue(wait(lambda: cdp.js("document.getAnimations().length === 0", sid)), "the page's motion has finished before anything is measured")
        return json.loads(cdp.js(BOXES, sid))

    def test_the_list_never_covers_the_unknown_field_error(self):
        with chrome() as cdp:
            for width in (1400, 900):
                for theme in ("light", "dark"):
                    got = self.typed(cdp, width, theme, "zzz:a ", True)
                    where = f"{width} px, {theme}"
                    self.assertTrue(got["text"], where + ": the unknown field is said")
                    self.assertGreater(got["options"], 0, where + ": the suggestion list is open with the error (else this proves nothing)")
                    self.assertGreaterEqual(got["list"]["top"], got["msg"]["bottom"] - 0.5, where + ": the list starts below the message line")
                    self.assertTrue(got["msgOnTop"], where + ": the message is the top thing at its own place")
                    self.assertGreaterEqual(got["msg"]["top"], got["line"]["bottom"], where + ": the message is under the line")

    def test_with_no_message_the_list_still_floats_just_under_the_line(self):
        with chrome() as cdp:
            for width in (1400, 900):
                for theme in ("light", "dark"):
                    got = self.typed(cdp, width, theme, "ow", False)
                    where = f"{width} px, {theme}"
                    self.assertGreater(got["options"], 0, where + ": the list is open")
                    self.assertGreaterEqual(got["list"]["top"], got["line"]["bottom"], where + ": the list is below the line")
                    self.assertLessEqual(got["list"]["top"] - got["line"]["bottom"], 12, where + ": and close to it (it floats just under the box)")


if __name__ == "__main__":
    unittest.main()
