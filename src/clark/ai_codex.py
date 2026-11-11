"""The ChatGPT sign-in for ask clark (#52, #54): the person's own `codex` command, signed in with ChatGPT. No key, no network code of clark's.

WHY THIS IS NOT JUST ANOTHER COMMAND LINE. Codex's "read-only" sandbox limits writes, not reads: tested on 04-11-2026, a run read a planted file
in the home folder and sent it to OpenAI. clark's rule is that a run can read nothing but what clark sends it. So a run has three layers, and
each is tested on its own:

1. TOOLS OFF. Every tool feature is disabled by name (`DISABLED`), and web search too.
2. THE WALL. The command runs inside a macOS sandbox whose rules clark writes (`wall`): nothing under the people's folders, the temporary folders
   or other volumes can be read, except Codex's own folder, the folder its program is in and this run's own empty folders; nothing can be written
   but those. The wall does not depend on anything Codex does. A read of the planted file gets "Operation not permitted".
3. THE REPLY IS CHECKED. An answer from a run that shows any tool use is dropped (`read_events`), whatever it says.

Also: the native program from fixed places (ask_claude.find_command, its ownership checks too), an environment built from nothing
(ask_claude.child_env), the user's config and rules ignored, nothing kept (`--ephemeral`), clark's fixed rules in place of Codex's own prompt, and
only a sign-in with ChatGPT: an API key is refused (billing per use is a later item, #643).
"""
import json
import os
import pwd
import re

from clark import ask, ask_claude, platform

PROVIDER = "chatgpt"
SUBDIR = "node_modules/@openai/codex/node_modules/@openai/codex-darwin-arm64/vendor/aarch64-apple-darwin/bin/codex"
PLACES = (f"~/.local/lib/{SUBDIR}", f"/opt/homebrew/lib/{SUBDIR}", "/opt/homebrew/bin/codex")
# The models a ChatGPT sign-in offers (`codex debug models`, 04-11-2026), with each one's context in tokens, pinned so a change is reviewed.
MODELS = ("gpt-6.1-sol", "gpt-6.1-terra", "gpt-6-sol", "gpt-6-astra", "gpt-6-luna")
CONTEXT_TOKENS = {"gpt-6.1-sol": 500000, "gpt-6.1-terra": 500000, "gpt-6-sol": 272000, "gpt-6-astra": 272000, "gpt-6-luna": 272000}
RECOMMENDED = "gpt-6.1-sol"     # the owner, 04-11-2026: the middle model, the one that compares with Sonnet. Codex calls it the "workhorse for coding and everyday work"
SMALLER = ("gpt-6.1-terra", "gpt-6-luna")                  # ask first, as Haiku does: Codex calls them balanced for straightforward work, and fast for easier tasks
MODEL_NAMES = {"gpt-6.1-sol": "GPT-6.1 Sol", "gpt-6.1-terra": "GPT-6.1 Terra", "gpt-6-sol": "GPT-6 Sol", "gpt-6-astra": "GPT-6 Astra", "gpt-6-luna": "GPT-6 Luna"}
DISABLED = ("shell_tool", "unified_exec", "apps", "plugins", "multi_agent", "multi_agent_v2", "image_generation", "browser_use", "computer_use",
            "in_app_browser", "goals", "skill_search", "hooks", "code_mode_host", "sleep_tool", "shell_snapshot", "view_image", "tool_suggest")
NEEDED_FLAGS = ("--ignore-user-config", "--ignore-rules", "--ephemeral", "--skip-git-repo-check", "--sandbox", "--disable", "--json", "--config", "--model")
SANDBOX = "/usr/bin/sandbox-exec"
PREFIX = "clark-codex-"
TMP_NAMES = ("TMPDIR",)
VERSION = re.compile(rb"^codex-cli (\d+)\.(\d+)\.(\d+)\b")
# The versions the wall and the tools-off list were tested with. A newer Codex could bring a tool DISABLED doesn't name, and the wall can't limit the network
# to OpenAI's hosts (a macOS sandbox rule names an address or a port, never a host name), so a new version means a new release of clark.
TESTED_FROM, TESTED_TO = (0, 166, 0), (0, 166, 999)
HOME_ROOTS = ("/Users", "/private/var/folders")
UNSAFE_IN_PATH = ('"', "\\", "\n")           # a path holding one of these could change the meaning of the sandbox rules
SIGNED_IN = "Logged in using ChatGPT"
KEY_WORDS = re.compile(r"api key", re.I)
ALLOWED_ITEMS = ("agent_message", "reasoning", "error")   # anything else in a run's events is a tool, so the answer is dropped
LIMIT_TEXT = re.compile(r"(usage limit|rate limit|limit (reached|exceeded)|hit your .{0,20}limit|too many requests)", re.I)
MODEL_TEXT = re.compile(r"model is not supported|model .{0,60}not supported|unknown model", re.I)

