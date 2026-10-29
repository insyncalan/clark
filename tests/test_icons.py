"""#73: clark's icon files, and the page carrying them. Rules: Done-when on the planning repo #73.

Run: python3 dev/run_tests.py test_icons
Standard library only: a PNG's size is read from its IHDR chunk. The icon is clark's own (the "Sibling of creaite" option), not
taken from creaite. The page has no route for files, so the favicon, its PNG fallback and the touch icon are data: links.
"""
import base64
import hashlib
import re
import struct
import sys
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT, TOOLS

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402

from clark import page  # noqa: E402

ASSETS = ROOT / "src" / "clark" / "page" / "assets"
PNG_SIZES = {"clark-icon-16.png": 16, "clark-icon-32.png": 32, "clark-icon-180.png": 180, "clark-icon-192.png": 192,
             "clark-icon-512.png": 512, "clark-icon-maskable-512.png": 512}
LINK = re.compile(r"<link\b[^>]*>")
COMMENT = re.compile(r"<!--(.*?)-->", re.S)
DATA_SVG = re.compile(r"data:image/svg\+xml;base64,([A-Za-z0-9+/=]+)")
ALLOWED_COMMENT = "Sibling of creaite, option A"


def png_size(path):
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n" and data[12:16] == b"IHDR", f"{path.name} is not a PNG"
    return struct.unpack(">II", data[16:24])


class Files(unittest.TestCase):
    def test_each_png_has_the_size_its_name_says(self):
        for name, side in PNG_SIZES.items():
            self.assertEqual(png_size(ASSETS / name), (side, side), name)

    def test_the_svg_is_square_and_has_a_viewbox(self):
        svg = (ASSETS / "clark-icon.svg").read_text(encoding="utf-8")
        box = re.search(r'viewBox="0 0 (\d+) (\d+)"', svg)
        self.assertIsNotNone(box)
        self.assertEqual(box.group(1), box.group(2))

    def test_there_are_no_other_files(self):
        self.assertEqual(sorted(p.name for p in ASSETS.iterdir()), sorted([*PNG_SIZES, "clark-icon.svg"]))


class Comments(unittest.TestCase):
    """The SVG is copied into the page as base64, so a comment in it would ship: only the one neutral line may be there."""

    def test_the_svg_has_one_comment_and_it_is_the_neutral_line(self):
        svg = (ASSETS / "clark-icon.svg").read_text(encoding="utf-8")
        self.assertEqual([c.strip() for c in COMMENT.findall(svg)], [ALLOWED_COMMENT])

    def test_the_page_has_no_comment_beyond_it_in_the_text_or_in_any_decoded_svg(self):
        html = page.PAGE.read_text(encoding="utf-8")
        self.assertEqual(COMMENT.findall(html), [], "no comment in the page's own text")
        copies = DATA_SVG.findall(html)
        self.assertGreaterEqual(len(copies), 2, "the favicon link and the top bar's background")
        for b64 in copies:
            svg = base64.b64decode(b64).decode("utf-8")
            self.assertEqual([c.strip() for c in COMMENT.findall(svg)], [ALLOWED_COMMENT])

    def test_every_svg_data_copy_in_the_page_is_the_asset_file(self):
        html = page.PAGE.read_text(encoding="utf-8")
        asset = (ASSETS / "clark-icon.svg").read_bytes()
        for b64 in DATA_SVG.findall(html):
            self.assertEqual(base64.b64decode(b64), asset)

    def test_no_png_carries_a_text_chunk(self):
        for name in PNG_SIZES:
            data = (ASSETS / name).read_bytes()
            pos, kinds = 8, []
            while pos < len(data):
                length, = struct.unpack(">I", data[pos:pos + 4])
                kinds.append(data[pos + 4:pos + 8])
                pos += 12 + length
            self.assertFalse({b"tEXt", b"iTXt", b"zTXt"} & set(kinds), name)


class InThePage(unittest.TestCase):
    def setUp(self):
        self.html = page.PAGE.read_text(encoding="utf-8")

    def test_the_head_has_the_svg_favicon_the_32_px_fallback_and_the_touch_icon_as_data(self):
        links = LINK.findall(self.html)
        found = []
        for link in links:
            m = re.fullmatch(r'<link rel="([a-z-]+)" type="([a-z/+]+)" href="data:([a-z/+]+);base64,([A-Za-z0-9+/=]+)">', link)
            self.assertIsNotNone(m, link)
            self.assertEqual(m.group(2), m.group(3))
            found.append((m.group(1), m.group(2), base64.b64decode(m.group(4))))
        self.assertEqual(found, [("icon", "image/svg+xml", (ASSETS / "clark-icon.svg").read_bytes()),
                                 ("icon", "image/png", (ASSETS / "clark-icon-32.png").read_bytes()),
                                 ("apple-touch-icon", "image/png", (ASSETS / "clark-icon-180.png").read_bytes())])
        self.assertLess(self.html.index("<link"), self.html.index("<style"), "the icons are in the head, before the styles")

    def test_the_three_links_are_the_pinned_pictures_exactly(self):
        # changing an icon is a deliberate edit of page.ICON_LINKS (the publish scan lets only these through)
        pictures = [base64.b64decode(re.search(r"base64,([A-Za-z0-9+/=]+)", link).group(1)) for link in LINK.findall(self.html)]
        self.assertEqual(len(pictures), 3)
        self.assertEqual(len(page.ICON_LINKS), 3)
        links = LINK.findall(self.html)
        rebuilt = [page.icon_link(rel, mime, base64.b64encode((ASSETS / name).read_bytes()).decode("ascii")) for rel, mime, name in build_page.ICONS]
        self.assertEqual(links, rebuilt, "the three tags are exactly what page.icon_link() writes, which is what the scan rebuilds")
        genuine = {}
        for link in LINK.findall(self.html):
            m = re.fullmatch(r'<link rel="([a-z-]+)" type="([a-z/+]+)" href="data:([a-z/+]+);base64,([A-Za-z0-9+/=]+)">', link)
            genuine[hashlib.sha256(base64.b64decode(m.group(4))).hexdigest()] = (m.group(1), m.group(2))
        self.assertEqual(genuine, page.ICON_LINKS, "the table has each picture's rel and mime exactly as the page's link")
        self.assertEqual({hashlib.sha256((ASSETS / name).read_bytes()).hexdigest(): (rel, mime) for rel, mime, name in build_page.ICONS},
                         page.ICON_LINKS)

    def test_nothing_is_addressed_outside_the_file(self):
        self.assertNotRegex(self.html, r"""(?i)\b(src|href)\s*=\s*(?!["']?data:)""")
        self.assertNotRegex(self.html, r"""(?i)url\(\s*(?!["']?data:)""")

    def test_the_top_bar_icon_is_shown_unless_a_local_brand_layer_hides_it(self):
        self.assertIn("--logo-icon: inline-block", self.html)
        self.assertRegex(self.html, r"\.logo-icon \{[^}]*display: var\(--logo-icon\)")
        self.assertIn('class:"logo-icon"', self.html.replace("class: ", "class:"), "the top bar draws the icon")
        with tempfile.TemporaryDirectory() as empty, tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "tokens.css").write_text(":root { --brand-navy: #123456; }", encoding="utf-8")
            block = page.page_html(tmp)
            block = block[block.index('id="brand-local"'):]
            self.assertNotIn("--logo-icon: none", page.page_html(empty))
        self.assertLess(block.index("--logo-icon: none"), block.index("--brand-navy: #123456"), "the brand's own tokens come last")


if __name__ == "__main__":
    unittest.main()
