# Project brief: clark

Written by the project lead on 27-10-2026, revised the same day from the owner's notes, and approved by the owner on 27-10-2026 ("approve the brief, client brand local only"; see `DECISIONS.md`). The owner's words: "We'll define this as we go." So this brief sets direction, not detail.

## Goal

clark is a **report editor** for programme managers. You keep the project's work items and milestones in clark, edit them, and publish a report as a **Word document** or as an **HTML reporting dashboard** that clients and the team can review. clark is a reporting tool. The owner is the first user, and it is built so other programme managers can use it too.

## Who it is for

- **Programme and project managers.** They keep the work items and write and publish the reports.
- **Clients and the team.** They read the published report or the HTML dashboard. They don't edit it.
- Nothing in clark assumes one person, one laptop or one organisation, so branding and set-up belong to each user.

## What it does

- **Work items and milestones in a database.** Actions, risks, issues, decisions and milestones are kept in clark's own database.
- **Edit in a work items view.** This is based on creaite's peek, the side panel for viewing and changing an item. It includes generating milestones.
- **Import and export.** Read work items in from Excel and write them back out. Read from Word and write to Word. The likely start is input from Excel, edits in the work items view, then export.
- **ask clark.** An assistant inside clark, based on ask creaite.
- **Publish.** A report as a Word document, or as a self-contained HTML dashboard page.

## What it reuses from creaite

As much as possible, including:
- the report builder and its engine
- the peek and the work items view
- milestone generation
- ask creaite, which becomes ask clark
- Word and HTML publishing
- the Word templates

Each copy is proposed first in the reuse record and copied from a release tag once the owner approves it. ask creaite rests on creaite's guarded files (`live_server`, `reach`, `filechange`, `permissions`). Copies of those are marked and read by a second reader before use. creaite's concepts that clark doesn't need (the mail and Teams check, the register file) are left out, and clark's data model is decided here, not inherited.

## Out of scope (for now)

- Reading mail, Teams, calendars or meeting transcripts.
- Sending by email, Teams or any message. **Changed 27-10-2026, approved by the owner 28-10-2026:** Publish may also put the report in the client's SharePoint folder, but only when the user ticks "To client" for that publish (Local is always used). It does this by copying the file into the client folder that the user's OneDrive app already syncs, so clark holds no Microsoft sign-in and no network code.
- Anything from creaite's private repos, and any real client, company or person's name. All data is fictional demo data.

## Decided

- **Name:** clark. It's lower case and is written "clark" in user text, so a line never starts with it, the same as "ask clark".
- **Wording:** creaite's plain-words rules apply to everything a user reads.

## Still to define

- **Input:** likely Excel, then edits in the work items view, then export. The details are to be defined.
- **Data model:** which items, which fields, and how milestones are generated.
- **What the HTML dashboard shows clients versus the team.** This matters because client-safe output is a creaite guarded area.

## First step

**A new design system for clark's client-facing output**: the HTML dashboard and the reports. It covers colours, type, components and page layouts, so the dashboard, the Word report and the app look like one product. It uses a fictional demo brand, and each user can rebrand it.

## First milestone

To be proposed once the design system is agreed. It will be small, testable and use demo data only.
