"""WorkFilters hunt 15: the open filter box keeps the focus when a tick drops its field, and stays inside the window at both edges.

Run: python3 -B -m unittest test_work_filters_box (from tests/, with PYTHONPATH=../src:../vendor). Browser test: needs Chrome.
The component is mounted on its own (bundled by the pinned esbuild) in headless Chrome at 1400 and 900 px.
"""
import contextlib
import http.server
import tempfile
import threading
import unittest
from pathlib import Path

from _paths import ROOT, SRC  # noqa: F401
import build_page  # noqa: E402
import esbuild  # noqa: E402
from test_server import chrome, wait  # noqa: E402
from test_work_filters import PAGE_SRC, click, need_chrome  # noqa: E402
from test_work_items import page_target  # noqa: E402

ENTRY = f'''import {{ render }} from "preact"; import {{ FilterBar }} from "{PAGE_SRC / "components" / "WorkFilters.jsx"}";
import {{ data, openFilter }} from "{PAGE_SRC / "stores" / "report.js"}"; import {{ setFilterState }} from "{PAGE_SRC / "stores" / "report.js"}";
import {{ decode }} from "{PAGE_SRC / "filters.js"}";
window.draw = () => {{
  data.value = {{ actions: [{{ id: "A-1", status: "Open", description: "one", owner: "Owner A", priority: "High", due_date: "2026-12-01" }}], raid: [], decisions: [], milestones: [], use_cases: [] }};
  render(<FilterBar />, document.getElementById("host"));
}};
window.start = (text) => setFilterState(decode(text));
window.openIt = (f) => {{ openFilter.value = f; }};
'''


CSS = "\n".join(ln for ln in (PAGE_SRC.parent / "shell.css").read_text(encoding="utf-8").splitlines() if ln.startswith((".fbar", ".fwrap", ".fbtn", ".fbox")))


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"<!doctype html><meta charset=utf-8><style>" + CSS.encode() + b"</style><body style='margin:0'><div id=host></div>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


class WorkFiltersBox(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        need_chrome()
        entry = Path(tempfile.mkdtemp()) / "entry.jsx"
        entry.write_text(ENTRY, encoding="utf-8")
        out = entry.parent / "bar.js"
        done = esbuild.run(["--bundle", "--format=iife", "--tsconfig-raw={}", *build_page.preact_flags(), str(entry), f"--outfile={out}"], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        cls.script = out.read_text(encoding="utf-8")
        cls.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def mount(self, cdp, width):
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.httpd.server_port}/"}, sid)
        wait(lambda: cdp.js("!!document.getElementById('host')", sid))
        res = cdp.call("Runtime.evaluate", {"expression": self.script + ";draw(); true", "returnByValue": True}, sid)
        self.assertNotIn("exceptionDetails", res, res)
        return sid

    def test_unticking_the_last_value_of_a_field_that_leaves_the_bar_keeps_the_focus_inside_the_filters(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.mount(cdp, width)
                js = lambda e: cdp.js(e, sid)
                js("start('reviewed:stale')")
                self.assertTrue(wait(lambda: js("!!document.querySelector('[data-fb=reviewed]')")), "an active Freshness filter is offered")
                click(cdp, sid, "[data-fb=reviewed]")
                self.assertTrue(wait(lambda: js("!!document.querySelector('#fbox-reviewed input')")))
                click(cdp, sid, "#fbox-reviewed input[value=stale]")          # untick: Freshness is no longer active, and no row has a date for it
                self.assertTrue(wait(lambda: js("!document.querySelector('#fbox-reviewed input[value=stale]:checked')")))
                self.assertTrue(wait(lambda: js("!!document.activeElement && document.activeElement !== document.body")), "the focus did not fall to the page")
                self.assertTrue(js("!!document.activeElement.closest('.fbar')"), "the focus is still in the filters")

    def test_a_box_that_must_turn_to_the_right_edge_does_not_then_run_off_the_left(self):
        # At 900 px a box wider than its room both runs off the right (so it turns to the right edge) and, turned, off the left: drawn here by widening the box and moving the bar in from the left, not by narrowing the window.
        with chrome() as cdp:
            sid = self.mount(cdp, 900)
            js = lambda e: cdp.js(e, sid)
            js("(() => { const s = document.createElement('style'); s.textContent = '.fbox { width: 700px; }'; document.head.appendChild(s); document.getElementById('host').style.marginLeft = '300px'; })()")
            click(cdp, sid, "[data-fb=workstream]")
            self.assertTrue(wait(lambda: js("!!document.querySelector('.fbox')")))
            r = js("(() => { const b = document.querySelector('.fbox').getBoundingClientRect(); return [b.left, b.right, innerWidth]; })()")
            self.assertGreaterEqual(r[0], 8, f"left edge {r}")
            self.assertLessEqual(r[1], r[2], f"right edge {r}")


if __name__ == "__main__":
    unittest.main()
