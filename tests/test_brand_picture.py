"""#98: the brand's picture. The server answers GET /assets/<name> for four fixed names, from the local brand folder, and nothing
else; the brand layering finds its place by a named hook. Rules: the Done-when on clark-plan #98.

Run: python3 dev/run_tests.py test_brand_picture
Every picture here is made by the test, a few bytes in a temporary folder: no real brand's file is read or committed. The
browser test needs Google Chrome and is required: it fails, never skips, without it.
"""
import json
import os
import re
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest import mock

from _paths import ROOT

from clark import page, publish, server as sv
from test_publish import made
from test_server import Running, chrome, raw_reply, wait, _Collect


def png(width=8, height=8, rgb=(200, 30, 120)):
    """A real, tiny PNG of one fictional colour."""
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    rows = b"".join(b"\0" + bytes(rgb) * width for _ in range(height))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


PNG = png()
JPEG = b"\xff\xd8\xff\xe0" + b"fictional jpeg"
WEBP = b"RIFF\x10\x00\x00\x00WEBPVP8 " + b"fictional"
TOKENS = ':root { --brand-navy: #123456; --image-cover: url("assets/cover.png"); }'
SECRET = b"\x89PNG\r\n\x1a\n" + b"a fictional secret that must never be served"


class Brand:
    """A temporary brand folder with a tokens.css and an assets folder, removed when the test ends."""

    def __init__(self, test, tokens_in=""):
        self.tmp = tempfile.TemporaryDirectory()
        test.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.dir = self.root / tokens_in
        self.assets = self.dir / "assets"
        self.assets.mkdir(parents=True)
        (self.dir / "tokens.css").write_text(TOKENS, encoding="utf-8")

    def put(self, name, data):
        (self.assets / name).write_bytes(data)
        return self.assets / name


def serve(test, brand, **kw):
    s = Running(**kw)
    s.httpd.brand_picture = lambda name: page.brand_picture(name, brand.root)      # this brand, not this laptop's
    test.addCleanup(s.close)
    return s


