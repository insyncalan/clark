// The list a G4 Edit part (Checklist, Key dates) builds its next save from. A save is made from the latest list, not the last drawn
// one: a blur-save followed at once by a click on another line's Remove (before the first save lands) keeps both changes.
// `put(make, words)` makes the next list from the latest one, saves it and resolves to the reply (null when it failed: the latest list
// is then the drawn one again).
import { useEffect, useRef } from "preact/hooks";
import { change } from "../../stores/changes.js";

export function useList(section, items, place = "cell") {
  const key = JSON.stringify(items);
  const now = useRef(items), drawn = useRef(items), flying = useRef(0);
  drawn.current = items;
  useEffect(() => { if (!flying.current) now.current = drawn.current; }, [key]);
  return {
    latest: () => now.current,
    put: (make, body, words) => {
      const next = make(now.current);
      now.current = next;
      flying.current += 1;
      const sent = change({ op: "update", id: section.id, changes: { body: body(next) }, place }, words);
      return sent.then((r) => { flying.current -= 1; if (!r || !flying.current) now.current = drawn.current; return r; });
    },
  };
}
