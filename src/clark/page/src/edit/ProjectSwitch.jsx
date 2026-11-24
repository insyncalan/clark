// The project switcher in the top bar (A-D25, and item 439 row 37, prototype core.js:292-295): the open project's name, always a button,
// with a chevron and a menu. The menu lists the projects (the open one marked, each with "N open items"), then "Project settings".
// Choosing a project is setProject(): one new address entry, so Back returns to the project before, and the toast says
// "Switched to <name>". Only the editor has it (a published file shows the name as plain words and never asks a server). The list is
// GET /api/projects, read when the bar draws and again each time the menu opens (so the counts follow the work done since); until it is read, or if it cannot be, the menu has the open project and Project settings.
// "New project..." (row 856) opens the project form Settings uses; the new project opens on Work items. The menu starts on the open project.
import { useEffect, useRef, useState } from "preact/hooks";
import { Menu } from "../components/Menu.jsx";
import { token, project, setProject, show, loadProjects, openProjectAt } from "../stores/report.js";
import { say } from "../stores/changes.js";
import { openBox, closeBox } from "./boxes.js";
import * as D from "../logic/dataCard.js";
import { ownToast } from "./BarToast.jsx";

const NEW = "\u0000new";
const SETTINGS = "\u0000settings";      // not a project code, so no project can be mistaken for it

export const openWords = (n) => (typeof n === "number" ? `${n} open ${n === 1 ? "item" : "items"}` : undefined);

export function ProjectSwitch({ name }) {
  const [list, setList] = useState([]);
  const live = useRef(true), asked = useRef(0);
  const read = () => {
    const mine = ++asked.current;       // only the newest answer is shown, so a slow older one cannot put old counts back
    fetch("/api/projects", { headers: { "X-Clark-Token": token() }, cache: "no-store" })
      .then((r) => r.json().then((b) => (r.ok && b.ok && Array.isArray(b.projects) ? b.projects : [])))
      .then((rows) => { if (live.current && mine === asked.current && rows.length) setList(rows); })
      .catch(() => {});
  };
  useEffect(() => { live.current = true; read(); return () => { live.current = false; }; }, []);
  const shown = name || project.value || "No project open";
  const rows = list.length ? list : project.value ? [{ code: project.value, name: shown }] : [];
  const items = [
    ...rows.map((p) => ({ id: p.code, name: p.name || p.code, line: openWords(p.open), checked: p.code === project.value })),
    ...(rows.length ? [{ id: "sep", sep: true }] : []),
    { id: NEW, name: "New project..." },
    { id: SETTINGS, name: "Project settings" },
  ];
  async function created(body) {
    closeBox();
    await loadProjects();
    openProjectAt(body.code, "work");
    say("done", D.PROJECT.created(body.name));
  }
  const pick = (id) => {
    if (id === NEW) { openBox("project", { row: null, opener: document.getElementById("project-name"), onSaved: created }); return; }
    if (id === SETTINGS) { show("settings"); return; }
    const row = rows.find((p) => p.code === id);
    setProject(id);
    say("note", `Switched to ${(row && row.name) || id}`, null, id);
    ownToast();       // made in View too, so View shows it (BarToast.jsx)
  };
  return <Menu id="project-name" btnCls="proj projbtn" label={shown} ariaLabel={`Project: ${shown}. Change project`} menuId="project-menu" menuLabel="Projects" left items={items} onPick={pick} onOpen={read} focusChecked />;
}
