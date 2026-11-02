"""The published page's cards are plain CSS and text: no image, no url( and no data: value in their rules, their styles or their markup.

Run: python3 dev/run_tests.py test_published_cards_plain
A real project is published with every kind of card in it (the glance tiles, a use case, RAID cards three and four across, a link
preview, and the card-style section), the finished file is opened from file:// in headless Chrome, and each card is checked in the
page as drawn. The fonts and the page's own small icon are not cards and are not looked at. All rows are fictional.
"""
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from _demo import USER
import test_glance_page as glance
from test_server import chrome

from clark import publish, section_kinds
from clark import store as store_module
from test_report_editor import EMPTY_BRANDING

CARD_SELECTOR = ".tcell, .uc, .raid-card, .tpl-lc, .secs > *"
CARD_CLASS = re.compile(r"(^|[^\w-])\.(tcell|tile|uc|ucrow|ucbar|ucdetail|raid-cards?|raid-\w+|tpl-[\w-]+|wil-[\w-]+|sec|secs|sec-[\w-]+|toc-card|sk-card|glance)([^\w-]|$)")

# Run in the page: what each card carries, as a list of plain sentences (empty when it is clean).
FINDINGS = r"""(() => {
  const out = [], bad = /url\(|^\s*data:|image-set|-webkit-image|(^|[^\w-])(image|cross-fade|element)\(/i, kinds = {};
  document.querySelectorAll(%s).forEach((el) => {
    const name = String(el.getAttribute("class") || el.tagName).split(/\s+/)[0];
    kinds[name] = (kinds[name] || 0) + 1;
    const here = el.tagName.toLowerCase() + "." + name;
    for (const part of [el, ...el.querySelectorAll("*")]) {
      if (/^(img|picture|video|canvas|image|source|object|embed|iframe|svg)$/i.test(part.tagName)) out.push(here + " holds <" + part.tagName.toLowerCase() + ">");
      for (const a of part.attributes) if (bad.test(a.value)) out.push(here + " has " + a.name + " with a picture value");
      for (const pseudo of [null, "::before", "::after", "::marker", "::first-line", "::first-letter"]) {
        const s = getComputedStyle(part, pseudo);
        for (const prop of ["backgroundImage", "listStyleImage", "borderImageSource", "maskImage", "webkitMaskImage", "content", "cursor", "filter", "clipPath", "shapeOutside", "maskBorderSource", "webkitMaskBoxImageSource", "backdropFilter"]) {
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
  window.__sections = [...document.querySelectorAll(".secs > [data-id]")].map((e) => e.dataset.id);
  return out;
})()"""

# The block of a rule that holds a picture: a url(), an image function, image-set, or a data: value.
PICTURE_VALUE = r"(?i)url\(|image-set|(^|[^\w-])(image|cross-fade|element)\(|:\s*[\"']?data:"
# The templates whose whole job is a picture: they rightly carry one, so they are not published here.
PICTURE_KINDS = ("textimage", "gallery", "imagecap")
# The class of the outermost element of each other template (the rules the page has for it start there).
ROOT_CLASS = {"headline": "tpl-band", "figures4": "tpl-figs", "figures3": "tpl-figs", "table": "tpl-table", "doclinks": "tpl-dl",
              "linkcard": "tpl-lc", "raid3": "raid-cards", "raid4": "raid-cards", "workitems": "wil-table", "callout": "tpl-callout",
              "quote": "tpl-quote", "contacts": "tpl-contacts", "checklist": "tpl-check", "keydates": "tpl-dates", "onedoc": "tpl-od"}


