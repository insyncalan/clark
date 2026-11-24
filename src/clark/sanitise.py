"""The rich-text cleaner: the one allow-list for clark's three rich fields (#66a).

The fields are projects.current_state, use_cases.standing and a text section's body. The editor writes them as HTML; the
store (#31), the page (cleanHtml, #66) and the publish build (#39) all pass them through clean_html() before they are saved
or shown. This is the authoritative copy. It is clark's own, written from the #66 readiness check; creaite's clean_markup
was a model for the shape of an allow-list only and nothing is copied (so there is no REUSE row).

What may stay, and nothing else:
- p, br, strong, em, s, h1, h2, h3, ul, ol, li, blockquote, hr, with no attributes at all;
- a, with href only and rel="noopener noreferrer" added: the address must be http:, https:, mailto: or a #fragment;
- input, only as `input type="checkbox"` (a checklist item), with `checked` and `disabled` as its only other attributes.
Every other tag is removed and its text stays (a removed block tag such as div or td leaves a line break between its text and
the next), except script, style, iframe, object, form, svg, math, template, noscript and the like, which are removed with
everything inside (embed is removed on its own: it has no end tag). Comments, CDATA, <![if]>, <?php ?> and doctypes are removed.

How it is safe: the output is built from scratch. Text is always escaped again (& < > and the no-break space), and the only
tags written are the ones above, with attributes written by this module, so nothing the parser misreads can reach the output
as markup. Where the input is mangled (an unclosed tag, `<scr<script>ipt>`) the worst result is escaped text. The cleaner also
repairs the tree as a browser would (a p ends at the next block, an li at the next li, an a inside an a closes the first), so
the output means the same to a browser and to this module, and cleaning it again changes nothing.

The markup is read by this module's own tokeniser (tokens(), below), not html.parser: that is slow on unfinished tags on
Python 3.9 and reads some cases differently from one Python to the next. This one is one pass, so any input of MAX_CHARS is fast.

Not here: Excel and Word round trips (plain text), the page's copy of these rules (sanitise.js, #66).
Difference from a browser, on the safe side: nesting deeper than MAX_DEPTH is flattened (the tags go, the text stays).

Standard library only, Python 3.9.
"""
import html as htmllib
from html.entities import html5
import re
import unicodedata

MAX_CHARS = 200_000          # the longest field accepted, and the longest result
MAX_DEPTH = 50               # open tags nested deeper than this are removed (their text stays); a browser stops near 512
MAX_HREF = 8000
MAX_BLANK_RUN = 5            # blank lines (empty paragraphs) in a row that are kept; a longer run is cut to this (#84)

ALLOWED = frozenset(("p", "br", "strong", "em", "s", "h1", "h2", "h3", "ul", "ol", "li", "blockquote", "hr", "a", "input"))
VOID = frozenset(("br", "hr", "input"))
INLINE = frozenset(("strong", "em", "s", "a"))
PARAGRAPH = frozenset(("p", "h1", "h2", "h3"))                  # these hold inline content only: a block ends them
ENDS_PARAGRAPH = frozenset(("p", "h1", "h2", "h3", "ul", "ol", "li", "blockquote", "hr"))
# Removed with everything inside (an unclosed one takes the rest of the field with it). Others just lose their tag.
# (Never a void element such as embed: it has no end tag to wait for, so everything after it would go.)
DROP_WITH_CONTENT = frozenset(("script", "style", "iframe", "object", "applet", "form", "svg", "math", "template",
                               "noscript", "noembed", "noframes", "textarea", "select", "title", "xmp", "plaintext", "head"))
# Block-level tags that are removed (their text stays): a line break is written where one begins or ends, so words do not join.
BLOCKS = frozenset(("address", "article", "aside", "caption", "center", "dd", "details", "dialog", "dir", "div", "dl", "dt",
                    "fieldset", "figcaption", "figure", "footer", "form", "h4", "h5", "h6", "header", "hgroup", "legend", "listing",
                    "main", "menu", "nav", "optgroup", "option", "pre", "section", "summary", "table", "tbody", "td", "tfoot", "th",
                    "thead", "tr"))
