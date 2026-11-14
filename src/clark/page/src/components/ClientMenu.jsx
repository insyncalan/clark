// The published file's own menu (issue 713): a round badge at the top right of the bar and the menu it opens. Drawn only when the page
// is a published file (components/TopBar.jsx); the editor has its own profile menu and never draws this one. It follows
// components/Menu.jsx: aria-haspopup and aria-expanded on the badge, Down opens, Up, Down, Home and End move, Esc closes with the
// focus back on the badge. The rows, in order: Profile, Export to Excel (only when the file holds a workbook), Export to PDF
// (the browser's print), Past reports. Light and dark have their own small button beside the badge. The reader's name and look are kept in their own browser only (stores/reader.js).
import { useEffect, useLayoutEffect, useRef, useState } from "preact/hooks";
import { Icon } from "./Icon.jsx";
import { actionIcon } from "../menuIcons.js";
import { MenuPanel, useMenuState } from "./Menu.jsx";
import { data } from "../stores/report.js";
import { printReport } from "../stores/print.js";
import { readerName, setReaderName, removeReader, initialsOf, look, toggleLook } from "../stores/reader.js";
import { workbookOf, tooLarge, pastReportsOf, bytesOf } from "../logic/clientMenu.js";

const WORDS = {
  menu: "Report menu", profile: "Profile", excel: "Export to Excel", pdf: "Export to PDF", past: "Past reports",
  theme: "Switch between light and dark",
  boxTitle: "Your profile", field: "Your name", save: "Save", cancel: "Cancel", remove: "Remove my profile",
  kept: "Kept only in this browser. It is never put in the report or sent anywhere.",
  big: "This report is too large to include a spreadsheet.", sameFolder: "Opens the earlier report if it is in the same folder as this one.", none: "No earlier reports.",
};
const XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

// The workbook goes to the reader through a Blob and an object address: no data: address, no library.
function download(book) {
  const bytes = bytesOf(book.base64);
  if (!bytes) return;
  const url = URL.createObjectURL(new Blob([bytes], { type: XLSX }));
  const a = document.createElement("a");
  a.href = url; a.download = book.name; a.hidden = true;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])';

// "Your profile": a labelled modal box. The page behind is inert, Tab stays inside, Esc and Cancel close it, and the focus goes back to the badge.
function ProfileBox({ onClose }) {
  const root = useRef(null), field = useRef(null);
  const has = readerName.value !== "";
  const [text, setText] = useState(readerName.value);
  useEffect(() => {
    const held = [document.getElementById("main"), ...[...document.querySelectorAll(".top > :not(.cm-wrap)")]].filter(Boolean);
    held.forEach((el) => el.setAttribute("inert", ""));
    if (field.current) { field.current.focus(); field.current.select(); }
    return () => held.forEach((el) => el.removeAttribute("inert"));
  }, []);
  const keys = (e) => {
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); onClose(); return; }
    if (e.key !== "Tab" || !root.current) return;
    const all = [...root.current.querySelectorAll(FOCUSABLE)];
    const a = all[0], z = all[all.length - 1];
    if (!root.current.contains(document.activeElement)) { e.preventDefault(); (e.shiftKey ? z : a).focus(); }
    else if (e.shiftKey && document.activeElement === a) { e.preventDefault(); z.focus(); }
    else if (!e.shiftKey && document.activeElement === z) { e.preventDefault(); a.focus(); }
  };
  const save = (e) => { e.preventDefault(); setReaderName(text); onClose(); };
  return (
    <div class="cm-scrim" onKeyDown={keys} onPointerDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <form class="cm-box" id="client-profile" role="dialog" aria-modal="true" aria-labelledby="client-profile-t" ref={root} onSubmit={save}>
        <h2 id="client-profile-t">{WORDS.boxTitle}</h2>
        <label for="client-profile-name">{WORDS.field}</label>
        <input id="client-profile-name" class="cm-field" type="text" maxlength="80" autocomplete="off" ref={field} value={text} onInput={(e) => setText(e.currentTarget.value)} />
        <p class="cm-note">{WORDS.kept}</p>
        <div class="cm-foot">
          {has ? <button type="button" class="btn" data-act="remove" onClick={() => { removeReader(); onClose(); }}>{WORDS.remove}</button> : null}
          <button type="button" class="btn" data-act="cancel" onClick={onClose}>{WORDS.cancel}</button>
          <button type="submit" class="btn cm-save" data-act="save">{WORDS.save}</button>
        </div>
      </form>
    </div>
  );
}

