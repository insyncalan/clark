// Row 1543 (the search folded in from #1545): the published report's search. The button is the editor's (same word "Go to or do", same
// 38 by 28 box, tooltip naming Ctrl or Cmd + K); it opens a small box that finds what THIS file holds, in the client's wording: work items
// (ID, title, owner, client message), milestones, use cases and the report's section text. The file holds nothing team-only, so nothing
// team-only can be found. A published file has no server: everything is read from the data already in the page, nothing is fetched.
import { useEffect, useLayoutEffect, useRef, useState } from "preact/hooks";
import { signal } from "@preact/signals-core";
import { data, rows, found, view, show, openPeek, openUseCase } from "../stores/report.js";
import { entries } from "../logic/minimap.js";
import { richWords } from "../logic/richWords.js";

const MAC = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform || "");
const open = signal(false);
let opener = null;

const plain = (html) => {      // the words of a piece of stored rich text; DOMParser builds no live element and runs nothing
  if (typeof html !== "string" || html === "") return "";
  if (!/[<&]/.test(html)) return html;
  try { return new DOMParser().parseFromString(html, "text/html").body.textContent || ""; } catch (e) { return html.replace(/<[^>]*>/g, " "); }
};
const SKIP = new Set(["id", "type", "beside", "url", "href", "kind", "hidden"]);
function wordsOf(v, depth = 0) {      // every string a section carries (headline, highlights, body ...), not its ids or links
  if (depth > 6 || v == null) return [];
  if (typeof v === "string") return [plain(v)];
  if (Array.isArray(v)) return v.flatMap((x) => wordsOf(x, depth + 1));
  if (typeof v === "object") return Object.entries(v).filter(([k]) => !SKIP.has(k)).flatMap(([, x]) => wordsOf(x, depth + 1));
  return [];
}
const fold = (...parts) => parts.filter((p) => typeof p === "string" && p !== "").join(" ").toLowerCase().replace(/\s+/g, " ");

/** The results for what was typed: [{id, kind, label, more, go}], at most 40. Pure of the DOM but for plain(). */
export function results(d, q, rowList, index) {
  const words = String(q || "").toLowerCase().split(/\s+/).filter(Boolean);
  if (!d || !words.length) return [];
  const hit = (hay) => words.every((w) => hay.includes(w));
  const out = [];
  for (const r of rowList || []) if (hit(index[r.id] || "")) out.push({ id: "i-" + r.id, kind: "Work item", label: r.title || r.id, more: r.id, go: () => openPeek(r.id, "item") });
  for (const m of d.milestones || []) {
    if (hit(fold(m.name, m.owner, m.client_message, richWords(m.latest_update)))) out.push({ id: "m-" + m.id, kind: "Milestone", label: m.name, more: "", go: () => openPeek(m.id, "milestone") });
  }
  const shown = new Set((d.use_case_pages || []).map((p) => p.id));
  for (const u of d.use_cases || []) {
    if (shown.size && !shown.has(u.id)) continue;
    if (hit(fold(u.ref, u.title, u.headline, u.owner, plain(u.standing)))) out.push({ id: "u-" + u.id, kind: "Use case", label: u.title || u.ref, more: u.ref || "", go: () => openUseCase(u.id) });
  }
  const list = entries(d.report_sections || [], []);
  for (const s of d.report_sections || []) {
    const text = fold(s.title, ...wordsOf(s));
    if (!hit(text)) continue;
    const e = list.find((x) => x.id === s.id);
    out.push({ id: "s-" + s.id, kind: "Report", label: s.title || (e && e.title) || "Section", more: "", go: () => {
      if (view.value !== "dashboard") show("dashboard");
      const jump = (n) => { const el = e && document.getElementById(e.anchor); if (el) el.scrollIntoView({ block: "start" }); else if (n < 20) setTimeout(() => jump(n + 1), 50); };
      jump(0);
    } });
  }
  return out.slice(0, 40);
}

export function closeSearch(back) {
  open.value = false;
  const el = opener; opener = null;
  if (back && el && el.isConnected && el.focus) el.focus();
}
export function openSearch() {
  if (open.value) return;
  const a = document.activeElement;
  opener = a && a !== document.body ? a : document.getElementById("pal-btn");
  open.value = true;
}

