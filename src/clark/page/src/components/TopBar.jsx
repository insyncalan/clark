import { useEffect, useLayoutEffect, useRef, useState } from "preact/hooks";
import { ClientMenu } from "./ClientMenu.jsx";
import { TITLES, SHORT_TITLES, shownTabs as tabs, view, show, project, data, fromFile, asAt, mode } from "../stores/report.js";

// A calendar date is shown DD-MM-YYYY (RULES.md); stored YYYY-MM-DD. Never shifted by a time zone.
const shownDate = (iso) => (/^\d{4}-\d\d-\d\d$/.test(iso) ? iso.slice(8) + "-" + iso.slice(5, 7) + "-" + iso.slice(0, 4) : iso);

export function TopBar({ tools }) {
  const name = data.value && data.value.project.name;
  const Toggle = tools && tools.Toggle && !fromFile.value ? tools.Toggle : null;     // View or Edit: only a page clark serves has it
  const ProfileMenu = tools && tools.ProfileMenu && !fromFile.value ? tools.ProfileMenu : null;     // the profile circle's menu (#77)
  const ProjectSwitch = tools && tools.ProjectSwitch && !fromFile.value ? tools.ProjectSwitch : null;     // the project switcher (A-D25)
  const Publish = tools && tools.Publish && !fromFile.value ? tools.Publish : null;     // only a page clark serves can publish
  const HelpButton = tools && tools.HelpButton && !fromFile.value ? tools.HelpButton : null;     // the "?" beside the profile circle: Help
  const SearchButton = tools && tools.SearchButton && !fromFile.value ? tools.SearchButton : null;     // the search icon: opens the command palette
  const AskButton = tools && tools.AskButton && !fromFile.value ? tools.AskButton : null;     // ask clark: opens the ask panel, only while asking is on
  const row = useRef(null);
  const [renaming, setRenaming] = useState(false);      // #926: the Gantt tab's name is a box while it is being renamed (Edit, on the Gantt page)
  const GanttName = tools && tools.GanttTabName && !fromFile.value && mode.value === "edit" ? tools.GanttTabName : null;
  useEffect(() => { if (view.value !== "gantt" || mode.value !== "edit") setRenaming(false); }, [view.value, mode.value]);
  const showOpen = () => {      // row 757: where the tab row scrolls inside its own box (narrow windows), the open tab is brought into it; no animation
    const on = row.current && row.current.querySelector('[aria-selected="true"]');
    if (on && on.scrollIntoView) on.scrollIntoView({ inline: "nearest", block: "nearest", behavior: "auto" });
  };
  useLayoutEffect(showOpen, [view.value, tabs.value.length]);      // a layout effect: the tab is in view in the step that draws the new open tab, not a frame or more later (Preact runs an ordinary effect after the paint)
  useEffect(() => {      // the row narrows or its tabs widen after that (the mode switch joins the bar, the fonts load): bring the open tab in again, on the next frame, once the layout has settled
    if (!row.current) return undefined;
    let frame = 0;
    const later = () => { if (frame) cancelAnimationFrame(frame); frame = requestAnimationFrame(() => { frame = 0; showOpen(); }); };
    const watch = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(later);
    if (watch) { watch.observe(row.current); Array.from(row.current.children).forEach((t) => watch.observe(t)); }
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(later);
    later();
    return () => { if (watch) watch.disconnect(); if (frame) cancelAnimationFrame(frame); };
  }, [tabs.value.length]);
  return (
    <header class="top">
      {fromFile.value
        ? <span class="logo" aria-label="clark"><span class="logo-icon" aria-hidden="true"></span><span class="wm">clark</span></span>      /* a published file has no Home: nothing in it is a button */
        : <button type="button" class="logo" aria-label="clark" onClick={() => show("dashboard")}><span class="logo-icon" aria-hidden="true"></span><span class="wm">clark</span></button>}      {/* row 854: in the app the logo goes Home, the first tab, same project */}
      <span class="divider"></span>
      {ProjectSwitch ? <ProjectSwitch name={name} /> : <span class="proj" id="project-name">{name || project.value || "No project open"}</span>}
      <nav class="tabs" ref={row} role="tablist" aria-label="Views">
        {tabs.value.map((v) => (v === "gantt" && renaming && GanttName && view.value === "gantt"
          ? <span class="tab" role="tab" key={v} data-view={v} aria-selected="true"><GanttName onDone={() => setRenaming(false)} /></span>
          : <button class="tab" role="tab" key={v} data-view={v} aria-selected={view.value === v ? "true" : "false"} onClick={() => (v === "gantt" && GanttName && view.value === "gantt" ? setRenaming(true) : show(v))} title={v === "gantt" && GanttName && view.value === "gantt" ? "Rename the tab" : undefined}>{SHORT_TITLES[v] ? <><span class="tl-full">{TITLES[v]}</span><span class="tl-short">{SHORT_TITLES[v]}</span></> : TITLES[v]}</button>
        ))}
      </nav>
      {fromFile.value && asAt.value ? <span class="asat num">As at {shownDate(asAt.value)}</span> : null}
      {Publish ? <Publish /> : null}
      {Toggle && view.value !== "dashboard" && view.value !== "settings" ? <Toggle /> : null}      {/* item 665: on the Dashboard the switch is the report bar's pill, never drawn twice; row 826: Settings has no switch */}
      {SearchButton ? <SearchButton /> : null}
      {AskButton ? <AskButton /> : null}
      {HelpButton ? <HelpButton /> : null}
      {ProfileMenu ? <ProfileMenu /> : null}
      {fromFile.value ? <ClientMenu /> : null}      {/* issue 713: the reader's badge and menu, a published file only */}
    </header>
  );
}
