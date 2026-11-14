// The project switcher in the top bar (A-D25, and item 439 row 37, prototype core.js:292-295): a button with a chevron and a menu. Row 1064: the name is not drawn in the bar
// (the Dashboard cover has it); it stays in the button for a screen reader, and in the label. The menu lists the projects (the open one marked, each with "N open items"). Row 1092: nothing else; adding a project and project settings are in Settings.
// Choosing a project is setProject(): one new address entry and a page load for that project (#944), so Back returns to the project before;
// the name in the bar says which is open, so there is no message. Only the editor has it (a published file shows the name as plain words and never asks a server). The list is
// GET /api/projects, read when the bar draws and again each time the menu opens (so the counts follow the work done since); until it is read, or if it cannot be, the menu has the open project. The menu starts on the open project.
import { useEffect, useRef, useState } from "preact/hooks";
import { Menu } from "../components/Menu.jsx";
import { token, project, setProject } from "../stores/report.js";
import { navigate } from "../router.js";
import { actionIcon } from "../menuIcons.js";

export const openWords = (n) => (typeof n === "number" ? `${n} open ${n === 1 ? "item" : "items"}` : undefined);

export function ProjectSwitch({ name, cover }) {      // `cover` (item 1176): the Dashboard cover's own copy, the name as its button
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
  const none = !rows.length;      // no project exists or is open: the menu must not be empty, so its one row says where a project is added
  const items = none ? [{ id: "__settings", name: "No project yet. Open Settings to add one.", icon: actionIcon("settings") }] : rows.map((p) => ({ id: p.code, name: p.name || p.code, line: openWords(p.open), icon: actionIcon("project"), checked: p.code === project.value }));      // row 1092: only the projects; adding a project and project settings are in Settings
  const pick = (id) => {
    if (id === "__settings") { navigate({ view: "settings", project: project.value }); return; }
    setProject(id);
  };
  if (cover) return <Menu btnCls="cover-switch" label={shown} tip="Click to change project" ariaLabel={`Project: ${shown}. Click to change project`} menuId="cover-project-menu" menuLabel="Projects" left fixed="start" items={items} onPick={pick} onOpen={read} focusChecked />;
  return <Menu id="project-name" btnCls="proj projbtn" label={shown} ariaLabel={`Project: ${shown}. Change project`} menuId="project-menu" menuLabel="Projects" left labelCls="sr" items={items} onPick={pick} onOpen={read} focusChecked />;
}
