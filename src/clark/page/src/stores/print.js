// Printing the report (#438). The published page shows one tab at a time, so for a print it draws every tab, one after another
// (`printing`, read by components/App.jsx), and goes back to the one tab afterwards. The browser says when: `beforeprint` (the
// print box, Ctrl+P or Cmd+P, from anywhere) and `afterprint`. Nothing is sent anywhere and nothing is added to the page: it prints
// what the tabs already draw. Only a published file asks for this; the editor never does.
import { signal } from "@preact/signals";
import { status } from "./report.js";
import { wantsPrint } from "../logic/printView.js";

export const printing = signal(false);
let wired = false;

// The page's print rules (shell.css) work under html.print-all, so they are on at once and the screen is never touched.
function set(on) {
  printing.value = on;
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
  if (typeof location === "undefined" || !wantsPrint(location.search)) return;
  let done = false;
  const stop = status.subscribe((v) => {
    if (v !== "ready" || done) return;
    done = true;
    setTimeout(() => { printReport(); }, 300);
    queueMicrotask(() => stop());
  });
}
