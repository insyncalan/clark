"""#192 Client Requested Report View, part 3: Highlights and Planned for next week (the pair), Risks, delays and items to watch, and
the delivery placeholder.

Run: python3 dev/run_tests.py test_client_report_part3
Source tests (no browser) pin the mapping words, the Escalate rule, that the text is cleaned and never drawn raw, that the page's
cleaner stays out of a published file, and that the look is tokens only. The browser test (class Drawn) draws the page from the real
server in View and in Edit, at 1400 and 900 px, light and dark: the sections exist in order, the pair is side by side at 1400 and
stacked at 900, the Delay, Risk and Monitor words are the mapped ones, nothing overflows, text is at least 13 px and 4.5:1.
"""
import re
import sys
import unittest
from unittest import mock

from _demo import USER, DemoStore
from _paths import SRC

from clark import page, server as sv  # noqa: E402
from test_page import navigate  # noqa: E402
from test_server import Running, chrome, wait  # noqa: E402

PAGE = SRC / "clark" / "page"
SRCDIR = PAGE / "src"


def text(*parts):
    return SRCDIR.joinpath(*parts).read_text(encoding="utf-8")


class Source(unittest.TestCase):
    def test_the_words_are_mapped_not_typed(self):
        js = text("logic", "clientRisks.js")
        self.assertIn('if (kind === "issue") return DELAY;', js)
        self.assertIn('row.priority === "High" || row.priority === "Urgent" ? RISK : MONITOR', js)
        self.assertIn('export const DELAY = "Delay", RISK = "Risk", MONITOR = "Monitor"', js)

    def test_escalate_is_yes_only_for_urgent_or_red_and_never_no(self):
        js = text("logic", "clientRisks.js")
        self.assertIn('row.priority === "Urgent" || colourOf(row.priority).colour === "red" ? "Yes" : null', js)
        self.assertNotIn('"No"', js)

    def test_back_on_track_comes_from_the_due_date_and_the_working_note_is_never_read(self):
        js = text("logic", "clientRisks.js")
        self.assertIn("dayNumber(row.due_date) === null ? null : row.due_date", js)
        for name in ("clientRisks.js", "clientReport.js"):
            self.assertNotIn("response_action", text("logic", name), name + ": the response is a working note, never in a report")
        self.assertNotIn("response_action", text("components", "clientreport", "Risks.jsx"))

    def test_the_rows_pass_mains_gate(self):
        """The rows are the ones the published file would hold: main's mirror of publish.select (logic/publishable.js)."""
        self.assertIn('publishable(r, "raid", rules)', text("logic", "clientRisks.js"))
        self.assertIn('publishable(m, "milestones", rules)', text("logic", "clientReport.js"))
        for name in ("Overall.jsx", "Plans.jsx", "Risks.jsx"):
            self.assertIn("clientRules(", text("components", "clientreport", name), name)

    def test_the_placeholder_says_it_in_plain_words(self):
        self.assertIn("The delivery progress template is not built yet.", text("components", "clientreport", "Delivery.jsx"))

    def test_the_pair_text_is_cleaned_never_drawn_raw(self):
        pair = text("components", "clientreport", "Pair.jsx")
        self.assertIn("tools.RichRead", pair)
        self.assertIn("tools.RichField", pair)
        raw = [m.start() for m in re.finditer("dangerouslySetInnerHTML", pair)]
        self.assertEqual(len(raw), 1, "the one raw draw is a published file's text, cleaned when it was published")
        self.assertRegex(pair[raw[0] - 160:raw[0]], r"fromFile\.value")
        read = text("edit", "RichRead.jsx")
        self.assertIn("cleanHtml(", read)
        self.assertIn("RichRead", text("edit", "index.js"))

    def test_the_cleaner_is_not_in_a_published_file(self):
        for f in ("Pair.jsx", "Risks.jsx", "Delivery.jsx"):
            self.assertNotRegex(text("components", "clientreport", f), r"import[^;]*cleanHtml")
        view = (PAGE / "page-view.html").read_text(encoding="utf-8")
        self.assertNotIn("SanitiseError", "".join(re.findall(r"<script>(.*?)</script>", view, re.S)))

    def test_the_fixed_sections_have_files_and_the_css_is_in_the_part_3_block(self):
        css = (PAGE / "shell.css").read_text(encoding="utf-8")
        block = css[css.index("/* -- 192 part 3"):]
        for sel in (".cr-wl .wl-row", ".cr-wl .wl-meta", ".cr-placeholder", "@media (max-width: 900px)"):
            self.assertIn(sel, block)
        clean = re.sub(r"/\*.*?\*/", "", block, flags=re.S)
        self.assertNotRegex(clean, r"#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(", "colours come from the tokens")
        self.assertNotRegex(clean, r"font-size:\s*(?:\d|1[0-2])px", "13 px is the floor")

    def test_no_names_or_dates_in_the_part_3_files(self):
        for rel in (("logic", "clientRisks.js"), ("components", "clientreport", "Pair.jsx"), ("components", "clientreport", "Risks.jsx"),
                    ("components", "clientreport", "Delivery.jsx"), ("edit", "RichRead.jsx")):
            self.assertNotRegex(text(*rel), r"\b20\d\d-\d\d-\d\d\b", "/".join(rel))


