"""Usage in tokens (row 1294, A8): how many questions asking answered this month and how many tokens they used, for each project.

Kept in one small file beside the data (`ask_usage.json`), on this computer only: a month key ("2026-11") holds, per project code, the questions
answered, the tokens the command reported for them and how many of those answers came with no count ("unreported"). Tokens only. A month other than the current one is never shown and is dropped
the next time a question is recorded. The command's own result object carries `usage` (input, cache and output tokens); a question the command
gave no readable count for is still counted as a question, with no tokens added and one more unreported. A file written before
"unreported" existed has none: a row with questions and no tokens reads as all unreported (nothing reported a count), any other row as all reported. Nothing here is sent anywhere; no question or answer text is kept.
"""
import json
import os
import re
import threading
from pathlib import Path

FILE = "ask_usage.json"
PROJECT_CODE = re.compile(r"[A-Z][A-Z0-9]{2,6}")
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")
MAX_COUNT = 10 ** 12                 # a count past this is taken as damaged and read as nothing

GROUP = "Usage, {first} to {last} {month} {year}"
ASKING_ON = "Asking is on"
ASKING_OFF = "Asking is off"
ALL_ROW = "All projects"
ALL_NOTE = "Tokens used"
READ_ONLY = "Read only. Nothing here leaves this computer."
THIS_MONTH = "Usage this month"
NO_QUESTIONS = "No questions: asking is off."


def month_key(day):
    return f"{day.year:04d}-{day.month:02d}"


def group_title(day):
    """The group's heading for the month so far: the 1st to today, in words ("Usage, 1 to 20 November 2026")."""
    return GROUP.format(first=1, last=day.day, month=MONTHS[day.month - 1], year=day.year)


def count_line(questions, tokens, unreported=0):
    """"<n> questions · <t> tokens" when every answer reported a count; "<n> questions · tokens not reported" when none did; else
    "<n> questions · <t> tokens, some not reported"."""
    if not unreported:
        return f"{questions_words(questions)} · {tokens_words(tokens)}"
    if unreported >= questions:
        return f"{questions_words(questions)} · tokens not reported"
    return f"{questions_words(questions)} · {tokens_words(tokens)}, some not reported"


def tokens_words(n):
    return f"{n} token" if n == 1 else f"{n} tokens"


def questions_words(n):
    return f"{n} question" if n == 1 else f"{n} questions"


def tokens_in(usage):
    """The tokens one run used, from the `usage` object of the command's result: input, cache-written, cache-read and output tokens added. None
    when it is not an object with whole, non-negative input and output counts (nothing is guessed)."""
    if not isinstance(usage, dict):
        return None
    total = 0
    for name, needed in (("input_tokens", True), ("cache_creation_input_tokens", False), ("cache_read_input_tokens", False), ("output_tokens", True)):
        n = usage.get(name)
        if n is None and not needed:
            continue
        if isinstance(n, bool) or not isinstance(n, int) or not 0 <= n <= MAX_COUNT:
            return None
        total += n
    return total


def whole(n):
    return n if isinstance(n, int) and not isinstance(n, bool) and 0 <= n <= MAX_COUNT else 0


def row_of(r):
    questions, tokens = whole(r.get("questions")), whole(r.get("tokens"))
    if "unreported" in r:
        unreported = min(whole(r["unreported"]), questions)
    else:                                  # a file from before this count: no tokens at all means none was reported
        unreported = questions if tokens == 0 else 0
    return {"questions": questions, "tokens": tokens, "unreported": unreported}


class AskUsage:
    def __init__(self, data_dir):
        self.path = Path(data_dir) / FILE
        self.lock = threading.Lock()

    def load(self):
        try:
            got = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {}
        return got if isinstance(got, dict) else {}

    def month(self, day):
        """{code: {"questions": n, "tokens": n, "unreported": n}} for the month of `day`; empty when nothing is kept or the file can't be read."""
        rows = self.load().get(month_key(day))
        if not isinstance(rows, dict):
            return {}
        return {c: row_of(r) for c, r in rows.items() if isinstance(c, str) and PROJECT_CODE.fullmatch(c) and isinstance(r, dict)}

    def record(self, code, tokens, day):
        """Count one answered question of `code`, with `tokens` (None: none reported). True when it was kept; it never raises: a file that
        can't be written loses the count, not the answer."""
        if not isinstance(code, str) or not PROJECT_CODE.fullmatch(code):
            return False
        with self.lock:
            rows = self.month(day)
            row = rows.setdefault(code, {"questions": 0, "tokens": 0, "unreported": 0})
            row["questions"] += 1
            row["tokens"] += whole(tokens)
            row["unreported"] += tokens is None
            tmp = self.path.with_name(self.path.name + ".tmp")
            try:
                tmp.write_text(json.dumps({month_key(day): rows}, sort_keys=True), encoding="utf-8")
                os.replace(tmp, self.path)
            except OSError:
                return False
        return True
