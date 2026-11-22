"""Row 1272 items 2 and 4, on the real page as Chrome lays it out at 1400 px.

Item 2: ruling (PM 22-11): 493 px is the half CARD width at 1400, border-box. The shared half column is 507.5 px (shell.css), 14.5 px over, so a
Classic-only rule in rules-2.css holds a half section that has a Callout to 493. The test measures the CARD (the section); the box inside it (463.5
here) is not pinned. Other templates' half cards keep the shared 507.5 (pinned below). Not proved at 900 px: the 900 px subtests are skipped (PAUSED_900), and the grid is one column there.
Item 4: the Callout's visible Edit field edge (the category field) is --control-edge already (edit.css); the title and words edges are transparent at rest by design, so no rule is added.
Run: TZ=Asia/Dubai python3 dev/run_tests.py test_tpl_callout_width_1272   (needs Chrome)
Fictional data only.
"""
import json
import unittest

from _demo import USER
from _paths import SRC
from test_server import chrome
from test_theme_callout_1272 import Shared

SEC = "document.querySelector('[data-id=%s]')"
EDIT = (SRC / "clark" / "page" / "src" / "edit" / "edit.css").read_text(encoding="utf-8")
RULES2 = (SRC / "clark" / "themes" / "prototype-2.0" / "rules-2.css").read_text(encoding="utf-8")
RULES = (SRC / "clark" / "themes" / "prototype-2.0" / "rules.css").read_text(encoding="utf-8")
EDGE = """(() => { const probe = (c) => { const d = document.createElement('div'); d.style.cssText = 'border:1px solid ' + c; document.body.appendChild(d); const v = getComputedStyle(d).borderTopColor; d.remove(); return v; };
  const f = (s) => getComputedStyle(document.querySelector(s)).borderTopColor;
  return { title: f('[data-id=%s] .tpl-edit-callout .cb-title'), cat: f('[data-id=%s] .tpl-edit-callout .cb-in'), control: probe('var(--control-edge)'), grey: probe('var(--grey-300)') }; })()"""


class Callouts(Shared):
    def make_pair(self):
        body = {"v": 1, "title": "Fictional callout", "paras": ["Fictional words."], "colour": "violet"}
        refs = []
        with self.store.step("dashboard", USER) as st:
            for n, beside in enumerate((1, 0)):
                refs.append(st.create("report_sections", {"project": "ABC", "type": "callout", "title": f"Fictional callout {n}", "sort_order": 998 + n, "beside": beside, "body": json.dumps(body)}))
        return refs

    def widths(self):
        left, right = self.make_pair()
        with chrome() as cdp:
            p = self.visit(cdp)
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": 1400, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, p.sid)
            return p.js("(() => [%s, %s].map((s) => [s.className, s.getBoundingClientRect().width, s.querySelector('.tpl-callout').getBoundingClientRect().width]))()" % (SEC % json.dumps(left), SEC % json.dumps(right)))

    def other_widths(self):
        with self.store.step("dashboard", USER) as st:
            refs = [st.create("report_sections", {"project": "ABC", "type": "text", "title": f"Fictional text {n}", "sort_order": 998 + n, "beside": beside, "body": json.dumps({"v": 1, "paras": ["Fictional words."]})}) for n, beside in enumerate((1, 0))]
        with chrome() as cdp:
            p = self.visit(cdp)
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": 1400, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, p.sid)
            return p.js("(() => [%s, %s].map((s) => [s.className, s.getBoundingClientRect().width]))()" % (SEC % json.dumps(refs[0]), SEC % json.dumps(refs[1])))

    def edge(self):
        ref = self.make_pair()[0]
        with chrome() as cdp:
            p = self.visit(cdp)
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": 1400, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, p.sid)
            p.edit()
            p.until("!!document.querySelector('[data-id=%s] .tpl-edit-callout .cb-title')" % json.dumps(ref), "the Callout Edit fields")
            return p.js(EDGE % (json.dumps(ref), json.dumps(ref)))


class Classic(Callouts):
    def test_a_half_callout_card_is_493_border_box_at_1400(self):
        got = self.widths()
        self.assertEqual([g[0] for g in got], ["sec slot-left band", "sec slot-right band"])
        self.assertEqual([g[1] for g in got], [493, 493])

    def test_a_half_text_card_is_still_the_shared_507_5_at_1400(self):
        got = self.other_widths()
        self.assertEqual([g[0] for g in got], ["sec slot-left band", "sec slot-right band"])
        self.assertEqual([g[1] for g in got], [507.5, 507.5])

    def test_the_rule_is_scoped_to_a_section_holding_a_callout_so_other_half_cards_are_unchanged(self):
        self.assertRegex(RULES2, r"\.sec\.slot-left:has\(\.tpl-callout\), \.sec\.slot-right:has\(\.tpl-callout\) \{ box-sizing: border-box; width: 493px; \}")
        self.assertNotRegex(RULES2, r"\.sec\.slot-(left|right) \{[^}]*width")
        self.assertNotIn("493", (SRC / "clark" / "page" / "shell.css").read_text(encoding="utf-8"))
        self.assertEqual(RULES.count("493px"), 0)

    def test_the_visible_callout_edit_field_edge_is_the_control_edge_and_the_title_edge_is_transparent_at_rest(self):
        got = self.edge()
        self.assertEqual(got["cat"], got["control"], "the category field")
        self.assertNotEqual(got["control"], got["grey"])
        self.assertEqual(got["title"], "rgba(0, 0, 0, 0)", "the title and the words draw no edge at rest (mock-up B); hover shows --text-muted")

    def test_the_category_edge_is_the_control_edge_value_at_1400_and_900_in_light_and_dark(self):
        ref = self.make_pair()[0]
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                    p = self.visit(cdp)
                    cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, p.sid)
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                    p.edit()
                    p.until("!!document.querySelector('[data-id=%s] .tpl-edit-callout .cb-title')" % json.dumps(ref), "the Callout Edit fields")
                    got = p.js(EDGE % (json.dumps(ref), json.dumps(ref)))
                    self.assertEqual(got["cat"], got["control"], f"the category field edge is --control-edge at {width} {scheme}")
                    self.assertNotEqual(got["cat"], got["grey"])
                    self.assertEqual(got["title"], "rgba(0, 0, 0, 0)", f"the title edge is transparent at rest at {width} {scheme} (edit.css:627), not the token")

    def test_the_css_says_so(self):
        self.assertRegex(EDIT, r"\.tpl-field\.cb-in \{[^}]*border-color: var\(--control-edge\);")
        self.assertRegex(EDIT, r"\.tpl-field\.cb-title \{[^}]*border-color: transparent;")
        self.assertNotIn("tpl-edit-callout", RULES2 + RULES)


if __name__ == "__main__":
    unittest.main()
