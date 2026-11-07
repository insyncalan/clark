// The Gantt tab's page, joined to its data (row 926): the served page gives the page the store host (tools.ganttHost, an Edit part: every change
// goes through the change route), a published file gives it the file host (reads what the file carries, changes nothing).
import { useMemo } from "preact/hooks";
import { GanttPage } from "./GanttPage.jsx";
import { createFileHost } from "../logic/ganttFileHost.js";

export function GanttView({ tools }) {
  const make = tools && tools.ganttHost;
  const host = useMemo(() => (make ? make() : createFileHost()), [make]);
  return <GanttPage host={host} tools={make ? tools : null} />;
}
