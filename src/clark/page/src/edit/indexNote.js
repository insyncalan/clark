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

const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;

/** The percent of files read, a whole number 0..100; 100 only when every file is read. */
export function percent(read, total) {
  if (!Number.isFinite(read) || !Number.isFinite(total) || total <= 0) return 0;
  const p = Math.floor((Math.max(0, read) / total) * 100);
  return read >= total ? 100 : Math.min(p, 99);
}

const dmy = (d) => (/^\d{4}-\d{2}-\d{2}/.test(String(d || "")) ? `${d.slice(8, 10)}-${d.slice(5, 7)}-${d.slice(0, 4)}` : "");

/** The words of the note, plus the link it carries ("" none, "why", "again"). */
export function note(s) {
  const st = s || {};
  if (st.phase === "waiting") return { text: WAITING, link: "" };
  if (st.phase === "reading") return { text: `Indexing… ${percent(st.read, st.total)}%`, link: "" };
  if (st.phase === "updating") return { text: `Updating… ${plural(st.changed || 0, "file", "files")} changed`, link: "" };
  if (st.phase === "paused") return { text: PAUSED, link: "" };
  if (st.phase === "failed") return { text: FAILED, link: "again" };
  if (st.phase === "cleared") return { text: CLEARED, link: "again" };
  if (st.phase === "done") {
    if (!(st.total > 0)) return { text: NO_FILES, link: "" };
    const date = dmy(st.date);
    const out = st.left_out > 0;
    let text = `100% indexed${date ? `, ${date}` : ""}`;
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
