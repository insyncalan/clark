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


def search_ok(args, on_parts):
    """True for a ToolSearch call that only asks for an allowed connector tool of a part that is On: `select:<name>[,<name>...]` with every name an
    allowed tool (full mcp__ name or the bare tool name), or a query that names one allowed tool. Anything else is not ok."""
    query = args.get("query") if isinstance(args, dict) else None
    if not isinstance(query, str) or not query.strip() or len(query) > 500:
        return False
    full = {f"{screen.SERVER_PREFIX[p]}__{t}" for p in screen.PARTS if on_parts is None or p in on_parts for t in screen.ALLOWED_TOOLS[p]}
    bare = {n.split("__", 2)[2] for n in full}
    q = query.strip()
    if q.startswith("select:"):
        names = [n.strip() for n in q[len("select:"):].split(",")]
        return bool(names) and all(n in full or n in bare for n in names)
    return any(n in q for n in full | bare)


def checked(out, on_parts):
    """(ok, used_line_text, result_bytes or None) for one connector run's stream output."""
    names, pairs, calls, searches = {}, [], [], set()
    result = None
    for ev in _events(out):
        kind = ev.get("type")
        if kind == "result":
            result = ev
        elif kind == "assistant":
            for b in _blocks(ev):
                if b.get("type") == "tool_use":
                    name = b.get("name")
                    if name == SEARCH_TOOL and search_ok(b.get("input"), on_parts):
                        searches.add(b.get("id"))          # loads the allowed tool; carries no connector content
                        continue
                    names[b.get("id")] = name
                    calls.append(name)
        elif kind == "user":
            for b in _blocks(ev):
                if b.get("type") == "tool_result" and b.get("tool_use_id") not in searches:
                    pairs.append((names.get(b.get("tool_use_id")), _text(b.get("content"))))
    # The real stream names every tool mcp__<server>__<tool>: a bare name is never one of ours, so it is refused here (the screen alone accepts a
    # bare name by its name, which only its own plain tests use).
    pairs = [(n if _prefixed(n) else "", t) for n, t in pairs]
    calls = [n if _prefixed(n) else "" for n in calls]
    verdicts = screen.screen_all(pairs, on_parts)
    verdicts += [screen.screen(name, "", 0, on_parts) for name in calls if name not in {p[0] for p in pairs}]
    line = screen.used_line(verdicts)
    if result is None or not all(v.used for v in verdicts):
        return False, line.text, None
    return True, line.text, json.dumps(result).encode("utf-8")
