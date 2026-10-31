"""Shared by test_clean_html_parity.py and test_rich_html_sanitise.py (#66): the page's cleanHtml, bundled alone with the pinned
esbuild and run in headless Chrome, so the same Python test can feed it text and read what comes back. Not a test file. It starts
no Chrome itself: the test passes in test_server.chrome (the #33 harness), so the test file is the browser test."""
import json
import tempfile
import time
from pathlib import Path

from _paths import ROOT, TOOLS

import esbuild


def wait_for(check, seconds):
    t0 = time.time()
    while time.time() - t0 < seconds:
        if check():
            return True
        time.sleep(0.2)
    return False


LOGIC = ROOT / "src" / "clark" / "page" / "src" / "logic"

ENTRY = """export { cleanHtml, plainText, href, SanitiseError, MAX_CHARS } from %s;
export { ENTITIES, LEGACY, BAD_ADDRESS } from %s;
import { cleanHtml, plainText, SanitiseError } from %s;

// What a call gives, as data: the string, or {error: message} for a SanitiseError (Python's SanitiseError, as a value).
export function run(fn, x) {
  try { return fn(x); } catch (e) { if (e instanceof SanitiseError) return { error: e.message }; throw e; }
}

// items: [[input, expected clean, expected plain], ...], each expected a string or {error}. Returns the count and the first
// differences, so a failing test shows them.
export function compare(items, limit) {
  const same = (want, got) => (typeof want === "string" ? want === got : typeof got === "object" && got !== null && want.error === got.error);
  const bad = [];
  let count = 0;
  items.forEach((it, i) => {
    const c = run(cleanHtml, it[0]), p = it.length > 2 ? run(plainText, it[0]) : null;
    if (!same(it[1], c) || (it.length > 2 && !same(it[2], p))) {
      count += 1;
      if (bad.length < limit) bad.push({ i, input: it[0].slice(0, 300), want: it[1], got: c, wantPlain: it[2], gotPlain: p });
    }
  });
  return { count, bad, total: items.length };
}
"""


def bundle(tmp):
    """cleanHtml.js (and its tables) as one script defining `CH`, written into `tmp`; returns its text."""
    entry = Path(tmp) / "entry.js"
    q = lambda name: json.dumps(str(LOGIC / name))  # noqa: E731
    entry.write_text(ENTRY % (q("cleanHtml.js"), q("sanitiseTables.js"), q("cleanHtml.js")), encoding="utf-8")
    out = Path(tmp) / "clean.js"
    done = esbuild.run(["--bundle", "--format=iife", "--global-name=CH", "--target=es2020", "--tsconfig-raw={}", str(entry),
                        f"--outfile={out}"], cwd=ROOT / "src" / "clark" / "page" / "src", capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return out.read_text(encoding="utf-8")


class Page:
    """A Chrome tab holding the bundle (and, optionally, big data as a second script), from file://. Use as a context manager:
    `with Page(chrome, data={"CORPUS": [...]}) as p: p.ev("CH.compare(CORPUS, 20)")`, `chrome` being test_server.chrome."""

    def __init__(self, launch, data=None):
        self.launch = launch
        self.data = data or {}

    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory()
        tmp = Path(self.tmp.name)
        (tmp / "clean.js").write_text(bundle(tmp), encoding="utf-8")
        # ensure_ascii escapes every non-ASCII character, so the data is plain ASCII and valid JavaScript, lone surrogates included
        (tmp / "data.js").write_text("".join(f"window.{k} = {json.dumps(v)};\n" for k, v in self.data.items()), encoding="utf-8")
        (tmp / "page.html").write_text("<!doctype html><meta charset=utf-8><body><script src=clean.js></script>"
                                       "<script src=data.js></script></body>", encoding="utf-8")
        self.chrome = self.launch()
        self.cdp = self.chrome.__enter__()
        tid = next(t["targetId"] for t in self.cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        self.sid = self.cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        self.cdp.call("Page.enable", {}, self.sid)
        self.cdp.call("Page.navigate", {"url": (tmp / "page.html").as_uri()}, self.sid)
        ok = wait_for(lambda: self.cdp.js("typeof CH === 'object' && (" + " && ".join(f"window.{k} !== undefined" for k in self.data) + ")"
                                      if self.data else "typeof CH === 'object'", self.sid) is True, 60)
        assert ok, "the page's script did not load"
        return self

    def __exit__(self, *exc):
        self.chrome.__exit__(*exc)
        self.tmp.cleanup()

    def ev(self, expr):
        """`expr` evaluated in the page, by value (JSON-able results only)."""
        return self.cdp.js(expr, self.sid)

    def call(self, fn, value):
        """CH.run(CH.<fn>, value) for one value: the string, or {"error": message}."""
        return self.ev(f"CH.run(CH.{fn}, {json.dumps(value)})")
