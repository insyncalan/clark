# Design: #72 The AI menu on the page

Written by the build team, 30-10-2026, as the plan for the page side of #72. Nothing here is built. Size of the whole page side: L. This note is read-only planning: no code, no guarded file touched.
**Sources:** #72 and its comments (decision of 28-10-2026: Claude only in v0.3, one small provider interface, #54 adds OpenAI in v0.5), the logic branch for #72 (the `72-ai-menu-logic` branch, head 9941521, three rounds of second-reader review), `docs/handoff/design-66-editor-wiring.md` and PR #194 (the one editor), `docs/handoff/readiness-54-providers.md` (#54), PR #123 (`ask.py`, ask clark's pure parts, #47c), `system/prototype/editor.js` (the look), the reuse record.

## 1. What the logic branch already delivers (`src/clark/ai_menu.py`, no page code)
- **The menu as data.** `OPTIONS` (12, with "Ask…" as the free-text one), `PLACES`, `GROUPS`, `FORMATS`, and `menu(place)`: the groups, Format notes as its own button, Make into for the rich places only, Ask… last.
- **The request.** `build_prompt(option, text, place, instruction)` takes exactly those four things and returns the prompt and `tools: []`. The text is fenced as material, never as instructions; 12,000 characters of text and 400 of instruction at most; hidden characters refused.
- **The reply check.** `check_reply` refuses an empty, far too long, identical, markup, script, hidden-character or added-address reply, and in a client message anything internal (blocking). It adds notes (never blocking) for lost or added figures, IDs and names. `plain_to_html` and `to_html` then `sanitise.clean_html` give the HTML the editor takes.
- **The card.** `AiSession` and `Card`: one card at a time; the editor is touched only by `accept`, which refuses if the text changed since the question; Discard; Try again (counts the old card as rejected, keeps a confidential "yes"); Show changes (`word_diff`); a late reply for a replaced card is ignored; counts-only stats.
- **The seam.** `Provider` (`name`, `status()` with `ready`, `off`, `not_signed_in` or `busy`, `ask(prompt, tools=())`), `suggest(...)` (the one-shot path; the provider is not asked unless ready), and fixed plain lines (`why_off`, `confidential_question`, `sends_notice`).
- **Not there:** any route, any page file, any real provider. `edit_ai.py` (a copy of a creaite guarded file) is untouched.

## 2. What the page side must add
- **Bubble AI zone.** The formatting bubble gets a second zone, "AI", on any non-empty selection: the groups of `menu(place)` (Improve, Structure or Tone), Format notes (several paragraphs only, rich places), Make into (notes and Current state only) and "Ask…" (a one-line box; Enter sends). Kept inside the window at 1400 and 900 px, light and dark.
- **Toolbar AI and Alt+/.** The toolbar's AI button and Alt+/ open the same list. On a selection they act on it; with none, on the whole field. Alt+/ also works from the keyboard alone, with arrow keys and Esc.
- **The suggestion card.** Under the field, one at a time: the option's name, the new text (drawn from the cleaned `card.html`, never raw), the notes, and four buttons: **Accept**, **Discard**, **Try again**, **Show changes**. States: asking (a confidential text, one question), running (with Stop), ready, failed (one plain line), off. Accept is one editor step, so one Cmd+Z undoes it; Discard changes nothing. The card carries the plain notice that the passage goes to Claude, the first time and in Settings.
- **Make into** (action, risk, decision): the selection becomes a new work item in one step with Undo, through the existing add-item change. No AI call.
- **A page client** (`aiClient`): one `fetch` to the route in slice 4, with a stop signal and a fixed error line for any failure. Nothing else on the page talks to a model.

