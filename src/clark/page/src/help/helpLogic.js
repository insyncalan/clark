// Help's rules as plain functions with no page and no clock (#82; BRD 5.13, FR-120 to FR-124). The words live in one file,
// helpContent.json, and the three tabs (Start here, How do I…, Reference), the search across all three, the keys list, the icon
// legend and "open Help at a place" are all worked out from it. The search follows the prototype's (system/prototype/help.js):
// words match from their start, a plural matches its singular, a title match counts most, every word must be found.
// Nothing here draws anything: the panel (when its page wiring lands) calls these and paints the result.
// FOR THE RULING (the owner / the review): the source says "Delete section" because that is what the section menu's button says today
// (edit/Gutter.jsx; a text section can really be deleted). Every other record is archived, never deleted, in Help. If the section
// button becomes Archive, change the one phrase in helpContent.json and SECTION_DELETE in tests/test_help_shown.py together.
import RAW from "clark-help-content";      // helpContent.json; the build aliases it to the same file without the held entries (dev/tools/build_page.py)
import LATER from "./helpLater.json";

const PREFIX = { howto: "howto-", reference: "ref-", start: "start-" };
export const START_PARTS = ["top", "loop", "first", "jobs", "where", "rules", "foot"];
// What each held part of Start here takes with it: the source's fields, emptied while the part is held.
const START_FIELDS = {
  top: { hero: { label: "", title: "", lead: "" } },
  loop: { loop: [], text: ["loop_title", "loop_intro", "loop_return"] },
  first: { first: [], text: ["first_title"] },
  jobs: { jobs: [], text: ["jobs_title", "jobs_intro"] },
  where: { where: [], text: ["where_title", "keyline", "keyline_link"] },
  rules: { rules: [], text: ["rules_title"] },
  foot: { text: ["foot", "foot_link"] },
};

/**
 * What Help shows: the source without the entries held in helpLater.json (an entry for a part of clark that is not on the page
 * yet). Held ids leave the tab lists, the search and the places; a group with nothing left goes too; `start.parts` lists the parts
 * of Start here still shown. The source is not changed. `later` is the held list ({} holds nothing).
 */
export function shownContent(raw, later) {
  const L = later || {}, c = JSON.parse(JSON.stringify(raw));
  const heldStart = Object.keys(L.start || {});
  c.start.parts = START_PARTS.filter((p) => !heldStart.includes(p));
  for (const p of heldStart) {
    const f = START_FIELDS[p] || {};
    for (const k of Object.keys(f)) {
      if (k === "text") f.text.forEach((t) => { c.start.text[t] = ""; });
      else c.start[k] = JSON.parse(JSON.stringify(f[k]));
    }
  }
  c.howto.tasks = c.howto.tasks.filter((x) => !(x.id in (L.howto || {})));
  c.reference.sections = c.reference.sections.filter((x) => !(x.id in (L.reference || {})));
  c.howto.groups = c.howto.groups.filter((g) => c.howto.tasks.some((x) => x.g === g));
  c.reference.groups = c.reference.groups.filter((g) => c.reference.sections.some((x) => x.g === g));
  const heldKeys = new Set((L.keys || []).map((k) => k.at));
  c.reference.keys = c.reference.keys.filter((_, i) => !heldKeys.has(i));
  return c;
}

let CONTENT = shownContent(RAW, LATER);
export let content = CONTENT;
/** For tests: show the source with a different held list ({} shows everything). The page never calls this. */
export function useHeld(later) { CONTENT = content = shownContent(RAW, later); }
export const TABS = CONTENT.tabs.map(([key, name]) => ({ key, name }));
const TAB_KEYS = TABS.map((t) => t.key);

// The screens a "go:" link may take you to. A settings anchor ("settings#profile") is a place on the Settings screen.
export const SCREENS = ["dashboard", "dashboard+edit", "work", "milestones", "settings", "publish", "preview", "ask"];
export const GO_LABEL = {
  dashboard: "Open the Dashboard", "dashboard+edit": "Open the Dashboard in Edit", work: "Open Work items", milestones: "Open Milestones",
  settings: "Open Settings", publish: "Open the Publish box", preview: "Preview the page", ask: "Open ask clark",
};
export const goLabel = (to) => GO_LABEL[to] || (String(to).startsWith("settings#") ? "Open Settings" : "Open it");

