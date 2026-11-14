"""The one provider module: the Claude command on this computer (#47c, commit 5 of the design note). GUARDED-DERIVED: new code
written for clark, not a copy (creaite's environment scrub is unreleased; the isolating flags, standard input, the fixed places,
the version and flag check and the process-group Stop are all new here). Two readers and the owner's own words before it merges.

What it does, and nothing more: it starts the person's own `claude` command, signed in with their own Claude plan, with every
customisation switched off and no tools, gives it the one request text on standard input, and reads the reply from standard
output. clark never sees, keeps or sends a key: the command holds its own sign-in.

The safety steps, each one tested in tests/test_ask_claude.py with a fake command:
- MAC ONLY: on any other system nothing is started and one fixed sentence (`MAC_ONLY`) is the status.
- FOUND IN FIXED PLACES ONLY (`PLACES`): an absolute path, never the PATH of whatever started clark, never a shell. The first place
  that holds anything decides; a later place is never tried after a refused one.
- A NATIVE PROGRAM ONLY (`native_problem`): the place is followed to the file it names, and that file must be a Mac program (a
  Mach-O file, never a script such as an npm or nvm shim, which would need a PATH the run does not give), a plain file owned by
  this user, writable by nobody else, in a folder writable by nobody else, inside the person's home folder or Homebrew's folders.
  The run starts that exact file, so the file checked is the file run.
- FAILS CLOSED ON VERSION AND FLAGS: `claude --version` must read as a version and `claude --help` must list every flag in
  `NEEDED_FLAGS`; otherwise nothing is sent and the status says to update the command. Kept per file (path, size, time, inode).
- FAILS CLOSED ON THE SIGN-IN (`login_problem`): before every question, `claude auth status` must report a Claude sign-in
  (`authMethod` "claude.ai"). An API key, an API key script, a token or another provider is refused, so a question can never move
  to paid use by accident; not signed in, or an answer that can't be read, sends nothing.
- ISOLATED RUN: `--safe-mode` (no CLAUDE.md, memory, skills, plugins, hooks, MCP servers or custom commands), `--setting-sources ""`
  (no settings file is read: the smoke test found that `--safe-mode` alone still ran the person's `apiKeyHelper`, a script that
  supplies an API key), `--disable-slash-commands`, `--tools ""` (no tool at all), `--strict-mcp-config` (no MCP server),
  `--no-session-persistence` (nothing saved under ~/.claude), `--system-prompt` with the fixed rules (the default prompt, which
  carries the folder, the platform and the date, is replaced), `--max-turns 1`, a pinned `--output-format json`
  (one result object, read strictly) and a `--max-budget-usd` cap. Never `--bare` (it would allow an API key only and never the sign-in),
  never `--add-dir`, never a model except one of `MODELS` (a fixed list of the command's aliases), never a file argument. `--max-turns` is documented for print mode but some versions leave it
  out of `--help`, so it is in `UNLISTED_FLAGS`: sent, not looked for (with no tools there is one answer either way).
- SCRUBBED ENVIRONMENT (`child_env`): an allow-list built from nothing: HOME, USER and LOGNAME from the system's own record of
  this user (never from clark's environment), a fixed system PATH and a plain language, plus the pinned switches in `PINNED_ENV`.
  Nothing clark was started with is passed on: no ANTHROPIC_*, CLAUDE_*, cloud keys, tokens, proxies, NODE_OPTIONS or DYLD_*.
- THE REQUEST ON STANDARD INPUT, never in the arguments (a long command line is visible to every local process); standard input
  then reaches its end, so the command can never wait for more.
- ITS OWN FOLDERS: an empty working folder and a private temporary folder (TMPDIR and CLAUDE_CODE_TMPDIR), both 0700, new for each
  run, outside clark's data folder and removed afterwards; umask 077; only standard input, output and error are inherited.
- LIMITS: one run at a time, a time limit, a cap on the bytes read back (checked after each read of at most 64 KB, so it can be
  passed by up to that much before the run is ended). Stop, the time limit and the cap end the WHOLE process group (the command
  starts helpers), then kill it after a short wait. The process handling itself is platform.run_stoppable (only platform.py
  starts a program).
- NO CONTENT IN LOGS OR ERRORS: no question, passage, reply, path or error text from the command is kept; failures are fixed
  sentences. The reply text is handed back to ask.ask_provider, which reads it with the reply reader and claims check.
"""
import glob
import json
import os
import pwd
import re
import shutil
import stat
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from clark import ask, platform