def picture_rules(text):
    """The card rules in a published file's own style whose block holds a picture value, and how many card rules were looked at."""
    css = "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", text, re.S))
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    seen, bad = 0, []
    for selector, block in re.findall(r"([^{}@;]+)\{([^{}]*)\}", css):
        if CARD_CLASS.search(selector + " ") or ".secpick" in selector:
            seen += 1
            if re.search(PICTURE_VALUE, block):
                bad.append(selector.strip())
    return bad, seen


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
            for n, (kind, body) in enumerate(self.other_bodies().items()):
                st.create("report_sections", {"project": "ABC", "type": kind, "title": "Fictional %s" % kind, "sort_order": 1100 + n,
                                              "body": store_module.check_section_body(kind, json.dumps(body))})

    def other_bodies(self):
        """One filled section of every other template that is published, none of them a picture one."""
        typed = {"mode": "typed", "label": "Budget used", "value": "62%", "detail": "of the approved budget", "asof": "2030-01-10"}
        bodies = {
            "headline": {"v": 1, "words": "Fictional pilot is live.", "label": "Read the plan", "href": "https://example.org/plan"},
            "figures4": {"v": 1, "figures": [{"mode": "live", "metric": "overdue"}, {"mode": "live", "metric": "risks"}, typed, typed]},
            "figures3": {"v": 1, "figures": [{"mode": "live", "metric": "overdue"}, typed, {"mode": "live", "metric": "decisions"}]},
            "table": {"v": 1, "cols": ["Item", "Owner"], "rows": [["Fictional scope", "Sam Example"]], "caption": "Fictional table."},
            "doclinks": {"v": 1, "items": [{"kind": "link", "href": "https://example.org/plan", "label": "The plan"}]},
            "workitems": {"v": 1},
            "callout": {"v": 1, "tone": "decision", "title": "Fictional decision", "paras": ["Fictional words."]},
            "quote": {"v": 1, "quote": "Fictional thanks.", "by": "Sam Example", "role": "Fictional sponsor"},
            "contacts": {"v": 1, "people": [{"name": "Sam Example", "role": "Fictional lead", "email": "sam@example.org", "phone": "+44 20 7946 0000"}]},
            "checklist": {"v": 1, "items": [{"text": "Fictional typed line", "done": 1}, {"text": "Another line", "done": 0}]},
            "keydates": {"v": 1, "items": [{"label": "Fictional typed date", "date": "2031-02-01"}]},
            "onedoc": {"v": 1, "file": {"name": "Signed SOW.pdf", "rel": "Report files/Signed SOW.pdf", "bytes": 2048}, "label": "The signed SOW",
                       "text": ["Signed."]},
        }
        wanted = set(section_kinds.TYPES) - set(PICTURE_KINDS) - {"linkcard", "raid3", "raid4"}
        self.assertEqual(set(bodies), wanted, "one of every template that is not a picture one")
        return bodies

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
                self.assertLessEqual(set(self.published_ids()), set(p.js("window.__sections")), "every published template section was checked")
                for needed in ("tcell", "uc", "raid-card", "tpl-lc"):
                    self.assertIn(needed, kinds, "the file has no %s card, so nothing was checked for it" % needed)
                self.assertGreaterEqual(kinds["tcell"], 4, "all four glance tiles")
                self.assertGreaterEqual(kinds["raid-card"], 2, "RAID cards three and four across")

    def published_ids(self):
        """The ids of the template sections the file holds; every template published here is among them."""
        built = publish.build(self.store, "ABC", now="2026-10-28", branding=EMPTY_BRANDING)["published"]["sections"]
        have = {s["type"] for s in built}
        for kind in ROOT_CLASS:
            self.assertIn(kind, have, "the file has no %s section, so nothing was checked for it" % kind)
        return [s["id"] for s in built if s["type"] in ROOT_CLASS]

    def test_the_card_rules_in_the_file_hold_no_picture_value(self):
        self.every_kind()
        text = self.publish().read_text(encoding="utf-8")
        bad, seen = picture_rules(text)
        self.assertEqual(bad, [])
        self.assertGreater(seen, 60, "the card rules were found in the file's own style")

    def test_a_picture_in_the_rules_of_any_published_template_is_seen(self):
        self.every_kind()
        text = self.publish().read_text(encoding="utf-8")
        for kind, cls in ROOT_CLASS.items():
            for name, value in (("url()", "url(a.png)"), ("data:", "data:image/png;base64,AA"), ("image-set()", "image-set(a)"), ("image()", "image(a.png)")):
                with self.subTest(kind=kind, value=name):
                    bad, _ = picture_rules(text.replace("</style>", ".%s > b { background: %s }</style>" % (cls, value), 1))
                    self.assertEqual(bad, [".%s > b" % cls])

    def test_a_picture_in_any_published_section_is_seen_on_the_page(self):
        self.every_kind()
        path = self.publish()
        sheet = "(() => { const s = new CSSStyleSheet(); s.replaceSync(%s); document.adoptedStyleSheets = [...document.adoptedStyleSheets, s]; })()"
        with chrome() as cdp:
            p = self.draw(cdp, path)
            ids = p.js("[...document.querySelectorAll('.secs > [data-id]')].map(e => e.dataset.id)")
            self.assertLessEqual(set(self.published_ids()), set(ids))
            self.assertEqual(p.js(findings_js()), [])
            p.js("window.__sheets = document.adoptedStyleSheets.slice()")
            for ref in ids:
                root = "document.querySelector('.secs > [data-id=%s]')" % json.dumps(ref)
                inner = "[...%s.querySelectorAll('*')].pop()" % root
                cases = {
                    "a url() on the section": (root + ".style.backgroundImage = 'url(x.png)'", root + ".style.backgroundImage = ''"),
                    "a url() on the last thing inside it": (inner + ".style.listStyleImage = 'url(x.png)'", inner + ".style.listStyleImage = ''"),
                    "a rule putting a url() in something inside it": (sheet % json.dumps("[data-id=%s] *::after { content: url(a.png) }" % json.dumps(ref)),
                                                                      "document.adoptedStyleSheets = window.__sheets"),
                }
                for name, (change, undo) in cases.items():
                    with self.subTest(section=ref, case=name):
                        p.js(change)
                        self.assertTrue(p.js(findings_js()), "%s in %s is not seen" % (name, ref))
                        p.js(undo)
                        self.assertEqual(p.js(findings_js()), [], "the undo left the section clean")

    def test_harmless_words_with_data_in_them_are_not_taken_for_a_data_value(self):
        self.every_kind()
        path = self.publish()
        with chrome() as cdp:
            p = self.draw(cdp, path)
            p.js("document.querySelector('.tcell').setAttribute('aria-label', 'Update data: weekly')")
            self.assertEqual(p.js(findings_js()), [])

    def test_a_cover_or_banner_picture_in_a_persons_own_look_never_reaches_a_card(self):
        self.every_kind()
        brand = Path(tempfile.mkdtemp(prefix="clark-brand-"))
        self.addCleanup(shutil.rmtree, brand, True)
        (brand / "tokens.css").write_text(":root { --art-home: url(data:image/png;base64,AA); --image-cover: url(data:image/png;base64,AA); --art-home-height: 40px; }\n", encoding="utf-8")
        out = tempfile.mkdtemp(prefix="clark-369-")
        self.addCleanup(shutil.rmtree, out, True)
        path = Path(publish.publish(self.store, "ABC", out, by_user=USER, now="2026-10-28", branding=brand)["path"])
        self.assertIn("--image-cover: url(data:image/png;base64,AA)", path.read_text(encoding="utf-8"), "the look reached the file")
        with chrome() as cdp:
            p = self.draw(cdp, path)
            self.assertEqual(p.js(findings_js()), [])
            self.assertEqual(p.js("getComputedStyle(document.documentElement).getPropertyValue('--image-cover').trim()"), "url(data:image/png;base64,AA)")
            p.js("document.querySelector('.tcell').style.backgroundImage = 'var(--image-cover)'")
            self.assertTrue(p.js(findings_js()), "a card that used the look's picture is seen")

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
