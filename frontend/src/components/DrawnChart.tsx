import { useEffect, useMemo, useState } from "react";
import { useReducedMotion } from "../hooks/useReducedMotion";

interface Pt { x: number; y: number; n?: number }

const VW = 560, VH = 320, L = 58, R = 18, T = 18, B = 52;
const sx = (v: number) => L + v * (VW - L - R);
const sy = (v: number) => VH - B - v * (VH - T - B);
const TICKS = [0, 0.25, 0.5, 0.75, 1];

/** Line that draws itself, with a crosshair that snaps to the nearest point. Both axes run 0 to 100%. */
export function DrawnChart({ points, xLabel, yLabel, lineName, refName, label }: { points: Pt[]; xLabel: string; yLabel: string; lineName: string; refName: string; label: string }) {
  const reduced = useReducedMotion();
  const [on, setOn] = useState(reduced);
  const [hi, setHi] = useState(-1);
  const [replay, setReplay] = useState(0);
  const pts = useMemo(() => [...points].sort((a, b) => a.x - b.x), [points]);
  const path = pts.map((p, k) => `${k ? "L" : "M"}${sx(p.x).toFixed(1)} ${sy(p.y).toFixed(1)}`).join(" ");
  const area = pts.length ? `${path} L${sx(pts[pts.length - 1].x).toFixed(1)} ${sy(0)} L${sx(pts[0].x).toFixed(1)} ${sy(0)} Z` : "";

  useEffect(() => {
    if (reduced) { setOn(true); return; }
    setOn(false);
    const t = window.setTimeout(() => setOn(true), 80);
    return () => window.clearTimeout(t);
  }, [reduced, replay, points]);

  const near = (clientX: number, rect: DOMRect) => {
    const vx = ((clientX - rect.left) / rect.width) * VW;
    let best = 0;
    pts.forEach((p, k) => { if (Math.abs(sx(p.x) - vx) < Math.abs(sx(pts[best].x) - vx)) best = k; });
    return best;
  };
  const h = hi >= 0 ? pts[hi] : null;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 4 }}>
        <button className="ghost" onClick={() => setReplay((r) => r + 1)}>Replay</button>
      </div>
      <div style={{ position: "relative" }}>
        <svg
          viewBox={`0 0 ${VW} ${VH}`} role="img" aria-label={label} tabIndex={0}
          onMouseMove={(e) => setHi(near(e.clientX, e.currentTarget.getBoundingClientRect()))} onMouseLeave={() => setHi(-1)}
          onKeyDown={(e) => {
            if (e.key === "ArrowRight") { e.preventDefault(); setHi((k) => Math.min(pts.length - 1, k + 1)); }
            if (e.key === "ArrowLeft") { e.preventDefault(); setHi((k) => Math.max(0, k < 0 ? 0 : k - 1)); }
            if (e.key === "Escape") setHi(-1);
          }}
          onBlur={() => setHi(-1)}
          style={{ width: "100%", height: "auto", display: "block", cursor: "crosshair", borderRadius: 8 }}
        >
          <defs>
            <linearGradient id="dc-area" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="var(--blue-500)" stopOpacity={0.35} /><stop offset="1" stopColor="var(--blue-500)" stopOpacity={0} /></linearGradient>
          </defs>
          {TICKS.map((t) => (
            <g key={t}>
              <line x1={L} x2={VW - R} y1={sy(t)} y2={sy(t)} stroke={t === 0 ? "var(--line-strong)" : "var(--grid-line)"} />
              <text x={L - 10} y={sy(t) + 4} fill="var(--ink-muted)" fontSize={11} textAnchor="end">{Math.round(t * 100)}%</text>
              <text x={sx(t)} y={VH - B + 18} fill="var(--ink-muted)" fontSize={11} textAnchor="middle">{Math.round(t * 100)}%</text>
            </g>
          ))}
          <text x={(L + VW - R) / 2} y={VH - 8} fill="var(--ink-soft)" fontSize={12} textAnchor="middle">{xLabel}</text>
          <text transform={`translate(14 ${(T + VH - B) / 2}) rotate(-90)`} fill="var(--ink-soft)" fontSize={12} textAnchor="middle">{yLabel}</text>
          <line x1={sx(0)} y1={sy(0)} x2={sx(1)} y2={sy(1)} stroke="var(--ink-muted)" strokeWidth={1.5} strokeDasharray="5 5" />
          <path d={area} fill="url(#dc-area)" style={{ opacity: on ? 1 : 0, transition: reduced ? "none" : "opacity 1s ease .9s" }} />
          <path d={path} pathLength={1} className={on ? "draw-line on" : "draw-line"} fill="none" stroke="var(--blue-200)" strokeWidth={2.5} strokeLinejoin="round" strokeLinecap="round" />
          {pts.map((p, k) => <circle key={k} cx={sx(p.x)} cy={sy(p.y)} r={3} fill="var(--bg)" stroke="var(--blue-200)" strokeWidth={1.5} style={{ opacity: on ? 1 : 0, transition: reduced ? "none" : `opacity .4s ease ${0.9 + k * 0.05}s` }} />)}
          {h && (
            <g>
              <line x1={sx(h.x)} x2={sx(h.x)} y1={T} y2={VH - B} stroke="var(--blue-100)" strokeDasharray="3 4" style={{ transition: "all .15s" }} />
              <circle cx={sx(h.x)} cy={sy(h.y)} r={6} fill="var(--bg-raised)" stroke="var(--blue-100)" strokeWidth={3} style={{ transition: "all .15s" }} />
            </g>
          )}
        </svg>
        {h && (
          <div role="status" style={{ position: "absolute", left: `${(sx(h.x) / VW) * 100}%`, top: 0, transform: `translate(${h.x > 0.6 ? "-105%" : "8px"}, 4px)`, background: "var(--bg-raised)", border: "1px solid var(--line-strong)", borderRadius: 8, padding: "8px 10px", fontSize: 12, pointerEvents: "none", whiteSpace: "nowrap" }}>
            <div style={{ color: "var(--ink-muted)" }}>Predicted {Math.round(h.x * 100)}% chance of leaving</div>
            <div style={{ fontWeight: 600 }}>{(h.y * 100).toFixed(1)}% actually left{h.n ? ` (${h.n.toLocaleString("en-US")} customers)` : ""}</div>
          </div>
        )}
      </div>
      <div style={{ display: "flex", gap: 18, flexWrap: "wrap", fontSize: 12, color: "var(--ink-muted)", marginTop: 6 }}>
        <span><span aria-hidden="true" style={{ display: "inline-block", width: 18, borderTop: "2px solid var(--blue-200)", verticalAlign: "middle", marginRight: 6 }} />{lineName}</span>
        <span><span aria-hidden="true" style={{ display: "inline-block", width: 18, borderTop: "2px dashed var(--ink-muted)", verticalAlign: "middle", marginRight: 6 }} />{refName}</span>
      </div>
    </div>
  );
}