PROVIDER = "claude"
# An npm global or nvm install is looked for too (a "*" stands for one nvm node version). Its `claude` is a link: it is followed to the file
# it names, and that file must still be a Mac program (the native package's own binary); a script is refused as before.
PLACES = ("~/.local/bin/claude", "~/.claude/local/claude", "/opt/homebrew/bin/claude", "/usr/local/bin/claude",
          "~/.npm-global/bin/claude", "~/.nvm/versions/node/*/bin/claude")
OTHER_ROOTS = ("/opt/homebrew", "/usr/local")       # besides the home folder, where the file a place names may be
NEEDED_FLAGS = ("--print", "--safe-mode", "--disable-slash-commands", "--tools", "--strict-mcp-config", "--setting-sources",
                "--no-session-persistence", "--system-prompt", "--output-format", "--max-budget-usd")
MODEL_FLAG = "--model"                             # #54: needed only when a model is asked for, so a command without it still answers with its own
MODELS = ("opus", "sonnet", "haiku", "fable")      # #54: the only --model values ever sent: the command's own aliases, never raw text
MODEL_NAMES = {"opus": "Opus", "sonnet": "Sonnet", "haiku": "Haiku", "fable": "Fable"}
UNLISTED_FLAGS = ("--max-turns",)                 # documented for print mode, missing from some versions' --help: sent, not checked
NEVER_FLAGS = ("--bare", "--add-dir", "--mcp-config", "--settings", "--dangerously-skip-permissions", "--resume", "--continue",
               "--verbose", "--append-system-prompt", "--plugin-dir", "--agents")
SAFE_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"
KEEP_ENV = ("HOME", "USER", "LOGNAME", "LANG")      # what the sign-in and the text need; everything else is left out
# Set in the child, never copied from clark's. The first three are the ones the design read named (no telemetry, no self-update,
# no other non-essential traffic); the last two are the documented belt and braces for error reports and saved prompt history.
PINNED_ENV = {"DISABLE_TELEMETRY": "1", "DISABLE_AUTOUPDATER": "1", "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
              "DISABLE_ERROR_REPORTING": "1", "CLAUDE_CODE_SKIP_PROMPT_HISTORY": "1"}
TMP_NAMES = ("TMPDIR", "CLAUDE_CODE_TMPDIR")        # set by platform.run_stoppable to a new private folder for each run
SIGNED_IN = "claude.ai"                             # the only `authMethod` a question may use: the person's Claude plan
KEY_LOGINS = ("api_key", "api_key_helper")
AUTH_ARGS = ("--setting-sources", "", "auth", "status")   # the sign-in check reads no settings file (no apiKeyHelper, env or hooks)
LOGIN_REUSE = 2.0                                   # seconds a status() sign-in check stands for the question that follows it
MAX_BUDGET_USD = "1.00"                             # the command's own cap on one question's spend (counts against the plan)
TIME_LIMIT = 120.0                                  # seconds for one answer
CHECK_LIMIT = 15.0                                  # seconds for --version, --help or auth status
MAX_OUT = 4 * ask.MAX_REPLY + 65536                 # bytes read back: the reply as UTF-8, in its JSON wrapping
MAX_HELP = 512 * 1024
MAX_AUTH = 64 * 1024
VERSION = re.compile(rb"^\s*v?(\d+)\.(\d+)\.(\d+)\b")
_FLAG = r"-{1,2}[A-Za-z][A-Za-z0-9-]*"
OPTION_LINE = re.compile(r"^[ \t]*(" + _FLAG + r"(?:[ \t]*,[ \t]*" + _FLAG + r")*)(?=[ \t<\[=]|$)")   # "  -p, --print <x>  text"
MACH_O = (b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xfe\xed\xfa\xce", b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca")
PROXY_NAMES = ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy", "NODE_EXTRA_CA_CERTS",
               "SSL_CERT_FILE", "SSL_CERT_DIR", "NODE_TLS_REJECT_UNAUTHORIZED")
KEY_NAMES = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")

MAC_ONLY = ("Questions work on a Mac for now. Everything else in the report works as before, and a later version will cover this computer.")
NOT_INSTALLED = ("Questions need the Claude command, and it isn't installed on this computer. Install it from claude.com/claude-code, "
                 "sign in once, then ask again. Everything else in the report works as before.")
