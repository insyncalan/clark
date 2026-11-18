// Printing the report (item 438). The published page shows one tab at a time, so for a print it draws every tab, one after another
// (`printing`, read by components/App.jsx), and goes back to the one tab afterwards. The browser says when: `beforeprint` (the
// print box, Ctrl+P or Cmd+P, from anywhere) and `afterprint`. Nothing is sent anywhere and nothing is added to the page: it prints
// what the tabs already draw. Only a published file asks for this; the editor never does.
import { signal } from "@preact/signals";
import { status, publication, asAt } from "./report.js";
import { lightForPrint } from "./reader.js";
import { wantsPrint, numberAsked, footLine, footRule } from "../logic/printView.js";

export const printing = signal(false);
let wired = false;

// The foot "Publication N · date" is a style the print adds and removes again (an @page margin box cannot be set from a script in
// any other way). The number on the address (&n=N) comes first: the Publish box prints the preview, which is built with the next
// number (N+1 once N is published), so the box puts the number it was just given there. Without it, the page's own number is used.
function foot(on) {
  try {
    if (document.documentElement.hasAttribute("data-pdf-foot")) return;      // the PDF clark makes carries its own foot (pdf.py): a second one would print the page's number beside it
    let el = document.getElementById("print-foot");
    const rule = on ? footRule(footLine(numberAsked(location.search) || publication.value, asAt.value)) : "";
    if (!rule) { if (el) el.remove(); return; }
    if (!el) { el = document.createElement("style"); el.id = "print-foot"; document.head.appendChild(el); }
    el.textContent = rule;
  } catch (e) { /* no document: no foot */ }
}

// The page's print rules (shell.css) work under html.print-all, so they are on at once and the screen is never touched.
function set(on) {
  printing.value = on;
  lightForPrint(on);                                      // a page in Dark prints light (issue 713)
  foot(on);
  try { document.documentElement.classList.toggle("print-all", on); } catch (e) { /* no document: nothing to mark */ }
}

export function watchPrint() {
  if (wired || typeof window === "undefined") return;
  wired = true;
  window.addEventListener("beforeprint", () => set(true));
  window.addEventListener("afterprint", () => set(false));
}

const frames = (n) => new Promise((done) => { const step = () => (n-- > 0 ? requestAnimationFrame(step) : done()); step(); });

// Open the print box now: draw the tabs, let them settle, then ask the browser. `afterprint` puts the page back.
export async function printReport() {
  set(true);
  await frames(3);
  window.print();
}

// A published file opened with ?print=1 prints itself once its data has drawn (one time).
export function printWhenAsked() {
  watchPrint();
  if (typeof location !== "object" || !wantsPrint(location.search)) return;
  let done = false;
  const stop = status.subscribe((v) => {
    if (v !== "ready" || done) return;
    done = true;
    setTimeout(() => { printReport(); }, 300);
    queueMicrotask(() => stop());
  });
}
