"""Row 1190, the At a glance template: the built-in glance section (store type "glance") is also a library template. The store type, the
tiles (project-level glance_tiles) and the Word, Excel and published readers are unchanged; this file holds what is new: the catalogue
entry, the page parts reached through templateFor / templateEdit instead of a hand branch in Section.jsx, and the words in one file.
Page side only. Fictional data.

Run: python3 dev/run_tests.py test_tpl_glance
Needs Chrome: these tests fail, never skip, without it.
"""
import contextlib
import json
import re
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT, SRC, TOOLS
import sys

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402

from test_server import Running, chrome, wait  # noqa: E402

PAGE_SRC = SRC / "clark" / "page" / "src"
DEMO = ROOT / "tests" / "fixtures" / "glance_section_demo.jsx"
_PAGE = {}


def page_html():
    if "html" not in _PAGE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "t.js"
            done = esbuild.run(["--bundle", "--format=iife", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(DEMO), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            script = out.read_text(encoding="utf-8").replace("</script", "<\\/script")
        _PAGE["html"] = ('<!doctype html>\n<html lang="en-GB"><head><meta charset="utf-8"><title>t</title></head>'
                         f'<body><div id="root"></div>\n<script>{script}</script>\n</body></html>\n')
    return _PAGE["html"]


def lit(x):
    return json.dumps(x)


FILE = {"project": {"health": "On track", "health_reason": "Plain reason"},
        "glance": {"tiles": [{"tile": "health", "outline": ""},
                             {"tile": "overdue", "label": "Overdue", "value": "3", "detail": "open", "colour": "red", "outline": ""}]}}


class Static(unittest.TestCase):
    def read(self, *parts):
        return PAGE_SRC.joinpath(*parts).read_text(encoding="utf-8")

    def test_section_jsx_has_no_hand_branch_for_glance(self):
        self.assertNotIn('section.type === "glance"', self.read("components", "Section.jsx"))

    def test_every_new_word_is_in_the_one_strings_file_as_an_unruled_constant(self):
        text = self.read("logic", "glanceStrings.js")
        self.assertRegex(text, r"export const UNRULED_GLANCE_HOLDS\b")
        self.assertRegex(text, r"export const UNRULED_GLANCE_ONCE\b")
        self.assertRegex(text, r"export const GLANCE_DESCRIPTION = \"Project health with its reason, and the count tiles\.\"", "the description is Help's existing, ruled sentence")

    def test_the_catalogue_entry_uses_the_strings_and_the_box_no_longer_offers_a_second_built_in(self):
        text = self.read("logic", "templates.js")
        entry = text[text.index('{ id: "at-a-glance"'):]
        entry = entry[:entry.index("\n  },") if "\n  }," in entry else entry.index("];")]
        self.assertIn('type: "glance"', entry)
        self.assertIn('kind: "figures"', entry)
        self.assertIn("GLANCE_DESCRIPTION", entry)
        self.assertIn("UNRULED_GLANCE_HOLDS", entry)
        self.assertNotIn('builtIn("glance"', text)

    def test_help_has_a_row_for_the_card(self):
        help_ = json.loads(self.read("help", "helpContent.json"))
        rows = []

        def walk(o):
            if isinstance(o, dict):
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                if len(o) == 3 and all(isinstance(x, str) for x in o):
                    rows.append(tuple(o))
                for v in o:
                    walk(v)
        walk(help_)
        self.assertIn(("At a glance", "Project health with its reason, and the count tiles.", "Full"), rows)


class Parts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack = contextlib.ExitStack()
        cls.server = Running(page_html=page_html)
        cls.stack.callback(cls.server.close)
        cls.cdp = cls.stack.enter_context(chrome())
        tid = next(t["targetId"] for t in cls.cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        cls.sid = cls.cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cls.cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{cls.server.port}/"}, cls.sid)
        assert wait(lambda: cls.cdp.js("!!(window.mountSection && window.K)", cls.sid)), "the test bundle ran"

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    def js(self, expr):
        return self.cdp.js(expr, self.sid)

    def look(self, width):
        self.cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)

    def test_the_template_has_a_ready_view_and_an_edit_part(self):
        self.assertEqual(self.js("[typeof K.templateFor('glance').view, typeof K.templateFor('glance').isEmpty, K.templateFor('glance').ready, typeof K.templateEdit('glance')].join()"),
                         "function,function,true,function")

    def test_a_published_file_draws_the_file_tiles_and_leaves_the_section_out_when_it_has_none(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                self.look(width)
                self.js(f"mountSection({lit(FILE)}, {lit({'file': True, 'width': width - 40})})")
                self.assertTrue(wait(lambda: self.js("!!document.querySelector('[data-glance]')"), 8))
                self.assertEqual(self.js("[...document.querySelectorAll('[data-tile]')].map(e => e.dataset.tile).join()"), "health,overdue")
                self.assertEqual(self.js("document.querySelector('[data-fig=overdue]').tagName"), "DIV", "no work tab in the file: not clickable")
                self.assertIn("Plain reason", self.js("document.querySelector('.hreason').textContent"))

    def test_isempty_is_the_files_rule_only(self):
        sec = "{type: 'glance'}"
        self.js(f"mountSection({lit(FILE)}, {{file: true}})")
        self.assertFalse(self.js(f"K.templateEmpty({sec}, {lit(FILE)})"))
        self.js(f"mountSection({lit(FILE)}, {{}})")
        self.assertFalse(self.js(f"K.templateEmpty({sec}, {lit({'project': {}})})"), "the served View always draws it")


if __name__ == "__main__":
    unittest.main()
