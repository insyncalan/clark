// Settings › Projects: the table of projects (Name, Code, Client, Workstreams, Items). Plain functions, no DOM and no Preact, so a
// test can run them alone. The words are here so the page and its tests read the same sentences.

export const TITLE = "Projects";
export const INTRO = "Archive hides a project and everything in it from clark. Nothing is deleted: Show archived brings it back to the list, and Restore puts it back to work.";
export const COLUMNS = ["Name", "Code", "Client", "Workstreams", "Items"];
export const LOADING = "Looking for your projects.";
export const NONE = "No projects yet. To add one, ask the clark team.";
export const ALL_ARCHIVED = "Every project is archived. Choose Show archived to restore one.";
export const FAILED = "The list of projects could not be read. Reload the page. If it happens again, restart clark.";
export const NO_CLIENT = "—";
export const LABELS = { open: "Open", archive: "Archive", restore: "Restore", show: "Show archived", hide: "Hide archived", tryAgain: "Try again" };
export const OPEN_NOW = "Open now";
export const OPEN_NOTE = "Open another project to archive this one.";
export const ARCHIVED = "Archived";

// One row of the table from a project's name and code (GET /api/projects) and its data (GET /api/data): its client's name, the names of
// its active workstreams (all of them for an archived project, whose workstreams are all archived), and how many work items it has.
export function rowOf(p, data, archived) {
  const d = data && typeof data === "object" ? data : {};
  const client = d.project && typeof d.project.client_name === "string" ? d.project.client_name.trim() : "";
  const ws = (Array.isArray(d.workstreams) ? d.workstreams : []).filter((w) => w && typeof w.name === "string" && (archived || (!w.archived && w.status !== "Closed"))).map((w) => w.name);
  const n = ["actions", "raid", "decisions"].reduce((sum, k) => sum + (Array.isArray(d[k]) ? d[k].length : 0), 0);
  return { code: p.code, name: p.name, client: client || NO_CLIENT, workstreams: ws.join(", ") || NO_CLIENT, items: n, archived: !!archived };
}

export const archivedWords = (name) => `${name} archived. Show archived brings it back.`;
export const restoredWords = (name) => `${name} restored.`;
export const countLabel = (n) => (n ? `${LABELS.show} (${n})` : LABELS.show);