READY = "ChatGPT is signed in on this computer."
NOT_INSTALLED = "ChatGPT needs the Codex command, and it isn't on this computer. Install Codex, sign in with ChatGPT, then try again."
NOT_NATIVE = "The Codex command on this computer can't be used safely. Install it again, then try again."
UNTESTED = "This version of Codex has not been tested with clark: update clark."
ODD_HOME = "Your computer's home folder is not where macOS usually keeps it, so clark can't keep ChatGPT away from your files. Nothing was sent."
CANT_USE = "The Codex command on this computer isn't one clark can use. Update it, then try again."
NOT_SIGNED_IN = "ChatGPT isn't signed in on this computer. Open Terminal, type codex login, sign in, then try again."
API_KEY_LOGIN = "Codex is signed in with an API key, which clark doesn't use. Open Terminal, type codex login, sign in with ChatGPT, then try again."
NO_ANSWER = "ChatGPT couldn't answer just now. Try again in a moment."
TOOLS_USED = "That answer was dropped, because the run tried to use something it isn't allowed to. Try again."
TOO_SLOW = "ChatGPT took too long to answer, so it was stopped. Try a shorter question."
TOO_LONG = "ChatGPT's answer was too long to read, so it was stopped. Ask a narrower question."
MODEL_UNAVAILABLE = "ChatGPT says that model can't be used with this sign-in. Choose another model in Settings."
LIMIT_REACHED = "ChatGPT says the limit for this model has been reached, so nothing more was sent. clark doesn't switch unless you choose to."


def quote(text):
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def own_home():
    """The home folder from the system's own record of this user, never from the environment."""
    return os.path.realpath(pwd.getpwuid(os.getuid()).pw_dir)


def home_problem(home):
    """True when the wall can't be trusted to cover `home`: it isn't a real folder, isn't under the places a Mac keeps them, or holds a character that could
    change the rules. A run is then refused: fails closed."""
    real = os.path.realpath(home)
    if not os.path.isdir(real) or any(c in real for c in UNSAFE_IN_PATH):
        return True
    return not any(real.startswith(root + "/") for root in HOME_ROOTS)


def wall(home, program, scratch, prefix=PREFIX):
    """The sandbox rules for one run. Reads are refused under the person's home, the people's folders, other volumes and the temporary folders, then allowed back
    only for Codex's own folder, the folder its program is in and this run's own folders. Writes are refused everywhere but Codex's folder and this run's folders.
    Listing a name is not reading it: Codex needs to look at the folders above the ones it may read. `(allow default)` leaves system files readable (/etc,
    /Library, /Applications): those are not the person's data, and Codex can't start without many of them. The wall is for the person's files and secrets. It
    also stops file reads only: the tools-off list and the version pin (TESTED_FROM) are what stop anything else."""
    if any(c in str(p) for p in (home, program, scratch) for c in UNSAFE_IN_PATH):
        raise ValueError("path")
    codex = os.path.join(home, ".codex")
    own = re.escape(os.path.join(scratch, prefix)) + "(tmp-)?" + "[a-z0-9_]" * 8 + "(/|$)"     # a run's two folders as Python names them, never another name that starts the same
    return "\n".join((
        "(version 1)", "(allow default)",
        f'(deny file-read-data (subpath "/Users") (subpath {quote(home)}) (subpath "/Volumes") (subpath "/private/tmp") (subpath "/private/var/folders") (subpath "/tmp"))',
        "(deny file-write*)",
        f'(allow file-read-data (literal "/Users") (literal {quote(home)}) (subpath {quote(codex)}) (subpath {quote(os.path.dirname(program))}) (regex #"^{own}"))',
        f'(allow file-write* (subpath {quote(codex)}) (regex #"^{own}") (literal "/dev/null") (literal "/dev/dtracehelper"))'))


def arguments(path, canary="", system=None, model=None, home=None, scratch=None):
    """The command line for one run: the wall, then Codex with every tool off and clark's rules as its instructions. Nothing the person typed.
    The question goes on standard input. `model` is None or one of MODELS; anything else raises ValueError."""
    if model is not None and (not isinstance(model, str) or model not in MODELS):
        raise ValueError("model")
    home = own_home() if home is None else home
    scratch = os.path.realpath(platform.scratch_parent()) if scratch is None else scratch     # the sandbox sees real paths: /tmp is /private/tmp
    off = [x for name in DISABLED for x in ("--disable", name)]
    pick = ["--model", model] if model else []
    return [SANDBOX, "-p", wall(home, str(path), scratch), str(path), "exec", "--ignore-user-config", "--ignore-rules", "--ephemeral",
            "--skip-git-repo-check", "--sandbox", "read-only", "--json", "--config", 'web_search="disabled"',
            "--config", "base_instructions=" + json.dumps(ask.system_prompt(canary, system)), *off, *pick, "-"]


