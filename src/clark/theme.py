"""Row 1260, step 4a: reading a Theme (src/clark/themes/<name>/tokens.css then rules.css) as the text the page layers.

A Theme is chosen per install; a project's Brand layers over it (committed tokens, then Theme, then Brand). This file only
answers "what is the CSS of the Theme called X": which install setting names X is a later step, so the name is passed in.
Nothing here joins a name onto a path: a name is looked up in the folders that exist under themes/, so "../x" or an absolute
path is simply not a Theme and the answer is None (today's look). Comments are stripped and the text made safe for a <style>
element, as for a Brand (page.strip_css_comments, page.escape_style). Standard library only.
"""
from pathlib import Path

from clark import page

THEMES = Path(__file__).resolve().parent / "themes"
FILES = ("tokens.css", "rules.css")         # in this order: the values first, then the rules that use them
LIMIT = 64 * 1024                          # a Theme file larger than this is not read


def installed():
    """The names of the Themes that ship, sorted: every folder under themes/ that holds both files."""
    if not THEMES.is_dir():
        return []
    return sorted(p.name for p in THEMES.iterdir() if p.is_dir() and all((p / f).is_file() for f in FILES))


def css(name):
    """The comment-free, style-safe text of the Theme `name` (tokens.css, then rules.css), or None for no name, an unknown
    name, or a file that cannot be read or is too large (the page then keeps today's look)."""
    if not isinstance(name, str) or name not in installed():
        return None
    parts = []
    for f in FILES:
        path = THEMES / name / f
        try:
            if path.is_symlink() or path.stat().st_size > LIMIT:
                return None
            parts.append(page.strip_css_comments(path.read_text(encoding="utf-8")).strip())
        except (OSError, UnicodeDecodeError):
            return None
    return page.escape_style("\n".join(parts))
