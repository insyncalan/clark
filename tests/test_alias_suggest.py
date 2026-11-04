"""#613: the Alias clark suggests from a full name (src/clark/page/src/logic/alias.js): the first name, then the initials, comma-separated.
"Jane Doe" suggests "Jane,JD"; a one-word name suggests only that word; an empty name suggests nothing; a suggestion never overwrites
an Alias already typed. Fictional names only. The Alias box waits for a stored Alias field (a guarded change); what the page has is a
read-only line under Settings › Personal › About you › Your name, worked out live from the name box and never kept or sent. It is
checked in the real page at 1400 and 900 px, light and dark.

Run: python3 dev/run_tests.py test_alias_suggest
The plain-JS logic runs inside headless Chrome (the #33 harness, as test_placement.py does), bundled with the pinned esbuild into a
temporary folder (never the repo). Chrome is required: these tests fail, never skip, without it.
"""
import contextlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from _paths import SRC, TOOLS

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402

from test_server import Running, chrome, wait  # noqa: E402  (the #33 browser harness, shared)
import test_about_you as about  # noqa: E402  (its helpers only: the module is imported, not its test class, so those tests run once)
from test_publish_dialog import Base  # noqa: E402

WIDTHS = (1400, 900)
LINE = "Suggested Alias: {}"
HELP = "What colleagues might call you, worked out from your name. Not saved."

ALIAS_JS = SRC / "clark" / "page" / "src" / "logic" / "alias.js"
_PAGE = {}


def test_page_html():
    """alias.js, bundled by the pinned esbuild in a temporary folder, on a bare page as window.T."""
    if "html" not in _PAGE:
        with tempfile.TemporaryDirectory() as tmp:
            entry, out = Path(tmp) / "entry.js", Path(tmp) / "t.js"
            entry.write_text(f"import * as alias from {json.dumps(ALIAS_JS.as_posix())};\nwindow.T = {{ alias }};\n", encoding="utf-8")
            done = esbuild.run(["--bundle", "--format=iife", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), str(entry), f"--outfile={out}"], cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            script = out.read_text(encoding="utf-8").replace("</script", "<\\/script")
        _PAGE["html"] = (f'<!doctype html>\n<html lang="en-GB"><head><meta charset="utf-8"><title>t</title></head>\n'
                         f'<body>\n<script>{script}</script>\n</body></html>\n')
    return _PAGE["html"]


