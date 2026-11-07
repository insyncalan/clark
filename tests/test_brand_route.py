"""Row 944, track T3 (tests first): the editor follows the open project's brand, server side. Design note, section 3 T3:
the swap is a fresh page load, GET /?project=<code>; the server hands the code to the page_html(project=None) seam and sends that
project's single <style id="brand-local"> with the CSP hashes of exactly those bytes (never two brand blocks, no CSP loosening);
pictures are GET /assets/<id>/<name> through the two-argument brand_picture(name, brand_id) seam (an id not installed, or any
other shape, is the existing 404 picture_not_found).

These tests need nothing from T1 or T2: the seams are stubbed here by what __main__ will pass (the minimal stand-in for
project -> projects.brand -> brands.folder is the dict `BRAND_OF` below). They fail today because page_route calls
page_html() with no project and brand_picture_route calls brand_picture(name) with one argument.

Run: python3 dev/run_tests.py test_brand_route
Every brand here is made by the test (fictional colours, 8 by 8 pictures); no real brand's file is read.
"""
import base64
import hashlib
import json
import re
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT  # noqa: F401

from clark import page, server as sv
from test_brand_picture import png
from test_server import Running

NAVY = {"ONE": "#123456", "TWO": "#654321"}
PIC = {"one-brand": png(8, 8, (10, 20, 30)), "two-brand": png(8, 8, (40, 50, 60))}
BRAND_OF = {"ONE": "one-brand", "TWO": "two-brand"}          # the stand-in for projects.brand; THREE and unknown codes are Generic
BLOCK = re.compile(r'<style id="brand-local">.*?</style>', re.S)


def make_brands(case):
    """{"one-brand": folder, "two-brand": folder, None: an empty folder (Generic: no tokens, so no block)} in a temporary place."""
    tmp = tempfile.TemporaryDirectory()
    case.addCleanup(tmp.cleanup)
    root = Path(tmp.name)
    folders = {}
    for project, bid in BRAND_OF.items():
        d = root / bid
        (d / "assets").mkdir(parents=True)
        (d / "tokens.css").write_text(
            f':root {{ --brand-navy: {NAVY[project]}; --image-cover: url("/assets/{bid}/cover.png"); }}\n:root[data-theme=auto], :root[data-theme=dark] {{ --brand-navy: {NAVY[project]}; }}\nbody {{ background-image: var(--image-cover); }}',
            encoding="utf-8")
        (d / "assets" / "cover.png").write_bytes(PIC[bid])
        folders[bid] = d
    (root / "generic").mkdir()
    folders[None] = root / "generic"
    return folders


def layered(html, folder):
    """page.page_html's own layering (the brand-local block after the demo block) over a page the caller built (the browser tests' hook page)."""
    css = page.local_tokens(folder)
    if css is None:
        return html
    i = page.after_demo_block(html)
    return html[:i] + f'\n<style id="brand-local">\n{page.CLIENT_BRAND}{page.escape_style(css)}\n</style>' + html[i:]


def seam(folders, seen=None, base=None):
    """What __main__ will pass: the open project's code -> that brand's folder -> page.page_html(branding=folder).
    `base` (the browser tests): a function giving the page to layer the brand on, in place of the served page."""
    def page_html(project=None):
        if seen is not None:
            seen.append(project)
        folder = folders[BRAND_OF.get(project)]
        return page.page_html(branding=folder) if base is None else layered(base(), folder)
    return page_html


def picture_seam(folders):
    """brand_picture(name, brand_id): the id must be installed and the name in BRAND_PICTURES; nothing is joined onto a path."""
    asked = []

    def brand_picture(name, brand_id):
        asked.append(brand_id)
        if brand_id not in PIC or name not in sv.BRAND_PICTURES:
            return None
        return page.brand_picture(name, folders[brand_id]) if name == "cover.png" else None
    brand_picture.asked = asked
    return brand_picture


def sha(text):
    return "'sha256-" + base64.b64encode(hashlib.sha256(text.encode("utf-8")).digest()).decode() + "'"


