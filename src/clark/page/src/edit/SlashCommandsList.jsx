// Row 1295: the list of slash commands in Settings (the ask clark page): every command that is available, with its name, its line in the menu and a tag.
// Open the editor, New slash command and each Edit open the editor page in a new browser tab (SlashEditor.jsx); this card changes nothing itself.
// Classic only (the caller checks); the server keeps the files (ask_commands_service.py).
import { useEffect, useState } from "preact/hooks";
import { BUILTINS, LOCKED, listAll } from "../logic/askShortcuts.js";
import { askCommandsRead } from "./publishApi.js";
import { askOn, askStatus, loadAsk, ASK_OFF_LINE } from "./askState.js";

export const SLASH_ALL_HEAD = "Slash commands for all projects";
export const SLASH_PROJECT_HEAD = (code) => `Slash commands in ${code}`;
export const SLASH_OPEN = "Open the editor ↗";
export const SLASH_NEW = "New slash command ↗";
export const SLASH_EDIT = "Edit ↗";
export const SLASH_UNAVAILABLE = "Slash commands aren't ready on this computer yet.";
export const SLASH_DAMAGED = "A file could not be read:";
export const TAG_BUILT = "Built in", TAG_YOURS = "Yours", TAG_ACTION = "Action", TAG_EDITED = "edited";
export const TAG_PROJECT = (code) => `${code} only`;

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

export function SlashList({ scope, code }) {
  const [data, setData] = useState(null);                 // null: not read yet; "unavailable"; or the answer
  useEffect(() => { loadAsk(); }, []);
  useEffect(() => {
    let live = true;
    askCommandsRead(scope === "all" ? "" : code).then((r) => {
      if (live) setData(r.status === 200 && r.body && r.body.ok === true && Array.isArray(r.body.all) ? r.body : "unavailable");
    });
    return () => { live = false; };
  }, [scope, code]);
  const list = data && data !== "unavailable" ? rows(data, scope, code) : [];
  const bad = data && data !== "unavailable" ? [...(data.damaged.all || []), ...(scope === "all" ? [] : data.damaged.project || [])] : [];
  const link = (name, isNew) => editorUrl(scope === "all" ? "" : code, scope, name, isNew);
  return (
    <section class="frame setting slash-list" id={scope === "all" ? "slash-all" : "slash-project"}>
      <h2>{scope === "all" ? SLASH_ALL_HEAD : SLASH_PROJECT_HEAD(code)}</h2>
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
      {bad.length ? <p class="muted" id="slash-damaged">{SLASH_DAMAGED} {bad.join(", ")}</p> : null}
    </section>
  );
}
