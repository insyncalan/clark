"""clark edit_ai: the text-cleaning core of creaite's edit_ai.py (#47b). Standard library only, Python 3.9.

Copied from creaite v2.6.9 (db5adb2): ID_RE, CODE_RE, Refused, LOOK_ALIKE, CONTROLS, DEFAULT_IGNORABLE, unseen, unmarked, normal.
Changed: loose_ids takes the project codes and an `exists` callable (the caller builds both from the store's read path) in place of
a database connection and the tracker. Added: hidden_count. Not here (#72 adds them as its own reviewed diff, which may not edit
this core): OPTIONS, PLACES, request, context, parse, check, result, relevel. Cut: the client, email, minutes and VIP parts.

Text is compared as a person sees it: a zero-width character, a Cyrillic look-alike or a Unicode "tag" character (U+E0000 range)
hides no ID, name or marker. USE `normal()` ONLY TO COMPARE AND DETECT (the claims check, the planted-instruction scan, a cited ID).
NEVER SHOW OR SEND ITS RESULT AS THE TEXT: `unseen` drops U+200C and U+200D, which Arabic and Persian writing uses to join and
separate letters, so a passage rewritten by it would be changed. A passage goes to the model and the user as it is, with
`hidden_count(text)` (how many hidden characters it holds) shown beside it. Whether to strip tag characters or controls from a passage
is 47c and 47d's decision.
"""
import re
import unicodedata

from clark import confusables

ID_RE = re.compile(r"\b[A-Z][A-Z0-9]{2,6}-(?:[A-Z]-)?\d{3}\b")       # ABC-A-001, ABC-001, ABC-D-001, ABC-M-001, ABC-W-001, ABC-U-001
CODE_RE = re.compile(r"[A-Z][A-Z0-9]{2,6}")


class Refused(Exception):
    """The request can't be suggested on (an unknown option or place, no text, too long)."""


# #123 review: a client reply's IDs are matched after normalising, so a look-alike, a zero-width character, a
# non-breaking hyphen, lower case or a missing space can't slip an item past the check (client_leak.text_findings matches IDs
# the same way since #127).
# v2.5.1 (#239): every look-alike letter of confusables.TABLE (Cyrillic, Greek, Armenian, Lisu, Cherokee, small capitals; ѕ, ԁ, у,
# օ and ꓮ among them), with the older entries below kept as they were where both name a character.
LOOK_ALIKE = str.maketrans({**{chr(k): v for k, v in confusables.TABLE.items()},
                            **{c: "-" for c in "\u2010\u2011\u2012\u2013\u2014\u2015\u2212\ufe58\ufe63\uff0d"},
                            **{c: "I" for c in "\u0399\u0406\u04c0\u01c0\u0131\u03b9\u0456"},
                            **{c: "V" for c in "\u0474\u0475\u03bd"}, **{c: "P" for c in "\u03a1\u0420\u03c1\u0440"},
                            # #127 review: the other Cyrillic and Greek letters that look Latin (a project code's "АВС")
                            **dict(zip("\u0410\u0412\u0415\u041a\u041c\u041d\u041e\u0421\u0422\u0425\u0430\u0435\u043e\u0441\u0445"
                                       "\u0391\u0392\u0395\u0396\u0397\u039a\u039c\u039d\u039f\u03a4\u03a5\u03a7\u03bf",
                                       "ABEKMHOCTXaeocxABEZHKMNOTYXo"))})


# #127 round 4: characters Word shows as nothing that aren't format characters (Unicode category Cf, all dropped by unseen): the
# combining grapheme joiner, variation selectors, Mongolian free variation selectors, Khmer inherent vowels, Hangul fillers and the
# unassigned U+2065 among the invisible operators.
# #127 round 5: Unicode's whole Default_Ignorable_Code_Point set (DerivedCoreProperties), assigned or not, as (first, last): an
# unassigned one (U+FFF0, U+E0080, U+E01F0) isn't category Cf, but Word and a browser still draw it as nothing.
DEFAULT_IGNORABLE = ((0x00AD, 0x00AD), (0x034F, 0x034F), (0x061C, 0x061C), (0x115F, 0x1160), (0x17B4, 0x17B5),
                     (0x180B, 0x180F), (0x200B, 0x200F), (0x202A, 0x202E), (0x2060, 0x206F), (0x3164, 0x3164),
                     (0xFE00, 0xFE0F), (0xFEFF, 0xFEFF), (0xFFA0, 0xFFA0), (0xFFF0, 0xFFF8), (0x1BCA0, 0x1BCA3),
                     (0x1D173, 0x1D17A), (0xE0000, 0xE0FFF))
SHOWN_AS_NOTHING = frozenset(cp for a, b in DEFAULT_IGNORABLE for cp in range(a, b + 1))
SHOWN_AS_SPACE = {0x2800: " "}            # #127 round 5: the braille blank draws as a space
# #127 round 6: control characters (Cc) other than tab, line feed and carriage return, and the noncharacters (U+FDD0 to U+FDEF and
# the last two of every plane): Word draws them as nothing (or won't open the file: docx_tools.esc strips them). Those Python's
# splitlines breaks a line at (so a Word export starts a new line there: VT, FF, the separators U+001C to U+001E, NEL) are a line break.
# #127 round 7: a lone surrogate (U+D800 to U+DFFF) too: docx_tools.esc drops it, so Word shows it as nothing.
LINE_LIKE = "\x0b\x0c\x1c\x1d\x1e\x85"
CONTROLS = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\ufdd0-\ufdef\ud800-\udfff"
                      + "".join(chr(p * 0x10000 + 0xFFFE) + chr(p * 0x10000 + 0xFFFF) for p in range(17)) + "]")


