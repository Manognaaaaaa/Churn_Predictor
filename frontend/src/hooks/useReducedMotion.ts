import { useEffect, useState } from "react";

const Q = "(prefers-reduced-motion: reduce)";

/** True when the visitor asked for less motion. Tweens jump to the end, the intro is skipped, the billboard stops. */
export function useReducedMotion(): boolean {
  const [r, setR] = useState(() => typeof window !== "undefined" && window.matchMedia(Q).matches);
  useEffect(() => {
    const m = window.matchMedia(Q);
    const on = () => setR(m.matches);
    m.addEventListener("change", on);
    return () => m.removeEventListener("change", on);
  }, []);
  return r;
}
