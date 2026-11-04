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
- Two code notes: `platform.container_mode` does not exist on this branch (item 427 adds it), so the container check is skipped until the branch is rebased on it. And `platform.run_program` has no stdin option, so `run_security` passes `input` through its `run` argument; adding a `stdin` argument to `run_program` would be cleaner, but `platform.py` is outside this slice.

## Open decisions for the owner
1. Keep `-T ""` (a macOS prompt on each read) or trust `security` (no prompt, weaker).
2. Keep "no proxy" for now, or add proxy support before the route is offered.
(Still open from the plan: offering the key route at all, no test call on Save, and the words.)
