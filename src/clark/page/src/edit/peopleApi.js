// The People card's way to the server (item 454): GET /api/people (the list), POST /api/people {op: "paste", rows} (one step for a whole
// paste) and POST /api/people/undo {apply_id}. Edit's page only: no other file names these routes, so the published page has no way
// to read or change a person. {ok, ...} always, never a throw. A refusal by the server (a 400 in its own plain sentences, which end
// "Nothing was changed.") is shown as it is when it is short; any other failure gets the page's own words.
import { token, project } from "../stores/report.js";
import { CHANGE_ROUTE } from "../api.js";

const FAILED = "That could not be saved just now, and nothing was changed. Wait a moment and try again. If it keeps happening, restart clark.";
const NO_ANSWER = "Nothing was changed, because clark did not answer. Check that clark is still running, then try again.";
const READ_FAILED = "The people list could not be read. Reload the page. If it happens again, restart clark.";

async function call(method, path, body) {
  try {
    const headers = { "X-Clark-Token": token() };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    const r = await fetch(path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body), cache: "no-store" });
    return { status: r.status, body: await r.json().catch(() => null) };
  } catch (e) {
    return { status: 0, body: null };
  }
}

const said = (r) => {
  const m = r.body && typeof r.body.message === "string" ? r.body.message : "";
  return r.status === 400 && m && m.length <= 400 && !/[\u0000-\u001f]/.test(m) ? m : "";
};
const people = (r) => (r.status === 200 && r.body && r.body.ok === true && Array.isArray(r.body.people) ? r.body.people : null);

/** The people list: {ok: true, people} or {ok: false, message}. */
export async function readPeople() {
  const r = await call("GET", "/api/people");
  const list = people(r);
  return list ? { ok: true, people: list } : { ok: false, message: r.status === 0 ? NO_ANSWER : READ_FAILED };
}

/** One paste, one step: rows are [{name, email, organisation, role}]. {ok: true, people, added, updated, step} (step is null when
 *  nothing changed, so there is nothing to undo) or {ok: false, message}. */
export async function pastePeople(rows) {
  const r = await call("POST", "/api/people", { op: "paste", rows });
  const list = people(r);
  if (list) return { ok: true, people: list, added: +r.body.added || 0, updated: +r.body.updated || 0, step: Number.isInteger(r.body.apply_id) ? r.body.apply_id : null };
  return { ok: false, message: said(r) || (r.status === 0 ? NO_ANSWER : FAILED) };
}

/** Take one people step back. {ok: true, people} or {ok: false, message} (the server's sentence says what to do first). */
export async function undoPeople(step) {
  const r = await call("POST", "/api/people/undo", { apply_id: step });
  const list = people(r);
  if (list) return { ok: true, people: list };
  return { ok: false, message: said(r) || (r.status === 0 ? NO_ANSWER : "That could not be undone just now, and nothing was changed. Try again.") };
}

/** Row 986: one owner change that also adds a new person, in one step (`new_person` on the owner update). {ok: true, reply} (the reply has the
 *  item, apply_id, undoable and person {id, name}) or {ok: false, message, code, person}: `code` is person_exists, person_archived or
 *  not_a_name when the server says so, and `person` ({id, name}) is the one already on the list. */
export async function assignNewPerson(table, id, changes, newPerson, place) {
  const r = await call("POST", CHANGE_ROUTE, { project: project.value, kind: table, op: "update", id, changes, new_person: newPerson, place });
  const b = r.body;
  if (r.status === 200 && b && b.ok === true && b.item) return { ok: true, reply: b };
  const code = b && typeof b.code === "string" ? b.code : "";
  const p = b && b.person && typeof b.person.name === "string" && typeof b.person.id === "string" ? { id: b.person.id, name: b.person.name } : null;
  const m = b && typeof b.message === "string" ? b.message : "";
  const own = (r.status === 400 || r.status === 409) && m && m.length <= 400 && !/[\u0000-\u001f]/.test(m);
  return { ok: false, message: own ? m : r.status === 0 ? NO_ANSWER : FAILED, code, person: p };
}
