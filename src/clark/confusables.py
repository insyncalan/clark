"""clark copy (#47b) of creaite v2.6.9 confusables.py (not guarded; only the `import paths` line is cut and edit_ai is imported
from clark). v2.5.1 (#239): the confusables skeleton every restricted-text scan reads text through. Standard library only; a library.

skeleton(text): NFKC (fullwidth forms, mathematical alphanumerics, ligatures and the other compatibility characters become the
letters they are), the characters Word and a browser draw as nothing gone (edit_ai.unseen: zero-width and format characters,
default-ignorables, controls), combining marks gone (edit_ai.unmarked), then each letter that looks like a Latin one (TABLE: Cyrillic,
Greek, Armenian, Lisu, Cherokee, small capitals, and a few Latin look-alikes) made that Latin letter, and NFKC once more. Both sides
of a match go through it (the text and the needle), so a name or wording in those scripts still matches itself.

edit_ai.LOOK_ALIKE is built from TABLE, so edit_ai.normal (which client_leak's checks call) reads text the same way.
"""
import unicodedata

# Look-alikes by script, as (characters, the Latin letters they look like), one for one. Kept to letters a reader takes for the
# Latin one at a glance in the fonts Word and Chrome use.
_PAIRS = (
    # Cyrillic capitals, then small letters
    ("\u0410\u0412\u0415\u041a\u041c\u041d\u041e\u0420\u0421\u0422\u0425\u0405\u0406\u0408\u04c0\u0474\u051a\u051c\u04ae",
     "ABEKMHOPCTXSIJIVQWY"),
    ("\u0430\u0435\u043e\u0440\u0441\u0443\u0445\u0455\u0456\u0458\u0501\u04bb\u0475\u051b\u051d\u0461\u043a",
     "aeopcyxsijdhvqwwk"),
    # Greek capitals, then small letters
    ("\u0391\u0392\u0395\u0396\u0397\u0399\u039a\u039c\u039d\u039f\u03a1\u03a4\u03a5\u03a7\u03f9\u037f",
     "ABEZHIKMNOPTYXCJ"),
    ("\u03b1\u03bf\u03c1\u03bd\u03b9\u03ba\u03c5\u03c7\u03f2\u03f3",
     "aopvikuxcj"),
    # Armenian
    ("\u0585\u0578\u057d\u0581\u0566\u0570\u0575\u0555\u054d",
     "onugqhjOU"),
    # Lisu (the letters that are Latin capitals in shape)
    ("\ua4ee\ua4d0\ua4d1\ua4d3\ua4d4\ua4d6\ua4d7\ua4d9\ua4da\ua4dc\ua4dd\ua4df\ua4e0\ua4e1\ua4e2\ua4e3\ua4e6\ua4e7"
     "\ua4ea\ua4eb\ua4ec\ua4f0\ua4f2\ua4f3\ua4f4",
     "ABPDTGKJCZFMNLSRVHWXYEIOU"),
    # Cherokee
    ("\u13aa\u13f4\u13df\u13a0\u13ac\u13bb\u13c0\u13ab\u13e6\u13b7\u13e2\u13d2\u13da\u13a2\u13d9\u13b3\u13c3\u13de",
     "ABCDEHGJKMPRSTVWZL"),
    # Small capitals (Latin extensions), which NFKC leaves alone
    ("\u1d00\u0299\u1d04\u1d05\u1d07\ua730\u0262\u029c\u026a\u1d0a\u1d0b\u029f\u1d0d\u0274\u1d0f\u1d18\u0280\ua731\u1d1b"
     "\u1d1c\u1d20\u1d21\u028f\u1d22",
     "ABCDEFGHIJKLMNOPRSTUVWYZ"),
    # Latin look-alikes and dotless letters
    ("\u0131\u0237\u01c0\u0269\u0251\u0261\u01bf",
     "ijlIagp"),
)


def _table():
    """{code point: Latin letter} from _PAIRS (the first pair naming a character wins)."""
    out = {}
    for chars, latin in _PAIRS:
        if len(chars) != len(latin):
            raise ValueError(f"confusables: {latin!r} doesn't pair one for one")
        for c, x in zip(chars, latin):
            out.setdefault(ord(c), x)
    return out


TABLE = _table()
DASHES = "‐‑‒–—―−﹘﹣－"


def skeleton(text):
    """The text as every restricted-text scan reads it (see the module's description). Never raises on a string."""
    from clark import edit_ai
    t = edit_ai.unseen(str(text or "")).translate(TABLE)        # first too: NFKD and NFKC make a look-alike (Ϲ) another letter (Σ)
    t = unicodedata.normalize("NFKC", edit_ai.unmarked(t).translate(TABLE))
    t = edit_ai.unseen(t).translate(TABLE).translate({ord(c): "-" for c in DASHES})
    return unicodedata.normalize("NFKC", t)
