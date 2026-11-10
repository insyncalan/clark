// The Published reports page (row 1087), Edit parts only: reached only from the profile circle's menu (and the Dashboard's "as at a day"
// choice), no tab and no Dashboard link. It replaces the card that was in Settings. Under the project's own cover band (the brand's
// picture and colours, as on the Dashboard) it says where the report is saved (the Local and Client folders, as Settings holds them) and
// lists what clark published: the latest, then the earlier ones (PublishedReports.jsx), from clark's own record, never from the folder.
// `api`, `openTab`, `toast`, `zone` and `goSettings` are seams for the tests; the page passes none of them.
import { data, project, show } from "../stores/report.js";
import * as L from "../logic/pastReports.js";
import { PublishedReports } from "./PublishedReports.jsx";
import { savedFolder, savedLocal } from "./publishState.js";

export function PublishedPage({ name, goSettings = () => show("settings"), ...rest }) {
  const d = data.value;
  const title = name || (d && d.project && d.project.name) || project.value;
  const local = savedLocal(), client = savedFolder();
  return (
    <div class="pp-page" id="pubs-page">
      <section class="frame pp-frame">
        <header class="cover" id="cover">
          <h1>{L.TITLE}</h1>
          <p class="cover-line"><b class="cover-kind">{title}</b></p>
          <p class="pubs-intro">{L.INTRO}</p>
        </header>
        <div class="pp-where" id="pubs-where">
          <p class="pp-kicker">{L.PAGE.saved}</p>
          <dl>
            <dt>{L.PAGE.local}</dt><dd>{local || L.PAGE.notChosen}</dd>
            <dt>{L.PAGE.client}</dt><dd>{client || L.PAGE.notChosen}</dd>
          </dl>
          <p><button type="button" class="btn sm" id="pubs-settings" onClick={goSettings}>{L.PAGE.change}</button></p>
          <p class="muted small">{L.PAGE.record}</p>
        </div>
        <PublishedReports {...rest} />
      </section>
    </div>
  );
}
