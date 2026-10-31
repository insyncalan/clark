# Readiness pass: #54 Sign in to Claude or OpenAI for ask clark

Written by a teammate, 28-10-2026, for the project lead to paste into the issue. It uses the same form as `readiness-v0.2.md`. Requirements: BR-10 and FR-63 to FR-68. Decisions: D-7 and D-8 (#52 and #53), decided 28-10-2026 with #55; see "Decided" below. Checked against creaite branch `v27-132-build` at `a6249e2d`: `system/scripts/providers.py`, `dev/proposals/132/` and `dev/tests/test_ai_models.py`. **Open** marks a decision still needed before the build.

## What creaite has, and what clark takes
- **`providers.py`, not guarded, built:**
  - **The key store.** macOS Keychain, written through Apple's Security framework with ctypes. No program is started, so the key is never on a command line. Service `creaite.ai.<vault id>.<provider>`, and `has()` never reads the secret.
  - **The model lister.** One HTTPS GET to `api.openai.com/v1/models` or `api.anthropic.com/v1/models`.
  - **The direct caller.** One HTTPS POST, **to OpenAI only** (`/v1/chat/completions`, `store: false`, no tools).
  - **Routing and limits,** and the fakes for tests.
- **Guarded, still patches in review:**
  - 01: the run environment scrub.
  - 02: the `/api/ai/*` routes and the run chain.
  - 03: `reach.py` refuses `providers.py`.
  - 04: `permissions.py` refuses any rule that names the keychain.
  - 05: the direct path in `edit_ai.py`.
- **G8, "Claude by API key" through the Claude command:** not built. It needs a canary check that Claude Code never passes the key to the programs its tools start.
- **clark takes:**
  - The store, the lister, the direct caller, the fakes and the AI models page (`AiModels.jsx`), cut down to Claude and OpenAI and one kind of job (ask clark).
  - The scrub and the `reach.py` rule, as clark's own copies.
- **clark doesn't need G8.** ask clark uses no tools (FR-67), so a Claude API key can go in a direct HTTPS call to `api.anthropic.com/v1/messages`, just like creaite's OpenAI call. No Claude Code process ever sees the key. This is new code, not a copy: one more host and path in the direct caller.

## Done when
**Connect and disconnect**
- Settings › AI shows a Claude card and an OpenAI card. Claude offers "Claude subscription" and "API key". OpenAI offers "API key" now, and "ChatGPT sign-in" once the spike passes (#52).
- Connect tests the key with the model-list call and saves the models the user ticks. A refused key keeps the box open and says why, for example "OpenAI did not accept this key (401)". A network failure says it couldn't reach the provider. Neither message contains the key or the response body.
- Disconnect deletes the keychain item. Anything set to that provider's models goes back to the recommended model, and a test checks this.

**Where the key lives and where it never goes**
- The key is in the macOS Keychain only, as service `clark.ai.<data folder id>.<provider>`, account `clark`.
- A canary test runs one fake key (`…TESTONLY`) through enter, test, call, error and remove. It then searches `clark.db`, settings, backups, logs, published files, the process list and the repo, and the canary is in none of them.
- No route returns a key. A pasted key in ask clark's chat box is refused before anything is sent.

**Every outgoing call**
- Each call goes to an exact host from a list in code: `api.openai.com` or `api.anthropic.com`.
- TLS 1.2 or later, verified against the system's certificates.
- No redirect is followed, and no proxy is taken from the environment.
- Limits on time, bytes sent, bytes read and reply tokens.
- The key goes in one header only.
- A static test fails if any module other than the provider caller imports `urllib.request`, `http.client`, `socket` or `ssl`. clark has no update fetch, so there are no exceptions.

**The Claude subscription route**
- The Claude command runs with `--tools "" --strict-mcp-config` and the chosen `--model`, from an empty folder outside the data folder, with creaite's no-context arguments. These are copied from creaite's `edit-ai` run kind at v2.6.9.
- Its environment is scrubbed of `ANTHROPIC_*`, `CLAUDE_CODE_USE_*`, `CLAUDE_CODE_OAUTH_TOKEN`, `CLAUDE_CODE_SIMPLE` and the key-helper time-to-live, from creaite patch 01's list. Without the scrub, a key in the user's shell would quietly move every run to paid API billing.
- `--bare` is never used, because it turns off hooks. A source test fails on `--bare` anywhere.

**The same ask clark on both providers (FR-67)**
- One function builds every provider request. The same question and the same passages give the same request text on Claude and OpenAI, apart from the envelope (a test).
- Proposed changes come back as fixed-form lines and are checked against the data before they are shown. A reply that doesn't parse is shown as text, with no change offered.

**Model choice (FR-65)**
- The model list shows only connected providers. The recommended model is marked and is the default.
- Choosing a weaker model asks first, and the user's "use it anyway" is remembered.
- The connect box says that passages sent leave the computer and are billed to that account. A test pins the wording.

**Limits (FR-66)**
- A limit is detected from HTTP 429 or the provider's limit error on direct calls, and from the Claude command's limit event on the subscription route.
- ask clark then says so and offers the other connected provider or a smaller model. It never switches by itself (a test).

**Tests**
- They use fakes only: `CLARK_FAKE_PROVIDERS=1`, honoured only in the development repo (a marker file) or a data folder inside the system's temporary folder, as creaite's G10 does.
- No test touches the real keychain or network. Every key in a test ends in `TESTONLY`.

## Touches
- `src/clark/providers.py`: the store, the lister, the direct caller, routing and the fakes.
- `/api/ai/*` routes on the server.
- `src/clark/ask.py`: ask clark's request builder and reply parser.
- The run launcher for the subscription route.
- clark's copy of `reach.py`: `providers.py` and the keychain are never readable by a run.
- The Settings page from `AiModels.jsx` and the settings store.
- `settings` rows for `ai.*`: models and choices, never a key.

## Depends on
- #33 (server and its route test) and #31 (store).
- #34 and #35 (the vendored front end and the page) for the Settings page.
- ask clark itself (#47): FR-60 to FR-62, search and the source folders.
- **The creaite release that includes #132** (#53: "wait fo release"). Patches 01, 03 and 04 must have landed in it. The build doesn't start before that tag exists.
- The ChatGPT spike, for the ChatGPT route only. API keys don't wait on it.

## Review
Full: two independent reviewers, never the builder, as for a guarded copy. It touches secrets, the clark copy of `reach.py` and the first outgoing network calls clark makes. The owner approves the exact code.

## Decided
- **#55, Claude and OpenAI:** "Both openai and claude handled the same.. no differnetiation." No per-project switch: ask clark sends the same passages to whichever provider the user connected. This settles the old open point 1 (D-9). FR-68 is rewritten to say so, and the connect box's wording (FR-65) says passages leave the computer whichever provider it is. The "never send to another provider" switch and its tests are dropped from this item.
- **#52, OpenAI sign-in:** "ChatGPT sign-in too", as well as an API key, after a spike proves the route (point 2 below).
- **#53, where the code comes from:** "wait fo release". clark copies from the creaite release that includes #132, not from the branch.

## Open
1. *(Decided, #55: see above.)*
2. **The ChatGPT spike (#52: "ChatGPT sign-in too").** The route is wanted; the spike must prove three things before it's built. First, that OpenAI's Codex command can run with no tools: no shell, no file reads and no network apart from its own model call. Second, that it takes the chosen model. Third, that the user's ChatGPT plan terms allow use from another app. Nothing about the Codex command's flags is checked yet. If the spike fails on any of them, the project lead takes it back to the owner. Until then, OpenAI is API key only.
3. **Size of what is sent.** creaite's direct call sends at most 16,000 characters, which suits edits of selected text. Checking a whole report against its data needs more. *Recommendation:* a per-provider limit, set from the chosen model's context size and pinned in code. ask clark says when passages were left out.
4. **More passages mid-answer.** With no tools, the model can't fetch more for itself. *Recommendation:* a fixed-form line `NEED: <query>` that clark answers with its own search, at most two rounds a question. The rounds work the same on both providers.
5. **Windows, later (not in v0.1).** The equivalent store is **Windows Credential Manager**: a generic credential through `advapi32` `CredWriteW`, `CredReadW` and `CredDeleteW` with ctypes. That's standard library only, per user, and nothing is installed, the same shape as creaite's `SecApi`. DPAPI alone would mean keeping an encrypted key file on disk, which the key rule forbids, so it isn't recommended. Until the port, `NotBuiltStore` answers "not connected" on any system other than macOS, as creaite's does.
