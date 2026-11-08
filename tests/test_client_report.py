"""#192 Client Requested Report View: the new page beside the Dashboard, Work items and Milestones.

Run: python3 dev/run_tests.py test_client_report
Source tests (no browser) pin the view's id and name, the fixed order of its sections, that the published file's tab list carries it
(the file's own checks are in test_client_report_file), the cover band, that the page says nothing to its author and explains nothing
(the client reads it), and that its look uses tokens only. The browser tests (class Drawn, added with the sections) draw the page from the real
server at 1400 and 900 px, light and dark (View; from #559 the client report is drawn from the published file).
"""
import json
import re
import shutil
import tempfile
import unittest

from _paths import ROOT, SRC

from pathlib import Path

from clark import page, publish
from test_publish import EMPTY_BRANDING, opened
from test_server import Running, chrome, wait
from test_work_items import FIXED_DATE, bundled, load_demo, page_target

PAGE = SRC / "clark" / "page"
SRCDIR = PAGE / "src"


def text(*parts):
    return (SRCDIR.joinpath(*parts)).read_text(encoding="utf-8")


class Source(unittest.TestCase):
    def test_the_view_has_an_id_a_name_and_a_page(self):
        self.assertRegex(text("router.js"), r'export const VIEWS = \["dashboard", "work", "milestones", "usecases", "gantt", "clientreport", "settings"\]')
        self.assertIn('"Client Requested Report View"', text("stores", "report.js"))   # the name stays in the store; the served page does not offer the tab (#559)
        self.assertIn('fromFile.value ? "Weekly snapshot"', text("stores", "report.js"), "a client has not asked for anything: the file's tab has its own name")
        app = text("components", "App.jsx")
        self.assertIn('clientreport: ClientReport', app)
        self.assertIn('import { ClientReport } from "./ClientReport.jsx"', app)

    def test_the_sections_come_in_one_fixed_order(self):
        body = text("components", "ClientReport.jsx")
        ids = re.findall(r'\{ id: "(\w+)", title: "([^"]+)", slot: "(\w+)"', body)
        self.assertEqual(ids, [("progress", "Overall progress", "full"), ("plans", "Progress by plan", "full"),
                               ("highlights", "Highlights", "left"),
                               ("nextweek", "Planned for next week", "right"), ("raid", "Risks, delays and items to watch", "full")])

    def test_the_cover_line_never_invents_a_client(self):
        body = text("components", "ClientReport.jsx")
        self.assertIn("WEEKLY PROGRESS SNAPSHOT", body)
        self.assertRegex(body, r'client \? ` · for \$\{client\}` : ""')

    def test_the_status_date_is_the_week_ending_then_the_published_date_then_today(self):
        body = text("components", "ClientReport.jsx")
        self.assertRegex(body, r"project\.week_ending")
        self.assertRegex(body, r"isFile && asAtValue \? asAtValue : todayIso\(\)")

    def test_the_published_file_gets_a_tab_for_it_unless_the_milestones_are_hidden(self):
        pub = (SRC / "clark" / "publish.py").read_text(encoding="utf-8")
        self.assertRegex(pub, r'if "milestones" not in hidden_types:[^\n]*\n\s+tabs\.append\("clientreport"\)')

    def test_nothing_unfinished_shows_and_the_delivery_plan_is_not_built(self):
        self.assertFalse((SRCDIR / "components" / "clientreport" / "Delivery.jsx").exists(), "the delivery template (on hold) has no file and no placeholder")
        body = text("components", "ClientReport.jsx")
        self.assertNotIn("Delivery", body)
        css = (PAGE / "shell.css").read_text(encoding="utf-8")
        self.assertNotIn("cr-placeholder", css)

    def test_a_not_set_prompt_is_only_ever_drawn_in_edit(self):
        # the client's page (a file, and the View) shows nothing rather than a placeholder: every "Not set" or "No milestones yet" in the
        # view's parts sits behind the Edit check, and a part with nothing to say is left out by sectionsShown
        for rel in ("clientreport/Overall.jsx", "clientreport/Plans.jsx"):
            code = re.sub(r"//[^\n]*", "", text("components", *rel.split("/")))
            for line in code.splitlines():
                if re.search(r"Not set|No milestones yet", line):
                    self.assertTrue(re.search(r"editing|mode\.value", line) or "overall ||" in line or "overall ?" in line or "health ||" in line,
                                    f"{rel}: a prompt not behind Edit: {line.strip()}")
        body = text("components", "ClientReport.jsx")
        self.assertIn("sectionsShown(", body)
        self.assertNotIn("There are no", text("components", "ClientReport.jsx"))

    def test_no_author_instruction_and_no_explainer_on_the_page(self):
        # The owner's rule: the client reads this page. No sentence tells the author to go and write something, none says how a
        # figure is worked out, none says something is not built. (The editor's own placeholder in Edit is a control.)
        for rel in ("ClientReport.jsx", "clientreport/Overall.jsx", "clientreport/Plans.jsx", "clientreport/Pair.jsx", "clientreport/Risks.jsx"):
            code = re.sub(r"//[^\n]*", "", text("components", *rel.split("/")))
            for bad in (r"on the Dashboard", r"Add a ", r"Write it", r"Nothing written", r"Nothing here yet", r"not built", r"counts the same",
                        r"fills in once", r"worked out", r"cr-how", r"placeholder", r"is the project's milestones", r"Escalate"):
                self.assertNotRegex(code, bad, rel)

    def test_a_risk_row_draws_no_item_number_and_no_escalate_line(self):
        # ruling on the 0.5.0 hand-check (step 14): the client view, in View and in the published file, leaves out the row's id
        # ("TUL-010" at the right of each row) and the "Escalate: Yes" line. Neither is drawn in any mode.
        code = re.sub(r"//[^\n]*", "", text("components", "clientreport", "Risks.jsx"))
        for bad in (r">\s*\{r\.id\}\s*<", r"Escalate", r"escalate", r"cr-esc", r"wl-id", r"idl", r"data-id"):
            self.assertNotRegex(code, bad, "Risks.jsx draws " + bad)
        css = (PAGE / "shell.css").read_text(encoding="utf-8")
        block = css[css.index(".cr-wl {"):css.index("/* The Use Cases tab of a published file")]
        for bad in ("cr-esc", "wl-id", ".idl"):
            self.assertNotIn(bad, block, "the look of a part that is no longer drawn is gone")

    def test_the_cover_is_a_dark_band_with_the_title_the_week_line_a_picture_and_a_logo(self):
        body = text("components", "ClientReport.jsx")
        self.assertRegex(body, r'<header class="cr-band">\s*<h1>\{d\.project\.name\}</h1>\s*<p class="cr-cover">')
        css = (PAGE / "shell.css").read_text(encoding="utf-8")
        band = re.search(r"\.cr-band \{[^}]*\}", css).group(0)
        self.assertIn("background: var(--brand-navy)", band)
        self.assertIn("var(--image-cover)", css[css.index(".cr-band::before"):])
        self.assertIn("var(--image-logo)", css[css.index(".cr-band::after"):])
        self.assertIn("--image-logo: none", (SRC / "clark" / "brand" / "tokens.css").read_text(encoding="utf-8"), "no logo of anyone's is in the repository")

    def test_the_look_is_tokens_only(self):
        css = (PAGE / "shell.css").read_text(encoding="utf-8")
        block = re.sub(r"/\*.*?\*/", "", css[css.index("/* ===== Client Requested Report View (item 192)"):], flags=re.S)
        self.assertNotRegex(block, r"#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(", "colours come from the tokens")
        self.assertNotRegex(block, r"font-size:\s*(?:\d|1[0-2])px", "13 px is the floor")


