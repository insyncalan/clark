# Bundled libraries

Everything clark needs at run time is here, so nothing is installed from the internet and clark runs on Python 3.9 or later with the standard library alone. Each library is copied unchanged from creaite v2.6.9 (`db5adb2`); the copies are recorded in the reuse record.

| Library | Licence | Folder | Used by |
|---------|---------|--------|---------|
| openpyxl 3.1.5, plus its dependency et_xmlfile 2.0.0 | MIT (et_xmlfile has parts under PSF-2.0) | `openpyxl/`, `et_xmlfile/`, licences in `licenses/` | Excel export and import (#37, #38) |
| Preact 10.29.8 with hooks and the JSX runtime, @preact/signals 2.11.2, signals-core 1.14.4 | MIT | `preact/` | the page (#35) |
| Readex Pro (Google Fonts v27, Latin, one variable woff2 for every weight), with its OFL licence | SIL Open Font License 1.1 | `fonts/readex-pro/` | the page's font, inlined by the build (#35); not from creaite |
| Tiptap 3.31.3 as one ES module, with every bundled package's licence | MIT | `tiptap/` | the one editor (#41) |

- `manifest.json` holds each Python library's version and licence and the SHA-256 of every file here outside `preact/`, `tiptap/` and `fonts/`. `tests/test_vendor_python.py` fails on a missing, changed or extra file.
- `preact/manifest.json` and `tiptap/manifest.json` do the same for the front-end libraries (`tests/test_vendor_preact.py`, `tests/test_vendor_tiptap.py`); `fonts/readex-pro/manifest.json` does the same for the font (`tests/test_font.py`).
- The esbuild bundler is not here: it is a development tool, fetched once per machine by `dev/tools/esbuild.py` into `dev/.cache/` (git ignores it) and checked against its pinned SHA-256.

Upgrade only deliberately: replace the folder, run `python3 dev/tools/vendor_manifest.py` (or `vendor_preact.py`, `tiptap.py vendor`), run the tests, and commit the library and its manifest together.
