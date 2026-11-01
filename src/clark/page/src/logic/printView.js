// Printing the report (#438): the published page prints itself, so a PDF needs no extra software. Pure parts only; the state is in
// stores/print.js and the look in shell.css (@media print).
export const PRINT_ORDER = ["dashboard", "work", "milestones", "usecases"];      // the page's own tab order: Use Cases last; Settings is never printed

// The tabs this file has, in print order.
export const printTabs = (tabs) => PRINT_ORDER.filter((v) => (tabs || []).includes(v));

// The line at the head of the first printed page: the day it was published, day first (DD-MM-YYYY). Nothing for a date that is not one.
export const publishedLine = (iso) => (/^\d{4}-\d\d-\d\d$/.test(iso || "") ? `Published ${iso.slice(8)}-${iso.slice(5, 7)}-${iso.slice(0, 4)}` : "");

// ?print=1 on the address asks the page to open the print box once it has drawn (the Publish box opens the page that way).
export const wantsPrint = (search) => new URLSearchParams(search || "").get("print") === "1";
export const printUrl = (url) => `${url}${String(url).includes("?") ? "&" : "?"}print=1`;