SECTION_ORDER = ["progress", "plans", "highlights", "nextweek", "raid"]
MODULE = SRCDIR / "logic" / "clientReport.js"


def ms(id, name, **kw):
    base = {"id": id, "name": name, "status": "Planned", "baseline_date": None, "forecast_date": None, "actual_date": None,
            "state": None, "state_set": 0, "archived": 0, "sort_order": 0, "client_visible": 1, "percent_complete": None, "workstream": None}
    base.update(kw)
    return base


# Every shape the figures care about, as at the date below.
LIST = [ms("M-1", "Kick-off", status="Done", baseline_date="2026-10-01", actual_date="2026-10-02", workstream="Build"),
        ms("M-2", "Half built", baseline_date="2026-10-10", percent_complete=40, workstream="Build"),
        ms("M-3", "No date yet", forecast_date="2027-01-10"),
        ms("M-4", "Dropped", status="Cancelled", baseline_date="2026-10-05", workstream="Build"),
        ms("M-5", "Hidden away", baseline_date="2026-10-05", archived=1, workstream="Build")]
# Every way a milestone is kept from the client (logic/publishable.js, the page's mirror of publish.select): none may show or count.
HIDDEN = [ms("M-6", "Not for the client", baseline_date="2026-10-05", client_visible=0, workstream="Build"),
          ms("M-7", "Left out of the report", baseline_date="2026-10-05", workstream="Build"),
          ms("M-8", "Marked Sensitive", baseline_date="2026-10-05", workstream="Build"),
          ms("M-9", "Excluded by a label", baseline_date="2026-10-05", workstream="Build")]
