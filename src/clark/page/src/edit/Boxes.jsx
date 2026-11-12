// Draws the box Settings opened (boxes.js): the project form or Import workbook (item 444). Edit only.
import { box, closeBox } from "./boxes.js";
import { Dialog } from "./Dialog.jsx";
import { ProjectForm } from "./ProjectForm.jsx";
import { ImportWorkbook } from "./ImportWorkbook.jsx";
import { DemoConfirm } from "./Demo.jsx";
import { ExcelLayout } from "./ExcelLayout.jsx";

export function Boxes() {
  const b = box.value;
  if (!b) return null;
  if (b.kind === "project") return <ProjectForm key="project" {...b.props} onClose={closeBox} />;
  if (b.kind === "import") return <ImportWorkbook key="import" {...b.props} onClose={closeBox} />;
  if (b.kind === "demo") return <DemoConfirm key="demo" {...b.props} onClose={closeBox} />;
  if (b.kind === "layout") return <ExcelLayout key="layout" {...b.props} onClose={closeBox} />;
  return null;
}
