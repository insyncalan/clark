# Design system: components clark adds

The entries for the parts of clark that the main design system (`docs/DESIGN-SYSTEM.md`, section 5) does not describe yet. Each entry says what the part is, how it looks (tokens only, from the committed look), its states, what happens at 900 px, and what is not settled. A person's own look (`system/branding/`) only changes token values, so none of these entries names a brand, a logo or a picture.

Every entry is checked on the live page at 1400 and 900 px, in light and dark, against the checks in section 7 of the main design system: text 4.5 to 1, controls and rings 3 to 1, text at least 13 px, targets at least 24 px, no sideways scroll of the page. "Not yet checked" is written where a check has not been made. The 'text under 12 px' figures in the entries were measured with the 12 px caption size as the floor, which is what the measuring script reports; text between 12 and 13 px has not been measured separately against that 13 px floor, so each entry lists it under 'Not yet checked'.

**How the figures were taken.** Each 'Measured' line comes from a headless browser run over the open page with fictional demo data: a script reads the page's own colours and sizes and reports text below 4.5 to 1 contrast, text under 12 px, controls under 24 px, elements that overflow their box and sideways scroll of the page. The board, Calendar, Legend and timeline were measured on the 0.2.1 release (the v0.2.1 tag); the profile menu on the branch of the Appearance and name-and-email change. The figures are repeatable with the same script; they are not part of the test suite.

**Status of the set.** This is the first batch: five entries. The rest are still to write: the peek and Sneak peek, ask clark (panel, bubbles, chips), the AI suggestion card, the Add tiles and the growing Add button, the Forecast state, the filter bar and its pills, form controls, dialogs and toasts, the Help view, use case rows (and the new Use cases page), editor tables against the report table, dark mode, empty states, keyboard shortcuts, and tooltips. Phone width is out of scope for now (laptop only).

