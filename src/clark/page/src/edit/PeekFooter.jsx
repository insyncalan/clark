// Row 1180: the peek's footer, the Edit part's (a published file and a Dashboard in View have no words box, so no footer): the key tag and the input that focuses on "/".
/** The footer: the key tag and the input that focuses on "/". Props: onAsk() is called when the input is used (the caller opens the words box). */
export function PeekFooter({ onAsk }) {
  let at = 0;      // when the input took focus: a second "/" soon after it opens the words box (the two-slash way in)
  return (
    <footer class="pk-foot" data-pk-foot>
      <kbd class="pk-foot-key" aria-hidden="true">//</kbd>
      <input type="text" class="pk-foot-in" data-pk-foot-in data-pk-ask placeholder="ask clark to update" aria-label="Ask clark to update for you" autocomplete="off"
        onFocus={() => { at = performance.now(); }}
        onKeyDown={(e) => {
          if (e.key === "/" && !e.currentTarget.value && performance.now() - at < 1000) { e.preventDefault(); if (onAsk) onAsk(); }
          else if (e.key === "Enter") { e.preventDefault(); if (onAsk) onAsk(); }
        }}
        onClick={() => { if (onAsk) onAsk(); }} />
    </footer>
  );
}
