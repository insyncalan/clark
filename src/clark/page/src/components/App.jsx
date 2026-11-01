// The page: the top bar and the open view. `tools` is what Edit adds (edit/index.js); the published page passes none.
import { view, status, tabs, fromFile, isFile } from "../stores/report.js";
import { TopBar } from "./TopBar.jsx";
import { Milestones, Settings, Gate, Leaving } from "./Views.jsx";
import { Dashboard } from "./Dashboard.jsx";
import { Peek } from "./Peek.jsx";
import { UseCasesTab } from "./UseCasesTab.jsx";
import { WorkItems } from "./WorkItems.jsx";

const PAGES = { dashboard: Dashboard, work: WorkItems, milestones: Milestones, usecases: UseCasesTab, settings: Settings };

export function App({ tools }) {
  const own = (tabs.value.includes(view.value) && PAGES[view.value]) || Dashboard;   // a view the file or editor does not offer falls back to the dashboard
  const Page = view.value !== "usecases" ? own : fromFile.value ? UseCasesTab : (tools && tools.UseCasesPage) || Dashboard;   // the Use cases page is the editor's; a published file has its own view-only tab
  const Toast = tools && tools.Toast;
  const Layer = tools && tools.HelpLayer;                // Help (#82) sits over the open page; a published file has none
  const Pal = tools && tools.Palette;                    // the command palette (#198); a published file has none
  const Ask = tools && tools.AskPanel;                   // the ask panel (#47a) sits over the open page; a published file has none
  const body = status.value === "ready" ? <><Page tools={tools} /><Leaving /></> : <Gate />;
  const AddDialog = tools && tools.AddDialog;
  return (
    <>
      <TopBar tools={tools} />
      <main id="main" aria-busy={status.value === "loading" && !isFile() ? "true" : undefined}>{Layer ? <Layer>{body}</Layer> : body}</main>
      {Ask ? <Ask /> : null}
      {status.value === "ready" ? <Peek tools={tools} /> : null}
      {Toast ? <Toast /> : null}
      {Pal ? <Pal /> : null}
      {AddDialog ? <AddDialog /> : null}
    </>
  );
}
