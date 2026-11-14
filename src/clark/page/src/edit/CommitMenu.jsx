// issue 709: the commitment chip in Edit: a small menu button like the status word. It lists the owner's three words (from data.commitments)
// and "No flag"; a choice is ONE change (kind use_cases, update, commitment) with one Undo and one History line. With no flag it reads
// "Set commitment" (row 791: the open menu is headed "Commitment"), a quiet empty chip that only exists in Edit. View and the published file draw components/CommitChip.jsx instead.
import { data } from "../stores/report.js";
import { change } from "../stores/changes.js";
import { Menu } from "../components/Menu.jsx";
import { actionIcon } from "../menuIcons.js";
import { commitWord, commitClass, commitWords } from "../logic/commitment.js";

export const NO_FLAG = "No flag";
export const SET_WORDS = "Set commitment";
const NONE = "__none";

export function CommitMenu({ u, left }) {
  const w = commitWord(u), words = commitWords(data.value), name = u.ref || u.id;
  const pick = (id) => {
    const next = id === NONE ? null : id;
    if ((next || "") === w) return;
    change({ kind: "use_cases", op: "update", id: u.id, changes: { commitment: next }, place: "cell" },
      next ? `Use case ${name}: commitment set to ${next}.` : `Use case ${name}: commitment cleared.`);
  };
  return (
    <span class="ucst uccm" data-uc-commit={u.id} data-edit-only>
      <Menu label={w || SET_WORDS} labelCls={`cchip ${w ? commitClass(w) : "cc-set"}`} btnCls="ucw-btn" left={left} chevron={false}
        ariaLabel={w ? `Commitment: ${w}. Change` : "Commitment: none. Set commitment"} menuLabel="Commitment" id={`uccm-${u.id}`}
        items={[{ id: "head", lab: "Commitment" }, ...words.map((n) => ({ id: n, name: n, icon: actionIcon("commit"), checked: w === n })), { id: NONE, name: NO_FLAG, icon: actionIcon("none"), checked: !w }]} onPick={pick} />
    </span>
  );
}