def read_events(out):
    """What a run's events say: ("answer", text), ("tools", None), ("limit", None), ("model", None) or ("none", None). Tool use outranks everything."""
    try:
        lines = out.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        return "none", None
    text, kinds, problems = None, set(), []
    for line in lines:
        try:
            ev = json.loads(line)
        except (ValueError, RecursionError):
            continue
        if not isinstance(ev, dict):
            continue
        item = ev.get("item")
        if isinstance(item, dict) and isinstance(item.get("type"), str):
            kinds.add(item["type"])
            if ev.get("type") == "item.completed" and item["type"] == "agent_message" and isinstance(item.get("text"), str):
                text = item["text"]
        if ev.get("type") in ("error", "turn.failed"):
            said = ev.get("message") if isinstance(ev.get("message"), str) else (ev.get("error") or {}).get("message") if isinstance(ev.get("error"), dict) else ""
            problems.append(said if isinstance(said, str) else "")
    if kinds - set(ALLOWED_ITEMS):
        return "tools", None
    for said in problems:
        if LIMIT_TEXT.search(said):
            return "limit", None
        if MODEL_TEXT.search(said):
            return "model", None
    if problems or not text:
        return "none", None
    return "answer", text


def run(args, data, env, limit, max_out, stop=None):
    return platform.run_stoppable(args, data, env, limit, max_out, stop=stop, prefix=PREFIX, tmp_names=TMP_NAMES)


class CodexCommand(ask_claude.ClaudeCommand):
    """The Codex command as an ask.Provider. The run lock, Stop and the fixed-rules check are the Claude command's, unchanged."""
    provider = PROVIDER
    models = MODELS

    def __init__(self, places=PLACES, env=None, limit=ask_claude.TIME_LIMIT, max_out=ask_claude.MAX_OUT, check_limit=ask_claude.CHECK_LIMIT, roots=None, walled=True):
        super().__init__(places, env, limit, max_out, check_limit, roots)
        self.walled = walled                   # False only in tests with a fake script, which the wall would refuse to run
        self.untested = False                  # the checked command is a version the wall hasn't been tested with

    def command(self):
        if self.walled and home_problem(own_home()):
            self.failed = "odd_home"
            return None, ODD_HOME
        got, why = super().command()
        if got is None:
            if self.untested and self.failed == "version_flags":
                self.failed = "untested"
            return None, {ask_claude.NOT_INSTALLED: NOT_INSTALLED, ask_claude.NOT_NATIVE: NOT_NATIVE,
                          ask_claude.CANT_USE: UNTESTED if self.untested else CANT_USE}.get(why, why)
        return got, None

    def _flags_ok(self, path):
        self.untested = False
        status, out, _code = run([str(path), "--version"], b"", self.env, self.check_limit, 4096)
        found = VERSION.match(out) if status == "ok" else None
        if not found:
            return False
        if not TESTED_FROM <= tuple(int(n) for n in found.groups()) <= TESTED_TO:
            self.untested = True
            return False
        status, out, _code = run([str(path), "exec", "--help"], b"", self.env, self.check_limit, ask_claude.MAX_HELP)
        if status != "ok":
            return False
        self.model_listed = True
        return set(NEEDED_FLAGS) <= ask_claude.listed_flags(out.decode("utf-8", "replace"))

    def login_problem(self, path):
        why = self._login_problem(path)
        self.failed = None if why is None else ("api_key" if why == API_KEY_LOGIN else "no_login" if why == NOT_SIGNED_IN else "login_unreadable")
        return why

    def _login_problem(self, path):
        status, out, code = platform.run_stoppable([str(path), "login", "status"], b"", self.env, self.check_limit, ask_claude.MAX_AUTH,
                                                    prefix=PREFIX, tmp_names=TMP_NAMES, merge_err=True)     # it says this on standard error
        if status not in ("ok", "failed") or code is None:
            return CANT_USE
        said = out.decode("utf-8", "replace")
        if code == 0 and SIGNED_IN in said:
            return None
        return API_KEY_LOGIN if KEY_WORDS.search(said) else NOT_SIGNED_IN

    def status(self):
        path, why = self.usable()
        self.passed = (path, ask_claude.time.monotonic()) if path is not None else None
        return {"connected": path is not None, "why": READY if path is not None else why}

    def answer(self, path, text, canary="", system=None, model=None):
        args = arguments(path, canary, system, model)
        if not self.walled:
            args = args[args.index(str(path)):]
        status, out, _code = run(args, text.encode("utf-8"), self.env, self.limit, self.max_out, stop=self.stop_event)
        if status == "stopped":
            return ask.Failure(ask.STOPPED)
        if status == "slow":
            return ask.Failure(TOO_SLOW)
        if status == "too_much":
            return ask.Failure(TOO_LONG)
        kind, reply = read_events(out)
        if kind == "tools":
            return ask.Failure(TOOLS_USED)
        if kind == "limit":
            return ask.Failure(LIMIT_REACHED)
        if kind == "model":
            return ask.Failure(MODEL_UNAVAILABLE)
        return reply if kind == "answer" and status == "ok" else ask.Failure(NO_ANSWER)
