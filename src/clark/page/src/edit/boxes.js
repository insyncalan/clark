// The boxes opened from Settings (#444): the project form, Import workbook and the Reset confirm. One signal says which is open and with
// what; Boxes.jsx draws it at the page's top level, outside <main>, so the page behind can be made inert while it is open.
// Edit parts only: a published file has no Settings.
import { signal } from "@preact/signals";

export const box = signal(null);                        // null, or { kind: "project" | "import" | "reset", props }
export const openBox = (kind, props) => { box.value = { kind, props: props || {} }; };
export const closeBox = () => { box.value = null; };