def unseen(text):
    """Text without the characters Word shows as nothing: every format character (category Cf: zero-width, direction marks and
    isolates, tags, the soft hyphen, the interlinear annotation marks) and every default-ignorable one (SHOWN_AS_NOTHING, assigned
    or not); the braille blank is a space (#127 rounds 4 and 5); control characters and noncharacters (CONTROLS) are gone, or a
    line break where a Word export breaks the line (LINE_LIKE; round 6)."""
    t = CONTROLS.sub(lambda m: "\n" if m.group() in LINE_LIKE else "", text or "")     # round 6: controls and noncharacters
    if t.isascii():
        return t
    return "".join(c for c in t if ord(c) not in SHOWN_AS_NOTHING and unicodedata.category(c) != "Cf").translate(SHOWN_AS_SPACE)


def unmarked(text):
    """Text without its combining marks (#127 round 5): NFKD, then every mark (Mn, Me and Mc) dropped, so an accent or an
    enclosing circle on a digit or a letter hides no ID, marker or name (an acute accent on a 0 of ABC-A-004 still reads ABC-A-004;
    Word draws the mark, so the reader still reads the ID). A name in a script
    that writes vowels as marks (Devanagari, Arabic) is still found: the register's name goes through the same fold as the text,
    so both lose the same marks."""
    t = text or ""
    if t.isascii():
        return t
    return "".join(c for c in unicodedata.normalize("NFKD", t) if not unicodedata.category(c).startswith("M"))


def normal(text):
    """Text as the client check matches it: NFKC, invisible characters gone (unseen, before and after NFKC, which can make a
    filler of a compatibility one), combining marks gone (unmarked), dashes and look-alike letters made plain."""
    t = unmarked(unseen(text).translate(LOOK_ALIKE)).translate(LOOK_ALIKE)      # v2.5.1: before NFKD/NFKC too (Ϲ would be Σ)
    t = unseen(unicodedata.normalize("NFKC", t)).translate(LOOK_ALIKE)
    return re.sub(r"\d", lambda m: str(unicodedata.decimal(m.group(), 0)), t)      # #127 review: any script's digits, as 0-9


def hidden_count(text):
    """How many characters of `text` a reader can't see: the ones `unseen` drops or turns into a space or a line break. clark's
    addition (creaite has none). It is a count to show beside a passage, which is itself left unchanged. A Persian or Arabic
    passage counts its joiners (U+200C, U+200D) too: the count is a signal, not proof of an attack."""
    n = 0
    for c in text or "":
        if CONTROLS.match(c) or ord(c) in SHOWN_AS_NOTHING or ord(c) in SHOWN_AS_SPACE or unicodedata.category(c) == "Cf":
            n += 1
    return n


def _held(exists, ref):
    """Whether `exists(ref)` says the item is real; True when it can't be asked (an `exists` that raises: fails closed)."""
    try:
        return bool(exists(ref))
    except Exception:  # noqa: BLE001  an item that can't be looked up is counted
        return True


def loose_ids(codes, exists, text):
    """Every item ID a text holds, however it is written: the strict form anywhere, and for each of the project `codes`,
    any case, with spaces, dots, dashes, underscores, slashes, backslashes, colons or brackets for its hyphens ("ABC (A) 004"),
    or run on to a word before it ("seeABC-A-004"); with a letter part, the number may also drop its zeros ("ABC-A-4") or write them as O
    ("ABC-A-OO4"), always as a whole number ("ABC-A-40" is ABC-A-040, never ABC-A-004), and not one a slash, colon or dot continues
    ("ABC A 10/09"). A loose match counts only when `exists(ref)` says the item is real (#123 review L: "ABC 100 users" isn't
    ABC-100 when there is no ABC-100); it fails closed, so an `exists` that raises counts the ID. Changed from creaite, which
    took a database connection: the caller builds `codes` and `exists` from the store's read path."""
    t = normal(text)
    out = set(ID_RE.findall(t))
    up, sep = t.upper(), r"[\s_.\-/:()\\]*"         # #127 round 5: a Markdown backslash escape ("ABC\-A\-004") too
    for c in codes or ():
        if not isinstance(c, str) or not CODE_RE.fullmatch(c):
            continue
        for m in re.finditer(rf"{re.escape(c)}{sep}(?:([A-NP-Z]){sep}([0-9O]{{1,3}})|([0-9O]{{3}}))(?![0-9O]|[/:.]\d)", up):
            num = (m.group(2) or m.group(3)).replace("O", "0").zfill(3)
            ref = f"{c}-{m.group(1)}-{num}" if m.group(1) else f"{c}-{num}"
            if ref not in out and _held(exists, ref):
                out.add(ref)
    return out