NOT_NATIVE = ("The Claude command on this computer can't be used safely, so nothing was sent. Install Claude with its own installer "
              "from claude.com/claude-code, then ask again.")
CANT_USE = "The version of Claude on this computer can't be used safely with clark. Update it, then ask again. Nothing was sent."
NOT_SIGNED_IN = "Claude isn't signed in on this computer. Open Terminal, type claude, and sign in when it asks. Then ask again."
API_KEY_LOGIN = ("Claude on this computer is signed in with an API key, which is paid for by use, so nothing was sent. "
                 "Connect Claude in Settings to use this.")
OTHER_LOGIN = ("Claude on this computer is signed in a way questions can't use, so nothing was sent. Open Terminal, type claude, "
               "and sign in with your Claude account. Then ask again.")
READY = "Claude is ready. Your question and the parts of the report it needs are sent to Claude, which Anthropic runs."
NO_ANSWER = ("Claude couldn't answer just now. Try again in a moment. If it keeps happening, open Terminal, type claude, and sign in "
             "when it asks.")
TOO_SLOW = "Claude took too long to answer, so it was stopped. Try a shorter question."
TOO_LONG_REPLY = "Claude's answer was too long to read, so it was stopped. Ask a narrower question."
BAD_SYSTEM = ask.BAD_INPUT                          # a coding fault, so the same plain line as any other bad input
MAX_SYSTEM = 8000                                   # characters of a caller-given system prompt
MODEL_REFUSED = "That model isn't one clark can use. Nothing was sent."
MODEL_NOT_OFFERED = "This version of Claude can't choose a model. Update Claude to choose one."
MODEL_UNAVAILABLE = "Claude says that model can't be used with this sign-in. Choose another model in Settings."
LIMIT_REACHED = "Claude says the limit for this model has been reached, so nothing more was sent."
LIMIT_OFFER = "You could ask again with {others}. clark doesn't switch unless you choose to."
BUSY = "Another question is being answered. Wait for it, or press Stop."
NOT_ELSEWHERE = ("Claude works in Terminal, but clark can't use it from where it is installed. Install it with its own installer "
                 "from claude.com/claude-code, then ask again.")
# Which words say "not found", by case: nowhere on this computer, or only somewhere clark does not look.
NOT_FOUND_WORDS = {"missing": NOT_INSTALLED, "elsewhere": NOT_ELSEWHERE}
# Hints: added after the status sentence when this computer's set-up is one questions can't follow.
PROXY_HINT = ("This computer reaches the internet through a proxy or its own security certificates. Questions don't use those "
              "settings, so Claude may not answer here. If questions fail, ask whoever runs your network for a way to reach Claude "
              "without them.")
CONFIG_HINT = ("Your Claude settings are kept in a folder of their own. Questions use the standard folder, so Claude may say you "
               "aren't signed in. To fix it, open Terminal, type env -u CLAUDE_CONFIG_DIR claude, and sign in when it asks.")
KEY_HINT = ("An API key is set up for Claude on this computer. Questions never use it: they use your Claude sign-in. Connect Claude "
            "in Settings to use this.")


def _me():
    """This user's home folder and name, from the system's own record (never from an environment variable)."""
    try:
        rec = pwd.getpwuid(os.getuid())
        return rec.pw_dir, rec.pw_name
    except (KeyError, OSError):
        return "", ""


def child_env(home=None, user=None):
    """The child's whole environment, built from nothing: the home folder and the user name (from the system's record of this
    user, so the command finds its own sign-in), a fixed system PATH, a plain language and the pinned switches. Nothing else
    that clark was started with is passed on. `home` and `user` are seams for the tests and the smoke test."""
    my_home, my_user = _me()
    home = my_home if home is None else home
    user = my_user if user is None else user
    env = {"PATH": SAFE_PATH, "LANG": "en_GB.UTF-8"}
    if home and os.path.isabs(home):
        env["HOME"] = home
    if user and re.fullmatch(r"[A-Za-z0-9._-]{1,64}", user):
        env["USER"] = env["LOGNAME"] = user
    env = {k: v for k, v in env.items() if k in KEEP_ENV + ("PATH",)}
    env.update(PINNED_ENV)
    return env


