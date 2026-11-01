"""Shared by test_ai_editor.py: the real RichText with the AI attached, on a bare page, with a FAKE provider. Not a test file.

The page offers:
  mount(value, cfg)   draws RichText for `value`; cfg {place, noMake}; window.made has every Make into call as [kind, text],
                      window.saves / window.ended as in _rich_page, window.opts the fake provider's settings, window.client the fake
  window.MI           the Make into request builder (logic/makeInto.js)
Nothing here signs in to anything or sends anything anywhere. Fictional text only.
"""
import json
import tempfile
from pathlib import Path

from _paths import TOOLS
from _rich_page import CTRL, META, Harness, PAGE_SRC, wait_for

import sys
sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402

ENTRY = """import { render } from "preact";
import { RichText } from %(rich)s;
import { stubAiClient } from %(client)s;
import { makeIntoRequest, makeIntoDone } from %(make)s;
window.opts = {};
window.client = stubAiClient(window.opts);
window.MI = { makeIntoRequest, makeIntoDone };
window.saves = []; window.ended = 0; window.made = [];
const root = document.getElementById("root");
window.unmount = () => render(null, root);
window.mount = (value, cfg) => {
  cfg = cfg || {};
  render(null, root);
  window.saves = []; window.ended = 0; window.made = [];
  render(<RichText value={value} label="Test text" aiPlace={cfg.place === undefined ? "current" : cfg.place} aiClient={window.client}
    onMakeInto={cfg.noMake ? undefined : (kind, text) => { window.made.push([kind, text]); }}
    onSave={(h) => { window.saves.push(h); return Promise.resolve(true); }}
    onClose={() => { window.ended += 1; render(null, root); }} />, root);
};
"""


def bundle(tmp):
    q = lambda *p: json.dumps(str(PAGE_SRC.joinpath(*p)))  # noqa: E731
    entry = Path(tmp) / "entry.jsx"
    entry.write_text(ENTRY % {"rich": q("edit", "RichText.jsx"), "client": q("edit", "aiClient.js"), "make": q("logic", "makeInto.js")},
                     encoding="utf-8")
    out = Path(tmp) / "aied.js"
    args = ["--bundle", "--format=iife", "--target=es2020", "--tsconfig-raw={}", "--loader:.jsx=jsx", *build_page.preact_flags(),
            str(entry), f"--outfile={out}"]
    done = esbuild.run(args, cwd=PAGE_SRC, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return out.read_text(encoding="utf-8")


class AiEditorHarness(Harness):
    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory()
        tmp = Path(self.tmp.name)
        (tmp / "aied.js").write_text(bundle(tmp), encoding="utf-8")
        css = build_page.page_css(build_page.ENTRY)
        (tmp / "page.html").write_text(f"<!doctype html><meta charset=utf-8><style>{css}</style>"
                                       "<body><p id=outside tabindex=0>Outside the field.</p><div id=root></div>"
                                       "<script src=aied.js></script></body>", encoding="utf-8")
        self.chrome = self.launch()
        self.cdp = self.chrome.__enter__()
        tid = next(t["targetId"] for t in self.cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        self.sid = self.cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        self.cdp.call("Page.enable", {}, self.sid)
        self.resize(1400)
        self.cdp.call("Page.navigate", {"url": (tmp / "page.html").as_uri()}, self.sid)
        assert wait_for(lambda: self.ev("typeof window.mount === 'function'") is True, 60), "the page's script did not load"
        self.mod = META if self.ev("/Mac/.test(navigator.platform)") else CTRL
        return self

    def open(self, value="", **cfg):
        self.ev(f"window.mount({json.dumps(value)}, {json.dumps(cfg)})")
        assert self.until("!!document.querySelector('.rt .ProseMirror')"), "the editor did not open"
        assert self.until("document.activeElement && document.activeElement.classList.contains('ProseMirror')"), "the editor has no focus"

    def select(self, a, b):
        """Choose the text between two document positions."""
        self.ev(f"document.querySelector('.ProseMirror').cxed.editor.chain().focus().setTextSelection({{from:{a},to:{b}}}).run()")
