"""Row 1306 slice C4b: the command-line arguments that let ONE connector's read-only tools in and keep every other account
connector out. Pure functions, standard library only; the discovery run is injected. Nothing about a connector is stored, and
ask_claude.py is not changed: the connector path is a separate switch-guarded code path that uses `compose`.

What the real spike on a Mac showed (claude -p): --strict-mcp-config hides ALL account connectors, so it cannot be used when one
is On; --disallowedTools=<server> removes every tool of that server; allow plus deny of one tool removes it (deny wins); the form
'--disallowedTools X <prompt>' swallows the prompt, so EVERY argument here is one piece in the '=' form.

connector_args(discovered, on): one '--disallowedTools=<prefix>' for every discovered server that is not On (and for every server
that has no allow table, even when asked On), then for the On server '--allowedTools=<prefix>__<tool>' for the exact read-only
tools of the On connectors, then '--disallowedTools=<prefix>__<tool>' by name for every other known tool of that server (every
write tool, and the read tools of its connectors that are Off). A name with a hidden character, '=', a leading '-' or odd spacing is
dropped and counted. build_call(on, run): discovery is run FRESH for each call; if it fails, a listed server name was dropped, or an On connector is not found, the
call is refused with no arguments.
"""
import re

from clark import ask_connectors

M365 = "claude.ai Microsoft 365"
FLAG_ALLOW, FLAG_DENY = "--allowedTools=", "--disallowedTools="

# The one built-in a connector run keeps: it loads the allowed connector tool (the tool is deferred behind it). The run passes `--tools ToolSearch`, an
# allow-list of built-ins (see ask_claude.connector_arguments), so a built-in added later cannot reach the model and no deny list of built-in names exists.
LOADER = "ToolSearch"

# Every claude.ai server known today (the Connected ones the command can show, and those that only offer an authorize tool). When a connector is On, each of
# these is denied whole by its prefix, except the server of the part that is On, found or not. A server that is NOT in this list but IS in the fresh
# discovery is denied whole too (connector_plan), so a call to it is refused before it is made; a listed server whose name cannot be turned into a
# prefix refuses the whole connector run (build_call). The stream check stays as the last net.
KNOWN_SERVERS = ("Claude_Docs", "Gmail", "Google_Calendar", "Google_Drive", "Linear", "Microsoft_365", "Plaud", "Slides_AI", "Todoist", "Uber", "Vercel")

# server -> connector -> read-only tools (fixed order). The only tools that can ever be allowed.
READ_TOOLS = {
    M365: {
        "mail": ("outlook_email_search",),
        "calendar": ("outlook_calendar_search", "outlook_find_available_time", "find_meeting_availability"),
        "teams": ("chat_message_search", "teams_list_teams", "teams_list_channels", "teams_list_chats",
                  "teams_list_channel_messages"),
        "sharepoint": ("sharepoint_search", "sharepoint_folder_search"),
        "people": ("search_people", "get_me"),
    },
}

# server -> read tools that are never allowed, whichever part is On: read_resource is a general reader of the server (it can be given a mail or
# calendar address), so SharePoint and OneDrive being On must not open it. Denied by name.
NEVER_ALLOWED = {M365: ("read_resource",)}

# server -> every other known tool: denied by name when the server is On.
WRITE_TOOLS = {
    M365: (
        "outlook_batch_delete_messages", "outlook_batch_modify_labels", "outlook_create_draft", "outlook_create_event",
        "outlook_create_filter", "outlook_create_label", "outlook_create_reply_all_draft", "outlook_create_reply_draft",
        "outlook_delete_draft", "outlook_delete_event", "outlook_delete_filter", "outlook_delete_label",
        "outlook_forward_mail", "outlook_modify_labels", "outlook_modify_thread_labels", "outlook_respond_to_event",
        "outlook_send_draft", "outlook_send_mail", "outlook_set_vacation", "outlook_trash_thread", "outlook_untrash_thread",
        "outlook_update_draft", "outlook_update_event", "outlook_update_label",
        "sharepoint_copy_item", "sharepoint_create_folder", "sharepoint_delete_item", "sharepoint_move_item",
        "sharepoint_rename_item", "sharepoint_update_file", "sharepoint_upload_file",
        "teams_create_chat", "teams_reply_channel_message", "teams_send_channel_message", "teams_send_chat_message",
        "get_granted_scopes",
    ),
}

_SERVER = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]| (?! ))*[A-Za-z0-9]$|^[A-Za-z0-9]$")
_ID = re.compile(r"^[a-z][a-z0-9_]{0,40}$")


def prefix(server):
    """The tool-name prefix of a server: mcp__ plus the name with every character outside letters and digits as '_'."""
    return "mcp__" + re.sub(r"[^A-Za-z0-9]", "_", server)