class Route(unittest.TestCase):
    def setUp(self):
        self.brand = Brand(self)
        self.s = serve(self, self.brand)

    def test_each_fixed_name_is_served_with_its_own_type_and_the_security_headers(self):
        for name, data, ctype in (("cover.png", PNG, "image/png"), ("cover.jpg", JPEG, "image/jpeg"),
                                  ("cover.jpeg", JPEG, "image/jpeg"), ("cover.webp", WEBP, "image/webp")):
            self.brand.put(name, data)
            status, msg, body = self.s.ask("GET", sv.BRAND_PREFIX + name)             # no token
            self.assertEqual((status, body), (200, data), name)
            self.assertEqual(msg.get_all("Content-Type"), [ctype], name)
            self.assertEqual(msg.get_all("Content-Length"), [str(len(data))])
            self.assertEqual(msg.get_all("Cache-Control"), ["no-store"])
            self.assertEqual(msg.get_all("X-Content-Type-Options"), ["nosniff"])

    def test_the_design_system_folder_counts_and_a_query_is_ignored(self):
        brand = Brand(self, "design-system")
        brand.put("cover.png", PNG)
        s = serve(self, brand)
        self.assertEqual(s.ask("GET", "/assets/cover.png?v=2")[2], PNG)

    def test_a_missing_file_is_a_404_in_plain_words_that_names_no_path(self):
        status, _, body = self.s.ask("GET", "/assets/cover.png")
        reply = json.loads(body)
        self.assertEqual((status, reply["code"], reply["ok"]), (404, "picture_not_found", False))
        self.assertEqual(reply["message"], sv.MESSAGES["picture_not_found"])
        for jargon in ("404", "Not found", "path", "folder is", self.brand.tmp.name, "Error"):
            self.assertNotIn(jargon, reply["message"])
        self.assertIn("cover.jpg", reply["message"])
        self.assertIn("reload", reply["message"])

    def test_no_tokens_css_means_no_picture(self):
        (self.brand.dir / "tokens.css").unlink()
        self.brand.put("cover.png", PNG)
        self.assertEqual(self.s.ask("GET", "/assets/cover.png")[0], 404)

    def test_a_file_that_is_not_the_picture_its_name_says_is_a_404(self):
        self.brand.put("cover.png", b"<html><script>alert(1)</script></html>")
        self.assertEqual(self.s.ask("GET", "/assets/cover.png")[0], 404, "text named .png")
        self.brand.put("cover.jpg", PNG)
        self.assertEqual(self.s.ask("GET", "/assets/cover.jpg")[0], 404, "a PNG named .jpg: the type comes from the name")
        self.brand.put("cover.webp", b"RIFF")
        self.assertEqual(self.s.ask("GET", "/assets/cover.webp")[0], 404)
        (self.brand.assets / "cover.jpeg").mkdir()
        self.assertEqual(self.s.ask("GET", "/assets/cover.jpeg")[0], 404, "a folder is not a picture")

    def test_a_file_over_the_size_limit_is_a_404(self):
        self.brand.put("cover.png", PNG)
        self.assertEqual(self.s.ask("GET", "/assets/cover.png")[0], 200)
        with mock.patch.object(page, "PICTURE_MAX_BYTES", len(PNG) - 1):
            self.assertEqual(self.s.ask("GET", "/assets/cover.png")[0], 404)
        with mock.patch.object(page, "PICTURE_MAX_BYTES", len(PNG)):
            self.assertEqual(self.s.ask("GET", "/assets/cover.png")[0], 200, "exactly the limit is allowed")

    def test_get_only(self):
        self.brand.put("cover.png", PNG)
        for method in ("POST", "PUT", "DELETE", "PATCH"):
            self.assertNotEqual(self.s.api(method, "/assets/cover.png", b"{}")[0], 200, method)
        self.assertEqual(self.s.api("POST", "/assets/cover.png", b"{}")[0], 404, "a POST is not a route (with the token)")
        self.assertEqual(self.s.ask("POST", "/assets/cover.png", {"Content-Length": "0"})[0], 403, "and needs the token")
        self.assertEqual(self.s.ask("OPTIONS", "/assets/cover.png", {"Origin": "https://evil.example"})[0], 403)
        self.assertNotEqual(self.s.ask("HEAD", "/assets/cover.png")[0], 200)

    def test_another_host_origin_or_site_is_refused_the_way_the_other_routes_do(self):
        self.brand.put("cover.png", PNG)
        for host in ("evil.example", "127.0.0.1.evil.example", "LOCALHOST", "", None, "127.0.0.1:0", "[::2]:80"):
            self.assertEqual(self.s.ask("GET", "/assets/cover.png", host=host)[0], 403, repr(host))
        for header in ({"Origin": "https://evil.example"}, {"Origin": "http://127.0.0.1.evil.example"},
                       {"Origin": "null"}, {"Sec-Fetch-Site": "cross-site"}, {"Sec-Fetch-Site": "Cross-Site"}):
            status, _, body = self.s.ask("GET", "/assets/cover.png", header)
            self.assertEqual((status, json.loads(body)["code"]), (403, "not_allowed"), header)
        for header in ({}, {"Sec-Fetch-Site": "same-origin"}, {"Sec-Fetch-Site": "none"},
                       {"Origin": f"http://127.0.0.1:{self.s.port}"}, {"Origin": f"http://localhost:{self.s.port}"}):
            self.assertEqual(self.s.ask("GET", "/assets/cover.png", header)[0], 200, header)
        for host in (f"localhost:{self.s.port}", f"[::1]:{self.s.port}"):
            self.assertEqual(self.s.ask("GET", "/assets/cover.png", host=host)[0], 200, host)

    def test_a_path_is_never_taken_from_the_request(self):
        """`../`, encoded variants, backslashes, a null byte, double slashes, absolute paths and other names: 404 each time,
        and never a file that is not one of the four names. A secret sits beside and above the assets folder to find."""
        (self.brand.dir / "secret.png").write_bytes(SECRET)
        (self.brand.root / "secret.png").write_bytes(SECRET)
        self.brand.put("cover.png", PNG)
        self.brand.put("other.png", SECRET)
        self.brand.put("logo.svg", b"<svg onload='alert(1)'/>")
        self.brand.put("cover.gif", b"GIF89a")
        self.brand.put("cover.svg", b"<svg/>")
        paths = [
            "/assets/../secret.png", "/assets/../../secret.png", "/assets/../assets/cover.png", "/assets/./cover.png",
            "/assets/..%2fsecret.png", "/assets/..%2Fsecret.png", "/assets/%2e%2e/secret.png", "/assets/%2E%2E/secret.png",
            "/assets/%2e%2e%2fsecret.png", "/assets/.%2e/secret.png", "/assets/%252e%252e/secret.png",
            "/assets/..%5csecret.png", "/assets/..\\secret.png", "/assets/%5c..%5csecret.png", "/assets/\\secret.png",
            "/assets/cover.png%00.jpg", "/assets/cover.png%00", "/assets/%00cover.png", "/assets/cover.png\\",
            "//assets/cover.png", "///assets/cover.png", "/assets//cover.png", "/assets///cover.png", "/assets/cover.png/",
            "/assets/cover.png/.", "/assets/cover.png/..", "/assets/%63over.png", "/assets/cover%2epng", "/assets/cover.png%20",
            "/assets/cover.png;x", "/assets/cover.png#x/../x", "/%61ssets/cover.png", "/assets%2fcover.png", "/Assets/cover.png",
            "/assets/COVER.PNG", "/assets/Cover.png", "/assets/other.png", "/assets/logo.svg", "/assets/cover.gif",
            "/assets/cover.svg", "/assets/cover", "/assets/cover.", "/assets/.png", "/assets/", "/assets", "/assets/..",
            "/assets/secret.png", "/secret.png", "/assets/tokens.css", "/assets/../tokens.css", "/tokens.css", "/cover.png",
            "/assets/etc/passwd", "/assets//etc/passwd", "/etc/passwd", "/assets/C:/cover.png", "/assets/C:\\cover.png",
            "/assets/file:///etc/passwd", "/assets/http://127.0.0.1/cover.png", f"/assets/{self.brand.dir}/secret.png",
            f"/assets/{self.brand.dir / 'assets' / 'cover.png'}", f"http://127.0.0.1:{self.s.port}/assets/cover.png",
            "/assets/cover.png/../../secret.png", "*", "/assets/%", "/assets/%zz",
            "/assets/\u202ecover.png", "/assets/cover\u2024png", "/assets/ cover.png",
        ]
        for path in paths:
            try:
                status, _, body = raw_reply(self.s.port, f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1:{self.s.port}\r\n\r\n"
                                            .encode("utf-8", "surrogateescape"))
            except (OSError, ValueError):
                continue                                           # a path the server hangs up on is not served either
            self.assertNotEqual(body, SECRET, path)
            self.assertNotEqual(status, 200, path)
            self.assertIn(status, (400, 403, 404), path)

    def test_the_odd_request_lines_a_client_library_will_not_send(self):
        self.brand.put("cover.png", PNG)
        for line in (b"GET /assets/cover.png\x00 HTTP/1.1", b"GET /assets/cover.png\x00.jpg HTTP/1.1",
                     b"GET /assets/..\\secret.png HTTP/1.1", b"GET //assets/cover.png HTTP/1.1",
                     b"GET /assets/cover.png%00 HTTP/1.1", b"GET /assets/\x00 HTTP/1.1"):
            status, _, body = raw_reply(self.s.port, line + f"\r\nHost: 127.0.0.1:{self.s.port}\r\n\r\n".encode())
            self.assertIn(status, (400, 404), line)
            self.assertNotEqual(body, PNG, line)
        self.assertEqual(raw_reply(self.s.port, f"GET /assets/cover.png HTTP/1.1\r\nHost: 127.0.0.1:{self.s.port}\r\n\r\n"
                                   .encode())[0], 200, "the same request without the odd part is served")

    @unittest.skipUnless(hasattr(os, "symlink"), "this system has no symbolic links")
    def test_a_link_out_of_the_brand_folder_is_not_followed_and_one_inside_is(self):
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        (Path(outside.name) / "cover.png").write_bytes(SECRET)
        try:
            os.symlink(Path(outside.name) / "cover.png", self.brand.assets / "cover.png")      # the file itself
            os.symlink(Path(outside.name), self.brand.dir / "linked")
        except OSError:
            self.skipTest("this account may not make symbolic links")
        self.assertEqual(self.s.ask("GET", "/assets/cover.png")[0], 404, "a file that is a link out")
        (self.brand.assets / "cover.png").unlink()
        self.brand.assets.rmdir()
        os.symlink(Path(outside.name), self.brand.dir / "assets")                                # the folder itself
        self.assertEqual(self.s.ask("GET", "/assets/cover.png")[0], 404, "an assets folder that is a link out")
        (self.brand.dir / "assets").unlink()
        (self.brand.dir / "assets").mkdir()
        self.brand.put("real.png", PNG)
        os.symlink(self.brand.assets / "real.png", self.brand.assets / "cover.png")              # a link that stays inside
        self.assertEqual(self.s.ask("GET", "/assets/cover.png")[2], PNG)

    def test_the_names_are_looked_up_and_never_joined_onto_a_path(self):
        self.brand.put("cover.png", PNG)
        for name in ("../secret.png", "cover.png/..", "/etc/passwd", "cover.PNG", "", None, "assets/cover.png"):
            self.assertIsNone(page.brand_picture(name, self.brand.root), repr(name))
        self.assertEqual(page.brand_picture("cover.png", self.brand.root), (PNG, "image/png"))
        src = (ROOT / "src" / "clark" / "server.py").read_text(encoding="utf-8")
        self.assertNotRegex(src, r"Path\(|os\.path|open\(", "the server touches no path: only page.brand_picture does")

    def test_the_brand_pictures_are_never_in_a_tracked_file(self):
        for f in (ROOT / "src" / "clark" / "page" / "page.html", ROOT / "src" / "clark" / "brand" / "tokens.css"):
            text = f.read_text(encoding="utf-8")
            self.assertNotRegex(text, r"url\(\s*[\"']?(?!data:)[^)]*\.(png|jpe?g|webp)", f.name)
            self.assertNotIn(PNG[8:20].decode("latin-1"), text)
        self.assertEqual(sorted(page.PICTURES), ["cover.jpeg", "cover.jpg", "cover.png", "cover.webp"])
        self.assertIn("system/branding/", (ROOT / ".gitignore").read_text(encoding="utf-8"))


