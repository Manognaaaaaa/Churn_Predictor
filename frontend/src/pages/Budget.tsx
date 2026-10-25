import { useEffect, useMemo, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { allocate, useCurve } from "../api";
import type { CurvePoint } from "../api";
import { full, short } from "../lib/format";
import { useTween } from "../hooks/useTween";
import { Odometer } from "../components/Odometer";
import { FlightDiagram } from "../components/FlightDiagram";
import { Message } from "../components/bits";
import { useApp } from "../state/app";

const STRATEGIES = [
  { key: "segment_aware", label: "Best return", desc: "Most value kept per unit spent" },
  { key: "uniform", label: "Same for everyone", desc: "Even split across flagged customers" },
  { key: "risk_proportional", label: "Most at-risk first", desc: "Highest chance of leaving first" },
] as const;
const QUICK = [250_000, 500_000, 1_000_000, 2_000_000, 5_000_000];
const MIN = 100_000, MAX = 5_000_000;

function interpolate(points: CurvePoint[] | undefined, budget: number): number | null {
  if (!points?.length) return null;
  const hi = points.findIndex((p) => p.budget >= budget);
  if (hi <= 0) return points[Math.max(0, hi)].expected_revenue_saved;
  const a = points[hi - 1], b = points[hi];
  return a.expected_revenue_saved + ((b.expected_revenue_saved - a.expected_revenue_saved) * (budget - a.budget)) / (b.budget - a.budget);
}

function StratCard({ s, selected, points, onPick, budget }: { s: (typeof STRATEGIES)[number]; selected: boolean; points: CurvePoint[] | undefined; onPick: () => void; budget: number }) {
  const v = interpolate(points, budget);
  const shown = useTween(v ?? 0, 700);
  return (
    <button className="strat" role="radio" aria-checked={selected} onClick={onPick}>
      <span style={{ display: "block", position: "relative", borderRadius: 12, padding: 1, overflow: "hidden", background: "rgba(var(--line-rgb), .16)" }}>
        {selected && <span className="spin" aria-hidden="true" style={{ position: "absolute", inset: "-150%", background: "conic-gradient(from 0deg, transparent 0 72%, rgba(var(--blue-200-rgb), .9) 86%, var(--ink) 92%, transparent 100%)" }} />}
        <span style={{ display: "flex", position: "relative", borderRadius: 11, background: selected ? "var(--budget-strat-on)" : "var(--budget-strat-off)", padding: "14px 16px", justifyContent: "space-between", gap: 12, alignItems: "baseline", transition: "background .3s" }}>
          <span style={{ display: "flex", flexDirection: "column" }}>
            <span style={{ fontWeight: 500 }}>{s.label}</span>
            <span style={{ fontSize: 13, color: "var(--ink-muted)" }}>{s.desc}</span>
          </span>
          <span style={{ fontSize: 20, fontWeight: 500, letterSpacing: "-0.03em", color: selected ? "var(--blue-100)" : "var(--ink-muted)", whiteSpace: "nowrap" }}>
            {v == null ? "…" : `+${short(shown)}`}
          </span>
        </span>
      </span>
    </button>
  );
}

export default function Budget() {
  const [budget, setBudget] = useState(1_000_000);
  const [strat, setStrat] = useState<(typeof STRATEGIES)[number]["key"]>("segment_aware");
  const [debounced, setDebounced] = useState(budget);
  const [runId, setRunId] = useState(0);
  const odo = useOdoSize();
  const { segLabel } = useApp();

  useEffect(() => { const t = window.setTimeout(() => setDebounced(budget), 250); return () => window.clearTimeout(t); }, [budget]);

  const alloc = useQuery({
    queryKey: ["alloc", debounced, strat],
    queryFn: ({ signal }) => allocate(debounced, strat, signal),
    placeholderData: keepPreviousData,
  });
  const curves = [useCurve("segment_aware"), useCurve("uniform"), useCurve("risk_proportional")];
  const curve = curves[STRATEGIES.findIndex((s) => s.key === strat)];
  const a = alloc.data;

  const fromCurve = interpolate(curve.data?.points, budget);
  const kept = a ? a.expected_revenue_saved : fromCurve ?? 0;
  const spent = a ? a.spent : budget;
  const net = useTween(Math.max(0, kept - spent), 700);
  const ratio = useTween(spent > 0 ? kept / spent : 0, 700);
  const reached = useTween(a?.n_targeted ?? 0, 700);
  const budgetShown = useTween(budget, 400);
  const pctFill = ((budget - MIN) / (MAX - MIN)) * 100;
  const targets = useMemo(
    () => (a?.by_offer ?? []).map((o) => ({ offer: o.offer, customers: o.customers, spend: o.spend, kept: o.expected_revenue_saved })).sort((x, y) => y.kept - x.kept),
    [a],
  );

  return (
    <div style={{ padding: "56px clamp(16px, 3.4vw, 48px)", display: "flex", flexDirection: "column", gap: 28 }}>
      <div>
        <div style={{ color: "var(--blue-200)", fontWeight: 500, fontSize: 13 }}>Retention budget</div>
        <h1 style={{ margin: "6px 0 0", fontWeight: 600, fontSize: "clamp(30px, 5vw, 44px)", lineHeight: 1.1, letterSpacing: "-0.04em", maxWidth: 760 }}>Where the money goes, and what comes back</h1>
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 20 }}>
        <section className="panel" style={{ flex: "1 1 420px", minWidth: 0, padding: 28, display: "flex", flexDirection: "column", gap: 14 }}>
          <label htmlFor="bud" style={{ color: "var(--ink-muted)", fontSize: 14 }}>Budget to spend</label>
          <div style={{ fontWeight: 300, fontSize: "clamp(44px, 9vw, 60px)", lineHeight: 1.1, letterSpacing: "-0.045em" }} aria-live="polite">{full(budgetShown)}</div>
          <input id="bud" type="range" min={MIN} max={MAX} step={50_000} value={budget} onChange={(e) => setBudget(Number(e.target.value))} style={{ ["--pct" as string]: `${pctFill.toFixed(1)}%` }} aria-valuetext={`${full(budget)}`} />
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {QUICK.map((q) => <button key={q} className={budget === q ? "seg on" : "seg"} aria-pressed={budget === q} onClick={() => setBudget(q)}>{short(q).replace(".00", "")}</button>)}
          </div>
          <div style={{ fontSize: 13, color: "var(--ink-muted)", marginTop: 10 }}>Strategy</div>
          <div role="radiogroup" aria-label="Strategy" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {STRATEGIES.map((s, k) => <StratCard key={s.key} s={s} selected={strat === s.key} points={curves[k].data?.points} budget={budget} onPick={() => setStrat(s.key)} />)}
          </div>
          {curves.some((c) => c.isLoading) && <p style={{ fontSize: 12, color: "var(--ink-faint)" }}>The first visit runs the allocation solver for each strategy. This can take a minute.</p>}
        </section>

        <section style={{ flex: "1.3 1 540px", minWidth: 0, display: "flex", flexDirection: "column", gap: 20 }}>
          <div style={{ borderRadius: 16, padding: 28, background: "radial-gradient(ellipse 70% 90% at 90% 0%, rgba(var(--blue-500-rgb), .45), transparent 60%), linear-gradient(160deg, var(--budget-card-a), var(--budget-card-b))", border: "1px solid rgba(var(--blue-200-rgb), .22)", position: "relative", overflow: "hidden" }}>
            <div aria-hidden="true" style={{ position: "absolute", inset: 0, backgroundImage: "linear-gradient(rgba(var(--blue-100-rgb), .05) 1px, transparent 1px), linear-gradient(90deg, rgba(var(--blue-100-rgb), .05) 1px, transparent 1px)", backgroundSize: "32px 32px", WebkitMaskImage: "radial-gradient(ellipse at 90% 0%, #000, transparent 70%)", maskImage: "radial-gradient(ellipse at 90% 0%, #000, transparent 70%)" }} />
            <div style={{ color: "var(--blue-100)", position: "relative", fontSize: 14 }}>Value kept <span style={{ color: "var(--ink-muted)" }}>(yearly value that stays)</span></div>
            <div style={{ position: "relative", overflow: "hidden", maxWidth: "100%" }}>
              <Odometer value={kept} size={odo} height={Math.round(odo * 1.1)} />
            </div>
            <div style={{ position: "relative", display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 12, marginTop: 10, paddingTop: 16, borderTop: "1px solid rgba(var(--blue-200-rgb), .15)" }}>
              <div><div style={{ fontSize: 12, color: "var(--ink-muted)" }}>Net gain</div><div style={{ fontSize: 22, fontWeight: 500, letterSpacing: "-0.03em" }}>+{short(net)}</div></div>
              <div><div style={{ fontSize: 12, color: "var(--ink-muted)" }}>Back per 1 spent</div><div style={{ fontSize: 22, fontWeight: 500, letterSpacing: "-0.03em" }}>{ratio.toFixed(2)}</div></div>
              <div><div style={{ fontSize: 12, color: "var(--ink-muted)" }}>Customers reached</div><div style={{ fontSize: 22, fontWeight: 500, letterSpacing: "-0.03em" }}>{a ? full(reached) : "…"}</div></div>
            </div>
          </div>

          <div className="panel" style={{ padding: 24, display: "flex", flexDirection: "column", gap: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
              <div>
                <h2 style={{ fontSize: 17, fontWeight: 600, letterSpacing: "-0.02em" }}>Send the money out</h2>
                <div style={{ fontSize: 13, color: "var(--ink-muted)" }}>Watch the budget split across offers.</div>
              </div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <button className="cta" onClick={() => setRunId((r) => r + 1)} disabled={!a}>Allocate budget</button>
                <a className="ghost" style={{ height: 46, textDecoration: "none" }} href={`/allocate/export?budget=${debounced}&strategy=${strat}`} download="retention-offers.csv">Download list (CSV)</a>
              </div>
            </div>
            {alloc.isError && <Message>The allocation could not be calculated. Check that the API is running.</Message>}
            {a ? <FlightDiagram targets={targets} budget={spent} runId={runId} /> : !alloc.isError && <p style={{ color: "var(--ink-muted)" }}>Calculating…</p>}
          </div>
        </section>
      </div>

      <section className="panel" style={{ padding: 24, display: "flex", flexDirection: "column", gap: 14 }}>
        <div>
          <h2 style={{ fontSize: 17, fontWeight: 600, letterSpacing: "-0.02em" }}>Which customer groups get the money</h2>
          <div style={{ fontSize: 13, color: "var(--ink-muted)" }}>How this budget splits across customer groups with the chosen strategy.</div>
        </div>
        {(a?.by_segment ?? []).slice(0, 8).map((g, k, arr) => (
          <motion.div key={g.segment_name} layout style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
              <span style={{ fontWeight: 500 }}>{segLabel(g.segment_name)}</span>
              <span style={{ fontWeight: 500 }}>{short(g.spend)}</span>
            </div>
            <div style={{ height: 8, borderRadius: 999, background: "var(--track)", overflow: "hidden" }}>
              <div style={{ height: "100%", borderRadius: 999, width: `${(g.spend / Math.max(1, arr[0].spend)) * 100}%`, background: "linear-gradient(90deg, var(--blue-500), var(--blue-200))", transition: "width .7s var(--ease)" }} />
            </div>
            <div style={{ fontSize: 12, color: "var(--ink-muted)" }}>{full(g.customers)} customers, keeps about {short(g.expected_revenue_saved)}</div>
          </motion.div>
        ))}
      </section>
      <p style={{ fontSize: 12, color: "var(--ink-faint)" }}>Yearly value is the customer's estimated salary from the dataset. Offer effects are estimates: the project has no data from real offers.</p>
    </div>
  );
}

function useOdoSize(): number {
  const [w, setW] = useState(() => window.innerWidth);
  useEffect(() => { const on = () => setW(window.innerWidth); window.addEventListener("resize", on); return () => window.removeEventListener("resize", on); }, []);
  return w < 520 ? 44 : w < 900 ? 64 : 84;
}
