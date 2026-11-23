"""Row 1272 (AP8): the callout's Edit fields draw their edge in the control-edge token, as Chrome computes it, at 1400 and 900 px, Classic, light and dark.

Read: the Category field and every toolbar button that is not switched on (a switched-on button draws the brand edge by design, .cb-btn[aria-pressed=true]).
The token's 3:1 ratio is pinned in test_tpl_callout_contrast_1272.py; this file pins that the fields USE the token. The expected colour is the token as the
page resolves it, drawn on a probe element, so the test follows the token, not a typed colour. The Title and Words fields are not read here: the approved
mock-up draws them borderless at rest on purpose (callout-approved.html, .pe-in and .pe .rt-view; hover shows --text-muted), and the product ruling of 24-11 keeps that look.
Run: python3 dev/run_tests.py test_tpl_callout_edge_1272   (needs Chrome). Fictional data only.
"""
import json
import unittest

import _tpl_notes as n
from _classic_page import classic
from test_changes import KIND
from test_report_editor import Base
from test_server import chrome

BODY = {"v": 1, "title": "Fictional title", "paras": ["Fictional words."], "category": "Budget", "colour": "violet", "icon": "info"}
PROBE = "(() => { const d = document.createElement('div'); d.style.cssText = 'border:1px solid var(--control-edge)'; document.body.appendChild(d); const c = getComputedStyle(d).borderTopColor; d.remove(); return c; })()"


def edges(ref):
    sec = f"[data-id={json.dumps(ref)}] .cb"
    return f"""(() => {{ const out = {{}}, off = [], on = [], seen = [];
  const cat = document.querySelector({json.dumps(sec + " [aria-label=Category]")});
  const all = [...document.querySelectorAll({json.dumps(sec + " .cb-btn")})];
  for (const b of all) {{ const sel = b.getAttribute('aria-pressed') === 'true' || b.getAttribute('aria-checked') === 'true';
    const cs = getComputedStyle(b); const e = [cs.borderTopColor, cs.borderRightColor, cs.borderBottomColor, cs.borderLeftColor, cs.borderTopWidth, cs.borderTopStyle];
    (sel ? on : off).push([b.getAttribute('aria-label') || b.textContent, e]); }}
  const cc = getComputedStyle(cat);
  return {{ cat: cat ? [cc.borderTopColor, cc.borderRightColor, cc.borderBottomColor, cc.borderLeftColor, cc.borderTopWidth, cc.borderTopStyle] : null, off, on }}; }})()"""


class Edge(Base):
    def make(self):
        from _demo import USER
        with self.store.step("dashboard", USER) as st:
            ref = st.create("report_sections", {"project": "ABC", "type": "callout", "title": "Fictional callout", "sort_order": 999})
        status, got = self.real_change({"project": "ABC", "kind": KIND, "op": "update", "id": ref, "changes": {"body": json.dumps(BODY)}})
        assert status == 200, got
        return ref

    def read(self, width, scheme):
        ref = self.make()
        with chrome() as cdp:
            p = self.visit(cdp)
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, p.sid)
            p.js(f"document.documentElement.setAttribute('data-theme', {json.dumps(scheme)}); true")
            p.edit()
            p.until(f"!!document.querySelector('[data-id={json.dumps(ref)}] .cb .cb-in')", "the callout in Edit")
            return p.js(PROBE), p.js(edges(ref))

    def check(self, width, scheme):
        want, got = self.read(width, scheme)
        tag = f"{width} {scheme}"
        self.assertNotEqual(want, "rgba(0, 0, 0, 0)", tag)
        self.assertIsNotNone(got["cat"], tag)
        self.assertEqual(got["cat"], [want] * 4 + ["1px", "solid"], f"{tag}: the Category field")
        self.assertGreaterEqual(len(got["off"]), 5, f"{tag}: the toolbar buttons that are off are read")
        for label, e in got["off"]:
            self.assertEqual(e, [want] * 4 + ["1px", "solid"], f"{tag}: the button {label!r}")
        self.assertGreaterEqual(len(got["on"]), 1, f"{tag}: a switched-on button is in the toolbar")
        self.assertNotIn(want, [e[0] for _, e in got["on"]], f"{tag}: a switched-on button draws the brand edge, not the control edge")


def add(width, scheme):
    def t(self):
        classic(self)
        self.check(width, scheme)
    t.__name__ = f"test_the_callout_edit_field_edges_are_the_control_edge_at_{width}_{scheme}"
    return t


for w in (1400, 900):
    for s in ("light", "dark"):
        f = add(w, s)
        setattr(Edge, f.__name__, f)


if __name__ == "__main__":
    unittest.main()
