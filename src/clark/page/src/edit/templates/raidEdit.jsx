// The Edit part RAID cards (#96) share: one row per card (the work item, where its words come from, and the card's own words),
// saved in place. Every committed choice is one change() to the section's body: one step, one Undo, place "report". A card holds
// the item's id only, so what the item says is read when the page is drawn or published. Plain text only; nothing is drawn as markup.
import { data } from "../../stores/report.js";
import { change } from "../../stores/changes.js";
import { publishable } from "../../logic/publishable.js";
import { OWN_MAX, SOURCES, bodyOf, kindOfId, kindWords, parse, rowOf, rulesOf, titleOf, wordsOf } from "../../templates/raid.js";

const GROUPS = [["raid", "Risks and issues"], ["actions", "Actions"], ["decisions", "Decisions"]];
const cut = (s, n) => { const c = Array.from(s); return c.length > n ? `${c.slice(0, n - 1).join("").trimEnd()}…` : s; };

function save(section, cards, words) {
  return change({ op: "update", id: section.id, changes: { body: bodyOf(cards) }, place: "report" }, words);
}

export function RaidEdit({ section, size }) {
  const d = data.value || {};
  const cards = parse(section.body).slice(0, size);
  const rules = rulesOf(d);
  const slots = Math.min(size, cards.length + 1);
  const put = (i, card, words) => {
    const now = ((data.value && data.value.report_sections) || []).find((s) => s.id === section.id);      // the body as the page has it now, not as it was drawn
    const next = parse(now ? now.body : section.body).slice(0, size);
    if (card) next[i] = card; else next.splice(i, 1);
    return save(section, next, words);
  };
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
    const isAction = card ? kindOfId(card.id) === "actions" : false;
    const choose = (e) => {
      const id = e.currentTarget.value;
      if (!id) return put(i, null, "Card removed.");
      const source = card && card.source === "latest" && kindOfId(id) !== "actions" ? "client" : card ? card.source : "client";
      return put(i, { id, source, own: card ? card.own : "" }, card ? "Card changed." : "Card added.");
    };
    const pick = (e) => put(i, { ...card, source: e.currentTarget.value }, "Card text changed.");
    const commit = (e) => {
      const el = e.currentTarget, text = el.value.replace(/\s+/g, " ").trim();
      if (text === card.own) { el.value = card.own; return; }
      put(i, { ...card, own: text }, "Card text changed.");
    };
    const keys = (e) => {
      if (e.isComposing) return;
      if (e.key === "Enter") { e.preventDefault(); e.currentTarget.blur(); }
      else if (e.key === "Escape") { e.preventDefault(); e.currentTarget.value = card.own; e.currentTarget.blur(); }
    };
    const missing = card && !found;
    const note = !card ? "" : missing ? "This item is not in the record any more. Choose another item or remove the card."
      : card.source === "client" && !wordsOf(card, found.row) ? "This item has no client wording yet, so the card shows the item only. Add it on the item, or choose Own words."
      : card.source === "latest" && !wordsOf(card, found.row) ? "This action has no latest update yet, so the card shows the item only."
      : "";
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
            <label class="rce-f"><span>Text under the card</span>
              <select aria-label={`Card ${i + 1} text`} value={card.source} onChange={pick}>
                {SOURCES.filter(([v]) => v !== "latest" || isAction).map(([v, w]) => <option key={v} value={v}>{w}</option>)}
              </select></label>
            {card.source === "own" ? (
              <label class="rce-f"><span>Own words</span>
                <input type="text" key={`${card.id}|${card.own}`} defaultValue={card.own} maxLength={OWN_MAX} aria-label={`Card ${i + 1} own words`} onBlur={commit} onKeyDown={keys} spellcheck /></label>
            ) : null}
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
      <ul class="rce-list">{rows}</ul>
    </div>
  );
}