DATA = {"project": {"code": "ABC"}, "report_hidden": [{"item_id": "M-7"}], "labels": {"M-8": ["Sensitive"], "M-9": ["Internal"]},
        "label_rules": [{"name": "Internal", "behaviour": "exclude"}], "report_sections": []}
ON = "2026-10-20"


class Logic(unittest.TestCase):
    """logic/clientReport.js in Chrome: what each number on the page means."""

    @classmethod
    def setUpClass(cls):
        cls.script = bundled(MODULE, "CR")

    def run_js(self, expr):
        with chrome() as cdp:
            sid = page_target(cdp)
            cdp.call("Page.navigate", {"url": "about:blank"}, sid)
            return json.loads(cdp.js(self.script + ";JSON.stringify(" + expr + ")", sid))

    def test_lines_groups_and_totals(self):
        got = self.run_js(f"CR.progress({json.dumps(LIST)}, {json.dumps(ON)}, false)")
        self.assertEqual([g["name"] for g in got["groups"]], ["Build", "Other milestones"], "cancelled and archived are left out; no workstream is Other")
        build, other = got["groups"]
        self.assertEqual([(l["no"], l["text"], l["planned"], l["achieved"], l["behind"]) for l in build["lines"]],
                         [(1, "Kick-off", 100, 100, 0), (2, "Half built", 100, 40, 60)])
        self.assertEqual((other["lines"][0]["planned"], other["lines"][0]["achieved"], other["lines"][0]["behind"]), (None, None, 0),
                         "no agreed date is no planned figure; no percent is not set")
        self.assertEqual(build["total"], {"actual": 70, "planned": 100})
        self.assertEqual(other["total"], {"actual": 0, "planned": 0})
        self.assertEqual(got["overall"], {"actual": 47, "planned": 67}, "every line counts the same, across all groups")

    def test_a_hidden_milestone_never_shows_and_never_moves_a_figure(self):
        rules = f"CR.clientRules({json.dumps(DATA)})"
        with_hidden = self.run_js(f"CR.progress({json.dumps(LIST + HIDDEN)}, {json.dumps(ON)}, true, {rules})")
        without = self.run_js(f"CR.progress({json.dumps(LIST)}, {json.dumps(ON)}, true, {rules})")
        self.assertEqual(with_hidden, without, "hidden milestones change nothing the client sees")
        names = [l["text"] for g in with_hidden["groups"] for l in g["lines"]]
        for gone in ("Not for the client", "Left out of the report", "Marked Sensitive", "Excluded by a label"):
            self.assertNotIn(gone, names)
        hidden_section = dict(DATA, report_sections=[{"type": "milestones", "hidden": 1}])
        self.assertEqual(self.run_js(f"CR.progress({json.dumps(LIST)}, {json.dumps(ON)}, true, CR.clientRules({json.dumps(hidden_section)}))"),
                         {"overall": None, "groups": []}, "a hidden Milestones section leaves no milestone on this page")

    def test_a_hidden_text_section_is_never_the_source_of_the_pair(self):
        secs = [{"id": "S-1", "type": "text", "title": "This week", "hidden": 1}, {"id": "S-2", "type": "text", "title": "Highlights", "hidden": 0},
                {"id": "S-3", "type": "text", "title": "Next week", "hidden": 0}]
        self.assertEqual(self.run_js(f"CR.sectionFor({json.dumps(secs)}, /highlight|this week/i, []).id"), "S-2", "the owner hid S-1")
        self.assertIsNone(self.run_js(f"CR.sectionFor({json.dumps(secs)}, /next week/i, [{{'item_id': 'S-3'}}])"), "S-3 is left out of the report")

    def test_the_end_date_is_the_achieved_date_then_the_forecast_then_the_agreed_date(self):
        got = self.run_js(f"CR.progress({json.dumps(LIST)}, {json.dumps(ON)}, false).groups.map(g => g.lines.map(l => l.end))")
        self.assertEqual(got, [["2026-10-02", "2026-10-10"], ["2027-01-10"]])

    def test_no_milestones_is_no_figures_and_one_group_name_when_none_has_a_workstream(self):
        self.assertEqual(self.run_js("CR.progress([], '2026-10-20', false)"), {"overall": None, "groups": []})
        got = self.run_js(f"CR.progress({json.dumps([ms('M-9', 'Alone', baseline_date='2026-12-01')])}, '2026-10-20', false)")
        self.assertEqual([g["name"] for g in got["groups"]], ["Milestones"])
        self.assertEqual(got["overall"], {"actual": 0, "planned": 0})

    def test_the_gap_in_words(self):
        got = self.run_js("[CR.gapWords({actual: 49, planned: 50}), CR.gapWords({actual: 50, planned: 50}), CR.gapWords({actual: 55, planned: 50}),"
                          " CR.gapWords({actual: 10, planned: 12}), CR.gapWords(null), CR.behindWords(1), CR.behindWords(3)]")
        self.assertEqual(got, ["1 point behind plan", "On plan", "5 points ahead of plan", "2 points behind plan", "", "1 point behind plan", "3 points behind plan"])

    def test_the_rules_never_read_the_clock_or_the_page(self):
        body = MODULE.read_text(encoding="utf-8")
        for bad in ("new Date()", "Date.now", "document.", "window.", "fetch("):
            self.assertNotIn(bad, body)


