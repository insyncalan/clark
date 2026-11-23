// Test-only: stands in for preact/hooks so the Feedback tag component can be called as a plain function in node (no DOM, no effects).
export const useState = (v) => [typeof v === "function" ? v() : v, () => {}];
export const useRef = (v) => ({ current: v === undefined ? null : v });
export const useEffect = () => {};
export const useMemo = (f) => f();
