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


def checked(out, on_parts):
    """(ok, used_line_text, result_bytes or None) for one connector run's stream output."""
    names, pairs, calls = {}, [], []
    result = None
    for ev in _events(out):
        kind = ev.get("type")
        if kind == "result":
            result = ev
        elif kind == "assistant":
            for b in _blocks(ev):
                if b.get("type") == "tool_use":
                    name = b.get("name")
                    names[b.get("id")] = name
                    calls.append(name)
        elif kind == "user":
            for b in _blocks(ev):
                if b.get("type") == "tool_result":
                    pairs.append((names.get(b.get("tool_use_id")), _text(b.get("content"))))
    verdicts = screen.screen_all(pairs, on_parts)
    verdicts += [screen.screen(name, "", 0, on_parts) for name in calls if name not in {p[0] for p in pairs}]
    line = screen.used_line(verdicts)
    if result is None or not all(v.used for v in verdicts):
        return False, line.text, None
    return True, line.text, json.dumps(result).encode("utf-8")
