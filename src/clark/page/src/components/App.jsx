// The page: the top bar and the open view. `tools` is what Edit adds (edit/index.js); the published page passes none.
import { view, status, tabs } from "../stores/report.js";
import { TopBar } from "./TopBar.jsx";
import { Milestones, Settings, Gate } from "./Views.jsx";
import { Dashboard } from "./Dashboard.jsx";
import { UseCasesTab } from "./UseCasesTab.jsx";
import { WorkItems } from "./WorkItems.jsx";

const PAGES = { dashboard: Dashboard, work: WorkItems, milestones: Milestones, usecases: UseCasesTab, settings: Settings };

export function App({ tools }) {
  const Page = (tabs.value.includes(view.value) && PAGES[view.value]) || Dashboard;   // the editor has no Use Cases tab: only a file does
  const Toast = tools && tools.Toast;
  const Layer = tools && tools.HelpLayer;                // Help (#82) sits over the open page; a published file has none
  const body = status.value === "ready" ? <Page tools={tools} /> : <Gate />;
  return (
    <>
      <TopBar tools={tools} />
      <main id="main">{Layer ? <Layer>{body}</Layer> : body}</main>
      {Toast ? <Toast /> : null}
    </>
  );
}
