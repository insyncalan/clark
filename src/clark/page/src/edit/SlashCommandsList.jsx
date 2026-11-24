// Row 1295: the list of slash commands in Settings (the ask clark page): every command that is available, with its name, its line in the menu and a tag.
// Open the editor, New slash command and each Edit open the editor page in a new browser tab (SlashEditor.jsx); this card changes nothing itself.
// Classic only (the caller checks); the server keeps the files (ask_commands_service.py).
import { useEffect, useState } from "preact/hooks";
import { say, sayLocalUndo } from "../stores/changes.js";
import { BUILTINS, LOCKED, listAll } from "../logic/askShortcuts.js";
import { askCommandsRead, askCommandsChange } from "./publishApi.js";
import { askOn, askStatus, loadAsk, ASK_OFF_LINE } from "./askState.js";

export const SLASH_ALL_HEAD = "Slash commands for all projects";
export const SLASH_PROJECT_HEAD = (code) => `Slash commands in ${code}`;
export const SLASH_OPEN = "Open the editor ↗";
export const SLASH_NEW = "New slash command ↗";
export const SLASH_EDIT = "Edit ↗";
export const SLASH_UNAVAILABLE = "Slash commands aren't ready on this computer yet.";
// Row 1435 (the words are approved, row 1435, words log of 24-11 21:1x; the toast and the failed line come from the server, ask_commands_service.py MESSAGES). The "!" is an icon, not text.
export const SLASH_NEEDS_FIX = "Needs a fix", SLASH_FIX = "Fix it with AI";
export const TAG_BUILT = "Built in", TAG_YOURS = "Yours", TAG_ACTION = "Action", TAG_EDITED = "edited";
export const TAG_PROJECT = (code) => `${code} only`;
// Words from the approved mock-up A8 (FINAL-settings-A8.html:145,158), row 1294.
export const SLASH_ALL_ROW = "Type / in the box";
export const SLASH_ALL_LINE = "These are the slash commands available in every project. A project can have its own with the same name; its own wins there. Built-in ones can be edited or copied.";
export const SLASH_PROJECT_ROW = (code) => `Only in ${code}`;
export const SLASH_PROJECT_LINE = "Slash commands that exist only in this project. One with the same name as one for all projects wins here.";
export const SLASH_PROJECT_NONE = "None yet. The ones for all projects work here too.";
export const SLASH_FROM_ALL = "From All projects";
export const SLASH_SEE = "See them";
export const SLASH_NEW_TAB_ALL = "The editor is its own page: it opens in a new tab.";
export const SLASH_NEW_TAB_PROJECT = "The editor opens in a new tab.";
export const counts = (yours, built, actions) => `${yours} yours, ${built} built in, ${actions} ${actions === 1 ? "action" : "actions"}`;
export const SLASH_ALL_COUNTS = (n, yours, built, actions) => `The ${n} ${n === 1 ? "slash command" : "slash commands"} for all projects (${counts(yours, built, actions)}).`;

/** The address of the editor page. `name` opens that command; "" opens it with nothing chosen; `isNew` opens a new one. */
export function editorUrl(project, scope, name, isNew) {
  const q = new URLSearchParams({ "slash-editor": "1" });
  if (project) q.set("project", project);
  if (scope === "all") q.set("scope", "all");
  if (name) q.set("name", name);
  if (isNew) q.set("new", "1");
  return "/?" + q.toString();
}

/** The rows the person sees. For all projects: their own, then the built-ins. In a project: its own commands win over a same-named one for all projects. */
export function rows(data, scope, code) {
  const all = data.all || [], own = scope === "all" ? [] : data.project || [];
  const base = scope === "all" ? all : [...all.filter((m) => m.replaces), ...own.filter((m) => m.replaces)];
  const over = new Map(base.map((m) => [m.replaces, m]));
  const ownReplaces = new Set(own.filter((m) => m.replaces).map((m) => m.replaces));
  // inherited: on a project tab, kept for all projects (Remove and Reset are not done from here; Save makes a project copy)
  const builtIn = BUILTINS.map((b) => (over.has(b.name) ? { ...over.get(b.name), name: b.name, builtin: true, edited: true, inherited: scope !== "all" && !ownReplaces.has(b.name) } : b));
  const names = new Set(own.filter((m) => !m.replaces).map((m) => m.name));
  const yours = [...all.filter((m) => !m.replaces && !names.has(m.name)).map((m) => ({ ...m, tag: TAG_YOURS, inherited: true })),
                 ...own.filter((m) => !m.replaces).map((m) => ({ ...m, tag: TAG_PROJECT(code) }))];
  if (scope === "all") return [...listAll(all).yours.map((m) => ({ ...m, tag: TAG_YOURS })), ...builtIn.map(tagBuilt)];
  return [...yours, ...builtIn.map(tagBuilt)];
}
const tagBuilt = (b) => ({ ...b, tag: LOCKED.includes(b.name) ? TAG_ACTION : TAG_BUILT });

/** The rows of the Settings list (row 1294). For all projects: their own, then the built-ins. In a project: only that project's own commands (those for all projects are one click away). */
export function listRows(data, scope, code) {
  const all = data.all || [];
  if (scope !== "all") return (data.project || []).map((m) => ({ ...m, tag: TAG_PROJECT(code) }));
  const over = new Map(all.filter((m) => m.replaces).map((m) => [m.replaces, m]));
  const builtIn = BUILTINS.map((b) => (over.has(b.name) ? { ...over.get(b.name), name: b.name, builtin: true, edited: true } : b));
  return [...listAll(all).yours.map((m) => ({ ...m, tag: TAG_YOURS })), ...builtIn.map(tagBuilt)];
}

