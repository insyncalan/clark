# The design system

The rules for how clark looks: the tokens a look sets, how a person's own look layers over the committed one, and the checks every screen passes. It describes what is committed in this repo, which carries no client's name, logo or picture. A person's own look lives only in `system/branding/`, which git ignores (`RULES.md`).

Owner: the Product Manager (the wording). The Designer proposes; the Product Manager decides; the owner decides anything visible.

## 1. The two layers
1. **The committed look.** `src/clark/brand/tokens.css` (the values) and the "look" section at the end of `src/clark/page/shell.css` (the pill buttons, the header, the type). Both are built into `page.html` and `page-view.html` by `dev/tools/build_page.py`. Nothing loads from the internet: the two typefaces are vendored and inlined as data.
2. **A person's own look (optional).** A `tokens.css` in `system/branding/` with the same token names. Its text is added after the committed look as a second style block, so the same names take its values. A name it leaves out keeps the committed value. The top bar's clark icon is hidden under an own look (`--logo-icon: none`); the own look sets it back to `inline-block` if it wants it.

An own look may also add rules (a logo picture, a still picture for the home banner). Those pictures are `data:` images inside its own `tokens.css`. They never enter the committed files: `tests/test_no_client_image.py` allows only clark's own icon set.

## 2. The token contract
`tests/test_page.py` (`CONTRACT`) lists the names a look may set; the committed look sets all of them. The page also uses a few more, which a look may set too: `--flash` (the brief highlight on a changed row), `--white`, `--brand-blue-strong`, `--brand-blue-tint`, `--brand-charcoal`, `--status-grey` and `--logo-icon`.

| Group | Tokens | What they are for |
|-------|--------|-------------------|
| Brand | `--brand-navy` `--brand-blue` `--brand-blue-strong` `--brand-blue-tint` `--brand-ink` `--brand-cyan` `--brand-charcoal` | The header bar (navy), links, focus rings and the selected state (blue), the underline of the open tab (cyan) |
| Greys | `--grey-50` to `--grey-700`, `--white`, `--black` | Page, cards, rules and muted text |
| Roles | `--bg` `--surface` `--surface-muted` `--text` `--text-muted` `--heading` `--border` `--link` `--focus` `--text-on-brand` | What a screen uses. Use a role, not a grey, wherever there is one |
| Status | `--status-green` `-amber` `-red` `-blue` `-grey`, each with a `-tint` and a `-text` | Red, amber, green and blue keep one meaning each in every look |
| Data | `--data-1` to `--data-6` | Chart and series colours |
| Pill and bar | `--pill-bg` `--pill-color` `--pill-fg` `--pill-glow` `--pill-glow-hover` `--bar-end` `--accent-line` | The main button, the pressed switch, the header's lift to the right and the tab underline |
| Type | `--font` `--font-head` `--font-label`, `--size-*`, `--leading`, `--weight-*`, `--tracking-caps` | One text face, one heading face, one label face |
| Shape and space | `--radius-sm` `--radius` `--radius-lg` `--radius-pill`, `--space-1` to `--space-8`, `--max-width`, `--topbar` | Corners and spacing: use the tokens, not numbers |
| Depth and motion | `--shadow`, `--ease-*`, `--dur-*`, `--stagger` | See section 6 |
| Pictures | `--image-cover` `--image-logo` `--image-fade` `--art-home` `--art-home-height` | Empty and flat by default; only an own look fills them. `--image-logo` is the logo at the right of the Client Requested Report View's cover band |
| Profile circle | `--profile-bg` `--profile-fg` `--profile-ring` `--profile-size` | The initials circle in the header |

**Rule: no raw colour in a rule.** A rule in `shell.css` or a component uses a token. A new colour is a new token in the contract, with a dark value.

