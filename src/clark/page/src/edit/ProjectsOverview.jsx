// Row 1299 (S3, read only, Classic only): the Projects overview at the head of the All projects page. One row for each live project with the values
// that matter (GET /api/projects-overview, projects_overview.py), a click on a value opens that setting for that project, a filter for what needs a look.
// Grey is the default, amber is an override or something to fix. Bulk change, copy and Undo are a later slice (S5). The words are the ticket's ruling.
import { useEffect, useState } from "preact/hooks";
import { zoneFetch } from "../api.js";
import { token, showSettings, chooseSettingsProject, SWITCH_TABS } from "../stores/report.js";

export const INTRO = "Every project at a glance. Click a value to open that setting for the project. Grey is the default, amber is an override or something to fix.";
export const COLUMNS = ["Project", "Asking", "Brand", "Read folders", "Review days", "Client folder", "Last backup"];
export const NOT_SET = "Not set";
export const looking = (n) => `${n} to look at`;
export const FILTERS = { all: (n) => `All (${n})`, attention: (n) => `Needs attention (${n})` };
export const NO_BACKUP = "No backup yet";
export const NONE_TO_LOOK_AT = "Nothing needs attention.";
export const brandWords = (b) => (b === "generic" ? "clark default" : b);
export const openTitle = (what, code) => `Open ${what} for ${code}`;
const WHAT = { asking: "ask clark", brand: "Brand", folders: "Read folders", review: "Review days", client: "Client folder", backup: "Backups" };
export const backupWords = (d) => (d === null ? NO_BACKUP : d === 0 ? "Today" : d === 1 ? "1 day ago" : `${d} days ago`);
export const issueWords = (row, code) => ({
  no_client_folder: `${row.code} has no client folder`,
  backup_old: `${row.code}: last backup ${backupWords(row.last_backup_days)}`,
  asking_no_folders: `${row.code}: asking is on, no folders`,
}[code] || "");
// The page each value opens (a Settings slug): Asking and Read folders are on ask clark, Brand and Client folder on Brand and publishing.
const OPENS = { asking: "claude", brand: "brand", folders: "claude", review: "reports", client: "brand", backup: "backups" };

export function ProjectsOverview({ read = () => zoneFetch("/api/projects-overview", { headers: { "X-Clark-Token": token() }, cache: "no-store" }).then((r) => r.json().then((b) => (r.ok && b.ok ? b : null))) }) {
  const [body, setBody] = useState(null);
  const [only, setOnly] = useState(false);
  useEffect(() => {
    let live = true;
    read().then((b) => { if (live) setBody(b); }).catch(() => {});
    return () => { live = false; };
  }, []);
  if (!body || !body.projects.length) return null;      // no read, or no project: the table below stands alone
  const rows = body.projects, shown = only ? rows.filter((r) => r.attention.length) : rows;
  const issues = rows.flatMap((r) => r.attention.map((a) => issueWords(r, a))).filter(Boolean);
  const open = (code, key) => { showSettings(OPENS[key]); if (SWITCH_TABS) chooseSettingsProject(code); };      // with the switch off the cards edit the open project, so the page opens and no other project is chosen
  const val = (r, key, text, flag) => <td><button type="button" class={`ov-val${flag ? " ov-amber" : ""}`} data-ov={key} title={openTitle(WHAT[key], r.code)} onClick={() => open(r.code, key)}>{text}</button></td>;
  return (
    <section class="frame setting ov" id="projects-overview" aria-label="Projects overview">
      <p class="muted">{INTRO}</p>
      {issues.length ? <p class="ov-issues" id="ov-issues">{looking(body.attention_count)}: {issues.join("; ")}</p> : <p class="muted" id="ov-none">{NONE_TO_LOOK_AT}</p>}
      <div class="ov-filters">
        <button type="button" class="btn sm" data-ov-filter="all" aria-pressed={only ? "false" : "true"} onClick={() => setOnly(false)}>{FILTERS.all(rows.length)}</button>
        <button type="button" class="btn sm" data-ov-filter="attention" aria-pressed={only ? "true" : "false"} onClick={() => setOnly(true)}>{FILTERS.attention(body.attention_count)}</button>
      </div>
      <table class="items ov-table" aria-label="Projects overview">
        <thead><tr>{COLUMNS.map((c) => <th key={c} scope="col">{c}</th>)}</tr></thead>
        <tbody>
          {shown.map((r) => (
            <tr key={r.code} data-ov-project={r.code}>
              <td><b>{r.name}</b> <span class="muted">{r.code}</span></td>
              {val(r, "asking", r.asking ? "On" : "Off", r.attention.includes("asking_no_folders"))}
              {val(r, "brand", brandWords(r.brand), r.brand_override)}
              {val(r, "folders", String(r.folders), r.attention.includes("asking_no_folders"))}
              {val(r, "review", String(r.review_days), r.review_override)}
              {val(r, "client", r.client_folder || NOT_SET, !r.client_folder)}
              {val(r, "backup", backupWords(r.last_backup_days), r.attention.includes("backup_old") || r.attention.includes("no_backup"))}
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
