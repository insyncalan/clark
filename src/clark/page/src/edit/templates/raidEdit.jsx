// The Edit part RAID cards (#96) share: one row per card (the work item; slice A: no words choice, an old saved one is kept in the body),
// saved in place. Every committed choice is one change() to the section's body: one step, one Undo, place "report". A card holds
// the item's id only, so what the item says is read when the page is drawn or published.
import { data } from "../../stores/report.js";
import { change } from "../../stores/changes.js";
import { putCard } from "../../logic/putCard.js";
import { publishable } from "../../logic/publishable.js";
import { MANY, acrossOf, bodyOf, kindOfId, kindWords, parse, rowOf, rulesOf, titleOf } from "../../templates/raid.js";

const GROUPS = [["raid", "Risks and issues"], ["actions", "Actions"], ["decisions", "Decisions"]];
const cut = (s, n) => { const c = Array.from(s); return c.length > n ? `${c.slice(0, n - 1).join("").trimEnd()}…` : s; };

function save(section, cards, words, named = null, across = 0) {
  return change({ op: "update", id: section.id, changes: { body: bodyOf(cards, across) }, place: "report" }, words, named);
}

// `choice` (row 1270, the one RAID cards card): three or four across and up to eight cards. An old body (version 1) keeps its shape until the
// author picks the number across or adds a fifth card; then it is saved as version 2 with four across (what it was drawn with).
export function RaidEdit({ section, size: base, choice = false }) {
  const d = data.value || {};
  const size = choice ? MANY : base;
  const across = choice ? acrossOf(section.body) || base : 0;
  const cards = parse(section.body).slice(0, size);
  const rules = rulesOf(d);
  const slots = Math.min(size, cards.length + 1);
  const bodyNow = () => { const now = ((data.value && data.value.report_sections) || []).find((s) => s.id === section.id); return now ? now.body : section.body; };      // the body as the page has it now, not as it was drawn
  const acrossFor = (list, body) => (!choice ? 0 : acrossOf(body) || (list.length > base ? base : 0));
  const put = (i, card, words, named = null) => {
    const body = bodyNow();
    const next = putCard(parse(body).slice(0, size), i, card);
    return save(section, next, words, named, acrossFor(next, body));
  };
  const setAcross = (e) => save(section, parse(bodyNow()).slice(0, size), "Card changed.", null, Number(e.currentTarget.value));
  const options = (current) => {
    const out = [];
    for (const [kind, label] of GROUPS) {
      const rows = (d[kind] || []).filter((r) => r && Number(r.archived) !== 1 && (r.id === current || !cards.some((c) => c.id === r.id)));
      if (!rows.length) continue;
      out.push(
        <optgroup label={label} key={kind}>
          {rows.map((r) => (
            <option key={r.id} value={r.id}>{`${r.id}: ${cut(titleOf(r, kind) || "No text", 70)}${publishable(r, kind, rules) ? "" : " (left out of the published page)"}`}</option>
          ))}
        </optgroup>,
      );
    }
    return out;
  };
  const rows = [];
  for (let i = 0; i < slots; i++) {
    const card = cards[i] || null;
    const found = card ? rowOf(d, card.id) : null;
    const choose = (e) => {
      const id = e.currentTarget.value;
      if (!id) return put(i, null, "Card removed.");
      const source = card && card.source === "latest" && kindOfId(id) !== "actions" ? "client" : card ? card.source : "client";
      return put(i, { id, source, own: card ? card.own : "" }, card ? "Card changed." : "Card added.");      // an old saved own or latest choice is kept in the body as it was, never drawn
    };
    const missing = card && !found;
    const note = missing ? "This item is not in the record any more. Choose another item or remove the card." : "";
    rows.push(
      <li class="rce-card" key={i} data-slot={i}>
        <label class="rce-f"><span>{`Card ${i + 1}`}</span>
          <select aria-label={`Card ${i + 1} item`} value={card ? card.id : ""} onChange={choose}>
            <option value="">{card ? "No item (remove this card)" : "Choose an item…"}</option>
            {missing ? <option value={card.id}>{`${card.id}: not in the record any more`}</option> : null}
            {options(card && card.id)}
          </select></label>
        {card ? (
          <>
            {found ? <p class="quiet rce-what">{`${kindWords(found.row, found.kind)}: ${cut(titleOf(found.row, found.kind), 100)}`}</p> : null}
            {note ? <p class="quiet rce-note">{note}</p> : null}
          </>
        ) : null}
      </li>,
    );
  }
  return (
    <div class="rce" data-edit-only="">
      {cards.length === 0 ? <p class="quiet rce-first">Choose an item for the first card. This section stays out of the published page until a card is chosen.</p> : null}
      {choice ? (
        <label class="rce-f rce-across"><span>RAID cards</span>
          <select aria-label="RAID cards" value={String(across)} onChange={setAcross}>
            <option value="3">RAID cards, three</option>
            <option value="4">RAID cards, four</option>
          </select></label>
      ) : null}
      <ul class="rce-list">{rows}</ul>
    </div>
  );
}
