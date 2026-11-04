"""The pictures for Help (#642 step 5): take each named shot in dev/tools/help_shots.json from clark running on the fictional demo
data, and write one small PNG per shot into src/clark/page/help-pictures/.

    python3 dev/tools/help_pictures.py            # take every shot and write the pictures
    python3 dev/tools/help_pictures.py --check    # open every shot and check each selector matches; write nothing
    python3 dev/tools/help_pictures.py --only templates-add-box --only publish-menu     # some shots only
    python3 dev/tools/help_pictures.py --data FOLDER    # a folder that already holds the demo data (dev/demo_data.py); any other is refused

The data: only the fictional demo data (dev/demo_data.py), built at a fixed date so the same shots come out each time. With no
--data, clark is started with its own --demo (a temporary folder, removed after). With --data, the folder's clark.db must be a
demo database made by dev/demo_data.py; anything else is refused before clark is started, because a picture must never show a
real client, a name or a brand (docs/RULES.md).

The look: headless Chrome, a 1400 x 1000 window, the light theme only (the window is told it prefers light, and a shot fails if
the page is not light), device scale factor 1, animations switched off. The fonts are the ones inside the page (vendor/fonts),
not the computer's, so the same shot looks the same on every machine. Each shot is cropped to its control with a small margin;
an optional ring or number is drawn on a control in the brand blue (the token --brand-blue), only in the picture, never in the page.

The shots are in help_shots.json (one place naming which screen each picture shows). A shot is:
    id        the file name without .png (letters, digits and hyphens)
    guide     which guide it is for (a word, to group them)
    screen    the address to open, after the host: "#dashboard&p=TUL"
    steps     what to do first, in order; each is one of
                {"mode": "edit"} or {"mode": "view"}
                {"click": CSS}  {"hover": CSS}  {"wait": CSS}  {"away": true} (move the pointer off every control)
    crop      a CSS selector, or a list of them (the picture holds all of them), to crop to
    margin    pixels around the crop (default 12)
    marks     optional list of {"ring": CSS, "number": N}: a ring on that control, and a number beside it if given
"""
import argparse
import importlib
import json
import os
import re
import socket
import struct
import subprocess
import sys
import time
import zlib
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent.parent
for _folder in (TOOLS, ROOT / "dev", ROOT / "vendor", ROOT / "src"):
    if str(_folder) not in sys.path:
        sys.path.insert(0, str(_folder))

SHOTS = TOOLS / "help_shots.json"
OUT = ROOT / "src" / "clark" / "page" / "help-pictures"
WIDTH, HEIGHT, SCALE = 1400, 1000, 1          # CSS pixels and device scale factor 1: the same pixels on every screen
FIXED_NOW = "2026-10-28 09:00"                # the demo data's "now"; every date in it is an offset from this
DEFAULT_MARGIN = 12
ID = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
STEP_KEYS = ("mode", "click", "hover", "wait", "away")
SHOT_KEYS = {"id", "guide", "screen", "steps", "crop", "margin", "marks"}


class Refused(Exception):
    """Something to say in one plain sentence, then stop."""


# ---- the shots list -----------------------------------------------------------------------------------------------------------

