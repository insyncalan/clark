"""No client picture is committed (a client's logo, name and picture never enter clark).

Run: python3 dev/run_tests.py test_no_client_image
The only pictures under src/, vendor/ and system/templates/ are clark's own icon set (pinned below by SHA-256; the three the page links are also
pinned by tests/test_icons.py). Any other image file fails, and so does any `data:image` picture inside a text file (the built page holds clark's
own icon as data, and nothing else) unless its bytes are one of the pinned icons. The check itself is tried on made-up files.
"""
import base64
import hashlib
import re
import subprocess
import unittest
from urllib.parse import unquote_to_bytes

from _paths import ROOT

IMAGE_FILE = re.compile(r"\.(png|jpe?g|gif|svg|webp|ico|icns|bmp|tiff?|avif|heic)$", re.I)
SCOPE = ("src/", "vendor/", "system/templates/")
ICON_DIR = "src/clark/page/assets/"
PINNED = {                                    # clark's own icon set: name to SHA-256
    "clark-icon-16.png": "6f9453edf03625138adc7bca6d811d10dddc24f50410b7a13c3e6671df7ad834",
    "clark-icon-180.png": "ca3e8e79d1761c245d596d22287ccef7030933f7d358daced0cfad9cbdb22a7e",
    "clark-icon-192.png": "6bde4c54e680a6fec6f1b522400d5448c00a172b2c4f2725f89aaa3cd19df386",
    "clark-icon-32.png": "5b46bd7786aab805faa93c1dcc250c1d284cb5c9e43adf96f656bc44e1e714df",
    "clark-icon-512.png": "f949c0b8ac90573926a58a15359cd6ef0650e9ebb6f507729a52744f802b48cf",
    "clark-icon-maskable-512.png": "e79939ac5b5cd2a0e359ebecd29fd6f110254b96445151b17ca4ce8b88013f61",
    "clark-icon.svg": "11d8526dbc1e91b74e541db82a2cb8ed04784ad702c6279410ad8f1858d8a384",
}
SHA = hashlib.sha256
DATA_B64 = re.compile(r"data:image/[a-z0-9.+-]+;base64,([A-Za-z0-9+/=]{16,})", re.I)
DATA_RAW = re.compile(r"""data:image/[a-z0-9.+-]+,([^"')\s]{16,})""", re.I)
TEXT = re.compile(r"\.(css|js|jsx|mjs|html|htm|py|json|md|txt|xml)$", re.I)


def problems(files, pinned=PINNED, scope=SCOPE, icon_dir=ICON_DIR):
    """[(path, what)] for {path: bytes}: an image file that is not a pinned icon, or a data:image picture that is not one."""
    ok = set(pinned.values())
    out = []
    for path, data in sorted(files.items()):
        if not path.startswith(scope):
            continue
        if IMAGE_FILE.search(path):
            if not (path.startswith(icon_dir) and path[len(icon_dir):] in pinned and SHA(data).hexdigest() == pinned[path[len(icon_dir):]]):
                out.append((path, "an image that is not clark's own icon"))
        elif TEXT.search(path):
            text = data.decode("utf-8", "replace")
            for m in DATA_B64.finditer(text):
                try:
                    if SHA(base64.b64decode(m.group(1))).hexdigest() not in ok:
                        out.append((path, "a data:image picture that is not clark's own icon"))
                except ValueError:
                    out.append((path, "a data:image picture that can't be read"))
            for m in DATA_RAW.finditer(text):
                if SHA(unquote_to_bytes(m.group(1))).hexdigest() not in ok:
                    out.append((path, "a data:image picture that is not clark's own icon"))
    return out


def tracked_files():
    names = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"], capture_output=True, check=True).stdout.decode("utf-8").split("\0")
    return {n: (ROOT / n).read_bytes() for n in names if n and n.startswith(SCOPE) and (ROOT / n).is_file()}


class NoClientImage(unittest.TestCase):
    def test_no_client_image_is_committed(self):
        found = problems(tracked_files())
        self.assertEqual(found, [], "only clark's own icon may be a picture here; a client's logo or picture stays in the folder git ignores")

    def test_the_icon_set_on_disk_is_the_pinned_one(self):
        for name, sha in PINNED.items():
            self.assertEqual(SHA((ROOT / ICON_DIR / name).read_bytes()).hexdigest(), sha, name)
        on_disk = {p.name for p in (ROOT / ICON_DIR).iterdir() if IMAGE_FILE.search(p.name)}
        self.assertEqual(on_disk, set(PINNED))

    def test_the_check_itself_catches_a_planted_picture(self):
        icon = b"made-up icon bytes"
        pinned = {"clark-icon.svg": SHA(icon).hexdigest()}
        scope, icons = ("src/", "vendor/"), "src/icons/"
        planted = b"made-up client logo bytes"
        b64 = base64.b64encode(planted).decode()
        files = {"src/icons/clark-icon.svg": icon,                                  # fine: the pinned icon
                 "src/page.html": f'<link href="data:image/svg+xml;base64,{base64.b64encode(icon).decode()}">'.encode(),     # fine: the same icon as data
                 "src/icons/logo.png": planted,                                       # an image that is not an icon
                 "src/icons/clark-icon-x.png": icon,                                  # not in the pinned names
                 "vendor/a.js": f'x = "data:image/png;base64,{b64}"'.encode(),         # a picture as data
                 "src/b.css": b'.a { background: url("data:image/svg+xml,%3Csvg%20xmlns%3D%22http%22%3E%3C%2Fsvg%3E"); }',
                 "docs/shot.png": planted}                                            # outside the scope: not this test's job
        found = problems(files, pinned, scope, icons)
        self.assertEqual(sorted(p for p, _ in found), ["src/b.css", "src/icons/clark-icon-x.png", "src/icons/logo.png", "vendor/a.js"])
        self.assertEqual(problems({"src/icons/clark-icon.svg": icon}, pinned, scope, icons), [])
        self.assertEqual(problems({"src/icons/clark-icon.svg": icon + b"x"}, pinned, scope, icons), [("src/icons/clark-icon.svg", "an image that is not clark's own icon")])


if __name__ == "__main__":
    unittest.main()
