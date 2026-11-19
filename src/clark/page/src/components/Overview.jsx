// Settings > Projects overview (row 1299 slice 2, mock-up FINAL-settings-A7 `projects`): one row per project, every value a link to that setting for that project, a banner and a chip
// for what needs a look. Asking is one per-computer setting (ruling on 1299 S2): each row shows it as a read-only value that opens the ask clark page, with no switch. Edit's page
// only: a published file has no Settings. `api` is a seam for the tests. Plain words and rules are in logic/overviewRules.js.
import { useEffect, useState } from "preact/hooks";
import { openSettingsOf } from "../stores/report.js";
import { overviewRead } from "../edit/projectsApi.js";
import * as R from "../logic/overviewRules.js";

const REAL = { read: overviewRead };

// A value that opens one setting for this project: a real address (Back, Forward and open in a new tab work), and a plain click goes the router's way.
function Val({ row, page, warn, title, children }) {
  const go = (e) => { if (e.button || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return; e.preventDefault(); openSettingsOf(row.code, page); };
  return <a data-setting={page} href={`#settings&p=${row.code}&s=${page}`} class={warn ? "ov-val warn" : "ov-val"} title={title} onClick={go}>{children}</a>;
}

export function Overview({ api = REAL }) {
  const [state, setState] = useState({ phase: "loading", rows: [] });
  const [filter, setFilter] = useState("all");

  async function load() {
    setState({ phase: "loading", rows: [] });
    const got = await api.read();
    setState(got ? { phase: "ready", rows: R.rowsOf(got) } : { phase: "failed", rows: [] });
  }
  useEffect(() => { load(); }, []);

  const rows = state.rows;
  const iss = R.allProblems(rows);
  const shown = filter === "attn" ? rows.filter(R.needsLook) : rows;
  return (
    <section class="frame setting overview" id="overview">
      <h2 id="overview-h" tabIndex={-1}>{R.TITLE}</h2>
      <p class="muted">{R.INTRO}</p>
      {state.phase === "loading" ? <p class="muted">{R.LOADING}</p> : null}
      {state.phase === "failed" ? <p class="error" role="alert">{R.FAILED} <button type="button" class="btn sm" onClick={load}>{R.TRY_AGAIN}</button></p> : null}
      {state.phase === "ready" && !rows.length ? <p class="muted">{R.NONE}</p> : null}
      {rows.length ? (
        <>
          {iss.length ? <p class="ov-attn" id="overview-attention" role="status"><b>{iss.length + " to look at:"}</b> {iss.join(" · ")}</p> : null}
          <div class="ov-chips" role="group" aria-label="Show">
            <button type="button" class="ov-chip" data-filter="all" aria-pressed={filter === "all" ? "true" : "false"} onClick={() => setFilter("all")}>{"All (" + rows.length + ")"}</button>
            <button type="button" class="ov-chip" data-filter="attn" aria-pressed={filter === "attn" ? "true" : "false"} onClick={() => setFilter("attn")}>{"Needs attention (" + rows.filter(R.needsLook).length + ")"}</button>
          </div>
          <div class="ov-scroll">
            <table class="items ov-table" id="overview-table" aria-label={R.TITLE}>
              <thead><tr>{R.COLUMNS.map((c) => <th key={c} scope="col">{c}</th>)}</tr></thead>
              <tbody>
                {shown.map((row) => (
                  <tr key={row.code} data-project={row.code} data-attention={R.needsLook(row) ? "" : undefined}>
                    <td><Val row={row} page="pages"><b>{row.name}</b></Val></td>
                    <td><Val row={row} page="ask">{R.askingWords(row.asking)}</Val></td>
                    <td><Val row={row} page="brand">{row.brand}</Val></td>
                    <td class="num"><Val row={row} page="ask">{row.folders === null ? R.NOT_KNOWN : row.folders ? String(row.folders) : R.NO_FOLDERS}</Val></td>
                    <td class="num"><Val row={row} page="pages">{String(row.reviewDays)}</Val></td>
                    <td><Val row={row} page="brand" warn={row.clientFolder === ""} title={row.clientFolder || undefined}>{row.clientFolder === null ? R.NOT_KNOWN : row.clientFolder || "Not set"}</Val></td>
                    <td><Val row={row} page="backups" warn={row.lastBackupDays !== null && row.lastBackupDays > 1}>{R.backupWords(row.lastBackupDays)}</Val></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
    </section>
  );
}