TEXT_ROW = {"id": "ABC-S-001", "type": "text", "title": "Notes", "body": "", "beside": 0, "hidden": 0, "sort_order": 1}
OPEN_ACTION = {"id": "ABC-A-001", "project": "ABC", "archived": 0, "client_visible": 1, "status": "Open", "due_date": "2030-01-01",
               "description": "Fictional"}


class DeletedBuiltIns(unittest.TestCase):
    """Row 906: on the live page a built-in section with no row is left out as publish.hidden_types leaves it out, once the
    project has other section rows or has had them all deleted; a project with no rows yet and none deleted keeps the defaults."""

    CASES = (("other rows", [TEXT_ROW], False, False), ("all deleted", [], True, False), ("no rows yet", [], False, True))

    @classmethod
    def setUpClass(cls):
        tpl = SRCDIR / "templates"
        cls.script = ";".join((bundled(MODULE, "CR"), bundled(tpl / "figures.js", "FG"), bundled(tpl / "workItemsList.js", "WL")))

    def run_js(self, expr):
        with chrome() as cdp:
            sid = page_target(cdp)
            cdp.call("Page.navigate", {"url": "about:blank"}, sid)
            return json.loads(cdp.js(self.script + ";JSON.stringify(" + expr + ")", sid))

    def test_the_risks_part_follows_publish(self):
        for name, sections, deleted, want in self.CASES:
            with self.subTest(name):
                self.assertEqual("raid" not in publish.hidden_types(sections, deleted), want, "publish agrees")
                self.assertEqual(self.run_js(f"CR.raidShown({json.dumps(sections)}, false, {json.dumps(deleted)})"), want)
                d = {"project": {"code": "ABC"}, "report_sections": sections, "sections_deleted": 1 if deleted else 0, "milestones": []}
                self.assertEqual("raid" in self.run_js(f"CR.sectionsShown({json.dumps(d)}, false, false, {json.dumps(ON)})"), want,
                                 "sectionsShown passes the data's sections_deleted")
        hidden = [dict(TEXT_ROW, id="ABC-S-002", type="raid", hidden=1)]
        self.assertFalse(self.run_js(f"CR.raidShown({json.dumps(hidden)}, false, false)"), "a hidden Risks section is left out")
        self.assertTrue(self.run_js(f"CR.raidShown({json.dumps([dict(hidden[0], hidden=0)])}, false, true)"), "a shown Risks section is drawn")
        self.assertEqual(self.run_js("[CR.raidShown([], true, true), CR.raidShown([], true, false)]"), [False, False],
                         "a file with no Risks section has it hidden, whatever the flag")

    def test_the_live_figures_and_the_work_items_list_follow_publish(self):
        for name, sections, deleted, want in self.CASES:
            with self.subTest(name):
                self.assertEqual("actions" not in publish.hidden_types(sections, deleted), want, "publish agrees")
                d = {"project": {"code": "ABC"}, "report_sections": sections, "sections_deleted": 1 if deleted else 0, "actions": [OPEN_ACTION],
                     "raid": [], "decisions": [], "report_hidden": [], "labels": {}, "label_rules": []}
                self.assertEqual("overdue" in self.run_js(f"FG.liveFigures({json.dumps(d)}, '2030-01-15')"), want, "Key figures")
                self.assertEqual(self.run_js(f"WL.publishedOnly({json.dumps(d)}).actions.map(r => r.id)"), ["ABC-A-001"] if want else [],
                                 "the work items list")


