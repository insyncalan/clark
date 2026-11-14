// The Use Cases section as a library template (item 1191), store type "usecases": its view part. It draws the same summary the built-in
// section drew (components/UseCases.jsx: the strip, up to five rows, the line to the Use cases page), read only here. The section has no
// body: its data is the project's use cases. isEmpty: false in the served View (the summary says "No use cases yet." itself); true only in
// a published file with no use cases, which leaves the section out as it always has.
import { UseCases } from "../components/UseCases.jsx";
import { fromFile } from "../stores/report.js";

export const READY = true;

export const isEmpty = (section, data) => !!fromFile.value && !(data && data.use_cases && data.use_cases.length);

export function View() {
  return <UseCases tools={null} />;
}