BREAKING = ALLOWED - INLINE - {"input"}                         # the written tags that already start a new line
EMPTY_FOREIGN = ("svg", "math")                                  # `<svg/>` is an empty element, as in a browser

# Control characters (not tab, newline or carriage return) and lone surrogates: removed before parsing, so `<scr\x00ipt>` is
# seen as the script it is, and again from decoded text and attribute values (`&#1;`).
CONTROL = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\ud800-\udfff]")
ADDRESS = re.compile(r"(?:https?://[^/?#]|mailto:.|#)", re.I)    # what a link may start with, after the clean-up below
BAD_IN_ADDRESS = frozenset(("Cc", "Cf", "Cs", "Co", "Zl", "Zp", "Zs"))   # a plain space is the one allowed (see href())
# Not Cn (unassigned): unicodedata's table is a different Unicode version on each Python, so a character assigned later would
# pass on one and not on another. The noncharacters are Cn for good, and these format characters were Cn before Unicode 14 and
# 15 (U+0890-0891 and U+13439-1343F): refused by number so the answer is the same on every Python.
ALWAYS_BAD = ((0x0890, 0x0891), (0x13439, 0x1343F), (0xFDD0, 0xFDEF))


def bad_in_address(c):
    n = ord(c)
    return (c != " " and unicodedata.category(c) in BAD_IN_ADDRESS) or n & 0xFFFE == 0xFFFE or any(a <= n <= b for a, b in ALWAYS_BAD)


class SanitiseError(ValueError):
    """The text could not be cleaned, in words a person can act on (it is too long, or not text)."""


