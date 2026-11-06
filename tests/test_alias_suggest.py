"""#613: the Alias clark suggests from a full name (src/clark/page/src/logic/alias.js): the first name, then the initials, comma-separated.
"Jane Doe" suggests "Jane,JD"; a one-word name suggests only that word; an empty name suggests nothing; a suggestion never overwrites
an Alias already typed. Fictional names only. Settings › Personal › About you has an Alias box under Your name, kept by clark beside
the name and the email: while nothing was saved and nobody has typed in it, it is filled in from the name with a space after the
comma ("Jane, JD") and follows the name; once saved, or typed in, it is never filled in again. It is checked in the real page
at 1400 and 900 px, light and dark.

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
from _new_page import reload_to_new_page  # noqa: E402

WIDTHS = (1400, 900)
LABEL = "Alias"
PLACEHOLDER = "What colleagues call you, or your initials"
HELP = "Your first name and your initials, worked out from your full name. You can change it."

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
    """The Alias box under the name box in the real page, kept by clark."""
    saved = about.AboutYou.saved
    open_menu = about.AboutYou.open_menu
    open_settings = about.AboutYou.open_settings
    type_into = about.AboutYou.type_into
    toast_is = about.AboutYou.toast_is
    handled = about.AboutYou.handled
    close_menu = about.AboutYou.close_menu

    def box(self, p):
        return p.js("(() => { const i = document.querySelector('[data-about-you] #about-alias'); if (!i) return null; const f = i.closest('.fld'); "
                    "const prev = f.previousElementSibling; return {label: f.querySelector('label').textContent, placeholder: i.placeholder, "
                    "help: f.querySelector('small').textContent, value: i.value, autocomplete: i.autocomplete, "
                    "under: !!prev && !!prev.querySelector('#about-name')}; })()")

    def alias(self, p):
        return p.js("document.querySelector('#about-alias').value")

    def settle(self, p, frames=3):
        """Let the page draw `frames` frames (an input event is taken in a frame), waiting on a counter the page itself counts."""
        p.js(f"window.__fr = 0; (function tick() {{ window.__fr++; if (window.__fr < {frames}) requestAnimationFrame(tick); }})()")
        p.until(f"window.__fr >= {frames}", "the page drew the frames")

    def alias_is(self, p, want, why):
        """The box holds `want` once the page has taken what was typed (a bounded wait, then the assertion that can fail)."""
        p.until(f"document.querySelector('#about-alias').value === {json.dumps(want)}", why)
        self.assertEqual(self.alias(p), want, why)

    def fits(self, p):
        return p.js("(() => { const f = document.querySelector('#about-alias').closest('.fld'), a = document.querySelector('[data-about-you]'); "
                    "const r = f.getBoundingClientRect(), b = a.getBoundingClientRect(); "
                    "return r.width > 0 && r.right <= b.right + 0.5 && document.documentElement.scrollWidth <= document.documentElement.clientWidth "
                    "&& f.querySelector('small').scrollWidth <= f.querySelector('small').clientWidth + 0.5; })()")

    def lightness(self, p, sel, prop="color"):
        rgb = p.js(f"getComputedStyle(document.querySelector({json.dumps(sel)})).{prop}")
        r, g, b = [int(x) for x in rgb[rgb.index("(") + 1:rgb.index(")")].split(",")[:3]]
        return (r + g + b) / 3

    def test_C_the_box_is_filled_from_the_name_at_both_widths_light_and_dark(self):
        for w in WIDTHS:
            with chrome() as cdp:
                p = self.page(cdp)
                p.width(w)
                self.open_settings(p)
                self.assertEqual(self.box(p), {"label": LABEL, "placeholder": PLACEHOLDER, "help": HELP, "value": "", "autocomplete": "nickname", "under": True},
                                 "an empty name leaves the Alias empty")
                for theme in ("light", "dark"):
                    with self.subTest(width=w, theme=theme):
                        p.js(f"document.querySelector('#personal [data-appearance] button[data-theme-pick={theme}]').click()")
                        p.until(f"document.documentElement.dataset.theme === {json.dumps('dark' if theme == 'dark' else None)} "
                                f"|| ({json.dumps(theme)} === 'light' && !document.documentElement.dataset.theme)", "the appearance applied")
                        for name, alias in (("Jane Doe", "Jane, JD"), ("Jane", "Jane"), ("Mary Ann Smith", "Mary, MAS")):
                            self.type_into(p, "name", name, leave="none")
                            p.until(f"document.querySelector('#about-alias').value === {json.dumps(alias)}", f"{name} fills in {alias}")
                            self.assertTrue(self.fits(p), "the box fits, with no sideways scroll")
                        for sel in ("#about-alias", "#about-alias-line"):
                            light = self.lightness(p, sel)
                            if theme == "dark":
                                self.assertGreater(light, 128, f"{sel} is light text on dark")
                            else:
                                self.assertLess(light, 128, f"{sel} is dark text on light")
                        self.assertGreater(abs(self.lightness(p, "#about-alias") - self.lightness(p, "#about-alias", "backgroundColor")), 100,
                                           "the Alias reads against its box")
                        self.type_into(p, "name", "", leave="none")
                        p.until("document.querySelector('#about-alias').value === ''", "an empty name leaves the Alias empty")
                        self.type_into(p, "name", "   ", leave="none")
                        self.settle(p)
                        self.assertEqual(self.alias(p), "", "spaces alone leave it empty")
                self.assertEqual(self.saved(), {}, "nothing was saved while nothing was left")

    def test_C_jane_doe_is_saved_with_jane_jd_and_a_typed_alias_is_kept_when_the_name_changes(self):
        with chrome() as cdp:
            p = self.page(cdp)
            p.width(1400)
            self.open_settings(p)
            self.type_into(p, "name", "Jane Doe")
            self.toast_is(p, "Name saved.")
            self.assertTrue(wait(lambda: self.saved().get("profile_alias") == "Jane, JD"), "the filled-in Alias is kept, as shown")
            self.assertEqual(self.saved().get("profile_name"), "Jane Doe")
            self.handled(p, "Jane Doe")
            # once saved, the Alias is frozen: a later name change in the same session leaves it as it is, in the box and in clark
            self.type_into(p, "name", "Jane Roe")
            self.toast_is(p, "Name saved.")
            self.assertTrue(wait(lambda: self.saved().get("profile_name") == "Jane Roe"))
            self.handled(p, "Jane Roe")             # the page has taken that save, so the next toast speaks only of the Alias
            self.settle(p)
            self.assertEqual(self.alias(p), "Jane, JD", "a saved Alias does not follow the name")
            self.assertEqual(self.saved().get("profile_alias"), "Jane, JD", "a saved Alias is not rewritten")
            # typed in, the Alias is the person's
            self.type_into(p, "alias", "JJ")
            self.toast_is(p, "Alias saved.")
            self.assertTrue(wait(lambda: self.saved().get("profile_alias") == "JJ"))
            for name in ("Sam Lee", "Pat Roe"):
                self.type_into(p, "name", name)
                self.assertTrue(wait(lambda: self.saved().get("profile_name") == name))
                self.handled(p, name)
                self.settle(p)
                self.assertEqual(self.alias(p), "JJ", "a typed Alias is kept when the name changes")
                self.assertEqual(self.saved().get("profile_alias"), "JJ")
            # emptied by the person, it stays empty
            self.type_into(p, "alias", "")
            self.toast_is(p, "Alias cleared.")
            self.type_into(p, "name", "Dana Moss")
            self.assertTrue(wait(lambda: self.saved().get("profile_name") == "Dana Moss"))
            self.handled(p, "Dana Moss")
            self.settle(p)
            self.assertEqual(self.alias(p), "", "an Alias the person emptied is not filled in again")

    def test_C_a_saved_alias_is_never_replaced_after_a_reload(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p)
            self.type_into(p, "name", "Jane Doe")
            self.assertTrue(wait(lambda: self.saved().get("profile_alias") == "Jane, JD"))
            self.handled(p, "Jane Doe")             # the page has taken the name's save before the Alias is typed over the filled-in one
            self.type_into(p, "alias", "Janey")
            self.assertTrue(wait(lambda: self.saved().get("profile_alias") == "Janey"))
            reload_to_new_page(p.js, "!!document.querySelector('#profile-btn')", "the page again (not the one being left)")
            self.open_settings(p)
            p.until("document.querySelector('#about-alias').value === 'Janey'", "the Alias is read from clark")
            self.type_into(p, "name", "Sam Lee")
            self.assertTrue(wait(lambda: self.saved().get("profile_name") == "Sam Lee"))
            self.handled(p, "Sam Lee")
            self.settle(p)
            self.assertEqual(self.alias(p), "Janey", "a saved Alias is never replaced by a suggestion")
            self.assertEqual(self.saved().get("profile_alias"), "Janey")

    def test_C_undo_of_the_first_save_lets_the_alias_follow_the_name_again(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p)
            self.type_into(p, "name", "Jane Doe")
            self.toast_is(p, "Name saved.")
            self.handled(p, "Jane Doe")
            self.assertTrue(wait(lambda: self.saved().get("profile_alias") == "Jane, JD"))
            p.until("!!document.querySelector('.toast [data-undo]')", "Undo is still offered")
            p.js("document.querySelector('.toast [data-undo]').click()")
            self.handled(p, "", "")
            self.assertTrue(wait(lambda: self.saved().get("profile_alias", "") == ""), "Undo takes the first Alias back with the name")
            self.alias_is(p, "", "Undo empties the Alias box")
            self.type_into(p, "name", "Sam Lee", leave="none")
            p.until("document.querySelector('#about-alias').value === 'Sam, SL'", "with nothing saved, the Alias follows the name again")

    def test_C_an_emptied_alias_stays_empty_in_the_session_and_is_suggested_again_after_a_reload(self):
        # an empty saved Alias cannot be told from one never set: after a reload the box is filled from the name again (and saved on the
        # next save), which the person can empty again
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p)
            self.type_into(p, "name", "Jane Doe")
            self.assertTrue(wait(lambda: self.saved().get("profile_alias") == "Jane, JD"))
            self.type_into(p, "alias", "")
            self.toast_is(p, "Alias cleared.")
            self.assertTrue(wait(lambda: self.saved().get("profile_alias", "") == ""))
            self.type_into(p, "name", "Jane Roe")
            self.assertTrue(wait(lambda: self.saved().get("profile_name") == "Jane Roe"))
            self.handled(p, "Jane Roe")
            self.settle(p)
            self.assertEqual(self.alias(p), "", "an Alias the person emptied is not filled in again in that session")
            self.assertEqual(self.saved().get("profile_alias", ""), "")
            reload_to_new_page(p.js, "!!document.querySelector('#profile-btn')", "the page again (not the one being left)")
            self.open_settings(p)
            p.until("document.querySelector('#about-alias').value === 'Jane, JR'", "an empty saved Alias is suggested from the name again")
            self.assertEqual(self.saved().get("profile_alias", ""), "", "a suggestion alone writes nothing")

    def test_C_a_refused_alias_says_why_under_its_box_and_writes_nothing(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p)
            self.type_into(p, "name", "Jane Doe")
            self.assertTrue(wait(lambda: self.saved().get("profile_alias") == "Jane, JD"))
            before = self.saved()
            self.type_into(p, "alias", "A" * 61)
            bad = "document.querySelector('#about-alias').closest('.fld').querySelector('.fld-bad').textContent"
            p.until(f"{bad} !== ''", "the refusal shows")
            self.assertEqual(p.js(bad), "Your Alias is too long. Use 60 characters or fewer. Nothing was saved.")
            self.assertEqual(p.js("document.querySelector('#about-alias').getAttribute('aria-invalid')"), "true")
            self.assertEqual(self.alias(p), "A" * 61, "what was typed stays in the box")
            self.assertEqual(self.saved(), before, "nothing was written")


if __name__ == "__main__":
    unittest.main()
