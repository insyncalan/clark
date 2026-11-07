// The Gantt page's Import from Excel (row 926): the same two-step box the Settings Data card opens (ImportWorkbook.jsx), which offers the
// Gantt sheet with the others and changes the project in ONE step. Edit parts only: a published file has no server to ask.
import { data, project, reread } from "../stores/report.js";
import { openBox } from "./boxes.js";

export const importExcel = (opener) => openBox("import", {
  opener, project: project.value, projectName: data.value && data.value.project ? data.value.project.name : "", onDone: () => reread(project.value),
});
