"""The files that make clark a Chrome app (#71), as pure functions the server serves (the routes are in server.py: see
docs/handoff/design-71-launcher.md).

A browser fetches these without clark's token (it sends no custom header for a manifest, a worker script or an icon), so each
is fixed bytes with no data in them: `open_files()` is the whole list of what the server may answer without the token.

- manifest(): the web app manifest: name clark, standalone, a theme colour, and the three icons from #73 (192, 512 and maskable)
- service_worker(): src/clark/app/sw.js, which shows the offline page when clark isn't running
- offline_page(): src/clark/app/offline.html with the launcher's name and the start command filled in
- data_mark(): the short mark of a data folder, so the launcher can tell clark's own data folder from another's
- health_answer(): what /health says: only {"ok": true}, and with the mark asked for, whether the data folder is the same

The service worker script and the manifest are copied from creaite v2.6.9 (templates/app/sw.js, app_manifest in live_server.py,
BL-86), with the names and colours changed. Standard library only, Python 3.9.
"""
import hashlib
import html
import json
import os
import re
from pathlib import Path

from clark import look

HERE = Path(__file__).resolve().parent
APP = HERE / "app"
ICONS_FROM = HERE / "page" / "assets"          # the icons are #73's files, served from where they are: one copy
NAME = "clark"
THEME = "#062F3A"                              # --brand-navy: the top bar, which the title bar of the app window takes on (the page changes it with Light and Dark)
BACKGROUND = "#F3F6FC"                         # --grey-50: the page's background, shown while the app window opens
START_URL = "/"
MARK_HEADER = "X-Clark-Data"                   # the header the launcher asks /health with; a web page can't send it (a preflight is refused)
OFFLINE_ROUTE = "/offline"
# (route, file in ICONS_FROM, pixels, purpose)
ICONS = (("/app/icon-192.png", "clark-icon-192.png", 192, "any"),
         ("/app/icon-512.png", "clark-icon-512.png", 512, "any"),
         ("/app/icon-maskable-512.png", "clark-icon-maskable-512.png", 512, "maskable"))
SW_CSP = "default-src 'none'; connect-src 'self'"     # the worker script may fetch from this address only, and load nothing else


def icon_bytes(name):
    return (ICONS_FROM / name).read_bytes()


def icon_stamp():
    """Eight hex characters from the three icons' bytes: part of each icon's address in the manifest, so a new icon makes the
    browser fetch it again. (creaite launch.icon_stamp)"""
    h = hashlib.sha256()
    for _, name, _, _ in ICONS:
        h.update(icon_bytes(name))
    return h.hexdigest()[:8]


def manifest(stamp=None):
    """The web app manifest as a dict. The id and scope are "/" (the whole of clark's address), the window is standalone."""
    v = icon_stamp() if stamp is None else stamp
    return {"name": NAME, "short_name": NAME, "description": "Project reports, kept on this computer.", "lang": "en-GB",
            "id": START_URL, "start_url": START_URL, "scope": "/", "display": "standalone",
            "background_color": BACKGROUND, "theme_color": THEME,
            "icons": [{"src": f"{route}?v={v}", "sizes": f"{px}x{px}", "type": "image/png", "purpose": purpose}
                      for route, _, px, purpose in ICONS]}


def manifest_json(stamp=None):
    """The manifest as the bytes the server sends (application/manifest+json)."""
    return json.dumps(manifest(stamp), indent=2, sort_keys=False).encode("utf-8")


def service_worker():
    """The service worker's script, as bytes."""
    return (APP / "sw.js").read_bytes()


TOKENS_CSS = Path(__file__).resolve().parent / "brand" / "tokens.css"
# placeholder in offline.html -> (mode, token). The button keeps the light brand blue with white text in both modes: the dark
# brand blue (the dark --brand-blue token) is for lines and icons, not for a fill under text; a test checks the button text
# against the fill in both modes.
OFFLINE_COLOURS = {"@L_BG@": ("light", "--grey-50"), "@L_SURFACE@": ("light", "--surface"), "@L_INK@": ("light", "--brand-ink"),
                   "@L_MUTED@": ("light", "--grey-700"), "@L_LINE@": ("light", "--grey-300"),
                   "@D_BG@": ("dark", "--grey-50"), "@D_SURFACE@": ("dark", "--surface"), "@D_INK@": ("dark", "--brand-ink"),
                   "@D_MUTED@": ("dark", "--grey-700"), "@D_LINE@": ("dark", "--grey-300"),
                   "@ACCENT@": ("light", "--brand-blue"), "@ACCENT_INK@": ("light", "--text-on-brand")}


def token_value(css, mode, name):
    """A token's colour from tokens.css: the first :root block for light, the data-theme=dark block (over the first) for dark."""
    blocks = [re.search(r":root\s*\{(.*?)\n\}", css, re.S).group(1)]
    if mode == "dark":
        blocks.insert(0, re.search(r":root\[data-theme=dark\]\s*\{(.*?)\n\}", css, re.S).group(1))
    for block in blocks:
        m = re.search(re.escape(name) + r":\s*(#[0-9A-Fa-f]{3,6})\s*;", block)
        if m:
            return m.group(1).upper()
    raise KeyError(name)


def offline_page(launcher="clark.command"):
    """The page shown when clark isn't running, as bytes, with the launcher's file name and the command to type in Terminal
    (`./` and the name). The name comes from platform.launcher_name(); nothing a person typed is ever put in."""
    page = (APP / "offline.html").read_text(encoding="utf-8")
    css = TOKENS_CSS.read_text(encoding="utf-8")
    for holder, (mode, name) in OFFLINE_COLOURS.items():
        page = page.replace(holder, token_value(css, mode, name))
    page = page.replace("@FONT@", look.family_list("--font", css))      # the page's own list: it loads no font, so the first that is installed shows
    page = page.replace("@LAUNCHER@", html.escape(launcher)).replace("@COMMAND@", html.escape("./" + launcher))
    return page.encode("utf-8")


def open_files(launcher="clark.command"):
    """{route: (bytes, content type, extra headers)}: every file the server may answer without the token, read once. The
    server sends exactly these for GET (and only GET), after its Host check, and nothing else without the token. The icons
    are matched by their path without the ?v= part."""
    files = {"/manifest.webmanifest": (manifest_json(), "application/manifest+json", {}),
             "/sw.js": (service_worker(), "text/javascript", {"Content-Security-Policy": SW_CSP}),
             OFFLINE_ROUTE: (offline_page(launcher), "text/html", {})}
    for route, name, _, _ in ICONS:
        files[route] = (icon_bytes(name), "image/png", {})
    return files


def data_mark(folder):
    """A short mark of a data folder: the first 16 hex characters of the SHA-256 of its resolved path (as creaite's vault_mark).
    The server and the launcher both work it out, so /health can say "this is your data folder" without naming it."""
    return hashlib.sha256(os.path.normcase(str(Path(folder).expanduser().resolve())).encode("utf-8")).hexdigest()[:16]


def health_answer(asked, mark):
    """What /health says. Only {"ok": true} for anyone; the launcher, which sends its mark in X-Clark-Data, is also told
    whether this server's data folder is the same one."""
    out = {"ok": True}
    if asked:
        out["this_data"] = asked == mark
    return out
