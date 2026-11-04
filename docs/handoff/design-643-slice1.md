# #643 slice 1: Keychain store and HTTPS caller (not wired)

## What exists
- `src/clark/ai_keychain.py`: keeps the Claude and OpenAI keys in the Mac Keychain (service `clark-ai`, accounts `claude`, `openai`). Functions: `has_key`, `save_key`, `read_key`, `delete_key`, `valid_shape`. Every call to `/usr/bin/security` goes through one function, `run_security`. A key goes to `security -i` on standard input only, never in a command line, environment variable, log line or error text. A second save replaces the first (`-U`). A locked or unavailable Keychain raises `KeychainError` with one fixed sentence. Off the Mac, or in the container, it raises `platform.NotBuiltYet`.
- `src/clark/ai_https.py`: `post_json` to two pinned hosts only (`api.anthropic.com`, `api.openai.com`). Certificates are verified, redirects are refused, the reply size is capped, there is a timeout, and no retry. Every failure is an `HttpsError` with a fixed code: timeout, connection, too_big, refused_host, redirect.
- Tests for both, with no real Keychain and no real network.

## Deliberately not wired
No route, no setting, no page, no provider, no secret screen, no visible sentence. Nothing imports these modules. The sentences inside them are internal.

## Choices to know about
- Keychain `-T ""`: no application is trusted, so macOS asks before it gives a key out. Cost: a macOS prompt when the key is read. Dropping it removes the prompt and lets any program that can run `security` read the key.
- No proxy: Python's `http.client` ignores proxy settings, so a request goes straight to the host. Someone behind a company proxy could not use this route.
- `security -i` exit codes (confirmed on a real Mac): it exits 0 even when the add-generic-password inside it fails (it prints `add-generic-password: returned -25299`); only a bad command exits 1. So `save_key` does not trust exit 0: it reads both outputs for a `returned <number>` line, then confirms the item exists with a find, and raises the fixed sentence if either says no.
- Key shape is an allowlist: after the provider prefix (`sk-ant-` or `sk-`) only letters, digits, `-` and `_`; 20 to 400 characters. Refusals give a short code from `REFUSAL_CODES`, never the key.
- Timeouts: `socket.timeout` is not `TimeoutError` on Python 3.9, so both are caught. The per-call timeout is per socket call; there is also an overall deadline (default 60 s) checked between chunks. The reply cap is exact (a read never asks for more than one byte past it).
- Key exposure in a traceback: `save_key` deletes its `key` local, and `_call` and `run_security` delete their command-text locals, in `finally`, so a traceback walk finds the key in no `ai_keychain` frame (a test checks this). NOT claimed: the command text is still the `input` argument inside the `subprocess` call and in `platform.run_program` frames below `run_security`, and in the caller's own frame; a handler that captures every frame's locals could still reach it there. Only a real fix in `platform.run_program` (or never holding the key in a Python str) would close that.

## For when this is wired (not now)
- Give `platform.run_program` its own `input` and `timeout` options instead of the `functools.partial` in `run_security` (`platform.py` is out of scope for this slice).
- The proxy decision (no proxy now) and `-T ""` are with the owner.
- One real-Mac check before the route is wired: save, has, read, delete, and a deliberately failing add, against the real Keychain.

## Open decisions for the owner
1. Keep `-T ""` (a macOS prompt on each read) or trust `security` (no prompt, weaker).
2. Keep "no proxy" for now, or add proxy support before the route is offered.
(Still open from the plan: offering the key route at all, no test call on Save, and the words.)