BAD = '<p>Seeded highlight</p><script>window.__bad = 1</script><img src="x" onerror="window.__bad = 2"><p onclick="window.__bad = 3">Kept words</p>'
NEXT_BODY = "<ul><li>Close the open specifications</li><li>Start acceptance testing</li></ul>"

# What the contrast and size checks read, run in the page: every element of the three sections that holds its own text.
MEASURE = r"""
(function () {
  function rgb(s) { var m = /rgba?\(([^)]+)\)/.exec(s); if (!m) return null; var p = m[1].split(",").map(parseFloat); return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 }; }
  function lum(c) { function f(v) { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); } return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b); }
  function bg(el) { for (var e = el; e; e = e.parentElement) { var c = rgb(getComputedStyle(e).backgroundColor); if (c && c.a > 0.5) return c; } return rgb(getComputedStyle(document.documentElement).backgroundColor) || { r: 255, g: 255, b: 255, a: 1 }; }
  var bad = [], count = 0;
  document.querySelectorAll("#cr-highlights, #cr-nextweek, #cr-raid, #cr-delivery").forEach(function (root) {
    root.querySelectorAll("*").forEach(function (el) {
      var own = Array.prototype.some.call(el.childNodes, function (n) { return n.nodeType === 3 && n.textContent.trim(); });
      if (!own) return;
      count++;
      var cs = getComputedStyle(el), fg = rgb(cs.color), back = bg(el);
      var a = lum(fg), b = lum(back), ratio = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
      if (parseFloat(cs.fontSize) < 13) bad.push("size " + cs.fontSize + " " + el.className + " " + el.textContent.slice(0, 20));
      if (ratio < 4.5) bad.push("contrast " + ratio.toFixed(2) + " " + el.className + " " + el.textContent.slice(0, 20));
    });
  });
  return { count: count, bad: bad };
})()
"""


