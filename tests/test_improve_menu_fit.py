"""#657: every line of the selection toolbar's Improve menu stays inside the menu, whatever its words (Polish's hint is the long one).

Run: python3 dev/run_tests.py test_improve_menu_fit
The prototype page (system/prototype/index.html, served from a thread, nothing written into the tree) in headless Chrome: Edit, the
"Where it stands" editor, a selection, then the bubble's Improve button opens the menu. For every row (and the row's name and hint)
the text is not wider than its box (scrollWidth <= clientWidth) and its right edge is not past the menu's right edge, and the menu is
inside the window. At 1400 and 900 px, light and dark, and at browser zoom 125% and 200% (the same window, bigger text).
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
DRIVER = """<script>window.__open = async (theme) => {
  const $ = s => document.querySelector(s), sleep = ms => new Promise(r => setTimeout(r, ms));
  await C.started;
  C.theme(theme);
  if (!C.UI.editing) { $('[data-mode=edit]').dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true })); await sleep(120); }
  C.closePop();
  if (!$('[data-cs] .ProseMirror')) { $('[data-cs]').dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true })); await sleep(200); }
  const pm = $('[data-cs] .ProseMirror'); pm.focus();
  const range = document.createRange(); range.selectNodeContents(pm.querySelector('p'));
  const sel = getSelection(); sel.removeAllRanges(); sel.addRange(range);
  document.dispatchEvent(new Event('selectionchange')); await sleep(400);
  $('.fmt-bubble [data-g=Improve]').dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true })); await sleep(120);
  return !!$('.menu');
};</script>"""
MEASURE = """(() => {
  const menu = document.querySelector('.menu'), m = menu.getBoundingClientRect(), bad = [];
  const rows = [...menu.querySelectorAll('[data-i]')];
  for (const row of rows) for (const el of [row, ...row.querySelectorAll('*')]) {
    const r = el.getBoundingClientRect(), what = (el.textContent || '').trim().slice(0, 40);
    if (el.scrollWidth > el.clientWidth + 0.5 && el.clientWidth) bad.push(['scrollWidth ' + el.scrollWidth + ' > clientWidth ' + el.clientWidth, el.tagName, what]);
    if (r.right > m.right + 0.5) bad.push(['right ' + r.right + ' > menu right ' + m.right, el.tagName, what]);
  }
  if (menu.scrollWidth > menu.clientWidth + 0.5) bad.push(['menu scrollWidth ' + menu.scrollWidth + ' > ' + menu.clientWidth, 'MENU', '']);
  if (m.left < 0 || m.right > innerWidth + 0.5) bad.push(['menu outside the window ' + m.left + ' to ' + m.right + ' of ' + innerWidth, 'MENU', '']);
  return { names: rows.map(r => r.textContent.trim().slice(0, 14)), width: m.width, bad };
})()"""


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.split("?")[0] == "/fit.html":
            page = (PROTO / "index.html").read_text(encoding="utf-8")
            body = page.replace("<head>", "<head>" + DRIVER, 1).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            super().do_GET()

    def log_message(self, *a):
        pass


class ImproveMenuFit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=str(PROTO)))
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def look(self, cdp, sid, width, zoom):
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": round(width / zoom), "height": 900, "deviceScaleFactor": zoom, "mobile": False}, sid)

    def test_no_row_of_the_improve_menu_is_wider_than_the_menu(self):
        with chrome() as cdp:
            tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
            sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
            cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, sid)
            cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.httpd.server_port}/fit.html"}, sid)
            for _ in range(100):
                if cdp.js("typeof window.__open === 'function' && typeof C !== 'undefined' && !!C.started", sid):
                    break
                cdp.call("Runtime.evaluate", {"expression": "new Promise(r => setTimeout(r, 100))", "awaitPromise": True}, sid)
            for zoom in (1, 1.25, 2):
                for width in (1400, 900):
                    for theme in ("light", "dark"):
                        with self.subTest(width=width, theme=theme, zoom=zoom):
                            self.look(cdp, sid, width, zoom)
                            res = cdp.call("Runtime.evaluate", {"expression": f"window.__open({json.dumps(theme)})", "awaitPromise": True,
                                                                 "returnByValue": True}, sid)["result"].get("value")
                            self.assertTrue(res, "the Improve menu opened")
                            got = cdp.js(MEASURE, sid)
                            self.assertEqual(len(got["names"]), 5, got["names"])
                            self.assertTrue(got["names"][-1].startswith("Polish"), got["names"])
                            self.assertEqual(got["bad"], [], f"menu width {got['width']}")


if __name__ == "__main__":
    unittest.main()
