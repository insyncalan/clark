"""Shared by test_rich_editor.py and test_one_editor_gate.py (#66): the editor on a bare page. Not a test file.

`Harness` bundles a small entry (the real RichText component and clarkEditor, built the way build_page builds the page, the
same aliases and the page's own CSS) into a temporary folder, opens it in headless Chrome through test_server.chrome, and gives
the test `ev` (evaluate in the page), `key`, `type`, `resize` and `theme`. The page offers:
  unmount()             removes it
  mount(value)          draws RichText for `value`; window.saves has every html it saved, window.ended counts closes
  window.CE             { clarkEditor, cleanHtml, toHtml, forEditor, href }
Fictional text only.
"""
import json
import tempfile
import time
from pathlib import Path

from _paths import SRC, TOOLS

import sys
sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402

PAGE_SRC = SRC / "clark" / "page" / "src"
META, CTRL, SHIFT = 4, 2, 8                       # Input.dispatchKeyEvent modifiers

ENTRY = """import { render } from "preact";
import { RichText } from %(rich)s;
import { clarkEditor } from %(editor)s;
import { toHtml, forEditor } from %(html)s;
import { cleanHtml, href } from %(clean)s;
window.CE = { clarkEditor, cleanHtml, toHtml, forEditor, href };
window.saves = []; window.ended = 0; window.saveResult = true;
const root = document.getElementById("root");
window.unmount = () => render(null, root);
window.mount = (value) => {
  render(null, root);
  window.saves = []; window.ended = 0; window.saveResult = window.saveResult === undefined ? true : window.saveResult;
  render(<RichText value={value} label="Test text"
    onSave={(h) => { window.saves.push(h); return Promise.resolve(window.saveResult); }}
    onClose={() => { window.ended += 1; render(null, root); }} />, root);
};
"""


def wait_for(check, seconds=10):
    t0 = time.time()
    while time.time() - t0 < seconds:
        if check():
            return True
        time.sleep(0.1)
    return False


def bundle(tmp):
    q = lambda *p: json.dumps(str(PAGE_SRC.joinpath(*p)))  # noqa: E731
    entry = Path(tmp) / "entry.jsx"
    entry.write_text(ENTRY % {"rich": q("edit", "RichText.jsx"), "editor": q("core", "editor.js"), "html": q("core", "richHtml.js"),
                              "clean": q("logic", "cleanHtml.js")}, encoding="utf-8")
    out = Path(tmp) / "rich.js"
    args = ["--bundle", "--format=iife", "--target=es2020", "--tsconfig-raw={}", "--loader:.jsx=jsx", *build_page.preact_flags(),
            str(entry), f"--outfile={out}"]
    done = esbuild.run(args, cwd=PAGE_SRC, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return out.read_text(encoding="utf-8")


class Harness:
    """A Chrome tab with the editor page. `with Harness(test_server.chrome) as h:`."""

    def __init__(self, launch):
        self.launch = launch

    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory()
        tmp = Path(self.tmp.name)
        (tmp / "rich.js").write_text(bundle(tmp), encoding="utf-8")
        css = build_page.page_css()
        (tmp / "page.html").write_text(f"<!doctype html><meta charset=utf-8><style>{css}</style>"
                                       "<body><p id=outside tabindex=0>Outside the field.</p><div id=root></div>"
                                       "<script src=rich.js></script></body>", encoding="utf-8")
        self.chrome = self.launch()
        self.cdp = self.chrome.__enter__()
        tid = next(t["targetId"] for t in self.cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        self.sid = self.cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        self.cdp.call("Page.enable", {}, self.sid)
        self.resize(1400)
        self.cdp.call("Page.navigate", {"url": (tmp / "page.html").as_uri()}, self.sid)
        assert wait_for(lambda: self.ev("typeof window.mount === 'function'") is True, 60), "the page's script did not load"
        self.mod = META if self.ev("/Mac/.test(navigator.platform)") else CTRL        # ProseMirror's Mod key
        return self

    def __exit__(self, *exc):
        self.chrome.__exit__(*exc)
        self.tmp.cleanup()

    def ev(self, expr):
        return self.cdp.js(expr, self.sid)

    def until(self, expr, seconds=10):
        return wait_for(lambda: self.ev(expr), seconds)

    def resize(self, width, height=900):
        self.cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": False}, self.sid)

    def theme(self, name):
        self.ev(f"document.documentElement.dataset.theme = {json.dumps(name)}")

    def key(self, key, modifiers=0, code=None, vk=0):
        for kind in ("keyDown", "keyUp"):
            self.cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": key, "code": code or key, "windowsVirtualKeyCode": vk,
                                                      "modifiers": modifiers}, self.sid)

    def type(self, text):
        self.cdp.call("Input.insertText", {"text": text}, self.sid)

    def mount(self, value=""):
        self.ev(f"window.mount({json.dumps(value)})")
        assert self.until("!!document.querySelector('.rt .ProseMirror')"), "the editor did not open"
        assert self.until("document.activeElement && document.activeElement.classList.contains('ProseMirror')"), "the editor has no focus"

    def select_all(self):
        self.key("a", self.mod, "KeyA", 65)