def text_escape(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\xa0", "&nbsp;")


def attr_escape(text):
    return text.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")


def href(value):
    """The address a link may point to, tidied, or None. http:, https:, mailto: or #fragment only; checked after what a browser
    does first (tab, newline and carriage return go from anywhere, leading and trailing control characters and spaces go), so
    `jav&#9;ascript:`, ` javascript:` and `&#106;avascript:` (decoded by the parser) never pass. Any control, format,
    line-separator or other odd space character, and any noncharacter, inside refuses the address; a plain space becomes %20."""
    if value is None:
        return None
    v = value.replace("\t", "").replace("\n", "").replace("\r", "").strip("".join(chr(c) for c in range(33)))
    if not v or len(v) > MAX_HREF or not ADDRESS.match(v):
        return None
    if any(bad_in_address(c) for c in v):
        return None
    return v.replace(" ", "%20")


# ===== Reading the markup (linear: each step moves forward, so no input is slow) =====
# html.parser is not used: on Python 3.9 it rescans unfinished tags and comments and takes minutes on 200,000 characters of
# `<a <a <a`, and its rules differ between Python versions. This follows the HTML tokeniser's rules for the cases that matter.
RAW_TEXT = frozenset(("script", "style", "textarea", "title", "xmp", "iframe", "noembed", "noframes", "noscript", "plaintext"))
SPACE = " \t\n\r\f"
TAG_NAME = re.compile(r"[a-zA-Z][^ \t\n\r\f/>]*")
SPACES_AND_SLASHES = re.compile(r"[ \t\n\r\f/]*")
SPACES = re.compile(r"[ \t\n\r\f]*")
ATTR_NAME = re.compile(r"[^ \t\n\r\f/>][^ \t\n\r\f/>=]*")
UNQUOTED = re.compile(r"[^ \t\n\r\f>]*")
RAW_END = {name: re.compile(r"</%s(?=[ \t\n\r\f/>])" % name, re.I) for name in RAW_TEXT}
COMMENT_END = re.compile(r"--!?>")
HUGE_NUMBER = re.compile(r"&#(?:[0-9]{9,}|[xX][0-9a-fA-F]{9,});?")   # a browser reads these as U+FFFD; int() of them is slow or refused


REFERENCE = re.compile(r"&(#[0-9]+;?|#[xX][0-9a-fA-F]+;?|[^\t\n\f <&#;]{1,32};?)")
LEGACY = frozenset(name for name in html5 if not name.endswith(";"))   # the names a browser reads without their semicolon


def attribute_reference(m):
    """One reference in an attribute value. As in a browser, a name without its semicolon is left as written when the next
    character is `=` or a letter or digit (`&region=eu` in an address is not (R)ion=eu); html.unescape would decode it. The
    names are html.entities' own table, the same on every Python, so the rule is made here."""
    name = m.group(1)
    if name[0] == "#" or name in html5:
        return htmllib.unescape(m.group())
    for size in range(len(name) - 1, 1, -1):
        if name[:size] in LEGACY:
            following = m.string[m.start(1) + size:m.start(1) + size + 1]
            if following == "=" or (following.isascii() and following.isalnum()):
                return m.group()
            return html5[name[:size]] + name[size:]
    return m.group()


def decode(text, attribute=False):
    """Character references decoded (&amp; &#106; &#x6A; and the old forms without a semicolon). In an attribute value (an
    address) a name without a semicolon followed by `=` or a letter or digit stays as written."""
    if "&" not in text:
        return text
    text = HUGE_NUMBER.sub("\ufffd", text)
    return REFERENCE.sub(attribute_reference, text) if attribute else htmllib.unescape(text)


def read_tag(text, pos):
    """The attributes of the tag whose name has just ended at `pos`: (attrs, self_closing, position after the `>`), or None
    if the text ends first (a browser drops a tag that never ends)."""
    attrs, n = [], len(text)
    while True:
        end = SPACES_AND_SLASHES.match(text, pos).end()
        if end >= n:
            return None
        if text[end] == ">":
            return attrs, text[end - 1] == "/" and end > pos, end + 1
        m = ATTR_NAME.match(text, end)
        name, pos = m.group().lower(), m.end()
        after = SPACES.match(text, pos).end()
        value = ""
        if after < n and text[after] == "=":
            after = SPACES.match(text, after + 1).end()
            if after >= n:
                return None
            if text[after] in "\"'":
                close = text.find(text[after], after + 1)
                if close < 0:
                    return None
                value, pos = text[after + 1:close], close + 1
            else:
                m = UNQUOTED.match(text, after)
                value, pos = m.group(), m.end()
        attrs.append((name, decode(value, True)))


def tokens(text):
    """The markup in `text` as ("text", raw), ("start", name, attrs, self_closing) and ("end", name). Comments, <![CDATA[ ]]>,
    <![if]>, <?php ?> and doctypes give nothing; so does the inside of a raw-text element (script, style and the like), which
    runs to its own end tag, or to the end of the text."""
    pos, n = 0, len(text)
    while pos < n:
        lt = text.find("<", pos)
        if lt < 0:
            yield "text", text[pos:]
            return
        if lt > pos:
            yield "text", text[pos:lt]
        pos, nxt = lt + 1, text[lt + 1:lt + 2]
        after = text[lt + 2:lt + 3]                            # what follows `</`
        if text.startswith("!--", pos):
            pos += 3
            if text.startswith(">", pos) or text.startswith("->", pos):      # `<!-->` and `<!--->` are whole comments
                pos += 1 + (text[pos] == "-")
                continue
            m = COMMENT_END.search(text, pos)
            pos = m.end() if m else n
        elif nxt == "/" and after == ">":                      # `</>`
            pos += 2
        elif nxt in ("!", "?") or (nxt == "/" and not (after.isascii() and after.isalpha())):
            close = text.find(">", pos)                        # a bogus comment, up to the first >
            pos = close + 1 if close >= 0 else n
        elif nxt == "/" or (nxt.isascii() and nxt.isalpha()):
            ending = nxt == "/"
            pos += ending
            m = TAG_NAME.match(text, pos)
            name = m.group().lower()
            read = read_tag(text, m.end())
            if read is None:
                return
            attrs, self_closing, pos = read
            if ending:
                yield "end", name
                continue
            yield "start", name, attrs, self_closing
            if name == "plaintext":
                return
            if name in RAW_TEXT:
                m = RAW_END[name].search(text, pos)
                pos = m.start() if m else n
        else:
            yield "text", "<"


class _Cleaner:
    """Receives the tokens and writes the clean markup. `out` is what is written; `stack` the tags open in it."""

    def __init__(self):
        self.out, self.stack = [], []
        self.skip, self.nest = None, 0         # inside a dropped element: its name, and how many of it are open
        self.gap, self.running = False, False  # a removed block tag was passed; the last thing written is text or inline

    # ----- the tree
    def _pop_to(self, index):
        while len(self.stack) > index:
            self.running = self.stack[-1] in INLINE
            self.out.append(f"</{self.stack.pop()}>")

    def _write(self, piece, tag=None):
        """Write `piece`, with a line break first if a removed block tag came between it and running text or an inline tag."""
        if self.gap and self.running and tag not in BREAKING and piece[0] not in SPACE:
            self.out.append("\n")
        self.gap = False
        self.running = tag not in BREAKING and not piece.endswith("\n")
        self.out.append(piece)

    def _make_room(self, tag):
        """Close what a browser would close before `tag` opens."""
        if tag == "a" and "a" in self.stack:
            self._pop_to(self.stack.index("a"))
        if tag == "li":                                       # the previous item of this list, if it is still open
            for i in range(len(self.stack) - 1, -1, -1):
                if self.stack[i] in ("ul", "ol", "blockquote"):
                    break
                if self.stack[i] == "li":
                    self._pop_to(i)
                    break
        if tag in ENDS_PARAGRAPH:                             # a p or heading, with only inline tags above it
            i = len(self.stack) - 1
            while i >= 0 and self.stack[i] in INLINE:
                i -= 1
            if i >= 0 and self.stack[i] in PARAGRAPH:
                self._pop_to(i)

    # ----- the tokens
    def start(self, tag, attrs, self_closing):
        if self_closing and tag in EMPTY_FOREIGN:             # `<svg/>` is an empty element; `<p/>` opens a p, as in a browser
            return
        if self.skip:
            self.nest += tag == self.skip
            return
        if tag in BLOCKS:
            self.gap = True
        if tag in DROP_WITH_CONTENT:
            self.skip, self.nest = tag, 1
            return
        if tag not in ALLOWED:
            return                                            # the tag goes, its text stays
        given = {}
        for name, value in attrs:
            given.setdefault(name, value)                     # the first of a repeated attribute counts, as in a browser
        self._make_room(tag)
        if tag == "input":
            if given.get("type", "").strip().lower() != "checkbox":
                return
            flags = "".join(f" {k}" for k in ("checked", "disabled") if k in given)
            self._write(f'<input type="checkbox"{flags}>', tag)
            return
        if tag == "a":
            target = href(given.get("href"))
            if target is None:
                return                                        # a link with no safe address is just its text
            opening = f'<a href="{attr_escape(target)}" rel="noopener noreferrer">'
        else:
            opening = f"<{tag}>"
        if tag in VOID:
            self._write(opening, tag)
        elif len(self.stack) < MAX_DEPTH:
            self._write(opening, tag)
            self.stack.append(tag)

    def end(self, tag):
        if self.skip:
            if tag == self.skip:
                self.nest -= 1
                if not self.nest:
                    self.skip = None
            return
        if tag == "br":                                       # a browser reads `</br>` as `<br>`
            self.start("br", [], False)
            return
        if tag in BLOCKS:
            self.gap = True
        if tag in ALLOWED and tag not in VOID and tag in self.stack:
            self._pop_to(len(self.stack) - 1 - self.stack[::-1].index(tag))

    def text(self, data):
        if not self.skip:
            data = CONTROL.sub("", data)
            if data:
                self._write(text_escape(data))


def clean_html(text):
    """`text` (HTML the editor wrote) reduced to the allow-list, as one well-formed string. None and "" give "". A field
    that is already clean comes back byte for byte; cleaning the result again changes nothing. Raises SanitiseError if `text`
    is not text, or is, or would come out, longer than MAX_CHARS. Blank lines (empty paragraphs) are kept, a paragraph of only spaces becomes empty, and a run
    of more than MAX_BLANK_RUN is cut to that (spaces and newlines between them do not hide a run)."""
    if text is None:
        return ""
    if not isinstance(text, str):
        raise SanitiseError("Rich text must be text, not %s." % type(text).__name__)
    check_length(len(text))
    cleaner = _Cleaner()
    for token in tokens(CONTROL.sub("", text)):
        if token[0] == "text":
            cleaner.text(decode(token[1]))
        elif token[0] == "start":
            cleaner.start(*token[1:])
        else:
            cleaner.end(token[1])
    cleaner._pop_to(0)
    result = limit_blank_lines("".join(cleaner.out))
    check_length(len(result), tidied=True)
    return result


# A blank line, as the editor writes it: an empty paragraph, or one holding only a line break (a paragraph of only spaces is
# made empty first, since a browser draws that with no height). A run of them is cut to MAX_BLANK_RUN: five is a clear gap
# between two parts of a text; more is spacing used as layout, or a field padded to be large. Nothing else is touched.
SPACE_ONLY = re.compile(r"<p>[ \t\n\r\f]+</p>")
BLANK_TEXT = " \t\n\r\f\xa0"                   # what a blank line may hold as text in plain_text (no zero-width or wide spaces)
BLANK_LINE = r"<p>(?:<br>)?</p>"
GAP = r"[ \t\n\r\f]*"                   # spaces and newlines the editor leaves between two paragraphs
BLANK_RUN = re.compile(r"(?:%s%s){%d,}" % (BLANK_LINE, GAP, MAX_BLANK_RUN + 1))


def limit_blank_lines(markup):
    """`markup` (already cleaned) with a paragraph of only spaces made empty and any run of blank lines cut to MAX_BLANK_RUN.
    One linear pass; cleaning the result again changes nothing. This is a tidy-up, not a limit on size: it counts only
    `<p></p>` and `<p><br></p>`, so a run of `<p>&nbsp;</p>` or `<p><br><br></p>` is kept (and draws a line each); the bound on
    a field is MAX_CHARS."""
    if "</p>" not in markup:
        return markup
    markup = SPACE_ONLY.sub("<p></p>", markup)
    return BLANK_RUN.sub(lambda m: "".join(re.findall(BLANK_LINE, m.group())[:MAX_BLANK_RUN]), markup)


def check_length(n, tidied=False):
    """Refuse a length over MAX_CHARS. The message says which count it is: the text as written, or the text once tidied (a
    symbol such as & takes more room then, so a field a little under the limit can still be refused)."""
    if n > MAX_CHARS:
        if tidied:
            raise SanitiseError("That text is too long: it comes to %s characters once it is tidied up for saving (a symbol such "
                                "as & takes more room then), and the most one field can hold is %s."
                                % (format(n, ","), format(MAX_CHARS, ",")))
        raise SanitiseError("That text is too long: it is %s characters as written, and the most one field can hold is %s."
                            % (format(n, ","), format(MAX_CHARS, ",")))


BREAKS = frozenset(("p", "br", "h1", "h2", "h3", "ul", "ol", "li", "blockquote", "hr"))


def plain_text(html):
    """The words in `html`: it is cleaned first (so script and style text never counts), tags are removed, entities are
    decoded, and paragraphs, list items and line breaks become a newline. For search and length checks; it is not HTML and
    must not be put back into a page unescaped. Same length limit as clean_html. Each blank line (an empty paragraph, or one of
    only spaces or &nbsp;) is one empty line, a run is capped as in clean_html, and the ends are trimmed."""
    parts, found, i = [], list(tokens(clean_html(html))), 0     # the cleaned markup holds only text and allowed tags
    while i < len(found):
        token = found[i]
        i += 1
        if token[0] == "text":
            parts.append(decode(token[1]))
        elif token[1] in BREAKS and parts and not parts[-1].endswith("\n"):
            parts.append("\n")
        if token[0] == "start" and token[1] == "p":              # a blank line: <p></p> or <p><br></p> is one empty line (#84)
            j = i
            if j < len(found) and found[j][0] == "text" and not decode(found[j][1]).strip(BLANK_TEXT):
                j += 1                                           # a paragraph of only spaces or &nbsp; is a blank line too
            elif j < len(found) and found[j][:2] == ("start", "br"):
                j += 1
            if j < len(found) and found[j][:2] == ("end", "p"):
                if parts:
                    parts.append("\n")
                i = j + 1
    return "".join(parts).strip()