class Layering(unittest.TestCase):
    """The brand is layered after the element with id="brand-demo", found by that name and not by one exact string."""

    def layered(self, html, css=":root { --brand-navy: #123456; }"):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "tokens.css").write_text(css, encoding="utf-8")
            with mock.patch.object(page, "PAGE", mock.Mock(read_text=lambda **kw: html)):
                return page.page_html(tmp)

    def test_the_committed_page_has_exactly_one_hook_and_the_layering_uses_it(self):
        html = page.PAGE.read_text(encoding="utf-8")
        self.assertEqual(len(page.DEMO_OPEN.findall(html)), 1)
        self.assertEqual(page.DEMO_ID, "brand-demo")
        out = self.layered(html)
        self.assertEqual(out.count('id="brand-local"'), 1)
        self.assertLess(out.index('id="brand-demo"'), out.index('id="brand-local"'))
        self.assertEqual(len(sv.csp_hashes(out)["style"]), 2, "the policy hashes both blocks")

    def test_the_layout_around_the_hook_may_change(self):
        demo = ":root{--a:1}"
        shapes = [
            f'<html><head><style id="brand-demo">{demo}</style></head><body></body></html>',                    # no newline
            f'<html><head>\r\n<style id="brand-demo">\r\n{demo}\r\n</style>\r\n</head>\r\n<body></body></html>',     # CRLF
            f'<html><head><style   media="all"  id = \'brand-demo\' >{demo}</style ></head><body></body></html>',     # spacing, order
            f'<html><head><STYLE ID="brand-demo">{demo}</STYLE><style>x{{}}</style></head></html>',                  # case, a later block
            f'<html><head><style id=brand-demo>{demo}</style></head></html>',                                        # unquoted
            f'<html><head><style id="brand-demo">{demo}</style><title>x</title></head></html>',                      # more in the head
        ]
        for html in shapes:
            out = self.layered(html)
            self.assertIn('<style id="brand-local">', out, html)
            self.assertIn("--brand-navy: #123456", out, html)
            self.assertLess(out.index("brand-demo"), out.index('id="brand-local"'), html)
            self.assertEqual(len(sv.csp_hashes(out)["style"]), 2 + (html.count("<style>")), html)

    def test_a_page_with_no_hook_raises_in_words_and_does_not_drop_the_brand(self):
        for html in ('<html><head><style>x{}</style></head></html>', '<html><head><style id="brand-demo-2">x{}</style></head></html>',
                     '<html><head><style id="brand-demo">never closed</head></html>', '<html><head></head></html>',
                     '<html><body><p id="brand-demo">x</p></body></html>'):
            with self.assertRaises(page.PageError, msg=html) as e:
                self.layered(html)
            self.assertIn("python3 dev/tools/build_page.py", str(e.exception))
            self.assertNotIn(".py:", str(e.exception))

    def test_no_local_brand_needs_no_hook(self):
        with tempfile.TemporaryDirectory() as empty:
            with mock.patch.object(page, "PAGE", mock.Mock(read_text=lambda **kw: "<html>no hook</html>")):
                self.assertEqual(page.page_html(empty), "<html>no hook</html>")

    def test_the_output_is_what_the_old_exact_string_gave(self):
        """The same bytes as before for the committed page, so no policy hash and no published file changes."""
        html = page.PAGE.read_text(encoding="utf-8")
        old = html.replace("</style>\n</head>", f'</style>\n<style id="brand-local">\n{page.CLIENT_BRAND}:root {{ --x: 1; }}\n</style>\n</head>', 1)
        self.assertEqual(self.layered(html, ":root { --x: 1; }"), old)


