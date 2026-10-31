import { TITLES, tabs, view, show, project, data, fromFile, asAt } from "../stores/report.js";

// A calendar date is shown DD-MM-YYYY (RULES.md); stored YYYY-MM-DD. Never shifted by a time zone.
const shownDate = (iso) => (/^\d{4}-\d\d-\d\d$/.test(iso) ? iso.slice(8) + "-" + iso.slice(5, 7) + "-" + iso.slice(0, 4) : iso);

export function TopBar({ tools }) {
  const name = data.value && data.value.project.name;
  const Toggle = tools && tools.Toggle && !fromFile.value ? tools.Toggle : null;     // View or Edit: only a page clark serves has it
  const ProfileMenu = tools && tools.ProfileMenu && !fromFile.value ? tools.ProfileMenu : null;     // the profile circle's menu (#77)
  const ProjectSwitch = tools && tools.ProjectSwitch && !fromFile.value ? tools.ProjectSwitch : null;     // the project switcher (A-D25)
  const Publish = tools && tools.Publish && !fromFile.value ? tools.Publish : null;     // only a page clark serves can publish
  return (
    <header class="top">
      <span class="logo" aria-label="clark"><span class="logo-icon" aria-hidden="true"></span><span class="wm">clark</span></span>
      <span class="divider"></span>
      {ProjectSwitch ? <ProjectSwitch name={name} /> : <span class="proj" id="project-name">{name || project.value || "No project open"}</span>}
      <nav class="tabs" role="tablist" aria-label="Views">
        {tabs.value.map((v) => (
          <button class="tab" role="tab" key={v} data-view={v} aria-selected={view.value === v ? "true" : "false"} onClick={() => show(v)}>{TITLES[v]}</button>
        ))}
      </nav>
      {fromFile.value && asAt.value ? <span class="asat num">As at {shownDate(asAt.value)}</span> : null}
      {Publish ? <Publish /> : null}
      {Toggle ? <Toggle /> : null}
      {ProfileMenu ? <ProfileMenu /> : null}
    </header>
  );
}
