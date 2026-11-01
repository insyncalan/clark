"""ask: a plain-code screen for secrets in text read from a saved folder (#215). No model, no file, no network, no logging.
Standard library only.

ONE LIST. The key shapes are the publish scan's own (`dev/tools/publish_public.py`, SECRET_PATTERNS and BASE64_RUN), written here as
text because that tool is a development tool that is not shipped; a test compares the two lists, so they cannot drift apart. The
key-word lines are this screen's own, wider than the publish scan's (a prefix such as DB_, a closing quote, short quoted values,
table cells, CSV and TSV columns) and bounded in time. Text is read as it is and as the client check sees it (hidden characters and
look-alike letters undone).

THE SAFE CHOICE. If any of it matches, the WHOLE file is left out, never part of it. The caller counts it and names its label
and the reason; the matched text is not kept, not returned and not put in an error. The file is read two ways (as it is and
with line breaks taken out), so a secret that a line break or a Word run cut in two is
still caught. The cost is fixed by the size: every pattern is a single pass with no nested repeats, and base64 runs are
looked at up to a cap, past which the file counts as a hit (fail closed). A base64 run is decoded and read for the key shapes and,
when it decodes to plain text, for the key-word lines too; text with %-escapes is also read with them undone.

NOT SCREENED, on purpose (#257, #374): a password word followed by plain words ("password: see below"; the other languages act the same);
the file name "secret_santa2025.xlsx" (only that whole name, with any 4-digit year); text escaped three times; a token cut by a space ("token: ab12cd34 ef56gh78"), since joining words across a space would
leave out every file that says "token: 2026 plan"; a secret of fewer than 8 characters after secret or a key name; a key-word line
whose base64 form is shorter than 24 characters.
"""
import base64
import re
import urllib.parse

from clark import ask, edit_ai

REASON = "looks like it holds a secret"
NEXT_STEP = "Remove the secret from the file or move it out of the saved folder."
MAX_RUNS = 20000                     # different base64-looking runs looked at in one file; more than this counts as a hit
MAX_ROWS = 400                       # rows under a table header looked at for a secret column
MAX_HEADER = 2000                    # characters: a longer line is not read as a table header