function onKey(e) {
  if ((e.key || "").toLowerCase() === "k" && (e.metaKey || e.ctrlKey) && !e.altKey && !e.shiftKey && !e.isComposing) {
    if (!open.value && document.querySelector("dialog[open], [role=dialog], [role=alertdialog], [role=menu]")) return;      // another box or menu has the page: leave it be
    e.preventDefault(); e.stopImmediatePropagation();
    if (e.repeat) return;
    if (open.value) closeSearch(true); else openSearch();
  }
}

export function PubSearch() {
  useLayoutEffect(() => { window.addEventListener("keydown", onKey, true); return () => window.removeEventListener("keydown", onKey, true); }, []);
  return (
    <>
      <button type="button" class="tb-act" id="pal-btn" aria-haspopup="dialog" aria-expanded={open.value ? "true" : "false"} aria-label="Go to or do" title={`Go to or do (${MAC ? "Cmd" : "Ctrl"} + K)`} onClick={() => openSearch()}>
        <svg class="tb-ico" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><circle cx="9" cy="9" r="5.5" /><path d="M13 13l4 4" /></svg>
      </button>
      {open.value ? <Box /> : null}
    </>
  );
}

function Box() {
  const el = useRef(null), input = useRef(null), list = useRef(null);
  const [q, setQ] = useState("");
  const [at, setAt] = useState(0);
  const found_ = results(data.value, q, rows.value, found.value);
  const on = Math.min(at, Math.max(found_.length - 1, 0));
  useEffect(() => {
    const d = el.current;
    if (d && !d.open && d.showModal) d.showModal();
    if (input.current) input.current.focus();
    return () => { if (d && d.open) d.close(); };
  }, []);
  useEffect(() => {
    const row = list.current && list.current.querySelector("[aria-selected=true]");
    if (row && row.scrollIntoView) row.scrollIntoView({ block: "nearest" });
  }, [on, q]);
  const choose = (r) => { if (!r) return; closeSearch(false); r.go(); };
  const n = found_.length;
  const keys = (e) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); if (n) setAt((on + (e.key === "ArrowDown" ? 1 : n - 1)) % n); }
    else if (e.key === "Home" || e.key === "End") { e.preventDefault(); setAt(e.key === "Home" ? 0 : Math.max(n - 1, 0)); }
    else if (e.key === "Enter" && !e.isComposing) { e.preventDefault(); choose(found_[on]); }
  };
  const live = !q.trim() ? "" : n ? `${n} ${n === 1 ? "result" : "results"}` : "Nothing matches.";
  return (
    <dialog id="pub-search" class="dlg pal" aria-label="Go to or do" ref={el} onCancel={(e) => { e.preventDefault(); closeSearch(true); }} onClick={(e) => { if (e.target === e.currentTarget) closeSearch(true); }}>
      <div class="pal-q">
        <input type="text" id="pub-search-q" role="combobox" aria-expanded="true" aria-controls="pub-search-list" aria-autocomplete="list" aria-activedescendant={n ? "ps-" + found_[on].id : undefined}
          placeholder="Search this report" aria-label="Search this report" autocomplete="off" spellcheck={false} ref={input} value={q}
          onInput={(e) => { setQ(e.currentTarget.value); setAt(0); }} onKeyDown={keys} />
      </div>
      <ul id="pub-search-list" class="pal-list" role="listbox" aria-label="Results" ref={list}>
        {found_.map((r, i) => (
          <li key={r.id} id={"ps-" + r.id} role="option" class={`pal-row${i === on ? " on" : ""}`} data-kind={r.kind} aria-selected={i === on ? "true" : "false"}
            onMouseMove={() => { if (i !== on) setAt(i); }} onMouseDown={(e) => e.preventDefault()} onClick={() => choose(r)}>
            <span class="pal-kind">{r.kind}</span>
            <span class="pal-label">{r.label}</span>
            {r.more ? <span class="pal-more muted num">{r.more}</span> : null}
          </li>
        ))}
      </ul>
      <p class="pal-none muted" hidden={!q.trim() || n > 0}>Nothing matches “{q}”.</p>
      <p class="sr-only" role="status" aria-live="polite">{live}</p>
    </dialog>
  );
}
