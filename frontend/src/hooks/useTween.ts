import { useEffect, useRef, useState } from "react";
import { useReducedMotion } from "./useReducedMotion";

const easeOutCubic = (t: number) => 1 - Math.pow(1 - t, 3);

/** Eased value that follows `target` over `ms` (rAF, ease-out-cubic). Jumps when motion is reduced. */
export function useTween(target: number, ms = 700): number {
  const reduced = useReducedMotion();
  const [v, setV] = useState(reduced ? target : 0);
  const cur = useRef(v);
  cur.current = v;
  useEffect(() => {
    if (reduced || ms <= 0) { setV(target); return; }
    const from = cur.current;
    if (from === target) return;
    let raf = 0, t0: number | null = null;
    const step = (ts: number) => {
      if (t0 == null) t0 = ts;
      const t = Math.min(1, (ts - t0) / ms);
      setV(from + (target - from) * easeOutCubic(t));
      if (t < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [target, ms, reduced]);
  return v;
}
