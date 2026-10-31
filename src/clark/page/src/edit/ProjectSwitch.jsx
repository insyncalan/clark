// The project switcher in the top bar (A-D25): the open project's name with a chevron, and a menu of the projects to change to.
// Only the editor has it (a published file shows the name as plain words and never asks a server). The list is GET /api/projects,
// read once when the bar draws; until it is read, or if it cannot be, the name stays plain words. Choosing one is setProject():
// one new address entry, so Back returns to the project before.
import { useEffect, useState } from "preact/hooks";
import { Menu } from "../components/Menu.jsx";
import { token, project, setProject } from "../stores/report.js";

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
  const items = list.map((p) => ({ id: p.code, name: p.name || p.code, checked: p.code === project.value }));
  if (items.length < 2) return <span class="proj" id="project-name">{shown}</span>;       // one project (or none read): nothing to switch to
  return <Menu id="project-name" btnCls="proj projbtn" label={shown} ariaLabel={`Project: ${shown}. Change project`} menuId="project-menu" menuLabel="Projects" left items={items} onPick={(code) => setProject(code)} />;
}