def _clean(entry):
    """(server, connector) for a well-formed entry, else None."""
    if not isinstance(entry, dict):
        return None
    server, connector = entry.get("server"), entry.get("connector")
    if not (isinstance(server, str) and isinstance(connector, str)):
        return None
    if len(server) > 100 or not server.isascii() or not _SERVER.match(server) or not _ID.match(connector):
        return None
    return server, connector


def connector_plan(discovered, on):
    """(args, dropped): args as described above, dropped = how many discovered entries had a name that was refused."""
    on_ids = {c for c in (on if isinstance(on, (list, tuple, set, frozenset)) else ()) if isinstance(c, str) and _ID.match(c)}
    servers, dropped = {}, 0
    for entry in discovered if isinstance(discovered, (list, tuple)) else ():
        pair = _clean(entry)
        if pair is None:
            dropped += 1
            continue
        servers.setdefault(pair[0], set()).add(pair[1])
    whole, allow, named = [], [], []
    any_on = False
    for server in sorted(servers):
        table = READ_TOOLS.get(server)
        live = [c for c in table if c in on_ids and c in servers[server]] if table else []
        if not live:
            whole.append(FLAG_DENY + prefix(server))
            continue
        any_on = True
        p = prefix(server)
        allowed = []
        for c in table:                      # fixed table order
            if c in live:
                allowed.extend(table[c])
        allow.extend(f"{FLAG_ALLOW}{p}__{t}" for t in allowed)
        names = set(WRITE_TOOLS[server]) | set(NEVER_ALLOWED.get(server, ())) | {t for c in table for t in table[c]}
        named.extend(f"{FLAG_DENY}{p}__{t}" for t in sorted(names - set(allowed)))
    if any_on:
        have = {a[len(FLAG_DENY):] for a in whole}
        on_servers = {prefix(sv) for sv in servers if READ_TOOLS.get(sv) and any(c in on_ids and c in servers[sv] for c in READ_TOOLS[sv])}
        whole = sorted(set(whole) | {FLAG_DENY + "mcp__claude_ai_" + k for k in KNOWN_SERVERS
                                     if "mcp__claude_ai_" + k not in on_servers and "mcp__claude_ai_" + k not in have})
    return whole + allow + named, dropped


def connector_args(discovered, on):
    return connector_plan(discovered, on)[0]


class Call:
    """The verdict for one call: ok, args (empty when refused or when no connector is On), reason, dropped, connectors (False
    when nothing is On: the caller then keeps its normal locked-down path)."""
    __slots__ = ("ok", "args", "reason", "dropped", "connectors", "servers")

    def __init__(self, ok, args=(), reason="", dropped=0, connectors=False, servers=()):
        self.ok, self.args, self.reason, self.dropped, self.connectors = ok, tuple(args), reason, dropped, connectors
        self.servers = frozenset(servers)         # the server names the argument list was built from (the fresh discovery of this call)


def build_call(on, run=None):
    """The arguments for ONE call, from a fresh discovery made now (never the cache). Refused (ok False, no args) when a
    connector is On and the discovery failed or did not find it."""
    on_ids = [c for c in (on if isinstance(on, (list, tuple, set, frozenset)) else ()) if isinstance(c, str)]
    if not on_ids:
        return Call(True)
    ok, found = ask_connectors.list_fresh(run)
    if not ok:
        return Call(False, reason="discovery failed")
    args, dropped = connector_plan(found, on_ids)
    if dropped:         # a listed server whose name cannot be denied by prefix: it could be called, so no connector run at all
        return Call(False, reason="server name not readable", dropped=dropped)
    present = {e["connector"] for e in found if _clean(e)}
    if not set(on_ids) <= present or not any(a.startswith(FLAG_ALLOW) for a in args):
        return Call(False, reason="connector not found", dropped=dropped)
    return Call(True, args, dropped=dropped, connectors=True, servers={e["server"] for e in found})


def server_appeared(call, run=None):
    """Row 1306 F5: True when a server is listed NOW that the call's argument list was not built from (it appeared after the discovery, so no deny
    covers it), or when the list cannot be read to check. Asked after a connector run, from a fresh discovery; the run's answer is then not used."""
    ok, found = ask_connectors.list_fresh(run)
    return not ok or bool({e["server"] for e in found} - call.servers)


def compose(base, call):
    """The full argument list: `base` (ask_claude.arguments' list) with --strict-mcp-config taken out and the call's arguments
    added before the prompt flags. Refused call: raises ValueError, so nothing is ever sent without the deny list."""
    if not call.ok:
        raise ValueError(call.reason)
    if not call.connectors:
        return list(base)
    return [a for a in base if a != "--strict-mcp-config"] + list(call.args)