## 1. The Work items board
Cards in lanes, with the lanes grouped by status, due date, priority or another field.
- **Look.** A card is `--surface` with a one-pixel `--grey-200` edge, `--radius` and `--shadow`; padding 10 by 12 px. Top line: the item's id in `--text-muted` (13 px), the move button on the right. Title: 14 px, at most three lines, then cut. Foot: the due date and the status chip (tint, dot and word) on the right. A finished card's title is `--text-muted`. A selected card has a `--brand-blue` edge. A lane heading is 13 px `--text-muted`.
- **Colour.** Status, due and priority lanes carry the colour of their state on the heading. The word is always there: colour is never the only cue.
- **States.** Rest; hover (the move button goes from faint to full); focus (2 px `--brand-blue` ring, offset 2 px, on the card's main area and on the move button); selected; being dragged (half opacity). In Edit a card can be dragged; in View it cannot.
- **Move button.** 24 px square, 16 px icon, faint at rest and full on hover or focus: the keyboard way to move a card.
- **900 px.** The lanes scroll sideways inside the board; the page itself never scrolls sideways. The board is the designed exception to "no horizontal scroll at 900 px". The headings stay pinned under the top bar while the board scrolls.
- **Measured** (light and dark, both widths): contrast failures 0, text under 12 px 0, controls under 24 px 0, no sideways page scroll.
- **Not yet checked.** The focus ring on a card, the disabled and error states, reduced motion on the drag, and the peek opened from the board, and text between 12 and 13 px against the 13 px floor.
- **Open points.** The lane headings sit under the page title with no level in between (a heading-order gap). A column that does not fit at 900 px has no cue that it is there. In full screen the top bar is hidden, so the tab bar goes with it.

## 2. The profile menu
The round button at the right of the top bar and its menu.
- **Status of this entry.** It describes the profile menu as built for the Appearance and name-and-email change, which is on main. The 'Measured' line was taken on the branch before it merged.
- **Structure, top to bottom.** The person's name in bold with the email under it (or only the name), or the link "Add your name in Settings" when neither is set; the actions (Publish, Preview the page in a new tab, Export to Excel); a separator; the group named Appearance with System, Light and Dark, the one in use ticked; a separator; Settings and Help.
- **Look.** A menu panel on `--surface`, `--radius-lg`, `--shadow`; rows with a hover and keyboard highlight; the tick is `--status-blue-text` in a fixed 1.2 em box so the words line up; the group name is a quiet 13 px `--text-muted` line.
- **For a screen reader.** The three Appearance choices are radio items inside one group named Appearance, so each is read as "Appearance, Light, radio, checked".
- **Keys.** Arrow keys, Home and End move between rows; Enter chooses; Escape closes and puts focus back on the round button.
- **900 px.** Long names and emails are cut with an ellipsis and the full text is the tooltip; the menu keeps to 280 px for them.
- **Measured** (both widths, light and dark): contrast failures 0, controls under 24 px 0, text under 12 px 0, no sideways page scroll.
- **Not yet checked.** Disabled rows (Publish and Export wait until the report has loaded), reduced motion, and the focus ring on every row, and text between 12 and 13 px against the 13 px floor.
- **Open points.** "Preview the page in a new tab" wraps to two lines at 200 px; the menu needs a stated minimum width.

## 3. The milestone Calendar (Week, Month, Quarter)
- **Look.** Seven columns divided by one-pixel `--grey-200` lines. Weekend and out-of-month days sit on `--grey-50`. Today's number is a filled `--brand-blue` pill with `--text-on-brand`. Day numbers are 13 px `--text-muted`. A milestone in a day is a small row (14 px icon and the name, cut with an ellipsis); a milestone whose date has moved is drawn as a dashed `--status-red` outline with red text and no fill.
- **Scales.** A button group switches Week, Month and Quarter; the one in use has `aria-current`, a tinted fill and a `--brand-blue` edge. Day heights: Week 180 px, Month 88 px, Quarter 44 px with the name hidden (icon only, three months across).
- **States.** Hover tints the milestone (`--brand-blue-tint`); focus is a 2 px `--brand-blue` ring on a milestone and on the scale buttons. In a published file a milestone is text, not a button: no hover, default cursor.
- **900 px.** Day height 64 px; names are hidden (icons only); the Quarter view becomes one column. A name hidden at 900 px is reachable only by opening the milestone.
- **Measured** (both widths, light and dark): contrast failures 0, text under 12 px 0, controls under 24 px 0, no sideways page scroll.
- **Not yet checked.** Reduced motion on the scale change, arrow keys between days, and the contrast of the dashed moved outline on a tinted day, and text between 12 and 13 px against the 13 px floor.
- **Open points.** Whether a hidden name at 900 px should get a tooltip.

## 4. The milestone Legend
- **Look.** A quiet button at the right above the timeline: icon and word in `--text-muted` 13 px, at least 28 px high and wide. It opens a panel (320 px, or the window width less 48 px) on `--surface` with a `--grey-200` edge, `--radius-lg` and `--shadow`: a row for each marker with a 20 px symbol and the words, and a second block below a rule for the symbols (the moved outline, the Today line).
- **States.** Opens on hover or keyboard focus and closes when both leave; Escape shuts it until hover or focus moves on. Hover turns the button text from `--text-muted` to `--text`; focus is a 2 px `--brand-blue` ring. The panel is not a dialog: it holds no controls and does not trap focus.
- **Motion.** The panel fades and moves 4 px; reduced motion is not yet checked.
- **Measured** (both widths, light and dark): contrast failures 0, text under 12 px 0, controls under 24 px 0.
- **Open points.** The panel opens upward, so near the top of the page it can leave the window: check at 900 px with the page at the top. Opening on hover is a mouse habit; the keyboard opens it by focus.

## 5. Milestone markers and Movement (the timeline)
- **Look.** A strip on `--grey-50` between two `--grey-200` rules; month lines with 13 px `--text-muted` names; a 2 px `--grey-300` line through the middle; Today is a 2 px `--brand-navy` line with the word "Today" in `--status-blue-text` on a `--surface` chip. A marker is a 24 px round target with a 16 px icon, scaling to 1.18 on hover or focus. A label is the name in medium weight with the date under it, drawn above the Today line on the strip's own colour so no line is drawn through a name or a date. Green label text means on time; red means moved or late, and the words say it too.
- **Moved milestone.** A 14 px dashed `--status-red` ghost circle at the old date and a dashed red connector to the new one: shapes, not only colour.
- **States.** Hover tints the label; focus is a 2 px `--brand-blue` ring, offset 2 px. In a published file a marker is text: no hover, default cursor.
- **Scroll.** The strip scrolls sideways inside its own box and can be made taller (up to 900 px); the page does not scroll sideways.
- **Measured** (both widths, light and dark): contrast failures 0, text under 12 px 0, controls under 24 px 0, no sideways page scroll.
- **Not yet checked.** Reduced motion on the hover scale, and two labels within a few days of each other, and text between 12 and 13 px against the 13 px floor.
- **Open points.** There is no rule yet for two close labels (stack them, hide one, or collide).