def arguments(path, canary="", system=None, model=None):
    """The command line for one run: the fixed flags, the fixed rules as the system prompt (with this request's canary, #277),
    and nothing the person typed. `system` is a fixed rules text written in clark's own code (ai_menu.SUGGEST_RULES); left out,
    it is ask clark's `ask.RULES`. The canary goes onto either one. `model` is None (the command's own choice) or one of
    `MODELS`; anything else raises ValueError, so text can never reach --model."""
    if model is not None and (not isinstance(model, str) or model not in MODELS):
        raise ValueError("model")
    pick = ["--model", model] if model else []
    return [str(path), "--print", "--safe-mode", "--disable-slash-commands", "--tools", "", "--strict-mcp-config",
            "--setting-sources", "", "--no-session-persistence", "--max-turns", "1", "--output-format", "json",
            "--max-budget-usd", MAX_BUDGET_USD, *pick, "--system-prompt", ask.system_prompt(canary, system)]


def roots_for(home=None):
    """The folders the command's file may be in: the person's home folder and Homebrew's."""
    home = _me()[0] if home is None else home
    return tuple(str(Path(r).resolve()) for r in ((home,) if home else ()) + OTHER_ROOTS)


def _inside(path, roots):
    return any(path == Path(r) or Path(r) in path.parents for r in roots)


def _ancestor_problem(folder):
    """True when a folder above `folder` (up to /) could let someone else swap the path: owned by anyone but this user or the
    system, or writable by others without the sticky bit (a sticky folder such as /tmp lets others add names, never move ours)."""
    for up in folder.parents:
        try:
            st = os.stat(str(up))
        except OSError:
            return True
        if st.st_uid not in (0, os.getuid()):
            return True
        if st.st_mode & (stat.S_IWGRP | stat.S_IWOTH) and not st.st_mode & stat.S_ISVTX:
            return True
    return False


def native_reason(real, roots):
    """None when `real` (a resolved absolute path) is a Mac program this user owns that nobody else can change, inside `roots`,
    in a folder nobody else can write to, below folders nobody else can use to swap the path. Otherwise which check failed, as a
    short code: "unreadable", "owner" (wrong owner, not a plain runnable file, writable by others, outside the allowed folders)
    or "not_mac" (the first four bytes are not a Mac program's). Reads the first four bytes only."""
    try:
        st = os.stat(str(real), follow_symlinks=False)
        folder = os.stat(str(real.parent))
    except OSError:
        return "unreadable"
    if not stat.S_ISREG(st.st_mode) or not (st.st_mode & stat.S_IXUSR) or st.st_uid != os.getuid():
        return "owner"
    if st.st_mode & (stat.S_IWGRP | stat.S_IWOTH) or folder.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        return "owner"
    if not _inside(real, roots) or _ancestor_problem(real.parent):
        return "owner"
    try:
        fd = os.open(str(real), os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0))
        try:
            head = os.read(fd, 4)
        finally:
            os.close(fd)
    except OSError:
        return "unreadable"
    return None if head in MACH_O else "not_mac"


def native_problem(real, roots):
    """None when `real` passes every check of native_reason, otherwise True."""
    return None if native_reason(real, roots) is None else True


def _version_key(path):
    """Sort key by the numbers in a path (v20.1.0 -> 20, 1, 0), so v10 and v20 come after v9; a name with no number sorts lowest.
    A pre-release suffix (v1.0.8-rc10) sorts below its release (v1.0.8) and above the version before it; its own digits come last."""
    m = re.search(r"(?<=\d)[-+_]?(?:rc|alpha|beta|pre|dev|a|b)\d*", path, re.I)
    core, pre = (path[:m.start()], path[m.start():]) if m else (path, "")
    nums = tuple(int(n) for n in re.findall(r"\d+", core))
    if not nums:
        return (0, (), 0, ())
    return (1, nums, 0 if m else 1, tuple(int(n) for n in re.findall(r"\d+", pre)))


def _expand(places):
    """Each place as an absolute path; a "*" in one is every match, the highest name first (the newest nvm node version)."""
    for place in places:
        p = os.path.expanduser(place)
        if "*" in p and os.path.isabs(p):
            yield from sorted(glob.glob(p), key=_version_key, reverse=True)
        else:
            yield p


