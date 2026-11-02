"""The published page's cards are plain CSS and text: no image, no url( and no data: value in their rules, their styles or their markup.

Run: python3 dev/run_tests.py test_published_cards_plain
A real project is published with every kind of card in it (the glance tiles, a use case, RAID cards three and four across, a link
preview, and the card-style section), the finished file is opened from file:// in headless Chrome, and each card is checked in the
page as drawn. The fonts and the page's own small icon are not cards and are not looked at. All rows are fictional.
"""
import json
import re
import unittest

from _demo import USER
import test_glance_page as glance
from test_server import chrome

from clark import store as store_module

CARD_SELECTOR = ".tcell, .uc, .raid-card, .tpl-lc, .secs > *"
CARD_CLASS = re.compile(r"(^|[^\w-])\.(tcell|tile|uc|ucrow|ucbar|ucdetail|raid-cards?|raid-\w+|tpl-lc[\w-]*|toc-card|sk-card|glance)([^\w-]|$)")

# Run in the page: what each card carries, as a list of plain sentences (empty when it is clean).
FINDINGS = r"""(() => {
  const out = [], bad = /url\(|data:|image-set|-webkit-image/i, kinds = {};
  document.querySelectorAll(%s).forEach((el) => {
    const name = String(el.getAttribute("class") || el.tagName).split(/\s+/)[0];
    kinds[name] = (kinds[name] || 0) + 1;
    const here = el.tagName.toLowerCase() + "." + name;
    for (const part of [el, ...el.querySelectorAll("*")]) {
      if (/^(img|picture|video|canvas|image|source|object|embed|iframe|svg)$/i.test(part.tagName)) out.push(here + " holds <" + part.tagName.toLowerCase() + ">");
      for (const a of part.attributes) if (bad.test(a.value)) out.push(here + " has " + a.name + " with a picture value");
      for (const pseudo of [null, "::before", "::after"]) {
        const s = getComputedStyle(part, pseudo);
        for (const prop of ["backgroundImage", "listStyleImage", "borderImageSource", "maskImage", "webkitMaskImage", "content", "cursor", "filter", "clipPath", "shapeOutside"]) {
          if (bad.test(s[prop] || "")) out.push(here + " " + (pseudo || "") + " " + prop + " is " + s[prop].slice(0, 60));
        }
      }
    }
  });
  const rule = new RegExp(%s, "i");
  const walk = (list) => { for (const r of list) {
    if (r.cssRules && !r.selectorText) walk(r.cssRules);
    else if (r.selectorText && rule.test(r.selectorText) && bad.test(r.cssText)) out.push("rule " + r.selectorText + " has a picture value");
  } };
  for (const sheet of [...document.styleSheets, ...document.adoptedStyleSheets]) walk(sheet.cssRules);
  window.__kinds = kinds;
  return out;
})()"""


def findings_js():
    return FINDINGS % (json.dumps(CARD_SELECTOR), json.dumps(CARD_CLASS.pattern + "|\\.secpick"))


class Plain(glance.Setup):
    publish = glance.Published.publish
    draw = glance.Published.draw

    def every_kind(self):
        """Four glance tiles, a use case (planted by Setup), RAID cards at three and four across and a link preview."""
        status, _ = self.real_change({"project": "ABC", "kind": "glance_tiles", "op": "update", "id": "decisions", "changes": {"hidden": 0}})
        self.assertEqual(status, 200)
        with self.store.step("dashboard", USER) as st:
            risk = st.create("raid", {"project": "ABC", "type": "Risk", "description": "Supplier may slip", "raised": "2026-10-01", "source": "demo",
                                      "client_message": "We are watching the supplier."})
            for kind, size in (("raid3", 3), ("raid4", 4)):
                ref = st.create("report_sections", {"project": "ABC", "type": kind, "title": "Fictional cards %d" % size, "sort_order": 990 + size})
                st.update("report_sections", ref, {"body": json.dumps({"v": 1, "cards": [{"id": risk, "source": "client"}]})})
            ref = st.create("report_sections", {"project": "ABC", "type": "linkcard", "title": "Fictional link", "sort_order": 999})
            st.update("report_sections", ref, {"body": store_module.check_section_body("linkcard", json.dumps(
                {"v": 1, "href": "https://example.org/pilot", "title": "Pilot", "site": "Example", "text": ["Updated weekly."]}))})

    def test_the_published_cards_carry_no_image_no_url_and_no_data_value(self):
        self.every_kind()
        path = self.publish()
        for width, dark in ((1400, False), (900, True)):
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                p = self.draw(cdp, path, width, dark)
                for style in ("slim", "roomy", "grey", "card"):
                    p.js("document.documentElement.dataset.secstyle = %s" % json.dumps(style))
                    self.assertEqual(p.js(findings_js()), [], style)
                kinds = p.js("window.__kinds")
                for needed in ("tcell", "uc", "raid-card", "tpl-lc"):
                    self.assertIn(needed, kinds, "the file has no %s card, so nothing was checked for it" % needed)
                self.assertGreaterEqual(kinds["tcell"], 4, "all four glance tiles")
                self.assertGreaterEqual(kinds["raid-card"], 2, "RAID cards three and four across")

    def test_the_card_rules_in_the_file_hold_no_picture_value(self):
        self.every_kind()
        text = self.publish().read_text(encoding="utf-8")
        css = "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", text, re.S))
        css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
        seen = 0
        for selector, block in re.findall(r"([^{}@;]+)\{([^{}]*)\}", css):
            if CARD_CLASS.search(selector + " ") or ".secpick" in selector:
                seen += 1
                self.assertNotRegex(block, r"(?i)url\(|data:|image-set", selector.strip())
        self.assertGreater(seen, 20, "the card rules were found in the file's own style")

    def test_the_check_does_see_a_picture_put_into_a_card(self):
        self.every_kind()
        path = self.publish()
        sheet = "(() => { const s = new CSSStyleSheet(); s.replaceSync(%s); document.adoptedStyleSheets = [...document.adoptedStyleSheets, s]; })()"
        cases = {
            "an img": "document.querySelector('.raid-card').appendChild(document.createElement('img'))",
            "a url() background": "document.querySelector('.tcell').style.backgroundImage = 'url(x.png)'",
            "a data: value": "document.querySelector('.uc').setAttribute('data-x', 'data:image/png;base64,AA')",
            "a rule with url()": sheet % json.dumps(".tpl-lc { background: url(a.png) }"),
            "a pseudo-element picture": sheet % json.dumps(".raid-card::before { content: url(a.png) }"),
            "an svg": "document.querySelector('.tpl-lc').appendChild(document.createElementNS('http://www.w3.org/2000/svg', 'svg'))",
        }
        for name, change in cases.items():
            with self.subTest(name), chrome() as cdp:
                p = self.draw(cdp, path)
                self.assertEqual(p.js(findings_js()), [])
                p.js(change)
                self.assertTrue(p.js(findings_js()), name + " is not seen")


if __name__ == "__main__":
    unittest.main()