## 3. Places and the editors that use them
| Place | Editors | Options |
|---|---|---|
| `current` (rich) | Current state, a use case's "Where it stands", every text section of the report | Improve, Structure (no checklist), Format notes, Make into, Ask… |
| `notes` (rich) | A Notes-kind section (#96) and any meeting-notes field when it lands | As current, plus Checklist |
| `plain` | Short plain fields in the peek (an item's text, a risk's wording), section titles stay out | Improve (3 options), Ask… |
| `email` | The Draft email preview (a plain box, #44) | Improve (3), Tone (Formal, Warmer), Ask… |
| `client_message` | The milestone's client wording in the peek, any text meant to reach a client | Improve (3), Ask…; blocking client check |

The page keeps this table once (`logic/aiMenu.js`) with a parity test against `ai_menu.menu()` for all five places, the way `cleanHtml` is tested against `sanitise.py`. The server stays the authority; the page table only decides what to draw.

## 4. What is blocked, and what we can build now
| Piece | Blocked by | Seam or stub we can build now |
|---|---|---|
| Bubble, toolbar AI, Alt+/ inside the editor | **#66.** #194 ships the editor with the `ai` hook left null and its write kinds behind the empty `RICH_WRITES` seam (waits for the `changes.py` diff). | A small `AiMenu` component and card that mount on any element, tested in a page harness against a stub `aiClient`. When #194 merges the hook is filled in: one place, `RichText.jsx`. Accept uses `replace_html(start, end, html)` (the logic's proposal); #66 must confirm its offsets match `text_between` |
| The route and the provider | **#47** (ask clark's run path) and **#54** (sign-in). The Claude sign-in route copies creaite's #132 release, which does not exist yet (#53) | `aiClient` stub with canned replies, a "fake provider" switch honoured only in the development repo or a temporary data folder (as #54 plans). The menu shows and says why it is off until a provider is ready |
| The two provider shapes | **#47c** `ask.Provider` (`ask(request)` returns text or a `Failure`; `status()` gives `{connected, why}`) is not the shape of `ai_menu.Provider` (`status()` is a word; `ask(prompt, tools)`) | One adapter, written once the real provider exists; both stay as they are. Tests: the adapter never passes tools; `connected` false maps to `not_signed_in` or `off` with the same plain reason |
| Store-aware client check | The store's codes and people (wiring) | Replace the shape check by `edit_ai.loose_ids` with real codes and known names; the parity test already holds the hostile and ordinary lists |
| Email place for an outside recipient | **#50** (the Draft email wiring) | Offer the email place only for the user's own domains until then |

**Privacy rules the build must keep (each a test):** only the selected text (or the whole field the user chose), the option's fixed instruction and Ask…'s one line go out; no project name, people, IDs or other data; no tools, ever; the provider is not asked when AI is off, not signed in or busy, and the menu says why in one plain line (no fault text, no key); a confidential text asks once, and Try again keeps that yes; nothing changes before Accept; a reply with markup, scripts, hidden characters or a new address is never shown; a pasted key in Ask… is refused before sending; the debug log gets the option, the place and the length, never text.

## 5. Guarded files
- **`src/clark/server.py`**: the `POST /api/ai/suggest` and `GET /api/ai/status` routes (token-checked, one run at a time, Stop). **Full tier.**
- **`src/clark/store.py` / `changes.py`**: only if Make into needs a new change kind or a rich write. The existing add-item change is expected to be enough; the rich-field write kinds are #66's own guarded diff, not ours.
- **`src/clark/edit_ai.py`**: not edited (the logic branch reads it). The reuse rows for `edit_ai` and `client_leak` are marked guarded, second reader pending.
- **Also guarded here:** the publish scan, `schema.sql`, `VERSION`, workflows. None is expected to change.
- Each guarded diff needs two readers plus the second reader, and the owner approves the exact diff in his own words. Slices 1 to 3 and 5 to 7 touch none.

## 6. Build order
| # | Slice | Size | Review | Waits for |
|---|---|---|---|---|
| 1 | `logic/aiMenu.js` (places, groups, plain lines) and its parity test against `ai_menu.menu()`; the plain-words test over every string | S | Light | nothing |
| 2 | The suggestion card component, all five states, Accept/Discard/Try again/Show changes (diff from the server's `word_diff`), against a stub `aiClient`; browser tests at 1400 and 900, light and dark | M | Light | nothing |
| 3 | Bubble AI zone, toolbar AI, Alt+/, Ask… box, Make into; one browser test per key; the "one editor" gate extended | M | Light (Full if it edits `core/editor.js`) | **#66** (#194 merged) |
| 4 | The two guarded routes and the status line in Settings › AI | S | **Full** | **#47** run path |
| 5 | Provider adapter to the real Claude route; the notice "passages go to Claude"; the canary tests (nothing but the selection reaches the provider) | S | Full (it is the privacy line) | **#54** and #53 |
| 6 | Map the editors to places: Current state, use case, sections (`current`); peek fields (`plain`); client wording (`client_message`) | S | Light | 3 and 4 |
| 7 | Store-aware client check (real codes and names); Draft email place with the outside-recipient rule | S | Full (client check) | store wiring, **#50** |
| 8 | The end-to-end browser tests for each option's flow with the fake provider | M | Light | 3, 4 |

## 6a. Keyboard, focus, announcements and design roles (slices 2 and 3)
Roles are from `docs/DESIGN-SYSTEM.md`; the build uses roles and tokens only, no raw colour and no fixed pixel numbers.
- **Opening.** Alt+/ or the toolbar AI button opens the list. In the list: Up and Down move, Enter chooses, Esc closes. In the Ask... box Enter sends and Esc closes it. The list is a menu, not a trap: Tab closes it and moves on.
- **Focus on open.** The list puts focus on its first item. When a card opens, focus goes to the card's heading line (the option name), so a keyboard user reads the result first. While running, focus stays on Stop.
- **Tab order.** Bubble buttons, then the card's four buttons: Accept, Discard, Try again, Show changes. The card is not a focus trap.
- **Focus return.** Accept, Discard and Esc return focus to the editor at the changed place (for Discard and Esc, where the selection was). Try again keeps focus on its own button, and the new card takes it when ready. Show changes keeps focus on its link.
- **Live region.** One polite live region per card, never assertive (nothing here is urgent and Accept is never done for the person). It says: "Working on it", "Suggestion ready", and a failed or off line as the same plain text shown on the card. The state words are text, not only colour.
- **Design roles.** Card: `--surface`, one-pixel `--border`, `--radius-lg`, `--shadow`; text `--text`, notes `--text-muted`. Accept is the main pill (`.again`, `--pill-*`); Discard and Try again are outline pills; Show changes is a link (`--link`). Focus ring `--focus`. Bubble AI zone: the bubble's existing surface, with the AI zone divided by `--border`. States off and not signed in: a greyed button and the plain line "Connect Claude in Settings to use this", real text at 4.5 to 1 (it carries the message). Busy: the card's running state with Stop. No status colour (red, amber, green, blue) for AI: each already has one meaning. Targets at least 24 px. Running motion uses `--dur-*` and stops under `prefers-reduced-motion`.

**Done-when, slice 2 (the card):** each of the five states has a browser test; keyboard path (Tab order, Enter, Esc) passes; focus returns as above after Accept, Discard and Esc; the announcement text for working, ready, failed and off is asserted; the off line is text at 4.5 to 1; reduced motion stops the running state; the design-review checklist is measured in the live page at 1400 and 900 px, light and dark (no phone widths), before the slice is called done.

**Done-when, slice 3 (the bubble):** one browser test per key (Alt+/, arrows, Enter, Esc, Tab); the bubble stays inside the window at 1400 and 900 px, light and dark; focus returns to the editor after each exit; the AI zone uses roles only (no status colour); the greyed state before a provider is text at 4.5 to 1; the same design-review checklist, measured in the live page, before the slice is called done.

## 7. Open questions
1. **Where does the card live?** Recommendation: on the page (the route is one-shot: ask, check, return the cleaned text and notes). The Python `AiSession` stays as the tested rules and the page follows them; this keeps the guarded route thin and stateless.
2. **Should the menu show before a provider exists?** Recommendation: yes. It shows, greyed, with "Connect Claude in Settings to use this", so slices 1 to 3 can ship in v0.3 without waiting for #53.
3. **How strict is the client check?** Recommendation: keep it blocking, but make the message name what was found ("it added the word health") instead of a bare "Try again"; creaite compares with the project's own health reason, which we can do in slice 7.
4. **Draft email with an outside recipient.** Recommendation: AI is off there until #50 wires the store-aware check; own-domain emails get Improve and Tone now.
5. **Make into: does the new item keep a link back to the passage?** Recommendation: no link, just the source label of the field (for example "From Current state"), so no passage is stored twice.
