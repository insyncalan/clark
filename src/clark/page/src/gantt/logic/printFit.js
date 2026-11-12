// Row 1038: the Gantt on paper is scaled down to the page width instead of being cut at the right edge. The chart keeps its drawn
// width on screen; on `beforeprint` GanttChart.jsx measures it and sets --gt-fit on the box, and shell.css zooms the canvas by it
// (html.print-all .gt-in). `afterprint` clears it. The page is A4 portrait (shell.css @page) with 12 mm side margins: 186 mm = 703 px.
export const PAGE_PX = 703;
export const FLOOR = 0.5;      // a very wide plan is not shrunk below half size; past that the empty tail is clipped, never the bars

// The ratio (FLOOR to 1) that makes `natural` pixels fit `page` pixels.
export function fitRatio(natural, page = PAGE_PX, floor = FLOOR) {
  if (!(natural > 0) || !(page > 0) || natural <= page) return 1;
  return Math.max(floor, Math.floor((page / natural) * 1000) / 1000);
}

// Set (or clear) --gt-fit on every chart box in the document.
export function fitCharts(root, on) {
  if (!root || !root.querySelectorAll) return;
  root.querySelectorAll(".gt-gx").forEach((gx) => {
    if (!on) { gx.style.removeProperty("--gt-fit"); return; }
    const l = gx.querySelector(".gt-lhead"), r = gx.querySelector(".gt-rhead");
    if (!l || !r) return;
    const k = fitRatio(l.offsetWidth + r.offsetWidth);
    if (k < 1) gx.style.setProperty("--gt-fit", String(k)); else gx.style.removeProperty("--gt-fit");
  });
}