/** How many commands are for all projects and of which kind (the foot of the all projects list; the "From All projects" row). */
export function tally(data) {
  const list = listRows(data, "all", "");
  const n = (t) => list.filter((r) => r.tag === t).length;
  return { total: list.length, yours: n(TAG_YOURS), built: n(TAG_BUILT), actions: n(TAG_ACTION) };
}

export function SlashList({ scope, code, goAll }) {
  const [data, setData] = useState(null);                 // null: not read yet; "unavailable"; or the answer
  useEffect(() => { loadAsk(); }, []);
  useEffect(() => {
    let live = true;
    askCommandsRead(scope === "all" ? "" : code).then((r) => {
      if (live) setData(r.status === 200 && r.body && r.body.ok === true && Array.isArray(r.body.all) ? r.body : "unavailable");
    });
    return () => { live = false; };
  }, [scope, code]);
  const list = data && data !== "unavailable" ? listRows(data, scope, code) : [];
  const bad = data && data !== "unavailable" ? [...(data.damaged.all || []).map((file) => ({ file, from: "all" })), ...(scope === "all" ? [] : data.damaged.project || []).map((file) => ({ file, from: "project" }))] : [];
  const reread = () => askCommandsRead(scope === "all" ? "" : code).then((r) => { if (r.status === 200 && r.body && r.body.ok === true && Array.isArray(r.body.all)) setData(r.body); });
  const send = (b, action, file) => askCommandsChange({ scope: b.from, ...(b.from === "project" ? { project: code } : {}), action, name: file });
  const fix = async (b) => {                          // local, no AI call: the server keeps `<file>.old`, rewrites the file, and answers the counts
    const r = await send(b, "fix", b.file);
    if (r.status === 200 && r.body && r.body.ok === true) {
      setData(r.body);
      sayLocalUndo("done", r.body.message, async () => { await send(b, "unfix", b.file); reread(); }, code);
    } else say("problem", (r.body && r.body.message) || "Could not fix the file. The old file is kept.", null, code);
  };
  const t = data && data !== "unavailable" ? tally(data) : null;
  const link = (name, isNew) => editorUrl(scope === "all" ? "" : code, scope, name, isNew);
  return (
    <section class="frame setting slash-list" id={scope === "all" ? "slash-all" : "slash-project"}>
      <h2>{scope === "all" ? SLASH_ALL_HEAD : SLASH_PROJECT_HEAD(code)}</h2>
      <p class="muted" id={scope === "all" ? "slash-all-line" : "slash-project-line"}><b>{scope === "all" ? SLASH_ALL_ROW : SLASH_PROJECT_ROW(code)}.</b> {scope === "all" ? SLASH_ALL_LINE : SLASH_PROJECT_LINE}</p>
      <div class="row">
        <a class="btn" data-slash-open href={link("", false)} target="_blank" rel="noopener">{SLASH_OPEN}</a>
        <a class="btn" data-slash-new href={link("", true)} target="_blank" rel="noopener">{SLASH_NEW}</a>
      </div>
      {askStatus.value === "ready" && !askOn.value ? <p class="muted" id="slash-off">{ASK_OFF_LINE}</p> : null}
      {data === "unavailable" ? <p class="muted" id="slash-note">{SLASH_UNAVAILABLE}</p> : null}
      {list.length ? (
        <ul class="slash-rows">
          {list.map((c) => (
            <li key={c.name + (c.tag || "")} data-slash-row={c.name}>
              <b class="slash-name">/{c.name}</b>
              <span class="muted slash-menu">{c.menu}</span>
              <span class="slash-tag">{c.tag}{c.edited ? ` · ${TAG_EDITED}` : ""}</span>
              {c.locked ? null : <a class="slash-edit" href={link(c.name, false)} target="_blank" rel="noopener" aria-label={`Edit /${c.name}`}>{SLASH_EDIT}</a>}
            </li>
          ))}
        </ul>
      ) : null}
      {scope !== "all" && Array.isArray(data && data.all) && !list.length ? <p class="muted" id="slash-none">{SLASH_PROJECT_NONE}</p> : null}
      {scope === "all" && t ? <p class="muted" id="slash-all-foot">{SLASH_NEW_TAB_ALL} {counts(t.yours, t.built, t.actions)}.</p> : null}
      {scope !== "all" && t ? (
        <div class="row" id="slash-from-all">
          <span><b>{SLASH_FROM_ALL}</b> <span class="muted">{SLASH_ALL_COUNTS(t.total, t.yours, t.built, t.actions)}</span></span>
          <button type="button" class="btn sm quiet" data-slash-see onClick={goAll}>{SLASH_SEE}</button>
        </div>
      ) : null}
      {scope !== "all" ? <p class="muted" id="slash-project-foot">{SLASH_NEW_TAB_PROJECT}</p> : null}
      {bad.length ? (
        <ul class="slash-rows slash-damaged" id="slash-damaged">
          {bad.map((b) => (
            <li key={b.from + b.file} data-slash-damaged={b.file}>
              <b class="slash-name">{b.file}</b>
              <span class="slash-pill"><span class="slash-pill-icon" aria-hidden="true">!</span><span class="slash-pill-text">{SLASH_NEEDS_FIX}</span></span>
              <button type="button" class="btn sm quiet" data-slash-fix onClick={() => fix(b)}>{SLASH_FIX}</button>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
