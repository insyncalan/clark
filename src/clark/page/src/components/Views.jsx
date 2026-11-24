// The other pages as a shell: Work items and the Dashboard (Dashboard.jsx) sit in one frame of the same width (
// "Make Dashboard same width as work items"). The Work items list is WorkItems.jsx (#36).
import { useEffect, useRef, useState } from "preact/hooks";
import { skeleton, reduced } from "../stores/motion.js";
import { status, message, project, projects, projectsState, openProject, tryAgain, view, isFile, data, fromFile, asAt, settingsPage, settingsFeedbackShown, showSettings, token, settingsProject, chooseSettingsProject, SWITCH_TABS } from "../stores/report.js";
import { classicTheme } from "./Contents.jsx";
import { milestoneRows, headLine, emptyHead, showDate, todayIso } from "../logic/milestones.js";

import { MsBlock } from "./MsBlock.jsx";
import { Icon } from "./Icon.jsx";

// The placeholder shown while a project's data is on its way: grey blocks in the shape of the screen, always still (no shimmer), and only if the wait is longer than SKELETON_AFTER_MS, so data that arrives at once never flashes one. A published
// file has its data inside it and no wait, so it never draws one. The words are for a screen reader; the blocks are hidden from it.
export const SKELETON_AFTER_MS = 150;

const BLOCKS = {
  work: () => (
    <>
      <span class="skel skel-line wide" />
      {[0, 1, 2, 3, 4, 5].map((i) => (
        <div class="skel-row" key={i}><span class="skel skel-line" /><span class="skel skel-line wide" /><span class="skel skel-line" /><span class="skel skel-line" /></div>
      ))}
    </>
  ),
  milestones: () => [0, 1, 2, 3, 4].map((i) => <div class="skel-row one" key={i}><span class="skel skel-line wide" /></div>),
  dashboard: () => (
    <>
      <div class="skel-tiles">{[0, 1, 2].map((i) => <span class="skel skel-tile" key={i} />)}</div>
      {[0, 1, 2].map((i) => <div class="skel-sec" key={i}><span class="skel skel-line half" /><span class="skel skel-line wide" /><span class="skel skel-line wide" /></div>)}
    </>
  ),
};

function Loading() {
  const [late, setLate] = useState(false);
  useEffect(() => {
    if (isFile()) return undefined;
    skeleton.value = null;
    const t = setTimeout(() => { setLate(true); skeleton.value = view.value; }, SKELETON_AFTER_MS);
    return () => clearTimeout(t);
  }, []);
  if (!late) return null;
  const Shape = BLOCKS[view.value] || BLOCKS.work;
  return (
    <section class="frame skel-frame">
      <h1 class="sr">Loading</h1>
      <p class="sr">Opening {project.value}.</p>
      <div class="skel-body" aria-hidden="true"><span class="skel skel-title" /><Shape /></div>
    </section>
  );
}

// When the data arrives after a placeholder was drawn, the placeholder fades out over --dur-instant on top of the screen. It
// never takes a click, and it is not drawn at all when the page may not move, where the screen replaces it at once.
export function Leaving() {
  const shape = skeleton.value, still = reduced();
  useEffect(() => {
    if (!shape) return undefined;
    if (still) { skeleton.value = null; return undefined; }
    const t = setTimeout(() => { skeleton.value = null; }, 600);      // if the animation event never comes
    return () => clearTimeout(t);
  }, [shape, still]);
  if (!shape || still) return null;
  const Shape = BLOCKS[shape] || BLOCKS.work;
  return (
    <div class="frame skel-frame skel-leave" aria-hidden="true" onAnimationEnd={() => { skeleton.value = null; }}>
      <div class="skel-body"><span class="skel skel-title" /><Shape /></div>
    </div>
  );
}

function Empty({ title, children, action }) {
  return <section class="frame empty"><h1>{title}</h1><p class="muted">{children}</p>{action}</section>;
}

// The head of the Milestones page (#458; the prototype's): the project, the title, a sentence on where the last milestone stands and,
// in the editor, the Add milestone button. The sentence is worked out from the rows the list shows, so a published file's is the client's.
function MsHead({ Add }) {
  const client = fromFile.value, today = client && asAt.value ? asAt.value : todayIso();
  const rows = milestoneRows(data.value.milestones, today, client), line = headLine(rows), classic = classicTheme();      // row 1329: Classic has no forecast sentence (only the empty / cancelled words); Cards keeps its own
  return (
    <>
      <p class="crumbs">{data.value.project.name}</p>
      <div class="head">
        <div>
          <h1>Milestones</h1>
          {classic
            ? (line ? null : <p class="head-sub">{emptyHead(rows)}</p>)
            : <p class={line ? "head-sub head-sub-off" : "head-sub"} id="ms-summary">
              {line
                ? <><b>{line.name}</b>{line.date ? ` is ${line.agreed ? "agreed" : "forecast"} for ${showDate(line.date)}` : " has no date yet"}{line.expected ? ` and now expected ${showDate(line.expected)}` : ""}. {line.achieved} achieved, {line.toCome} to come.</>
                : emptyHead(rows)}
            </p>}
        </div>
        {Add ? <Add /> : null}
      </div>
    </>
  );
}

