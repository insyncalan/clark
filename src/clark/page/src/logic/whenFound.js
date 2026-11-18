// Look for something that is drawn a little later: try now and on each frame after, a bounded number of times, then give up.
export function whenFound(find, raf, tries = 30) {
  let n = 0;
  const step = () => {
    const el = find();
    if (el) return el;
    if (++n >= tries) return null;
    raf(step);
    return null;
  };
  return step();
}