def missing_case(name="claude"):
    """"elsewhere" when the person's PATH holds a command of this name that is not in a place clark looks (it works in Terminal,
    but clark never runs a command found by PATH), else "missing". Only looked up, never run."""
    return "elsewhere" if shutil.which(name) else "missing"


def find_command(places=PLACES, roots=None):
    """(the resolved absolute Path of the command, None), or (None, plain reason). The first place that holds anything decides."""
    path, why, _code = find_checked(places, roots)
    return path, why


def find_checked(places=PLACES, roots=None):
    """find_command with a third item: the short code of the check that failed (None when it was found)."""
    roots = roots_for() if roots is None else tuple(roots)
    for place in _expand(places):
        p = Path(place)
        if not p.is_absolute() or not os.path.lexists(str(p)):
            continue
        try:
            real = p.resolve(strict=True)
        except (OSError, RuntimeError):
            return None, NOT_NATIVE, "unreadable"
        if native_problem(real, roots):
            return None, NOT_NATIVE, native_reason(real, roots) or "owner"
        return real, None, None
    return None, NOT_INSTALLED, "not_found"


def listed_flags(text):
    """The option names `--help` lists: only the names at the start of an option's own line count, never a name that appears in
    another option's description."""
    names = set()
    for line in text.splitlines():
        m = OPTION_LINE.match(line)
        if m:
            names.update(re.findall(_FLAG, m.group(1)))
    return names


def hints(environ=None):
    """The plain hints for this computer's set-up, from the environment clark was started with (only names are looked at)."""
    environ = os.environ if environ is None else environ
    out = []
    if any(environ.get(n) for n in PROXY_NAMES):
        out.append(PROXY_HINT)
    if environ.get("CLAUDE_CONFIG_DIR"):
        out.append(CONFIG_HINT)
    if any(environ.get(n) for n in KEY_NAMES):
        out.append(KEY_HINT)
    return out


def read_answer(out):
    """The reply text from the command's JSON output, or None when it isn't one successful result object holding text."""
    try:
        got = json.loads(out.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError):
        return None
    if not isinstance(got, dict) or got.get("type") != "result" or got.get("subtype") != "success" or got.get("is_error") is not False:
        return None
    text = got.get("result")
    if not isinstance(text, str) or not text.strip():
        return None
    return text


LIMIT_TEXT = re.compile(r"(hit your (usage |rate )?limit|(usage|rate|message) limit (reached|exceeded)|limit reached)", re.I)
MODEL_TEXT = re.compile(r"(selected model|unrecognized model|model .{0,80}(not found|not available|may not exist|don't have access))", re.I)


def _events(out):
    """The JSON objects in the command's output: one object, a list of them, or one per line. Anything else gives none."""
    try:
        text = out.decode("utf-8")
    except UnicodeDecodeError:
        return []
    try:
        got = json.loads(text)
        return [x for x in (got if isinstance(got, list) else [got]) if isinstance(x, dict)]
    except (ValueError, RecursionError):
        pass
    found = []
    for line in text.splitlines():
        try:
            x = json.loads(line)
        except (ValueError, RecursionError):
            continue
        if isinstance(x, dict):
            found.append(x)
    return found


def limit_reached(out):
    """True when the command's output says a usage limit stopped the run: its own limit event (a `rate_limit_event` whose
    status is `rejected`) or a failed result with status 429 first; failing those, the failed result's text. Reads nothing else."""
    for ev in _events(out):
        if ev.get("type") == "rate_limit_event":
            info = ev.get("rate_limit_info")
            if isinstance(info, dict) and info.get("status") == "rejected":
                return True
        elif ev.get("type") == "result" and ev.get("is_error") is True:
            if ev.get("api_error_status") == 429:
                return True
            text = ev.get("result")
            if isinstance(text, str) and LIMIT_TEXT.search(text):
                return True
    return False


def model_unavailable(out):
    """True when the command's failed result says it can't use the model it was given: an alias this version or this plan doesn't have."""
    for ev in _events(out):
        if ev.get("type") == "result" and ev.get("is_error") is True and isinstance(ev.get("result"), str) and MODEL_TEXT.search(ev["result"]):
            return True
    return False


def run(args, data, env, limit, max_out, stop=None):
    """One run of the command (platform.run_stoppable: its own group, its own folders, the environment exactly `env`)."""
    return platform.run_stoppable(args, data, env, limit, max_out, stop=stop, prefix="clark-ask-", tmp_names=TMP_NAMES)


