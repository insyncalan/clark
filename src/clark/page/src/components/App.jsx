// The page: the top bar and the open view. `tools` is what Edit adds (edit/index.js); the published page passes none.
import { useLayoutEffect, useRef } from "preact/hooks";
import { view, status, tabs, fromFile, isFile, publication, asAt, rebuilt, data, TITLES } from "../stores/report.js";
import { AsAtBanner } from "./AsAtBanner.jsx";
import { printing } from "../stores/print.js";
import { printTabs, publishedLine } from "../logic/printView.js";
import { plainDate } from "../logic/picker.js";
import { TopBar } from "./TopBar.jsx";
import { Milestones, Settings, Gate, Leaving } from "./Views.jsx";
import { Dashboard } from "./Dashboard.jsx";
import { Peek } from "./Peek.jsx";
import { UseCasesTab } from "./UseCasesTab.jsx";
import { WorkItems } from "./WorkItems.jsx";
import { ClientReport } from "./ClientReport.jsx";

const PAGES = { dashboard: Dashboard, work: WorkItems, milestones: Milestones, usecases: UseCasesTab, clientreport: ClientReport, settings: Settings };

// The printed page (item 438): every tab the file has, one after another, each under its own name, with the day it was published at the head.
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

// Row 876: on a tab change only (the view name changes, never a redraw in place) <main> gets .view-in, which shell.css animates under
// no-preference only; the class comes off when it ends, so the next change starts it again.
function useViewEnter() {
  const was = useRef(view.value);
  useLayoutEffect(() => {
    if (was.current === view.value) return;
    was.current = view.value;
    const el = document.getElementById("main");
    if (!el) return;
    el.classList.remove("view-in");
    void el.offsetWidth;
    el.classList.add("view-in");
    const done = (e) => { if (e.target !== el) return; el.classList.remove("view-in"); el.removeEventListener("animationend", done); };   // not a child's own animation ending
    el.addEventListener("animationend", done);
  }, [view.value]);
}

export function App({ tools: given }) {
  useViewEnter();
  // item 349: the Dashboard as at a day is read only: the page draws it as a published file is drawn, with no Edit part at all (no
  // Edit, Publish, menu, peek tools, Help, palette or ask panel), behind its banner; Back to now gives them back.
  const past = !!rebuilt.value && !fromFile.value;
  const tools = past ? null : given;
  const own = (tabs.value.includes(view.value) && PAGES[view.value]) || Dashboard;   // a view the file or editor does not offer falls back to the dashboard
  const Page = view.value !== "usecases" ? own : fromFile.value ? UseCasesTab : (tools && tools.UseCasesPage) || Dashboard;   // the Use cases page is the editor's; a published file has its own view-only tab
  const DemoBanner = !fromFile.value && tools && tools.DemoBanner;         // #731: the demo data line (Edit only); a published file has none, nor has any page drawn from one
  const Toast = tools && tools.Toast;
  const RowMenu = tools && tools.RowMenu;               // the right-click menu on a work item (#97); a published file has none
  const Layer = tools && tools.HelpLayer;                // Help (#82) sits over the open page; a published file has none
  const Pal = tools && tools.Palette;                    // the command palette (#198); a published file has none
  const Ask = tools && tools.AskPanel;                   // the ask panel (#47a) sits over the open page; a published file has none
  const HPeek = tools && tools.HelpPeek;                 // the Help peek (#645) sits at the right edge over the open page; a published file has none
  const stacked = fromFile.value && printing.value && status.value === "ready";
  // #656: with no project open Settings still opens, for its Projects card (Add project) and its Data card: a first install has no other way to make a project
  const bare = status.value === "none" && view.value === "settings" && !fromFile.value && !!tools && !!tools.Projects;
  const body = bare ? <Settings tools={tools} /> : status.value === "ready" ? <>{past ? <AsAtBanner /> : null}<Page tools={tools} /><Leaving /></> : <Gate tools={tools} />;
  const AddDialog = tools && tools.AddDialog;
  const Boxes = tools && tools.Boxes;                    // the boxes Settings opens (item 444): the project form and Import workbook; a published file has none
  const UcBoxes = tools && tools.ucEdit && tools.ucEdit.Boxes;      // the Dashboard's use case boxes (#455): beside <main>, which they make inert
  const MsLayers = tools && tools.MsLayers;              // the milestone picker and an archived milestone's peek (Edit only)
  return (
    <>
      <TopBar tools={tools} />
      {DemoBanner ? <DemoBanner /> : null}
      <main id="main" aria-busy={status.value === "loading" && !isFile() ? "true" : undefined}>{stacked ? <PrintStack tools={tools} /> : Layer ? <Layer>{body}</Layer> : body}</main>
      {publication.value ? <footer class="pubfoot num" id="publication-footer">{asAt.value ? `Published ${plainDate(asAt.value)}. ` : ""}Publication {publication.value}.</footer> : null}
      {Ask ? <Ask /> : null}
      {HPeek && status.value === "ready" ? <HPeek /> : null}
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
