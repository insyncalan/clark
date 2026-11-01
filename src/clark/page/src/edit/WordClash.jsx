// The question when a Word report's name is already taken (#48), in the Export to Word box and in the Publish box: nothing has been
// written yet. Add a number saves beside the old file; Replace it needs its own confirmation. Cancel is the box's own Cancel.
// The server's words say which file is taken and where; the choices are real radio buttons, so they work with the keyboard.
export function WordClash({ clash, choice, confirmed, onPick, onConfirm }) {
  return (
    <>
      <p class="word-ask" id="word-ask">{clash.message}</p>
      <fieldset class="pub-clash" aria-describedby="word-ask">
        <legend class="sr-only">What should clark do?</legend>
        <label class="pubopt"><input type="radio" name="word-clash" value="number" checked={choice === "number"} onChange={() => onPick("number")} />
          <span><b>Add a number</b><small>Keeps the old file and saves the new one beside it.</small></span></label>
        {clash.canReplace ? (
          <label class="pubopt"><input type="radio" name="word-clash" value="overwrite" checked={choice === "overwrite"} onChange={() => onPick("overwrite")} />
            <span><b>Replace it</b><small>The old file is overwritten.</small></span></label>
        ) : null}
        {choice === "overwrite" ? (
          <div class="pub-note">
            <label class="pubopt"><input type="checkbox" id="word-confirm" checked={confirmed} onChange={(e) => onConfirm(e.currentTarget.checked)} />
              <span>Yes, replace the file</span></label>
          </div>
        ) : null}
      </fieldset>
    </>
  );
}
