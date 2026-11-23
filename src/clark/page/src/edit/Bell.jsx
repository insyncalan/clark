// Row 1046, piece 2: the bell in the top bar, left of search. Editor only; not drawn at all while nothing is unread (and not while the popup is open,
// so it never vanishes under the person's hands). The popup is a non-modal dialog: it never opens by itself, focus goes in and comes back to the bell on Esc or Close.
import { useEffect, useRef, useState } from "preact/hooks";
import { WORDS, LABELS, badgeText, bellName, bellShown } from "../logic/notices.js";
import { shown, unread, readIds, announced, noticesOpen, readOne, readAll, startNotices, stopNotices, loadInstalled } from "./noticesState.js";
import { show } from "../stores/report.js";

const ICONS = {
  info: <><circle cx="10" cy="10" r="7" /><path d="M10 9v5M10 6.2v.1" /></>,
  warning: <><path d="M10 3l7.5 13h-15z" /><path d="M10 8v4M10 14.2v.1" /></>,
  critical: <><circle cx="10" cy="10" r="7" /><path d="M10 6v5M10 13.7v.1" /></>,
};
const niceDate = (iso) => iso.slice(8) + "-" + iso.slice(5, 7) + "-" + iso.slice(0, 4);      // DD-MM-YYYY

function go(to) {      // an action only names a place inside clark (logic/notices.js insidePlace): "/settings" opens that tab
  const view = to.replace(/^\//, "").split(/[/?#]/)[0];
  if (view) show(view);
}

export function Bell() {
  const btn = useRef(null), box = useRef(null), back = useRef(false), [kept, setKept] = useState(false);      // kept: the bell stays drawn until focus is back on it (after Mark all as read the count is 0 and a bell with nothing unread is not drawn: it stays until focus leaves it)
  const count = unread.value.length, open = noticesOpen.value;
  useEffect(() => { loadInstalled(); startNotices(); return stopNotices; }, []);
  const close = () => { back.current = true; setKept(true); noticesOpen.value = false; };      // focus goes back in the effect below, after the popup is gone: a focus call here can be undone by the pending focus-in effect (a quick Close under load)
  useEffect(() => {
    if (open && box.current) box.current.focus();
    else if (!open && back.current) { back.current = false; if (btn.current) btn.current.focus();  }
  }, [open]);
  useEffect(() => {
    if (!open) return undefined;
    const away = (e) => { if (box.current && !box.current.contains(e.target) && btn.current && !btn.current.contains(e.target)) noticesOpen.value = false; };
    document.addEventListener("mousedown", away);
    return () => document.removeEventListener("mousedown", away);
  }, [open]);
  const live = <span class="sr-only" role="status" aria-live="polite" id="bell-live">{announced.value}</span>;
  return (
    <span class="bell-wrap">
      {bellShown(count) || open || kept ? (
        <button type="button" class="tb-act tb-bell" id="bell-btn" ref={btn} onBlur={() => { if (!noticesOpen.value) setKept(false); }} aria-haspopup="dialog" aria-expanded={open ? "true" : "false"} aria-label={bellName(count)} title={bellName(count)} onClick={() => { noticesOpen.value = !open; }}>
          <svg class="tb-ico" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="M5 14V9a5 5 0 0 1 10 0v5l1.5 1.5h-13zM8.5 17.5h3" /></svg>
          {count > 0 ? <span class="bell-badge num" aria-hidden="true">{badgeText(count)}</span> : null}
        </button>
      ) : null}
      {live}
      {open ? (
        <div class="bell-pop" id="bell-pop" role="dialog" aria-label="Notifications" tabIndex={-1} ref={box} onKeyDown={(e) => { if (e.key === "Escape") { e.stopPropagation(); close(); } }}>
          <div class="bell-head">
            <b class="bell-title">Notifications</b>
            {count > 0 ? <button type="button" class="bell-link" id="bell-all" onClick={readAll}>{WORDS.markAll}</button> : null}
            <button type="button" class="bell-link" id="bell-close" onClick={close}>{WORDS.close}</button>
          </div>
          {shown.value.length === 0 ? <p class="bell-empty">{WORDS.caughtUp}</p> : (
            <ul class="bell-list">
              {shown.value.map((n) => {
                const isRead = readIds.value.includes(n.id);
                return (
                  <li key={n.id} class={"bell-item bell-" + n.severity + (isRead ? " bell-read" : "")} data-id={n.id}>
                    <p class="bell-sev"><svg class="bell-sev-ico" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true">{ICONS[n.severity]}</svg><span class="bell-sev-w">{LABELS[n.severity]}</span><span class="bell-date num">{niceDate(n.date)}</span></p>
                    <p class="bell-ttl">{n.title}</p>
                    {n.body ? <p class="bell-body">{n.body}</p> : null}
                    <p class="bell-acts">
                      {n.action ? <button type="button" class="bell-act" onClick={() => { go(n.action.to); close(); }}>{n.action.label}</button> : null}
                      {isRead ? null : <button type="button" class="bell-link bell-one" onClick={() => readOne(n.id)}>{WORDS.markRead}</button>}
                    </p>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      ) : null}
    </span>
  );
}
