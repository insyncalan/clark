"""#891: the child that reads one PDF. Run ONLY by `pdf_reader` as `python -I -S pdf_reader_child.py <vendor> <max_pages> <max_chars>`
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


def _say(status, pages=()):
    sys.stdout.write(json.dumps({"status": status, "pages": [list(p) for p in pages]}))
    sys.stdout.flush()


def main(argv):
    vendor, max_pages, max_chars = argv[1], int(argv[2]), int(argv[3])
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
        pages = []
        for n in range(count):
            text = (reader.pages[n].extract_text() or "").strip()
            if text:
                pages.append((n + 1, text[:max_chars]))
    except Exception:
        return _say("corrupt")
    return _say("ok" if pages else "scanned", pages)


if __name__ == "__main__":
    main(sys.argv)
