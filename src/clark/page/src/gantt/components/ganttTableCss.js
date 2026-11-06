// The table's styles (#926), in one string the table draws as a <style> of its own: it uses the brand tokens only, so light and dark both
// follow the page. Kept beside the component so the table needs nothing added to the shell's style sheet.
export const TABLE_CSS = `
.gt { --gz: 1; display: block; color: var(--text); font-size: var(--size-small, 13px); }
.gt-bar { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin: 0 0 6px; color: var(--text-muted); font-size: 12px; min-height: 28px; }
.gt-bar button { border: 1px solid var(--border); background: var(--surface); color: var(--text); border-radius: var(--radius); height: 26px; min-width: 28px; padding: 0 8px; font: inherit; cursor: pointer; }
.gt-bar button:hover { border-color: var(--brand-blue); }
.gt-bar button:focus-visible, .gt-menu button:focus-visible, .gt-eye:focus-visible, .gt-rb:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; }
.gt-msg { flex: 1 1 240px; min-width: 0; }
.gt-msg.gt-bad { color: var(--status-red-text); font-weight: 600; }
.gt-msg button { margin-left: 8px; }
.gt-pos { margin-left: auto; }
.gt-scroll { position: relative; overflow: auto; max-height: var(--gt-max, 60vh); border: 1px solid var(--border); border-radius: var(--radius); outline: 0; background: var(--surface); user-select: none; }
.gt-scroll:focus-visible { outline: 2px solid var(--focus); outline-offset: 1px; }
.gt table { border-collapse: separate; border-spacing: 0; table-layout: fixed; font-size: calc(12.5px * var(--gz)); }
.gt th, .gt td { height: calc(26px * var(--gz)); padding: 0 calc(7px * var(--gz)); border-bottom: 1px solid var(--border); border-right: 1px solid var(--border); background: var(--surface); text-align: left; white-space: nowrap; overflow: clip; text-overflow: ellipsis; box-sizing: border-box; }
.gt thead th { position: sticky; top: 0; z-index: 5; background: var(--grey-100); color: var(--text-muted); font-weight: 600; cursor: pointer; padding-right: calc(24px * var(--gz)); }
.gt thead th.hs, .gt .gt-rh.hs { background: color-mix(in srgb, var(--brand-blue) 22%, var(--grey-100)); color: var(--text); }
.gt thead th.gt-hid { background-image: repeating-linear-gradient(135deg, transparent 0 6px, color-mix(in srgb, var(--text-muted) 22%, transparent) 6px 7px); }
.gt th.gt-fz, .gt td.gt-fz { position: sticky; z-index: 3; }
.gt thead th.gt-fz { z-index: 7; }
.gt .gt-rh, .gt .gt-rh0 { position: sticky; left: 0; z-index: 6; background: var(--grey-100); color: var(--text-muted); text-align: center; font-weight: 400; cursor: pointer; padding: 0; }
.gt thead .gt-rh0 { top: 0; z-index: 8; }
.gt td.gt-ro { background: var(--grey-50); color: var(--text-muted); }
.gt tr.gt-p td { font-weight: 700; }
.gt td.gt-clash { color: var(--status-amber-text); }
.gt td.gt-sel { background: color-mix(in srgb, var(--brand-blue) 14%, var(--surface)); }
.gt td.gt-act { outline: 2px solid var(--brand-blue); outline-offset: -2px; background: var(--surface); }
.gt td.gt-ed { padding: 0; overflow: visible; }
.gt td.gt-ed input, .gt td.gt-ed select { width: 100%; height: 100%; box-sizing: border-box; border: 0; outline: 2px solid var(--brand-blue); outline-offset: -2px; background: var(--surface); color: var(--text); font: inherit; padding: 0 calc(7px * var(--gz)); user-select: text; }
.gt td.gt-last { position: relative; }
.gt .gt-fh { position: absolute; right: 0; bottom: 0; width: 9px; height: 9px; background: var(--brand-blue); border: 1px solid var(--surface); cursor: crosshair; z-index: 4; }
.gt .gt-cr { position: absolute; right: -3px; top: 0; bottom: 0; width: 8px; cursor: col-resize; z-index: 9; }
.gt .gt-cr:hover, .gt .gt-cr.gt-on { background: var(--brand-blue); opacity: .45; }
.gt thead th .gt-hl { pointer-events: none; }
.gt-eye, .gt-rb { border: 0; background: transparent; color: var(--text-muted); padding: 0; border-radius: var(--radius-sm); cursor: pointer; display: inline-flex; align-items: center; justify-content: center; }
.gt-eye { position: absolute; right: 6px; top: 4px; width: 18px; height: 18px; }
.gt-eye:hover, .gt-rb:hover { color: var(--brand-blue); background: var(--surface); }
.gt-eye .i, .gt-rb .i { width: 14px; height: 14px; }
.gt-rb { display: none; width: 16px; height: 16px; }
.gt .gt-rh:hover .gt-rn, .gt .gt-rh:focus-within .gt-rn { display: none; }
.gt .gt-rh:hover .gt-rb, .gt .gt-rh:focus-within .gt-rb { display: inline-flex; }
.gt-rb.gt-del:hover { color: var(--status-red-text); }
.gt-menu { position: fixed; z-index: 70; min-width: 200px; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); box-shadow: var(--shadow); padding: 4px; }
.gt-menu button { display: block; width: 100%; text-align: left; border: 0; background: transparent; color: var(--text); padding: 6px 10px; border-radius: var(--radius-sm); font: inherit; cursor: pointer; }
.gt-menu button:hover, .gt-menu button:focus-visible { background: var(--grey-100); outline: 0; }
.gt-menu button.gt-danger { color: var(--status-red-text); }
.gt-menu hr { border: 0; border-top: 1px solid var(--border); margin: 4px 0; }
`;
