// The Edit part RAID cards (item 96) share: one row per card (the work item; slice A: no words choice, an old saved one is kept in the body),
// saved in place. Every committed choice is one change() to the section's body: one step, one Undo, place "report". A card holds
// the item's id only, so what the item says is read when the page is drawn or published. The "Also show on the card" boxes are drawn for the
// one RAID cards card only (`choice`): an old three or four across section saves a version 1 body, which has no show (raid3 _check refuses it).
import { useState } from "preact/hooks";
import { StartPrompt } from "../StartPrompt.jsx";
import { data } from "../../stores/report.js";
import { change } from "../../stores/changes.js";
import { putCard } from "../../logic/putCard.js";
import { publishable } from "../../logic/publishable.js";
import { MANY, acrossOf, bodyOf, kindOfId, kindWords, latestOf, parse, ratingOf, rowOf, rulesOf, shows, titleOf } from "../../templates/raid.js";

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
  const [picking, setPicking] = useState(false);
  const [query, setQuery] = useState("");
  // Row 1270: the "Also show on the card" choices are saved as the card's show; an old body (version 1) becomes version 2 with the number it was drawn with
  const setShow = (i, key, on) => {
    const body = bodyNow();
    const list = parse(body).slice(0, size);
    list[i] = { ...list[i], show: { ...list[i].show, [key]: on } };
    return save(section, list, "Card changed.", null, choice ? acrossOf(body) || base : 0);
  };
  const remove = (i) => put(i, null, "Card removed.");
  const pickable = () => {
    const q = query.trim().toLowerCase();
    const out = [];
    for (const [kind] of GROUPS) {
      for (const r of d[kind] || []) {
        if (!r || Number(r.archived) === 1 || cards.some((c) => c.id === r.id) || !publishable(r, kind, rules)) continue;
        const text = titleOf(r, kind);
        if (!q || r.id.toLowerCase().includes(q) || text.toLowerCase().includes(q)) out.push({ id: r.id, kind, row: r, text });
      }
    }
    return out;
  };
  const pick = (id) => { put(cards.length, { id, source: "client", own: "" }, "Card added."); setPicking(false); setQuery(""); };
  const options = (current) => {
    const out = [];
    for (const [kind, label] of GROUPS) {
      const rows = (d[kind] || []).filter((r) => r && Number(r.archived) !== 1 && (r.id === current || !cards.some((c) => c.id === r.id)));
      if (!rows.length) continue;
      out.push(
        <optgroup label={label} key={kind}>
          {rows.map((r) => (
            <option key={r.id} value={r.id} disabled={r.id !== current && !publishable(r, kind, rules)}>{`${r.id}: ${cut(titleOf(r, kind) || "No text", 70)}${publishable(r, kind, rules) ? "" : " (left out of the published page)"}`}</option>
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
      // row 1270 (PM ruling 26-11): an item the published page would leave out (hidden, archived) is refused like the picker and the options do; the item the card already holds stays stored
      const row = rowOf(d, id);
      if (!(card && card.id === id) && !(row && publishable(row.row, row.kind, rules))) { e.currentTarget.value = card ? card.id : ""; return null; }
      const source = card && card.source === "latest" && kindOfId(id) !== "actions" ? "client" : card ? card.source : "client";
      return put(i, { id, source, own: card ? card.own : "", show: card ? card.show : {} }, card ? "Card changed." : "Card added.");      // an old saved own or latest choice is kept in the body as it was, never drawn
    };
    const missing = card && !found;
    const note = missing ? "This item is not in the record any more. Choose another item or remove the card." : "";
    rows.push(
      <li class="rce-card" key={i} data-slot={i}>
        <label class="rce-f"><span>{`Card ${i + 1}`}</span>
          <select aria-label={`Card ${i + 1} item`} value={card ? card.id : ""} onChange={choose}>
            <option value="">{card ? `Remove card ${i + 1}` : "Choose an item…"}</option>
            {missing ? <option value={card.id}>{`${card.id}: not in the record any more`}</option> : null}
            {options(card && card.id)}
          </select></label>
        {card ? (
          <>
            <button type="button" class="rce-rm" aria-label={`Remove card ${i + 1}`} onClick={() => remove(i)}>×</button>
            {found && choice ? <fieldset class="rce-show"><legend>Also show on the card</legend>
              {(() => {
                const has = !!latestOf(found.row);
                const box = (key, label, on, off, hint) => (
                  <label class="rce-ck"><input type="checkbox" checked={on && !off} disabled={off} onChange={(e) => setShow(i, key, e.currentTarget.checked)} /><span>{label}{hint ? <small>{hint}</small> : null}</span></label>
                );
                return <>
                  {box("latest", "Latest update", shows(card.show, "latest"), !has, has ? "" : "This item has no latest update yet.")}
                  {box("meta", "Owner, status and date", shows(card.show, "meta"), false, "")}
                  {found.kind === "raid" ? box("rating", "Impact and likelihood", shows(card.show, "rating"), false, "") : null}
                </>;
              })()}
            </fieldset> : null}
            {found ? <p class="quiet rce-what">{`${kindWords(found.row, found.kind)}: ${cut(titleOf(found.row, found.kind), 100)}`}</p> : null}
            {note ? <p class="quiet rce-note">{note}</p> : null}
          </>
        ) : null}
      </li>,
    );
  }
  return (
    <div class="rce" data-edit-only="">
      {cards.length === 0 ? <StartPrompt id={`raid-${base}`} /> : null}
      {cards.length === 0 ? <p class="quiet rce-first">Choose an item for the first card. This section stays out of the published page until a card is chosen.</p> : null}
      {choice ? (
        <label class="rce-f rce-across"><span>Cards across</span>
          <select aria-label="Cards across" value={String(across)} onChange={setAcross}>
            <option value="3">3</option>
            <option value="4">4</option>
          </select></label>
      ) : null}
      <div class="rce-bar">
        <button type="button" class="rce-pick" aria-expanded={picking} disabled={cards.length >= size} onClick={() => setPicking(!picking)}>Pick an item</button>
        <span class="rce-count">{`${cards.length} of ${size} picked`}</span>
      </div>
      {picking ? (
        <div class="rce-picker">
          <input type="search" aria-label="Pick an item" value={query} onInput={(e) => setQuery(e.currentTarget.value)} />
          <ul class="rce-opts" role="listbox" aria-label="Pick an item">
            {pickable().map((o) => (
              <li key={o.id} role="option" aria-selected="false"><button type="button" data-pick={o.id} onClick={() => pick(o.id)}><b>{o.id}</b> <span class="rce-kind">{kindWords(o.row, o.kind)}</span> {ratingOf(o.row, o.kind).word ? <><span class="rce-rate">{ratingOf(o.row, o.kind).word}</span> </> : null}{o.text}</button></li>
            ))}
          </ul>
          {pickable().length === 0 ? <p class="quiet rce-none">No item matches</p> : null}
        </div>
      ) : null}
      <ul class="rce-list">{rows}</ul>
    </div>
  );
}
