// The page: the top bar and the open view. `tools` is what Edit adds (edit/index.js); the published page passes none.
import { view, status } from "../stores/report.js";
import { TopBar } from "./TopBar.jsx";
import { Milestones, Settings, Gate } from "./Views.jsx";
import { Dashboard } from "./Dashboard.jsx";
import { Peek } from "./Peek.jsx";
import { WorkItems } from "./WorkItems.jsx";

const PAGES = { dashboard: Dashboard, work: WorkItems, milestones: Milestones, settings: Settings };

export function App({ tools }) {
  const Page = view.value === "usecases" ? (tools && tools.UseCasesPage) || Dashboard : PAGES[view.value];     // the Use cases page is the editor's: a published file has none
  const Toast = tools && tools.Toast;
  const RowMenu = tools && tools.RowMenu;               // the right-click menu on a work item (#97); a published file has none
  const Layer = tools && tools.HelpLayer;                // Help (#82) sits over the open page; a published file has none
  const Pal = tools && tools.Palette;                    // the command palette (#198); a published file has none
  const Ask = tools && tools.AskPanel;                   // the ask panel (#47a) sits over the open page; a published file has none
  const body = status.value === "ready" ? <Page tools={tools} /> : <Gate />;
  const AddDialog = tools && tools.AddDialog;
  return (
    <>
      <TopBar tools={tools} />
      <main id="main">{Layer ? <Layer>{body}</Layer> : body}</main>
      {Ask ? <Ask /> : null}
      {status.value === "ready" ? <Peek tools={tools} /> : null}
      {Toast ? <Toast /> : null}
      {RowMenu ? <RowMenu /> : null}
      {Pal ? <Pal /> : null}
      {AddDialog ? <AddDialog /> : null}
    </>
  );
}
