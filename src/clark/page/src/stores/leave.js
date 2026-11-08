// What must happen before this page goes (#944): a different project is a page load, and Back or a closed tab ends the page. Kept apart
// from report.js, whose open path holds no timer (test_peek OpenTime); nothing here is on that path.
export const busy = [];                  // functions that give a promise for what is still being saved (changes.js: its queue)
export const beforeReload = [];          // functions run just before the page is loaded again (changes.js: keep the message, once)
export const leaving = { on: false };    // true while the page is going away: api.js then sends a save so that it outlives the page

export const trouble = { n: 0 };        // counts the problems said (changes.js say("problem")): a save that failed is one
export const stayed = [];                // functions run when the page stays because the save failed or ran past the wait (changes.js: say it, once)

// Wait (at most `limit` ms) for what the field just left has started, and for every save in the queue, including ones queued meanwhile.
// Resolves true when they all finished with no problem said since `since` (trouble.n then), false when one failed or the wait ran out:
// the page then stays (stay()) with the field as it is and the problem on show, and nothing is loaded.
export async function saved(limit = 8000, since = trouble.n) {
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  let timer;
  const late = new Promise((r) => { timer = setTimeout(() => r("late"), limit); });     // the timer itself says the time is up (a clock check could read a hair early)
  try {
    await wait(0);                                         // what the field's blur starts is started by now
    for (let i = 0; i < 20; i++) {
      const mine = busy.map((f) => f());
      const first = await Promise.race([Promise.all(mine).then(() => "done"), late]);
      if (first === "late") { stay(true); return false; }
      await wait(0);
      if (busy.map((f) => f()).every((p, k) => p === mine[k])) break;      // nothing new was queued meanwhile
    }
  } finally { clearTimeout(timer); }
  if (trouble.n !== since) { stay(false); return false; }
  return true;
}
function stay(late) { try { stayed.forEach((f) => f(late)); } catch (e) {} }
