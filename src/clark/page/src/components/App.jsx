// The page: the top bar and the open view. `tools` is what Edit adds (edit/index.js); the published page passes none.
import { view, status, tabs, fromFile, data, asAt, TITLES } from "../stores/report.js";
import { printing } from "../stores/print.js";
import { printTabs, publishedLine } from "../logic/printView.js";
import { TopBar } from "./TopBar.jsx";
import { Milestones, Settings, Gate } from "./Views.jsx";
import { Dashboard } from "./Dashboard.jsx";
import { Peek } from "./Peek.jsx";
import { UseCasesTab } from "./UseCasesTab.jsx";
import { WorkItems } from "./WorkItems.jsx";
import { ClientReport } from "./ClientReport.jsx";

const PAGES = { dashboard: Dashboard, work: WorkItems, milestones: Milestones, usecases: UseCasesTab, clientreport: ClientReport, settings: Settings };

// The printed page (#438): every tab the file has, one after another, each under its own name, with the day it was published at the head.
// Only a published file draws it, and only while the browser is printing (stores/print.js).
function PrintStack({ tools }) {
  const name = data.value && data.value.project && data.value.project.name;
  return (
    <div class="print-stack">
      <div class="print-head"><b>{name}</b> <span>{publishedLine(asAt.value)}</span></div>
      {printTabs(tabs.value).map((v) => {
        const Tab = PAGES[v];
        return <section class="print-tab" key={v}><h2 class="print-tab-title">{TITLES[v]}</h2><Tab tools={tools} /></section>;
      })}
    </div>
  );
}

export function App({ tools }) {
  const own = (tabs.value.includes(view.value) && PAGES[view.value]) || Dashboard;   // a view the file or editor does not offer falls back to the dashboard
  const Page = view.value !== "usecases" ? own : fromFile.value ? UseCasesTab : (tools && tools.UseCasesPage) || Dashboard;   // the Use cases page is the editor's; a published file has its own view-only tab
  const Toast = tools && tools.Toast;
  const Layer = tools && tools.HelpLayer;                // Help (#82) sits over the open page; a published file has none
  const Pal = tools && tools.Palette;                    // the command palette (#198); a published file has none
  const Ask = tools && tools.AskPanel;                   // the ask panel (#47a) sits over the open page; a published file has none
  const stacked = fromFile.value && printing.value && status.value === "ready";
  const body = status.value === "ready" ? <Page tools={tools} /> : <Gate />;
  const AddDialog = tools && tools.AddDialog;
  return (
    <>
      <TopBar tools={tools} />
      <main id="main">{stacked ? <PrintStack tools={tools} /> : Layer ? <Layer>{body}</Layer> : body}</main>
      {Ask ? <Ask /> : null}
      {status.value === "ready" ? <Peek tools={tools} /> : null}
      {Toast ? <Toast /> : null}
      {Pal ? <Pal /> : null}
      {AddDialog ? <AddDialog /> : null}
    </>
  );
}
