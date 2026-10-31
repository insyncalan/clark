# Client comments on the published page: options

Written by a teammate, 28-10-2026. The owner's words: "work items should be editable in customer view by the customer. Also, use cases... we need a method to capture these comments - perhaps first to the database then auto saved to the excel? Let's add this as a requirements on the board and in the brd and figure out how". This changes "view only" for the client page.

**Decided since (the owner, 28-10-2026, #21 and #22):** "Clients can only add comments to work items also". Clients comment on work items and on use cases, and **change nothing**. So a client file may only carry comments. Any other field in it is refused, and the file is reported. Which way the comments come back (the options below) is still open: D-1, for the owner's decision.

## The options

**A. A comments file through the shared folder (the project lead's working idea).**
- The page stays one self-contained file with no server.
- The client adds comments, then clicks "Save my comments", which saves a small comments file.
- The file goes back into the client's SharePoint folder.
- clark reads that folder through the PM's OneDrive sync and stages the comments. The PM accepts or rejects each one.

**B. Hosted:** a small web service or form we run.
- It gives real sign-in, live updates, and no files to move.
- But it sends data out, costs money every month, has to be secured and watched, and breaks "the data stays on the PM's machine".
- Every part of it is the owner's decision.

**C. Microsoft Forms or Lists in the client's or our SharePoint.**
- Forms can save its answers to an Excel file in SharePoint, which clark could read through the sync with no stored sign-in.
- But editing leaves the page for a separate form, so it isn't the interactive page the owner asked for.
- External clients usually answer as anonymous users, so the PM doesn't learn who answered.
- Lists needs guest access to the tenant and a sign-in for clark to read it.

## How A holds up against each question

| Question | Answer for A |
|---|---|
| **Getting the file back** | SharePoint usually downloads an .html file rather than showing it, so the client opens the report on their own machine. Saving the comments straight into the SharePoint folder only works in Chrome or Edge, and only if the client also syncs that folder. **So the dependable path is to download the comments file and drop it into the shared folder.** Saving straight into the folder is a shortcut when the browser allows it. The page explains both in plain words |
| **Who the client is** | The gate is SharePoint: only people the folder is shared with can put a file there. The comments file carries the name the client typed, which is a claim, not proof. clark shows it as "from (as entered)". Real identity needs option B |
| **Tampering** | Signing the file would only be pretend security, because any key inside the page can be read by anyone who has the page. Protection comes from what clark does when it reads the file. The file must name the report it answers (the published file's SHA-256 from `publications`) and the project. Only allowed fields are read; anything else is refused. Text is plain (no HTML), with size limits (256 KB a file, 2,000 characters a comment). **Nothing applies until the PM accepts it**, and clark records each file's SHA-256 so the same file is never applied twice |
| **Two clients commenting** | Each client saves their own file (their name and the time are in the file name). clark stages each file separately. Comments only add, so two files never clash |
| **What a client may send** | **Decided: comments only**, on a published work item or use case (the owner, #21 and #22). A comment names the item's id and must be on a row that was published. A file with any other field is refused whole, so there is no per-project field list |
| **Conflicts with the PM's own edits** | None: a comment changes no field. If the item has changed since publishing, clark shows the comment next to what the client saw and the item now |
| **What goes out and comes in** | Outbound, the published page holds only rows the editor chose (one output, #24). Inbound, client text is outside text: ask clark treats it as information, never as instructions, and the "confirm first" rule applies to any change ask clark proposes from it. An accepted client comment is shown to the client again only if the PM keeps it client-visible |
| **What goes into Excel, and when** | Only after the PM accepts it, as the owner suggested: "first to the database then auto saved to the excel". After each accept, clark refreshes the project's workbook automatically. If the workbook has edits not yet imported, clark doesn't overwrite them; it asks the PM to import first. Staged comments that haven't been accepted never reach Excel |
| **How clark notices** | While clark is running, it checks the project's shared folder every few minutes and when it starts. It only reads there, and never moves or deletes the client's file. A file it has already handled is recognised by its SHA-256 |

## Recommendation

**Option A**, with the download-and-drop path as the standard and the PM accepting every comment. It keeps the interactive page, needs no server, no new account and no stored sign-in, and costs nothing. Its limit is identity: clark knows only that someone with access to the folder sent the file, and who they say they are. If the owner needs to know for certain who said what, that is option B, and a security and money decision for him.

## For the backlog (after milestone 1)
1. The comments file format and its checks: comments only, any other field refuses the file (Full review: it's an input from outside).
2. Comment boxes on the published page for work items and use cases, with "Save my comments".
3. Watching the shared folder and the staged comments view for the PM, with accept and reject.
4. Refreshing Excel automatically after an accept.
