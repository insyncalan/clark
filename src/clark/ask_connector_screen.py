"""Row 1306 slice C4: the screen for what a connector returns to ask clark. Pure functions, injected inputs, standard library only.
No store, no files, no network, and ask_claude.py is not touched.

ALLOWED_TOOLS: the exact allow-list of read-only connector tools, by connector part. Any other tool name is refused (`tool_allowed`).
screen(result): every tool result goes through this before use. A result with a hidden or invisible character (zero-width, bidi
control, tag character, any other Cf or control character except newline and tab) is REFUSED, not stripped, and counts as "not used".
A result over MAX_RESULT characters is refused; once MAX_TOTAL is used up, further results are refused. Nothing is rewritten.
used_line(): names what was used and what was not, and keeps no connector content. Provenance: `mark(text)` returns a Sourced value
that carries the flag `from_connector`, so a text that came from a connector can be told apart wherever it travels.
"""
import json
import unicodedata
from dataclasses import dataclass, field

MAX_RESULT = 40000
MAX_TOTAL = 70000

# connector part -> the read-only tool names allowed for it. Nothing that sends, replies, deletes, moves, creates or updates.
ALLOWED_TOOLS = {
    "Mail": frozenset(("outlook_email_search",)),
    "Calendar": frozenset(("outlook_calendar_search", "outlook_find_available_time", "find_meeting_availability")),
    "Teams": frozenset(("chat_message_search", "teams_list_teams", "teams_list_channels", "teams_list_channel_messages",
                        "teams_list_chats")),
    "SharePoint and OneDrive": frozenset(("sharepoint_search", "sharepoint_folder_search", "read_resource")),
    "Todoist": frozenset(("find-tasks", "find-tasks-by-date", "find-projects", "find-sections", "find-comments",
                          "find-completed-tasks", "fetch-object", "get-overview")),
}
PARTS = tuple(ALLOWED_TOOLS)

OK, REFUSED_HIDDEN, REFUSED_SIZE, REFUSED_TOTAL, REFUSED_TOOL, REFUSED_OFF = (
    "ok", "hidden characters", "too long", "over the total", "tool not allowed", "connector is off")

_KEEP = frozenset("\n\t")


def part_of_tool(tool):
    """The connector part a tool name belongs to (an exact match, a prefix like mcp__server__ is dropped), or None."""
    if not isinstance(tool, str):
        return None
    name = tool.rsplit("__", 1)[-1]
    for part, names in ALLOWED_TOOLS.items():
        if name in names:
            return part
    return None


def tool_allowed(tool, on_parts=None):
    """True only for a tool on the allow-list; with `on_parts` (the parts turned On) its part must be among them."""
    part = part_of_tool(tool)
    return part is not None and (on_parts is None or part in on_parts)


def hidden_count(text):
    """How many hidden or invisible characters `text` holds: Cc, Cf, Cs, Co, Cn, Zl, Zp except newline and tab (this covers
    zero-width, bidi controls and tag characters)."""
    return sum(1 for ch in text if ch not in _KEEP and unicodedata.category(ch) in ("Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp"))


@dataclass(frozen=True)
class Screened:
    """The verdict on one result. `text` is the result itself when used, else "" (a refused result is never carried on)."""
    tool: str
    part: object
    used: bool
    reason: str
    size: int
    text: str = ""


@dataclass(frozen=True)
class Sourced:
    """Text that came from a connector. `from_connector` is always True: untrusted data, never instructions."""
    text: str
    part: str
    from_connector: bool = True


def mark(text, part):
    return Sourced(text=text, part=part)


def is_from_connector(value):
    return bool(getattr(value, "from_connector", False))