class Suggest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack = contextlib.ExitStack()
        cls.server = Running(page_html=test_page_html)
        cls.stack.callback(cls.server.close)
        cls.cdp = cls.stack.enter_context(chrome())
        tid = next(t["targetId"] for t in cls.cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        cls.sid = cls.cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cls.cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{cls.server.port}/"}, cls.sid)
        assert wait(lambda: cls.cdp.js("!!(window.T && window.T.alias)", cls.sid)), "the test bundle ran"

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    def call(self, fn, *args):
        got = self.cdp.js(f"JSON.stringify(T.alias.{fn}({', '.join(json.dumps(a) for a in args)}))", self.sid)
        self.assertIsNotNone(got, fn)
        return json.loads(got)

    def test_a_full_name_suggests_the_first_name_then_the_initials(self):
        self.assertEqual(self.call("suggestAlias", "Jane Doe"), "Jane,JD")
        self.assertEqual(self.call("suggestAlias", "Sam Lee"), "Sam,SL")
        self.assertEqual(self.call("suggestAlias", "Mary Ann Smith"), "Mary,MAS")

    def test_the_initials_are_capitals_whatever_was_typed(self):
        self.assertEqual(self.call("suggestAlias", "jane doe"), "jane,JD")
        self.assertEqual(self.call("suggestAlias", "Pia van Berg"), "Pia,PVB")
        self.assertEqual(self.call("suggestAlias", "Éla Ørn"), "Éla,ÉØ")

    def test_spaces_and_commas_in_the_name_do_not_spoil_the_suggestion(self):
        self.assertEqual(self.call("suggestAlias", "  Jane   Doe  "), "Jane,JD")
        self.assertEqual(self.call("suggestAlias", "Doe, Jane"), "Doe,DJ")
        self.assertEqual(self.call("suggestAlias", "Jane\tDoe"), "Jane,JD")

    def test_a_word_with_no_letter_adds_no_initial(self):
        self.assertEqual(self.call("suggestAlias", "Jane Doe 2"), "Jane,JD")

    def test_a_one_word_name_suggests_only_that_word(self):
        self.assertEqual(self.call("suggestAlias", "Jane"), "Jane")
        self.assertEqual(self.call("suggestAlias", " Jane "), "Jane")

    def test_an_empty_name_suggests_nothing(self):
        for empty in ("", "   ", ",", None):
            self.assertEqual(self.call("suggestAlias", empty), "", repr(empty))

    def test_a_suggestion_is_offered_only_while_the_alias_is_empty(self):
        self.assertEqual(self.call("aliasOffer", "Jane Doe", ""), "Jane,JD")
        self.assertEqual(self.call("aliasOffer", "Jane Doe", "   "), "Jane,JD")
        self.assertEqual(self.call("aliasOffer", "Jane Doe", "JJ"), "", "an Alias the person typed is never overwritten")
        self.assertEqual(self.call("aliasOffer", "Jane Doe", None), "Jane,JD")
        self.assertEqual(self.call("aliasOffer", "", ""), "")


class OnThePage(Base):
    """The read-only line under the name box in the real page."""
    saved = about.AboutYou.saved
    open_menu = about.AboutYou.open_menu
    open_settings = about.AboutYou.open_settings
    type_into = about.AboutYou.type_into

    def offer(self, p):
        return p.js("(() => { const o = document.querySelector('[data-about-you] [data-alias-offer]'); if (!o) return null; "
                    "const ps = o.querySelectorAll('p'); return {line: ps[0].textContent, alias: o.querySelector('[data-alias]').textContent, "
                    "help: ps[1].textContent, under: !!o.closest('.fld') && !!o.closest('.fld').querySelector('#about-name')}; })()")

    def fits(self, p):
        return p.js("(() => { const o = document.querySelector('[data-alias-offer]'), f = document.querySelector('[data-about-you]'); "
                    "const r = o.getBoundingClientRect(), b = f.getBoundingClientRect(); "
                    "return r.width > 0 && r.right <= b.right + 0.5 && document.documentElement.scrollWidth <= document.documentElement.clientWidth "
                    "&& [...o.querySelectorAll('p')].every((e) => e.scrollWidth <= e.clientWidth + 0.5); })()")

    def lightness(self, p, sel):
        rgb = p.js(f"getComputedStyle(document.querySelector({json.dumps(sel)})).color")
        r, g, b = [int(x) for x in rgb[rgb.index("(") + 1:rgb.index(")")].split(",")[:3]]
        return (r + g + b) / 3

    def test_C_the_line_follows_the_name_box_at_both_widths_light_and_dark(self):
        for w in WIDTHS:
            with chrome() as cdp:
                p = self.page(cdp)
                p.width(w)
                self.open_settings(p)
                self.assertIsNone(self.offer(p), "an empty name shows no line")
                for theme in ("light", "dark"):
                    with self.subTest(width=w, theme=theme):
                        p.js(f"document.querySelector('input[name=appearance][value={theme}]').click()")
                        p.until(f"document.documentElement.dataset.theme === {json.dumps('dark' if theme == 'dark' else None)} "
                                f"|| ({json.dumps(theme)} === 'light' && !document.documentElement.dataset.theme)", "the appearance applied")
                        for name, alias in (("Jane Doe", "Jane,JD"), ("Jane", "Jane"), ("Mary Ann Smith", "Mary,MAS")):
                            self.type_into(p, "name", name, leave="none")
                            p.until(f"(document.querySelector('[data-alias]') || {{}}).textContent === {json.dumps(alias)}", f"{name} shows {alias}")
                            self.assertEqual(self.offer(p), {"line": LINE.format(alias), "alias": alias, "help": HELP, "under": True})
                            self.assertTrue(self.fits(p), "the line fits, with no sideways scroll")
                        for sel in ("[data-alias-offer] .alias-help", "[data-alias]"):
                            light = self.lightness(p, sel)
                            if theme == "dark":
                                self.assertGreater(light, 128, f"{sel} is light text on dark")
                            else:
                                self.assertLess(light, 128, f"{sel} is dark text on light")
                        self.type_into(p, "name", "", leave="none")
                        p.until("!document.querySelector('[data-alias-offer]')", "an empty name shows no line")
                        self.type_into(p, "name", "   ", leave="none")
                        self.assertIsNone(self.offer(p), "spaces alone show no line")
                self.assertEqual(self.saved(), {}, "nothing was saved")

    def test_C_the_line_changing_sends_nothing_and_keeps_nothing(self):
        with chrome() as cdp:
            p = self.page(cdp)
            p.width(900)
            self.open_settings(p)
            p.js("(() => { window.__sent = []; const f = window.fetch; window.fetch = (u, o) => { "
                 "if (String(u).includes('/api/profile') && o && o.method && o.method !== 'GET') window.__sent.push(String(o.body)); return f(u, o); }; "
                 "const s = XMLHttpRequest.prototype.send, op = XMLHttpRequest.prototype.open; "
                 "XMLHttpRequest.prototype.open = function (m, u, ...r) { this.__u = String(u); return op.call(this, m, u, ...r); }; "
                 "XMLHttpRequest.prototype.send = function (b) { if ((this.__u || '').includes('/api/profile')) window.__sent.push(String(b)); return s.call(this, b); }; "
                 "navigator.sendBeacon = () => { window.__sent.push('beacon'); return true; }; })()")
            for name, alias in (("Jane Doe", "Jane,JD"), ("Jane", "Jane"), ("Sam Lee", "Sam,SL")):
                self.type_into(p, "name", name, leave="none")
                p.until(f"(document.querySelector('[data-alias]') || {{}}).textContent === {json.dumps(alias)}", f"{name} shows {alias}")
            self.type_into(p, "name", "", leave="none")
            p.until("!document.querySelector('[data-alias-offer]')", "the line went")
            self.assertEqual(p.js("window.__sent"), [], "nothing is sent to /api/profile while the line changes")
            self.assertEqual(self.saved(), {}, "nothing is kept by clark")
            self.assertEqual(p.js("Object.keys(localStorage).concat(Object.keys(sessionStorage)).filter(k => /alias/i.test(k))"), [],
                             "nothing is kept in the browser")
            # a name that is saved (the box is left) sends the name and the email only: never an Alias
            self.type_into(p, "name", "Jane Doe", leave="enter")
            p.until("window.__sent.length === 1", "the name box was saved")
            self.assertNotIn("alias", p.js("window.__sent[0]").lower())
            self.assertTrue(wait(lambda: self.saved().get("profile_name") == "Jane Doe"), "the name was kept")
            self.assertNotIn("alias", json.dumps(self.saved()).lower(), "no Alias is kept")


if __name__ == "__main__":
    unittest.main()
