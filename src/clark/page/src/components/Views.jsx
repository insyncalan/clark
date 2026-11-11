// The other pages as a shell: Work items and the Dashboard (Dashboard.jsx) sit in one frame of the same width (
// "Make Dashboard same width as work items"). The Work items list is WorkItems.jsx (#36).
import { useEffect, useRef, useState } from "preact/hooks";
import { skeleton, reduced } from "../stores/motion.js";
import { status, message, project, projects, projectsState, openProject, tryAgain, view, isFile, data, fromFile, asAt, settingsPage, restoreY, show, openSettings, settingsFallback, takeArrival, wantName } from "../stores/report.js";
import { milestoneRows, headLine, showDate, todayIso } from "../logic/milestones.js";

import { MsBlock } from "./MsBlock.jsx";

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
  const line = headLine(milestoneRows(data.value.milestones, today, client));
  return (
    <>
      <p class="crumbs">{data.value.project.name}</p>
      <div class="head">
        <div>
          <h1>Milestones</h1>
          <p class="head-sub" id="ms-summary">
            {line
              ? <><b>{line.name}</b>{line.date ? ` is ${line.agreed ? "agreed" : "forecast"} for ${showDate(line.date)}` : " has no date yet"}{line.expected ? ` and now expected ${showDate(line.expected)}` : ""}. {line.achieved} achieved, {line.toCome} to come.</>
              : "No milestones yet."}
          </p>
        </div>
        {Add ? <Add /> : null}
      </div>
    </>
  );
}

export function Milestones({ tools }) {
  const Wrap = tools && tools.MilestonesPage;     // the owner's Plan / Movement switch and Movement view (#136, C-M2): the served page only, so a published page has none
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

// The Settings shell (item 1024, option A): a menu down the left and ONE page at a time at its right. The menu names the pages in five
// groups; choosing one is a new history entry (its address is "#settings&s=people", plain "#settings" is Projects), so Back and Forward
// step through the pages, and each page keeps its own place on the screen (stores/report.js). The cards are the ones they always were,
// only drawn on the page that holds them. The menu lists a page only if its tool is here and, for the pages that need an open project,
// only with one open. At 900 px and narrower the menu keeps the row of buttons it had (item 1024, PR 4 turns it into one dropdown line).
function SettingsMenu({ groups, here, onChoose, note }) {
  const nav = useRef(null);
  // Up, Down, Home and End move between entries, in a column or a wrapped row (none is chosen by moving); Left and Right are left to the browser; Enter or Space on one chooses it (it is a button)
  const key = (e) => {
    if (e.altKey || e.ctrlKey || e.metaKey) return;      // the browser's own shortcuts are left alone
    const to = { ArrowDown: 1, ArrowUp: -1, Home: "first", End: "last" }[e.key];
    if (to === undefined) return;
    const items = [...nav.current.querySelectorAll(".set-item")], at = items.indexOf(document.activeElement);
    if (at < 0) return;
    e.preventDefault();
    items[to === "first" ? 0 : to === "last" ? items.length - 1 : Math.max(0, Math.min(items.length - 1, at + to))].focus();
  };
  return (
    <nav class="set-menu" aria-label="Settings pages" ref={nav} onKeyDown={key}>
      {groups.map(([group, pages], i) => (
        <div class={group === "Advanced" ? "set-group set-advanced" : "set-group"} key={group}>
          <p class="set-group-h" id={`set-group-${i}`}>{group}</p>
          {group === "Advanced" ? <p class="set-group-note">{note}</p> : null}
          <ul class="set-list" aria-labelledby={`set-group-${i}`}>{pages.map(([slug, name]) => (
            <li key={slug}><button type="button" class="set-item" aria-current={here === slug ? "page" : undefined} onClick={() => onChoose(slug)}>{name}</button></li>
          ))}</ul>
        </div>
      ))}
    </nav>
  );
}

export function Settings({ tools }) {
  const cfg = tools && tools.SettingsPages;      // the pages, their groups and words are Edit's (edit/settingsPages.js): a published file has no Settings and none of them
  const { GROUPS, ADVANCED_NOTE, NEEDS_PROJECT } = cfg || { GROUPS: [], ADVANCED_NOTE: "", NEEDS_PROJECT: [] };
  const open = !!data.value;      // item 682: with no project open the cards that need one (Publishing, Published reports, Freshness) are left out
  const have = (tool) => !!(tools && tools[tool] && (open || !NEEDS_PROJECT.includes(tool)));      // Edit's tools only: a published file has no Settings
  const groups = GROUPS.map(([group, pages]) => [group, pages.filter(([, , drawn]) => drawn.every(have))]).filter(([, pages]) => pages.length);
  const all = groups.flatMap(([, pages]) => pages);
  const asked = settingsPage.value, page = all.find(([slug]) => slug === asked) || all[0];
  const slug = page ? page[0] : "";
  const shown = useRef(false);
  useEffect(() => () => { wantName.value = false; }, []);      // "Add your name" asked for a box that never drew: leaving Settings spends the wish
  const reading = status.value === "loading";      // read while drawing, so the end of the read draws again
  useEffect(() => { if (!reading && asked && !all.some(([s]) => s === asked)) settingsFallback(); });      // a page that is not here opens Projects: the entry is rewritten, never added; not while the project is still being read (its pages, Folder, are not drawn yet)
  // after a page change the page takes its place on the screen and its heading takes the focus (unless a box in it has already taken it: "Add your name")
  useEffect(() => {
    if (!page) return;
    let moved = false;      // the heading was scrolled to by hand below: the saved place must not be put back over it
    window.scrollTo(0, restoreY.value);
    requestAnimationFrame(() => { if (!moved) window.scrollTo(0, restoreY.value); });      // once the page has its height (a list that arrived a moment later)
    const arrived = takeArrival();
    if (!shown.current) { shown.current = true; if (!arrived) return; }      // a first draw from a reload leaves the focus; one from another screen (Settings unmounts when the view changes) is an arrival, and the heading takes it
    const inside = document.activeElement && document.activeElement.closest && document.activeElement.closest(".set-cards");
    const head = document.getElementById(page[3]);
    if (head && !inside) {
      head.focus({ preventScroll: true });
      // window.scrollTo did not always take (a hosted macOS run had the heading 4466 px down at scrollY 0): only a heading still outside the window, or under the 56 px top bar, is scrolled to
      const r = head.getBoundingClientRect(), kept = restoreY.value > 0 && Math.abs(window.scrollY - restoreY.value) <= 1;      // a restored place may have it off the screen on purpose
      if (!kept && (r.top < 56 || r.bottom > window.innerHeight)) { moved = true; (head.closest("section") || head).scrollIntoView({ block: "start" }); }
    }
  }, [slug]);
  const drawn = page ? page[2] : [];
  return (
    <div class="set-layout">
      <section class="frame set-head">
        <h1>Settings</h1>
        <p class="muted">Where reports are published, how clark looks for you, when an item counts as not reviewed, the log, your backups and asking Claude.</p>
      </section>
      {page ? <SettingsMenu groups={groups} here={slug} onChoose={(s) => (s === "published" ? show("published") : openSettings(s === all[0][0] ? "" : s))} note={ADVANCED_NOTE} /> : null}
      <div class="set-cards" data-settings-page={slug}>
        {drawn.map((tool) => { const Card = tools[tool]; return <Card key={tool} />; })}
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
