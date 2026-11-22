"""Row 1225 (template family redesign), first slice: AP1 and AP2, the two checks the template list itself owns.

AP1: the Add a section box offers no Needs from you template, and a Needs from you section already stored is not drawn.
AP2: the box offers one Image template (full-image) and not Image with caption (image-caption); a stored Image with caption
     section (store type imagecap) is still drawn, because full-image uses the same store type.
Run: python3 dev/run_tests.py test_template_family_1225
Needs Chrome (the harness of test_templates): fails, never skips, without it. The widths 1400 and 900 do not change the list.
"""
import contextlib
import json
import unittest

import test_placement as tp
from _paths import ROOT, SRC
from test_server import chrome, wait

tp.DEMO = ROOT / "tests" / "fixtures" / "templates_demo.js"
PAGE_SRC = SRC / "clark" / "page" / "src"
_PAGE = {}


def page_html():
    if "html" not in _PAGE:
        tp._PAGE.pop("html", None)
        _PAGE["html"] = tp.test_page_html()
        tp._PAGE.pop("html", None)
    return _PAGE["html"]


class TemplateList(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from test_server import Running
        cls.stack = contextlib.ExitStack()
        cls.server = Running(page_html=page_html)
        cls.stack.callback(cls.server.close)
        cls.cdp = cls.stack.enter_context(chrome())
        tid = next(t["targetId"] for t in cls.cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        cls.sid = cls.cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    def setUp(self):
        self.cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.server.port}/"}, self.sid)
        self.assertTrue(wait(lambda: self.cdp.js("!!(window.T && window.T.templates)", self.sid)), "the test bundle ran")

    def templates(self):
        got = self.cdp.js("JSON.stringify(T.templates.TEMPLATES)", self.sid)
        self.assertIsNotNone(got)
        return json.loads(got)

    def test_needs_from_you_is_not_in_the_template_list(self):
        cat = self.templates()
        self.assertEqual([x["id"] for x in cat if x["name"] == "Needs from you" or x["type"] == "needs" or "needs" in x["id"]], [])
        self.assertTrue(len(cat) > 20, "the list is read, not empty")
        # a stored Needs from you section is filtered out before it is drawn (Dashboard.jsx)
        src = (PAGE_SRC / "components" / "Dashboard.jsx").read_text(encoding="utf-8")
        self.assertIn('.filter((s) => s.type !== "needs")', src)

    def test_picker_has_image_and_not_image_with_caption(self):
        cat = self.templates()
        ids = [x["id"] for x in cat]
        self.assertEqual(ids.count("image-caption"), 0)
        self.assertEqual(ids.count("full-image"), 1)
        self.assertEqual([x["name"] for x in cat if x["name"] == "Image with caption"], [])
        # the store type stays offered through Image, so a stored Image with caption section is still found and drawn
        full = next(x for x in cat if x["id"] == "full-image")
        self.assertEqual(full["type"], "imagecap")
        self.assertEqual(self.cdp.js("JSON.stringify(T.templates.find('image-caption'))", self.sid), "null")


if __name__ == "__main__":
    unittest.main()
