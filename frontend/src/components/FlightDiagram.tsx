import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { full, short } from "../lib/format";
import { offerColor, offerLabel } from "../lib/plain";
import { useReducedMotion } from "../hooks/useReducedMotion";

interface Target { offer: string; customers: number; spend: number; kept: number }

const W = 580;
const DOTS = 45;

/** Glowing dots fly from the budget bar to each offer type. Each total fades in when the dots arrive. */
export function FlightDiagram({ targets, budget, runId }: { targets: Target[]; budget: number; runId: number }) {
  const reduced = useReducedMotion();
  const box = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);
  const [arrived, setArrived] = useState(reduced);
  const n = Math.max(1, targets.length);
  const H = 70 + n * 76;
  const mid = H / 2;
  const ys = targets.map((_, k) => 45 + k * 76);
  const path = (y: number) => `M24 ${mid} C 240 ${mid}, 260 ${y}, 436 ${y}`;

  useLayoutEffect(() => {
    const el = box.current?.parentElement;
    if (!el) return;
    const on = () => setScale(Math.min(1, el.clientWidth / W));
    on();
    const ro = new ResizeObserver(on);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // new budget or strategy: hide the totals again; "Allocate budget" (runId) flies the dots and reveals them
  useEffect(() => { setArrived(reduced); }, [budget, targets.length, reduced]);
  useEffect(() => {
    if (!runId) return;
    setArrived(reduced);
    if (reduced) return;
    const t = window.setTimeout(() => setArrived(true), 2300);
    return () => window.clearTimeout(t);
  }, [runId, reduced]);

  return (
    <div style={{ width: "100%", height: H * scale }}>
      <div ref={box} style={{ position: "relative", width: W, height: H, transform: `scale(${scale})`, transformOrigin: "top left" }}>
        <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} aria-hidden="true" style={{ position: "absolute", inset: 0 }}>
          {ys.map((y, k) => <path key={k} d={path(y)} fill="none" stroke="rgba(var(--line-rgb), .2)" strokeWidth={1.5} />)}
          <rect x="18" y={mid - 30} width="6" height="60" rx="3" fill="var(--blue-200)" />
        </svg>
        <div style={{ position: "absolute", left: 34, top: mid - 15, fontSize: 13, color: "var(--blue-100)", fontWeight: 500 }}>{short(budget)}</div>
        {targets.map((t, k) => (
          <div key={t.offer} style={{ position: "absolute", left: 444, top: ys[k] - 22, display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ width: 8, height: 38, borderRadius: 3, background: offerColor(t.offer) }} />
            <div style={{ display: "flex", flexDirection: "column", lineHeight: "17px" }}>
              <span style={{ fontSize: 12, color: "var(--ink-muted)", maxWidth: 130, lineHeight: "15px" }}>{offerLabel(t.offer)}</span>
              <span style={{ fontWeight: 600, fontSize: 16, opacity: arrived ? 1 : 0, transform: arrived ? "none" : "translateY(6px)", transition: "opacity .5s, transform .6s var(--ease)" }}>+{short(t.kept)}</span>
              <span style={{ fontSize: 11, color: "var(--ink-faint)", opacity: arrived ? 1 : 0, transition: "opacity .5s" }}>{full(t.customers)} customers</span>
            </div>
          </div>
        ))}
        {runId > 0 && !reduced && targets.length > 0 &&
          Array.from({ length: DOTS }, (_, i) => {
            const k = i % targets.length;
            const c = offerColor(targets[k].offer);
            return (
              <div
                key={`${runId}-${i}`} className="fly" aria-hidden="true"
                style={{ position: "absolute", left: 0, top: 0, width: 6, height: 6, margin: "-3px 0 0 -3px", borderRadius: 999, background: c, boxShadow: `0 0 12px ${c}`, offsetPath: `path('${path(ys[k])}')`, offsetRotate: "0deg", animationDelay: `${Math.floor(i / targets.length) * 70 + (i % targets.length) * 25}ms` }}
              />
            );
          })}
      </div>
    </div>
  );
}
