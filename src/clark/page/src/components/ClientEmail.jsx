// Draft email on the published page (#51; FR-94, FR-95): the editor's Draft email component, fed by the builder that runs in the
// page (logic/draftEmailBuild.js). No server, no model and no history: nothing leaves the page but what the reader copies, and a
// draft never carries a change into clark. It exists only in a published file that carries a project contact. It offers the
// open actions, risks, issues and decisions that were published, and the email goes To that contact.
import { useState } from "preact/hooks";
import { signal } from "@preact/signals";
import { data, contact, asAt, fromFile } from "../stores/report.js";
import { DraftEmail } from "./DraftEmail.jsx";
import { Icon } from "./Icon.jsx";
import { itemsOf, build, barred, NO_SENDER_HERE } from "../logic/draftEmailBuild.js";
import { todayIso, nowStamp } from "../workItems.js";
import { buildOptions, startPicks } from "../logic/draftEmail.js";

const opened = signal(null);            // null, or the ids ticked to start with

/** Whether this page can draft an email: a published file that carries a contact. */
export const canDraft = () => fromFile.value && !!contact.value;
/** Open the Draft email on these ids (none: every item offered). */
export function openEmail(ids) { opened.value = ids && ids.length ? ids.slice() : []; }

function offered() { return itemsOf(data.value).filter((i) => !barred(i, true)); }
function now() { return `${asAt.value || todayIso()}${nowStamp().slice(10)}`; }

function Dialog({ ids }) {
  const items = offered(), list = items.map((i) => ({ id: i.id, text: i.text }));
  const [state, setState] = useState({ mode: "update_request", picked: startPicks(list, ids.length ? ids.filter((x) => items.some((i) => i.id === x)) : null), replyBy: "", unblocks: "", includeUpdate: false });
  const [from, setFrom] = useState("");
  const c = contact.value, project = data.value.project;
  const draft = build({ ...buildOptions(state), items, name: c.name, email: c.email, from, own_domains: [], sender_words: NO_SENDER_HERE, now: now(), project_names: { [project.code]: project.name } });
  return (
    <div class="cde-back" onClick={(e) => { if (e.target === e.currentTarget) opened.value = null; }}>
      <div class="cde-box">
        <label class="cde-from">Your name <input type="text" value={from} autocomplete="off" onInput={(e) => setFrom(e.currentTarget.value)} /></label>
        <DraftEmail items={list} state={state} draft={draft} today={asAt.value} noSent={true} onChange={setState} onClose={() => { opened.value = null; }} />
      </div>
    </div>
  );
}

/** The dialog, when open. */
export function ClientEmail() {
  if (opened.value === null || !canDraft() || !data.value) return null;
  return <Dialog key={opened.value.join(",")} ids={opened.value} />;
}

/** The button that opens it on every item offered, for the Work items page head. */
export function ClientEmailButton() {
  if (!canDraft()) return null;
  return <button type="button" class="btn cde-open" onClick={() => openEmail([])}><Icon name="mail" /> Draft email</button>;
}

/** The small envelope on one row. */
export function RowEmail({ id }) {
  if (!canDraft()) return null;
  return <button type="button" class="cde-row" aria-label={`Draft email about ${id}`} title="Draft email about this item" onClick={() => openEmail([id])}><Icon name="mail" /></button>;
}
