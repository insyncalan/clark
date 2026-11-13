"""#891: read the text of one PDF for ask clark, in a SEPARATE process. Standard library only; the server process never imports pypdf.

The PDF is parsed by `pdf_reader_child.py` (python -I -S, the vendored pypdf) started through `platform.run_stoppable`: its own
process group and empty folder, a minimal environment, the bytes on standard input, at most MAX_OUT bytes of standard output,
a hard wall-clock limit (SECONDS), then the whole group is ended. The parent also refuses, before starting anything, a file over
MAX_BYTES. The child refuses more than MAX_PAGES pages and keeps at most MAX_PAGE_CHARS characters of a page. No OCR; no network;
no file is written. NOTHING raises into the caller: `read` always returns a `Result`.

`Result.status` is "ok" (pages hold (page number, text), numbers from 1) or "not_read" with a `reason` code, never shown as
words here: "too_big", "too_many_pages", "timeout", "crash", "corrupt", "unavailable" (no pypdf), or the two with their own
meaning, "scanned" (the PDF has no text to read: only pictures) and "encrypted". For those two `status` is the reason itself.
`NEW_WORDS` lists the sentences the screen would need (constants only; nothing here is shown)."""
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from clark import platform

SECONDS = 20.0                       # wall clock for one PDF
MAX_BYTES = 20 * 1024 * 1024         # a larger file is not read
MAX_PAGES = 200
MAX_PAGE_CHARS = 50_000
MAX_OUT = 2 * 1024 * 1024            # the parent's hard stop on the child's output
OUT_BUDGET = MAX_OUT * 3 // 4        # the child stops adding pages at this much JSON, so a big PDF returns its leading pages
VENDOR = Path(__file__).resolve().parents[2] / "vendor"
CHILD = Path(__file__).with_name("pdf_reader_child.py")
REASONS = ("too_big", "too_many_pages", "timeout", "crash", "corrupt", "unavailable", "scanned", "encrypted")

# Sentences the screen would need, to be approved (NEW-WORDS.md); not used by any screen yet.
NEW_WORDS = {
    "scanned": "{n} PDF {was} not read: it holds pictures of pages and no text.",
    "encrypted": "{n} PDF {was} not read: it is protected with a password.",
    "not_read": "{n} PDF {was} not read: it could not be read safely.",
    "sources_page": "{name}, page {page}",
}


@dataclass(frozen=True)
class Result:
    status: str                  # "ok" or "not_read" / "scanned" / "encrypted"
    reason: str = ""             # a code from REASONS when not ok
    pages: tuple = ()            # ((page number, text), ...)


def _no(reason):
    return Result(reason if reason in ("scanned", "encrypted") else "not_read", reason)


def _env():
    return {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"}


def read(raw, vendor=None, truncated=False):
    """The pages of the PDF `raw` (bytes); `truncated` says the file held more than was read. Never raises."""
    try:
        if truncated or not isinstance(raw, (bytes, bytearray)) or len(raw) > MAX_BYTES:
            return _no("too_big")
        args = [sys.executable, "-I", "-S", str(CHILD), str(vendor or VENDOR), str(MAX_PAGES), str(MAX_PAGE_CHARS), str(OUT_BUDGET)]
        status, out, _code = platform.run_stoppable(args, bytes(raw), _env(), SECONDS, MAX_OUT, prefix="clark-pdf-")
        if status == "slow":
            return _no("timeout")
        if status != "ok":
            return _no("crash")
        said = json.loads(out.decode("utf-8"))
        code = said["status"]
        if code == "ok":
            pages = tuple((int(n), str(t)) for n, t in said["pages"] if int(n) >= 1 and str(t).strip())
            return Result("ok", "", pages) if pages else _no("scanned")
        return _no(code if code in REASONS else "crash")
    except Exception:                                  # a faulty answer, a missing python: it is "not read", never an error
        return _no("crash")
