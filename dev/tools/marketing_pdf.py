"""Render clark's two marketing documents from their HTML with headless Chrome (#706, #707). Re-runnable.

    python3 dev/tools/marketing_pdf.py            makes all three files below
    python3 dev/tools/marketing_pdf.py overview   only the overview
    python3 dev/tools/marketing_pdf.py start      only the getting-started PDF

Reads docs/marketing/clark-overview.html and docs/marketing/clark-getting-started.html and writes, beside them:
  clark-overview.pdf          one A4 page
  clark-overview.png          the same page at 2x (a 1240 x 1754 window at device scale 2, so 2480 x 3508 pixels)
  clark-getting-started.pdf   A4, with page numbers from the page's own CSS

Chrome is found the way the other tools find it (run_support.chrome_path: CLARK_CHROME, the PATH, then the Mac app). Each
run uses a fresh temporary profile folder, which is removed again, and Chrome is started in its own process group, so
whatever happens it is stopped and nothing is left running. The fonts are the computer's own: the pages fetch nothing.
This is a build step, not a test: tests/test_marketing_materials.py only checks the files that are committed.
"""
import os
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import run_support                      # noqa: E402
from help_pictures import optimise_png  # noqa: E402

OUT = HERE.parent.parent / "docs" / "marketing"
WINDOW = (1240, 1754)
SCALE = 2
LIMIT_SECONDS = 90


class Refused(Exception):
    """A plain one-line reason nothing was made."""


def run_chrome(args):
    """One headless Chrome run with a temporary profile; always stopped and cleaned up."""
    path = run_support.chrome_path()
    if not path:
        raise Refused("Chrome was not found. Install Google Chrome, or set CLARK_CHROME to its file.")
    profile = tempfile.mkdtemp(prefix="clark-marketing-")
    # the shared builder puts in the keychain flags; this run prints or photographs a page, so its DevTools pipe is not wanted
    cmd = run_support.chrome_command(path, profile, "--hide-scrollbars")[:-2]      # the last two are the pipe flag and the blank page
    cmd += args
    proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            start_new_session=True)
    try:
        proc.wait(timeout=LIMIT_SECONDS)
    except subprocess.TimeoutExpired:
        raise Refused("Chrome took more than %d seconds and was stopped." % LIMIT_SECONDS)
    finally:
        try:
            os.killpg(proc.pid, signal.SIGTERM)       # the helpers Chrome started go with it
        except (ProcessLookupError, PermissionError):
            pass
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
        shutil.rmtree(profile, ignore_errors=True)


def to_pdf(html, pdf):
    if pdf.exists():
        pdf.unlink()
    run_chrome(["--no-pdf-header-footer", "--print-to-pdf=" + str(pdf), html.as_uri()])
    if not pdf.exists() or pdf.stat().st_size < 1000:
        raise Refused("Chrome made no PDF from %s." % html.name)


def to_png(html, png):
    if png.exists():
        png.unlink()
    run_chrome(["--window-size=%d,%d" % WINDOW, "--force-device-scale-factor=%d" % SCALE,
                "--screenshot=" + str(png), html.as_uri()])
    if not png.exists():
        raise Refused("Chrome made no picture from %s." % html.name)
    data = png.read_bytes()
    width, height = struct.unpack(">II", data[16:24])
    if (width, height) != (WINDOW[0] * SCALE, WINDOW[1] * SCALE):
        raise Refused("The picture is %d x %d, not %d x %d." % (width, height, WINDOW[0] * SCALE, WINDOW[1] * SCALE))
    png.write_bytes(optimise_png(data))


def main(argv):
    which = argv[1] if len(argv) > 1 else "all"
    if which not in ("all", "overview", "start"):
        print(__doc__.split("\n\n")[0], file=sys.stderr)
        return 2
    try:
        if which in ("all", "overview"):
            to_pdf(OUT / "clark-overview.html", OUT / "clark-overview.pdf")
            to_png(OUT / "clark-overview.html", OUT / "clark-overview.png")
        if which in ("all", "start"):
            to_pdf(OUT / "clark-getting-started.html", OUT / "clark-getting-started.pdf")
    except Refused as why:
        print(why, file=sys.stderr)
        return 1
    for name in ("clark-overview.pdf", "clark-overview.png", "clark-getting-started.pdf"):
        if (OUT / name).exists():
            print("%s  %d bytes" % (name, (OUT / name).stat().st_size))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
