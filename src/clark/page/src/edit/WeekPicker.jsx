// The week picker beside "Week ending" on the Dashboard's report bar (#344, follow-on 3 of the #125 design note; the prototype's
// #wkPast in system/prototype/past.js). It lists each published week of the open project, newest first, and opens the one picked
// read only: a page that was kept opens in a new tab as it was published (pastReportsApi.js, as Settings › Published reports'
// Open does); one that was not kept opens as the Dashboard as at the day it was published (GET /api/as-at, #349), behind its banner.
// The last line goes to Settings › Published reports › Dashboard as at a day. It only reads; it is in View and Edit, and like the
// rest of the report bar it is an Edit part, so a published file never has it. `api`, `openTab` and `code` are seams for the tests.
import { useEffect, useState } from "preact/hooks";
import { project, showAsAt } from "../stores/report.js";
import { say } from "../stores/changes.js";
import { openInNewTab } from "../router.js";
import { dialog, latest } from "./publishState.js";
import { listPublications, readyPast } from "./pastReportsApi.js";
import { readAsAt } from "./asAtApi.js";
import { showPublished } from "./PublishedReports.jsx";
import * as L from "../logic/weekPicker.js";
import * as P from "../logic/pastReports.js";
import * as A from "../logic/asAt.js";

const REAL = { list: listPublications, ready: readyPast, asAt: readAsAt };

export function WeekPicker({ api = REAL, openTab = openInNewTab, code = project.value }) {
  const [rows, setRows] = useState([]);
  const [busy, setBusy] = useState(false);
  const publishing = dialog.value !== null;                  // the list is read again when the Publish box closes
  useEffect(() => {
    let live = true;
    if (!code || publishing) return undefined;
    api.list(code).then((r) => { if (live) setRows(r.status === 200 && P.isList(r.body) ? L.options(r.body.publications) : []); });
    return () => { live = false; };
  }, [code, publishing, latest.value]);
  if (!rows.length) return null;                             // nothing published yet: no picker

  async function openKept(n) {
    let r = null;
    const opened = await openTab(async () => {
      r = await api.ready(code, n);
      return r.status === 200 && r.body && r.body.ok === true && typeof r.body.url === "string" ? r.body.url : null;
    });
    if (opened) say("note", L.opening(n));
    else say("problem", r && r.status === 200 ? P.BLOCKED : P.openWords(r ? r.status : 0, r ? r.body : null));
  }

  async function openRebuilt(day) {
    const r = await api.asAt(code, day);
    if (r.status === 200 && A.isData(r.body, code, day) && showAsAt(day, r.body.data)) return;
    say("problem", A.failWords(r.status, r.status === 200 ? null : r.body));
  }

  async function pick(e) {
    const el = e.currentTarget, v = el.value;
    el.value = "";                                           // the picker always reads "Published weeks" again
    if (!v || busy) return;
    if (v === "asat") {
      showPublished();
      setTimeout(() => { const box = document.getElementById("as-at-day"); if (box) box.focus({ preventScroll: true }); }, 120);
      return;
    }
    const row = rows.find((x) => x.value === v);
    if (!row) return;
    setBusy(true);
    try { if (row.kept) await openKept(row.number); else await openRebuilt(row.day); } finally { setBusy(false); }
  }

  return (
    <select class="rbar-past" id="week-past" aria-label={L.LABEL} disabled={busy} onChange={pick}>
      <option value="">{L.FIRST}</option>
      {rows.map((x) => <option value={x.value} key={x.value}>{x.text}</option>)}
      <option value="asat">{L.AS_AT}</option>
    </select>
  );
}
