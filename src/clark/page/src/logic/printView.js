// Printing the report (item 438): the published page prints itself, so a PDF needs no extra software. Pure parts only; the state is in
// stores/print.js and the look in shell.css (@media print).
export const PRINT_ORDER = ["dashboard", "work", "milestones", "usecases", "gantt"];      // the page's tab order with Use cases last (the prototype's PDF); Settings is never printed

// The tabs this file has, in print order.
export const printTabs = (tabs) => PRINT_ORDER.filter((v) => (tabs || []).includes(v));

// The day, day first (DD-MM-YYYY). Nothing for a date that is not one.
export const dayFirst = (iso) => (/^\d{4}-\d\d-\d\d$/.test(iso || "") ? `${iso.slice(8)}-${iso.slice(5, 7)}-${iso.slice(0, 4)}` : "");

// The line at the head of the first printed page: the day it was published.
export const publishedLine = (iso) => (dayFirst(iso) ? `Published ${dayFirst(iso)}` : "");

// The foot of every printed page (row 31): "Publication N · DD-MM-YYYY". It is digits and a date only, and nothing without a number.
// With a number but no date it is "Publication N" alone.
export const footLine = (n, iso) => (Number.isInteger(n) && n >= 1 ? `Publication ${n}${dayFirst(iso) ? ` · ${dayFirst(iso)}` : ""}` : "");

// The @page rule that puts that line at the bottom left. The line is digits, a dot and a date; quotes, backslashes and line breaks are dropped anyway.
export const footRule = (line) => (line ? `@page { @bottom-left { content: "${String(line).replace(/[\\"\n\r]/g, "")}"; font: 13px Arial, sans-serif; } }` : "");

// ?print=1 on the address asks the page to open the print box once it has drawn (the Publish box opens the page that way).
export const wantsPrint = (search) => new URLSearchParams(search || "").get("print") === "1";
// &n=N on that address gives the publication number to a page that does not carry one (a preview): whole numbers 1 to 999999 only.
export const numberAsked = (search) => { const v = new URLSearchParams(search || "").get("n"); return v && /^[1-9]\d{0,5}$/.test(v) ? Number(v) : 0; };
export const printUrl = (url, n) => `${url}${String(url).includes("?") ? "&" : "?"}print=1${Number.isInteger(n) && n >= 1 ? `&n=${n}` : ""}`;
