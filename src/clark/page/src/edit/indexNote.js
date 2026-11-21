// The quiet status line under each source folder in Settings (row 1371): where the folder's index has got to. Plain functions the card and the
// tests both use; nothing here reads the page or the network. The state it reads is a stand-in until the index reports one:
// {phase: "waiting"|"reading"|"done"|"updating"|"paused"|"failed"|"cleared", read, total, left_out, changed, date}.
// Never a file name, a path or any text of a file. The percent is the share of the files read, never a time estimate.
export const ANNOUNCE_AT = [0, 25, 50, 75, 100];     // the screen-reader line says the state at these only, not every percent

export const WAITING = "Waiting to index";
export const NO_FILES = "No files to index";
export const PAUSED = "Indexing paused. It carries on when clark is open";
export const FAILED = "Could not index this folder.";
export const CLEARED = "Not indexed.";
// The links a note carries, built as links by the card (never dropped): the words on the link, then what it does.
export const LINKS = { why: "(why)", retry: "Try again", reindex: "Index again" };   // "(why)" opens the list of files left out

const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;

/** The percent of files read, a whole number 0..100; 100 only when every file is read. */
export function percent(read, total) {
  if (!Number.isFinite(read) || !Number.isFinite(total) || total <= 0) return 0;
  const p = Math.floor((Math.max(0, read) / total) * 100);
  return read >= total ? 100 : Math.min(p, 99);
}

/** The note of the All projects tab: how many projects are indexed. */
export const projectsNote = (done, all) => `Indexed for ${done} of ${all} projects`;

/** The words of the note, plus the link it carries ("" none, "why", "retry", "reindex"); LINKS[link] is the link's own text. */
export function note(s) {
  const st = s || {};
  if (st.phase === "waiting") return { text: WAITING, link: "" };
  if (st.phase === "reading") return { text: `Indexing… ${percent(st.read, st.total)}%`, link: "" };
  if (st.phase === "updating") return { text: `Updating… ${plural(st.changed || 0, "file", "files")} changed`, link: "" };
  if (st.phase === "paused") return { text: PAUSED, link: "" };
  if (st.phase === "failed") return { text: FAILED, link: "retry" };
  if (st.phase === "cleared") return { text: CLEARED, link: "reindex" };
  if (st.phase === "done") {
    if (!(st.total > 0)) return { text: NO_FILES, link: "" };
    const out = st.left_out > 0;
    let text = "100% indexed";
    if (out) text += `. ${plural(st.left_out, "file", "files")} could not be read`;
    return { text, link: out ? "why" : "" };
  }
  return { text: "", link: "" };
}

/** The milestone (0, 25, 50, 75, 100) a state has reached, or -1 when it is not a reading state. */
export function milestone(s) {
  if (!s) return -1;
  if (s.phase === "done") return s.total > 0 ? 100 : -1;
  if (s.phase !== "reading") return -1;
  const p = percent(s.read, s.total);
  return ANNOUNCE_AT.filter((m) => m <= p && m < 100).pop();
}

/** The sentence for the polite live region, or "" when nothing should be said: only when a milestone is first reached. */
export function announce(prev, next) {
  const m = milestone(next);
  if (m < 0 || m === milestone(prev)) return "";
  if (m === 100) return note(next).text;
  return m === 0 ? "Indexing started" : `Indexing… ${m}%`;
}