class Drawn(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store
        base = {"project": "ABC", "raised": "2026-10-01", "source": "demo", "owner": "Sam Rivers"}
        with self.store.step("dashboard", USER) as st:
            st.create("raid", {**base, "type": "Issue", "description": "Design sign-off is running late", "impact": "Medium", "likelihood": "Medium",
                               "due_date": "2026-11-13", "response_action": "A weekly call between both leads."})
            st.create("raid", {**base, "type": "Risk", "description": "Test system may be too small", "impact": "High", "likelihood": "Medium",
                               "due_date": "2026-11-20", "owner": "Alex Morgan"})
            st.create("raid", {**base, "type": "Risk", "description": "Urgent supplier risk", "impact": "High", "likelihood": "High"})
            st.create("raid", {**base, "type": "Risk", "description": "Licence renewal falls in a busy week", "impact": "Low", "likelihood": "Low",
                               "due_date": "2026-11-15", "owner": "Jo Patel"})
            st.create("raid", {**base, "type": "Risk", "description": "Medium risk to watch", "impact": "Medium", "likelihood": "Low"})
            st.create("raid", {**base, "type": "Assumption", "description": "Everyone has a laptop", "impact": "Low", "likelihood": "Low"})
            st.create("raid", {**base, "type": "Risk", "description": "Hidden from the client", "impact": "High", "likelihood": "High", "client_visible": 0})
            left = st.create("raid", {**base, "type": "Risk", "description": "Left out of the report", "impact": "High", "likelihood": "High"})
            st.create("report_hidden", {"project": "ABC", "item_id": left})
            sens = st.create("raid", {**base, "type": "Risk", "description": "Marked Sensitive", "impact": "High", "likelihood": "High", "owner": "Pat Quinn"})
            st.create("item_labels", {"item_id": sens, "label": "Sensitive"})
            st.create("labels", {"name": "Board only", "behaviour": "exclude", "default_choice": "include"})
            kept = st.create("raid", {**base, "type": "Issue", "description": "Kept out by a label", "impact": "High", "likelihood": "High", "owner": "Pat Quinn"})
            st.create("item_labels", {"item_id": kept, "label": "Board only"})
            st.create("raid", {**base, "type": "Risk", "description": "Says it the client's way", "impact": "Low", "likelihood": "Low",
                               "client_message": "The client's own words", "due_date": "2026-11-30"})
            gone = st.create("raid", {**base, "type": "Issue", "description": "Already closed issue", "impact": "Low", "likelihood": "Low"})
        self.hidden_ids = [left, sens, kept]
        with self.store.step("dashboard", USER) as st:
            st.update("raid", gone, {"status": "Closed", "closed": "2026-10-05"})
        secs = [r for r in self.store.read("report_sections", "ABC") if r["type"] == "text"]
        self.assertGreaterEqual(len(secs), 3, "the demo project starts with Summary, This week and Next week")
        by = {r["title"]: r["id"] for r in secs}
        with self.store.step("dashboard", USER) as st:
            st.update("report_sections", by["This week"], {"body": BAD})
            st.update("report_sections", by["Next week"], {"body": NEXT_BODY})
        quiet = mock.patch.object(sv.LOG, "disabled", True)
        quiet.start()
        self.addCleanup(quiet.stop)

    def look(self, cdp, sid, width, theme):
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.js(f"document.documentElement.dataset.theme = {theme!r}; true" if theme == "dark" else "delete document.documentElement.dataset.theme; true", sid)
        wait(lambda: cdp.js("window.innerWidth", sid) == width, 5)

    def check(self, cdp, sid, width, theme, edit):
        js = lambda e: cdp.js(e, sid)  # noqa: E731
        where = f"{'edit' if edit else 'view'} {width} {theme}"
        order = js("[...document.querySelectorAll('.client-report .sec')].map(function(e){return e.dataset.sec})")
        self.assertEqual(order, ["progress", "plans", "delivery", "highlights", "nextweek", "raid"], where)
        hi = js("(function(){var r=document.getElementById('cr-highlights').getBoundingClientRect();return [r.left,r.top,r.right,r.bottom]})()")
        nx = js("(function(){var r=document.getElementById('cr-nextweek').getBoundingClientRect();return [r.left,r.top,r.right,r.bottom]})()")
        if width >= 1400:
            self.assertLess(abs(hi[1] - nx[1]), 3, f"the pair shares a top edge: {where}")
            self.assertGreaterEqual(nx[0], hi[2] - 1, f"the pair is side by side: {where}")
        else:
            self.assertLess(abs(hi[0] - nx[0]), 3, f"the pair is one column: {where}")
            self.assertGreaterEqual(nx[1], hi[3] - 1, f"the pair is stacked: {where}")
        words = js("[...document.querySelectorAll('#cr-raid [data-word]')].map(function(e){return [e.dataset.word, e.querySelector('.pill').textContent, e.querySelector('.wl-title').textContent]})")
        self.assertEqual([w[:2] for w in words], [["Delay", "Delay"], ["Risk", "Risk"], ["Risk", "Risk"], ["Monitor", "Monitor"], ["Monitor", "Monitor"], ["Monitor", "Monitor"]], where)
        titles = [w[2] for w in words]
        self.assertEqual(titles[0], "Design sign-off is running late")
        for left_out in ("Everyone has a laptop", "Hidden from the client", "Already closed issue", "Left out of the report", "Says it the client's way",
                         "Marked Sensitive", "Kept out by a label"):
            self.assertNotIn(left_out, titles, where)
        raid_text = js("document.getElementById('cr-raid').innerText")
        for hid in self.hidden_ids:
            self.assertNotIn(hid, raid_text, "a hidden row's number never shows: " + where)
        self.assertNotIn("Pat Quinn", raid_text, "nor its owner: " + where)
        self.assertIn("The client's own words", titles, "a row's client message is what the client reads: " + where)
        page = js("document.getElementById('clientreport').innerText")
        self.assertNotIn("A weekly call between both leads.", page, "the response is a working note, never on this page: " + where)
        rows = js("[...document.querySelectorAll('#cr-raid .wl-row')].map(function(e){return [e.querySelector('.cr-back').textContent, e.querySelector('.cr-esc').textContent, e.querySelector('.wl-resp') ? 'shown' : '—', e.querySelector('.idl').textContent]})")
        self.assertEqual(rows[0][:3], ["Back on track by 13-11-2026", "Escalate: —", "—"], where)
        self.assertEqual(rows[1][1], "Escalate: Yes", "a High priority risk is Red: " + where)
        self.assertEqual(rows[2][0], "Back on track by —", where)
        self.assertEqual(rows[3][0], "Review by 15-11-2026", where)
        self.assertEqual(rows[3][2], "—", where)
        self.assertRegex(rows[0][3], r"^ABC-\d{3}$")
        self.assertEqual(js("document.querySelector('#cr-delivery .quiet').textContent"), "The delivery progress template is not built yet.", where)
        self.assertIn("Seeded highlight", js("document.getElementById('cr-highlights').textContent"), where)
        self.assertIn("Kept words", js("document.getElementById('cr-highlights').textContent"), where)
        self.assertEqual(js("document.querySelectorAll('#cr-highlights script, #cr-highlights img, #cr-highlights [onclick]').length"), 0, "cleaned: " + where)
        self.assertIsNone(js("window.__bad"), where)
        self.assertEqual(js("document.querySelectorAll('#cr-nextweek li').length"), 2, where)
        self.assertEqual(js("document.querySelectorAll('#cr-highlights [data-edit-only], #cr-nextweek [data-edit-only]').length"), 0, "read-only until the body editor is on: " + where)
        self.assertLessEqual(js("document.documentElement.scrollWidth"), js("window.innerWidth"), "no sideways scroll: " + where)
        self.assertEqual(js("[...document.querySelectorAll('#cr-highlights, #cr-nextweek, #cr-raid, #cr-delivery')].filter(function(e){return e.scrollWidth > e.clientWidth + 1}).length"), 0, "no overflow: " + where)
        m = js(MEASURE)
        self.assertGreater(m["count"], 20, where)
        self.assertEqual(m["bad"], [], where)

    def test_view_and_edit_at_1400_and_900_light_and_dark(self):
        s = Running(data_for=self.store.data_for, page_html=lambda: page.page_html(None))
        self.addCleanup(s.close)
        with chrome() as cdp:
            sid = navigate(cdp, s.port, "#clientreport&p=ABC")
            self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('#cr-raid .wl-row').length > 0", sid), 20), "the page drew")
            for edit in (False, True):
                if edit:
                    cdp.js("document.querySelector('[data-mode=edit]').click(); true", sid)
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-mode=edit][aria-pressed=true]')", sid), 10), "Edit is on")
                for width in (1400, 900):
                    for theme in ("light", "dark"):
                        self.look(cdp, sid, width, theme)
                        self.check(cdp, sid, width, theme, edit)


if __name__ == "__main__":
    unittest.main()
