// The one setting row (row 1115, S1): the name and one help line at the left, the control at the right, a thin rule between two rows.
// It only lays a setting out; what the control does stays with the card. The name is the control's label (for = id), the help line is
// the control's description (aria-describedby = help id), and a refusal line (role alert) stands under the help line when the card has one.
// A row whose setting is not at its default (`changed`) shows a small dot after the name and a Reset button (`onReset`) at the left of the
// control; a row at its default shows neither. Reset is the card's own change, so it has the same toast and Undo as any change (row 1115, S4).
// Extra attributes (a data-... hook the page or a test reads) go on the row itself. Edit parts only.
/** After Reset the button is gone from the page, so the focus would drop to the page's top: it goes to the row's own control (row 1115, S4). */
export function focusControl(id) {
  const el = document.getElementById(id);
  if (el && el.focus) el.focus({ preventScroll: true });
}

export function SettingRow({ id, name, help, helpId, bad, changed, onReset, children, ...rest }) {
  return (
    <div class="set-row" {...rest}>
      <div class="set-row-text">
        <div class="set-row-name">
          <label for={id}>{name}</label>
          {changed ? <span class="set-dot" role="img" aria-label="Changed from the default" title="Changed from the default" /> : null}
        </div>
        {help ? <small id={helpId}>{help}</small> : null}
        {bad ? bad : null}
      </div>
      <div class="set-row-ctl">
        {changed && onReset ? <button type="button" class="set-reset" aria-label={`Reset ${name} to its default`} onClick={onReset}>Reset</button> : null}
        {children}
      </div>
    </div>
  );
}
