// "Add a text section below" (Edit only): one text section just below this one. `after` is this section's id; null adds at the end.
import { add } from "./actions.js";

export function Add({ after }) {
  return (
    <button type="button" class="sec-add" data-edit-only data-add onClick={() => add(after, "report")}>
      <span aria-hidden="true">+</span> Add a text section below
    </button>
  );
}
