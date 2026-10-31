// "Add a section" for a report with no sections at all (Edit only): there is no section to put the control beside. It asks the
// Add a section dialog (edit/addSection.js) to add one at the end.
import { askToAdd } from "./addSection.js";

export function Add() {
  return (
    <button type="button" class="sec-add" data-edit-only data-add onClick={(e) => askToAdd(null, e.currentTarget)}>
      <span aria-hidden="true">+</span> Add a section
    </button>
  );
}
