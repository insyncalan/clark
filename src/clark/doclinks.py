"""Links on Supporting Documents (#74; BRD FR-100, FR-81): one rule for what a link may be, and what a person sees of it.

New in clark; no creaite source. Pure functions with no database and no network, so the page's dialog, the store's `url`
check and the publish build can all call the same rule (the spec's four layers must not drift apart). A link is
refused unless, after trimming spaces at either end, it is an http, https or mailto address and nothing about it can
hide where it goes. Anything odd is refused, never repaired: the only changes made are lower-casing the scheme and the host,
and dropping the leading zeros of a port number (:08080 is kept as :8080, so one address has one spelling).

Nothing here depends on which Unicode version the running Python knows (no `unicodedata`, no `isalpha`, no `\\w`, no
normalisation): the answers come from the character's code point and the fixed lists below, so every Python gives the
same answer for every text, whether or not a character was assigned yet. (Only str.lower() and str.split() are still used,
on text where they can't differ: lower() on host names that are already plain a-z, and the title's comparison of a
non-ASCII host, which is "another place" either way.)

Two notes for whoever builds on this. A link may hold a single quote or a backtick, and check_link keeps it as typed, so
whoever writes a link's address into an href (the page, and the publish build) must escape it at render and at publish.
src/clark/order.py must stay identical to the copy in #65 part A (sections) until both are on main.
"""
import re

MAX_LENGTH = 2000
SCHEMES = ("http", "https", "mailto")

# Plain words for the dialog. The first is the owner's text from the spec (point 12); none names a scheme or a "URL".
NOT_USABLE = "That link can't be used. It must start with https://, http:// or mailto:"
EMPTY = "Add a link."
TOO_LONG = "That link is too long. It can be 2,000 characters at most. Use a shorter link to the same page."
HIDDEN = "That link has a space, a hidden character or a character that can't be used in it. Paste it again."
CREDENTIALS = "That link has a user name or password in it, which isn't allowed. Take them out, then add the link again."
NO_SITE = "That link has no site name in it. Copy the whole address from the address bar, then paste it again."
BAD_SITE = "That site name can't be used. If it uses another alphabet, open the site and copy its address from the address bar."
BAD_PORT = "That link's number after the site name isn't right. Copy the address from the address bar, then paste it again."
ONE_EMAIL = "An email link must hold one email address and nothing else."
BAD_EMAIL = "That email address isn't written the usual way."
TITLE_ELSEWHERE = "That title looks like the address of another site. Use words, or the link's own site name."

# The kinds a document may be (#74): the store, the change route and the publish build all read this one list.
KINDS = ("Minutes", "Actions list", "Report", "Slides", "Plan", "Other")


class LinkError(ValueError):
    """A link that can't be used; the message is in plain words for the person adding it."""


_SCHEME = re.compile(r"([A-Za-z][A-Za-z0-9+.-]*):")
_LABEL = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?")
_PORT = re.compile(r"[0-9]{1,5}")
_LOCAL = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9._+'-]*[A-Za-z0-9_+'-])?")
_BAD_CHARACTER = re.compile(r'[\\<>"]|%(?:[01][0-9A-Fa-f]|7[Ff])')     # backslash reads as "/"; %00 to %1F and %7F are controls
_MAIL_EXTRAS = re.compile(r"[?#%,;]")                                   # headers, a fragment, encoding, a second recipient


# Fixed lists of code points (Unicode 17), so no Python's own table is consulted. Characters that are unassigned, or
# assigned later than the list, are not refused: only these are.
_FORMAT = ((0xAD, 0xAD), (0x600, 0x605), (0x61C, 0x61C), (0x6DD, 0x6DD), (0x70F, 0x70F), (0x890, 0x891), (0x8E2, 0x8E2),
           (0x180E, 0x180E), (0x200B, 0x200F), (0x202A, 0x202E), (0x2060, 0x2064), (0x2066, 0x206F), (0xFEFF, 0xFEFF),
           (0xFFF9, 0xFFFB), (0x110BD, 0x110BD), (0x110CD, 0x110CD), (0x13430, 0x1343F), (0x1BCA0, 0x1BCA3),
           (0x1D173, 0x1D17A), (0xE0001, 0xE0001), (0xE0020, 0xE007F))        # zero-width, right-to-left override, tags ...
_CONTROL = ((0x00, 0x1F), (0x7F, 0x9F))
_SPACE = ((0x20, 0x20), (0xA0, 0xA0), (0x1680, 0x1680), (0x2000, 0x200A), (0x2028, 0x2029), (0x202F, 0x202F),
          (0x205F, 0x205F), (0x3000, 0x3000))                                  # every separator (categories Zs, Zl, Zp)
_SURROGATE_OR_PRIVATE = ((0xD800, 0xF8FF), (0xF0000, 0xFFFFD), (0x100000, 0x10FFFD))


def _in(c, ranges):
    return any(lo <= ord(c) <= hi for lo, hi in ranges)