const KEY_NAMES = { Enter: "Enter", Esc: "Esc", Left: "←", Right: "→", Up: "↑", Down: "↓", Space: "Space", Tab: "Tab" };

// The text with its small markup taken off: **bold**, `code`, [[keys]] and [words](#place) / [words](go:screen).
export function plain(s, mac = false) {
  return String(s == null ? "" : s)
    .replace(/\[\[(.+?)\]\]/g, (_, k) => k.split(/\+(?!$)/).map((p) => (p === "Mod" ? (mac ? "⌘" : "Ctrl") : KEY_NAMES[p] || p)).join("+"))
    .replace(/\*\*(.+?)\*\*/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\[([^\]]+)\]\((?:#|go:)[^)]+\)/g, "$1");
}

// ---------- the tab lists ----------
export const tasks = () => CONTENT.howto.tasks;
export const sections = () => CONTENT.reference.sections;
export const jobs = () => CONTENT.start.jobs.map(([id, title, does, go]) => ({ id, place: `howto-${id}`, title, does, go }));
export const firstTen = () => CONTENT.start.first;
export const loopSteps = () => CONTENT.start.loop;

/** A tab as its groups, each with its entries (id, title, place): the contents list down the side of How do I… and Reference. */
export function tabList(tab) {
  const by = (groups, list, pre) => groups.map((g) => ({ group: g, entries: list.filter((x) => x.g === g).map((x) => ({ id: x.id, title: x.t, place: pre + x.id })) }));
  if (tab === "howto") return by(CONTENT.howto.groups, tasks(), PREFIX.howto);
  if (tab === "reference") return by(CONTENT.reference.groups, sections(), PREFIX.reference);
  if (tab === "start") return CONTENT.start.parts.length ? [{ group: "Start here", entries: CONTENT.start.parts.map((p) => ({ id: p, title: startTitle(p), place: PREFIX.start + p })) }] : [];
  return [];
}

function startTitle(part) {
  const t = CONTENT.start.text;
  return { top: CONTENT.start.hero.title, loop: t.loop_title, first: t.first_title, jobs: t.jobs_title, where: t.where_title, rules: t.rules_title, foot: "Start here" }[part];
}

// ---------- the keys and the icons ----------
/** The keys table: what to press (plain, with ⌘ on a Mac) and what it does. */
export const keysList = (mac = false) => CONTENT.reference.keys.map(([k, d]) => ({ keys: plain(k, mac), does: plain(d, mac) }));
/** The icon legend: the icon's name in the page's icon set, its title, what it does and where it is. */
export const iconLegend = () => CONTENT.reference.icons.map(([icon, title, does, where]) => ({ icon, title, does: plain(does), where }));
/** The milestone marks, their words and what each means (the page draws the marks). */
export const milestoneMarks = () => CONTENT.reference.milestone_states.concat(CONTENT.reference.milestone_extra).map(([state, means]) => ({ state, means: plain(means) }));

// ---------- the places ----------
/** Every place Help can open at: "start-top", "howto-publish-the-report", "ref-keys" and so on. */
export function placeIds() {
  return CONTENT.start.parts.map((p) => PREFIX.start + p)
    .concat(tasks().map((x) => PREFIX.howto + x.id), sections().map((x) => PREFIX.reference + x.id));
}

/**
 * Where C.help.open(where) lands: { tab, target, known }. Nothing (or an empty text) opens the tab used last. A tab name opens
 * that tab. A place opens its tab and scrolls to it; a place that does not exist opens the tab used last and says known: false.
 */
export function placeOf(where, lastTab = "start") {
  const last = TAB_KEYS.includes(lastTab) ? lastTab : "start";
  const w = typeof where === "string" ? where.trim() : "";
  if (!w) return { tab: last, target: null, known: true };
  if (TAB_KEYS.includes(w)) return { tab: w, target: null, known: true };
  const tab = TAB_KEYS.find((t) => w.startsWith(PREFIX[t]));
  if (!tab) return { tab: last, target: null, known: false };
  return placeIds().includes(w) ? { tab, target: w, known: true } : { tab, target: null, known: false };
}

// ---------- every link inside Help ----------
function strings(o, out) {
  if (typeof o === "string") out.push(o);
  else if (Array.isArray(o)) o.forEach((x) => strings(x, out));
  else if (o && typeof o === "object") Object.values(o).forEach((x) => strings(x, out));
  return out;
}

/** The text of the source: everything a person reads. */
export function allText() {
  return strings({ start: CONTENT.start, howto: CONTENT.howto, reference: CONTENT.reference }, []);
}

/** The links in the text: `inside` (places in Help, "howto-x") and `screens` ("work", "settings#profile"), each once. */
export function linksIn() {
  const inside = new Set(), screens = new Set(), re = /\]\((#|go:)([^)]+)\)/g;
  for (const s of allText()) for (const m of s.matchAll(re)) (m[1] === "#" ? inside : screens).add(m[2]);
  for (const j of CONTENT.start.jobs) { inside.add(`howto-${j[0]}`); screens.add(j[3]); }
  for (const t of tasks()) if (t.go) screens.add(t.go);
  for (const w of CONTENT.start.where) if (w[2]) screens.add(w[2]);
  inside.add("ref-keys");   // the Start here key line links to it
  return { inside: [...inside], screens: [...screens] };
}

// ---------- search ----------
const norm = (s) => String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
export const wordsOf = (s) => norm(s).match(/[a-z0-9]+/g) || [];
const stems = (w) => {
  const c = [w];
  if (w.length > 3) { if (w.endsWith("ies")) c.push(w.slice(0, -3) + "y"); if (w.endsWith("es")) c.push(w.slice(0, -2)); if (w.endsWith("s")) c.push(w.slice(0, -1)); }
  return c;
};
const hit = (q, t) => stems(q).some((c) => c.length >= 2 && t.startsWith(c));

function entry(tab, id, title, lines) {
  const ls = lines.map((l) => plain(l)).filter(Boolean);
  return { tab, id, title, lines: ls, tw: wordsOf(title), lw: ls.map(wordsOf) };
}

function refLines(sec, dynamic) {
  const R = CONTENT.reference, out = [];
  if (sec.w) out.push("Where: " + sec.w);
  for (const [k, a, b] of sec.b) {
    if (k === "p") out.push(a);
    else if (k === "ul") out.push(...a);
    else if (k === "tbl") b.forEach((r) => out.push(...r));
    else if (k === "keys") R.keys.forEach((r) => out.push(...r));
    else if (k === "icons") R.icons.forEach(([, t, d, w]) => out.push(t, d, w));
    else if (k === "marks") milestoneMarks().forEach((m) => out.push(m.state, m.means));
    else if (dynamic && Array.isArray(dynamic[k])) out.push(...dynamic[k]);   // "types" and "ai": the page supplies them
  }
  return out;
}

/** The search index over all three tabs, from the source alone. `dynamic` adds the lines of the parts the page fills in. */
export function buildIndex(dynamic = null) {
  const S = CONTENT.start, T = S.text, idx = [];
  const add = (...a) => idx.push(entry(...a));
  const on = (p) => S.parts.includes(p);
  if (on("top")) add("start", "start-top", S.hero.title, [S.hero.label, S.hero.lead]);
  if (on("loop")) add("start", "start-loop", T.loop_title, [T.loop_intro, ...S.loop.map((x) => `${x.t}. ${x.d}`), T.loop_return]);
  if (on("first")) add("start", "start-first", T.first_title, S.first.map((x) => `${x.t}. ${x.d}`));
  if (on("jobs")) add("start", "start-jobs", T.jobs_title, [T.jobs_intro, ...S.jobs.map((j) => `${j[1]} ${j[2]}`)]);
  if (on("where")) add("start", "start-where", T.where_title, [...S.where.map((w) => `${w[0]}. ${w[1]}`), T.keyline]);
  if (on("rules")) add("start", "start-rules", T.rules_title, S.rules.map((r) => `${r[0]}. ${r[1]}`));
  if (on("foot")) add("start", "start-foot", "Start here", [T.foot, T.foot_link]);
  tasks().forEach((x) => add("howto", PREFIX.howto + x.id, x.t, ["Where: " + x.w, ...x.s, ...(x.n ? [x.n] : []), ...(x.say ? ["Or ask clark: " + x.say.join(" ")] : [])]));
  sections().forEach((x) => add("reference", PREFIX.reference + x.id, x.t, refLines(x, dynamic)));
  return idx;
}

/**
 * The matches for a search, best first: { tab, id, title, line, score } where `line` is the number of the line that matched best
 * (-1: only the title matched). Every word of the search (two letters or more) has to be found, in the title or in a line.
 * No words, no results. Nothing is sent anywhere.
 */
export function search(index, q) {
  const qw = wordsOf(q).filter((w) => w.length >= 2);
  if (!qw.length) return [];
  const out = [];
  index.forEach((e, n) => {
    let s = 0;
    for (const w of qw) {
      if (e.tw.some((x) => hit(w, x))) s += 10;
      else if (!e.lw.some((l) => l.some((x) => hit(w, x)))) return;
    }
    let li = -1, best = 0;
    e.lw.forEach((l, i) => { const k = qw.filter((w) => l.some((x) => hit(w, x))).length; if (k > best) { best = k; li = i; } });
    out.push({ n, tab: e.tab, id: e.id, title: e.title, line: li, score: s + best * 3 + (e.tab === "howto" ? 1 : 0) });
  });
  return out.sort((a, b) => b.score - a.score || a.n - b.n);
}

/**
 * A line of a result as parts, the words the search matched marked: [{ t: "text", hit: true | false }]. A long line that
 * matches late starts a little before the match, with an ellipsis (the prototype's `mark`, help.js). Never HTML: the page draws
 * each part as text, a marked one inside <mark>.
 */
export function markParts(line, q) {
  const qw = wordsOf(q).filter((w) => w.length >= 2), s = String(line == null ? "" : line), out = [];
  let last = 0, first = -1;
  for (const m of s.matchAll(/[\p{L}\p{N}]+/gu)) {
    if (!qw.some((w) => hit(w, norm(m[0])))) continue;
    if (first < 0) first = m.index;
    if (m.index > last) out.push({ t: s.slice(last, m.index), hit: false });
    out.push({ t: m[0], hit: true });
    last = m.index + m[0].length;
  }
  if (last < s.length) out.push({ t: s.slice(last), hit: false });
  if (first > 60 && s.length > 170) {
    const cut = s.lastIndexOf(" ", first - 40);
    if (cut > 0) return [{ t: "…", hit: false }, ...markParts(s.slice(cut + 1), q)];
  }
  return out;
}

const TAB_NAME = Object.fromEntries(CONTENT.tabs);
/** The results as the panel shows them: a count line, then groups in the order How do I…, Reference, Start here. */
export function resultsView(index, q) {
  const trimmed = String(q || "").trim();
  if (!trimmed) return { kind: "none-asked", count: 0, groups: [] };
  const res = search(index, q);
  if (!res.length) return { kind: "empty", count: 0, groups: [], ...noResults(trimmed) };
  const groups = ["howto", "reference", "start"].map((t) => ({ tab: t, name: TAB_NAME[t], results: res.filter((r) => r.tab === t) })).filter((g) => g.results.length);
  return { kind: "results", count: res.length, line: `${res.length} result${res.length === 1 ? "" : "s"}`, groups };
}

/** What a search with no match says. It points to the tabs (ask clark returns when it exists), and the word searched for is shown as text, never as markup. */
export const noResults = (q) => ({ title: `Nothing in Help for “${String(q).trim()}”`,
  hint: String(q).trim().length < 2 ? "Type at least two letters." : "Try another word, or look through the tabs." });
