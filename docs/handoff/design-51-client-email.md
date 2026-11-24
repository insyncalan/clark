# Design: #51 Draft email on the client page

Written by a teammate's agent, 31-10-2026. **Built in PR 31 (not merged when this note was written).** PR 31 builds the Publish-screen field, the per-project storage and the guarded route. Not built: a per-item ticked set, and an undo button in the Publish dialog. **Sources:** #51 and the owner's earlier hold (28-10-2026: "Put this on hold for the client for now - editor only"), BRD FR-94, FR-95 and D-6, and the PR 31 diff.

**The owner lifted the hold on 31-10-2026** (Decisions, below). BRD D-6 still says "On hold" and needs updating.

## Decisions (the owner, 31-10-2026)
1. **The 28-10 hold is lifted.** Build it.
2. **One outside contact per project**, not chosen at each publish. It is a project setting (schema version 3: `projects.contact_name`, `projects.contact_email`), set on the Publish screen and saved as an ordinary step with history and Undo.
3. **No warning** on the Publish screen that the address will sit in the client's file.

Per-item ticked sets were not asked for; "this item" and "all open items" stay as built. The built dialog has a tick box per item, which is not the same as a saved ticked set.

## 1. What the person sees
The client opens a published report. If the file carries a contact, the Work items page shows a **Draft email** button, and each row shows a small **envelope** by its title. The envelope opens the draft on that item alone; the button opens it on every open item. The client types their name (it signs the email), picks a kind (update request, chase, decision), and sees the email addressed to the contact. They copy it out with **Copy for Outlook**, **Copy as text**, or **Open in mail app** (short emails only). A file with no contact shows no button and no envelope. Nothing is sent by clark.

## 2. Where the contact is set
On the Publish screen, two fields (the contact's name and address), kept per project and saved as an ordinary step with history and Undo. PR 31 builds the field (`edit/ClientContact.jsx` on `Publish.jsx`), the storage (schema version 3 migration) and the route `POST /api/client-contact` (`publish_flow.py` and `server.py`, body limit 1 KB). The route is guarded by tier, because it writes a person's address that later goes into a client file. It refuses without the session token, refuses a bad or team address with a plain message and stores nothing else.

## 3. What the client page may and may not show
The page holds only what publish kept, so a hidden row or an internal note is not in the file to be drafted from. On top of that:
- Rows whose text, response or update contain "confidential" or "restricted" (read through the look-alike scan) are never offered.
- A row flagged sensitive is left out when the contact is outside the team's domains.
- The contact must be one plain address (no spaces, no list, no angle brackets) and **must not be on the team's own domains**. The route refuses a team address or a bad one with a plain message. If one is written past the route, `build()` drops it silently and the file carries no contact.
- **Own domains are a list in the settings file (`settings.own_domains`) with no screen.** Until someone sets it, nothing counts as a team address, so the team-address rule does not apply on its own. A screen for it is not built.
- Name and address are one line of plain text; the name is cut to 80 characters.

## 4. The exact change to `publish.py` (a guarded file)
Four edits, 18 lines in `publish.py`. PR 31's other guarded files are `store.py` (migration step 3), `publish_flow.py`, `settings.py` and the schema.
1. `import draft_email`.
2. `build()` and `publish()` gain `contact=None, own_domains=()`; `publish()` passes them on.
3. In `build()`, after `select()` and `add_glance()`, the contact goes through `draft_email.client_contact(...)`; if it passes, it is set as `published["contact"]`.
4. `data_block()` adds a `contact` key to the JSON block, only when there is one.

**This is not a change to the publish scan.** `select()`, the client checks (#43) and every scan that decides which rows reach the file are untouched, and no row is added, widened or let through. The change adds one new, separate field to the data block, checked by its own function. A reader can judge it by confirming: `select()` is not in the diff; a file built with no contact is byte for byte what it was before (test needed, below); the `<>&` escaping in `data_block()` still applies to the new key.

## 5. What the draft contains, and how it leaves
The page builder (`draftEmailBuild.js`) is a port of `draft_email.py`: same wording and rules, run in the browser, no server and no model. It takes the published rows (id, text, due, owner, status, latest update) and the contact, and returns a subject, an HTML body and a plain-text body. A test builds the same email in Python and in the page and compares them. Copy for Outlook puts the HTML on the clipboard; Copy as text puts the plain text; Open in mail app uses a `mailto:` link for a short email. The page asks for nothing outside itself. A draft never carries a change into clark (FR-95); edits come back only by the changes file.

## 6. Risks
- **A contact address is personal data in a published file.** It is readable by anyone who holds the file: the client and anyone the client forwards it to. The file is the client's once handed over; clark cannot recall it. The Publish field should say so in plain words, and the address should be the one the user chose for this purpose.
- The page port can drift from `draft_email.py`; the comparison test is the guard.
- A look-alike or confidential word missed by the scan would put a row in an email; the scan is the same as the editor's.
- The email shows the client the same rows they can already see; it adds no row.

## 7. Tests
**`tests/test_client_email.py` (15):** Python and page builders agree; hidden, confidential and look-alike rows never offered; text read as the Python scan reads it; published rows become items; contact must be one plain address; outside contact kept and cut; team, bad or no address never kept; the file carries the contact and no team address or hidden marker; the dialog drafts to the contact from published rows only; a name is needed, then the email is ready; no kind or set of items puts a hidden row, an internal note or a team address in an email; the envelope opens that item alone; the page asks for nothing outside itself; no button without a contact; fit at 1400 and 900, light and dark.

**`tests/test_client_contact.py` (26):** the route refuses without the token and refuses a bad or team address in plain words, changing nothing; save then undo puts the old value back; one contact per project; a file built without a contact is what it was before and has no button; the saved contact is in the file and in the client copy; a team address written past the route never reaches a file; no hidden or sensitive row reaches a file that carries a contact; the published page has no contact field or route; the field shows values as text only; fit at 1400 and 900, light and dark.

**Still needed:**
- A screen for the own-domains setting, and a test that a team address is refused once it is set from there.
- The ticked-set path, if it is ever wanted.

## 8. Tier
**Full.** It edits `publish.py` and (when built) `server.py`, both guarded, and its output goes to a client. Two readers are needed, one of them reading section 4 against the publish scan.

## 9. Questions for the owner, and where they stand
1. **Is the 28-10 hold lifted?** Yes, on 31-10-2026.
2. **One contact per project, or chosen at each publish?** One per project.
3. **Should the Publish screen warn that the address will sit in the client's file?** No.
4. **Per-item ticked sets?** Not asked for; "this item" and "all open items" are enough for now.

**Recommendation.** The note's work is built in PR 31, which needs two readers (section 8). Merge this note after, or with, that PR. Next step: decide whether the own-domains setting needs a screen.