def load_shots(path=SHOTS):
    """The shots in `path`, checked for shape. Raises Refused with a plain sentence."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Refused(f"The list of shots {path} could not be read: {e}") from e
    shots = data.get("shots") if isinstance(data, dict) else None
    if not isinstance(shots, list) or not shots:
        raise Refused(f"{path} must hold a list called shots, with at least one shot in it.")
    seen = set()
    for s in shots:
        name = s.get("id") if isinstance(s, dict) else None
        if not isinstance(name, str) or not ID.match(name):
            raise Refused(f"A shot in {path} has no usable id (lower-case words joined by hyphens): {s!r}")
        if name in seen:
            raise Refused(f"The shot id {name} is listed twice in {path}.")
        seen.add(name)
        extra = set(s) - SHOT_KEYS
        if extra:
            raise Refused(f"Shot {name} has a key this script does not know: {', '.join(sorted(extra))}.")
        if not isinstance(s.get("screen"), str) or not s["screen"].startswith("#"):
            raise Refused(f"Shot {name} needs a screen that starts with #, such as #dashboard&p=TUL.")
        crops = crop_list(s)
        if not crops or not all(isinstance(c, str) and c for c in crops):
            raise Refused(f"Shot {name} needs a crop: a CSS selector, or a list of them.")
        for step in s.get("steps", []):
            keys = [k for k in step if k in STEP_KEYS] if isinstance(step, dict) else []
            if len(keys) != 1 or len(step) != 1:
                raise Refused(f"Shot {name} has a step that is not exactly one of {', '.join(STEP_KEYS)}: {step!r}")
            if keys[0] == "mode" and step["mode"] not in ("edit", "view"):
                raise Refused(f"Shot {name} has a mode that is not edit or view: {step['mode']!r}")
        for m in s.get("marks", []):
            if not isinstance(m, dict) or not isinstance(m.get("ring"), str) or set(m) - {"ring", "number"}:
                raise Refused(f"Shot {name} has a mark that is not {{\"ring\": selector, \"number\": n}}: {m!r}")
    return shots


def crop_list(shot):
    c = shot.get("crop")
    return [c] if isinstance(c, str) else c if isinstance(c, list) else []


def shot_ids(path=SHOTS):
    return [s["id"] for s in load_shots(path)]


# ---- only the demo data -------------------------------------------------------------------------------------------------------

def check_demo_folder(folder):
    """Raise Refused unless `folder` holds clark.db and it is a demo database made by dev/demo_data.py. Nothing is opened for
    writing and clark is not started."""
    import demo_data
    folder = Path(folder).expanduser()
    db = folder / "clark.db"
    if not db.is_file() or not demo_data.is_demo_database(db):
        raise Refused(f"The folder {folder} does not hold the fictional demo data, so no pictures were taken: a picture must never "
                      "show real work, a client or a brand. Leave out --data to use the demo data, or build a folder with "
                      "python3 dev/demo_data.py --out FOLDER/clark.db.")
    return folder


# ---- making the pictures small (standard library only) ------------------------------------------------------------------------

def optimise_png(data):
    """The same picture in fewer bytes: only the chunks a picture needs are kept (no text, time or colour-profile chunks) and the
    pixel data is packed again at the strongest level, which is kept only if it is smaller. The pixels are not changed. Anything
    that is not a plain PNG comes back as it was."""
    sig = b"\x89PNG\r\n\x1a\n"
    if not data.startswith(sig):
        return data
    pos, keep, idat = len(sig), [], []
    while pos + 8 <= len(data):
        size, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + size]
        pos += 12 + size
        if kind == b"IDAT":
            idat.append(body)
        elif kind in (b"IHDR", b"PLTE", b"tRNS"):
            keep.append((kind, body))
        elif kind == b"IEND":
            break
    if not idat or not keep or keep[0][0] != b"IHDR":
        return data
    try:
        raw = zlib.decompress(b"".join(idat))
    except zlib.error:
        return data
    best = min((zlib.compress(raw, 9), *(_deflate(raw, strategy) for strategy in (zlib.Z_FILTERED, zlib.Z_DEFAULT_STRATEGY))), key=len)
    out = [sig]
    for kind, body in keep + [(b"IDAT", best), (b"IEND", b"")]:
        out.append(struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF))
    packed = b"".join(out)
    return packed if len(packed) < len(data) else data


def _deflate(raw, strategy):
    c = zlib.compressobj(9, zlib.DEFLATED, 15, 9, strategy)
    return c.compress(raw) + c.flush()


# ---- clark, started on the demo data ------------------------------------------------------------------------------------------

def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Clark:
    """`python3 -m clark` as a child process on the demo data: --demo (its own temporary folder), or --data with a folder that
    check_demo_folder has passed. The address it prints is read from its output."""

    def __init__(self, data=None):
        self.data = check_demo_folder(data) if data else None
        self.port = free_port()
        env = dict(os.environ, CLARK_NOW=FIXED_NOW, PYTHONPATH=os.pathsep.join([str(ROOT / "src"), str(ROOT / "vendor")]))
        args = ["--data", str(self.data)] if self.data else ["--demo"]
        self.proc = subprocess.Popen([sys.executable, "-m", "clark", *args, "--port", str(self.port)], cwd=str(ROOT), env=env,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.wait_listening()

    def wait_listening(self):
        end = time.monotonic() + 60
        while time.monotonic() < end:
            line = self.proc.stdout.readline()
            if f"127.0.0.1:{self.port}" in line:
                return
            if not line and self.proc.poll() is not None:
                break
        self.stop()
        raise Refused("clark did not start on the demo data, so no pictures were taken.")

    def stop(self):
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
        if self.proc.stdout:
            self.proc.stdout.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Take the pictures for Help from the fictional demo data.")
    parser.add_argument("--check", action="store_true", help="open every shot and check its selectors match; write nothing")
    parser.add_argument("--only", action="append", default=[], metavar="ID", help="take only this shot (may be repeated)")
    parser.add_argument("--data", metavar="FOLDER", help="a folder holding the demo data (clark.db made by dev/demo_data.py); any other is refused")
    parser.add_argument("--shots", default=str(SHOTS), help=argparse.SUPPRESS)
    parser.add_argument("--out", default=str(OUT), help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        shots = load_shots(args.shots)
        unknown = [i for i in args.only if i not in {s["id"] for s in shots}]
        if unknown:
            raise Refused(f"No shot is called {', '.join(unknown)} in the list of shots.")
        shots = [s for s in shots if not args.only or s["id"] in args.only]
        if args.data:
            check_demo_folder(args.data)                      # refused before anything starts
        clark = Clark(args.data)
        try:
            shoot = importlib.import_module("help_pictures_browser")        # by name: the quick tests never load the browser half
            with shoot.Browser() as b:
                out = Path(args.out)
                if not args.check:
                    out.mkdir(parents=True, exist_ok=True)
                total = 0
                for s in shots:
                    data = shoot.take(b, clark.port, s, write=not args.check)
                    if data is not None:
                        (out / f"{s['id']}.png").write_bytes(data)
                        total += len(data)
                        print(f"{s['id']}: {len(data) / 1024:.1f} KB")
                    else:
                        print(f"{s['id']}: ok")
        finally:
            clark.stop()
    except Refused as e:
        print(f"help_pictures: {e}", file=sys.stderr)
        return 1
    print(f"{len(shots)} shot{'s' if len(shots) != 1 else ''} {'checked' if args.check else f'written, {total / 1024:.0f} KB in all'}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
