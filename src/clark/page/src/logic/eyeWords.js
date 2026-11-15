// Row 1195: the words of the eye on a work item row, one place for the screen reader label, the tooltip and the announcement after a toggle.
// On the page: "Take <id> <title> off the page" (tooltip "Take off the page"); off the page: "Put <id> <title> on the page" (tooltip "Put on the page").
// An empty title leaves the id alone. The toast after a toggle (`said`) is the ruled 15-11 pair: "<id> is off the page." after taking it off, "<id> is on the page." after putting it on. Pure: no store, no page.
export function eyeWords(on, row) {
  const id = String((row && row.id) || "").trim(), title = String((row && row.title) || "").trim(), name = title ? `${id} ${title}` : id;
  return on
    ? { label: `Take ${name} off the page`, title: "Take off the page", said: `${id} is off the page.` }
    : { label: `Put ${name} on the page`, title: "Put on the page", said: `${id} is on the page.` };
}
