"""#130 point 9: text is at least 12 px and targets are at least 24 px, across the page. Rules: Done-when on the planning repo #130.

Run: python3 dev/run_tests.py test_sizes
Loads the real page in headless Chrome (the #33 harness) with a small fictional project, opens Dashboard, Work items,
Milestones and Settings at 1400, 900 and 390 px, and fails on any visible text under 12 px or any visible button, link,
field or handle whose hit box is under 24 by 24 CSS px. The hit box is measured, not assumed: an element counts as big
enough when its own box is, or when it sits inside a larger box that takes the click for it (a label around a checkbox).
The allow-list is empty. Chrome is required: this test fails, never skips, without it.
"""
import json
import tempfile
import unittest

from _paths import SRC  # noqa: F401  (puts src/ on the path)

from clark import page, publish
from test_page import DATA as BASE, navigate
from test_server import Running, chrome, wait

ALLOWED = ()        # selectors exempt from the check; empty, and a new entry needs the Head's word

DATA = {"ABC": {**BASE["ABC"],
                "milestones": [{"id": "ABC-M-001", "name": "Pilot live", "baseline_date": "2030-03-01", "state": "On track", "status": "Planned"}],
                "actions": [{"id": "ABC-A-001", "description": "Agree the cut-over plan", "owner": "Sam", "due_date": "2030-01-10", "status": "Open"}],
                "raid": [{"id": "ABC-001", "type": "Risk", "description": "Supplier may deliver late", "owner": "Priya", "status": "Open"}],
                "decisions": [{"id": "ABC-D-001", "decision": "Use the shared calendar", "made_by": "Steering group", "status": "Made"}],
                "report_sections": [{"id": "current", "type": "current", "title": "Current state"},
                                    {"id": "glance", "type": "glance", "title": "At a glance"},
                                    {"id": "t1", "type": "text", "title": "Next steps", "body": "<p>Book the room.</p>"},
                                    {"id": "risks", "type": "raid", "title": "Risks and issues"},
                                    {"id": "ms", "type": "milestones", "title": "Milestones"}]}}

OPENERS = ".fbtn, .toc-lines, .newb, .top button:not(.tab), [aria-haspopup], [aria-expanded=false]"

# Runs in the page. Returns one line per offender: "<selector-ish> <what> <size>".
AUDIT = """(function (allowed) {
  var out = [];
  function visible(e) {
    var r = e.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) return false;
    for (var n = e; n && n.nodeType === 1; n = n.parentElement) {
      var s = getComputedStyle(n);
      if (s.display === 'none' || s.visibility === 'hidden' || parseFloat(s.opacity) === 0) return false;
      if (n.classList.contains('sr')) return false;
    }
    return true;
  }
  function name(e) { return e.tagName.toLowerCase() + (e.className && e.className.baseVal === undefined ? '.' + String(e.className).trim().split(/\\s+/).join('.') : '') + '[' + (e.textContent || e.getAttribute('aria-label') || e.getAttribute('title') || '').trim().slice(0, 24) + ']'; }
  function exempt(e) { return allowed.some(function (sel) { return e.matches(sel); }); }
  var all = document.querySelectorAll('body *');
  for (var i = 0; i < all.length; i++) {
    var e = all[i];
    if (exempt(e) || !visible(e)) continue;
    var own = false;
    for (var c = e.firstChild; c; c = c.nextSibling) if (c.nodeType === 3 && c.textContent.trim()) own = true;
    if (own) {
      var fs = parseFloat(getComputedStyle(e).fontSize);
      if (fs < 12) out.push(name(e) + ' text ' + fs + 'px');
    }
    var interactive = e.matches('a[href], button, input:not([type=hidden]), select, textarea, summary, [role=button], [role=menuitem], [role=tab], [role=link], [tabindex]:not([tabindex="-1"])');
    if (interactive) {
      var box = e.getBoundingClientRect(), w = box.width, h = box.height;
      var lab = e.closest('label');
      if (lab && (e.type === 'checkbox' || e.type === 'radio')) { var lr = lab.getBoundingClientRect(); w = Math.max(w, lr.width); h = Math.max(h, lr.height); }
      if (e.matches('.sr, [type=file]')) continue;
      if (w < 24 || h < 24) out.push(name(e) + ' target ' + Math.round(w) + 'x' + Math.round(h));
    }
  }
  return JSON.stringify(out);
})(%s)"""


