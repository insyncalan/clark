"""A pasted SharePoint or OneDrive link as the one folder OneDrive syncs it to on this computer (item 647). publish_flow.py calls
match() for the client folder's paste box; the folder it finds is then checked exactly as a chosen one. Nothing here opens the
link or reaches the network: the link is read as text, and the only disk reads are folder listings under the OneDrive roots.

Standard library only, Python 3.9.
"""
import re
import unicodedata
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

MAX_LINK_PARTS = 40                  # folders below a SharePoint library that a link may name
SHAREPOINT_HOST = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.sharepoint\.com")
OPAQUE_HOSTS = ("onedrive.live.com", "1drv.ms")      # personal OneDrive links name an item by number, never by folder


def has_control(text):
    """True when `text` holds a control or formatting character (a new line, NUL, a zero-width or direction mark)."""
    return any(unicodedata.category(ch) in ("Cc", "Cf") for ch in text)


def plain(name):
    """A name for matching a link to a folder: letters and digits only, without case."""
    return "".join(ch for ch in unicodedata.normalize("NFC", str(name)).casefold() if ch.isalnum())


def folders(path):
    try:
        return [p for p in Path(path).iterdir() if p.is_dir()]
    except OSError:
        return []


def child_path(base, names):
    """`base` with each of `names` below it, as existing folders matched without case; None when one isn't there or is ambiguous."""
    here = Path(base)
    for name in names:
        if not name or "/" in name or name in (".", ".."):
            return None
        exact = here / name
        if exact.is_dir():
            here = exact
            continue
        same = [p for p in folders(here) if p.name.casefold() == name.casefold()]
        if len(same) != 1:
            return None
        here = same[0]
    try:
        return here.resolve(strict=True) if here.is_dir() else None
    except (OSError, RuntimeError):
        return None


def match(text, onedrive_roots):
    """A SharePoint link as the one folder OneDrive syncs it to here. The link's site, library and folders are read from its
    address (or its id= for a library view); a synced library is a folder in a OneDrive root named "<site> - <library>"
    (the default library's address name, "Shared Documents", is shown as "Documents"), and a folder synced on its own is
    "<site> - <folder>". Names are compared ignoring case, spaces and punctuation. A link to someone's own OneDrive
    (-my.sharepoint.com/personal/...) is matched under a root that is not a shared-libraries one. Only one existing folder
    may match: none, or more than one, is no match. A sharing link that names no folder (/:f:/s/...) never matches."""
    try:
        u = urlsplit(text)
        host = (u.hostname or "").lower()
        port = u.port
    except ValueError:
        return None, "paste_unknown"
    if u.username or u.password or port is not None:
        return None, "paste_unknown"
    if host in OPAQUE_HOSTS:
        return None, "paste_no_match"
    if not SHAREPOINT_HOST.fullmatch(host):
        return None, "paste_unknown"
    query = parse_qs(u.query)
    ids = query.get("id") or query.get("RootFolder")
    where = ids[0] if ids else unquote(u.path)
    if has_control(where) or "\\" in where:
        return None, "paste_unknown"
    parts = [p for p in where.split("/") if p]
    if parts and re.fullmatch(r":[a-z]:", parts[0]):
        if parts[1:2] != ["r"]:
            return None, "paste_no_match"
        parts = parts[2:]
    if not ids:
        cut = next((i for i, p in enumerate(parts) if p.lower() == "forms" or p.lower().endswith(".aspx")), len(parts))
        parts = parts[:cut]
    if any(p in (".", "..") for p in parts) or len(parts) > MAX_LINK_PARTS + 3:
        return None, "paste_unknown"
    found = set()
    for base, rest in _link_bases(host, parts, onedrive_roots):
        folder = child_path(base, rest)
        if folder is not None:
            found.add(folder)
    if len(found) != 1:
        return None, "paste_no_match"
    return found.pop(), None


def _link_bases(host, parts, onedrive_roots):
    """(a folder in a OneDrive root, the folder names below it) for each place the link's address could be synced to."""
    roots = [Path(r) for r in onedrive_roots]
    if host.endswith("-my.sharepoint.com"):
        if len(parts) >= 3 and parts[0].lower() == "personal":
            for root in roots:
                if "sharedlibraries" not in plain(root.name):
                    yield root, parts[3:]
        return
    if len(parts) < 3 or parts[0].lower() not in ("sites", "teams"):
        return
    site, library, tail = plain(parts[1]), parts[2], parts[3:]
    libraries = {plain(library)} | ({plain("Documents")} if plain(library) == plain("Shared Documents") else set())
    for root in roots:
        for child in folders(root):
            pieces = child.name.split(" - ")
            for i in range(1, len(pieces)):
                if plain(" - ".join(pieces[:i])) != site:
                    continue
                right = plain(" - ".join(pieces[i:]))
                if right in libraries:
                    yield child, tail
                for n, name in enumerate(tail):
                    if right == plain(name):
                        yield child, tail[n + 1:]