export function ClientMenu() {
  const [open, setOpen] = useMenuState();
  const [box, setBox] = useState(false);
  const btn = useRef(null), back = useRef(false);
  const d = data.value, book = workbookOf(d), big = !book && tooLarge(d), past = pastReportsOf(d);
  const name = readerName.value, ini = initialsOf(name);
  const close = (how) => { back.current = how === "esc" || how === "pick"; setOpen(false); };
  // Focus goes back to the badge only if nothing took it: the box has put focus in itself, and the menu must not steal it.
  useEffect(() => { if (!open && back.current) { back.current = false; const at = document.activeElement; if (btn.current && (!at || at === document.body || at === btn.current)) btn.current.focus(); } }, [open]);
  const wasBox = useRef(false);
  useLayoutEffect(() => { if (wasBox.current && !box && btn.current) btn.current.focus(); wasBox.current = box; }, [box]);
  const run = (fn) => () => { close("pick"); fn(); };
  const item = (row, label, fn, extra) => <button type="button" class="cm-row" role="menuitem" tabIndex={-1} data-row={row} onClick={run(fn)} {...extra}>{actionIcon(row) ? <Icon name={actionIcon(row)} cls="mi" /> : null}{label}</button>;
  return (
    <span class="cm-wrap">
      <button type="button" class="cm-theme" id="client-theme-btn" aria-label={WORDS.theme} title={WORDS.theme} data-tip={WORDS.theme} onClick={toggleLook}>
        <Icon name={look.value === "dark" ? "sun" : "moon"} />
      </button>
      <button type="button" class="cm-badge" id="client-menu-btn" ref={btn} aria-label={WORDS.menu} title={WORDS.menu} data-tip={WORDS.menu}
        aria-haspopup="menu" aria-expanded={open ? "true" : "false"} aria-controls={open ? "client-menu" : undefined}
        onKeyDown={(e) => { if (e.key === "ArrowDown" && !open) { e.preventDefault(); setOpen(true); } }}
        onClick={(e) => { e.preventDefault(); setOpen(!open); }}>
        {ini ? <span class="cm-ini" aria-hidden="true">{ini}</span> : <Icon name="user" />}
      </button>
      {open ? (
        <MenuPanel label={WORDS.menu} id="client-menu" cls="cm-menu" anchor={btn.current} onClose={close}>
          {item("profile", WORDS.profile, () => setBox(true))}
          {book ? item("excel", WORDS.excel, () => download(book)) : null}
          {big ? <button type="button" class="cm-row" role="menuitem" aria-disabled="true" data-keep="1" tabIndex={-1} data-row="excel" aria-describedby="client-menu-big"><Icon name={actionIcon("excel")} cls="mi" />{WORDS.excel}</button> : null}
          {big ? <div class="cm-note" id="client-menu-big" role="presentation">{WORDS.big}</div> : null}
          {item("pdf", WORDS.pdf, () => { printReport(); })}
          <div class="cm-group" role="group" aria-labelledby="client-menu-past" data-row="past">
            <div class="lab" role="presentation" id="client-menu-past">{WORDS.past}</div>
            {past.map((r) => <a class="cm-row cm-link" role="menuitem" tabIndex={-1} href={r.href} title={`Report of ${r.date}`} key={r.iso + r.href}><Icon name={actionIcon("pastReport")} cls="mi" />{r.date}</a>)}
            <div class="cm-note" role="presentation">{past.length ? WORDS.sameFolder : WORDS.none}</div>
          </div>
        </MenuPanel>
      ) : null}
      {box ? <ProfileBox onClose={() => setBox(false)} /> : null}
    </span>
  );
}