class ThePageFollowsTheProject(unittest.TestCase):
    def setUp(self):
        self.folders = make_brands(self)
        self.seen = []
        self.s = Running(page_html=seam(self.folders, self.seen))
        self.addCleanup(self.s.close)

    def get(self, path="/"):
        status, msg, body = self.s.ask("GET", path)
        return status, msg, body.decode("utf-8")

    def test_project_one_gets_its_block_and_not_the_other(self):
        status, _, html = self.get("/?project=ONE")
        self.assertEqual(status, 200)
        self.assertEqual(len(re.findall(r'id="brand-local"', html)), 1)
        self.assertIn(NAVY["ONE"], html)
        self.assertNotIn(NAVY["TWO"], html)
        self.assertNotIn("two-brand", html)

    def test_project_two_gets_its_block_and_not_the_other(self):
        status, _, html = self.get("/?project=TWO")
        self.assertEqual(status, 200)
        self.assertEqual(len(re.findall(r'id="brand-local"', html)), 1)
        self.assertIn(NAVY["TWO"], html)
        self.assertNotIn(NAVY["ONE"], html)
        self.assertNotIn("one-brand", html)

    def test_generic_unknown_malformed_and_missing_codes_get_the_page_with_no_brand_block(self):
        for q in ("/?project=THREE", "/?project=NOPE", "/?project=..%2f..%2fetc", "/?project=" + "A" * 500, "/?project=", "/"):
            status, _, html = self.get(q)
            self.assertEqual(status, 200, q)
            self.assertNotIn('id="brand-local"', html, q)
            self.assertNotIn(NAVY["ONE"], html, q)
            self.assertNotIn(NAVY["TWO"], html, q)

    def test_the_seam_is_only_given_a_well_formed_code_or_none(self):
        for q in ("/?project=ONE", "/?project=%3Cscript%3E", "/?project=" + "A" * 500, "/?project=a%00b", "/?project=ONE&project=TWO", "/"):
            self.get(q)
        self.assertTrue(self.seen, "the server called the page seam")
        for got in self.seen:
            self.assertTrue(got is None or sv.PROJECT_CODE.fullmatch(got), f"the seam was handed {got!r}")

    def test_the_policy_hashes_the_swapped_block_and_loosens_nothing(self):
        hashes = {}
        for code in ("ONE", "TWO"):
            status, msg, html = self.get(f"/?project={code}")
            policy = msg.get("Content-Security-Policy")
            block = BLOCK.search(html).group(0)
            inner = block[len('<style id="brand-local">'):-len("</style>")]
            self.assertIn(sha(inner), policy, "the hash of this response's own brand bytes is in its policy")
            elem = next(p for p in policy.split("; ") if p.startswith("style-src-elem"))
            self.assertNotIn("unsafe-inline", elem)
            self.assertNotIn("unsafe-eval", policy)
            hashes[code] = sha(inner)
        self.assertNotEqual(hashes["ONE"], hashes["TWO"])
        _, msg, html = self.get("/?project=TWO")
        self.assertNotIn(hashes["ONE"], msg.get("Content-Security-Policy"), "one project's policy never names the other brand's bytes")

    def test_the_brand_block_comes_after_the_demo_block_and_the_security_headers_stay(self):
        status, msg, html = self.get("/?project=ONE")
        self.assertLess(html.index('id="brand-demo"'), html.index('id="brand-local"'))
        self.assertEqual(msg.get_all("Cache-Control"), ["no-store"])
        self.assertEqual(msg.get_all("X-Content-Type-Options"), ["nosniff"])

    def test_the_other_host_is_refused_with_a_project_in_the_address_too(self):
        status, _, _ = self.s.ask("GET", "/?project=ONE", host="evil.example")
        self.assertNotEqual(status, 200)

    def test_a_brand_block_is_not_offered_by_an_api_route(self):
        # the design note rejects the other shape (a route returning the block; the policy would have to name every brand's hash)
        for path in ("/api/brand?project=ONE", "/brand?project=ONE"):
            status, _, body = self.s.ask("GET", path)
            self.assertIn(status, (403, 404), path)       # no token: refused before the route is looked up
            self.assertNotIn(NAVY["ONE"].encode(), body)


class ThePicturesFollowTheBrand(unittest.TestCase):
    def setUp(self):
        self.folders = make_brands(self)
        self.s = Running()
        self.seam = self.s.httpd.brand_picture = picture_seam(self.folders)
        self.addCleanup(self.s.close)

    def test_each_installed_id_serves_its_own_cover_with_the_security_headers(self):
        for bid, data in PIC.items():
            status, msg, body = self.s.ask("GET", f"{sv.BRAND_PREFIX}{bid}/cover.png")
            self.assertEqual((status, body), (200, data), bid)
            self.assertEqual(msg.get_all("Content-Type"), ["image/png"])

    def test_an_id_not_installed_is_the_existing_404(self):
        status, _, body = self.s.ask("GET", f"{sv.BRAND_PREFIX}unknown/cover.png")
        self.assertEqual(status, 404)
        self.assertEqual(json.loads(body)["code"], "picture_not_found")

    def test_any_other_shape_is_a_404_and_never_a_file(self):
        for path in ("/assets/one-brand/../two-brand/cover.png", "/assets/one-brand/logo.png", "/assets/one-brand/cover.png/extra",
                     "/assets/one-brand/", "/assets//cover.png", "/assets/%2e%2e/one-brand/cover.png", "/assets/one-brand%2fcover.png",
                     "/assets/ONE-BRAND/cover.png", "/assets/../cover.png", "/assets/..-/cover.png"):
            status, _, body = self.s.ask("GET", path)
            self.assertEqual(status, 404, path)
            for data in PIC.values():
                self.assertNotEqual(body, data, path)
        self.assertEqual([i for i in self.seam.asked if i not in PIC], [])      # no id of another shape reached the seam

    def test_the_servers_allow_list_still_equals_the_pages(self):
        self.assertEqual(tuple(sv.BRAND_PICTURES), tuple(page.PICTURES))


if __name__ == "__main__":
    unittest.main()
