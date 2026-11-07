"""#943: the file address that opens a PDF at a page (file:///...#page=N), built from a path in a saved folder. Unguarded; pure
apart from looking at the disk for a link. It starts nothing (platform.py does) and reads no file. A path is refused (PdfLinkRefused)
unless it is a .pdf, is not a link (nor below one), and is inside one of the saved folders. The name is percent-encoded, so a
space, a "#", a "%" or a "?" in it can never end the address early or start the fragment. The page is a whole number from 1 to
MAX_PAGE, or None for the file with no page."""
import os
from pathlib import Path
from urllib.parse import quote

MAX_PAGE = 100000


class PdfLinkRefused(ValueError):
    """A path or page that cannot be turned into a PDF address."""


def _page(page):
    if page is None:
        return None
    if isinstance(page, bool) or not isinstance(page, int) or not 1 <= page <= MAX_PAGE:
        raise PdfLinkRefused("The page must be a whole number from 1 to %d." % MAX_PAGE)
    return page


def pdf_url(path, page, folders):
    """The address for `path` at `page` (int or None), if `path` is a .pdf inside one of `folders` (paths) and neither it nor any
    folder between its saved folder and it is a link. Raises PdfLinkRefused."""
    page = _page(page)
    if not isinstance(path, (str, os.PathLike)) or not str(path) or "\x00" in str(path):
        raise PdfLinkRefused("That is not a file path.")
    p = Path(os.path.abspath(path))
    if p.suffix.lower() != ".pdf":
        raise PdfLinkRefused("Only a PDF can be opened at a page.")
    for folder in folders or ():
        try:
            root = Path(os.path.abspath(folder))
            rel = p.relative_to(root)
        except (ValueError, TypeError):
            continue
        walk = root
        for part in rel.parts:
            walk = walk / part
            if walk.is_symlink():
                raise PdfLinkRefused("That file is reached through a shortcut, so it is not opened.")
        if ".." in rel.parts:
            break
        url = "file://" + quote(p.as_posix(), safe="/")
        return url if page is None else f"{url}#page={page}"
    raise PdfLinkRefused("That file is not in a folder saved for asking.")
