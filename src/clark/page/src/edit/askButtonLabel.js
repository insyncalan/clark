// The ask clark button's spoken label (row 1349), pure so a test can pin it. Open or idle: "ask clark"; an answer being made: "ask clark, working";
// answers that landed while the panel was closed: "ask clark, 1 answer ready", "ask clark, N answers ready" for N of 2 or more.
export function askButtonLabel(open, working, ready) {
  if (open || (!working && !ready)) return "ask clark";
  if (working) return "ask clark, working";
  return `ask clark, ${ready} ${ready >= 2 ? "answers" : "answer"} ready`;
}
