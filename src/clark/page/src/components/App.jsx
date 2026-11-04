// The page: the top bar and the open view. `tools` is what Edit adds (edit/index.js); the published page passes none.
import { view, status, tabs, fromFile, isFile, publication, asAt, rebuilt } from "../stores/report.js";
import { AsAtBanner } from "./AsAtBanner.jsx";
import { plainDate } from "../logic/picker.js";
import { TopBar } from "./TopBar.jsx";
import { Milestones, Settings, Gate, Leaving } from "./Views.jsx";
import { Dashboard } from "./Dashboard.jsx";
import { Peek } from "./Peek.jsx";
import { UseCasesTab } from "./UseCasesTab.jsx";
import { WorkItems } from "./WorkItems.jsx";
import { ClientReport } from "./ClientReport.jsx";

const PAGES = { dashboard: Dashboard, work: WorkItems, milestones: Milestones, usecases: UseCasesTab, clientreport: ClientReport, settings: Settings };

export function App({ tools: given }) {
  // item 349: the Dashboard as at a day is read only: the page draws it as a published file is drawn, with no Edit part at all (no
  // Edit, Publish, menu, peek tools, Help, palette or ask panel), behind its banner; Back to now gives them back.
  const past = !!rebuilt.value && !fromFile.value;
  const tools = past ? null : given;
  const own = (tabs.value.includes(view.value) && PAGES[view.value]) || Dashboard;   // a view the file or editor does not offer falls back to the dashboard
  const Page = view.value !== "usecases" ? own : fromFile.value ? UseCasesTab : (tools && tools.UseCasesPage) || Dashboard;   // the Use cases page is the editor's; a published file has its own view-only tab
  const Toast = tools && tools.Toast;
  const RowMenu = tools && tools.RowMenu;               // the right-click menu on a work item (#97); a published file has none
  const Layer = tools && tools.HelpLayer;                // Help (#82) sits over the open page; a published file has none
  const Pal = tools && tools.Palette;                    // the command palette (#198); a published file has none
  const Ask = tools && tools.AskPanel;                   // the ask panel (#47a) sits over the open page; a published file has none
  const body = status.value === "ready" ? <>{past ? <AsAtBanner /> : null}<Page tools={tools} /><Leaving /></> : <Gate />;
  const AddDialog = tools && tools.AddDialog;
  const Boxes = tools && tools.Boxes;                    // the boxes Settings opens (item 444): the project form, Import workbook, the Reset confirm; a published file has none
  const UcBoxes = tools && tools.ucEdit && tools.ucEdit.Boxes;      // the Dashboard's use case boxes (#455): beside <main>, which they make inert
  const MsLayers = tools && tools.MsLayers;              // the milestone picker and an archived milestone's peek (Edit only)
  return (
    <>
      <TopBar tools={tools} />
      <main id="main" aria-busy={status.value === "loading" && !isFile() ? "true" : undefined}>{Layer ? <Layer>{body}</Layer> : body}</main>
      {publication.value ? <footer class="pubfoot num" id="publication-footer">{asAt.value ? `Published ${plainDate(asAt.value)}. ` : ""}Publication {publication.value}{asAt.value ? ` · ${plainDate(asAt.value)}` : ""}. View only.</footer> : null}
      {Ask ? <Ask /> : null}
      {status.value === "ready" ? <Peek tools={tools} /> : null}
      {Toast ? <Toast /> : null}
      {RowMenu ? <RowMenu /> : null}
      {Pal ? <Pal /> : null}
      {AddDialog ? <AddDialog /> : null}
      {Boxes ? <Boxes /> : null}
      {UcBoxes ? <UcBoxes /> : null}
      {MsLayers && status.value === "ready" ? <MsLayers /> : null}
    </>
  );
}