## 3. Colour
- **Light is the default.** With no `data-theme` the page is light. `data-theme=dark` is the chosen dark look; `data-theme=auto` follows the computer's setting.
- **Dark values are written twice** (for `dark` and for `auto` inside the colour-scheme query), because CSS cannot share them. `tests/test_page.py` keeps the two copies equal. The surfaces, greys, text, brand blue and its tint, status and data colours, `--flash` and `--shadow` each have a dark value that differs from the light one (`tests/test_work_filters.py` checks it). A few keep one value in both modes on purpose: `--brand-cyan`, `--brand-charcoal`, `--black`, the profile circle and the pill, bar and picture tokens.
- **Contrast is measured, never judged by eye.** Text 4.5 to 1; icons, focus rings and control edges 3 to 1; in light and dark (`tests/test_dark_contrast.py`, `tests/test_app_files.py`). On the brand colour, text is `--text-on-brand`, which is white in light mode and dark in dark mode; the pill has its own `--pill-fg`.
- **One meaning per colour.** Red is overdue or off track, amber is at risk or look soon, green is on track or done, blue is information or not started. Colour is never the only cue: a status also has a word or a shape.
- **The header follows `--brand-navy`.** An own look that sets only that token still colours the bar; `--bar-end` is the soft lift to the right and an own look may set it to the same colour for a flat bar.

## 4. Type
- **Text:** the text face (`--font`), regular weight. **Headings and big figures:** the heading face (`--font-head`), extra-bold. **The small line above a title:** the label face, bold capitals with wide spacing. **Buttons:** extra-bold.
- **The floor is 13 px** for any text the page draws, SVG chart text included (`tests/test_font.py` parses every size in use). `--size-caption` (12 px) is a contract token a look may set; the committed page does not use it for text.
- Line length at most about 80 characters; no skipped heading level; no one-word last lines.
- **Fonts are vendored:** `vendor/fonts/<family>/` holds the woff2 files, the licence and a manifest with each file's SHA-256 (`tests/test_font.py`). A look that falls back to a system face does so only for characters outside the Latin range.

## 5. Components
- **Main button (`.again`) and the pressed switch or filter:** the pill gradient with `--pill-fg` text, a soft glow, a small lift on hover. Other buttons are pill-shaped outlines. Targets are at least 24 px.
- **Tabs:** muted text, the open tab white with a gradient underline. **Header:** `--brand-navy` with the lift to the right; the clark word and icon on the left.
- **Cards and frames:** `--surface`, a one-pixel `--grey-200` edge, `--radius-lg`, `--shadow`. **Status chips:** the tint behind the `-text` colour, a dot, and the word.
- **Tables:** a header row in capitals, one hairline per row, dates `DD-MM-YYYY` on one line. The Due column is wide enough for a date in the text face at 900 px.
- **Empty states** say what is missing and the next step. A view filtered to nothing says why.
- **Home banner:** an empty strip above "No project open"; `--art-home` and `--art-home-height` fill it in an own look. It is a still picture, never animated.
- **Components clark adds** (the Work items board, the profile menu, the milestone Calendar, Legend and timeline, and the rest as they are written) are described in `docs/DESIGN-SYSTEM-COMPONENTS.md`.

## 6. Motion
Only while something is working or changing state. Durations come from `--dur-*`; entrances use `--ease-enter`; nothing bounces. Anything that animates is switched off under `prefers-reduced-motion`.

## 7. Checks for every screen
Look at the live page, never a static picture, at **1400 px and 900 px**, in **light and dark** (laptop widths only for now). Then:
1. Text 4.5 to 1 and controls 3 to 1, measured.
2. Nothing under 13 px; no horizontal scroll of the page, a table or a row at 900 px (the Work items board's lanes and the milestone timeline strip scroll inside their own boxes: those are the exceptions).
3. The thing to do is the loudest thing on the first screen.
4. One label says a thing once; no stray separators; no bare dashes for empty values.
5. Plain words: no file path, script name, extension or jargon where a person reads. Dates `DD-MM-YYYY`, times 24-hour, British English.
6. The sort column stays on screen at 900 px.

A visible change waits for the owner's before-and-after sign-off.

## 8. How a look is changed
- **The committed look:** change `src/clark/brand/tokens.css` and the look section of `shell.css`, run `python3 dev/tools/build_page.py`, and run `python3 dev/run_tests.py test_page test_font test_dark_contrast test_app_files test_no_client_image test_no_real_names`. Show before and after.
- **An own look:** edit the `tokens.css` in `system/branding/`. No code changes. The committed repo is never touched.
- **A new token:** add it to the committed tokens (light and both dark copies), to `CONTRACT`, and to this table.
