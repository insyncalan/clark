// Full width image (row 1223), Edit only: Crop. The whole image with a box (corner handles to resize, the box to move); Apply, Cancel or
// "Use the whole image". The box is fractions of the stored original; its arithmetic is logic/fullImageFrame.js's. Arrow keys move the box,
// with Shift they resize it; Enter applies, Esc cancels. Nothing is saved until Apply.
import { useRef, useState } from "preact/hooks";
import { UNRULED_WORDS as W } from "../../logic/fullImageWords.js";
import { startBox, moveBox, resizeBox, nudgeBox } from "../../logic/fullImageFrame.js";

const CORNERS = ["nw", "ne", "sw", "se"];

export function Crop({ src, info, start, onApply, onCancel, onWhole }) {
  const [box, setBox] = useState(startBox({ crop: start }));
  const area = useRef(null), drag = useRef(null);
  const down = (e, kind) => {
    e.preventDefault(); e.stopPropagation();
    e.currentTarget.setPointerCapture(e.pointerId);
    drag.current = { kind, x: e.clientX, y: e.clientY, box };
  };
  const move = (e) => {
    const d = drag.current;
    if (!d) return;
    const r = area.current.getBoundingClientRect();
    const dx = (e.clientX - d.x) / r.width, dy = (e.clientY - d.y) / r.height;
    setBox(d.kind === "move" ? moveBox(d.box, dx, dy) : resizeBox(d.box, d.kind, dx, dy));
  };
  const up = () => { drag.current = null; };
  const key = (e) => {
    if (e.key === "Escape") { e.preventDefault(); onCancel(); return; }
    if (e.key === "Enter") { e.preventDefault(); onApply(box); return; }
    const dir = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[e.key];
    if (!dir) return;
    e.preventDefault();
    setBox(nudgeBox(box, dir[0], dir[1], e.shiftKey));
  };
  const pc = (n) => `${(n * 100).toFixed(3)}%`;
  return (
    <div class="fi-crop">
      <div class="fi-crop-area" ref={area} style={{ width: `min(100%, calc(70vh * ${info.w / info.h}))`, aspectRatio: `${info.w} / ${info.h}` }}>
        <img src={src} alt="" draggable={false} />
        <div class="fi-crop-box" tabIndex={0} role="group" aria-label={W.cropBox} aria-description={W.cropHelp} data-crop-box
          style={{ left: pc(box.x), top: pc(box.y), width: pc(box.w), height: pc(box.h) }}
          onPointerDown={(e) => down(e, "move")} onPointerMove={move} onPointerUp={up} onPointerCancel={up} onKeyDown={key}>
          {CORNERS.map((c) => <span key={c} class={`fi-crop-h ${c}`} data-corner={c} title={W.corner[c]} onPointerDown={(e) => down(e, c)} onPointerMove={move} onPointerUp={up} onPointerCancel={up} />)}
        </div>
      </div>
      <p class="quiet fi-help">{W.cropHelp}</p>
      <div class="fi-crop-acts">
        <button type="button" class="btn sm" data-act="crop-apply" onClick={() => onApply(box)}>{W.apply}</button>
        <button type="button" class="btn sm quiet" data-act="crop-cancel" onClick={onCancel}>{W.cancel}</button>
        <button type="button" class="btn sm quiet" data-act="crop-whole" onClick={onWhole}>{W.whole}</button>
      </div>
    </div>
  );
}