def _hidden_character(c):
    """A control, format (zero-width, right-to-left override), separator (any space), surrogate or private-use
    character: categories Cc, Cf, Z*, Cs and Co, from fixed lists. Unassigned characters are not hidden characters."""
    if 0x20 < ord(c) < 0x7F:                                            # plain ASCII, the usual case
        return False
    return _in(c, _CONTROL) or _in(c, _SPACE) or _in(c, _FORMAT) or _in(c, _SURROGATE_OR_PRIVATE)


def _host(host):
    """The host in lower case, or LinkError. Letters, digits and hyphens in dotted labels; one trailing dot is kept.
    A last label of digits must be a plain four-part number, and 0x... is refused, so no browser can read the host as
    another number system (2130706433, 0x7f000001, 0177.0.0.1)."""
    if not host:
        raise LinkError(NO_SITE)
    name = host[:-1] if host.endswith(".") else host
    labels = name.split(".")
    if len(name) > 253 or not all(_LABEL.fullmatch(label) for label in labels):
        raise LinkError(BAD_SITE)
    last = labels[-1]
    if re.fullmatch(r"0[xX][0-9A-Fa-f]*", last):
        raise LinkError(BAD_SITE)
    if last.isdigit():
        quad = len(labels) == 4 and all(label.isdigit() and int(label) < 256 and (label == "0" or label[0] != "0")
                                        for label in labels)
        if not quad:
            raise LinkError(BAD_SITE)
    return host.lower()


def _parse(text):
    """(address, host, mailbox) for a link that may be used; LinkError otherwise. `mailbox` is the whole email
    address in lower case for a mailto link, else None. `address` is the text with its scheme and host lower-cased."""
    if not isinstance(text, str):
        raise LinkError(EMPTY)
    text = text.strip(" ")
    if not text:
        raise LinkError(EMPTY)
    if len(text) > MAX_LENGTH:
        raise LinkError(TOO_LONG)
    if any(_hidden_character(c) for c in text) or _BAD_CHARACTER.search(text):
        raise LinkError(HIDDEN)
    found = _SCHEME.match(text)
    if not found or found.group(1).lower() not in SCHEMES:             # also refuses "//host", "example.com", "/path"
        raise LinkError(NOT_USABLE)
    scheme, rest = found.group(1).lower(), text[found.end():]

    if scheme == "mailto":
        if rest.startswith("//") or _MAIL_EXTRAS.search(rest):
            raise LinkError(ONE_EMAIL)
        local, at, domain = rest.partition("@")
        if not at or "@" in domain or not _LOCAL.fullmatch(local) or ".." in local:
            raise LinkError(BAD_EMAIL)
        domain = _host(domain)
        return f"mailto:{local}@{domain}", domain, f"{local}@{domain}".lower()

    if not rest.startswith("//"):                                       # "https:example.com" is read as a site by browsers
        raise LinkError(NOT_USABLE)
    rest = rest[2:]
    end = min((i for i in (rest.find(c) for c in "/?#") if i >= 0), default=len(rest))
    authority, tail = rest[:end], rest[end:]
    if "@" in authority:
        raise LinkError(CREDENTIALS)
    host, colon, port = authority.partition(":")
    host = _host(host)                                                  # first, so "[::1]" is a site problem, not a number one
    if colon:
        if not (_PORT.fullmatch(port) and 1 <= int(port) <= 65535):
            raise LinkError(BAD_PORT)
        port = str(int(port))                                           # ":08080" is ":8080"
    return f"{scheme}://{host}{colon}{port}{tail}", host, None


def check_link(text):
    """The address to keep for `text`, or LinkError with a plain message.

    Allowed: http, https and mailto, in any letter case, 2,000 characters at most, spaces trimmed from either end. Refused:
    every other scheme (javascript, data, vbscript, file, blob, ftp ...), a scheme hidden by case, an entity, a tab,
    new line, NUL or other control character, a space or a leading control inside it; "//host", a relative path or a bare
    "example.com"; an empty site name; a site name not written as letters, digits and hyphens (a lookalike letter, an
    IPv6 or number-system host); a user name or password in the address; a backslash, "<", ">" or a quote; an encoded
    control character (%00, %0d); and a mailto with a second recipient or any header (?cc=, ?bcc=, ?body=, ?subject=).
    Only the scheme and the host are lower-cased and a port loses its leading zeros (:08080 becomes :8080; a port of more
    than five digits is refused); the rest is returned as it was given, so check_link(check_link(x)) is check_link(x).
    Only control, format, separator, surrogate and private-use characters are refused (a fixed list, the same on every
    Python); any other character, assigned or not, is accepted in a path, query or fragment."""
    return _parse(text)[0]


def link_host(url):
    """The site name where `url` goes, lower case, without its port: example.com for https://example.com:8080/x, and the
    part after the @ for a mailto. This is what Edit, View and the published file show beside the title. LinkError when
    `url` can't be used."""
    return _parse(url)[1].rstrip(".")