export function Milestones({ tools }) {
  const Wrap = !classicTheme() && tools && tools.MilestonesPage;     // the owner's Plan / Movement switch and Movement view (#136, C-M2): the served page only, so a published page has none
  const Archived = tools && tools.ArchivedMilestones;   // Show archived (C-M4): the served page only; a published file holds no archived row
  const Add = tools && !fromFile.value ? tools.MsAdd : null;      // the owner's Add milestone (row 458): always on this page (it has no mode), and never in a published file
  const plan = <><MsBlock place="page" tools={tools} />{Archived ? <Archived /> : null}</>;
  return (
    <section class={`frame milestones${fromFile.value ? " pub" : ""}`} id="milestones">
      <MsHead Add={Add} />
      {Wrap ? <Wrap plan={plan} /> : plan}
    </section>
  );
}

// Settings shows ONE page at a time (row 1024): a menu down the left, the page named in the address (`s`, router.js), and each page change is a Back or Forward step.
// A page holds one or more cards, drawn as before; a card that is not on the page (a published file, or no project open) leaves its page out, and a page with no card is not in the menu.
// Search settings looks at every page at once: while the box holds words the menu is hidden and all the cards that match are shown.
const GROUPS = [
  ["Everyday", [["projects", "Projects", ["Projects"]], ["people", "People", ["People"]], ["profile", "Profile", ["Essentials", "Profile"]]]],
  ["Publishing", [["folder", "Folder", ["ClientFolder"]], ["brand", "Brand", ["Brands"]], ["theme", "Theme", ["ThemeSettings"]]]],
  ["Look and feel", [["appearance", "Appearance", ["Personal"]], ["reports", "Reports", ["ReviewDays", "GanttSetting"]]]],
  ["Data and safety", [["backups", "Backups", ["Safety"]], ["data", "Export and import", ["Data"]]]],
  ["Advanced", [["claude", "Claude and AI", ["AskSettings"]], ["logs", "Logs and diagnostics", ["Diagnostics"]], ["version", "Version and updates", ["Update", "Quit"]]]],
];
// Row 1299 slice 1a, Classic only (the Cards look keeps GROUPS above): the mock-up's four groups and page names. Theme is part of Look, Folder is part of Brand and publishing; the old slugs (s=theme, s=folder) open those pages (OLD_SLUGS)
const GROUPS_CLASSIC = [
  ["You", [["profile", "Profile", ["Essentials", "Profile"]], ["appearance", "Look", ["Personal", "ThemeSettings"]]]],
  ["All projects", [["projects", "Projects overview", ["Projects"]], ["backups", "Backups", ["Safety"]]]],
  ["Project settings", [["reports", "Reports and pages", ["ReviewDays", "GanttSetting"]], ["brand", "Brand and publishing", ["ClientFolder", "Brands"]], ["people", "People", ["People"]], ["claude", "ask clark", ["AskSettings"]], ["data", "Export and import", ["Data"]]]],
  ["Help and about", [["version", "Version and updates", ["Update", "Feedback", "Quit"]], ["logs", "Logs and diagnostics", ["Diagnostics"]]]],
];
const OLD_SLUGS = { folder: "brand", theme: "appearance" };
const AFFECTS_OF = { "You": () => "You", "All projects": () => "All projects", "Project settings": (code) => code };
const ADVANCED_LINE = "These are for setting up Claude, and for when something goes wrong. Most people never need them.";
const NEEDS_PROJECT = ["ClientFolder", "ReviewDays", "GanttSetting"];
const HEADS = { Essentials: "essentials-h", Profile: "profile-h", ClientFolder: "client-folder-h", Personal: "personal-h", ReviewDays: "review-days-h", GanttSetting: "gantt-setting-h", Diagnostics: "diagnostics-h", Projects: "projects-h", Data: "data-card-h", Safety: "safety-h", Update: "update-h", Brands: "brands-h", ThemeSettings: "theme-settings-h", People: "people-h", AskSettings: "ask-settings-h", Feedback: "feedback-h", Quit: "quit-h" };
// Row 1299 slice 1b (W4): the glyph in each menu entry's tile, one per page (the page's own icons, components/Icon.jsx); the tile's class is set-tile-<slug> and the Classic rules in themes/prototype-2.0/rules-2.css colour it (one fill per page); the tile and the window class are drawn in the Classic theme only, Cards draws neither
const SET_ICON = { profile: "user", appearance: "sun", theme: "moon", projects: "board", backups: "archive", reports: "chart", folder: "ul", brand: "flag", people: "people", claude: "sparkle", data: "dl", version: "info", logs: "clock" };