# Runs in the page. One line per offender: text under 13 px, or text under 4.5:1 against what is behind it.
AUDIT = """(function () {
  function lum(c) { var a = c.map(function (v) { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); }); return .2126 * a[0] + .7152 * a[1] + .0722 * a[2]; }
  function rgba(s) { var m = s.match(/rgba?\\(([^)]+)\\)/); if (!m) return null; var p = m[1].split(/[ ,\\/]+/).map(Number); return { c: p.slice(0, 3), a: p.length > 3 ? p[3] : 1 }; }
  function over(f, b) { return f.a >= 1 ? f.c : f.c.map(function (v, i) { return v * f.a + b[i] * (1 - f.a); }); }
  function back(e) { for (var n = e; n; n = n.parentElement) { var c = rgba(getComputedStyle(n).backgroundColor); if (c && c.a > 0) return over(c, [255, 255, 255]); } return [255, 255, 255]; }
  function ratio(a, b) { var x = lum(a), y = lum(b); return (Math.max(x, y) + .05) / (Math.min(x, y) + .05); }
  function visible(e) { var r = e.getBoundingClientRect(); if (r.width < 1 || r.height < 1) return false;
    for (var n = e; n && n.nodeType === 1; n = n.parentElement) { var s = getComputedStyle(n); if (s.display === 'none' || s.visibility === 'hidden' || n.classList.contains('sr')) return false; } return true; }
  var out = [], root = document.querySelector('#clientreport');
  [].slice.call(root.querySelectorAll('*')).forEach(function (e) {
    if (!visible(e)) return;
    var own = false; for (var c = e.firstChild; c; c = c.nextSibling) if (c.nodeType === 3 && c.textContent.trim()) own = true;
    if (!own) return;
    var s = getComputedStyle(e), fs = parseFloat(s.fontSize), t = (e.textContent || '').trim().slice(0, 24);
    if (fs < 13) out.push(e.tagName + '[' + t + '] text ' + fs + 'px');
    var f = rgba(s.color), b = back(e);
    if (f) { var r = ratio(over(f, b), b); if (r < 4.5) out.push(e.tagName + '[' + t + '] contrast ' + r.toFixed(2)); }
  });
  var bar = root.querySelector('[data-bar]');
  if (bar) { var track = back(bar), fill = rgba(getComputedStyle(bar.querySelector('.fill')).backgroundColor), mk = rgba(getComputedStyle(bar.querySelector('.mk')).backgroundColor);
    if (ratio(fill.c, track) < 3) out.push('bar fill against its track ' + ratio(fill.c, track).toFixed(2));
    if (ratio(mk.c, track) < 3) out.push('planned marker against the track ' + ratio(mk.c, track).toFixed(2)); }
  return JSON.stringify(out);
})()"""


