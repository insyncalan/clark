"""Row 1260, step 4a: reading a Theme (src/clark/themes/<name>/tokens.css, rules.css, then rules-2.css) as the text the page layers.

A Theme is chosen per install; a project's Brand layers over it (committed tokens, then Theme, then Brand). This file only
answers "what is the CSS of the Theme called X": which install setting names X is a later step, so the name is passed in.
Nothing here joins a name onto a path: a name is looked up in the folders that exist under themes/, so "../x" or an absolute
path is simply not a Theme and the answer is None (today's look). Comments are stripped and the text made safe for a <style>
element, as for a Brand (page.strip_css_comments, page.escape_style). Standard library only.
"""
from pathlib import Path

from clark import page

THEMES = Path(__file__).resolve().parent / "themes"
FILES = ("tokens.css", "rules.css", "rules-2.css")   # in this order: the values first, then the rules that use them; each file keeps its own LIMIT (rules-2.css holds every new row; the Row 1314 block stays last)
LIMIT = 128 * 1024                         # a Theme file larger than this is not read (the shipped files are held under it by a test)


def installed():
    """The names of the Themes that ship, sorted: every folder under themes/ that holds both files."""
    if not THEMES.is_dir():
        return []
    return sorted(p.name for p in THEMES.iterdir() if p.is_dir() and all((p / f).is_file() for f in FILES))


def css(name):
    """The comment-free, style-safe text of the Theme `name` (tokens.css, rules.css, then rules-2.css), or None for no name, an unknown
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


# Row 1269 slice B, changed by row 1363: Classic (the prototype-2.0 folder) is the only theme applied. The install's stored setting
# ('classic' or 'cards') is only read and is never rewritten; a stored 'cards' value stays in the file, unused, so bringing Cards back needs no migration.
# The Cards page is still what page.page_html(theme=None) draws; nothing in the app asks for it.
CLASSIC = "prototype-2.0"


def name_for(setting):
    """The Theme folder name page.page_html(theme=...) takes for an install setting: Classic for every value, a stored 'cards' included (row 1363)."""
    return CLASSIC


def of_store(store):
    """The Theme folder name for the Theme the open `store` holds now (read only; Classic whatever it holds)."""
    return name_for(store.theme())