def screen(tool, result, total_so_far=0, on_parts=None):
    """Screen one tool result before use. Returns Screened. Refused (never stripped) when the tool is not on the allow-list or its
    part is Off, the result is not text, holds a hidden character, is over MAX_RESULT, or would take the total over MAX_TOTAL."""
    part = part_of_tool(tool)
    name = str(tool)
    if part is None:
        return Screened(name, None, False, REFUSED_TOOL, 0)
    if on_parts is not None and part not in on_parts:
        return Screened(name, part, False, REFUSED_OFF, 0)
    if not isinstance(result, str):
        return Screened(name, part, False, REFUSED_HIDDEN, 0)     # not plain text: not used
    size = len(result)
    if hidden_count(result):
        return Screened(name, part, False, REFUSED_HIDDEN, size)
    if size > MAX_RESULT:
        return Screened(name, part, False, REFUSED_SIZE, size)
    if total_so_far + size > MAX_TOTAL:
        return Screened(name, part, False, REFUSED_TOTAL, size)
    return Screened(name, part, True, OK, size, result)


def screen_all(results, on_parts=None):
    """Screen (tool, result) pairs in order, carrying the running total of what was used. Returns a list of Screened."""
    out, total = [], 0
    for tool, result in results:
        s = screen(tool, result, total, on_parts)
        if s.used:
            total += s.size
        out.append(s)
    return out


@dataclass(frozen=True)
class UsedLine:
    used: tuple = ()
    not_used: tuple = ()
    text: str = field(default="")


# The words the person reads (approved word for word): part -> (what the line calls it, one, many). `read` is "Read your <what>".
SHOWN = {
    "Mail": ("Mail", "mail", "message", "messages"),
    "Calendar": ("Calendar", "calendar", "event", "events"),
    "Teams": ("Teams chats", "Teams chats", "message", "messages"),
    "SharePoint and OneDrive": ("Files", "files", "file", "files"),
    "Todoist": ("Tasks", "tasks", "task", "tasks"),
}
REASON_WORDS = {
    REFUSED_HIDDEN: "has hidden characters", REFUSED_SIZE: "was too long", REFUSED_TOTAL: "was over the total",
    REFUSED_TOOL: "is not allowed", REFUSED_OFF: "is off",
}


def count_of(text):
    """How many things a result lists, only when the answer is a countable list: a JSON list, or a JSON object holding exactly one
    list. Anything else (plain text, no list, more than one list) is not countable: None."""
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return None
    if isinstance(data, dict):
        lists = [v for v in data.values() if isinstance(v, list)]
        data = lists[0] if len(lists) == 1 else None
    return len(data) if isinstance(data, list) else None


def used_line(screened):
    """The Used line from Screened verdicts: 'Used: Read your mail (3 messages)' (the count only when the answer is a countable list)
    and 'Not used: Mail was too long'. Names and counts only; no connector content or tool arguments. A refusal that belongs to no
    connector part (a tool not on the list) is in `not_used` as data but is not worded in the line."""
    counts, skipped, data_skipped = {}, [], []
    for s in screened:
        if s.used:
            n = count_of(s.text)
            if s.part in counts:
                prev = counts[s.part]
                counts[s.part] = None if prev is None or n is None else prev + n
            else:
                counts[s.part] = n
        elif s.part in SHOWN:
            item = f"{SHOWN[s.part][0]} {REASON_WORDS[s.reason]}"
            if item not in skipped:
                skipped.append(item)
            if item not in data_skipped:
                data_skipped.append(item)
        else:
            item = f"unknown connector ({s.reason})"
            if item not in data_skipped:
                data_skipped.append(item)
    read = []
    for part, n in counts.items():
        _, what, one, many = SHOWN.get(part, (part, part, "", ""))
        read.append(f"Read your {what}" + ("" if n is None else f" ({n} {one if n == 1 else many})"))
    parts = []
    if read:
        parts.append("Used: " + ", ".join(read))
    if skipped:
        parts.append("Not used: " + ", ".join(skipped))
    return UsedLine(tuple(counts), tuple(data_skipped), ". ".join(parts))