@dataclass(frozen=True)
class LimitReached(ask.Failure):
    """A usage limit stopped the run. `model` is the one asked (None: the command's own) and `others` the aliases that could be
    offered instead; the message already names them. Nothing is retried or switched."""
    model: object = None
    others: tuple = ()


def limit_failure(model):
    others = tuple(m for m in MODELS if m != model)
    words = ", ".join(MODEL_NAMES[m] for m in others)
    return LimitReached(LIMIT_REACHED + " " + LIMIT_OFFER.format(others=words), model, others)


class ClaudeCommand(ask.Provider):
    """The Claude command as an ask.Provider. `places`, `roots`, `env`, `limit` and `max_out` are seams for the tests (a fake
    command); clark itself uses the defaults."""
    provider = PROVIDER
    models = MODELS                            # what `model` may be; a command for another provider has its own list
    command_name = "claude"
    not_found_words = NOT_FOUND_WORDS

    def __init__(self, places=PLACES, env=None, limit=TIME_LIMIT, max_out=MAX_OUT, check_limit=CHECK_LIMIT, roots=None):
        self.places, self.limit, self.max_out, self.check_limit = tuple(places), limit, max_out, check_limit
        self.roots = roots
        self.env = env if env is not None else child_env()
        self.lock = threading.Lock()           # one run at a time
        self.stop_event = threading.Event()
        self.guard = threading.Lock()          # #284: a run is registered, and Stop looks at it and ends it, only under this
        self.owner = None                      # who asked for the run now going (ask.Request.owner), set and cleared under the guard
        self.model_listed = False              # #54: whether the checked command's --help lists MODEL_FLAG
        self.checked = {}                      # (path, size, mtime, inode, device) -> the version and flag check, once per file
        self.failed = None                     # the short code of the check that last failed (see command and login_problem), None when none did
        self.passed = None                     # (path, when) of the last sign-in check status() passed, used once by ask()

    # ----- the checks -----
    def command(self):
        """(path, None) when the command is found, native and passes the version and flag check, else (None, plain reason)."""
        self.failed = None
        if platform.container_mode():                   # item 1100: in Docker the server has no command; say where to start clark
            self.failed = "container"
            return None, platform.needs_mac_words()
        if platform.system() != platform.MAC:           # the fixed places, the process handling and the sign-in are the Mac's
            self.failed = "container" if platform.container_mode() else "not_mac_os"
            return None, MAC_ONLY
        path, why, code = find_checked(self.places, self.roots)
        if path is None:
            self.failed = code
            return None, (self.not_found_words[missing_case(self.command_name)] if why == NOT_INSTALLED else why)
        try:
            st = path.stat()
            key = (str(path), st.st_size, st.st_mtime_ns, st.st_ino, st.st_dev)
        except OSError:
            self.failed = "not_found"
            return None, NOT_INSTALLED
        if key not in self.checked:
            self.checked = {key: self._flags_ok(path)}
        if not self.checked[key]:
            self.failed = "version_flags"
        return (path, None) if self.checked[key] else (None, CANT_USE)

    def _flags_ok(self, path):
        status, out, _code = run([str(path), "--version"], b"", self.env, self.check_limit, 4096)
        if status != "ok" or not VERSION.match(out):
            return False
        status, out, _code = run([str(path), "--help"], b"", self.env, self.check_limit, MAX_HELP)
        if status != "ok":
            return False
        listed = listed_flags(out.decode("utf-8", "replace"))
        self.model_listed = MODEL_FLAG in listed
        return set(NEEDED_FLAGS) <= listed

    def login_problem(self, path):
        """None when the command reports a Claude sign-in; otherwise the plain reason nothing is sent. Asked before every question.
        The check that failed is kept in `failed`."""
        why = self._login_problem(path)
        self.failed = None if why is None else ("api_key" if why == API_KEY_LOGIN else "no_login" if why in (NOT_SIGNED_IN, OTHER_LOGIN) else "login_unreadable")
        return why

    def _login_problem(self, path):
        status, out, code = run([str(path), *AUTH_ARGS], b"", self.env, self.check_limit, MAX_AUTH)
        if status not in ("ok", "failed") or code is None:
            return CANT_USE
        try:
            got = json.loads(out.decode("utf-8"))
        except (UnicodeDecodeError, ValueError, RecursionError):
            return CANT_USE
        if not isinstance(got, dict):
            return CANT_USE
        method = got.get("authMethod")
        if method in KEY_LOGINS:
            return API_KEY_LOGIN
        if code != 0 or got.get("loggedIn") is not True or method == "none":
            return NOT_SIGNED_IN
        return None if method == SIGNED_IN else OTHER_LOGIN

    def usable(self, reuse=False):
        """(path, None) when a question may be sent now, else (None, plain reason). With `reuse`, a sign-in check that status()
        passed for this same file less than LOGIN_REUSE seconds ago stands (once), so a question costs one check, not two."""
        path, why = self.command()
        if path is None:
            return None, why
        passed, self.passed = self.passed, None
        if reuse and passed is not None and passed[0] == path and time.monotonic() - passed[1] < LOGIN_REUSE:
            return path, None
        why = self.login_problem(path)
        return (path, None) if why is None else (None, why)

    def status(self):
        path, why = self.usable()
        self.passed = (path, time.monotonic()) if path is not None else None
        words = " ".join([READY if path is not None else why] + hints())
        return {"connected": path is not None, "why": words}

    # ----- one question -----
    def answer(self, path, text, canary="", system=None, model=None):
        """Send `text` to the command at `path` (already checked) and read its answer: the reply text, or an ask.Failure.
        A usage limit gives a `LimitReached` (never a switch to another model: the caller offers, the person chooses)."""
        status, out, _code = run(arguments(path, canary, system, model), text.encode("utf-8"), self.env, self.limit, self.max_out, stop=self.stop_event)
        if status in ("ok", "failed") and limit_reached(out):
            return limit_failure(model)
        if status in ("ok", "failed") and model is not None and model_unavailable(out):
            return ask.Failure(MODEL_UNAVAILABLE)
        if status == "stopped":
            return ask.Failure(ask.STOPPED)
        if status == "slow":
            return ask.Failure(TOO_SLOW)
        if status == "too_much":
            return ask.Failure(TOO_LONG_REPLY)
        reply = read_answer(out) if status == "ok" else None
        if reply is None:
            return ask.Failure(" ".join([NO_ANSWER] + hints()))
        return reply

    @staticmethod
    def fixed_rules(system):
        """True only for a rules text clark's own code wrote (ask clark's, or the suggestions'): a caller cannot choose its own."""
        from clark import ai_menu                    # here, not at the top: ai_menu is the page-facing module and imports ask
        return isinstance(system, str) and len(system) <= MAX_SYSTEM and system in (ask.RULES, ai_menu.SUGGEST_RULES)

    def ask(self, request, model=None, prefer=False):
        """`prefer`: the model is only a default, so a command that can't choose one answers with its own instead of refusing."""
        if model is not None and not (isinstance(model, str) and model in self.models):
            return ask.Failure(MODEL_REFUSED)    # fails closed, before anything is checked or sent
        with self.guard:                       # #284: registering the run and clearing stop state are one step Stop cannot split
            if not self.lock.acquire(blocking=False):
                return ask.Failure(BUSY)
            self.owner = getattr(request, "owner", None)
            self.stop_event.clear()
            cancel = getattr(request, "cancel", None)
            cancelled = cancel is not None and cancel.is_set()   # a Stop that came before this point, for this run
        try:
            if cancelled:
                return ask.Failure(ask.STOPPED)
            system = getattr(request, "system", "")
            if not self.fixed_rules(system):         # an empty one too: it never quietly becomes ask clark's rules
                return ask.Failure(BAD_SYSTEM)       # fails closed, before any sign-in check: never falls back to another prompt
            path, why = self.usable(reuse=True)
            if path is None:
                return ask.Failure(why)
            if model is not None and not self.model_listed:
                if not prefer:
                    return ask.Failure(MODEL_NOT_OFFERED)  # nothing is sent, and a question with no model is unaffected
                model = None
            return self.answer(path, self.envelope(request.text), request.canary, system, model)
        finally:
            with self.guard:
                self.owner = None
                self.lock.release()

    def stop(self, owner=None):
        """Stop the question being answered, if there is one (its whole process group ends). True when one was running. With
        `owner`, only a run that owner asked for (#284: one service's Stop never ends the other's run)."""
        with self.guard:
            running = self.lock.locked() and (owner is None or owner is self.owner)
            if running:
                self.stop_event.set()
            return running