/** The pages this page can show now, as groups: [[group, [[slug, name, [tool names that are here]]]]]. */
function pagesOf(tools, open) {
  const here = (tool) => !!(tools && tools[tool]) && (open || !NEEDS_PROJECT.includes(tool));
  return (classicTheme() ? GROUPS_CLASSIC : GROUPS).map(([group, pages]) => [group, pages.map(([slug, name, list]) => [slug, name, list.filter(here)]).filter(([, , list]) => list.length)]).filter(([, pages]) => pages.length);
}

function focusFirstHead(tool) {
  const head = document.getElementById(HEADS[tool]);
  if (head) head.focus({ preventScroll: false });
}

// Search settings (row 1115, S2): the box in the head. A card whose heading matches stays whole; otherwise a card with setting rows keeps only the rows
// whose name, help line or data-keywords match, and a card without rows stays when its text matches. Cards with no match, and the menu, are hidden
// while the box holds words. Esc or clearing the box brings every card back. It reads the page, so a card that draws later is filtered too.
function searchCards(root, query) {
  const q = query.trim().toLowerCase();
  for (const card of root.querySelectorAll(":scope > section, :scope > .setting")) {
    const rows = [...card.querySelectorAll(".set-row")], hit = (el) => (el.textContent + " " + (el.getAttribute("data-keywords") || "")).toLowerCase().includes(q);
    const head = card.querySelector("h2, h3"), headHit = !!head && head.textContent.toLowerCase().includes(q);
    let show = !q || headHit;
    if (!show && rows.length) { for (const r of rows) { const m = hit(r); r.hidden = !m; show = show || m; } }
    else { for (const r of rows) r.hidden = false; if (!show) show = hit(card); }
    card.hidden = !show;
  }
}

function SettingsSearch({ onQuery }) {
  const [q, setQ] = useState("");
  useEffect(() => {
    const root = document.querySelector(".set-cards");
    if (!root) return undefined;
    const run = () => searchCards(root, q);
    run();
    const seen = window.MutationObserver ? new MutationObserver(run) : null;
    if (seen) seen.observe(root, { childList: true, subtree: true });
    onQuery(q.trim() !== "");
    return () => { if (seen) seen.disconnect(); };
  }, [q]);
  return (
    <div class="set-search">
      <label for="set-search-box">Search settings</label>
      <input id="set-search-box" type="search" value={q} autocomplete="off" onInput={(e) => setQ(e.currentTarget.value)} onKeyDown={(e) => { if (e.key === "Escape" && q) { e.preventDefault(); setQ(""); } }} />
    </div>
  );
}

function SettingsHead({ groups, page, searching, setSearching }) {
  const go = (slug) => showSettings(slug);
  const first = groups.length ? page[2][0] : "";
  return (
    <>
      <section class="frame set-head">
        <h1>Settings</h1>
        <p class="muted">Where reports are published, how clark looks for you, when an item counts as not reviewed, the log, your backups and asking Claude.</p>
        <SettingsSearch onQuery={setSearching} />
      </section>
      {first && !searching ? <button type="button" class="skip skip-cards" onClick={() => focusFirstHead(first)}>Skip to settings</button> : null}      {/* item 1170: after the search box and before the menu; Enter moves focus to the page's first heading, so Your name is one Tab on instead of seventeen */}
      {groups.length && !searching ? (
        <nav class="set-bar" aria-label="Settings pages">
          <ul class="set-nav">{groups.map(([group, pages]) => (
            <li key={group} class={`set-group${group === "Advanced" ? " set-advanced" : ""}`}>
              <span class="set-group-name">{group}</span>
              {group === "Advanced" ? <span class="set-group-line muted">{ADVANCED_LINE}</span> : null}
              <ul class="plain">{pages.map(([slug, name]) => (
                <li key={slug}><button type="button" class="set-chip" aria-current={page[0] === slug ? "page" : undefined} onClick={() => go(slug)}>{classicTheme() ? <span class={`set-tile set-tile-${slug}`} aria-hidden="true"><Icon name={SET_ICON[slug] || "circleminus"} /></span> : null}{name}</button></li>
              ))}</ul>
            </li>
          ))}</ul>
        </nav>
      ) : null}
    </>
  );
}