def link_label(title, url):
    """What a person sees for a link: the title, or the site name when the title is blank.

    The title is text only: control and hidden characters are dropped (a right-to-left override can't turn "exe.pdf"
    around) and runs of spaces and line breaks become one space; markup is left as the text it is. A blank title shows
    link_host(url), never the whole address, and the address is never the label in place of a title that says something.
    Where the link really goes is shown beside the label by the page (link_host); looks_like_other_place says when that
    must be made prominent. LinkError when `url` can't be used."""
    host = link_host(url)
    shown = "".join(" " if _in(c, _CONTROL) or _in(c, _SPACE) else c
                    for c in str(title or "") if not _in(c, _FORMAT))
    return " ".join(shown.split()) or host


# File names look like site names ("minutes.pdf"). These endings aren't site endings, so a title naming a file isn't read as an address.
_FILE_ENDINGS = {"pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "csv", "png", "jpg", "jpeg", "gif", "json", "xml",
                 "rtf", "odt", "ods", "odp"}
# What can be a letter or digit inside an address written in a title, decided by code point alone (no Unicode table):
# a-z, 0-9 and every character outside the listed blocks of spaces, punctuation, symbols, emoji and private use.
# A non-ASCII letter is then "another place" (below), and a mark or emoji beside an address is not part of the address.
_NOT_LETTERS = ((0x80, 0xBF), (0xD7, 0xD7), (0xF7, 0xF7), (0x1680, 0x1680), (0x2000, 0x2BFF), (0x2E00, 0x2E7F),
                (0x3000, 0x303F), (0xD800, 0xF8FF), (0xFE30, 0xFE6F), (0xFF00, 0xFF65), (0xFFF0, 0xFFFF),
                (0x1F000, 0x1FFFF), (0xE0000, 0x10FFFF))


def _letter_class():
    out, start = "", 0x80
    for lo, hi in _NOT_LETTERS + ((0x110000, 0x110000),):
        if lo > start:
            out += "\\U%08x-\\U%08x" % (start, lo - 1)
        start = max(start, hi + 1)
    return "A-Za-z0-9" + out


_L = _letter_class()                    # letters and digits
_W = _L + "_"                           # as \w, without its Unicode table
_SCHEMED = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://([^\s/?#]*)")
_EMAIL = re.compile(r"[^\s@<>()\[\],;:]+@([^\s@/?#<>()\[\],;]+)")
_WWW = re.compile(r"(?<![%s])[wW][wW][wW]\.[^\s/?#]+" % _W)
_BARE = re.compile(r"(?<![%s@.-])((?:[%s-])+(?:\.(?:[%s-])+)+)(?![%s@-])" % (_W, _L, _L, _W))
_NUMBERED = re.compile(r"(?<![%s.])([0-9]{1,3}(?:\.[0-9]{1,3}){3})(?![%s@-]|\.[0-9])" % (_W, _W))
_ENDING = re.compile(r"[A-Za-z%s]{2,}" % _L[len("A-Za-z0-9"):])


def _places(title):
    """(host, mailbox) for each thing in `title` that reads as an address: a scheme://host, an email address, www.something,
    something.com, or a four-part number. `mailbox` is the whole email address in lower case, else None."""
    text = "".join(chr(ord(c) - 0xFEE0) if 0xFF01 <= ord(c) <= 0xFF5E else c for c in title if not _in(c, _FORMAT))
    text = text.replace("\u3002", ".").replace("\uff61", ".")                # full-width letters, digits and dots read as ASCII
    found = []
    for m in _SCHEMED.finditer(text):
        host = m.group(1).rpartition("@")[2]
        host = host.rpartition(":")[0] if re.search(r":[0-9]*$", host) else host
        found.append((host, None))
    for m in _EMAIL.finditer(text):
        found.append((m.group(1), m.group(0).lower()))
    found += [(m.group(0), None) for m in _WWW.finditer(text)]
    for m in _BARE.finditer(text):
        last = m.group(1).rpartition(".")[2]
        if _ENDING.fullmatch(last) and last.lower() not in _FILE_ENDINGS:
            found.append((m.group(1), None))
    found += [(m.group(1), None) for m in _NUMBERED.finditer(text)]
    return found


def _bare(host):
    """A host as compared: lower case, no trailing dot, no leading www."""
    host = host.lower().rstrip(".")
    return host[4:] if host.startswith("www.") else host


def looks_like_other_place(title, url):
    """True when `title` holds an address (a web address, an email address, www.something, something.com or a four-part
    number) for a different place than the one `url` goes to: title "portal.example.com" linking to evil.example.net.
    The page uses it to make the real site name stand out beside the title.

    The same place means the same host, or a link inside the title's site (title example.com, link portal.example.com),
    ignoring a leading www. and the port. An email address in the title must be the link's own mailto address. A host
    with letters outside a-z (a lookalike letter) is always another place. A title with no address in it is False.
    Over-reporting is harmless (the site name is shown anyway); missing a mismatch is not. LinkError when `url` can't be used."""
    _, link_host_, mailbox = _parse(url)
    here = _bare(link_host_)
    for host, shown_mailbox in _places(str(title or "")):
        there = _bare(host)
        if not there.isascii():
            return True
        if mailbox is not None and shown_mailbox is not None:
            if shown_mailbox != mailbox:
                return True
            continue
        if there != here and not here.endswith("." + there):
            return True
    return False