class Publish(unittest.TestCase):
    """The published file stays one self-contained file: a brand that names its picture by address is refused, as before."""

    def test_a_brand_that_names_the_route_is_refused_and_the_file_never_carries_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "tokens.css").write_text(TOKENS, encoding="utf-8")
            self.assertIn('url("assets/cover.png")', page.page_html(tmp), "the page's own text is not changed by the route")
            with self.assertRaises(publish.PublishError):
                made(branding=tmp)
            (Path(tmp) / "tokens.css").write_text(":root { --brand-navy: #123456; }", encoding="utf-8")
            (Path(tmp) / "assets").mkdir()
            (Path(tmp) / "assets" / "cover.png").write_bytes(PNG)
            _, _, text = made(branding=tmp)
        self.assertNotIn(sv.BRAND_PREFIX, text)
        self.assertNotIn(PNG[8:20].decode("latin-1"), text, "the picture is not copied into the file")
        self.assertEqual(publish.outside_addresses(text), [], "no outside address")


# ===== the real browser =====
class RealBrowser(unittest.TestCase):
    def test_a_planted_brand_picture_loads_and_nothing_else_of_this_server_is_an_image(self):
        brand = Brand(self)
        (brand.dir / "tokens.css").write_text(TOKENS + "\nbody { background-image: var(--image-cover); }", encoding="utf-8")
        brand.put("cover.png", png(8, 8))
        s = serve(self, brand, page_html=lambda: page.page_html(brand.root))
        blocked = []
        handler = _Collect(blocked)
        sv.LOG.addHandler(handler)
        sv.LOG.setLevel("INFO")
        self.addCleanup(sv.LOG.removeHandler, handler)
        load = ("new Promise(function (ok) { var i = new Image(); i.onload = function () { ok([i.naturalWidth, i.naturalHeight]); }; "
                "i.onerror = function () { ok('error'); }; i.src = %s; })")
        with mock.patch.dict(sv.CSP_REPORTS, since=__import__("time").time(), n=0, dropped=0):
            with chrome() as cdp:
                tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
                sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
                cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{s.port}/"}, sid)
                self.assertTrue(wait(lambda: cdp.js("document.readyState", sid) == "complete"))
                # the brand's own CSS value, as the page would use it, resolved against the page
                value = cdp.js("getComputedStyle(document.documentElement).getPropertyValue('--image-cover').trim()", sid)
                self.assertEqual(value, 'url("assets/cover.png")')
                got = cdp.call("Runtime.evaluate", {"expression": load % json.dumps("assets/cover.png"), "awaitPromise": True,
                                                    "returnByValue": True}, sid)["result"]["value"]
                self.assertEqual(got, [8, 8], "the planted picture loaded: its natural size is 8 by 8")
                self.assertIn("assets/cover.png", cdp.js("getComputedStyle(document.body).backgroundImage", sid))
                self.assertEqual(blocked, [], f"the policy blocked nothing: {blocked}")
                # an image from any other path of this server is blocked by the policy (img-src names only the route)
                other = cdp.call("Runtime.evaluate", {"expression": load % json.dumps("/health"), "awaitPromise": True,
                                                      "returnByValue": True}, sid)["result"]["value"]
                self.assertEqual(other, "error")
                self.assertTrue(wait(lambda: any("img-src" in b for b in blocked), 10), f"the report named img-src: {blocked}")
                self.assertTrue(any("img-src self" in b for b in blocked), blocked)
                # and a different file name under the route is a plain 404
                miss = cdp.call("Runtime.evaluate", {"expression": load % json.dumps("assets/other.png"), "awaitPromise": True,
                                                     "returnByValue": True}, sid)["result"]["value"]
                self.assertEqual(miss, "error")


if __name__ == "__main__":
    unittest.main()
