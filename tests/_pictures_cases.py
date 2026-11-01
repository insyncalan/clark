"""The page tests the Pictures group's templates share (#96): a section of one type added to the demo store, View drawing it at
1400 and 900 px in light and dark, and Edit adding a picture through the real route with one Undo. Fictional data only."""
import base64
import json
import sqlite3

from _demo import USER
from clark import changes
from test_report_editor import Base as PageBase
from test_server import chrome

CANVAS_FILE = """(async () => {{
  const c = document.createElement('canvas'); c.width = {w}; c.height = {h};
  const g = c.getContext('2d'); g.fillStyle = 'rgb(40,90,160)'; g.fillRect(0, 0, {w}, {h});
  const blob = await new Promise(r => c.toBlob(r, 'image/png'));
  const dt = new DataTransfer(); dt.items.add(new File([blob], 'fictional.png', {{ type: 'image/png' }}));
  const input = document.querySelector({sel}); input.files = dt.files;
  input.dispatchEvent(new Event('change', {{ bubbles: true }}));
}})()"""


class PicturePage(PageBase):
    KIND = None

    def setUp(self):
        super().setUp()
        self.s.httpd.section_image = changes.make_section_image(self.store.path, [], USER)

    def add(self, body=None, title="Fictional pictures", hidden=0):
        with self.store.step("dashboard", USER) as st:
            ref = st.create("report_sections", {"project": "ABC", "type": self.KIND, "title": title, "sort_order": 999, "hidden": hidden})
        if body is not None:
            with self.store.step("dashboard", USER) as st:
                st.update("report_sections", ref, {"body": json.dumps(body)})
        return ref

    def body(self, ref):
        row = next(r for r in self.store.read("report_sections", "ABC") if r["id"] == ref)
        return json.loads(row["body"]) if row["body"] else {}

    def applies(self):
        con = sqlite3.connect(str(self.store.path))
        try:
            return con.execute("SELECT count(*) FROM applies").fetchone()[0]
        finally:
            con.close()

    def drop_file(self, p, selector, w=2400, h=1200):
        p.js(CANVAS_FILE.format(w=w, h=h, sel=json.dumps(selector)))

    def width_of(self, data_url):
        raw = base64.b64decode(data_url.split(",", 1)[1])
        if raw[:8] == b"\x89PNG\r\n\x1a\n":
            return int.from_bytes(raw[16:20], "big")
        return None

    def at_widths(self, cdp, p, sel, inner):
        """At 1400 and 900 px, light and dark: the section fits its box and `inner` fits inside it."""
        for width in (1400, 900):
            for theme in ("light", "dark"):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                p.js(f"document.documentElement.dataset.theme = {json.dumps(theme)}")
                box = p.js(f"(function(){{var s=document.querySelector('{sel}'), r=s.getBoundingClientRect();"
                           f"var ok=[...s.querySelectorAll({json.dumps(inner)})].every(e => {{var i=e.getBoundingClientRect(); return i.right <= r.right + 1 && i.left >= r.left - 1;}});"
                           "return {fits: s.scrollWidth <= s.clientWidth + 1, ok: ok};})()")
                self.assertTrue(box["fits"] and box["ok"], (width, theme, box))

    def chrome(self):
        return chrome()
