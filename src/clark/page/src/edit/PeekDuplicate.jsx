// The peek's Duplicate button (Edit only): the row menu's Duplicate for the item shown. One change, one Undo (the copy is taken back); the
// copy opens in the peek, as the row menu's does. The request and the words are the row menu's own (logic/rowMenu.js).
import { data, openPeek } from "../stores/report.js";
import { changeRecord } from "../stores/changes.js";
import { Icon } from "../components/Icon.jsx";
import { tableOf } from "./itemEdit.js";
import { actionIcon } from "../menuIcons.js";
import { duplicateRequest, duplicateWords, rawOf } from "../logic/rowMenu.js";

export function duplicateFromPeek(row) {
  const raw = rawOf(data.value, row);
  if (!raw) return undefined;
  return changeRecord({ ...duplicateRequest(raw, tableOf(row)), place: "peek" }, (reply) => duplicateWords(row, reply.ref))
    .then((r) => { if (r && r.ref) openPeek(r.ref, "item"); });
}

export function PeekDuplicate({ row }) {
  const run = () => duplicateFromPeek(row);
  return <button type="button" class="pkp-btn" data-pk-dup title="Duplicate" aria-label="Duplicate" onClick={run}><Icon name={actionIcon("duplicate")} /></button>;
}
