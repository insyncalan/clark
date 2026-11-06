// The peek's Client wording, edited in place as plain text (a work item's `client_message`): the report rows' own field (ItemRowsEdit.jsx
// Words), drawn in the peek's Details. Enter or a click away saves, Esc puts the old words back, an empty or too long text is put back
// in words; one change, one Undo.
import { Words } from "./ItemRowsEdit.jsx";

export function PeekWording({ row }) { return <Words row={row} text={row.client_message || ""} cls="pk-ce" />; }
