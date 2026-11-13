"""#891: the child that reads one PDF. Run ONLY by `pdf_reader` as `python -I -S pdf_reader_child.py <vendor> <max_pages> <max_chars> [<budget>]`
in its own process, folder and process group. Standard library plus the vendored pypdf; no network, no OCR, no writes.
The PDF bytes come on standard input; one line of JSON goes to standard output: {"status": ..., "pages": [[number, text], ...]}.
status is "ok", "encrypted" (nothing is tried, not even a blank password), "scanned" (no page has text), "too_many_pages",
"corrupt" or "unavailable" (pypdf cannot be imported). Anything else the parent counts as a crash. Only text is taken from a page:
no links, files, scripts, forms or pictures are touched."""
import json
import sys


def _limits():
    try:
        import resource
    except ImportError:
        return
    for name, value in (("RLIMIT_CPU", 15), ("RLIMIT_AS", 1024 * 1024 * 1024), ("RLIMIT_CORE", 0)):
        try:
            res = getattr(resource, name)
            resource.setrlimit(res, (value, value))
        except (AttributeError, ValueError, OSError):
            pass                                  # macOS refuses to lower RLIMIT_AS: the parent's time limit still holds


DEFAULT_BUDGET = 1_500_000          # bytes of JSON: pages after this are left out, so a big readable PDF is not lost to the parent's cut


def _say(status, pages=(), left=0):
    said = {"status": status, "pages": [list(p) for p in pages]}
    if left:
        said["left"] = left                       # pages after the budget cut, only when there were some
    sys.stdout.write(json.dumps(said))
    sys.stdout.flush()


def main(argv):
    vendor, max_pages, max_chars = argv[1], int(argv[2]), int(argv[3])
    budget = int(argv[4]) if len(argv) > 4 else DEFAULT_BUDGET
    _limits()
    data = sys.stdin.buffer.read()
    sys.path.insert(0, vendor)
    try:
        import io
        from pypdf import PdfReader
    except Exception:
        return _say("unavailable")
    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
        if reader.is_encrypted:
            return _say("encrypted")
        count = len(reader.pages)
        if count > max_pages:
            return _say("too_many_pages")
        pages, used, left = [], 0, 0
        for n in range(count):
            text = (reader.pages[n].extract_text() or "").strip()[:max_chars]
            if text:
                used += len(json.dumps([n + 1, text])) + 2          # ensure_ascii counted: a non-ASCII character is up to 12 bytes
                if pages and used > budget:
                    left = count - n                                # the leading pages are kept; the rest is left out, and counted
                    break
                pages.append((n + 1, text))
    except Exception:
        return _say("corrupt")
    return _say("ok" if pages else "scanned", pages, left)


if __name__ == "__main__":
    main(sys.argv)