SECRET_PATTERNS = (
    ("a private key", r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP |ENCRYPTED )?PRIVATE KEY"),
    ("a GitHub token", r"\b(?:gh[pousr]_[A-Za-z0-9]{16,}|github_pat_[A-Za-z0-9_]{16,})"),
    ("an AWS access key", r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    ("a Slack token", r"\bxox[baprs]-[A-Za-z0-9-]{8,}"),
    ("a JSON web token", r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),
    ("an Anthropic or OpenAI key", r"\bsk-(?:ant-|proj-|svcacct-|admin-)[A-Za-z0-9_-]{8,}|\bsk-[A-Za-z0-9]{32,}"),
    ("a Stripe live key", r"\b[sr]k_live_[A-Za-z0-9]{8,}"),
    ("a Google API key", r"\bAIza[0-9A-Za-z_-]{30,}"),
    ("an npm token", r"\bnpm_[A-Za-z0-9]{20,}|_authToken\s*=\s*[A-Za-z0-9][^\s$\x22']{15,}"),
    ("a PyPI token", r"\bpypi-[A-Za-z0-9_-]{20,}"),
    ("a password in an address", r"[A-Za-z][A-Za-z0-9+.-]*://[^/\s:@]+:[^/\s@]+@[^/\s]"),
    ("an authorization header", r"(?i)authorization\s*[:=]\s*[\x22']?(?:bearer|basic|token)\s+[A-Za-z0-9._~+/=-]{8,}"),
)
GENERIC_SECRET = r"""(?i)(?:api[_-]?key|secret|token|passw(?:or)?d|pwd)["']?\s*[:=]\s*["']([^"'\s]{16,})["']"""
UNQUOTED_SECRET = r"""(?i)(?:api[_-]?key|secret|token|(passw(?:or)?d|pwd))\w*["']?[ \t]*[:=][ \t]*([^\s"'`$<>{}()\[\],;]{8,})"""
# The same ideas, written for this screen (#215 review): a prefix such as DB_ before the key word and a closing quote after it
# are allowed, a quoted value needs only 8 characters, a table cell or a comma, tab or bar between the word and its value counts,
# and every gap is bounded so a long run of key words takes a time that grows with the size, not with its square.
# Password in other languages (#257): German, French, Spanish, Portuguese, Dutch, Swedish, Polish, Italian, Russian and Arabic.
_PW_OTHER = (r"passwort|kennwort|mot[ \t]?de[ \t]?passe|motdepasse|contrase(?:ñ|nn?)a|senha|wachtwoord|l(?:ö|o)senord|has(?:ł|l)o|"
             r"parola[ \t]?d'ordine|пароль|كلمة[ \t]?(?:المرور|السر)")
_PW = r"(?:passw(?:or)?d|pwd|passcode|" + _PW_OTHER + r"|(?<![A-Za-z])(?:pass|pw|pin|creds|credentials)(?![A-Za-z]))"
_KEY = r"(?:api[_-]?key|access[_-]?key|ssh[_-]?private[_-]?key|secret|token|" + _PW + r")"
QUOTED_LOCAL = r"""(?i)""" + _KEY + r"""\w{0,40}["']?\s{0,20}[:=]\s{0,20}["']([^"'\s]{8,})["']"""
UNQUOTED_LOCAL = (r"""(?i)(?:api[_-]?key|access[_-]?key|ssh[_-]?private[_-]?key|token|(secret|""" + _PW + r"""))\w{0,40}["']?[ \t]{0,20}[:=][ \t]{0,20}"""
                  r"""([^\s"'`$<>{}()\[\],;]{8,})""")
CELL_LOCAL = r"""(?i)""" + _KEY + r"""\w{0,40}["']?[ \t]{0,20}:?[ \t]{0,20}[|\t,][ \t]{0,20}["']?([^\s|,;"'`$<>{}()\[\]]{8,})"""
SHORT_PASSWORD = r"""(?i)(?<!\w)(?:passw(?:or)?d|pwd|passcode|""" + _PW_OTHER + r""")(?!\w)["']?[ \t]{0,20}[:=][ \t]{0,20}["']?(\S{4,})"""
HEADER_WORDS = re.compile(r"(?i)^(?:api[ _-]?key|access[ _-]?key|ssh[ _-]?private[ _-]?key|secret|token|passw(?:or)?d|pwd|passcode|pass|pw|pin|creds|credentials|"
                          + _PW_OTHER + r")\w{0,20}$")
# A passphrase with spaces, in matching quotes (the password family only), and a password written as prose ("the wifi password is
# Sunshine2026"): a key word, is or was, then a mixed value of 8 or more characters.
QUOTED_PHRASE = r"""(?i)""" + _PW + r"""\w{0,40}["']?[ \t]{0,20}[:=][ \t]{0,20}(?:"([^"\n]{8,80})"|'([^'\n]{8,80})')"""
PROSE_SECRET = r"""(?i)(?:\b(?:passw(?:or)?d|pwd|passcode|pass|pw|pin|creds|credentials|secret)\b)["']?[ \t]{1,3}(?:is|was)[ \t]{1,3}["'(]?([^\s"'`$<>{}()\[\],;]{8,})"""
# A file's name: a key word, then - _ . or a space and a mixed value of 8 or more characters ("notes-password-Hunter2xyz9.txt").
NAME_SECRET = r"""(?i)""" + _KEY + r"""[-_. ]([A-Za-z0-9]{8,})"""
# The one ordinary name taken out before a file name is screened (#374): "secret_santa" (with an optional 4-digit year) as the whole
# name or the whole name before its extension, so "secret_santa2025.xlsx" is a file name; "secret_santa_key=..." is still read.
_SANTA = re.compile(r"(?<![^/])secret_santa(?:\d{4})?(?=\.[A-Za-z0-9]{1,5}$|$)")
# Known gaps, kept as Tech Debt: a secret of letters only ("correcthorsebattery") and a bare 40-character hex string with no key
# word are not caught; guessing them would drop too many ordinary files.
BASE64_RUN = r"[A-Za-z0-9+/_-]{24,}"

# The publish scan's address shape starts at every letter and can take a long time on a long run of letters, so here it starts at
# the "://" instead (the same addresses are found).
ADDRESS_KIND = "a password in an address"
ADDRESS_LINEAR = r"[A-Za-z0-9+.-]://[^/\s:@]+:[^/\s@]+@[^/\s]"
_SHAPES = tuple(re.compile(ADDRESS_LINEAR if k == ADDRESS_KIND else p) for k, p in SECRET_PATTERNS)
_QUOTED = re.compile(QUOTED_LOCAL)
_UNQUOTED = re.compile(UNQUOTED_LOCAL)
_CELL = re.compile(CELL_LOCAL)
_PHRASE = re.compile(QUOTED_PHRASE)
_PROSE = re.compile(PROSE_SECRET)
_SHORT = re.compile(SHORT_PASSWORD)
_NAME = re.compile(NAME_SECRET)
_RUN = re.compile(BASE64_RUN)
_BYTE_SHAPES = tuple(re.compile((ADDRESS_LINEAR if k == ADDRESS_KIND else p).encode("ascii")) for k, p in SECRET_PATTERNS)
_BREAKS = re.compile(r"[\r\n]+")


def _mixed(value):
    return bool(re.search(r"[0-9]", value) and re.search(r"[A-Za-z]", value))


def _plain(raw):
    """Decoded base64 as text, or None when it is mostly not printable (a picture, a compressed file); the replacement
    character counts as printable, so mostly-text data with a few bad bytes is still read."""
    text = raw.decode("utf-8", "replace")
    return text if sum(c.isprintable() or c in "\r\n\t" for c in text) >= len(text) * 0.9 else None


def _in_base64(text):
    seen = set()
    for m in _RUN.finditer(text):
        if m.group() in seen:
            continue
        seen.add(m.group())
        if len(seen) > MAX_RUNS:
            return True                                   # too many different ones to look at: leave the file out
        run = m.group().replace("-", "+").replace("_", "/")
        for offset in range(4):
            chunk = run[offset:]
            chunk = chunk[:len(chunk) - len(chunk) % 4]
            if len(chunk) < 24:
                continue
            try:
                plain = base64.b64decode(chunk)
            except ValueError:
                continue
            if any(rx.search(plain) for rx in _BYTE_SHAPES):
                return True
            words = _plain(plain)
            if words is not None and _key_words(words):
                return True
    return False


def _columns(text):
    """A table (Word cells joined by " | ", CSV, TSV) whose header names a secret: the cells under it are the secret."""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if len(line) > MAX_HEADER:
            continue
        for sep in ("|", "\t", ","):
            if sep not in line:
                continue
            cells = [c.strip(" \t\r\"'`") for c in line.split(sep)]
            for col, cell in enumerate(cells):
                if not HEADER_WORDS.match(cell):
                    continue
                for row in lines[i + 1:i + 1 + MAX_ROWS]:
                    if len(row) > MAX_HEADER:
                        continue
                    parts = [c.strip(" \t\r\"'`") for c in row.split(sep)]
                    if col < len(parts) and len(parts[col]) >= 8 and _mixed(parts[col]) and " " not in parts[col]:
                        return True
    return False


def _loose(text):
    """The long-run guess, narrower than the question screen's (that one is for a short question; here a hit drops a whole file):
    a long mixed run with the look of a random key (the class of character changes often), not a word-joined name, not an
    address's path, not inside a picture's data address (the base64 look is decoded and read separately)."""
    for m in re.finditer(r"[A-Za-z0-9+/_=-]{32,}", text):
        run = m.group()
        if not (re.search(r"[a-z]", run) and re.search(r"[A-Z]", run) and re.search(r"\d", run)) or ask._words_joined(run):
            continue
        before = text[max(0, m.start() - 200):m.start()].rsplit(None, 1)
        word = before[-1] if before else ""
        if "://" in word or word.startswith("data:") or "base64," in word:
            continue
        kind = [("l" if c.islower() else "u" if c.isupper() else "d" if c.isdigit() else "o") for c in run]
        if sum(1 for x, y in zip(kind, kind[1:]) if x != y) >= len(run) // 2:
            return True
    for m in _SHORT.finditer(text):
        value = m.group(1).strip(".,;)'\"")
        if any(not c.isalpha() for c in value):
            return True
    return False


def _key_words(text):
    for m in _QUOTED.finditer(text):
        if _mixed(m.group(1)):
            return True
    for m in _UNQUOTED.finditer(text):
        if len(m.group(2)) >= (8 if m.group(1) else 16) and _mixed(m.group(2)):
            return True
    for m in _CELL.finditer(text):
        if _mixed(m.group(1)):
            return True
    for m in _PHRASE.finditer(text):
        if _mixed(m.group(1) or m.group(2)):
            return True
    for m in _PROSE.finditer(text):
        if _mixed(m.group(1).rstrip(".!?:")):
            return True
    return False


def _one(text):
    if any(rx.search(text) for rx in _SHAPES):
        return True
    return _key_words(text) or _in_base64(text) or _loose(text) or _columns(text)


def looks_like_secret(text):
    """Whether `text` looks like it holds a secret. Never raises, never keeps or returns what matched; text that cannot be
    read as a string counts as a hit. Read as it is, as the client check sees it (hidden characters and look-alike letters
    undone) and with line breaks taken out of each."""
    if not isinstance(text, str):
        return True
    try:
        seen = [text, edit_ai.normal(text)]
        for _ in range(2):                                # %-escapes undone up to twice ("%253D"), each result read as it is and normalised
            if any("%" in t for t in seen):
                seen += [x for t in list(seen) if "%" in t for x in (urllib.parse.unquote_plus(t), edit_ai.normal(urllib.parse.unquote_plus(t)))]
        for t in dict.fromkeys(seen):
            if _one(t) or _one(_BREAKS.sub("", t)):
                return True
        return False
    except (RecursionError, MemoryError, ValueError):
        return True                                       # fail closed


def name_looks_like_secret(name):
    """Whether a file's name looks like it holds a secret: the text screen, plus a key word joined to its value by - or _."""
    if not isinstance(name, str):
        return True
    name = _SANTA.sub("santa", name)
    return looks_like_secret(name) or any(_mixed(m.group(1)) for m in _NAME.finditer(name))