class Drawn(unittest.TestCase):
    """The client report drawn in a PUBLISHED FILE made from the demo database (TUL), at 1400 and 900 px, light and dark.

    #559: the served page no longer offers this view, so these tests run on the published file (View only)
    and the coverage runs on it (publish.read_inputs -> select -> render -> open from file://), as test_client_report_file does."""

    @classmethod
    def setUpClass(cls):
        cls.store, cls.folder, _ = load_demo()

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        shutil.rmtree(str(cls.folder), ignore_errors=True)

    def serve(self, data=None):
        """Write the published file for TUL (as at the fixed demo date) and return its file:// address. `data` replaces the data after select."""
        inputs = publish.read_inputs(self.store, "TUL", as_at="2026-10-28")
        pub = publish.select(inputs)
        if data:
            pub["data"] = {**pub["data"], **data}
        text = publish.render(pub, page.page_html(EMPTY_BRANDING), "2026-10-28", pub["data"]["project"]["name"])
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "report.html"
        path.write_text(text, encoding="utf-8")
        return path.as_uri()

    def open_page(self, cdp, url, code=None):
        sid = opened(cdp, url)
        self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.ready", sid) == "1"), "the file drew")
        # Click the tab on every poll until the view is up (showing a view twice is the same as once): a click made before the tab
        # is there, or one the page took while it was still settling, is lost, and a single click then waits for nothing.
        seen = lambda: cdp.js("!!document.querySelector('#clientreport .sec') || ((document.querySelector('[data-view=clientreport]') || {click(){}}).click(), false)", sid)  # noqa: E731
        self.assertTrue(wait(seen, 20), "the report view drew; the page has: " + str(cdp.js(
            "JSON.stringify({view: (document.querySelector('.tab[aria-selected=true]') || {}).dataset && document.querySelector('.tab[aria-selected=true]').dataset.view, tabs: [...document.querySelectorAll('.tab')].map(t => t.dataset.view), text: document.body.innerText.slice(0, 200)})", sid)))
        return sid

    def check(self, cdp, sid, where, order=SECTION_ORDER):
        self.assertEqual(cdp.js("[...document.querySelectorAll('#clientreport .sec')].map(a => a.dataset.sec)", sid), order,
                         f"{where}: the sections in the fixed order")
        self.assertEqual(cdp.js("document.documentElement.scrollWidth <= window.innerWidth", sid), True, f"{where}: no sideways scroll")
        self.assertEqual(cdp.js("(() => { const f = document.querySelector('#clientreport').getBoundingClientRect();"
                                " return [...document.querySelectorAll('#clientreport *')].filter(e => { const r = e.getBoundingClientRect();"
                                " return r.width > 0 && (r.right > f.right + 1 || r.left < f.left - 1); }).length; })()", sid), 0,
                         f"{where}: nothing leaves the page's frame")
        self.assertEqual(json.loads(cdp.js(AUDIT, sid)), [], f"{where}: text at 13 px or more and 4.5:1")
        band = json.loads(cdp.js("(() => { const f = document.querySelector('#clientreport'), b = f.querySelector('.cr-band'), h = b.querySelector('h1'), w = b.querySelector('.cr-cover');"
                                 " const c = getComputedStyle(b).backgroundColor.match(/\\d+/g).map(Number), bb = b.getBoundingClientRect(), first = f.querySelector('.secs').getBoundingClientRect();"
                                 " return JSON.stringify({ dark: c[0] < 80 && c[1] < 80 && c[2] < 100, above: bb.bottom <= first.top, wide: bb.width > f.getBoundingClientRect().width * .9,"
                                 " inside: h.getBoundingClientRect().left >= bb.left && w.getBoundingClientRect().right <= bb.right, order: h.getBoundingClientRect().bottom <= w.getBoundingClientRect().top + 1 }); })()", sid))
        self.assertEqual(band, {"dark": True, "above": True, "wide": True, "inside": True, "order": True}, f"{where}: the dark cover band, the title over the week line")
        self.assertNotRegex(cdp.js("document.querySelector('#clientreport').innerText", sid),
                            r"on the Dashboard|Nothing written|Nothing here yet|not built|counts the same", f"{where}: nothing for the author and no explainer")

    def test_view_at_1400_and_900_in_light_and_dark(self):
        # Dropped with #559: the served-page run; the published file is the only place the client report is drawn.
        url = self.serve()
        with chrome() as cdp:
            sid = self.open_page(cdp, url)
            for width in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
                for theme in ("light", "dark"):
                    cdp.js(f"document.documentElement.dataset.theme = '{theme}'", sid)
                    # the theme's colour changes settle (no finite animation left running) before the page is measured. #650: only
                    # finite ones count, so a spinner that loops for ever (.spin, .ask-dots) could never fail this wait.
                    self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.theme === '%s' && document.getAnimations().filter(a => a.effect.getComputedTiming().iterations !== Infinity).length === 0" % theme, sid)), "the theme settled")
                    # the demo has no Highlights or Next week text: the View leaves those two boxes out
                    self.check(cdp, sid, f"View {width}px {theme}", ["progress", "plans", "raid"])
                    shown = cdp.js("document.querySelector('#clientreport').innerText", sid)
                    self.assertNotRegex(shown, r"Escalate", f"{width}px {theme}: no Escalate line")
                    self.assertEqual(cdp.js("document.querySelectorAll('#cr-raid .cr-esc, #cr-raid .wl-id, #cr-raid .idl, #cr-raid [data-id]').length", sid), 0)
                    self.assertNotRegex(cdp.js("document.querySelector('#cr-raid').innerText", sid), r"\b[A-Z]{2,6}-\d{3}\b", f"{width}px {theme}: no row id on a risk row")
                    self.assertNotRegex(shown, r"Not set|Nothing written|Write it in|not built yet|No milestones yet", f"View {width}px {theme}: no prompt for the author")

    def test_the_figures_the_demo_gives(self):
        url = self.serve()
        with chrome() as cdp:
            sid = self.open_page(cdp, url)
            text = lambda q: cdp.js(f"document.querySelector('{q}').textContent", sid)  # noqa: E731
            self.assertEqual(cdp.js("document.querySelector('#clientreport h1').textContent", sid), "Tulip Records Migration")
            self.assertRegex(text(".cr-cover"), r"^WEEKLY PROGRESS SNAPSHOT · Status as at \d{2}-\d{2}-\d{4}( · for .+)?$")
            self.assertIn("At risk", text("[data-fig=health]"))
            self.assertEqual((text("[data-fig=actual] .v"), text("[data-fig=planned] .v")), ("17%", "33%"))
            self.assertEqual(text("[data-gap]"), "16 points behind plan")
            self.assertEqual(cdp.js("document.querySelector('[data-bar] .fill').style.width", sid), "17%")
            self.assertEqual(cdp.js("document.querySelector('[data-bar] .mk').style.left", sid), "33%")
            self.assertEqual(cdp.js("[...document.querySelectorAll('[data-group]')].map(g => g.dataset.group)", sid), ["Scanning", "Training", "Indexing"])
            self.assertEqual(cdp.js("document.querySelectorAll('[data-line]').length", sid), 6)
            # row 799: a line with no Achieved figure (a dash) shows no red chip beside it; the chip is test_snapshot_avatar_chip's
            self.assertEqual(cdp.js("document.querySelectorAll('[data-line] .cr-behind').length", sid), 0, "the demo's lines behind plan have no Achieved figure")
            self.assertEqual(cdp.js("document.querySelectorAll('#clientreport input, #clientreport textarea, #clientreport select, #clientreport [contenteditable]').length", sid), 0)
            self.assertNotRegex(cdp.js("document.querySelector('#clientreport').innerText", sid), r"\d{4}-\d{2}-\d{2}", "dates are DD-MM-YYYY")

    def test_a_project_with_no_milestones_shows_no_figure_never_a_made_up_number(self):
        # Dropped with #559: the served-page run; the published file is the only place the client report is drawn. In a file with no
        # milestones the tab is left out (test_client_report_file), so the milestones are emptied after select, as the served page's data was.
        url = self.serve({"milestones": []})
        with chrome() as cdp:
            sid = self.open_page(cdp, url)
            self.assertEqual(cdp.js("document.querySelectorAll('[data-fig=actual], [data-fig=planned], [data-bar], [data-gap], [data-line], [data-no-lines], #cr-plans').length", sid), 0, "no figure, no bar, no lines")
            self.assertNotRegex(cdp.js("document.querySelector('#clientreport').innerText", sid), r"Not set|No milestones yet")
            self.assertEqual(json.loads(cdp.js(AUDIT, sid)), [])

    def test_a_published_file_opened_at_its_client_report_address_lands_on_the_weekly_snapshot(self):
        """#559: the served page maps #clientreport to the first tab, but a published file keeps it (its own tab list decides)."""
        url = self.serve() + "#clientreport"
        with chrome() as cdp:
            sid = opened(cdp, url)
            self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.ready", sid) == "1"), "the file drew")
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#clientreport .sec')", sid)), "the snapshot is the open view")
            self.assertEqual(cdp.js("document.querySelector('.tab[aria-selected=true]').dataset.view", sid), "clientreport")
            self.assertEqual(cdp.js("document.querySelector('[data-view=clientreport]').innerText", sid), "Weekly snapshot")


