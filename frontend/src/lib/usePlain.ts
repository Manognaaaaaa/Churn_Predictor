import { useEffect, useMemo, useState } from "react";
import { usePortfolio } from "../api";
import { buildSegmentLabeler } from "./plain";

/** Segment labeller built from the real segment list so group letters are consistent on every page. */
export function useSegmentLabel() {
  const portfolio = usePortfolio();
  return useMemo(
    () => buildSegmentLabeler((portfolio.data?.by_segment ?? []).map((s) => s.segment_name)),
    [portfolio.data],
  );
}

export function useNarrow(max = 520): boolean {
  const query = `(max-width: ${max}px)`;
  const [narrow, setNarrow] = useState(() => window.matchMedia(query).matches);
  useEffect(() => {
    const m = window.matchMedia(query);
    const on = () => setNarrow(m.matches);
    m.addEventListener("change", on);
    return () => m.removeEventListener("change", on);
  }, [query]);
  return narrow;
}
