"""Argos step 1: save the Classic screens of the tickets in Building as PNGs, at widths 1400 and 900.

Run from the repository root:  python3 dev/tools/argos_shots.py [--out DIR] [--width 1400|900 ...]
--out is the output folder (default ./screenshots). --width may repeat; only 1400 or 900 are allowed (anything else exits 2); none given means both.
It starts the real page from the demo database on 127.0.0.1 and a headless Chrome, the way tests/test_theme_classic_1317.py does.
No network, no upload, no token. The upload step is not here. At most MAX_SHOTS files are saved per run; the rest are counted and printed.
File names: <ticket>-<screen>-<width>.png
"""
import argparse
import base64
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
THEME = "prototype-2.0"            # the Classic theme
WIDTHS = (1400, 900)
HEIGHT = 900
MAX_SHOTS = 40
# (ticket, screen, how to reach it: the address fragment the page opens at)
SCREENS = [
    ("1299", "projects-overview", "#settings"),
    ("1299", "project-tab", "#settings&p=TUL"),
    ("1299", "project-profile", "#settings&p=TUL&s=profile"),
    ("1294", "ask-settings", "#settings&p=TUL&s=claude"),
    ("1298", "help", "#help"),
]


def candidates(screens=SCREENS, widths=WIDTHS):
    """Every (file name, fragment, width) the table asks for, in table order."""
    return [(f"{t}-{s}-{w}.png", how, w) for t, s, how in screens for w in widths]


def save_all(out, grab, screens=SCREENS, widths=WIDTHS, limit=MAX_SHOTS):
    """Saves at most `limit` PNGs into `out` using grab(fragment, width) -> PNG bytes. Returns (saved names, dropped count)."""
    todo = candidates(screens, widths)
    keep, dropped = todo[:limit], len(todo) - min(len(todo), limit)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for name, how, width in keep:
        (out / name).write_bytes(grab(how, width))
    return [k[0] for k in keep], dropped


def parse(argv):
    ap = argparse.ArgumentParser(prog="argos_shots.py", description="Save the Classic screens as PNGs.")
    ap.add_argument("--out", default="screenshots", help="output folder (default screenshots)")
    ap.add_argument("--width", type=int, action="append", choices=WIDTHS, metavar="N",
                    help="1400 or 900; may repeat; default both")
    a = ap.parse_args(argv[1:])
    return Path(a.out), tuple(dict.fromkeys(a.width)) if a.width else WIDTHS


def main(argv):
    out, widths = parse(argv)
    sys.path[:0] = [str(ROOT / "tests"), str(ROOT / "src"), str(ROOT / "dev" / "tools")]
    from _editor_checks import for_url
    from clark import page
    from test_server import Running, chrome, wait
    from test_work_items import FIXED_DATE, load_demo, page_target
    store, folder, _ = load_demo()
    try:
        names = {p["code"]: p["name"] for p in store.read("projects")}
        server = Running(data_for=lambda code, **kw: store.data_for(code) if code in names else None,
                         projects=lambda archived=False: [{"code": c, "name": n} for c, n in sorted(names.items())],
                         page_html=lambda: page.page_html(tempfile.mkdtemp(), theme=THEME))
        try:
            def grab(how, width):
                with chrome() as cdp:
                    sid = page_target(cdp)
                    cdp.call("Page.enable", {}, sid)
                    cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": HEIGHT, "deviceScaleFactor": 1, "mobile": False}, sid)
                    cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": "light"}]}, sid)
                    cdp.call("Page.navigate", {"url": for_url(f"http://127.0.0.1:{server.port}/{how}")}, sid)
                    wait(lambda: bool(cdp.js("document.readyState === 'complete' && !!document.body.children.length", sid)), 30)
                    time.sleep(0.5)
                    return base64.b64decode(cdp.call("Page.captureScreenshot", {"format": "png"}, sid)["data"])
            saved, dropped = save_all(out, grab, widths=widths)
        finally:
            server.close()
    finally:
        store.close()
    print(f"saved {len(saved)} PNGs in {out}; dropped {dropped}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
