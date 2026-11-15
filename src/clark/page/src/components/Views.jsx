// The other pages as a shell: Work items and the Dashboard (Dashboard.jsx) sit in one frame of the same width (
// "Make Dashboard same width as work items"). The Work items list is WorkItems.jsx (#36).
import { useEffect, useRef, useState } from "preact/hooks";
import { skeleton, reduced } from "../stores/motion.js";
import { status, message, project, projects, projectsState, openProject, tryAgain, view, isFile, data, fromFile, asAt } from "../stores/report.js";
import { milestoneRows, headLine, emptyHead, showDate, todayIso } from "../logic/milestones.js";

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
  const rows = milestoneRows(data.value.milestones, today, client), line = headLine(rows);
  return (
    <>
      <p class="crumbs">{data.value.project.name}</p>
      <div class="head">
        <div>
          <h1>Milestones</h1>
          <p class="head-sub" id="ms-summary">
            {line
              ? <><b>{line.name}</b>{line.date ? ` is ${line.agreed ? "agreed" : "forecast"} for ${showDate(line.date)}` : " has no date yet"}{line.expected ? ` and now expected ${showDate(line.expected)}` : ""}. {line.achieved} achieved, {line.toCome} to come.</>
              : emptyHead(rows)}
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

// The Settings head: the title, a line of help and one chip for each card that is on the page. A chip scrolls to its card and moves
// focus to the card's heading. The chips are buttons, not "#" links, because the page's own address (its hash) names the view.
// The links (item 440, S2; issue 697) are a list down the left of the cards at 900 px and wider and the old row of chips under the head below 900 px. Either way it stays under the top bar as you scroll, and the link of the card you are reading is marked (aria-current).
const CARDS = [["Essentials", "Essentials", "essentials-h"], ["Profile", "Profile", "profile-h"], ["ClientFolder", "Publishing", "client-folder-h"], ["Personal", "Personal", "personal-h"], ["ReviewDays", "Freshness", "review-days-h"], ["GanttSetting", "Gantt", "gantt-setting-h"], ["Diagnostics", "Logs and diagnostics", "diagnostics-h"],
  ["Projects", "Projects", "projects-h"], ["Data", "Data", "data-card-h"], ["Safety", "Backups", "safety-h"], ["Update", "", "update-h"], ["Brands", "", "brands-h"],
  ["People", "People", "people-h"], ["AskSettings", "Asking", "ask-settings-h"], ["Feedback", "Feedback", "feedback-h"], ["Quit", "", "quit-h"]];       // in the order the cards are drawn; a card that is not on the page has no chip

const cardOf = (headId) => { const head = document.getElementById(headId); return head ? head.closest("section") || head : null; };

function goToCard(headId) {
  const head = document.getElementById(headId);
  if (!head) return;
  const calm = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  cardOf(headId).scrollIntoView({ block: "start", behavior: calm ? "auto" : "smooth" });
  head.focus({ preventScroll: true });
}

// The card you are reading: the last one whose top has come up to the bar (with a little room). At the foot of the page the last
// cards can never come up that far, so there the chip last chosen stays marked while its card is in view.
function cardHere(cards, picked) {
  const bar = document.querySelector(".set-bar");
  if (!bar || !cards.length) return "";
  const top = document.querySelector(".top"), row = window.matchMedia("(max-width: 899px)").matches;      // a row of chips has the cards under it; a list at the left has them beside it
  const edge = (row ? bar : top || bar).getBoundingClientRect().bottom + 24, foot = window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 2;
  const chosen = picked && cardOf(picked);
  if (foot && chosen && chosen.getBoundingClientRect().top < window.innerHeight) return picked;
  let here = cards[0][2];
  for (const [, , headId] of cards) { const card = cardOf(headId); if (card && card.getBoundingClientRect().top <= edge) here = headId; }
  return here;
}

// Search settings (row 1115, S2): the box in the head. A card whose heading matches stays whole; otherwise a card with setting rows keeps only the rows
// whose name, help line or data-keywords match, and a card without rows stays when its text matches. Cards with no match, and the row of chips, are hidden
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

function SettingsHead({ cards }) {
  const [here, setHere] = useState("");
  const [searching, setSearching] = useState(false);
  const picked = useRef("");
  const ids = cards.map(([, , headId]) => headId).join(" ");
  useEffect(() => {
    const mark = () => setHere(cardHere(cards, picked.current));
    // the row's height (one row of chips or two) is room the browser keeps clear when it scrolls a card or a box into view (shell.css); a list at the left takes none
    const bar = document.querySelector(".set-bar"), root = document.documentElement;
    const room = () => { root.style.setProperty("--set-bar", `${bar ? bar.offsetHeight : 0}px`); mark(); };
    const seen = bar && window.ResizeObserver ? new ResizeObserver(room) : null;
    if (seen) seen.observe(bar);
    room();
    window.addEventListener("scroll", mark, { passive: true });
    return () => { window.removeEventListener("scroll", mark); if (seen) seen.disconnect(); root.style.removeProperty("--set-bar"); };
  }, [ids]);
  const go = (headId) => { picked.current = headId; setHere(headId); goToCard(headId); };
  return (
    <>
      <section class="frame set-head">
        <h1>Settings</h1>
        <p class="muted">Where reports are published, how clark looks for you, when an item counts as not reviewed, the log, your backups and asking Claude.</p>
        <SettingsSearch onQuery={setSearching} />
      </section>
      {cards.length && !searching ? <button type="button" class="skip skip-cards" onClick={() => go(cards[0][2])}>Skip to settings</button> : null}      {/* item 1170: after the search box and before the chips; Enter moves focus to the first card's heading, so Your name is one Tab on instead of seventeen */}
      {cards.length && !searching ? (
        <nav class="set-bar" aria-label="Settings sections">
          <ul class="set-nav">{cards.map(([, name, headId]) => (
            <li key={headId}><button type="button" class="set-chip" aria-current={here === headId ? "location" : undefined} onClick={() => go(headId)}>{name}</button></li>
          ))}</ul>
        </nav>
      ) : null}
    </>
  );
}

export function Settings({ tools }) {
  const open = !!data.value;      // item 682: with no project open the cards that need one (Publishing, Freshness) are left out
  const ClientFolder = open && tools && tools.ClientFolder;      // the client folder (#43); the rest of Settings is FR-1
  const Essentials = tools && tools.Essentials;        // Essentials (row 1115, S3): the first card and the first chip; the eight settings most people come for, drawn again on the shared row; Edit's page only
  const Profile = tools && tools.Profile;              // the Profile card (#950): About you, name, Alias and email; first on the page; Edit's page only
  const Personal = tools && tools.Personal;            // Settings › Personal (#45): Edit's page only; a published file has no Settings
  const ReviewDays = open && tools && tools.ReviewDays;          // Freshness (item 160): the project's "Not reviewed after (days)"
  const GanttSetting = open && tools && tools.GanttSetting;      // Gantt (#926): the two ticks and the tab name, per project
  const Diagnostics = tools && tools.Diagnostics;        // logs and diagnostics (#110)
  const Data = tools && tools.Data;                    // the Data card (A-S11): Export to Excel; Edit only
  const Safety = tools && tools.Safety;                  // the backups (#111); a published file has none
  const Brands = tools && tools.Brands;                  // Brands (#944); a published file has none
  const Update = tools && tools.Update;                  // Version and updates; a published file has none
  // a card's chip says its heading; an Edit-only card with no name here brings its own (`chip`), so a published file never holds it
  const NEEDS_PROJECT = ["ClientFolder", "ReviewDays", "GanttSetting"];
  const cards = CARDS.filter(([tool]) => tools && tools[tool] && (open || !NEEDS_PROJECT.includes(tool))).map(([tool, name, headId]) => [tool, name || tools[tool].chip || "", headId]);
  const AskSettings = tools && tools.AskSettings;        // asking: the switch and its folders (#47)
  const Feedback = tools && tools.Feedback;              // Feedback (#1069): a form that opens the user's mail app; Edit's page only
  const People = tools && tools.People;                  // the People card (item 454): email, organisation, role, Paste from Excel; Edit's page only
  const Quit = tools && tools.Quit;                      // Quit clark (#836); Edit's page only
  const Projects = tools && tools.Projects;              // the projects table (A-S6); a published file has none
  return (
    <div class="set-layout">
      <SettingsHead cards={cards} />
      <div class="set-cards">
      {Essentials ? <Essentials /> : null}
      {Profile ? <Profile /> : null}
      {ClientFolder ? <ClientFolder /> : null}
      {Personal ? <Personal /> : null}
      {ReviewDays ? <ReviewDays /> : null}
      {GanttSetting ? <GanttSetting /> : null}
      {Diagnostics ? <Diagnostics /> : null}
      {Projects ? <Projects /> : null}
      {Data ? <Data /> : null}
      {Safety ? <Safety /> : null}
      {Update ? <Update /> : null}
      {Brands ? <Brands /> : null}
      {People ? <People /> : null}
      {AskSettings ? <AskSettings /> : null}
      {Feedback ? <Feedback /> : null}
      {Quit ? <Quit /> : null}
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
