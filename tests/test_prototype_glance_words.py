"""#669: the prototype's At a glance tiles say the build's words and look (white tile with a thin outline, no tint).

Run: python3 dev/run_tests.py test_prototype_glance_words
The words are read from the page's own glanceData; the look is the computed style of the drawn tiles, in light and dark.
Chrome is required: the test fails, never skips, without it.
"""
import functools
import http.server
import json
import threading
import unittest

from _paths import ROOT
from test_server import chrome

PROTO = ROOT / "system" / "prototype"


class PrototypeGlance(unittest.TestCase):
    def test_words_are_the_builds(self):
        js = (PROTO / "views.js").read_text(encoding="utf-8")
        for w in ("of 1 open risk or issue", "of ${openRI} open risks and issues", "${D.plural(openA, 'open action')}", "None high", "None open", "Oldest needed by ${D.fd(",
                  "No date set", "None waiting", "No open actions"):
            self.assertIn(w, js, w)
        for old in ("red or urgent", "None red", "Oldest ${"):
            self.assertNotIn(old, js, old)

    def test_risks_colour_does_not_use_the_red_count(self):
        js = (PROTO / "views.js").read_text(encoding="utf-8")
        line = next(x for x in js.splitlines() if "k: 'High risks and issues'" in x)
        self.assertIn("rag: high.length ? 'R' : openRI ? 'A' : 'G'", line)

    def test_no_stale_plural(self):
        js = (PROTO / "views.js").read_text(encoding="utf-8")
        self.assertNotIn("open actions`", js.split("overdue:")[1].split("risks:")[0])


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


WORDS = """(async () => {
  await C.started;
  const D = window.ClarkDB, p = D.S.projects.find(x => x.code === C.UI.code), all = D.S.items, mine = all.filter(x => x.code === p.code && !x.archived);
  const open = mine.filter(x => x.type === 'A' && C.isOpen(x)), out = {};
  try {
    D.S.items = open.slice(0, 1); out.one = C.glanceData(p).overdue.d;
    D.S.items = open.slice(0, 2); out.two = C.glanceData(p).overdue.d;
    D.S.items = []; out.none = C.glanceData(p).overdue.d;
  } finally { D.S.items = all; }
  return out;
})()"""
LOOK = """(() => {
  const out = {};
  for (const t of document.querySelectorAll('.glance .fig.go')) { const s = getComputedStyle(t); out[t.dataset.fig] = { rag: t.className.match(/rag-\\w/)[0], bg: s.backgroundColor, border: s.borderTopWidth + ' ' + s.borderTopStyle, hero: !!t.closest('.hero-tiles') }; }
  return { tiles: out, surface: getComputedStyle(document.body).getPropertyValue('--surface').trim() };
})()"""


class PrototypeGlanceLook(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=str(PROTO)))
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def test_words_and_look_in_the_drawn_page(self):
        with chrome() as cdp:
            tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
            sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
            cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.httpd.server_port}/index.html"}, sid)
            for _ in range(100):
                if cdp.js("typeof C !== 'undefined' && !!C.started && !!document.querySelector('.glance .fig.go')", sid):
                    break
                cdp.call("Runtime.evaluate", {"expression": "new Promise(r => setTimeout(r, 100))", "awaitPromise": True}, sid)
            words = cdp.call("Runtime.evaluate", {"expression": WORDS, "awaitPromise": True, "returnByValue": True}, sid)["result"]["value"]
            self.assertEqual(words, {"one": "of 1 open action", "two": "of 2 open actions", "none": "No open actions"})
            for theme, bg in (("light", "rgb(255, 255, 255)"), ("dark", "rgb(23, 33, 44)")):
                cdp.call("Runtime.evaluate", {"expression": f"C.theme({json.dumps(theme)})", "returnByValue": True}, sid)
                cdp.call("Runtime.evaluate", {"expression": "new Promise(r => setTimeout(r, 400))", "awaitPromise": True}, sid)
                got = cdp.js(LOOK, sid)["tiles"]
                self.assertTrue(got, "tiles are drawn")
                for key, t in got.items():
                    if t["hero"]:
                        continue
                    with self.subTest(theme=theme, tile=key):
                        self.assertEqual(t["bg"], bg, "a white tile (the page surface) whatever its colour: " + t["rag"])
                        self.assertEqual(t["border"], "1px solid")


if __name__ == "__main__":
    unittest.main()
