"""Item 1169: both Gantt "on" boxes, the Asking folder box and a select in a `.fld` (the brand choice) draw the 2 px house focus ring, in real Chrome.

Run: python3 dev/run_tests.py test_settings_focus_ring_1169
The real Settings page over the fictional demo data at 1400 and 900 px, light and dark. Each control is focused from the keyboard's point of view
(:focus-visible) and its computed outline is measured: solid, 2 px wide, in the house blue.
Chrome is required.
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
from test_work_items import FIXED_DATE, load_demo, page_target  # noqa: E402

EMPTY_BRANDING = tempfile.mkdtemp(prefix="clark-no-brand-")
PROBE_SELECT = "(() => { const d = document.createElement('div'); d.className = 'fld'; d.innerHTML = '<label for=\"probe-select\">x</label><select id=\"probe-select\"><option>a</option></select>'; document.querySelector('#update').appendChild(d); const a = document.createElement('div'); a.className = 'ai-model'; a.innerHTML = '<select id=\"probe-ai-model\"><option>a</option></select>'; document.body.appendChild(a); const f = document.createElement('form'); f.className = 'row'; f.innerHTML = '<input id=\"ask-folder-path\" class=\"grow\" type=\"text\">'; document.querySelector('#update').appendChild(f); })()"
SEL = {"gantt-editor": "#gantt-editor", "gantt-client": "#gantt-client", "fld-select": "#probe-select", "ai-model-select": "#probe-ai-model", "ask-folder-path": "#ask-folder-path"}
MEASURE = r"""((sels) => {
  const out = {};
  const blue = getComputedStyle(document.documentElement).getPropertyValue('--brand-blue').trim();
  for (const [name, sel] of Object.entries(sels)) {
    const el = document.querySelector(sel);
    if (!el) { out[name] = null; continue; }
    el.focus({ preventScroll: true });
    const cs = getComputedStyle(el);
    out[name] = { visible: el.matches(':focus-visible'), style: cs.outlineStyle, width: parseFloat(cs.outlineWidth), offset: parseFloat(cs.outlineOffset), color: cs.outlineColor };
  }
  const probe = document.createElement('i'); probe.style.color = blue; document.body.appendChild(probe);
  out.blue = getComputedStyle(probe).color; probe.remove();
  return JSON.stringify(out);
})"""


def tearDownModule():
    shutil.rmtree(EMPTY_BRANDING, ignore_errors=True)


class SettingsFocusRing(unittest.TestCase):
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

    def measure(self, cdp, width, theme):
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.s.port}/#settings&p=TUL&s=reports"}, sid)
        self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.ready", sid) == "1"), "the bundle ran")
        cdp.js(f"document.documentElement.dataset.theme = {json.dumps(theme)}", sid)
        cdp.js("(document.querySelector('[data-mode=edit]') || {click() {}}).click()", sid)
        got = {}
        for page, names in (("reports", ("gantt-editor", "gantt-client")), ("version", ("fld-select", "ai-model-select", "ask-folder-path"))):      # row 1024: one Settings page at a time; the Gantt boxes are on Reports, Feedback on Version and updates
            cdp.js(f"location.hash = '#settings&p=TUL&s={page}'", sid)
            self.assertTrue(wait(lambda: cdp.js(f"document.querySelector('.set-cards').getAttribute('data-page') === {json.dumps(page)} && (!!document.querySelector({json.dumps(SEL[names[0]])}) || {json.dumps(page == "version")})", sid)), f"the {page} page drew {names[0]}")
            if page == "version":
                cdp.js(PROBE_SELECT, sid)       # the Brand for this project choice is a select in a .fld; its card needs the brand service, which this test server has not
            for name in names:
                self.assertTrue(wait(lambda: cdp.js(f"!!document.querySelector({json.dumps(SEL[name])})", sid)), f"{name} is on the page")
            self.assertTrue(wait(lambda: cdp.js("document.getAnimations().length === 0", sid)), "the page's motion has finished before anything is measured")
            for kind in ("keyDown", "keyUp"):       # a key, so the page is in keyboard mode and a focused control matches :focus-visible
                cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": "Shift", "code": "ShiftLeft", "windowsVirtualKeyCode": 16}, sid)
            got.update(json.loads(cdp.js(f"{MEASURE}({json.dumps({n: SEL[n] for n in names})})", sid)))
        return got

    def test_each_control_has_the_two_pixel_ring_at_both_widths_in_both_looks(self):
        with chrome() as cdp:
            for width in (1400, 900):
                for theme in ("light", "dark"):
                    got = self.measure(cdp, width, theme)
                    for name in SEL:
                        label = f"{name}, {width} px, {theme}"
                        m = got[name]
                        self.assertIsNotNone(m, label + ": on the page")
                        self.assertTrue(m["visible"], label + " shows its keyboard focus ring")
                        self.assertEqual(m["style"], "solid", label)
                        self.assertEqual(m["width"], 2, label + ": the ring is 2 px")
                        self.assertEqual(m["color"], got["blue"], label + ": the house blue")


if __name__ == "__main__":
    unittest.main()