class HiddenOnTheServedPage(unittest.TestCase):
    """#559: the served page has no client report tab; a published file keeps it as "Weekly snapshot". The tab bar is checked in both Dashboard modes (View, Edit): the mode switch exists only on the Dashboard."""

    @classmethod
    def setUpClass(cls):
        cls.store, cls.folder, _ = load_demo()

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        shutil.rmtree(str(cls.folder), ignore_errors=True)

    def test_the_served_page_has_no_client_report_tab_in_either_dashboard_mode_and_its_address_falls_back(self):
        projects = self.store.read("projects")            # read here: the store's connection belongs to this thread, and the server answers on another
        s = Running(data_for=self.store.data_for, projects=lambda archived=False: projects, page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(s.close)
        with chrome() as cdp:
            sid = page_target(cdp)
            cdp.call("Page.enable", {}, sid)
            cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{s.port}/#clientreport&p=TUL"}, sid)
            def drew():   # the address #clientreport falls back by reloading the page: a read in that instant is refused ("navigated or closed"), so ask again
                try:
                    return cdp.js("document.documentElement.dataset.ready", sid) == "1"
                except RuntimeError:
                    return False
            self.assertTrue(wait(drew), "the page drew")
            wait(lambda: drew() and cdp.js("document.querySelectorAll('.tabs .tab').length", sid) >= 5)   # the fallback may reload once after the first ready: settle before the Edit click; the assertions below still judge the tabs
            for dashboard_mode in ("view", "edit"):  # Dashboard mode
                if dashboard_mode == "edit":
                    # a click before the page's handler is bound is lost on a loaded box: press again until the mode shows (Edit is a mode, not a toggle)
                    self.assertTrue(wait(lambda: cdp.js("(document.querySelector('[data-mode=edit]').click(), !!document.querySelector('[data-mode=edit][aria-pressed=true]'))", sid)))
                tabs = "[...document.querySelectorAll('.tabs .tab')].map(t => t.dataset.view)"
                wait(lambda: len(cdp.js(tabs, sid)) >= 5)   # ready is set before the tab bar is drawn on a slow runner (CI flake); the assertion below still judges the list
                self.assertEqual(cdp.js(tabs, sid), ["dashboard", "work", "milestones", "usecases", "settings"], dashboard_mode)
                self.assertEqual(cdp.js("document.querySelectorAll('#clientreport').length", sid), 0, dashboard_mode)
                self.assertEqual(cdp.js("document.querySelector('.tab[aria-selected=true]').dataset.view", sid), "dashboard", dashboard_mode)
            self.assertNotIn("Client Requested Report View", cdp.js("document.body.innerText", sid))

    def test_a_published_file_still_lists_the_tab_as_weekly_snapshot(self):
        self.assertIn('fromFile.value ? "Weekly snapshot"', text("stores", "report.js"))
        self.assertRegex(text("stores", "report.js"), r"tabs\.value = VIEWS\.filter\(\(v\) => p\.tabs\.includes\(v\)\)")
        self.assertIn('tabs.append("clientreport")', (SRCDIR.parent.parent / "publish.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
