"""Row 1306 C4 wiring: read what a connector run did from the command's stream output and put every tool call and every tool result
through ask_connector_screen. Pure functions, standard library only.

A run that used a connector writes one JSON event per line (`--output-format stream-json`). Each tool the model called is a `tool_use`
block (id, name); each result is a `tool_result` block (tool_use_id, content). `checked(out, on_parts)` returns (ok, used_line_text,
final_result_bytes): ok only when every tool called is on the read-only allow-list of a part that is On, and every result is plain text
with no hidden character and inside the size caps. When not ok nothing of the run is shown. The final `result` event is what the caller
reads the answer from.
"""
import json

from clark import ask_connector_screen as screen


def _events(out):
    try:
        text = out.decode("utf-8")
    except (UnicodeDecodeError, AttributeError):
        return []
    found = []
    for line in text.splitlines():
        try:
            x = json.loads(line)
        except (ValueError, RecursionError):
            continue
        if isinstance(x, dict):
            found.append(x)
    return found


def _blocks(event):
    message = event.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    return [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []


def _text(content):
    """The result's text: a string, or a list of text blocks joined; anything else is None (not plain text, so not used)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list) and content and all(isinstance(b, dict) and b.get("type") == "text" and isinstance(b.get("text"), str)
                                                     for b in content):
        return "\n".join(b["text"] for b in content)
    return None


def _prefixed(name):
    return isinstance(name, str) and name.startswith("mcp__")


SEARCH_TOOL = "ToolSearch"       # the one built-in a connector run keeps: it loads the allowed connector tool (probe on a real Mac)


def _allowed_full(on_parts):
    return {f"{screen.SERVER_PREFIX[p]}__{t}" for p in screen.PARTS if on_parts is None or p in on_parts for t in screen.ALLOWED_TOOLS[p]}


def _names(items, key):
    """The tool names of a list of exact reference blocks (`items` a list of dicts with exactly the keys `key`), or None when the shape is anything else."""
    if not isinstance(items, list) or not items:
        return None
    out = []
    for x in items:
        if key == "ref":
            if not (isinstance(x, dict) and set(x) == {"type", "tool_name"} and x["type"] == "tool_reference" and isinstance(x["tool_name"], str)):
                return None
            out.append(x["tool_name"])
        else:
            if not isinstance(x, str):
                return None
            out.append(x)
    return out


def search_result_ok(content, use_result, on_parts):
    """The shape of a real ToolSearch result (probe on a real machine): ONE tool_reference block per tool found, content = exactly
    [{"type": "tool_reference", "tool_name": <name>}], and the event's tool_use_result = {"matches": [<name>], "total_deferred_tools": <int>}. ok only when every
    name is an allowed connector tool of a part that is On, the content is that exact shape (never text, never an extra block or key), and the matches, when
    the event carries them, are exactly the same names."""
    allowed = _allowed_full(on_parts)
    named = _names(content, "ref")
    if named is None or not all(n in allowed for n in named):
        return False
    if use_result is not None:
        if not isinstance(use_result, dict) or not set(use_result) <= {"matches", "total_deferred_tools"} or "matches" not in use_result:
            return False
        total = use_result.get("total_deferred_tools", 0)
        if not isinstance(total, int) or isinstance(total, bool) or total < 0:
            return False
        matches = _names(use_result["matches"], "name")
        if matches is None or sorted(matches) != sorted(named):
            return False
    return True


def search_ok(args, on_parts):
    """True for a ToolSearch call that only asks for an allowed connector tool of a part that is On: `select:<name>[,<name>...]` with every name an
    allowed tool (full mcp__ name or the bare tool name), or a query that names one allowed tool. Anything else is not ok."""
    query = args.get("query") if isinstance(args, dict) else None
    if not isinstance(query, str) or not query.strip() or len(query) > 500:
        return False
    full = _allowed_full(on_parts)
    bare = {n.split("__", 2)[2] for n in full}
    q = query
    if q != q.strip() or not all(32 <= ord(c) < 127 for c in q):
        return False
    if q.startswith("select:"):
        names = [n.strip() for n in q[len("select:"):].split(",")]
        return bool(names) and all(n in full or n in bare for n in names)
    return q in full or q in bare        # the whole query is one allowed tool name, nothing else


def init_problem(out):
    """"" when the stream has no init event or its tool list is exactly [ToolSearch] (the allow-list form: probe on a real machine); "absent" when the list lacks
    ToolSearch (the connector tool can not load); "extra" when ANY other tool is in it (a tool clark did not allow reached the run)."""
    problem = ""
    for ev in _events(out):
        if ev.get("type") == "system" and ev.get("subtype") == "init" and isinstance(ev.get("tools"), list):
            tools = ev["tools"]
            if any(t != SEARCH_TOOL for t in tools):
                return "extra"
            if tools != [SEARCH_TOOL]:
                problem = "absent"
    return problem


def checked(out, on_parts):
    """(ok, used_line_text, result_bytes or None) for one connector run's stream output."""
    ok, line, result = inspect(out, on_parts)
    return ok, line.text, result


def inspect(out, on_parts):
    """(ok, UsedLine, result_bytes or None): the same as `checked`, with the whole UsedLine (its used and not_used parts) kept."""
    names, pairs, calls, searches = {}, [], [], set()
    bad = False
    missing = False
    result = None
    for ev in _events(out):
        kind = ev.get("type")
        if kind == "system" and ev.get("subtype") == "init":
            if init_problem(out):
                missing = True                     # the run does not have exactly the one allowed built-in
        if kind == "result":
            result = ev
        elif kind == "assistant":
            for b in _blocks(ev):
                if b.get("type") == "tool_use":
                    name = b.get("name")
                    ident = b.get("id")
                    if not isinstance(ident, str) or not ident or ident in names or ident in searches:
                        bad = True                         # no id, or an id used twice: the results could not be told apart
                    if name == SEARCH_TOOL and search_ok(b.get("input"), on_parts):
                        searches.add(ident)                # loads the allowed tool; its result must be the exact tool_reference shape
                        continue
                    names[b.get("id")] = name
                    calls.append(name)
        elif kind == "user":
            for b in _blocks(ev):
                if b.get("type") == "tool_result" and b.get("tool_use_id") in searches:
                    if not search_result_ok(b.get("content"), ev.get("tool_use_result"), on_parts):
                        bad = True                     # a search result is only ever the tool_reference shape of an allowed tool
                elif b.get("type") == "tool_result":
                    pairs.append((names.get(b.get("tool_use_id")), _text(b.get("content"))))
    # The real stream names every tool mcp__<server>__<tool>: a bare name is never one of ours, so it is refused here (the screen alone accepts a
    # bare name by its name, which only its own plain tests use).
    pairs = [(n if _prefixed(n) else "", t) for n, t in pairs]
    calls = [n if _prefixed(n) else "" for n in calls]
    verdicts = screen.screen_all(pairs, on_parts)
    verdicts += [screen.screen(name, "", 0, on_parts) for name in calls if name not in {p[0] for p in pairs}]
    line = screen.used_line(verdicts)
    if missing:
        return False, line, None
    if bad or result is None or not all(v.used for v in verdicts):
        return False, line, None
    return True, line, json.dumps(result).encode("utf-8")
