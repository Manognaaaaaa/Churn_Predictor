import { useEffect, useState } from "react";
import { useReducedMotion } from "../hooks/useReducedMotion";
import { pct1 } from "../lib/format";

export interface ModelRow { name: string; label: string; pr: number; brier: number; ece: number }

type Key = "pr" | "brier" | "ece";
const MEASURES: { key: Key; title: string; question: string; better: "higher" | "lower"; fmt: (n: number) => string }[] = [
  { key: "pr", title: "Finding the leavers", question: "PR-AUC: how well real leavers sit at the top of the list.", better: "higher", fmt: pct1 },
  { key: "brier", title: "Error in the percentages", question: "Brier score: average squared distance between the percentage and what happened.", better: "lower", fmt: (n) => n.toFixed(3) },
  { key: "ece", title: "Gap from reality", question: "ECE: average gap between the predicted chance and the share who really left.", better: "lower", fmt: pct1 },
];

function winner(rows: ModelRow[], key: Key, better: "higher" | "lower"): ModelRow {
  return rows.reduce((a, b) => ((better === "higher" ? b[key] > a[key] : b[key] < a[key]) ? b : a));
}

function Bars({ rows, chosen, measure, on }: { rows: ModelRow[]; chosen: string; measure: (typeof MEASURES)[number]; on: boolean }) {
  const { key, better, fmt } = measure;
  const sorted = [...rows].sort((a, b) => (better === "higher" ? b[key] - a[key] : a[key] - b[key]));
  const max = Math.max(...rows.map((r) => r[key]));
  const top = sorted[0].name;
  return (
    <div className="panel" style={{ padding: "18px 18px 14px", borderRadius: 14, minWidth: 0 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 8, flexWrap: "wrap" }}>
        <h3 style={{ fontSize: 15, fontWeight: 600, letterSpacing: "-0.01em" }}>{measure.title}</h3>
        <span style={{ fontSize: 11, color: "var(--ink-muted)", border: "1px solid var(--line-strong)", borderRadius: 999, padding: "1px 8px" }}>{better === "higher" ? "Higher is better" : "Lower is better"}</span>
      </div>
      <p style={{ fontSize: 12, color: "var(--ink-faint)", margin: "4px 0 12px" }}>{measure.question}</p>
      <ol style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 10 }}>
        {sorted.map((r, k) => {
          const isChosen = r.name === chosen;
          return (
            <li key={r.name}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 8, fontSize: 13, color: isChosen ? "var(--blue-100)" : "var(--ink-soft)", fontWeight: isChosen ? 600 : 400 }}>
                <span style={{ minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {r.label}
                  {r.name === top && <span style={{ fontSize: 11, fontWeight: 500, color: "var(--ink-muted)", marginLeft: 8 }}>best here</span>}
                </span>
                <span style={{ fontVariantNumeric: "tabular-nums" }}>{fmt(r[key])}</span>
              </div>
              <div aria-hidden="true" style={{ height: 8, borderRadius: 4, background: "rgba(var(--line-rgb), .12)", marginTop: 4, overflow: "hidden" }}>
                <div style={{ height: "100%", borderRadius: 4, width: on ? `${(r[key] / max) * 100}%` : 0, background: isChosen ? "linear-gradient(90deg, var(--blue-500), var(--blue-100))" : "var(--blue-400)", transition: `width .9s var(--ease) ${k * 0.06}s` }} />
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

const VW = 560, VH = 330, L = 56, R = 20, T = 22, B = 50;

/** Ranking (up is better) against calibration gap (left is better): the best model sits top left. */
function Scatter({ rows, chosen }: { rows: ModelRow[]; chosen: string }) {
  const xMax = Math.ceil((Math.max(...rows.map((r) => r.ece)) * 100) / 2) * 2 / 100 || 0.02;
  const yMin = Math.floor(Math.min(...rows.map((r) => r.pr)) * 10) / 10;
  const yMax = Math.max(yMin + 0.1, Math.ceil(Math.max(...rows.map((r) => r.pr)) * 10) / 10);
  const sx = (v: number) => L + (v / xMax) * (VW - L - R);
  const sy = (v: number) => VH - B - ((v - yMin) / (yMax - yMin)) * (VH - T - B);
  const xt = Array.from({ length: 5 }, (_, k) => (xMax * k) / 4);
  const yt = Array.from({ length: Math.round((yMax - yMin) * 10) + 1 }, (_, k) => yMin + k / 10);

  // Models that land on the same spot (the two logistic regressions) share one label.
  const groups: { x: number; y: number; names: string[]; chosen: boolean }[] = [];
  for (const r of rows) {
    const g = groups.find((q) => Math.hypot(sx(q.x) - sx(r.ece), sy(q.y) - sy(r.pr)) < 10);
    if (g) { g.names.push(r.label); g.chosen ||= r.name === chosen; }
    else groups.push({ x: r.ece, y: r.pr, names: [r.label], chosen: r.name === chosen });
  }
  // Labels sit right of the dot, or left near the right edge; nudge apart when two would collide.
  const placed = groups
    .map((g) => ({ ...g, left: sx(g.x) > VW * 0.62, ly: sy(g.y) + 4 }))
    .sort((a, b) => a.ly - b.ly);
  for (let k = 1; k < placed.length; k++) {
    const a = placed[k - 1], b = placed[k];
    if (Math.abs(sx(a.x) - sx(b.x)) < 150 && b.ly - a.ly < 14) { a.ly -= 6; b.ly = a.ly + 16; }
  }
  const text = `Ranking against calibration gap for each model. ${rows.map((r) => `${r.label}: PR-AUC ${pct1(r.pr)}, gap ${pct1(r.ece)}`).join("; ")}.`;

  return (
    <svg viewBox={`0 0 ${VW} ${VH}`} role="img" aria-label={text} style={{ width: "100%", height: "auto", display: "block" }}>
      <rect x={L} y={T} width={(VW - L - R) * 0.4} height={(VH - T - B) * 0.4} rx={6} fill="rgba(var(--blue-500-rgb), .10)" />
      <text x={L + 8} y={T + 15} fill="var(--ink-muted)" fontSize={11}>Best corner</text>
      {yt.map((t) => (
        <g key={`y${t}`}>
          <line x1={L} x2={VW - R} y1={sy(t)} y2={sy(t)} stroke="var(--grid-line)" />
          <text x={L - 8} y={sy(t) + 4} fill="var(--ink-muted)" fontSize={11} textAnchor="end">{Math.round(t * 100)}%</text>
        </g>
      ))}
      {xt.map((t) => <text key={`x${t}`} x={sx(t)} y={VH - B + 18} fill="var(--ink-muted)" fontSize={11} textAnchor="middle">{(t * 100).toFixed(t * 100 % 1 ? 1 : 0)}%</text>)}
      <line x1={L} x2={VW - R} y1={VH - B} y2={VH - B} stroke="var(--line-strong)" />
      <line x1={L} x2={L} y1={T} y2={VH - B} stroke="var(--line-strong)" />
      <text x={(L + VW - R) / 2} y={VH - 8} fill="var(--ink-soft)" fontSize={12} textAnchor="middle">Gap from reality (ECE), left is better</text>
      <text transform={`translate(14 ${(T + VH - B) / 2}) rotate(-90)`} fill="var(--ink-soft)" fontSize={12} textAnchor="middle">Finding leavers (PR-AUC), up is better</text>
      {placed.map((g) => (
        <g key={g.names.join()}>
          <title>{`${g.names.join(", ")}: PR-AUC ${pct1(g.y)}, gap ${pct1(g.x)}`}</title>
          <circle cx={sx(g.x)} cy={sy(g.y)} r={g.chosen ? 8 : 6} fill={g.chosen ? "var(--blue-100)" : "var(--blue-400)"} stroke="var(--bg-raised)" strokeWidth={2} />
          {g.chosen && <circle cx={sx(g.x)} cy={sy(g.y)} r={13} fill="none" stroke="var(--blue-100)" strokeOpacity={0.5} />}
          <text x={sx(g.x) + (g.left ? -14 : 14)} y={g.ly} textAnchor={g.left ? "end" : "start"} fontSize={12} fontWeight={g.chosen ? 600 : 400} fill={g.chosen ? "var(--blue-100)" : "var(--ink-soft)"}>
            {g.names.length > 1 ? "Logistic regression (MLE and MAP)" : g.names[0]}{g.chosen ? " (chosen)" : ""}
          </text>
        </g>
      ))}
    </svg>
  );
}

export function ModelCompare({ rows, chosen, test }: { rows: ModelRow[]; chosen: string; test: Record<string, number> }) {
  const reduced = useReducedMotion();
  const [on, setOn] = useState(reduced);
  useEffect(() => {
    const t = window.setTimeout(() => setOn(true), 80);
    return () => window.clearTimeout(t);
  }, []);
  if (rows.length < 2) return null;

  const best = rows.find((r) => r.name === chosen) ?? winner(rows, "pr", "higher");
  const byPr = [...rows].sort((a, b) => b.pr - a.pr);
  const runner = byPr.find((r) => r.name !== best.name)!;
  const worst = byPr[byPr.length - 1];
  const eceTop = winner(rows, "ece", "lower");
  const brierTop = winner(rows, "brier", "lower");
  const beatenOn = [brierTop.name !== best.name ? "Brier" : null, eceTop.name !== best.name ? "ECE" : null].filter(Boolean);

  return (
    <section className="panel" style={{ padding: 24 }} aria-labelledby="cmp-title">
      <h2 id="cmp-title" style={{ fontSize: 18, fontWeight: 600, letterSpacing: "-0.02em" }}>Which model is best, and how do we know?</h2>
      <p style={{ fontSize: 14, color: "var(--ink-soft)", margin: "8px 0 16px", maxWidth: 820, lineHeight: "22px" }}>
        {rows.length} models were trained on the same customers and compared on validation customers none of them had seen. <b style={{ color: "var(--blue-100)" }}>{best.label}</b> was chosen because it is best at putting real leavers at the top of the list ({pct1(best.pr)}), {runner.pr / best.pr > 0.98 ? "narrowly " : ""}ahead of {runner.label} ({pct1(runner.pr)}) and well ahead of {worst.label} ({pct1(worst.pr)}).
      </p>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))", gap: 14 }}>
        {MEASURES.map((m) => <Bars key={m.key} rows={rows} chosen={best.name} measure={m} on={on} />)}
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 24, marginTop: 22, alignItems: "center" }}>
        <div style={{ flex: "1.3 1 380px", minWidth: 0 }}>
          <h3 style={{ fontSize: 15, fontWeight: 600 }}>Both things at once</h3>
          <p style={{ fontSize: 12, color: "var(--ink-faint)", margin: "4px 0 8px" }}>A good model is high (finds the leavers) and to the left (its percentages can be trusted).</p>
          <Scatter rows={rows} chosen={best.name} />
        </div>
        <div style={{ flex: "1 1 280px", minWidth: 0, fontSize: 14, color: "var(--ink-soft)", lineHeight: "22px", display: "flex", flexDirection: "column", gap: 10 }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, color: "var(--ink)" }}>How the winner was picked</h3>
          <p><b>1. Ranking decides.</b> The model with the highest PR-AUC on validation wins, because the budget goes to the customers at the top of the list.</p>
          {beatenOn.length > 0 ? (
            <p><b>2. It is not best at everything.</b> {eceTop.label} has the smallest gap from reality ({pct1(eceTop.ece)} against {pct1(best.ece)} for {best.label}){brierTop.name !== best.name ? ` and ${brierTop.name === eceTop.name ? "also " : `${brierTop.label} has `}the lowest Brier score` : ""}. With rankings this close, {runner.label} would be a reasonable choice too.</p>
          ) : (
            <p><b>2. It also has the most accurate percentages</b> of all the models, on both Brier and ECE.</p>
          )}
          {test.ece_raw != null && test.ece_calibrated != null && (
            <p><b>3. Calibration closes the gap.</b> The chosen model's percentages are corrected after training. On held-out test customers that cut its gap from {pct1(test.ece_raw)} to {pct1(test.ece_calibrated)}.</p>
          )}
        </div>
      </div>
    </section>
  );
}
