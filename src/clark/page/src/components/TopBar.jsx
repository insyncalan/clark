import { useEffect, useLayoutEffect, useRef, useState } from "preact/hooks";
import { ClientMenu } from "./ClientMenu.jsx";
import { CardsDate } from "./CardsDate.jsx";
import { ReportSearch } from "./ReportSearch.jsx";
import { classicTheme } from "./Contents.jsx";
import { coverLine } from "../logic/cover.js";
import { TITLES, titleOf, SHORT_TITLES, shownTabs as allTabs, view, show, project, data, fromFile, asAt, mode, status } from "../stores/report.js";

// A calendar date is shown DD-MM-YYYY (RULES.md); stored YYYY-MM-DD. Never shifted by a time zone.
const shownDate = (iso) => (/^\d{4}-\d\d-\d\d$/.test(iso) ? iso.slice(8) + "-" + iso.slice(5, 7) + "-" + iso.slice(0, 4) : iso);

export function TopBar({ tools }) {
  const tabs = { value: allTabs.value.filter((v) => v !== "settings" && v !== "published") };      // row 976: Settings is no tab; it opens from the profile circle's menu (and the address, and Published reports); the route and the view stay
  const name = data.value && data.value.project.name;
  const ProfileMenu = tools && tools.ProfileMenu && !fromFile.value ? tools.ProfileMenu : null;     // the profile circle's menu (#77)
  const ProjectSwitch = tools && tools.ProjectSwitch && !fromFile.value ? tools.ProjectSwitch : null;     // the project switcher (A-D25)
  const Publish = tools && tools.Publish && !fromFile.value ? tools.Publish : null;     // only a page clark serves can publish
  const SearchButton = tools && tools.SearchButton && !fromFile.value ? tools.SearchButton : null;     // the search icon: opens the command palette
  const Bell = tools && tools.Bell && !fromFile.value && classicTheme() ? tools.Bell : null;     // row 1046: the notices bell, left of search; the editor only and Classic only (Cards is frozen: it draws no bell), a published page carries nothing from notices
  const AskButton = tools && tools.AskButton && !fromFile.value ? tools.AskButton : null;     // ask clark: opens the ask panel, only while asking is on
  const HeaderDate = tools && tools.HeaderDate && !fromFile.value ? tools.HeaderDate : null;     // item 1177: the week as a button that opens the calendar (the editor only)
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
  useEffect(() => {      // row 1239: a long project name wraps instead of ending in an ellipsis, so the bar grows; every offset that reads --topbar follows the bar's real height
    const bar = document.querySelector("header.top");
    if (!bar) return undefined;
    const root = document.documentElement;
    const read = () => {      // the bar's own height never depends on --topbar (its minimum is --bar-min), so the override can be dropped before it is measured against the stylesheet's token
      const h = bar.getBoundingClientRect().height;
      root.style.removeProperty("--topbar");
      const token = parseFloat(getComputedStyle(root).getPropertyValue("--topbar"));
      if (h > 0 && !(Math.abs(h - token) < 0.01)) root.style.setProperty("--topbar", h + "px");      // only a bar grown past its token (a long name wrapped) needs the override; otherwise the stylesheet's token follows a resize at once, with no frame of lag
    };
    const watch = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(read);
    if (watch) watch.observe(bar);
    read();
    return () => { if (watch) watch.disconnect(); root.style.removeProperty("--topbar"); };
  }, []);
  const vs = tabs.value, stop = vs.includes(view.value) ? view.value : vs[0];      // roving tabindex: one tab is in the Tab order, the open one (the first when none is open)
  const onTabKey = (e) => {      // Left/Right/Home/End move between the tabs and open the one reached, as in Help
    const i = vs.indexOf(e.target && e.target.dataset ? e.target.dataset.view : "");
    if (i < 0 || e.altKey || e.ctrlKey || e.metaKey) return;      // Alt+Left is the browser's Back, Ctrl/Cmd+arrows are the system's: not ours
    const j = e.key === "ArrowRight" ? (i + 1) % vs.length : e.key === "ArrowLeft" ? (i + vs.length - 1) % vs.length : e.key === "Home" ? 0 : e.key === "End" ? vs.length - 1 : -1;
    if (j < 0) return;
    e.preventDefault(); show(vs[j]);
    setTimeout(() => { const b = row.current && row.current.querySelector(`[data-view="${vs[j]}"]`); if (b) b.focus(); }, 0);
  };
  const file = fromFile.value;
  const lines = file ? coverLine(data.value && data.value.project, "") : [];      // issue 1146: a published file has one bar; the banner's words ("Weekly report", the week) sit under the name
  const ganttTitle = data.value && data.value.gantt && typeof data.value.gantt.title === "string" ? data.value.gantt.title : "";
  const shownName = (view.value === "gantt" && ganttTitle) || name || project.value || "No project open";      // the Gantt page's own title, when the file carries one, as the banner showed it
  const Name = status.value === "ready" && (view.value === "dashboard" || view.value === "gantt") ? "h1" : "div";      // the Dashboard and Gantt pages had their heading in the banner; the other pages have their own
  const weekEnding = data.value && data.value.project && data.value.project.week_ending;
  const tail = (<>
      {Publish ? <Publish /> : null}
      {/* row 804: the top bar never draws View | Edit. It exists only on the Dashboard, as the report bar's pill (ReportBar.jsx, item 665); the other tabs are always editable */}
      {Bell ? <Bell /> : null}
      {SearchButton ? <SearchButton /> : null}
      {/* row 1543: a published report has its own search (the editor's button, a box of its own) */}
      {file ? <ReportSearch /> : null}
      {AskButton ? <AskButton /> : null}
      {ProfileMenu ? <ProfileMenu /> : null}
  </>);
  return (
    <header class={file ? "top top-file" : "top top-hdr"}>
      {fromFile.value
        ? <span class="logo" aria-label="clark"><span class="logo-icon" aria-hidden="true"></span><span class="wm">clark</span></span>      /* a published file has no Home: nothing in it is a button */
        : <button type="button" class="logo" aria-label="clark" onClick={() => show("dashboard")}><span class="logo-icon" aria-hidden="true"></span><span class="wm">clark</span></button>}      {/* row 854: in the app the logo goes Home, the first tab, same project */}
      {file
        ? <div class="top-id"><Name class="top-name" id="project-name" title={classicTheme() ? shownName : undefined}>{shownName}</Name><p class="cover-line top-line"><b class="cover-kind">Weekly report</b>{lines.map((t) => <span key={t}>{t}</span>)}</p></div>
        : <div class="hdr-id">{/* item 1177: the editor's one header: the project name (a button that opens the project list), then "Weekly report" and the week (a button that opens the calendar); no "for <client>" and no banner under it */}
            {(() => {
              const who = ProjectSwitch ? <ProjectSwitch name={name} header /> : <span class="hdr-project hdr-static" id="project-name" title={classicTheme() ? name || project.value || "No project open" : undefined}>{name || project.value || "No project open"}</span>;
              return view.value === "dashboard" && status.value === "ready" ? <h1 class="hdr-h1">{who}</h1> : who;      /* the Dashboard keeps its one level-1 heading: the project name, same size and same click (item 1177 took its cover); the Gantt page has its own in its cover, and the other pages have theirs */
            })()}
            <p class="hdr-line"><b class="hdr-kind">Weekly report</b>{HeaderDate ? <>{" "}<i class="hdr-dot" aria-hidden="true"></i><HeaderDate /></> : weekEnding ? <>{" "}<i class="hdr-dot" aria-hidden="true"></i><span class="hdr-date hdr-static num">Week ending {shownDate(weekEnding)}</span></> : null}</p>
          </div>}
      <nav class="tabs" ref={row} role="tablist" aria-label="Views" onKeyDown={onTabKey}>
        {tabs.value.map((v) => (v === "gantt" && renaming && GanttName && view.value === "gantt"
          ? <span class="tab" role="tab" key={v} data-view={v} aria-selected="true"><GanttName onDone={() => setRenaming(false)} /></span>
          : <button class="tab" role="tab" key={v} data-view={v} aria-selected={view.value === v ? "true" : "false"} tabIndex={v === stop ? 0 : -1} onClick={() => (v === "gantt" && GanttName && view.value === "gantt" ? setRenaming(true) : show(v))} title={v === "gantt" && GanttName && view.value === "gantt" ? "Rename the tab" : undefined}>{SHORT_TITLES[v] ? <><span class="tl-full">{titleOf(v)}</span><span class="tl-short">{SHORT_TITLES[v]}</span></> : titleOf(v)}</button>
        ))}
      </nav>
      {file && asAt.value && !classicTheme() ? <CardsDate /> : null}      {/* Cards only: the date button of a client's header; the Classic header has no date button (row 1543) */}
      {file ? <span class="top-slot" data-slot="theme"></span> : null}      {/* issue 1146: the place for the light and dark switcher icon (issue 1144), before the profile circle; empty, it takes no room */}
      {file ? tail : <div class="hdr-end">{tail}</div>}
      {fromFile.value ? <ClientMenu /> : null}      {/* issue 713: the reader's badge and menu, a published file only */}
    </header>
  );
}
