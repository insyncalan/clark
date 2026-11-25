// Row 1181: an Action's Details in the peek. Self-contained; Peek.jsx places it (in place of the shared ItemFields for kind=action) and
// puts the Latest update above it. The rows are Workstream, Milestone, Raised (read only, with its hint), then the Client visible line.
// Type, Use case, Client wording and Last reviewed are not drawn for an action (the ticket's 'Decide before build': the simplest choice, dropped for actions only).
// Row 1256: a risk and an issue use this body too and keep their Use case row (decided in the ticket: keep it); Type, Client wording and Last reviewed are not drawn.
import { PeekDetails } from "./PeekDetails.jsx";
import { Icon } from "./Icon.jsx";
import { showDate } from "../workItems.js";
import { iconClass } from "../iconColours.js";

const DASH = "—";
const text = (v) => (v === null || v === undefined || v === "" ? DASH : String(v));

function ARow({ name, icon, tone = "b", children, data }) {
  return <div class="pk-row" data-row={data || undefined}><dt>{icon ? <span class={`pk-rowic ${iconClass(tone)}`}><Icon name={icon} /></span> : null}{name}</dt><dd>{children}</dd></div>;
}

/** The date an action was raised: live data carries `raised` (with a review flag), a published file carries `raised_on`. */
export const raisedOf = (row) => (typeof row.not_reviewed === "boolean" ? row.raised : row.raised_on) || "";

/** The one-line summary shown while Details is closed. */
export function actionSummary(row, editing) {
  const raised = raisedOf(row);
  return [row.workstream, row.milestone, raised ? `Raised ${showDate(raised)}` : "", editing ? (row.client ? "Client visible" : "Client not visible") : ""];
}

/** The Client visible line in View and in a published file: the same eye and words as the Edit line, read only. A published file never draws it (row 1466): the caller leaves it out when `onFile`. */
export function ClientRead({ row }) {
  const on = !!row.client;
  return <span class={`cv${on ? " on" : ""}`} data-pk-client-read><Icon name={on ? "eye" : "eyeoff"} />{on ? "Client visible" : "Client not visible"}</span>;
}

/** Props: row, editing, Pick (the workstream and milestone pickers, or null to draw text), ClientLine (the Client visible line in Edit, or null). */
export function PeekActionBody({ row, editing = false, Pick = null, ClientLine = null, onFile = false }) {
  const raised = raisedOf(row);
  return (
    <PeekDetails summary={actionSummary(row, editing)}>
      <dl class="pk-fields" data-pk-action-rows>
        <ARow name="Workstream" icon="board" data="workstream">{Pick ? <Pick row={row} field="workstream" /> : text(row.workstream)}</ARow>
        <ARow name="Milestone" icon="flag" data="milestone">{Pick ? <Pick row={row} field="milestone" /> : text(row.milestone)}</ARow>
        {row.kind === "risk" || row.kind === "issue" ? <ARow name="Use case" icon="doc" data="use_case">{Pick ? <Pick row={row} field="use_case" /> : text(row.uc)}</ARow> : null}
        <ARow name="Raised" icon="clock" data="raised">{raised ? showDate(raised) : DASH}<span class="muted pk-hint" data-pk-raised-hint> set when it was raised</span></ARow>
        {editing ? (ClientLine ? <div class="pk-row" data-pk-client-row><dd><ClientLine row={row} /></dd></div> : <ARow name="Shown to client">{row.client ? "Yes" : "No"}</ARow>) : (onFile ? null : <div class="pk-row" data-pk-client-row><dd><ClientRead row={row} /></dd></div>)}      {/* row 1466: a published file never draws the Client visible line or its eye */}
      </dl>
    </PeekDetails>
  );
}