VIEWS = (("dashboard", "#report"), ("work", "#work"), ("milestones", "#milestones"), ("settings", ".frame.empty"))


def published_page():
    """The published file's page (page-view.html) with its data block, as publish.render makes it but without the policy tag."""
    d = DATA["ABC"]
    text = page.page_html(tempfile.mkdtemp(), view=True).replace('<html lang="en-GB">', '<html lang="en-GB" data-mode="view">')
    block = publish.data_block({"data": {k: v for k, v in d.items() if k != "report_sections"}, "sections": d["report_sections"],
                                "tabs": [v for v, _ in VIEWS]}, "2030-01-01")
    i = text.rfind("</body>")
    return text[:i] + block + "\n" + text[i:]


class Sizes(unittest.TestCase):
    def audit(self, cdp, sid, where, hash_prefix, views, found):
        pause = {"expression": "new Promise(r => setTimeout(r, 400))", "awaitPromise": True}
        for view, ready in views:
            cdp.js(f"location.hash = '#{view}{hash_prefix}'", sid)
            self.assertTrue(wait(lambda: cdp.js(f"!!document.querySelector('{ready}')", sid)), f"{view} drew ({where})")
            cdp.call("Runtime.evaluate", pause, sid)
            audits = [("", json.loads(cdp.js(AUDIT % json.dumps(list(ALLOWED)), sid)))]
            # Each control that opens something (a filter list, the contents, a menu) is opened in turn and audited.
            for i in range(cdp.js("document.querySelectorAll(%s).length" % json.dumps(OPENERS), sid)):
                if not cdp.js("(function(){var b = document.querySelectorAll(%s)[%d]; if (!b || b.getBoundingClientRect().width < 1 || b.dataset.mode === 'view') return false; b.click(); return true;})()" % (json.dumps(OPENERS), i), sid):
                    continue
                cdp.call("Runtime.evaluate", pause, sid)
                audits.append((f" (opened #{i})", json.loads(cdp.js(AUDIT % json.dumps(list(ALLOWED)), sid))))
                cdp.js("document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true})); document.body.click()", sid)
            for how, got in audits:
                found += [f"{where} {view}{how}: {g}" for g in sorted(set(got))]

    def run_page(self, html, prefix, edit):
        s = Running(data_for=DATA.get, page_html=html)
        self.addCleanup(s.close)
        found = []
        with chrome() as cdp:
            sid = navigate(cdp, s.port, "#dashboard" + prefix)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#report')", sid)), "the page drew")
            for w in (1400, 900, 390):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": w < 600}, sid)
                self.audit(cdp, sid, f"{w}px", prefix, VIEWS, found)
                if edit:        # Edit shows the section handles and the add and options controls
                    cdp.js("location.hash = '#dashboard%s'; document.querySelector('[data-mode=edit]').click()" % prefix, sid)
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.handle')", sid)), "Edit shows the section handles")
                    self.audit(cdp, sid, f"{w}px edit", prefix, VIEWS[:1], found)
                    cdp.js("document.querySelector('[data-mode=view]').click()", sid)
        self.assertEqual(found, [], "every offender, by width and view:\n" + "\n".join(found))

    def test_the_app_has_text_of_12px_and_targets_of_24px_in_every_main_view_and_in_edit(self):
        self.run_page(lambda: page.page_html(tempfile.mkdtemp()), "&p=ABC", edit=True)

    def test_the_published_file_has_text_of_12px_and_targets_of_24px_in_every_view(self):
        self.run_page(published_page, "&p=ABC", edit=False)

    def test_the_page_with_no_project_open_has_targets_of_24px(self):
        s = Running(data_for=DATA.get, page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(s.close)
        found = []
        with chrome() as cdp:
            sid = navigate(cdp, s.port, "#dashboard")
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.frame.empty .link')", sid)), "the project list drew")
            for w in (1400, 390):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": w < 600}, sid)
                found += [f"{w}px: {g}" for g in json.loads(cdp.js(AUDIT % json.dumps(list(ALLOWED)), sid))]
        self.assertEqual(found, [], "\n".join(found))


if __name__ == "__main__":
    unittest.main()
