"""Item 1169: both Gantt "on" boxes and the Feedback box draw the 2 px house focus ring, in real Chrome.

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
SEL = {"gantt-editor": "#gantt-editor", "gantt-client": "#gantt-client", "feedback": "#feedback-message", "feedback-shown": "#feedback-shown"}
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
# The clipboard always refuses, so the Feedback box draws its shown-text box (#feedback-shown) after Copy as text.
REFUSE_CLIPBOARD = "Object.defineProperty(navigator, 'clipboard', {configurable: true, value: {writeText: () => Promise.reject(new Error('refused'))}});"
TYPE_MESSAGE = """(() => {
  const el = document.querySelector('#feedback-message');
  el.value = 'x';
  el.dispatchEvent(new Event('input', {bubbles: true}));
})()"""


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
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": REFUSE_CLIPBOARD}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.s.port}/#settings&p=TUL"}, sid)
        self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.ready", sid) == "1"), "the bundle ran")
        cdp.js(f"document.documentElement.dataset.theme = {json.dumps(theme)}", sid)
        cdp.js("(document.querySelector('[data-mode=edit]') || {click() {}}).click()", sid)
        self.assertTrue(wait(lambda: cdp.js(f"!!document.querySelector({json.dumps(SEL['feedback'])})", sid)), "the Feedback box is on the page")
        cdp.js(TYPE_MESSAGE, sid)       # a message, then Copy as text, which the refused clipboard answers by drawing the shown-text box
        self.assertTrue(wait(lambda: cdp.js("!document.querySelector('button[data-feedback-copy]').disabled", sid)), "Copy as text is enabled by the message")
        cdp.js("document.querySelector('button[data-feedback-copy]').click()", sid)
        for name, sel in SEL.items():
            self.assertTrue(wait(lambda: cdp.js(f"!!document.querySelector({json.dumps(sel)})", sid)), f"{name} is on the page")
        self.assertTrue(wait(lambda: cdp.js("document.getAnimations().length === 0", sid)), "the page's motion has finished before anything is measured")
        for kind in ("keyDown", "keyUp"):       # a key, so the page is in keyboard mode and a focused control matches :focus-visible
            cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": "Shift", "code": "ShiftLeft", "windowsVirtualKeyCode": 16}, sid)
        return json.loads(cdp.js(f"{MEASURE}({json.dumps(SEL)})", sid))

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
                    self.assertEqual(got["feedback-shown"]["offset"], 1, f"feedback-shown, {width} px, {theme}: the ring sits 1 px off the box")


if __name__ == "__main__":
    unittest.main()
