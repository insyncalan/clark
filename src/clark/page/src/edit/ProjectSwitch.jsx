// The project switcher in the top bar (A-D25, and #439 row 37, prototype core.js:292-295): the open project's name, always a button,
// with a chevron and a menu. The menu lists the projects (the open one marked, each with "N open items"), then "Project settings".
// Choosing a project is setProject(): one new address entry, so Back returns to the project before, and the toast says
// "Switched to <name>". Only the editor has it (a published file shows the name as plain words and never asks a server). The list is
// GET /api/projects, read once when the bar draws; until it is read, or if it cannot be, the menu has the open project and Project settings.
// "New project…" is not here: the page has no way to make a project yet.
import { useEffect, useState } from "preact/hooks";
import { Menu } from "../components/Menu.jsx";
import { token, project, setProject, show } from "../stores/report.js";
import { say } from "../stores/changes.js";

const SETTINGS = "\u0000settings";      // not a project code, so no project can be mistaken for it

export const openWords = (n) => (typeof n === "number" ? `${n} open ${n === 1 ? "item" : "items"}` : undefined);

export function ProjectSwitch({ name }) {
  const [list, setList] = useState([]);
  useEffect(() => {
    let live = true;
    fetch("/api/projects", { headers: { "X-Clark-Token": token() }, cache: "no-store" })
      .then((r) => r.json().then((b) => (r.ok && b.ok && Array.isArray(b.projects) ? b.projects : [])))
      .then((rows) => { if (live) setList(rows); })
      .catch(() => {});
    return () => { live = false; };
  }, []);
  const shown = name || project.value || "No project open";
  const rows = list.length ? list : project.value ? [{ code: project.value, name: shown }] : [];
  const items = [
    ...rows.map((p) => ({ id: p.code, name: p.name || p.code, line: openWords(p.open), checked: p.code === project.value })),
    ...(rows.length ? [{ id: "sep", sep: true }] : []),
    { id: SETTINGS, name: "Project settings" },
  ];
  const pick = (id) => {
    if (id === SETTINGS) { show("settings"); return; }
    const row = rows.find((p) => p.code === id);
    setProject(id);
    say("note", `Switched to ${(row && row.name) || id}`, null, id);
  };
  return <Menu id="project-name" btnCls="proj projbtn" label={shown} ariaLabel={`Project: ${shown}. Change project`} menuId="project-menu" menuLabel="Projects" left items={items} onPick={pick} />;
}
