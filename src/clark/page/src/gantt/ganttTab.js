// The Gantt tab and its project setting (#926): the ONE place that knows the wire format. The project carries three fields
// (the data layer adds them as columns of projects, beside review_after_days): show_gantt_editor and show_gantt_client (0 or 1,
// default 0) and gantt_tab_name (text, default "Gantt"). They are read from data.project and written with the project-update
// change, exactly as review_after_days is. Nothing else in the page spells these field names. Pure: no store, no page.
export const FIELDS = { editor: "show_gantt_editor", client: "show_gantt_client", name: "gantt_tab_name" };
export const DEFAULT_NAME = "Gantt";
export const NAME_MAX = 30;

const on = (v) => v === 1 || v === true || v === "1";

/** True when the editor's page offers the Gantt tab for this project (data.project). */
export const editorOn = (project) => !!project && on(project[FIELDS.editor]);

/** True when the project's setting says the client sees the Gantt. The published file's own tab list decides what a client gets. */
export const clientOn = (project) => !!project && on(project[FIELDS.client]);

/** The tab's label: the project's own name for it, else "Gantt". */
export function tabName(project) {
  const n = project && typeof project[FIELDS.name] === "string" ? project[FIELDS.name].trim() : "";
  return n || DEFAULT_NAME;
}

/** The name typed, tidied (spaces trimmed and squeezed), or null when it is empty or too long. */
export function nameOf(text) {
  const t = String(text == null ? "" : text).replace(/\s+/g, " ").trim();
  return t && t.length <= NAME_MAX ? t : null;
}

/** The `changes` of the project-update change for one setting: which is "editor", "client" or "name". */
export function changesFor(which, value) {
  const field = FIELDS[which];
  if (!field) throw new Error("unknown Gantt setting: " + which);
  return { [field]: which === "name" ? String(value) : value ? 1 : 0 };
}

/** The whole change request, as ReviewDays sends it. */
export const requestFor = (which, value) => ({ kind: "projects", op: "update", changes: changesFor(which, value), place: "menu" });