// Row 1299 (project tabs, Classic only): across the top of the project pages, one tab for each project, pinned while the page scrolls. The tab is the project
// open in the app (the address's `p`); a click on another sets the Settings-only project (stores/report.js settingsProject): no page read, the address and the top bar stay. Pages that hold one project's settings only; All projects and You pages have none.
export const PROJECT_PAGES = ["reports", "brand", "people", "claude", "data"];
// Off until the project cards (client folder, review days, brand, people, ask clark, data) read settingsProjectNow() and not the open project: a click on another tab
// would say "Affects: HAR" while the controls still edit the open project. With it off the other tabs are drawn but cannot be chosen.

function ProjectTabs({ current }) {
  const [list, setList] = useState([]);
  useEffect(() => {
    let live = true;
    globalThis.fetch("/api/projects", { headers: { "X-Clark-Token": token() }, cache: "no-store" })
      .then((r) => r.json().then((b) => (r.ok && b.ok && Array.isArray(b.projects) ? b.projects : [])))
      .then((rows) => { if (live) setList(rows); })
      .catch(() => {});
    return () => { live = false; };
  }, []);
  if (!list.length) return null;      // no projects, or the list not read: no bar
  return (
    <nav class="set-tabs" aria-label="Projects">
      <ul>{list.map((p) => (
        <li key={p.code}><button type="button" class="set-tab" aria-current={p.code === current ? "page" : undefined} aria-disabled={p.code !== current && !SWITCH_TABS ? "true" : undefined} onClick={() => { if (p.code === current || SWITCH_TABS) chooseSettingsProject(p.code); }}>{p.name || p.code}</button></li>
      ))}</ul>
    </nav>
  );
}

export function Settings({ tools }) {
  const open = !!data.value;      // item 682: with no project open the cards that need one (Publishing, Freshness) are left out
  const [searching, setSearching] = useState(false);
  const groups = pagesOf(tools, open);
  const all = groups.flatMap(([, pages]) => pages);
  const page = all.find(([slug]) => slug === (classicTheme() && OLD_SLUGS[settingsPage.value] || settingsPage.value || "projects")) || all[0] || ["", "", []];
  const shown = searching ? all.flatMap(([, , list]) => list) : page[2];
  const group = (groups.find(([, pages]) => pages.includes(page)) || [])[0], scope = AFFECTS_OF[group], affects = !searching && scope && classicTheme() ? scope(settingsProject.value || project.value) : "";
  return (
    <div class={classicTheme() ? "set-layout set-win" : "set-layout"}>
      <SettingsHead groups={groups} page={page} searching={searching} setSearching={setSearching} />
      <div class="set-cards" data-page={searching ? undefined : page[0]}>
        {affects ? <p class="set-affects muted">Affects: {affects}</p> : null}
        {classicTheme() && !searching && open && PROJECT_PAGES.includes(page[0]) ? <ProjectTabs current={settingsProject.value || project.value} /> : null}
        {shown.map((tool) => { const Card = tools[tool]; return <Card key={tool} />; })}
      </div>
    </div>
  );
}

// item 427: in the Docker route there is no --demo flag. The server's page carries data-container="1" on <html> then (page.page_html).
const inContainer = () => typeof document !== "undefined" && document.documentElement.dataset.container === "1";

// The "No project open" screen: the projects to choose from or, when there are none (or the list could not be read), what to do.
function NoProject({ tools }) {
  const NewProject = tools && tools.NewProjectButton;      // #731: the Edit page's one button here (a published file has no empty screen)
  const list = projects.value, state = projectsState.value;
  if (state === "loading") return <Empty title="No project open">Looking for projects.</Empty>;
  if (state === "failed") return <Empty title="No project open" action={<button type="button" class="again" onClick={tryAgain}>Try again</button>}>{message.value}</Empty>;
  if (!list.length) {
    return (
      <section class="frame empty">
        <h1>No project open</h1>
        <p class="muted">There are no projects yet.</p>
        {NewProject ? <p><NewProject /></p> : null}
        {inContainer() ? null : <p class="muted">To look around with made-up projects, close clark and start it again from the clark folder with <code>bash clark.command --demo</code>.</p>}
      </section>
    );
  }
  return (
    <section class="frame empty">
      <h1>No project open</h1>
      <p class="muted">Choose a project.</p>
      <ul class="plain choose">{list.map((p) => <li key={p.code}><button type="button" class="link" onClick={() => openProject(p.code)}>{p.name}</button> <span class="muted num">{p.code}</span></li>)}</ul>
    </section>
  );
}

export function Gate({ tools }) {
  const s = status.value;
  if (s === "none") return <NoProject tools={tools} />;
  if (s === "loading") return isFile() ? <Empty title="Loading">Opening {project.value}.</Empty> : <Loading key={project.value} />;
  if (s === "missing") return <Empty title="That project isn't here">{message.value || "Check the project's code."}</Empty>;
  if (s === "failed") return <Empty title="Something went wrong" action={<button type="button" class="again" onClick={tryAgain}>Try again</button>}>{message.value}</Empty>;
  return null;
}
